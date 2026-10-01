"""Week 3 vector retrieval wrapper for local ChromaDB index."""

from __future__ import annotations

from typing import Any, Dict, List

from database.build_vector_index import (
    DEFAULT_PERSIST_DIRECTORY,
    DEFAULT_COLLECTION_NAME,
    query_index,
)


def search_tactical_context(
    query_text: str,
    n_results: int = 5,
    persist_directory: str | None = None,
    collection_name: str | None = None,
) -> List[Dict[str, Any]]:
    if not query_text or not query_text.strip():
        raise ValueError("query_text must be a non-empty string.")

    n_results = max(1, min(int(n_results), 20))

    raw = query_index(
        query_text=query_text.strip(),
        n_results=n_results,
        persist_directory=persist_directory or DEFAULT_PERSIST_DIRECTORY,
        collection_name=collection_name or DEFAULT_COLLECTION_NAME,
    )

    # Chroma query result shape:
    # {
    #   "ids": [[...]],
    #   "documents": [[...]],
    #   "metadatas": [[...]],
    #   "distances": [[...]]
    # }
    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    dists = (raw.get("distances") or [[]])[0]

    results: List[Dict[str, Any]] = []

    for i, doc_id in enumerate(ids):
        metadata = metas[i] if i < len(metas) and metas[i] is not None else {}
        distance = dists[i] if i < len(dists) else None
        document = docs[i] if i < len(docs) else ""

        results.append(
            {
                "id": doc_id,
                "name": metadata.get("name"),
                "national_dex": metadata.get("national_dex"),
                "primary_type": metadata.get("primary_type"),
                "secondary_type": metadata.get("secondary_type"),
                "combat_role": metadata.get("combat_role"),
                "tags": metadata.get("tags"),
                "distance": distance,
                "document": document,
            }
        )

    return results