"""Week 3 ask pipeline: route -> retrieve -> build prompt -> answer."""

from __future__ import annotations

from typing import Any, Dict

from rag.context_assembler import assemble_context
from rag.prompt_builder import build_prompt


def _mock_llm_call(prompt: str) -> str:
    """
    Temporary local stub.
    Replace with real OpenAI call in Week 4.
    """
    return (
        "Mock answer (replace with real LLM):\n"
        "I analyzed the provided SQL/vector evidence and generated this placeholder response."
    )


def ask(user_query: str, top_k: int = 5) -> Dict[str, Any]:
    """Main RAG entry point for the app."""
    if not user_query or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    context = assemble_context(user_query, top_k=top_k)
    prompt = build_prompt(context)
    answer = _mock_llm_call(prompt)

    return {
        "query": user_query,
        "answer": answer,
        "routing": context.get("routing", {}),
        "sql_context": context.get("sql_context", {}),
        "vector_context": context.get("vector_context", []),
        "prompt_preview": prompt[:1200],  # helpful for debugging/logging
    }