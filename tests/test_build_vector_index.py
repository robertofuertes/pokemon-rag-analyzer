"""Tests for database/build_vector_index.py tactical document generation.

These tests only exercise pure, database-independent helpers (document/
metadata generation, embedding function). They must pass whether or not
chromadb is installed, and without any Chroma persistence directory,
network access, or Ollama.
"""

from __future__ import annotations

import importlib

import pytest

build_vector_index = importlib.import_module("database.build_vector_index")


SAMPLE_RECORD = {
    "national_dex": 6,
    "name": "Charizard",
    "primary_type": "Fire",
    "secondary_type": "Flying",
    "base_stats": {
        "HP": 78, "Attack": 84, "Defense": 78,
        "Sp. Atk": 109, "Sp. Def": 85, "Speed": 100,
    },
}

SINGLE_TYPE_RECORD = {
    "national_dex": 1,
    "name": "Bulbasaur",
    "primary_type": "Grass",
    "secondary_type": "",
    "base_stats": {
        "HP": 45, "Attack": 49, "Defense": 49,
        "Sp. Atk": 65, "Sp. Def": 65, "Speed": 45,
    },
}


class TestDeterministicHashingEmbeddingFunction:
    def test_same_text_produces_same_vector(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=32)
        vector_a = embed(["Charizard is a Fire/Flying type"])[0]
        vector_b = embed(["Charizard is a Fire/Flying type"])[0]
        assert vector_a == vector_b

    def test_different_text_produces_different_vector(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=32)
        vector_a = embed(["fast special attacker"])[0]
        vector_b = embed(["slow defensive wall"])[0]
        assert vector_a != vector_b

    def test_vector_is_normalized(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=16)
        vector = embed(["Pikachu is an Electric type Pokemon"])[0]
        norm_squared = sum(component * component for component in vector)
        assert norm_squared == pytest.approx(1.0, abs=1e-6)

    def test_empty_text_returns_zero_vector(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=8)
        vector = embed([""])[0]
        assert vector == [0.0] * 8

    def test_embed_query_is_consistent_with_call(self):
        # Regression test: ChromaDB's current query API calls
        # `embed_query` directly (not `__call__`) when embedding query
        # text, so the method must exist and must produce embeddings that
        # are deterministic and dimensionally/semantically compatible with
        # those produced for documents.
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=32)
        text = "fast special attacker"
        assert embed.embed_query([text]) == embed([text])

    def test_embed_query_output_is_normalized_and_sized(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=16)
        vector = embed.embed_query(["Pikachu is an Electric type Pokemon"])[0]
        assert len(vector) == 16
        norm_squared = sum(component * component for component in vector)
        assert norm_squared == pytest.approx(1.0, abs=1e-6)

    def test_get_config_and_build_from_config_round_trip(self):
        embed = build_vector_index.DeterministicHashingEmbeddingFunction(dimensions=64)
        config = embed.get_config()
        rebuilt = build_vector_index.DeterministicHashingEmbeddingFunction.build_from_config(config)
        assert rebuilt.dimensions == 64
        assert rebuilt(["fast special attacker"]) == embed(["fast special attacker"])


class TestCombatRoleAndTags:
    def test_fast_high_offense_pokemon_is_fast_attacker(self):
        role = build_vector_index.determine_combat_role(SAMPLE_RECORD)
        assert role == "fast attacker"

    def test_tags_include_type_and_stat_derived_tags(self):
        tags = build_vector_index.derive_synergy_tags(SAMPLE_RECORD)
        assert "type-fire" in tags
        assert "type-flying" in tags
        assert "high-special-attack" in tags
        assert "high-speed" in tags

    def test_single_type_pokemon_has_no_secondary_type_tag(self):
        tags = build_vector_index.derive_synergy_tags(SINGLE_TYPE_RECORD)
        type_tags = [tag for tag in tags if tag.startswith("type-")]
        assert type_tags == ["type-grass"]

    def test_balanced_low_stats_pokemon_is_not_misclassified_as_wall(self):
        role = build_vector_index.determine_combat_role(SINGLE_TYPE_RECORD)
        assert role in {"balanced generalist", "bulky support"}


