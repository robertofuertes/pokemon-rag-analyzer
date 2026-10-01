#!/usr/bin/env python3
"""Create and populate the Week 2 MySQL data layer."""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List

import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATABASE = os.getenv("MYSQL_DATABASE", "pokemon_rag")

# Supported MySQL identifier format for values that are interpolated into SQL
# text (e.g. the database name). Restricting to letters, digits, and
# underscores (starting with a letter or underscore) avoids building SQL from
# unsafe string interpolation while still allowing standard database names.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_CREATE_INDEX_RE = re.compile(
    r"^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\s+"
    r"ON\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\b",
    re.IGNORECASE,
)


def validate_identifier(name: str) -> str:
    """Validate a value intended for use as a MySQL identifier.

    Only ``[A-Za-z_][A-Za-z0-9_]{0,63}`` is accepted (max 64 characters,
    matching MySQL's identifier length limit). Raises ``ValueError`` for
    anything else instead of allowing arbitrary strings into SQL text.
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid MySQL identifier: {name!r}. Only letters, digits, and "
            "underscores are allowed, and it must start with a letter or "
            "underscore (max 64 characters)."
        )
    return name


def quote_identifier(name: str) -> str:
    """Validate and backtick-quote a MySQL identifier for safe interpolation."""
    validate_identifier(name)
    return f"`{name}`"


# Scraping scope stays limited to National Dex #1-151 for speed (see
# scraper.py), but the type system is modern-day canonical (post Gen 6),
# since the live source now reports retconned/modern typings for some Gen 1
# Pokémon (e.g. several Gen 1 Pokémon were later given the Fairy type).
MODERN_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
    "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon",
    "Dark", "Steel", "Fairy",
]

# Present-day (post Gen 6) type effectiveness relationships. Missing pairs
# are neutral (1.0) and intentionally omitted from the data below.
TYPE_EFFECTIVENESS: Dict[str, Dict[str, float]] = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}


def connection() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        charset="utf8mb4",
    )


def execute_schema(conn: mysql.connector.MySQLConnection) -> None:
    schema_template = (ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    schema = schema_template.replace("{{DB_NAME}}", quote_identifier(DATABASE))
    with conn.cursor() as cursor:
        for statement in schema.split(";"):
            statement = statement.strip()
            if statement:
                index_match = _CREATE_INDEX_RE.match(statement)
                if index_match:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.statistics
                        WHERE table_schema = DATABASE()
                          AND table_name = %s
                          AND index_name = %s
                        LIMIT 1
                        """,
                        (index_match.group(2), index_match.group(1)),
                    )
                    if cursor.fetchone():
                        continue
                cursor.execute(statement)
    conn.commit()


def type_ids(conn: mysql.connector.MySQLConnection) -> Dict[str, int]:
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT IGNORE INTO pokemon_types (name) VALUES (%s)",
            [(name,) for name in MODERN_TYPES],
        )
        cursor.execute("SELECT id, name FROM pokemon_types")
        result = {name: int(identifier) for identifier, name in cursor.fetchall()}
    conn.commit()
    return result


def load_effectiveness(conn: mysql.connector.MySQLConnection, ids: Dict[str, int]) -> None:
    rows = []
    for attack, defenders in TYPE_EFFECTIVENESS.items():
        for defender, multiplier in defenders.items():
            rows.append((ids[attack], ids[defender], Decimal(str(multiplier))))

    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO type_effectiveness (attack_type_id, defender_type_id, multiplier)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE multiplier = VALUES(multiplier)
            """,
            rows,
        )
    conn.commit()


def load_pokemon(conn: mysql.connector.MySQLConnection, ids: Dict[str, int], path: Path) -> int:
    records: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    with conn.cursor() as cursor:
        for record in records:
            primary = record.get("primary_type", "").strip()
            secondary = record.get("secondary_type", "").strip()
            stats = record.get("base_stats", {})

            cursor.execute(
                """
                INSERT INTO pokemon (national_dex, name, primary_type_id, secondary_type_id)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    primary_type_id = VALUES(primary_type_id),
                    secondary_type_id = VALUES(secondary_type_id)
                """,
                (record["national_dex"], record["name"], ids[primary], ids.get(secondary)),
            )
            cursor.execute(
                """
                INSERT INTO pokemon_base_stats
                    (national_dex, hp, attack, defense, sp_atk, sp_def, speed)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    hp = VALUES(hp), attack = VALUES(attack), defense = VALUES(defense),
                    sp_atk = VALUES(sp_atk), sp_def = VALUES(sp_def), speed = VALUES(speed)
                """,
                (
                    record["national_dex"],
                    stats.get("HP", 0), stats.get("Attack", 0), stats.get("Defense", 0),
                    stats.get("Sp. Atk", 0), stats.get("Sp. Def", 0), stats.get("Speed", 0),
                ),
            )
    conn.commit()
    return len(records)


def main() -> None:
    validate_identifier(DATABASE)

    json_path = Path(os.getenv("POKEMON_JSON_PATH", str(ROOT / "pokemon_gen1.json")))
    if not json_path.exists():
        raise FileNotFoundError(
            f"Missing {json_path}. Run scraper.py first or set POKEMON_JSON_PATH in .env."
        )

    conn = connection()
    try:
        execute_schema(conn)
        ids = type_ids(conn)
        load_effectiveness(conn, ids)
        count = load_pokemon(conn, ids, json_path)
        print(f"Loaded {count} Pokémon records into {DATABASE}.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
