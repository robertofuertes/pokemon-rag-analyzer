from rag.context_assembler import assemble_context


def test_assemble_context_sql_shape():
    result = assemble_context("Who has the highest speed?", top_k=3)
    assert "routing" in result
    assert "sql_context" in result
    assert "vector_context" in result
    assert isinstance(result["sql_context"], dict)
    assert isinstance(result["vector_context"], list)


def test_assemble_context_vector_shape():
    result = assemble_context("Recommend a bulky wall with synergy.", top_k=3)
    assert "routing" in result
    assert "sql_context" in result
    assert "vector_context" in result
    assert isinstance(result["vector_context"], list)


def test_assemble_context_hybrid_shape():
    result = assemble_context(
        "My team has Charizard and Jolteon. Who should I use against Water?",
        top_k=3,
    )
    assert "routing" in result
    assert "sql_context" in result
    assert "vector_context" in result


def test_empty_query_raises():
    import pytest

    with pytest.raises(ValueError):
        assemble_context("   ")