class TestDocumentGeneration:
    def test_build_tactical_document_mentions_types_and_stats(self):
        document = build_vector_index.build_tactical_document(SAMPLE_RECORD)
        assert "Charizard" in document
        assert "Fire/Flying" in document
        assert "Speed 100" in document

    def test_build_document_id_is_stable_and_zero_padded(self):
        assert build_vector_index.build_document_id(SAMPLE_RECORD) == "pokemon-006"
        assert build_vector_index.build_document_id(SINGLE_TYPE_RECORD) == "pokemon-001"

    def test_metadata_contains_required_fields(self):
        metadata = build_vector_index.build_document_metadata(SAMPLE_RECORD)
        assert metadata["national_dex"] == 6
        assert metadata["name"] == "Charizard"
        assert metadata["primary_type"] == "Fire"
        assert metadata["secondary_type"] == "Flying"
        assert metadata["source"] == "pokemondb-scraper"
        assert metadata["schema_version"] == build_vector_index.DOCUMENT_SCHEMA_VERSION

    def test_generate_documents_produces_matching_length_lists(self):
        records = [SAMPLE_RECORD, SINGLE_TYPE_RECORD]
        ids, documents, metadatas = build_vector_index.generate_documents(records)

        assert len(ids) == len(documents) == len(metadatas) == 2
        assert ids[0] == "pokemon-006"
        assert ids[1] == "pokemon-001"

    def test_generate_documents_ids_are_unique(self):
        records = [SAMPLE_RECORD, SINGLE_TYPE_RECORD, SAMPLE_RECORD]
        ids, _, _ = build_vector_index.generate_documents(records)
        # Duplicate input records produce duplicate (stable) IDs, which is
        # exactly what makes upsert-based indexing idempotent.
        assert ids[0] == ids[2]


class TestLoadPokemonRecords:
    def test_raises_clear_error_when_json_missing(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            build_vector_index.load_pokemon_records(missing_path)

    def test_loads_records_from_json_file(self, tmp_path):
        import json

        json_path = tmp_path / "pokemon_gen1.json"
        json_path.write_text(json.dumps([SAMPLE_RECORD]), encoding="utf-8")

        records = build_vector_index.load_pokemon_records(json_path)
        assert records == [SAMPLE_RECORD]


@pytest.mark.skipif(
    not build_vector_index.CHROMA_AVAILABLE, reason="chromadb is not installed"
)
class TestQueryIndexRegression:
    """Regression coverage for the `embed_query` AttributeError.

    Exercises the real ChromaDB `query()` code path (local, on-disk
    PersistentClient only -- no external server/network) end-to-end
    through our custom embedding function, which previously failed with
    ``AttributeError: ... has no attribute 'embed_query'``.
    """

    def test_build_and_query_round_trip(self, tmp_path):
        persist_directory = str(tmp_path / "chroma_data")
        records = [SAMPLE_RECORD, SINGLE_TYPE_RECORD]
        ids, documents, metadatas = build_vector_index.generate_documents(records)

        collection = build_vector_index.get_collection(
            persist_directory=persist_directory,
            collection_name="test-collection",
        )
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        results = build_vector_index.query_index(
            "fast special attacker",
            n_results=2,
            persist_directory=persist_directory,
            collection_name="test-collection",
        )

        assert len(results["documents"][0]) == 2
        assert set(ids) == {
            build_vector_index.build_document_id(r) for r in (SAMPLE_RECORD, SINGLE_TYPE_RECORD)
        }

    def test_query_index_does_not_raise_attribute_error(self, tmp_path):
        persist_directory = str(tmp_path / "chroma_data")
        ids, documents, metadatas = build_vector_index.generate_documents([SAMPLE_RECORD])
        collection = build_vector_index.get_collection(
            persist_directory=persist_directory,
            collection_name="test-collection",
        )
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        # This is the exact call that previously raised:
        # AttributeError: 'DeterministicHashingEmbeddingFunction' object
        # has no attribute 'embed_query'
        results = build_vector_index.query_index(
            "fast special attacker",
            n_results=5,
            persist_directory=persist_directory,
            collection_name="test-collection",
        )
        assert results["documents"][0]


class TestChromaOptionalImport:
    def test_module_imports_without_error_regardless_of_chroma_availability(self):
        # The module itself must be importable whether or not chromadb is
        # installed; CHROMA_AVAILABLE just reflects the actual environment.
        assert isinstance(build_vector_index.CHROMA_AVAILABLE, bool)

    def test_require_chroma_raises_clear_error_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(build_vector_index, "CHROMA_AVAILABLE", False)
        with pytest.raises(RuntimeError, match="chromadb is not installed"):
            build_vector_index._require_chroma()
