# Week 2 Progress Presentation: Database Schema & Hybrid Storage Setup

## Slide 1 — Project overview

**Project:** Pokémon Gen 1 AI Battle Analyzer
**Repository:** `robertofuertes/pokemon-rag-analyzer`
**Current stage:** Week 2 of the four-week roadmap
**Primary goal:** Turn scraped Pokémon data into both a reliable relational
foundation (MySQL) and a semantic retrieval foundation (ChromaDB) for the
later hybrid RAG pipeline.

The project is designed to combine:

- structured SQL queries for exact facts such as stats and comparisons;
- vector retrieval for tactical, stat-derived context;
- an AI layer (Week 3+) that turns those results into useful battle
  recommendations.

---

## Slide 2 — Roadmap position

### Week 1: completed foundation

The repository contains a scraper that:

- requests the PokémonDB Gen 1 Pokédex page;
- parses rows with BeautifulSoup and `lxml`;
- captures national Pokédex number, name, and primary/secondary type using
  the href already present in the Pokédex table row (no separate slug
  reconstruction needed);
- follows each Pokémon link to collect HP, Attack, Defense, Special Attack,
  Special Defense, and Speed, scoped to the "Base stats" table on the page;
- retries transient HTTP failures (timeouts, connection errors, 429, 5xx)
  with backoff, while still raising immediately on permanent failures;
- applies a polite, configurable delay between detail-page requests only
  (the initial Pokédex list request is not delayed);
- validates that exactly 151 records are collected;
- writes the result to a predictable `pokemon_gen1.json` path next to the
  script, regardless of the caller's working directory.

### Week 2: current work

This week adds:

1. the MySQL relational data layer and import process;
2. a local ChromaDB vector index of tactical documents;
3. a pytest test suite covering both, with no external services required.

### Week 3: next stage

The SQL layer and vector index will be combined with Ollama-based
generation for hybrid RAG responses.

### Week 4: final delivery

The project will receive a CLI or lightweight UI, additional tests, and
final polish.

---

## Slide 3 — Why a relational database?

A database is needed because the analyzer must answer exact questions
consistently.

Examples:

- Which Gen 1 Pokémon has the highest Speed?
- Compare Charizard and Blastoise by total base stats.
- Which Pokémon have a Water or Electric weakness?
- What damage multiplier applies when Fire attacks Grass?
- Which candidates resist a selected attacking type?

These are structured questions. MySQL is a better fit than asking a
language model to remember numeric facts because it provides:

- deterministic filtering and sorting;
- primary keys and uniqueness constraints;
- foreign-key validation;
- repeatable updates when the scraper is run again;
- efficient joins between Pokémon, types, stats, and matchups.

---

## Slide 4 — Database architecture

The Week 2 design uses four core tables:

```text
pokemon_types
    │
    ├── pokemon.primary_type_id
    ├── pokemon.secondary_type_id
    │
    └── type_effectiveness.attack_type_id
        type_effectiveness.defender_type_id

pokemon ─── pokemon_base_stats
```

### Responsibilities

- `pokemon_types`: canonical list of Gen 1 elemental types.
- `pokemon`: one row per Pokémon profile and its type relationships.
- `pokemon_base_stats`: six numeric base stats for each Pokémon.
- `type_effectiveness`: attack-type-to-defender-type multipliers.

This separates reusable reference data from Pokémon records and keeps
statistics normalized instead of storing repeated type names in every row.

---

## Slide 5 — Configurable database name, safely

Earlier revisions hardcoded the database name (`pokemon_rag`) directly in
`schema.sql`, while `.env` already exposed a configurable `MYSQL_DATABASE`.
This was fixed by:

- turning `schema.sql` into a small template with a `{{DB_NAME}}`
  placeholder instead of a hardcoded name;
- having `load_pokemon_data.py` substitute that placeholder with the
  `MYSQL_DATABASE` value from `.env` before executing any SQL;
- validating that value against a strict identifier pattern
  (`^[A-Za-z_][A-Za-z0-9_]{0,63}$`) and backtick-quoting it, instead of
  interpolating an arbitrary string into SQL text.

This keeps the database name consistent across `.env`, the schema, and the
loader, without opening the door to SQL injection through a misconfigured
or malicious `MYSQL_DATABASE` value.

---

## Slide 6 — `pokemon_types`, `pokemon`, `pokemon_base_stats`, `type_effectiveness`

- `pokemon_types`: stable IDs for the 15 Gen 1 elemental types, with a
  unique `name` column.
- `pokemon`: `national_dex` primary key, unique name, required primary
  type, optional secondary type (many Gen 1 Pokémon are single-typed).
- `pokemon_base_stats`: one row per Pokémon (HP, Attack, Defense, Sp. Atk,
  Sp. Def, Speed), primary key doubling as a foreign key to
  `pokemon.national_dex`, with `ON DELETE CASCADE` to avoid orphaned rows.
