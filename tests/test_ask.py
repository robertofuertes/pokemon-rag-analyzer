from rag.ask import ask


def test_ask_returns_expected_shape():
    result = ask("Who has the highest speed?", top_k=3)
    assert "query" in result
    assert "answer" in result
    assert "routing" in result
    assert "sql_context" in result
    assert "vector_context" in result
    assert "prompt_preview" in result


def test_ask_rejects_empty_query():
    import pytest
    with pytest.raises(ValueError):
        ask("   ")