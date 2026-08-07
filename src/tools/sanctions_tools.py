from typing import Dict, Any, List
from langchain_core.tools import tool

# Mock Watchlist DB of Sanctioned / PEP Entities
SANCTIONS_WATCHLIST = [
    {
        "entity_name": "Vladimir Petrov",
        "aliases": ["V. Petrov", "Petrov Vladimir"],
        "list": "OFAC SDN List",
        "program": "UKRAINE-EO13661 / Cyber Sanctions",
        "risk_level": "CRITICAL",
        "matched_country": "RUS"
    },
    {
        "entity_name": "Offshore Capital Shell Corp",
        "aliases": ["Shell Trading Corp", "Shell Trading Limited"],
        "list": "EU High-Risk Third Country Watchlist",
        "program": "AML Tax Evasion / Shell Operations",
        "risk_level": "HIGH",
        "matched_country": "CYP"
    },
    {
        "entity_name": "Global Maritime Logistics",
        "aliases": ["GML Shipping"],
        "list": "UN Maritime Advisory List",
        "program": "UN-SANCTION-MARITIME",
        "risk_level": "HIGH",
        "matched_country": "PAN"
    }
]


def perform_sanctions_check(name: str) -> Dict[str, Any]:
    """
    Checks an individual or company name against compliance sanctions databases.
    """
    if not name:
        return {
            "query": name,
            "has_match": False,
            "match_count": 0,
            "matches": [],
            "status": "CLEAR"
        }

    query_lower = name.lower().strip()
    matches = []

    for item in SANCTIONS_WATCHLIST:
        entity_lower = item["entity_name"].lower()
        alias_lowers = [a.lower() for a in item["aliases"]]

        if query_lower in entity_lower or entity_lower in query_lower:
            matches.append(item)
        elif any(query_lower in alias or alias in query_lower for alias in alias_lowers):
            matches.append(item)

    if matches:
        highest_risk = max([m["risk_level"] for m in matches], key=lambda r: {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}.get(r, 0))
        return {
            "query": name,
            "has_match": True,
            "match_count": len(matches),
            "matches": matches,
            "status": "FLAGGED",
            "highest_risk_level": highest_risk
        }

    return {
        "query": name,
        "has_match": False,
        "match_count": 0,
        "matches": [],
        "status": "CLEAR"
    }


@tool
def check_sanctions_watchlist(name: str) -> Dict[str, Any]:
    """Checks an individual or entity name against global compliance sanctions and PEP watchlists."""
    return perform_sanctions_check(name)
