import os
import datetime
from typing import Dict, Any
import dotenv
from langgraph.types import interrupt

from src.db.connection import SessionLocal
from src.db.models import Alert, Account, Transaction
from src.tools.transaction_tools import fetch_transaction_history
from src.tools.sanctions_tools import perform_sanctions_check
from src.agent.schemas import AgentState, RiskAssessment

# Load environment variables
dotenv.load_dotenv()


def get_utc_now():
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def investigate_alert_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Gathers alert details and executes transaction baseline & sanctions tools."""
    alert_id = state.get("alert_id")
    logs = list(state.get("logs", []))

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🔍 Starting investigation for Alert {alert_id}...")

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if not alert:
            logs.append(f"❌ Error: Alert {alert_id} not found in database.")
            return {"logs": logs, "status": "ERROR"}

        account_id = alert.account_id
        alert_data = {
            "alert_id": alert.alert_id,
            "account_id": alert.account_id,
            "transaction_id": alert.transaction_id,
            "trigger_reason": alert.trigger_reason,
            "amount": alert.amount,
            "created_at": alert.created_at.isoformat() if alert.created_at else None
        }

        # Retrieve associated transaction details if available
        counterparty_name = ""
        if alert.transaction_id:
            tx = db.query(Transaction).filter(Transaction.transaction_id == alert.transaction_id).first()
            if tx:
                alert_data["ip_address"] = tx.ip_address
                alert_data["location_country"] = tx.location_country
                alert_data["counterparty_name"] = tx.counterparty_name
                counterparty_name = tx.counterparty_name or ""

        # Tool 1: Fetch 30-day transaction history & baseline
        logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 📊 Tool Call: get_transaction_history(account_id='{account_id}')")
        history = fetch_transaction_history(account_id)
        logs.append(f"   ↳ 30-Day Avg: ${history.get('30_day_avg_amount', 0):,.2f} | 30-Day Frequency: {history.get('30_day_frequency', 0)} txs")

        # Tool 2: Check Sanctions Watchlist
        logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🛡️ Tool Call: check_sanctions_watchlist(name='{counterparty_name}')")
        sanctions_res = perform_sanctions_check(counterparty_name)
        if sanctions_res.get("has_match"):
            logs.append(f"   ⚠️ SANCTIONS HIT DETECTED! Entity: '{counterparty_name}' | Risk Level: {sanctions_res.get('highest_risk_level')}")
        else:
            logs.append(f"   ✓ Sanctions screening clear for '{counterparty_name}'")

        # Update DB alert status
        alert.status = "UNDER_INVESTIGATION"
        db.commit()

        return {
            "alert_id": alert_id,
            "account_id": account_id,
            "alert_data": alert_data,
            "transaction_history": history,
            "sanctions_check": sanctions_res,
            "status": "UNDER_INVESTIGATION",
            "logs": logs
        }
    finally:
        db.close()


def calculate_rule_risk_assessment(state: AgentState) -> RiskAssessment:
    """Calculates risk score and rationale using deterministic AML compliance rules."""
    alert_data = state.get("alert_data", {})
    history = state.get("transaction_history", {})
    sanctions = state.get("sanctions_check", {})
    trigger_reason = alert_data.get("trigger_reason", "").lower()
    amount = alert_data.get("amount", 0.0)

    score = 15  # Base baseline risk score
    risk_factors = []

    # Factor 1: Sanctions Watchlist Hit
    if sanctions.get("has_match"):
        risk_level = sanctions.get("highest_risk_level", "HIGH")
        if risk_level == "CRITICAL":
            score += 75
            risk_factors.append("CRITICAL: Counterparty matched on OFAC/EU Sanctions Watchlist")
        else:
            score += 55
            risk_factors.append("HIGH: Counterparty matched on Compliance Watchlist")

    # Factor 2: Structuring Detection (multiple transactions under $10k limit)
    if "structuring" in trigger_reason or "just under $10,000" in trigger_reason:
        score += 65
        risk_factors.append("HIGH: Cash structuring pattern detected (repeated transfers under $10,000 CTR limit)")

    # Factor 3: Baseline Anomaly Ratio
    avg_30_day = history.get("30_day_avg_amount", 0.0)
    if avg_30_day > 0:
        ratio = amount / avg_30_day
        if ratio >= 10:
            score += 40
            risk_factors.append(f"HIGH: Alert amount (${amount:,.2f}) is {ratio:.1f}x higher than 30-day baseline (${avg_30_day:,.2f})")
        elif ratio >= 4:
            score += 25
            risk_factors.append(f"MEDIUM: Alert amount (${amount:,.2f}) is {ratio:.1f}x higher than 30-day baseline (${avg_30_day:,.2f})")

    # Factor 4: Suspicious IP / Location
    ip_addr = alert_data.get("ip_address", "")
    country = alert_data.get("location_country", "USA")
    if country not in ["USA", "US"] or "cyprus" in trigger_reason or "185.220" in ip_addr:
        score += 25
        risk_factors.append(f"MEDIUM: Transaction originated from high-risk offshore jurisdiction/IP ({country} / {ip_addr})")

    score = min(100, max(0, score))

    if not risk_factors:
        risk_factors.append("Low overall variance from baseline spending patterns")

    rec_action = "HUMAN_REVIEW" if score > 70 else "AUTO_CLOSE"

    rationale = f"Risk Score {score}/100 assigned based on {len(risk_factors)} risk factors: " + "; ".join(risk_factors) + "."

    return RiskAssessment(
        risk_score=score,
        risk_factors=risk_factors,
        rationale=rationale,
        recommended_action=rec_action
    )


def evaluate_risk_with_gemini(state: AgentState) -> RiskAssessment:
    """Evaluates risk score and rationale using Gemini LLM with structured output."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Neither GEMINI_API_KEY nor GOOGLE_API_KEY is configured in environment.")

    # Ensure GOOGLE_API_KEY is set in env for langchain_google_genai
    if "GOOGLE_API_KEY" not in os.environ and api_key:
        os.environ["GOOGLE_API_KEY"] = api_key

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        google_api_key=api_key
    )

    structured_llm = llm.with_structured_output(RiskAssessment)

    alert_data = state.get("alert_data", {})
    history = state.get("transaction_history", {})
    sanctions = state.get("sanctions_check", {})

    prompt = f"""You are a Senior Anti-Money Laundering (AML) Compliance Officer analyzing a suspicious transaction alert.
Evaluate the data below and return a structured RiskAssessment with an integer risk_score between 0 and 100, key risk_factors, a comprehensive rationale, and a recommended_action ('HUMAN_REVIEW' if risk_score > 70 else 'AUTO_CLOSE').

ALERT DATA:
- Alert ID: {alert_data.get('alert_id')}
- Account ID: {alert_data.get('account_id')}
- Flagged Amount: ${alert_data.get('amount', 0.0):,.2f}
- Trigger Reason: {alert_data.get('trigger_reason')}
- IP Address: {alert_data.get('ip_address', 'N/A')}
- Country: {alert_data.get('location_country', 'N/A')}
- Counterparty: {alert_data.get('counterparty_name', 'N/A')}

30-DAY HISTORICAL BASELINE:
- Customer Name: {history.get('customer_name', 'N/A')}
- Account Type: {history.get('account_type', 'N/A')}
- Account Risk Tier: {history.get('risk_tier', 'N/A')}
- 30-Day Average Transaction Size: ${history.get('30_day_avg_amount', 0.0):,.2f}
- 30-Day Transaction Count: {history.get('30_day_frequency', 0)}
- 30-Day Maximum Transaction: ${history.get('max_transaction_amount', 0.0):,.2f}
- 30-Day Total Volume: ${history.get('total_volume', 0.0):,.2f}

COMPLIANCE & SANCTIONS SCREENING:
- Watchlist Match Status: {sanctions.get('status', 'CLEAR')}
- Total Matches: {sanctions.get('match_count', 0)}
- Highest Risk Level: {sanctions.get('highest_risk_level', 'NONE')}
- Match Hits: {sanctions.get('matches', [])}

SCORING CRITERIA:
- High risk (>70): Severe baseline deviation, cash structuring, sanctioned entity match, or suspicious offshore IP.
- Low risk (<=70): Minor baseline variance or routine standard transactions.
"""

    return structured_llm.invoke(prompt)


