#!/usr/bin/env python3
"""
Scrape Gen 1 Pokemon data from PokemonDB and save to JSON.
Validation ensures exactly 151 records are captured.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

POKEDEX_URL = "https://pokemondb.net/pokedex/all?gen=1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
BASE_STATS = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]


def fetch_page(url: str) -> BeautifulSoup:
    response = requests.get(url, timeout=30, headers=HEADERS)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


SPECIAL_SLUGS = {
    "Nidoran♀": "nidoran-f",
    "Nidoran♂": "nidoran-m",
    "Farfetch'd": "farfetchd",
    "Mr. Mime": "mr-mime",
}


def normalize_slug(name: str) -> str:
    if name in SPECIAL_SLUGS:
        return SPECIAL_SLUGS[name]
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def extract_row_data(row: Any) -> Optional[Dict[str, Any]]:
    number_cell = row.select_one("td:nth-of-type(1) > span")
    name_cell = row.select_one("td:nth-of-type(2) a.ent-name")
    type_links = row.select("td:nth-of-type(3) a")

    if not number_cell or not name_cell:
        href = name_cell.get("href", "")
        return None

    number_text = number_cell.get_text(strip=True)
    name = name_cell.get_text(strip=True)

    try:
        pokedex_number = int(number_text)
    except ValueError:
        return None

    types = [link.get_text(strip=True) for link in type_links if link.get_text(strip=True)]
    if len(types) > 2:
        types = types[:2]

    while len(types) < 2:
        types.append("")

    return {
        "national_dex": pokedex_number,
        "name": name,
        "url": href,
        "types": {
            "primary": types[0] if types else "",
            "secondary": types[1] if len(types) > 1 else "",
        },
    }


def extract_base_stats(page: BeautifulSoup) -> Dict[str, int]:
    stats: Dict[str, int] = {}

    for row in page.select("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) < 2:
            continue

        label = " ".join(cells[0].get_text(" ", strip=True).split())
        value = cells[1].get_text(" ", strip=True)

        if label in BASE_STATS:
            try:
                stats[label] = int(value)
            except ValueError:
                continue

    return {label: stats.get(label, 0) for label in BASE_STATS}


def fetch_pokemon_stats(url: str) -> Dict[str, int]:
    detail_url = url if url.startswith("http") else f"https://pokemondb.net{url}"
    page = fetch_page(detail_url)
    return extract_base_stats(page)


def scrape_gen_1() -> List[Dict[str, Any]]:
    page = fetch_page(POKEDEX_URL)
    rows = page.select("table#pokedex tbody tr")

    records: List[Dict[str, Any]] = []

    for row in rows:
        item = extract_row_data(row)
        if item is None:
            continue

        stats = fetch_pokemon_stats(item["url"])
        record = {
            "national_dex": item["national_dex"],
            "name": item["name"],
            "primary_type": item["types"]["primary"],
            "secondary_type": item["types"]["secondary"],
            "base_stats": stats,
        }
        records.append(record)

    return records


def validate_records(records: List[Dict[str, Any]]) -> None:
    if len(records) != 151:
        raise ValueError(f"Expected 151 Gen 1 Pokemon records, found {len(records)}.")


def main() -> None:
    records = scrape_gen_1()
    validate_records(records)

    output_path = Path("pokemon_gen1.json")
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print(f"Saved {len(records)} Gen 1 Pokemon records to {output_path}")


if __name__ == "__main__":
    main()