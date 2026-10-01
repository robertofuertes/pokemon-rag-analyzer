# Pokemon RAG Analyzer

A simple Retrieval-Augmented Generation (RAG) app for Pokémon analysis using:
- SQL-style stat lookups
- Vector retrieval for tactical/contextual questions
- OpenAI for final answer generation
- CLI + Streamlit UI

## Features

- Ask questions like:
  - "Who has the highest speed?"
  - "Best hazard remover for bulky offense?"
- Hybrid routing:
  - Structured/stat queries → SQL context
  - Strategy/open-ended queries → vector context
- LLM answer generation with safe mock fallback when API is unavailable
- CLI interface and simple Streamlit web UI

## Project Structure

```text
pokemon-rag-analyzer/
├─ app.py
├─ rag/
│  ├─ __init__.py
│  ├─ ask.py
│  ├─ cli.py
│  └─ llm_client.py
├─ tests/
│  ├─ test_ask.py
│  ├─ test_cli.py
│  └─ test_llm_client.py
└─ requirements.txt
```

## Setup

1. Clone repo and enter folder:
   ```bash
   git clone https://github.com/robertofuertes/pokemon-rag-analyzer.git
   cd pokemon-rag-analyzer
   ```

2. Create and activate virtual environment (recommended):
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - macOS/Linux:
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Required for real LLM responses:

- `OPENAI_API_KEY` = your API key
- `OPENAI_MODEL` = `gpt-4o-mini` (recommended)
- `OPENAI_MAX_TOKENS` = `300` (example cap)
- `USE_MOCK_LLM` = `false` for real API, `true` to force mock

### PowerShell example

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:OPENAI_MODEL="gpt-4o-mini"
$env:OPENAI_MAX_TOKENS="300"
$env:USE_MOCK_LLM="false"
```

If `OPENAI_API_KEY` is missing or a call fails, the app returns a mock answer by design.

## Run (CLI)

```bash
python -m rag.cli "Who has the highest speed?" --top-k 3
python -m rag.cli "Best hazard remover for bulky offense?" --top-k 4 --json
```

## Run (Streamlit UI)

```bash
python -m streamlit run app.py
```

Then open the local URL shown in terminal (usually `http://localhost:8501`).

## Tests

```bash
python -m pytest -q
```

## Notes

- API billing must be enabled in your OpenAI account for real responses.
- Keep `OPENAI_API_KEY` private (never commit it).
- Use low token limits + `gpt-4o-mini` to control cost.

## License

MIT (or your preferred license)