def risk_scoring_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Risk Scoring Agent calculates risk score (0-100) & rationale."""
    logs = list(state.get("logs", []))
    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ⚖️ Risk Scoring Agent evaluating risk factors...")

    # Check for Gemini API key and attempt LLM scoring with fallback
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    assessment = None
    engine_used = "Rule Engine (Fallback)"

    if api_key:
        try:
            logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🤖 Gemini LLM Engine active. Invoking gemini-2.5-flash...")
            assessment = evaluate_risk_with_gemini(state)
            engine_used = "Gemini LLM (gemini-2.5-flash)"
        except Exception as e:
            logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ⚠️ Gemini API evaluation failed: {e}. Falling back to Rule Engine...")
            assessment = calculate_rule_risk_assessment(state)
            engine_used = "Rule Engine (Fallback after API error)"
    else:
        logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ⚙️ GEMINI_API_KEY / GOOGLE_API_KEY not found in environment. Using Rule Engine fallback...")
        assessment = calculate_rule_risk_assessment(state)

    score = assessment.risk_score
    rationale = assessment.rationale
    rec_action = assessment.recommended_action

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🎯 Risk Assessment Complete [{engine_used}] -> Score: {score}/100 | Recommended Action: {rec_action}")
    logs.append(f"   ↳ Rationale: {rationale}")

    # Update DB with risk score
    alert_id = state.get("alert_id")
    if alert_id:
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert:
                alert.risk_score = score
                alert.risk_rationale = rationale
                if score > 70:
                    alert.status = "HIGH_RISK_AWAITING_APPROVAL"
                else:
                    alert.status = "AUTO_CLOSED"
                db.commit()
        finally:
            db.close()

    return {
        "risk_assessment": assessment.model_dump(),
        "risk_score": score,
        "risk_rationale": rationale,
        "logs": logs
    }


def human_review_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Human Checkpoint. Interrupts workflow to await compliance officer approval/rejection."""
    logs = list(state.get("logs", []))
    alert_id = state.get("alert_id")
    score = state.get("risk_score", 0)
    rationale = state.get("risk_rationale", "")

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ⏸️ HIGH RISK ALERT (Score {score} > 70) -> Invoking LangGraph HITL Interrupt for Analyst Review")

    # LangGraph Interrupt mechanism
    user_input = interrupt({
        "alert_id": alert_id,
        "risk_score": score,
        "risk_rationale": rationale,
        "message": "Action required: High-risk alert requires compliance officer approval or rejection."
    })

    decision = user_input.get("decision", "approve") if isinstance(user_input, dict) else "approve"
    comment = user_input.get("comment", "") if isinstance(user_input, dict) else ""

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ▶️ Compliance Officer Decision Received: '{decision.upper()}' | Analyst Comment: '{comment}'")

    return {
        "human_decision": decision,
        "human_comment": comment,
        "logs": logs
    }


