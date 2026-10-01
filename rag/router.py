"""Week 3 query router: classify requests as SQL, vector, or hybrid."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Literal


Route = Literal["sql", "vector", "hybrid"]


@dataclass(frozen=True)
class RoutingDecision:
    route: Route
    confidence: float
    reasons: List[str]
    normalized_query: str


# Exact/stat-heavy indicators -> SQL
SQL_KEYWORDS = {
    "speed",
    "sp atk",
    "sp. atk",
    "special attack",
    "sp def",
    "sp. def",
    "special defense",
    "attack",
    "defense",
    "hp",
    "base stat",
    "base stats",
    "stat total",
    "total stats",
    "type effectiveness",
    "weakness",
    "weaknesses",
    "resist",
    "resistance",
    "resistances",
    "immune",
    "immunity",
    "compare",
    "highest",
    "lowest",
    "fastest",
    "slowest",
    "strongest",
    "rank",
    "ranking",
    "top",
    "list",
}

# Tactical/semantic indicators -> Vector
VECTOR_KEYWORDS = {
    "tactical",
    "strategy",
    "playstyle",
    "role",
    "roles",
    "synergy",
    "synergies",
    "team comp",
    "team composition",
    "recommended",
    "recommendation",
    "recommend",
    "good against",
    "counter",
    "counters",
    "wall",
    "sweeper",
    "special attacker",
    "physical attacker",
    "bulky",
    "glass cannon",
    "support",
}

# Multi-pokemon team language often implies both facts + tactics
HYBRID_HINTS = {
    "my team",
    "opponent team",
    "against",
    "versus",
    "vs",
    "battle plan",
    "lineup",
    "pick for me",
    "who should i use",
}


def _normalize(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _keyword_hits(query: str, keywords: set[str]) -> List[str]:
    hits: List[str] = []
    for kw in keywords:
        if kw in query:
            hits.append(kw)
    return sorted(set(hits))


def route_query(user_query: str) -> RoutingDecision:
    """Route user query to sql/vector/hybrid.

    Heuristics:
    - SQL if exact-stat / ranking / type-effectiveness heavy.
    - Vector if tactical/role/semantic heavy.
    - Hybrid if both signals appear, or explicit team-vs-team phrasing appears.
    """
    if not user_query or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    query = _normalize(user_query)

    sql_hits = _keyword_hits(query, SQL_KEYWORDS)
    vector_hits = _keyword_hits(query, VECTOR_KEYWORDS)
    hybrid_hits = _keyword_hits(query, HYBRID_HINTS)

    reasons: List[str] = []
    route: Route
    confidence: float

    # Hybrid if both channels are signaled.
    if (sql_hits and vector_hits) or hybrid_hits:
        route = "hybrid"
        confidence = 0.85 if (sql_hits and vector_hits) else 0.78
        if sql_hits:
            reasons.append(f"SQL signals: {', '.join(sql_hits[:6])}")
        if vector_hits:
            reasons.append(f"Vector signals: {', '.join(vector_hits[:6])}")
        if hybrid_hits:
            reasons.append(f"Hybrid hints: {', '.join(hybrid_hits[:6])}")

    elif sql_hits:
        route = "sql"
        confidence = 0.82
        reasons.append(f"SQL signals: {', '.join(sql_hits[:6])}")

    elif vector_hits:
        route = "vector"
        confidence = 0.80
        reasons.append(f"Vector signals: {', '.join(vector_hits[:6])}")

    else:
        # Fallback: most user questions in this app are advisory/recommendation oriented
        route = "hybrid"
        confidence = 0.55
        reasons.append("No strong keyword match; defaulting to hybrid for safe coverage.")

    return RoutingDecision(
        route=route,
        confidence=confidence,
        reasons=reasons,
        normalized_query=query,
    )