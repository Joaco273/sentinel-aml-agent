# Sentinel AML: Autonomous Agentic Fraud & Compliance Engine

Sentinel AML is an enterprise-grade, agentic AI platform designed to automate Level-1 Anti-Money Laundering (AML) transaction analysis and Suspicious Activity Report (SAR) generation.

## 🚀 Key Features
- **Multi-Agent Orchestration**: Built with LangGraph for stateful tool execution and deterministic routing.
- **Dynamic Tool Calling**: Executes real-time SQL queries against transaction ledgers and external sanctions APIs.
- **Human-in-the-Loop (HITL)**: Enforces strict compliance checkpoints where human analysts approve/reject agent decisions for high-risk flags (>70 risk score).
- **Audit-Ready SAR Generation**: Auto-generates structured compliance documentation using Pydantic schemas.

## 🛠️ Tech Stack
- **Backend & Orchestration**: Python, LangGraph, FastAPI, Pydantic
- **Database**: PostgreSQL (Structured transaction ledgers)
- **Frontend**: React (or Streamlit) interactive dashboard
- **AI Infrastructure**: Built & orchestrated via Google Antigravity

## 🏁 Quickstart
1. Clone the repository: `git clone https://github.com/Joaco273/sentinel-aml-agent.git`
2. Install dependencies: `pip install -r requirements.txt`
3. Run migrations: `python scripts/init_db.py`
4. Start backend & UI: `uvicorn main:app --reload`