import streamlit as st
import requests
import time

# API Configuration
API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Sentinel AML - Agentic Fraud & Compliance Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: #F8FAFC;
        padding: 1.2rem 1.8rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-pending { background-color: #FEF3C7; color: #92400E; }
    .status-under-investigation { background-color: #E0F2FE; color: #075985; }
    .status-awaiting-approval { background-color: #FEE2E2; color: #991B1B; }
    .status-approved-sar { background-color: #DCFCE7; color: #166534; }
    .status-auto-closed { background-color: #F1F5F9; color: #475569; }
    .status-rejected { background-color: #F3F4F6; color: #6B7280; }

    .reasoning-box {
        background-color: #0F172A;
        color: #38BDF8;
        font-family: 'Courier New', Courier, monospace;
        padding: 1.2rem;
        border-radius: 8px;
        font-size: 0.9rem;
        line-height: 1.6;
        max-height: 350px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)


def fetch_alerts():
    try:
        res = requests.get(f"{API_BASE_URL}/api/alerts", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def fetch_alert_detail(alert_id):
    try:
        res = requests.get(f"{API_BASE_URL}/api/alerts/{alert_id}", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def trigger_investigation(alert_id):
    try:
        res = requests.post(f"{API_BASE_URL}/api/alerts/{alert_id}/investigate", timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Investigation request failed: {e}")
    return None


def submit_review(alert_id, decision, comment):
    try:
        res = requests.post(
            f"{API_BASE_URL}/api/alerts/{alert_id}/review",
            json={"decision": decision, "comment": comment},
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        st.error(f"Review submission failed: {e}")
    return None


def reset_database():
    try:
        res = requests.post(f"{API_BASE_URL}/api/reset_db", timeout=5)
        if res.status_code == 200:
            st.success("Database successfully reset and seeded!")
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Reset failed: {e}")


# Header Banner
st.markdown("""
<div class="main-header">
    <div>
        <span style="font-size: 1.8rem; margin-right: 8px;">🛡️</span>
        <span style="font-weight: 700;">SENTINEL AML</span>
        <span style="font-size: 0.9rem; margin-left: 12px; color: #94A3B8; font-weight: 400;">Autonomous Agentic Fraud & Compliance Investigation Engine</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar Control
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/security-checked.png", width=70)
    st.subheader("System Controls")
    st.caption("Environment: Local SQLite Ledger")

    if st.button("🔄 Reset Synthetic Data", use_container_width=True):
        reset_database()

    st.markdown("---")
    st.markdown("### 🤖 Agent Architecture")
    st.markdown("""
    - **Orchestrator**: LangGraph Stateful Graph
    - **Tools**: `get_transaction_history`, `check_sanctions_watchlist`
    - **Risk Scoring**: Pydantic Structured Output
    - **HITL Checkpoint**: LangGraph `interrupt` (>70 score)
    - **SAR Engine**: FinCEN Compliant Document Generator
    """)

# Load Alerts Queue
alerts = fetch_alerts()

if not alerts:
    st.warning("⚠️ Unable to connect to Sentinel AML Backend API (http://localhost:8000). Please ensure FastAPI server is running (`uvicorn src.api.app:app --port 8000`).")
else:
    # Summary Metrics Row
    total_alerts = len(alerts)
    high_risk_count = sum(1 for a in alerts if (a.get("risk_score") or 0) > 70)
    awaiting_count = sum(1 for a in alerts if a.get("status") == "HIGH_RISK_AWAITING_APPROVAL")
    sar_count = sum(1 for a in alerts if a.get("status") == "APPROVED_SAR")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_alerts}</div><div class="metric-label">Total Alerts</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #EF4444;">{high_risk_count}</div><div class="metric-label">High Risk Queue (>70)</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #F59E0B;">{awaiting_count}</div><div class="metric-label">Pending Analyst Approvals</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #10B981;">{sar_count}</div><div class="metric-label">Filed SAR Reports</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Workspace split: Left Queue | Right Active Investigation
    left_col, right_col = st.columns([1, 1.6])

    with left_col:
        st.subheader("📋 Alert Queue")

        selected_alert_id = st.radio(
            "Select Alert to Investigate:",
            options=[a["alert_id"] for a in alerts],
            format_func=lambda aid: f"{aid} | {next((a['customer_name'] for a in alerts if a['alert_id'] == aid), '')} | ${next((a['amount'] for a in alerts if a['alert_id'] == aid), 0):,.2f}",
            key="alert_selector"
        )

    with right_col:
        if selected_alert_id:
            alert_detail = fetch_alert_detail(selected_alert_id)
            if alert_detail:
                st.subheader(f"🔎 Investigation Workspace: {alert_detail['alert_id']}")

                # Alert Overview Card
                st.markdown(f"""
                **Customer**: {alert_detail['customer_name']} ({alert_detail['account_id']})  
                **Flagged Amount**: ${alert_detail['amount']:,.2f}  
                **Trigger Reason**: *{alert_detail['trigger_reason']}*  
                **Current Status**: `{alert_detail['status']}`
                """)

                # Investigation Trigger / Action Button
                if alert_detail['status'] == "PENDING":
                    if st.button("🚀 Start Agentic Investigation Workflow", type="primary", use_container_width=True):
                        with st.spinner("Agent executing tools and evaluating risk score..."):
                            res = trigger_investigation(selected_alert_id)
                            st.rerun()

                # Risk Score Meter Display
                if alert_detail.get('risk_score') is not None:
                    score = alert_detail['risk_score']
                    color = "#10B981" if score <= 30 else ("#F59E0B" if score <= 70 else "#EF4444")
                    st.markdown(f"""
                    <div style="background: #1E293B; padding: 1rem; border-radius: 8px; margin: 10px 0; color: white;">
                        <span style="font-size: 1.1rem;">Calculated AML Risk Score:</span>
                        <span style="font-size: 1.8rem; font-weight: bold; color: {color}; margin-left: 12px;">{score} / 100</span>
                    </div>
                    """, unsafe_allow_html=True)
                    st.caption(f"**Agent Rationale**: {alert_detail.get('risk_rationale')}")

                # Live Step-by-Step Reasoning Logs
                st.markdown("#### 🧠 Live Agent Reasoning & Tool Calls")
                logs = alert_detail.get("agent_logs", [])
                if logs:
                    log_text = "\n".join(logs)
                    st.markdown(f'<div class="reasoning-box"><pre style="color: #38BDF8; margin:0;">{log_text}</pre></div>', unsafe_allow_html=True)
                else:
                    st.info("Click 'Start Agentic Investigation Workflow' to run the agent pipeline.")

                # Interactive Human-in-the-Loop (HITL) Controls
                if alert_detail.get("is_awaiting_approval") or alert_detail.get("status") == "HIGH_RISK_AWAITING_APPROVAL":
                    st.markdown("---")
                    st.markdown("### ⚖️ Human-in-the-Loop Compliance Review")
                    st.warning("⚠️ High Risk Score (>70) detected. Action Required: Review agent findings and select approval decision below.")

                    comment = st.text_input("Compliance Officer Notes / Comments:", value="Verified anomalous offshore transaction. Immediate SAR filing warranted.")

                    rev_col1, rev_col2 = st.columns(2)
                    with rev_col1:
                        if st.button("✅ Approve & File SAR", type="primary", use_container_width=True):
                            with st.spinner("Resuming agent workflow & generating SAR..."):
                                submit_review(selected_alert_id, "approve", comment)
                                st.success("SAR successfully approved and generated!")
                                time.sleep(1)
                                st.rerun()

                    with rev_col2:
                        if st.button("❌ Reject & Dismiss Alert", use_container_width=True):
                            with st.spinner("Closing alert as false positive..."):
                                submit_review(selected_alert_id, "reject", comment)
                                st.info("Alert dismissed as false positive.")
                                time.sleep(1)
                                st.rerun()

                # SAR Document Display
                if alert_detail.get("sar_document"):
                    st.markdown("---")
                    st.markdown("### 📄 Generated Suspicious Activity Report (SAR)")
                    st.markdown(alert_detail["sar_document"])
                    st.download_button(
                        label="📥 Download Official SAR Document (.md)",
                        data=alert_detail["sar_document"],
                        file_name=f"SAR_{selected_alert_id}.md",
                        mime="text/markdown"
                    )
