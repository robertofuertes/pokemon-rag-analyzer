"""Tests for scraper.py parsing, validation, and retry configuration.

No network access is required: HTML fixtures are parsed directly with
BeautifulSoup, and retry behavior is verified against the configured
urllib3 Retry object rather than by making real HTTP calls.
"""

from __future__ import annotations

from typing import List

import pytest
from bs4 import BeautifulSoup

import scraper


POKEDEX_ROW_TEMPLATE = """
<tr>
  <td><span class="infocard-cell-img">{number}</span></td>
  <td class="cell-name"><a class="ent-name" href="{href}">{name}</a></td>
  <td class="cell-icon">
    {types}
  </td>
</tr>
"""


def _type_links(types: List[str]) -> str:
    return "".join(f'<a class="itype" href="/type/{t.lower()}">{t}</a>' for t in types)


def make_row(number: int, name: str, href: str, types: List[str]) -> BeautifulSoup:
    html = POKEDEX_ROW_TEMPLATE.format(
        number=number, href=href, name=name, types=_type_links(types)
    )
    return BeautifulSoup(html, "lxml").find("tr")


class TestExtractRowData:
    def test_normal_row_with_two_types(self):
        row = make_row(1, "Bulbasaur", "/pokedex/bulbasaur", ["Grass", "Poison"])
        result = scraper.extract_row_data(row)

        assert result == {
            "national_dex": 1,
            "name": "Bulbasaur",
            "url": "/pokedex/bulbasaur",
            "types": {"primary": "Grass", "secondary": "Poison"},
        }

    def test_single_type_row_fills_empty_secondary(self):
        row = make_row(4, "Charmander", "/pokedex/charmander", ["Fire"])
        result = scraper.extract_row_data(row)

        assert result["types"] == {"primary": "Fire", "secondary": ""}

    def test_special_character_name_uses_href_from_table(self):
        # Names such as Nidoran (with gender glyph) and Farfetch'd rely on
        # the href already provided in the Pokedex table row, rather than a
        # locally reconstructed slug.
        row = make_row(29, "Nidoran\u2640", "/pokedex/nidoran-f", ["Poison"])
        result = scraper.extract_row_data(row)

        assert result["url"] == "/pokedex/nidoran-f"
        assert result["name"] == "Nidoran\u2640"

    def test_more_than_two_types_are_truncated(self):
        row = make_row(6, "Charizard", "/pokedex/charizard", ["Fire", "Flying", "Extra"])
        result = scraper.extract_row_data(row)

        assert result["types"] == {"primary": "Fire", "secondary": "Flying"}

    def test_missing_name_cell_returns_none(self):
        html = """
        <tr>
          <td><span>1</span></td>
          <td class="cell-name"></td>
          <td class="cell-icon"></td>
        </tr>
        """
        row = BeautifulSoup(html, "lxml").find("tr")
        assert scraper.extract_row_data(row) is None

    def test_non_numeric_dex_number_returns_none(self):
        row = make_row("N/A", "Mystery", "/pokedex/mystery", ["Normal"])
        assert scraper.extract_row_data(row) is None


class TestExtractBaseStats:
    def _stats_page(self, rows_html: str, with_heading: bool = True) -> BeautifulSoup:
        heading = "<h2>Base stats</h2>" if with_heading else ""
        html = f"""
        <html><body>
          <h2>Pokedex data</h2>
          <table class="vitals-table">
            <tr><th>National №</th><td>1</td></tr>
          </table>
          {heading}
          <table class="vitals-table">
            {rows_html}
          </table>
        </body></html>
        """
        return BeautifulSoup(html, "lxml")

    def test_extracts_all_six_stats_scoped_to_base_stats_table(self):
        rows_html = "".join(
            f"<tr><th>{label}</th><td>{value}</td></tr>"
            for label, value in [
                ("HP", 45), ("Attack", 49), ("Defense", 49),
                ("Sp. Atk", 65), ("Sp. Def", 65), ("Speed", 45),
            ]
        )
        page = self._stats_page(rows_html)

        stats = scraper.extract_base_stats(page)

        assert stats == {
            "HP": 45, "Attack": 49, "Defense": 49,
            "Sp. Atk": 65, "Sp. Def": 65, "Speed": 45,
        }

    def test_ignores_unrelated_table_without_base_stats_heading(self):
        # The "Pokedex data" table also has a numeric second column ("1")
        # but must not be mistaken for base stats.
        page = self._stats_page("<tr><th>HP</th><td>45</td></tr>")
        stats = scraper.extract_base_stats(page)
        assert stats["HP"] == 45
        # Unrelated rows from other tables should not leak into base stats.
        assert all(key in scraper.BASE_STATS for key in stats)

    def test_missing_stats_default_to_zero(self):
        rows_html = "<tr><th>HP</th><td>45</td></tr>"
        page = self._stats_page(rows_html)
        stats = scraper.extract_base_stats(page)
        assert stats["HP"] == 45
        assert stats["Speed"] == 0

    def test_falls_back_to_whole_page_when_heading_missing(self):
        rows_html = "<tr><th>HP</th><td>60</td></tr>"
        page = self._stats_page(rows_html, with_heading=False)
        stats = scraper.extract_base_stats(page)
        # Fallback scans all rows on the page, so it still finds HP.
        assert stats["HP"] == 60

    def test_non_numeric_stat_value_is_skipped(self):
        rows_html = "<tr><th>HP</th><td>N/A</td></tr>"
        page = self._stats_page(rows_html)
        stats = scraper.extract_base_stats(page)
        assert stats["HP"] == 0


