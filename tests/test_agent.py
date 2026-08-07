import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from langgraph.types import Command

from src.db.connection import Base
from src.db.seed_data import seed_database
from src.agent.workflow import build_workflow
from src.agent.schemas import RiskAssessment


@pytest.fixture
def test_db(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    seed_database(db)

    # Patch SessionLocal in nodes and tools to use in-memory DB
    import src.agent.nodes as nodes
    import src.tools.transaction_tools as tt

    monkeypatch.setattr(nodes, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tt, "SessionLocal", TestingSessionLocal)

    yield db
    db.close()


def test_low_risk_auto_close_workflow(test_db):
    app = build_workflow()
    thread_id = "test-thread-low-risk"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "alert_id": "ALT-1001",
        "logs": []
    }

    # Run workflow
    final_state = app.invoke(initial_state, config=config)

    assert final_state["status"] == "AUTO_CLOSED"
    assert final_state["risk_score"] <= 70
    assert final_state.get("sar_document") is None
    assert any("Auto-closing alert" in log for log in final_state["logs"])


def test_high_risk_hitl_approval_workflow(test_db):
    app = build_workflow()
    thread_id = "test-thread-high-risk"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "alert_id": "ALT-1002",
        "logs": []
    }

    # 1. First invocation should hit interrupt at human_review node
    interrupted_state = app.invoke(initial_state, config=config)

    # Inspect current state: workflow should be paused awaiting human review
    current_snapshot = app.get_state(config)
    assert len(current_snapshot.next) > 0
    assert current_snapshot.next[0] == "human_review"
    assert interrupted_state["risk_score"] > 70

    # 2. Resume workflow with analyst approval
    resumed_state = app.invoke(
        Command(resume={"decision": "approve", "comment": "Approved by Compliance Director"}),
        config=config
    )

    assert resumed_state["status"] == "APPROVED_SAR"
    assert resumed_state.get("sar_document") is not None
    assert "SUSPICIOUS ACTIVITY REPORT (SAR)" in resumed_state["sar_document"]
    assert "Approved by Compliance Director" in resumed_state["sar_document"]


def test_gemini_scoring_and_fallback(test_db, monkeypatch):
    import src.agent.nodes as nodes

    # Case 1: No API key -> Fallback logging
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    app = build_workflow()
    state1 = app.invoke({"alert_id": "ALT-1001", "logs": []}, config={"configurable": {"thread_id": "t-gem-1"}})
    assert any("GEMINI_API_KEY / GOOGLE_API_KEY not found" in log for log in state1["logs"])
    assert any("[Rule Engine (Fallback)]" in log for log in state1["logs"])

    # Case 2: Mocked Gemini API call -> Gemini engine logging
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")

    mock_assessment = RiskAssessment(
        risk_score=85,
        risk_factors=["Gemini LLM detected suspicious activity"],
        rationale="Gemini LLM flagged severe offshore risk",
        recommended_action="HUMAN_REVIEW"
    )

    monkeypatch.setattr(nodes, "evaluate_risk_with_gemini", lambda state: mock_assessment)

    state2 = app.invoke({"alert_id": "ALT-1002", "logs": []}, config={"configurable": {"thread_id": "t-gem-2"}})
    assert any("Gemini LLM Engine active" in log for log in state2["logs"])
    assert any("[Gemini LLM (gemini-2.5-flash)]" in log for log in state2["logs"])
    assert state2["risk_score"] == 85