- `type_effectiveness`: composite-keyed attack/defender multipliers (e.g.
  Fire → Grass = `2.00`, Electric → Ground = `0.00`); pairs not listed are
  neutral (`1.0`).

A reporting view, `v_pokemon_profiles`, joins Pokémon, types, and stats and
exposes a computed `base_stat_total` for convenient downstream queries.

---

## Slide 7 — MySQL import pipeline

`database/load_pokemon_data.py` automates the database setup:

1. Loads connection values from `.env`, including `MYSQL_DATABASE`.
2. Validates `MYSQL_DATABASE` as a safe identifier.
3. Substitutes the validated, quoted database name into `schema.sql` and
   executes it (creating the database and tables if needed).
4. Inserts the canonical Gen 1 type list using duplicate-safe inserts.
5. Seeds non-neutral type-effectiveness relationships.
6. Reads `pokemon_gen1.json` produced by the Week 1 scraper.
7. Upserts Pokémon profiles and all six base stats.
8. Commits the transaction and reports the imported record count.
9. Closes the connection in a `finally` block.

The upsert behavior makes the loader safe to run again after refreshing
scraped data.

---

## Slide 8 — ChromaDB vector indexing (new this week)

`database/build_vector_index.py` fills in the previously-missing Week 2
vector-indexing deliverable:

- Creates/opens a **local, persistent** Chroma collection
  (`chroma_data/` by default — not committed to the repository).
- Generates one **tactical document per Pokémon** from the scraped JSON:
  types, base stats, a derived likely combat role (e.g. "fast attacker",
  "defensive wall", "special attacker"), and type/stat-derived synergy tags
  (e.g. `high-special-attack`, `type-fire`, `slow`).
- Documents are **transparent and deterministic** — generated only from
  structured scraped data. No move learnsets or sourced competitive claims
  are invented, since the scraper does not currently capture move data.
- Stores stable IDs (`pokemon-###`), the document text, and metadata:
  `national_dex`, `name`, `primary_type`, `secondary_type`, `combat_role`,
  `synergy_tags`, `source`, and a `schema_version` marker.
- Uses `collection.upsert(...)` keyed by the stable ID, so **re-running the
  build is idempotent** — it updates existing documents instead of
  duplicating them.
- Includes a CLI `query` command to test semantic retrieval locally and
  print back matching documents and metadata.

### Offline-first embeddings

Rather than depending on Ollama or a networked embedding API, the module
ships a small `DeterministicHashingEmbeddingFunction`: it hashes each
token (SHA-256) into a fixed-size vector, so the same text always produces
the same embedding, with no model download and no external dependency
beyond `chromadb` itself. This keeps the Week 2 pipeline runnable fully
offline; a Week 3+ effort could later swap in a stronger embedding model
without changing the document-generation logic.

`chromadb` is imported lazily/optionally in the module, so the scraper and
MySQL-loader tests continue to run even in environments where `chromadb`
isn't installed — it's still listed in `requirements.txt` since it's
required to actually build or query the index.

---

## Slide 9 — Configuration and reproducibility

`.env.example` documents the required configuration:

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
MYSQL_DATABASE=pokemon_rag
POKEMON_JSON_PATH=./pokemon_gen1.json

SCRAPER_REQUEST_DELAY_SECONDS=0.5
SCRAPER_TIMEOUT_SECONDS=30
SCRAPER_MAX_RETRIES=3
SCRAPER_BACKOFF_FACTOR=0.5

VECTOR_INDEX_PERSIST_DIRECTORY=./chroma_data
VECTOR_INDEX_COLLECTION_NAME=pokemon_gen1_tactics
VECTOR_INDEX_EMBEDDING_DIMENSIONS=256
```

The actual `.env` file, `chroma_data/` (local Chroma persistence), and
`pokemon_gen1.json` all remain local and are excluded via `.gitignore`.

`requirements.txt` now includes:

- `mysql-connector-python` and `python-dotenv` for the MySQL layer;
- `chromadb` for the vector index;
- `pytest` for the test suite;
- the existing scraping dependencies for Week 1.

---

## Slide 10 — How to run Week 2

From the repository root:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with local MySQL credentials

python scraper.py
python database/load_pokemon_data.py
python database/build_vector_index.py build
python database/build_vector_index.py query "fast special attacker"
```

Optional direct schema execution:

```bash
sed "s/{{DB_NAME}}/$MYSQL_DATABASE/g" database/schema.sql | mysql -u root -p
```

The loader itself also executes the schema, so the direct MySQL command is
useful for inspection or manual database setup but is not required for the
normal flow.

---

## Slide 11 — Automated tests (new this week)

A pytest suite in `tests/` covers:

- **Scraper parsing** — normal rows, single-type rows, special-character
  names (e.g. Nidoran♀), truncation of extra types, and malformed rows.
- **Base-stat extraction** — scoped parsing from the "Base stats" table,
  fallback behavior when that heading is missing, and non-numeric value
  handling.
