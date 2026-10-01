"""Week 4 LLM client: environment-configured answer generation."""

from __future__ import annotations

import os


def _mock_response(prompt: str) -> str:
    return (
        "Mock answer (LLM disabled or unavailable). "
        "Set OPENAI_API_KEY to enable real model responses."
    )


def generate_answer(prompt: str) -> str:
    """
    Generate an answer from the configured LLM provider.

    Env vars:
    - OPENAI_API_KEY: required for real calls
    - OPENAI_MODEL: optional, defaults to gpt-4o-mini
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if not api_key:
        return _mock_response(prompt)

    # Lazy import so local dev/tests work without package if API is not used.
    try:
        from openai import OpenAI
    except Exception:
        return _mock_response(prompt)

    try:
        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model=model,
            input=prompt,
            temperature=0.2,
        )
        # SDK commonly exposes final text via output_text
        text = getattr(resp, "output_text", None)
        if text and text.strip():
            return text.strip()

        # Fallback parsing for compatibility
        parts = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                t = getattr(content, "text", None)
                if t:
                    parts.append(t)
        joined = "\n".join(p.strip() for p in parts if p and p.strip()).strip()
        return joined if joined else _mock_response(prompt)
    except Exception:
        # Fail safe for app stability
        return _mock_response(prompt)