def generate_sar_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Generates a Suspicious Activity Report (SAR) markdown text document if approved."""
    logs = list(state.get("logs", []))
    alert_id = state.get("alert_id")
    alert_data = state.get("alert_data", {})
    history = state.get("transaction_history", {})
    sanctions = state.get("sanctions_check", {})
    score = state.get("risk_score", 0)
    rationale = state.get("risk_rationale", "")
    decision = state.get("human_decision", "approve")
    comment = state.get("human_comment", "Approved by Compliance Analyst")

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 📄 Generating FinCEN Suspicious Activity Report (SAR)...")

    now_dt = get_utc_now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    sar_text = f"""# SUSPICIOUS ACTIVITY REPORT (SAR)
**Filing Agency**: Financial Crimes Enforcement Network (FinCEN) Compliance Engine
**Document ID**: SAR-{alert_id}-{now_dt.strftime('%Y%m%d%H%M')}
**Date of Report**: {now_str}
**Status**: APPROVED & FILED

---

## 1. SUBJECT INFORMATION
- **Account ID**: {alert_data.get('account_id')}
- **Customer Name**: {history.get('customer_name', 'N/A')}
- **Account Type**: {history.get('account_type', 'N/A').upper()}
- **Risk Classification**: {history.get('risk_tier', 'HIGH')}

