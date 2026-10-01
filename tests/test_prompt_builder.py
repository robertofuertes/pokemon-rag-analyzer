from rag.context_assembler import assemble_context
from rag.prompt_builder import build_prompt


def test_build_prompt_contains_query_and_routing():
    ctx = assemble_context("Who has the highest speed?", top_k=3)
    prompt = build_prompt(ctx)
    assert "Who has the highest speed?" in prompt
    assert "Routing decision:" in prompt


def test_build_prompt_handles_vector_context():
    ctx = assemble_context("Recommend a bulky wall with synergy.", top_k=3)
    prompt = build_prompt(ctx)
    assert "User question:" in prompt


def test_build_prompt_raises_on_invalid_input():
    import pytest

    with pytest.raises(ValueError):
        build_prompt({})