class TestValidateRecords:
    def test_accepts_exactly_151_records(self):
        records = [{"national_dex": i} for i in range(1, 152)]
        scraper.validate_records(records)  # should not raise

    def test_rejects_other_counts(self):
        with pytest.raises(ValueError):
            scraper.validate_records([{"national_dex": 1}])

        with pytest.raises(ValueError):
            scraper.validate_records([{"national_dex": i} for i in range(1, 200)])


class TestScraperRemovals:
    def test_special_slugs_mapping_removed(self):
        assert not hasattr(scraper, "SPECIAL_SLUGS")

    def test_normalize_slug_function_removed(self):
        assert not hasattr(scraper, "normalize_slug")


class TestRetryConfiguration:
    def test_build_session_configures_retry_for_transient_failures(self):
        session = scraper.build_session()
        adapter = session.get_adapter("https://pokemondb.net")
        retry = adapter.max_retries

        assert retry.total == scraper.MAX_RETRIES
        assert 429 in retry.status_forcelist
        assert 500 in retry.status_forcelist
        assert 502 in retry.status_forcelist
        assert 503 in retry.status_forcelist
        assert 504 in retry.status_forcelist
        # 404 (permanent failure) should not be retried.
        assert 404 not in retry.status_forcelist

    def test_build_session_applies_custom_headers(self):
        session = scraper.build_session()
        assert session.headers["User-Agent"] == scraper.HEADERS["User-Agent"]


class TestDelayBetweenDetailRequests(object):
    def test_delay_applied_between_detail_requests_but_not_before_first(self, monkeypatch):
        sleep_calls: List[float] = []
        monkeypatch.setattr(scraper.time, "sleep", lambda seconds: sleep_calls.append(seconds))
        monkeypatch.setattr(scraper, "REQUEST_DELAY_SECONDS", 0.25)

        list_html = """
        <table id="pokedex"><tbody>
        <tr><td><span>1</span></td><td class="cell-name">
          <a class="ent-name" href="/pokedex/bulbasaur">Bulbasaur</a></td>
          <td class="cell-icon"><a class="itype">Grass</a></td></tr>
        <tr><td><span>2</span></td><td class="cell-name">
          <a class="ent-name" href="/pokedex/ivysaur">Ivysaur</a></td>
          <td class="cell-icon"><a class="itype">Grass</a></td></tr>
        <tr><td><span>3</span></td><td class="cell-name">
          <a class="ent-name" href="/pokedex/venusaur">Venusaur</a></td>
          <td class="cell-icon"><a class="itype">Grass</a></td></tr>
        </tbody></table>
        """
        list_page = BeautifulSoup(list_html, "lxml")

        def fake_fetch_page(url, session=None):
            assert session is not None or url == scraper.POKEDEX_URL
            return list_page

        monkeypatch.setattr(scraper, "fetch_page", fake_fetch_page)
        monkeypatch.setattr(
            scraper,
            "fetch_pokemon_stats",
            lambda url, session=None: {stat: 10 for stat in scraper.BASE_STATS},
        )

        records = scraper.scrape_gen_1()

        assert len(records) == 3
        # 3 detail requests => 2 delays (no delay before the first detail
        # request, and the initial list request is never delayed).
        assert sleep_calls == [0.25, 0.25]
