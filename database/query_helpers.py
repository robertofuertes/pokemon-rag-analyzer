"""Reusable MySQL queries for the Week 3 hybrid RAG pipeline."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any, Dict, List

import mysql.connector
from dotenv import load_dotenv

from database.load_pokemon_data import ROOT

load_dotenv(ROOT / ".env")


STAT_COLUMNS = {
    "hp": "hp",
    "attack": "attack",
    "defense": "defense",
    "sp_atk": "sp_atk",
    "sp_def": "sp_def",
    "speed": "speed",
}


def get_connection() -> mysql.connector.MySQLConnection:
    """Create a connection to the configured MySQL database."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "pokemon_rag"),
        charset="utf8mb4",
    )


def get_pokemon_by_name(name: str) -> Dict[str, Any] | None:
    """Return one Pokémon profile by name, or None if not found."""
    query = """
        SELECT
            national_dex,
            name,
            primary_type,
            secondary_type,
            hp,
            attack,
            defense,
            sp_atk,
            sp_def,
            speed,
            base_stat_total
        FROM v_pokemon_profiles
        WHERE LOWER(name) = LOWER(%s)
        LIMIT 1
    """

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (name.strip(),))
            return cursor.fetchone()


def get_fastest_pokemon(limit: int = 5) -> List[Dict[str, Any]]:
    """Return Pokémon ordered by descending Speed."""
    limit = max(1, min(int(limit), 151))

    query = """
        SELECT
            national_dex,
            name,
            primary_type,
            secondary_type,
            hp,
            attack,
            defense,
            sp_atk,
            sp_def,
            speed,
            base_stat_total
        FROM v_pokemon_profiles
        ORDER BY speed DESC, base_stat_total DESC, national_dex ASC
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()


def get_highest_stat_pokemon(
    stat_name: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Return Pokémon ordered by a selected base stat."""
    normalized_stat = stat_name.strip().lower()

    if normalized_stat not in STAT_COLUMNS:
        valid_stats = ", ".join(STAT_COLUMNS)
        raise ValueError(
            f"Unknown stat {stat_name!r}. Valid stats: {valid_stats}"
        )

    limit = max(1, min(int(limit), 151))
    column = STAT_COLUMNS[normalized_stat]

    # The column name comes only from the allow-listed STAT_COLUMNS mapping.
    query = f"""
        SELECT
            national_dex,
            name,
            primary_type,
            secondary_type,
            hp,
            attack,
            defense,
            sp_atk,
            sp_def,
            speed,
            base_stat_total
        FROM v_pokemon_profiles
        ORDER BY {column} DESC, base_stat_total DESC, national_dex ASC
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (limit,))
            return cursor.fetchall()


def get_type_matchups(defender_type: str) -> List[Dict[str, Any]]:
    """Return attack effectiveness values against a single defender type.

    Neutral matchups are not stored explicitly in the database, so missing
    rows are returned as multiplier 1.0.
    """
    query = """
        SELECT
            attack_type.name AS attack_type,
            COALESCE(effectiveness.multiplier, 1.0) AS multiplier
        FROM pokemon_types AS attack_type
        LEFT JOIN type_effectiveness AS effectiveness
            ON effectiveness.attack_type_id = attack_type.id
           AND effectiveness.defender_type_id = (
                SELECT id
                FROM pokemon_types
                WHERE LOWER(name) = LOWER(%s)
                LIMIT 1
           )
        ORDER BY multiplier DESC, attack_type.name ASC
    """

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, (defender_type.strip(),))
            rows = cursor.fetchall()

    for row in rows:
        if isinstance(row["multiplier"], Decimal):
            row["multiplier"] = float(row["multiplier"])

    return rows


def compare_pokemon(names: List[str]) -> List[Dict[str, Any]]:
    """Return exact profiles for a list of Pokémon names."""
    cleaned_names = [name.strip() for name in names if name.strip()]

    if not cleaned_names:
        return []

    placeholders = ", ".join(["%s"] * len(cleaned_names))

    query = f"""
        SELECT
            national_dex,
            name,
            primary_type,
            secondary_type,
            hp,
            attack,
            defense,
            sp_atk,
            sp_def,
            speed,
            base_stat_total
        FROM v_pokemon_profiles
        WHERE LOWER(name) IN ({placeholders})
        ORDER BY national_dex ASC
    """

    with get_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                query,
                tuple(name.lower() for name in cleaned_names),
            )
            return cursor.fetchall()