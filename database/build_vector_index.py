#!/usr/bin/env python3
"""Week 2 ChromaDB vector-indexing module.

Builds (or refreshes) a local, persistent ChromaDB collection of tactical
documents for the 151 Gen 1 Pokemon, derived deterministically from the
structured data already produced by ``scraper.py`` (national dex number,
name, primary/secondary type, and base stats).

This intentionally does **not** invent move learnsets or sourced competitive
claims: the tactical description, combat role, and synergy tags are all
computed from the scraped base stats and types using simple, transparent
rules. It also does not depend on Ollama or any networked embedding
service — embeddings are produced locally with a deterministic hashing
embedding function so the pipeline is fully offline-capable.

ChromaDB is imported lazily/optionally so that ``scraper.py``/database tests
that don't need vector indexing can still run in environments where
``chromadb`` isn't installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

try:  # pragma: no cover - exercised indirectly by import-guard tests
    import chromadb

    CHROMA_AVAILABLE = True
except ImportError:  # pragma: no cover
    chromadb = None  # type: ignore[assignment]
    CHROMA_AVAILABLE = False

DEFAULT_JSON_PATH = str(ROOT / "pokemon_gen1.json")
DEFAULT_PERSIST_DIRECTORY = str(ROOT / "chroma_data")
DEFAULT_COLLECTION_NAME = "pokemon_gen1_tactics"
# Bumped whenever the deterministic document-generation rules change, so
# stored metadata records which "shape" of document produced it.
DOCUMENT_SCHEMA_VERSION = "week2-v1"

STAT_KEYS = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]

# Thresholds are fixed, documented cutoffs (not dataset-relative percentiles)
# so document generation stays deterministic and reproducible for a single
# Pokemon in isolation.
HIGH_STAT_THRESHOLD = 100
LOW_STAT_THRESHOLD = 55


def _embedding_dimensions() -> int:
    return int(os.getenv("VECTOR_INDEX_EMBEDDING_DIMENSIONS", "256"))


class DeterministicHashingEmbeddingFunction:
    """Fully local, dependency-light embedding function.

    Produces a deterministic bag-of-words style vector using a hashing
    trick (SHA-256 of each token) instead of a heavyweight ML model. This
    keeps the Week 2 vector index runnable offline with no downloads, no
    Ollama dependency, and reproducible output for the same input text.
    """

    def __init__(self, dimensions: Optional[int] = None) -> None:
        self.dimensions = dimensions or _embedding_dimensions()

    # ChromaDB's EmbeddingFunction protocol expects a `name()` method on
    # newer versions; harmless if unused by older versions.
    def name(self) -> str:
        return "deterministic-hashing-embedding"

    def __call__(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002
        return [self._embed(text) for text in input]

    # Newer ChromaDB clients (>=1.x) call `embed_query` directly when
    # embedding query text for `collection.query(...)`, instead of falling
    # back to `__call__`. Our hashing scheme is identical for documents and
    # queries, so simply delegate to `__call__` to keep both deterministic
    # and dimensionally compatible with each other.
    def embed_query(self, input: Sequence[str]) -> List[List[float]]:  # noqa: A002
        return self.__call__(input)

    # Implementing these makes the embedding function serializable as part
    # of a collection's stored configuration, matching the full ChromaDB
    # `EmbeddingFunction` interface rather than relying on duck-typing.
    def get_config(self) -> Dict[str, Any]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "DeterministicHashingEmbeddingFunction":
        return DeterministicHashingEmbeddingFunction(dimensions=config.get("dimensions"))

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(component * component for component in vector))
        if norm > 0:
            vector = [component / norm for component in vector]
        return vector


def load_pokemon_records(json_path: Path) -> List[Dict[str, Any]]:
    if not json_path.exists():
        raise FileNotFoundError(
            f"Missing {json_path}. Run scraper.py first or set POKEMON_JSON_PATH."
        )
    return json.loads(json_path.read_text(encoding="utf-8"))


def _stat(record: Dict[str, Any], key: str) -> int:
    return int(record.get("base_stats", {}).get(key, 0) or 0)


def determine_combat_role(record: Dict[str, Any]) -> str:
    """Derive a likely combat role purely from base stats.

    This is an approximate, transparent heuristic based on which stats are
    dominant, not a sourced competitive-tier claim.
    """
    hp = _stat(record, "HP")
    atk = _stat(record, "Attack")
    dfn = _stat(record, "Defense")
    sp_atk = _stat(record, "Sp. Atk")
    sp_def = _stat(record, "Sp. Def")
    speed = _stat(record, "Speed")

    offense = max(atk, sp_atk)
    defense_total = dfn + sp_def + hp

    if speed >= HIGH_STAT_THRESHOLD and offense >= HIGH_STAT_THRESHOLD:
        return "fast attacker"
    if speed >= HIGH_STAT_THRESHOLD:
        return "speedster"
    if defense_total >= HIGH_STAT_THRESHOLD * 3 and offense < HIGH_STAT_THRESHOLD:
        return "defensive wall"
    if atk >= sp_atk and atk >= HIGH_STAT_THRESHOLD:
        return "physical attacker"
    if sp_atk > atk and sp_atk >= HIGH_STAT_THRESHOLD:
        return "special attacker"
    if defense_total >= HIGH_STAT_THRESHOLD * 3:
        return "bulky support"
    return "balanced generalist"


def derive_synergy_tags(record: Dict[str, Any]) -> List[str]:
    """Derive type/stat-derived tags describing likely tactical synergies.

    Tags are generated only from the scraped types and base stats; no move
    learnsets or external competitive data are used or implied.
    """
    tags: List[str] = []
    hp = _stat(record, "HP")
    atk = _stat(record, "Attack")
    dfn = _stat(record, "Defense")
    sp_atk = _stat(record, "Sp. Atk")
    sp_def = _stat(record, "Sp. Def")
    speed = _stat(record, "Speed")

    if atk >= HIGH_STAT_THRESHOLD:
        tags.append("high-physical-attack")
    if sp_atk >= HIGH_STAT_THRESHOLD:
        tags.append("high-special-attack")
    if dfn >= HIGH_STAT_THRESHOLD:
        tags.append("high-physical-defense")
    if sp_def >= HIGH_STAT_THRESHOLD:
        tags.append("high-special-defense")
    if hp >= HIGH_STAT_THRESHOLD:
        tags.append("high-hp")
    if speed >= HIGH_STAT_THRESHOLD:
        tags.append("high-speed")
    if speed <= LOW_STAT_THRESHOLD:
        tags.append("slow")
    if dfn <= LOW_STAT_THRESHOLD and sp_def <= LOW_STAT_THRESHOLD:
        tags.append("fragile-defense")

    for type_name in (record.get("primary_type"), record.get("secondary_type")):
        if type_name:
            tags.append(f"type-{type_name.strip().lower()}")

    return tags


def build_tactical_document(record: Dict[str, Any]) -> str:
    """Build a transparent, deterministic tactical description for a Pokemon."""
    name = record.get("name", "Unknown")
    primary_type = record.get("primary_type", "") or "Unknown"
    secondary_type = record.get("secondary_type", "")
    stats = record.get("base_stats", {})
    role = determine_combat_role(record)
    tags = derive_synergy_tags(record)

    type_summary = primary_type if not secondary_type else f"{primary_type}/{secondary_type}"
    stat_summary = ", ".join(f"{key} {stats.get(key, 0)}" for key in STAT_KEYS)
    total = sum(int(stats.get(key, 0) or 0) for key in STAT_KEYS)

    return (
        f"{name} (#{record.get('national_dex')}) is a {type_summary}-type Pokemon. "
        f"Base stats: {stat_summary} (total {total}). "
        f"Likely combat role based on base stats: {role}. "
        f"Type/stat-derived tags: {', '.join(tags) if tags else 'none'}."
    )


def build_document_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "national_dex": int(record["national_dex"]),
        "name": record.get("name", ""),
        "primary_type": record.get("primary_type", "") or "",
        "secondary_type": record.get("secondary_type", "") or "",
        "combat_role": determine_combat_role(record),
        "synergy_tags": ",".join(derive_synergy_tags(record)),
        "source": "pokemondb-scraper",
        "schema_version": DOCUMENT_SCHEMA_VERSION,
    }


def build_document_id(record: Dict[str, Any]) -> str:
    return f"pokemon-{int(record['national_dex']):03d}"


def generate_documents(
    records: Sequence[Dict[str, Any]],
) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """Generate (ids, documents, metadatas) for all given Pokemon records."""
    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for record in records:
        ids.append(build_document_id(record))
        documents.append(build_tactical_document(record))
        metadatas.append(build_document_metadata(record))

    return ids, documents, metadatas


def _require_chroma() -> None:
    if not CHROMA_AVAILABLE:
        raise RuntimeError(
            "chromadb is not installed. Install it with `pip install chromadb` "
            "(already listed in requirements.txt) to build or query the "
            "vector index."
        )


def get_client(persist_directory: str):
    """Create (or open) a local persistent ChromaDB client."""
    _require_chroma()
    Path(persist_directory).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_directory)


def get_collection(
    persist_directory: str = DEFAULT_PERSIST_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
):
    _require_chroma()
    client = get_client(persist_directory)
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=DeterministicHashingEmbeddingFunction(),
        metadata={"schema_version": DOCUMENT_SCHEMA_VERSION},
    )


def build_index(
    json_path: str = DEFAULT_JSON_PATH,
    persist_directory: str = DEFAULT_PERSIST_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> int:
    """Build/refresh the vector index. Idempotent: reruns upsert by ID."""
    records = load_pokemon_records(Path(json_path))
    ids, documents, metadatas = generate_documents(records)

    collection = get_collection(persist_directory, collection_name)
    # `upsert` replaces existing documents with the same ID instead of
    # duplicating them, so rerunning this function is safe.
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def query_index(
    query_text: str,
    n_results: int = 5,
    persist_directory: str = DEFAULT_PERSIST_DIRECTORY,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> Dict[str, Any]:
    collection = get_collection(persist_directory, collection_name)
    return collection.query(query_texts=[query_text], n_results=n_results)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or query the Week 2 ChromaDB tactical vector index."
    )
    parser.add_argument(
        "--json-path",
        default=os.getenv("POKEMON_JSON_PATH", DEFAULT_JSON_PATH),
        help="Path to the scraped pokemon_gen1.json file.",
    )
    parser.add_argument(
        "--persist-directory",
        default=os.getenv("VECTOR_INDEX_PERSIST_DIRECTORY", DEFAULT_PERSIST_DIRECTORY),
        help="Directory where the local Chroma database is persisted.",
    )
    parser.add_argument(
        "--collection-name",
        default=os.getenv("VECTOR_INDEX_COLLECTION_NAME", DEFAULT_COLLECTION_NAME),
        help="Name of the Chroma collection to create/use.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("build", help="Build or refresh the vector index (default).")

    query_parser = subparsers.add_parser("query", help="Run a semantic retrieval test query.")
    query_parser.add_argument("text", help="Free-text query, e.g. 'fast special attacker'.")
    query_parser.add_argument("--n-results", type=int, default=5)

    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    command = args.command or "build"

    if command == "build":
        count = build_index(args.json_path, args.persist_directory, args.collection_name)
        print(f"Indexed {count} Pokemon tactical documents into '{args.collection_name}'.")
    elif command == "query":
        results = query_index(
            args.text,
            n_results=args.n_results,
            persist_directory=args.persist_directory,
            collection_name=args.collection_name,
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        for rank, (document, metadata, distance) in enumerate(
            zip(documents, metadatas, distances), start=1
        ):
            print(f"{rank}. ({metadata.get('name')}, distance={distance:.4f})")
            print(f"   {document}")
    else:  # pragma: no cover - argparse restricts choices
        raise ValueError(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
