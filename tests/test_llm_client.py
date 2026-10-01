import os

from rag.llm_client import generate_answer


def test_generate_answer_returns_mock_when_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = generate_answer("hello")
    assert "Mock answer" in out


def test_generate_answer_mock_when_openai_missing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    # If import/openai call fails, function should fail-safe to mock.
    out = generate_answer("hello")
    assert isinstance(out, str)
    assert len(out) > 0