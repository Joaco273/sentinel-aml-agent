import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.connection import Base
from src.db.seed_data import seed_database
from src.tools.transaction_tools import fetch_transaction_history, get_transaction_history
from src.tools.sanctions_tools import perform_sanctions_check, check_sanctions_watchlist


from sqlalchemy.pool import StaticPool

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

    # Patch SessionLocal inside transaction_tools to use test in-memory DB
    import src.tools.transaction_tools as tt
    monkeypatch.setattr(tt, "SessionLocal", TestingSessionLocal)

    yield db
    db.close()


def test_fetch_transaction_history(test_db):
    res = fetch_transaction_history("ACC-1001")
    assert res["account_id"] == "ACC-1001"
    assert res["30_day_frequency"] > 0
    assert res["30_day_avg_amount"] > 0
    assert len(res["recent_transactions"]) > 0


def test_sanctions_watchlist_hit():
    res = perform_sanctions_check("Vladimir Petrov")
    assert res["has_match"] is True
    assert res["status"] == "FLAGGED"
    assert res["highest_risk_level"] == "CRITICAL"


def test_sanctions_watchlist_clear():
    res = perform_sanctions_check("Alice Vance")
    assert res["has_match"] is False
    assert res["status"] == "CLEAR"
