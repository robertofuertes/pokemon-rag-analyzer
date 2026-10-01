from rag.cli import _print_result


def test_print_result_text(capsys):
    sample = {
        "query": "Who is fastest?",
        "answer": "Regieleki is among the fastest.",
        "routing": {"intent": "stats_lookup", "confidence": 0.9},
        "sql_context": {"rows": [{"name": "Regieleki", "speed": 200}]},
        "vector_context": [{"id": "a"}, {"id": "b"}],
    }
    _print_result(sample, as_json=False)
    out = capsys.readouterr().out
    assert "=== Query ===" in out
    assert "=== Answer ===" in out
    assert "=== Routing ===" in out


def test_print_result_json(capsys):
    sample = {
        "query": "Q",
        "answer": "A",
        "routing": {},
        "sql_context": {},
        "vector_context": [],
    }
    _print_result(sample, as_json=True)
    out = capsys.readouterr().out
    assert '"query": "Q"' in out