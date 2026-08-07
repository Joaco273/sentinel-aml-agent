import datetime
from sqlalchemy.orm import Session
from src.db.models import Account, Transaction, Alert


def seed_database(db: Session):
    """Populates the database with synthetic accounts, transactions, and AML alerts."""

    # Clear existing data
    db.query(Alert).delete()
    db.query(Transaction).delete()
    db.query(Account).delete()
    db.commit()

    now = datetime.datetime.utcnow()

    # 1. Accounts
    account1 = Account(
        account_id="ACC-1001",
        customer_name="Alice Vance",
        account_type="checking",
        risk_tier="LOW",
        country="USA",
        created_at=now - datetime.timedelta(days=365)
    )

    account2 = Account(
        account_id="ACC-1002",
        customer_name="Global Tech Solutions LLC",
        account_type="corporate",
        risk_tier="MEDIUM",
        country="USA",
        created_at=now - datetime.timedelta(days=60)
    )

    account3 = Account(
        account_id="ACC-1003",
        customer_name="Marcus Vance",
        account_type="checking",
        risk_tier="HIGH",
        country="USA",
        created_at=now - datetime.timedelta(days=120)
    )

    account4 = Account(
        account_id="ACC-1004",
        customer_name="Viktor Petrov",
        account_type="checking",
        risk_tier="HIGH",
        country="USA",
        created_at=now - datetime.timedelta(days=45)
    )

    db.add_all([account1, account2, account3, account4])
    db.commit()

    # 2. Historical Baseline Transactions
    transactions = []

    # ACC-1001: Regular baseline spending ($50 - $350)
    for i in range(15):
        t_time = now - datetime.timedelta(days=30 - i * 2)
        transactions.append(Transaction(
            transaction_id=f"TX-1001-{i+1:02d}",
            account_id="ACC-1001",
            amount=150.0 + (i * 12.5),
            timestamp=t_time,
            counterparty_name=f"Merchant_{i+1}",
            ip_address="192.168.1.45",
            location_country="USA",
            transaction_type="debit_card",
            is_flagged=False
        ))

    # ACC-1002: Corporate baseline ($1,000 - $3,000 avg)
    for i in range(10):
        t_time = now - datetime.timedelta(days=28 - i * 2)
        transactions.append(Transaction(
            transaction_id=f"TX-1002-{i+1:02d}",
            account_id="ACC-1002",
            amount=1800.0 + (i * 50.0),
            timestamp=t_time,
            counterparty_name="Standard Vendor Inc",
            ip_address="64.233.160.1",
            location_country="USA",
            transaction_type="ach",
            is_flagged=False
        ))

    # ACC-1002: ANOMALY 1 - Sudden $50,000 wire transfer from suspicious offshore IP
    tx_anomaly1 = Transaction(
        transaction_id="TX-1002-ANOMALY",
        account_id="ACC-1002",
        amount=50000.0,
        timestamp=now - datetime.timedelta(hours=2),
        counterparty_name="Offshore Capital Shell Corp",
        ip_address="185.220.101.5",  # Tor exit node / suspicious proxy IP
        location_country="CYP",      # Cyprus
        transaction_type="wire_transfer",
        is_flagged=True
    )
    transactions.append(tx_anomaly1)

    # ACC-1003: ANOMALY 2 - Rapid Structuring ($9,900 x 4 to evade $10k reporting limit)
    for i in range(4):
        t_time = now - datetime.timedelta(hours=18 - i * 3)
        transactions.append(Transaction(
            transaction_id=f"TX-1003-STRUCT-{i+1}",
            account_id="ACC-1003",
            amount=9900.0,
            timestamp=t_time,
            counterparty_name="Cash Deposit ATM #402",
            ip_address="192.168.1.99",
            location_country="USA",
            transaction_type="cash_deposit",
            is_flagged=True
        ))

    # ACC-1004: ANOMALY 3 - Wire transfer to OFAC Sanctioned Entity "Vladimir Petrov"
    tx_sanction = Transaction(
        transaction_id="TX-1004-SANCTION",
        account_id="ACC-1004",
        amount=18500.0,
        timestamp=now - datetime.timedelta(hours=5),
        counterparty_name="Vladimir Petrov",
        ip_address="91.108.56.100",
        location_country="RUS",
        transaction_type="wire_transfer",
        is_flagged=True
    )
    transactions.append(tx_sanction)

    db.add_all(transactions)
    db.commit()

    # 3. Alerts
    alerts = [
        Alert(
            alert_id="ALT-1001",
            account_id="ACC-1001",
            transaction_id="TX-1001-15",
            trigger_reason="Routine periodic review (Low Risk Baseline)",
            amount=325.0,
            status="PENDING",
            created_at=now - datetime.timedelta(hours=6)
        ),
        Alert(
            alert_id="ALT-1002",
            account_id="ACC-1002",
            transaction_id="TX-1002-ANOMALY",
            trigger_reason="Sudden $50,000 international transfer from unverified Cyprus IP (185.220.101.5)",
            amount=50000.0,
            status="PENDING",
            created_at=now - datetime.timedelta(hours=2)
        ),
        Alert(
            alert_id="ALT-1003",
            account_id="ACC-1003",
            transaction_id="TX-1003-STRUCT-4",
            trigger_reason="Multiple cash deposits just under $10,000 threshold (Possible Structuring)",
            amount=39600.0,
            status="PENDING",
            created_at=now - datetime.timedelta(hours=4)
        ),
        Alert(
            alert_id="ALT-1004",
            account_id="ACC-1004",
            transaction_id="TX-1004-SANCTION",
            trigger_reason="Cross-border wire transfer matching sanctioned individual 'Vladimir Petrov'",
            amount=18500.0,
            status="PENDING",
            created_at=now - datetime.timedelta(hours=5)
        )
    ]

    db.add_all(alerts)
    db.commit()
    return len(alerts)
