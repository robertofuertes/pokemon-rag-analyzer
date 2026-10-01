"""Week 3 prompt builder: formats assembled context into an LLM-ready prompt."""

from __future__ import annotations

from typing import Any, Dict, List


SYSTEM_PROMPT = (
    "You are a Pokémon battle analyst. Answer using ONLY the evidence provided "
    "in the context below. If the evidence is insufficient, say so clearly. "
    "Be concise, accurate, and cite specific stats or tactical notes when relevant."
)


def _format_comparison(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    lines = ["Pokémon Comparison:"]
    for r in rows:
        lines.append(f"- {r}")
    return "\n".join(lines)


def _format_rankings(rankings: Dict[str, List[Dict[str, Any]]]) -> str:
    if not rankings:
        return ""
    lines = ["Stat Rankings:"]
    for stat, rows in rankings.items():
        lines.append(f"  {stat}:")
        for r in rows:
            lines.append(f"    - {r}")
    return "\n".join(lines)


def _format_type_matchups(matchups: Dict[str, Any] | None) -> str:
    if not matchups:
        return ""
    defender = matchups.get("defender_type", "Unknown")
    rows = matchups.get("rows", [])
    lines = [f"Type Matchups vs {defender}:"]
    for r in rows:
        lines.append(f"- {r}")
    return "\n".join(lines)


def _format_vector_context(vector_context: List[Dict[str, Any]]) -> str:
    if not vector_context:
        return ""
    lines = ["Tactical/Strategic Notes:"]
    for i, item in enumerate(vector_context, start=1):
        text = item.get("document") or item.get("text") or str(item)
        lines.append(f"{i}. {text}")
    return "\n".join(lines)


def build_prompt(assembled_context: Dict[str, Any]) -> str:
    """Convert assembled_context (from assemble_context) into a final LLM prompt."""
    if not assembled_context or "query" not in assembled_context:
        raise ValueError("assembled_context must be the dict returned by assemble_context().")

    query = assembled_context["query"]
    routing = assembled_context.get("routing", {})
    sql_context = assembled_context.get("sql_context", {}) or {}
    vector_context = assembled_context.get("vector_context", []) or []

    sections: List[str] = [SYSTEM_PROMPT, "", f"User question: {query}", ""]

    sections.append(f"Routing decision: {routing.get('route', 'unknown')} "
                     f"(confidence={routing.get('confidence', 0):.2f})")
    sections.append("")

    comparison_block = _format_comparison(sql_context.get("comparison", []))
    if comparison_block:
        sections.append(comparison_block)
        sections.append("")

    rankings_block = _format_rankings(sql_context.get("rankings", {}))
    if rankings_block:
        sections.append(rankings_block)
        sections.append("")

    matchups_block = _format_type_matchups(sql_context.get("type_matchups"))
    if matchups_block:
        sections.append(matchups_block)
        sections.append("")

    vector_block = _format_vector_context(vector_context)
    if vector_block:
        sections.append(vector_block)
        sections.append("")

    if not any([comparison_block, rankings_block, matchups_block, vector_block]):
        sections.append("No specific evidence was retrieved for this question.")
        sections.append("")

    sections.append("Answer the user's question using only the evidence above.")

    return "\n".join(sections).strip()