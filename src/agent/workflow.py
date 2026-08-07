from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

from src.agent.schemas import AgentState
from src.agent.nodes import (
    investigate_alert_node,
    risk_scoring_node,
    human_review_node,
    generate_sar_node,
    auto_close_node,
    reject_close_node
)


def route_after_risk_scoring(state: AgentState) -> str:
    """Conditional edge router based on calculated risk score."""
    score = state.get("risk_score", 0)
    if score > 70:
        return "human_review"
    return "auto_close"


def route_after_human_review(state: AgentState) -> str:
    """Conditional edge router based on compliance officer decision."""
    decision = state.get("human_decision", "approve")
    if decision == "approve":
        return "generate_sar"
    return "reject_close"


def build_workflow():
    """Builds and compiles the stateful LangGraph AML investigation graph with MemorySaver checkpointer."""
    workflow = StateGraph(AgentState)

    # Add processing nodes
    workflow.add_node("investigate", investigate_alert_node)
    workflow.add_node("risk_scoring", risk_scoring_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("generate_sar", generate_sar_node)
    workflow.add_node("auto_close", auto_close_node)
    workflow.add_node("reject_close", reject_close_node)

    # Core execution flow
    workflow.add_edge(START, "investigate")
    workflow.add_edge("investigate", "risk_scoring")

    # Conditional edge: High risk (>70) -> human review; Low risk (<=70) -> auto close
    workflow.add_conditional_edges(
        "risk_scoring",
        route_after_risk_scoring,
        {
            "human_review": "human_review",
            "auto_close": "auto_close"
        }
    )

    # Conditional edge: Human approval -> generate SAR; Rejection -> reject close
    workflow.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "generate_sar": "generate_sar",
            "reject_close": "reject_close"
        }
    )

    workflow.add_edge("generate_sar", END)
    workflow.add_edge("auto_close", END)
    workflow.add_edge("reject_close", END)

    # In-memory checkpointer to support interrupt/resume HITL states
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    return app


# Module-level singleton instance
aml_agent_app = build_workflow()
