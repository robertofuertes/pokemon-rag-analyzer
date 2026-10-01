"""Week 3/4 ask pipeline: route -> retrieve -> build prompt -> answer."""

from __future__ import annotations

from typing import Any, Dict

from rag.context_assembler import assemble_context
from rag.llm_client import generate_answer
from rag.prompt_builder import build_prompt


def ask(user_query: str, top_k: int = 5) -> Dict[str, Any]:
    """Main RAG entry point for the app."""
    if not user_query or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    context = assemble_context(user_query, top_k=top_k)
    prompt = build_prompt(context)
    answer = generate_answer(prompt)

    return {
        "query": user_query,
        "answer": answer,
        "routing": context.get("routing", {}),
        "sql_context": context.get("sql_context", {}),
        "vector_context": context.get("vector_context", []),
        "prompt_preview": prompt[:1200],
    }