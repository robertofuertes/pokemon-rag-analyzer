"""Week 3 context assembler: executes routing decisions and returns unified context."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from database.query_helpers import (
    compare_pokemon,
    get_fastest_pokemon,
    get_highest_stat_pokemon,
    get_type_matchups,
)
from database.vector_retrieval import search_tactical_context
from rag.router import RoutingDecision, route_query


# Keep this conservative to avoid false positives like "Who", "What", etc.
KNOWN_POKEMON = {
    "Bulbasaur", "Ivysaur", "Venusaur", "Charmander", "Charmeleon", "Charizard",
    "Squirtle", "Wartortle", "Blastoise", "Caterpie", "Metapod", "Butterfree",
    "Weedle", "Kakuna", "Beedrill", "Pidgey", "Pidgeotto", "Pidgeot",
    "Rattata", "Raticate", "Spearow", "Fearow", "Ekans", "Arbok", "Pikachu",
    "Raichu", "Sandshrew", "Sandslash", "Nidoran", "Nidorina", "Nidoqueen",
    "Nidorino", "Nidoking", "Clefairy", "Clefable", "Vulpix", "Ninetales",
    "Jigglypuff", "Wigglytuff", "Zubat", "Golbat", "Oddish", "Gloom", "Vileplume",
    "Paras", "Parasect", "Venonat", "Venomoth", "Diglett", "Dugtrio", "Meowth",
    "Persian", "Psyduck", "Golduck", "Mankey", "Primeape", "Growlithe", "Arcanine",
    "Poliwag", "Poliwhirl", "Poliwrath", "Abra", "Kadabra", "Alakazam", "Machop",
    "Machoke", "Machamp", "Bellsprout", "Weepinbell", "Victreebel", "Tentacool",
    "Tentacruel", "Geodude", "Graveler", "Golem", "Ponyta", "Rapidash", "Slowpoke",
    "Slowbro", "Magnemite", "Magneton", "Farfetchd", "Doduo", "Dodrio", "Seel",
    "Dewgong", "Grimer", "Muk", "Shellder", "Cloyster", "Gastly", "Haunter",
    "Gengar", "Onix", "Drowzee", "Hypno", "Krabby", "Kingler", "Voltorb",
    "Electrode", "Exeggcute", "Exeggutor", "Cubone", "Marowak", "Hitmonlee",
    "Hitmonchan", "Lickitung", "Koffing", "Weezing", "Rhyhorn", "Rhydon",
    "Chansey", "Tangela", "Kangaskhan", "Horsea", "Seadra", "Goldeen", "Seaking",
    "Staryu", "Starmie", "Mr Mime", "Scyther", "Jynx", "Electabuzz", "Magmar",
    "Pinsir", "Tauros", "Magikarp", "Gyarados", "Lapras", "Ditto", "Eevee",
    "Vaporeon", "Jolteon", "Flareon", "Porygon", "Omanyte", "Omastar", "Kabuto",
    "Kabutops", "Aerodactyl", "Snorlax", "Articuno", "Zapdos", "Moltres", "Dratini",
    "Dragonair", "Dragonite", "Mewtwo", "Mew",
}

TYPE_NAMES = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark",
    "Steel", "Fairy",
}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _extract_pokemon_names(user_query: str) -> List[str]:
    """
    Extract likely Pokémon names from a query.
    Strategy:
    - Grab title-cased words/phrases
    - Normalize punctuation (Mr. Mime -> Mr Mime)
    - Keep only names present in KNOWN_POKEMON
    """
    q = user_query.replace(".", " ")
    candidates = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\b", q)

    out: List[str] = []
    seen = set()
    for c in candidates:
        name = _normalize_ws(c)
        if name in KNOWN_POKEMON:
            k = name.lower()
            if k not in seen:
                seen.add(k)
                out.append(name)
    return out


def _extract_stat(user_query: str) -> Optional[str]:
    q = user_query.lower()
    if "sp atk" in q or "sp. atk" in q or "special attack" in q:
        return "sp_atk"
    if "sp def" in q or "sp. def" in q or "special defense" in q:
        return "sp_def"
    if (
        "base stat total" in q
        or "base stats total" in q
        or "stat total" in q
        or "stats total" in q
        or "bst" in q
        or "base_stat_total" in q
        or "overall stats" in q
    ):
        return "base_stat_total"
    if "speed" in q or "fastest" in q or "slowest" in q:
        return "speed"
    if re.search(r"\battack\b", q):
        return "attack"
    if "defense" in q:
        return "defense"
    if re.search(r"\bhp\b", q):
        return "hp"
    return None


def _extract_type(user_query: str) -> Optional[str]:
    q = user_query.lower()
    for t in TYPE_NAMES:
        tl = t.lower()
        if f"against {tl}" in q or f"vs {tl}" in q or f"versus {tl}" in q or f"weak to {tl}" in q:
            return t
    return None


def _build_sql_context(user_query: str, top_k: int) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "comparison": [],
        "rankings": {},
        "type_matchups": None,
    }

    names = _extract_pokemon_names(user_query)
    if names:
        context["comparison"] = compare_pokemon(names)

    stat = _extract_stat(user_query)
    if stat:
        if stat == "speed" and "highest" not in user_query.lower() and "top" not in user_query.lower():
            # For general speed-oriented asks, fastest helper is a nice default.
            context["rankings"]["speed"] = get_fastest_pokemon(limit=top_k)
        else:
            context["rankings"][stat] = get_highest_stat_pokemon(stat, limit=top_k)

    defender_type = _extract_type(user_query)
    if defender_type:
        context["type_matchups"] = {
            "defender_type": defender_type,
            "rows": get_type_matchups(defender_type),
        }

    return context


def assemble_context(user_query: str, top_k: int = 5) -> Dict[str, Any]:
    """Route the query and assemble SQL/vector/hybrid evidence."""
    if not user_query or not user_query.strip():
        raise ValueError("user_query must be a non-empty string.")

    top_k = max(1, min(int(top_k), 20))
    decision: RoutingDecision = route_query(user_query)

    sql_context: Dict[str, Any] = {"comparison": [], "rankings": {}, "type_matchups": None}
    vector_context: List[Dict[str, Any]] = []

    if decision.route in ("sql", "hybrid"):
        sql_context = _build_sql_context(user_query, top_k)

    if decision.route in ("vector", "hybrid"):
        vector_context = search_tactical_context(user_query, n_results=top_k)

    return {
        "query": user_query,
        "routing": {
            "route": decision.route,
            "confidence": decision.confidence,
            "reasons": decision.reasons,
            "normalized_query": decision.normalized_query,
        },
        "sql_context": sql_context,
        "vector_context": vector_context,
    }