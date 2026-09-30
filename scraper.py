#!/usr/bin/env python3
"""
Scrape Gen 1 Pokemon data from PokemonDB and save to JSON.
Validation ensures exactly 151 records are captured.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

POKEDEX_URL = "https://pokemondb.net/pokedex/all?gen=1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
BASE_STATS = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]

# Script directory anchors output/paths so behavior is predictable regardless
# of the caller's current working directory.
SCRIPT_DIR = Path(__file__).resolve().parent

REQUEST_TIMEOUT_SECONDS = float(os.getenv("SCRAPER_TIMEOUT_SECONDS", "30"))
# Polite delay applied between individual Pokemon *detail page* requests only.
# The initial Pokedex list request is not delayed.
REQUEST_DELAY_SECONDS = float(os.getenv("SCRAPER_REQUEST_DELAY_SECONDS", "0.5"))
MAX_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "3"))
BACKOFF_FACTOR = float(os.getenv("SCRAPER_BACKOFF_FACTOR", "0.5"))
# Transient failures worth retrying: request timeouts/connection errors are
# retried automatically by urllib3's Retry; these status codes cover rate
# limiting (429) and server-side failures (5xx). Anything else (e.g. 404)
# is treated as a permanent failure and raised immediately.
RETRY_STATUS_FORCELIST = (429, 500, 502, 503, 504)


def build_session() -> requests.Session:
    """Build a requests Session with retry/backoff for transient failures.

    Connection errors and read timeouts are retried by urllib3's Retry
    machinery; 429/5xx responses are retried with exponential backoff.
    Permanent failures (e.g. 404) are not retried and continue to raise
    ``requests.exceptions.HTTPError`` via ``raise_for_status``.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_FORCELIST,
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_DEFAULT_SESSION: Optional[requests.Session] = None


def _get_default_session() -> requests.Session:
    global _DEFAULT_SESSION
    if _DEFAULT_SESSION is None:
        _DEFAULT_SESSION = build_session()
    return _DEFAULT_SESSION


def fetch_page(url: str, session: Optional[requests.Session] = None) -> BeautifulSoup:
    active_session = session or _get_default_session()
    response = active_session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")


def extract_row_data(row: Any) -> Optional[Dict[str, Any]]:
    number_cell = row.select_one("td:nth-of-type(1) > span")
    name_cell = row.select_one("td:nth-of-type(2) a.ent-name")
    type_links = row.select("td:nth-of-type(3) a")

    if not number_cell or not name_cell:
        return None

    href = name_cell.get("href", "")
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


def _find_base_stats_table(page: BeautifulSoup) -> Optional[Any]:
    """Locate the table that follows the "Base stats" heading.

    PokemonDB detail pages contain several `table.vitals-table` elements
    (Pokedex data, training, breeding, base stats, and sometimes alternate
    forms). Scoping to the table that immediately follows the "Base stats"
    heading avoids accidentally reading stats from an unrelated table.
    """
    for heading in page.find_all(["h2", "h3"]):
        if heading.get_text(strip=True).lower() == "base stats":
            return heading.find_next("table")
    return None


def extract_base_stats(page: BeautifulSoup) -> Dict[str, int]:
    stats: Dict[str, int] = {}

    table = _find_base_stats_table(page)
    # Fall back to scanning the whole page if the "Base stats" heading isn't
    # found (e.g. the markup changes), keeping the parser resilient.
    rows = table.select("tr") if table is not None else page.select("tr")

    for row in rows:
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


def fetch_pokemon_stats(url: str, session: Optional[requests.Session] = None) -> Dict[str, int]:
    detail_url = url if url.startswith("http") else f"https://pokemondb.net{url}"
    page = fetch_page(detail_url, session=session)
    return extract_base_stats(page)


def scrape_gen_1() -> List[Dict[str, Any]]:
    session = _get_default_session()

    # The initial Pokedex list request is intentionally not delayed.
    page = fetch_page(POKEDEX_URL, session=session)
    rows = page.select("table#pokedex tbody tr")

    records: List[Dict[str, Any]] = []
    seen_dex_numbers: set[int] = set()
    detail_requests_made = 0

    for row in rows:
        item = extract_row_data(row)
        if item is None:
            continue

        dex_number = item["national_dex"]

        # Only keep the original 151 Gen 1 Pokemon, and skip
        # duplicate/alternate-form rows for the same dex number.
        if dex_number < 1 or dex_number > 151:
            continue
        if dex_number in seen_dex_numbers:
            continue

        seen_dex_numbers.add(dex_number)

        if detail_requests_made > 0 and REQUEST_DELAY_SECONDS > 0:
            time.sleep(REQUEST_DELAY_SECONDS)

        stats = fetch_pokemon_stats(item["url"], session=session)
        detail_requests_made += 1

        record = {
            "national_dex": dex_number,
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

    output_path = Path(os.getenv("POKEMON_JSON_PATH", str(SCRIPT_DIR / "pokemon_gen1.json")))
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    print(f"Saved {len(records)} Gen 1 Pokemon records to {output_path}")


if __name__ == "__main__":
    main()
