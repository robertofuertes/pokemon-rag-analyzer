"""Tests for database/load_pokemon_data.py helpers that don't require MySQL.

No live MySQL server is required: these tests only exercise the identifier
validation/quoting helpers and the static type-effectiveness data.
"""

from __future__ import annotations

import importlib

import pytest

load_pokemon_data = importlib.import_module("database.load_pokemon_data")


class TestIdentifierValidation:
    @pytest.mark.parametrize(
        "name",
        ["pokemon_rag", "pokemon_rag_test", "_leading_underscore", "a", "A1_b2"],
    )
    def test_accepts_valid_identifiers(self, name):
        assert load_pokemon_data.validate_identifier(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "pokemon-rag",  # hyphen not allowed
            "1pokemon",  # cannot start with a digit
            "pokemon rag",  # whitespace not allowed
            "pokemon_rag; DROP TABLE pokemon;--",  # injection attempt
            "`pokemon_rag`",  # already-quoted input is not a bare identifier
            "",
            "a" * 65,  # exceeds MySQL's 64-character identifier limit
        ],
    )
    def test_rejects_invalid_identifiers(self, name):
        with pytest.raises(ValueError):
            load_pokemon_data.validate_identifier(name)

    def test_quote_identifier_wraps_in_backticks(self):
        assert load_pokemon_data.quote_identifier("pokemon_rag") == "`pokemon_rag`"

    def test_quote_identifier_rejects_unsafe_input(self):
        with pytest.raises(ValueError):
            load_pokemon_data.quote_identifier("pokemon_rag; DROP TABLE pokemon;--")


class TestSchemaTemplating:
    def test_execute_schema_uses_validated_database_placeholder(self):
        schema_path = load_pokemon_data.ROOT / "database" / "schema.sql"
        schema_text = schema_path.read_text(encoding="utf-8")
        assert "{{DB_NAME}}" in schema_text
        # The schema must not hardcode a specific database name anymore.
        assert "CREATE DATABASE IF NOT EXISTS pokemon_rag" not in schema_text

    def test_execute_schema_skips_existing_indexes_on_rerun(self, monkeypatch):
        index_names = set()
        executed_indexes = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def execute(self, statement, params=None):
                if "FROM information_schema.statistics" in statement:
                    self.index_exists = (params[0], params[1]) in index_names
                else:
                    match = load_pokemon_data._CREATE_INDEX_RE.match(statement)
                    if match:
                        index_names.add((match.group(2), match.group(1)))
                        executed_indexes.append(match.group(1))

            def fetchone(self):
                return (1,) if self.index_exists else None

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self):
                pass

        monkeypatch.setattr(load_pokemon_data, "DATABASE", "pokemon_rag_test")
        connection = Connection()
        load_pokemon_data.execute_schema(connection)
        load_pokemon_data.execute_schema(connection)

        assert executed_indexes == ["idx_effectiveness_defender_multiplier"]


class TestTypeEffectivenessData:
    def test_all_type_names_are_in_modern_types(self):
        known = set(load_pokemon_data.MODERN_TYPES)
        for attacker, defenders in load_pokemon_data.TYPE_EFFECTIVENESS.items():
            assert attacker in known
            for defender in defenders:
                assert defender in known

    def test_multipliers_are_within_valid_range(self):
        for defenders in load_pokemon_data.TYPE_EFFECTIVENESS.values():
            for multiplier in defenders.values():
                assert 0.0 <= multiplier <= 4.0

    def test_modern_types_has_eighteen_unique_entries(self):
        assert len(load_pokemon_data.MODERN_TYPES) == 18
        assert len(set(load_pokemon_data.MODERN_TYPES)) == 18

    def test_modern_types_include_dark_steel_and_fairy(self):
        modern_additions = {"Dark", "Steel", "Fairy"}
        assert modern_additions.issubset(set(load_pokemon_data.MODERN_TYPES))

    def test_every_modern_type_is_an_attacker_in_effectiveness_data(self):
        # Every modern type should have at least one non-neutral interaction
        # defined, so the matrix isn't missing coverage for newer types.
        assert set(load_pokemon_data.TYPE_EFFECTIVENESS.keys()) == set(
            load_pokemon_data.MODERN_TYPES
        )
