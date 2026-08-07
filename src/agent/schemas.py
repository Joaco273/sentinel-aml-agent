from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """Pydantic structured output model for the Risk Scoring Agent."""

    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Calculated AML risk score between 0 (very low risk) and 100 (critical AML/fraud risk)."
    )
    risk_factors: List[str] = Field(
        default_factory=list,
        description="Key risk factors identified (e.g. baseline deviation, offshore IP, structuring, sanctions hit)."
    )
    rationale: str = Field(
        ...,
        description="Detailed analytical rationale explaining why this risk score was assigned."
    )
    recommended_action: str = Field(
        ...,
        description="Recommended action: 'AUTO_CLOSE' (score <= 70) or 'HUMAN_REVIEW' (score > 70)."
    )


class AgentState(TypedDict, total=False):
    """State schema for the LangGraph AML investigation workflow."""

    alert_id: str
    account_id: str
    alert_data: Dict[str, Any]
    transaction_history: Dict[str, Any]
    sanctions_check: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    risk_score: int
    risk_rationale: str
    status: str
    sar_document: Optional[str]
    human_decision: Optional[str]  # "approve" or "reject"
    human_comment: Optional[str]
    logs: List[str]
