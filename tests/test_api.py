import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.connection import Base, get_db
from src.db.seed_data import seed_database
from src.api.app import app


from sqlalchemy.pool import StaticPool

@pytest.fixture
def test_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    seed_database(db)

    # Patch get_db dependency in FastAPI app
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Patch SessionLocal in nodes and tools
    import src.agent.nodes as nodes
    import src.tools.transaction_tools as tt

    monkeypatch.setattr(nodes, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(tt, "SessionLocal", TestingSessionLocal)

    client = TestClient(app)
    yield client
    db.close()
    app.dependency_overrides.clear()


def test_api_list_alerts(test_client):
    response = test_client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    alert_ids = [a["alert_id"] for a in data]
    assert "ALT-1002" in alert_ids


def test_api_investigate_and_approve(test_client):
    # 1. Trigger investigation for ALT-1002 (High risk $50k offshore wire)
    res_inv = test_client.post("/api/alerts/ALT-1002/investigate")
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert inv_data["risk_score"] > 70
    assert inv_data["is_awaiting_approval"] is True

    # 2. Submit approval review
    res_rev = test_client.post(
        "/api/alerts/ALT-1002/review",
        json={"decision": "approve", "comment": "Approved by Head of Compliance"}
    )
    assert res_rev.status_code == 200
    rev_data = res_rev.json()
    assert rev_data["status"] == "APPROVED_SAR"
    assert "Approved by Head of Compliance" in rev_data["sar_document"]
