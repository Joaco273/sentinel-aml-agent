import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.connection import Base
from src.db.models import Account, Transaction, Alert
from src.db.seed_data import seed_database


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    seed_database(db)
    yield db
    db.close()


def test_seeded_accounts(test_db):
    accounts = test_db.query(Account).all()
    assert len(accounts) == 4
    account_ids = {a.account_id for a in accounts}
    assert "ACC-1001" in account_ids
    assert "ACC-1002" in account_ids
    assert "ACC-1003" in account_ids
    assert "ACC-1004" in account_ids


def test_seeded_alerts(test_db):
    alerts = test_db.query(Alert).all()
    assert len(alerts) == 4
    alert_ids = {a.alert_id for a in alerts}
    assert "ALT-1002" in alert_ids

    alt2 = test_db.query(Alert).filter(Alert.alert_id == "ALT-1002").first()
    assert alt2.amount == 50000.0
    assert "unverified Cyprus IP" in alt2.trigger_reason
    assert alt2.status == "PENDING"


def test_anomaly_transactions(test_db):
    tx_anomaly = test_db.query(Transaction).filter(Transaction.transaction_id == "TX-1002-ANOMALY").first()
    assert tx_anomaly is not None
    assert tx_anomaly.amount == 50000.0
    assert tx_anomaly.location_country == "CYP"
    assert tx_anomaly.is_flagged is True
