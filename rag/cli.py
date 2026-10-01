from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from rag.ask import ask


def _print_result(result: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print("\n=== Query ===")
    print(result.get("query", ""))

    print("\n=== Answer ===")
    print(result.get("answer", ""))

    routing = result.get("routing", {})
    print("\n=== Routing ===")
    print(f"intent={routing.get('intent')} confidence={routing.get('confidence')}")

    sql_ctx = result.get("sql_context", {})
    if sql_ctx:
        print("\n=== SQL Context ===")
        print(sql_ctx)

    vec = result.get("vector_context", []) or []
    print(f"\n=== Vector Context Chunks === {len(vec)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pokemon RAG Analyzer CLI")
    parser.add_argument("question", help="User question to ask the RAG pipeline")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks")
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    result = ask(args.question, top_k=args.top_k)
    _print_result(result, as_json=args.json)


if __name__ == "__main__":
    main()