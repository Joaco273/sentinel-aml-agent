import datetime
from typing import Dict, Any, List
from langchain_core.tools import tool
from src.db.connection import SessionLocal
from src.db.models import Transaction, Account


def fetch_transaction_history(account_id: str) -> Dict[str, Any]:
    """
    Core python function to calculate 30-day baseline metrics for an account.
    Returns:
        30_day_avg_amount: float
        30_day_frequency: int (number of transactions in last 30 days)
        max_transaction_amount: float
        total_volume: float
        recent_transactions: list of dicts
    """
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.account_id == account_id).first()
        if not account:
            return {"error": f"Account {account_id} not found."}

        # Naive datetime comparison to match stored timestamps
        now = datetime.datetime.utcnow()
        thirty_days_ago = now - datetime.timedelta(days=30)

        txs = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == account_id,
                Transaction.timestamp >= thirty_days_ago
            )
            .order_by(Transaction.timestamp.desc())
            .all()
        )

        if not txs:
            return {
                "account_id": account_id,
                "customer_name": account.customer_name,
                "account_type": account.account_type,
                "risk_tier": account.risk_tier,
                "30_day_avg_amount": 0.0,
                "30_day_frequency": 0,
                "max_transaction_amount": 0.0,
                "total_volume": 0.0,
                "recent_transactions": []
            }

        amounts = [t.amount for t in txs]
        avg_amount = sum(amounts) / len(amounts)
        max_amount = max(amounts)
        total_volume = sum(amounts)
        frequency = len(txs)

        recent_txs = [
            {
                "transaction_id": t.transaction_id,
                "amount": t.amount,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "counterparty": t.counterparty_name,
                "ip_address": t.ip_address,
                "location_country": t.location_country,
                "transaction_type": t.transaction_type,
                "is_flagged": t.is_flagged
            }
            for t in txs[:10]
        ]

        return {
            "account_id": account_id,
            "customer_name": account.customer_name,
            "account_type": account.account_type,
            "risk_tier": account.risk_tier,
            "30_day_avg_amount": round(avg_amount, 2),
            "30_day_frequency": frequency,
            "max_transaction_amount": round(max_amount, 2),
            "total_volume": round(total_volume, 2),
            "recent_transactions": recent_txs
        }
    finally:
        db.close()


@tool
def get_transaction_history(account_id: str) -> Dict[str, Any]:
    """Fetches 30-day average transaction size, frequency, and recent ledger history for an account."""
    return fetch_transaction_history(account_id)
