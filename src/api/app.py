from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from langgraph.types import Command

from src.db.connection import get_db
from src.db.models import Alert, Account, Transaction
from src.db.seed_data import seed_database
from src.agent.workflow import aml_agent_app

app = FastAPI(
    title="Sentinel AML - Agentic Compliance API",
    description="Anti-Money Laundering & Fraud Investigation Agentic Workflow Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewRequest(BaseModel):
    decision: str  # "approve" or "reject"
    comment: Optional[str] = "Reviewed by compliance analyst"


@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Sentinel AML Agent Platform",
        "version": "1.0.0"
    }


@app.get("/api/alerts")
def list_alerts(db: Session = Depends(get_db)):
    """List all alerts with account details and current investigation status."""
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()
    results = []
    for a in alerts:
        account = db.query(Account).filter(Account.account_id == a.account_id).first()
        results.append({
            "alert_id": a.alert_id,
            "account_id": a.account_id,
            "customer_name": account.customer_name if account else "Unknown",
            "account_type": account.account_type if account else "Unknown",
            "trigger_reason": a.trigger_reason,
            "amount": a.amount,
            "status": a.status,
            "risk_score": a.risk_score,
            "risk_rationale": a.risk_rationale,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })
    return results


@app.get("/api/alerts/{alert_id}")
def get_alert_detail(alert_id: str, db: Session = Depends(get_db)):
    """Get full details for a specific alert, including live graph state if active."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    account = db.query(Account).filter(Account.account_id == alert.account_id).first()
    tx = db.query(Transaction).filter(Transaction.transaction_id == alert.transaction_id).first() if alert.transaction_id else None

    # Fetch graph state from checkpointer
    config = {"configurable": {"thread_id": f"thread-{alert_id}"}}
    graph_snapshot = aml_agent_app.get_state(config)

    logs = []
    if graph_snapshot and graph_snapshot.values:
        logs = graph_snapshot.values.get("logs", [])

    return {
        "alert_id": alert.alert_id,
        "account_id": alert.account_id,
        "customer_name": account.customer_name if account else "Unknown",
        "account_type": account.account_type if account else "Unknown",
        "trigger_reason": alert.trigger_reason,
        "amount": alert.amount,
        "status": alert.status,
        "risk_score": alert.risk_score,
        "risk_rationale": alert.risk_rationale,
        "sar_document": alert.sar_document,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "transaction_details": {
            "transaction_id": tx.transaction_id if tx else None,
            "ip_address": tx.ip_address if tx else None,
            "location_country": tx.location_country if tx else None,
            "counterparty_name": tx.counterparty_name if tx else None,
        } if tx else None,
        "agent_logs": logs,
        "is_awaiting_approval": bool(graph_snapshot and graph_snapshot.next and graph_snapshot.next[0] == "human_review")
    }


@app.post("/api/alerts/{alert_id}/investigate")
def run_investigation(alert_id: str, db: Session = Depends(get_db)):
    """Triggers the agentic LangGraph workflow for an alert."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    config = {"configurable": {"thread_id": f"thread-{alert_id}"}}
    initial_state = {
        "alert_id": alert_id,
        "logs": []
    }

    output_state = aml_agent_app.invoke(initial_state, config=config)

    snapshot = aml_agent_app.get_state(config)
    is_interrupted = bool(snapshot and snapshot.next and snapshot.next[0] == "human_review")

    # Re-query alert to get updated DB status
    db.refresh(alert)

    return {
        "alert_id": alert_id,
        "status": alert.status,
        "risk_score": alert.risk_score,
        "risk_rationale": alert.risk_rationale,
        "is_awaiting_approval": is_interrupted,
        "logs": output_state.get("logs", []),
        "sar_document": output_state.get("sar_document")
    }


@app.post("/api/alerts/{alert_id}/review")
def submit_human_review(alert_id: str, req: ReviewRequest, db: Session = Depends(get_db)):
    """Submits compliance officer approval or rejection to resume interrupted workflow."""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")

    config = {"configurable": {"thread_id": f"thread-{alert_id}"}}
    snapshot = aml_agent_app.get_state(config)

    if not snapshot or not snapshot.next:
        # If workflow was not already paused at interrupt, invoke initial run first
        initial_state = {"alert_id": alert_id, "logs": []}
        aml_agent_app.invoke(initial_state, config=config)
        snapshot = aml_agent_app.get_state(config)

    if snapshot.next and snapshot.next[0] == "human_review":
        resumed_state = aml_agent_app.invoke(
            Command(resume={"decision": req.decision, "comment": req.comment}),
            config=config
        )
        db.refresh(alert)
        return {
            "alert_id": alert_id,
            "status": alert.status,
            "human_decision": req.decision,
            "sar_document": resumed_state.get("sar_document"),
            "logs": resumed_state.get("logs", [])
        }

    return {
        "alert_id": alert_id,
        "status": alert.status,
        "message": "Workflow is not currently in an interrupted review state."
    }


@app.post("/api/reset_db")
def reset_database(db: Session = Depends(get_db)):
    """Resets database tables and re-seeds synthetic mock data."""
    count = seed_database(db)
    return {"status": "success", "seeded_alerts": count}