## 2. SUSPICIOUS ACTIVITY SUMMARY
- **Alert ID**: {alert_id}
- **Transaction ID**: {alert_data.get('transaction_id', 'N/A')}
- **Flagged Amount**: ${alert_data.get('amount', 0.0):,.2f}
- **Trigger Event**: {alert_data.get('trigger_reason')}
- **Originating IP**: {alert_data.get('ip_address', 'N/A')}
- **Originating Country**: {alert_data.get('location_country', 'N/A')}
- **Counterparty Name**: {alert_data.get('counterparty_name', 'N/A')}

## 3. AGENT INVESTIGATION & METRIC ANALYSIS
- **30-Day Historical Baseline Avg**: ${history.get('30_day_avg_amount', 0.0):,.2f}
- **30-Day Transaction Count**: {history.get('30_day_frequency', 0)} transactions
- **30-Day Total Volume**: ${history.get('total_volume', 0.0):,.2f}
- **Sanctions Watchlist Status**: {sanctions.get('status', 'CLEAR')} (Matches: {sanctions.get('match_count', 0)})

## 4. RISK ASSESSMENT & ANALYTICAL RATIONALE
- **Assigned Risk Score**: **{score}/100**
- **Risk Rationale**: {rationale}

## 5. HUMAN-IN-THE-LOOP COMPLIANCE OFFICER APPROVAL
- **Review Decision**: **{decision.upper()}**
- **Analyst Comments**: {comment}
- **Review Date**: {now_str}

---
**FILING RECOMMENDATION**: The investigating AI agent and human compliance officer unanimously recommend immediate transmission of this SAR to FinCEN and placing a temporary compliance hold on Account {alert_data.get('account_id')}.
"""

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] ✅ SAR Document successfully generated and recorded in audit log.")

    # Update database record
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if alert:
            alert.status = "APPROVED_SAR"
            alert.sar_document = sar_text
            db.commit()
    finally:
        db.close()

    return {
        "sar_document": sar_text,
        "status": "APPROVED_SAR",
        "logs": logs
    }


def auto_close_node(state: AgentState) -> Dict[str, Any]:
    """Node 5a: Auto closes low-risk alerts."""
    logs = list(state.get("logs", []))
    score = state.get("risk_score", 0)
    alert_id = state.get("alert_id")

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🟢 Alert {alert_id} Risk Score ({score} <= 70) is within safe operational limits. Auto-closing alert.")

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if alert:
            alert.status = "AUTO_CLOSED"
            db.commit()
    finally:
        db.close()

    return {
        "status": "AUTO_CLOSED",
        "logs": logs
    }


def reject_close_node(state: AgentState) -> Dict[str, Any]:
    """Node 5b: Closes alert upon analyst rejection."""
    logs = list(state.get("logs", []))
    alert_id = state.get("alert_id")
    comment = state.get("human_comment", "No comment provided")

    logs.append(f"[{get_utc_now().strftime('%H:%M:%S')}] 🔴 Compliance Officer Rejected SAR Filing for Alert {alert_id}. Reason: '{comment}'. Alert dismissed.")

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if alert:
            alert.status = "REJECTED"
            db.commit()
    finally:
        db.close()

    return {
        "status": "REJECTED",
        "logs": logs
    }