- **151-record validation** — accepted and rejected counts.
- **Retry/backoff configuration** — verifies the configured `Retry` object
  covers 429/5xx and not permanent failures like 404, without making real
  network calls.
- **Detail-page delay behavior** — confirms the configurable delay is
  applied between detail requests and not before the very first one or the
  initial list request, using monkeypatched I/O.
- **Vector index document generation** — deterministic embeddings, combat
  role/tag derivation, document/metadata/ID generation, and idempotent ID
  stability, all without needing chromadb installed or a live index.
- **Database identifier validation** — accepted/rejected `MYSQL_DATABASE`
  values, including SQL-injection-style inputs, and that `schema.sql` no
  longer hardcodes a database name.

None of the tests require a live MySQL server, internet access, Ollama, or
a preexisting Chroma database:

```bash
pip install -r requirements.txt
pytest
```

---

## Slide 12 — Validation checklist

Before considering Week 2 complete, verify:

- MySQL is running and the credentials in `.env` are correct.
- `pokemon_gen1.json` exists and contains 151 records.
- The loader finishes without a foreign-key error.
- `SELECT COUNT(*) FROM pokemon;` returns 151.
- `SELECT COUNT(*) FROM pokemon_base_stats;` returns 151.
- `SELECT COUNT(*) FROM pokemon_types;` returns 15.
- Type-effectiveness rows exist for non-neutral matchups.
- The profile view returns Pokémon names, types, stats, and totals.
- Re-running the loader does not create duplicate rows.
- `python database/build_vector_index.py build` reports 151 indexed
  documents.
- Re-running the vector index build does not duplicate documents (same
  151 stable IDs are upserted).
- `python database/build_vector_index.py query "..."` returns ranked
  documents with metadata.
- `pytest` passes locally.

Example SQL checks:

```sql
SELECT COUNT(*) FROM pokemon;
SELECT COUNT(*) FROM pokemon_base_stats;
SELECT COUNT(*) FROM pokemon_types;
SELECT * FROM v_pokemon_profiles LIMIT 5;
```

---

## Slide 13 — What has been completed so far

### Existing foundation

- Repository created and organized as a Python project.
- Scraping dependencies pinned in `requirements.txt`.
- Gen 1 scraper implemented with retry/backoff, polite delay, scoped
  stat parsing, predictable output paths, and 151-record validation.
- Four-week roadmap documented.

### Week 2 implementation

- Normalized MySQL schema, driven consistently by `MYSQL_DATABASE`.
- Safe identifier validation/quoting instead of raw string interpolation.
- Foreign keys, indexes, uniqueness rules, and cascading behavior.
- Type-effectiveness model and readable aggregate view.
- Repeatable JSON-to-MySQL loader.
- Local, persistent ChromaDB vector index of deterministic tactical
  documents, with idempotent upserts and a query CLI.
- Offline-capable deterministic embedding function (no Ollama, no
  network access required).
- Pytest test suite covering scraper parsing/retry behavior and vector
  index document generation, runnable without external services.
- Updated environment template, `.gitignore`, and documentation.

---

## Slide 14 — Current limitations and honest status

The repository contains the Week 2 implementation files, but successful
end-to-end execution still depends on the local environment:

- a running MySQL server and valid credentials in `.env`, for the
  relational layer;
- a generated `pokemon_gen1.json` file (produced by running the scraper
  against the live pokemondb.net site);
- installed Python dependencies, including `chromadb` for the vector
  index.

The vector index's tactical documents are limited to what the scraper
currently captures (name, types, base stats). They deliberately avoid
inventing move learnsets or sourced competitive claims; a richer
data source would be needed to add those safely.

The deterministic hashing embedding function favors reliability and
offline reproducibility over semantic quality compared to a trained
embedding model — retrieval quality can be improved later (e.g. by
swapping in a local sentence-embedding model) without changing the
document-generation logic.

Ollama integration is intentionally **not** part of this week; it belongs
to Week 3.

---

## Slide 15 — Transition to Week 3

The relational layer and the vector index now give the future AI pipeline
both reliable structured facts and semantic tactical context. Week 3 will
add:

1. SQL query helpers for exact stat comparisons.
2. Type-matchup retrieval for tactical context.
3. Query routing between structured SQL and the existing ChromaDB vector
   index.
4. Prompt engineering and Ollama (Llama 3) integration to produce battle
   recommendations grounded in retrieved data.

The key design principle is that the language model should explain
verified, retrieved results rather than inventing numeric battle facts or
unsourced move data.

---

## Slide 16 — Summary

Week 2 converts the scraper output into a reusable data foundation with
**two** complementary stores:

- a normalized MySQL layer for exact, structured facts;
- a local ChromaDB vector index for deterministic, transparent tactical
  context.

Both are repeatable to (re)build, covered by an automated test suite that
runs without external services, and documented end-to-end. This is the
bridge between data collection in Week 1 and the hybrid RAG intelligence
planned for Week 3.
