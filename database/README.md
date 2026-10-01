# Week 2: Database Schema & Hybrid Storage Setup

This stage adds the relational (MySQL) and vector (ChromaDB) storage layers
for the Pokémon battle analyzer.

## What is included

- `database/schema.sql` — DDL template for the core MySQL tables. The
  `{{DB_NAME}}` placeholder is substituted with the validated
  `MYSQL_DATABASE` value at load time.
- `database/load_pokemon_data.py` — loader that creates the schema, seeds
  the modern 18-type matchup table, and imports scraped Pokémon data (still
  scraped from National Dex #1–151 only, for speed). Honors `MYSQL_DATABASE`
  from `.env` consistently (used both to create/select the database and to
  report the loaded record count).
- `database/build_vector_index.py` — builds/queries a local, persistent
  ChromaDB collection of tactical documents for the 151 Gen 1 Pokémon.
- `.env.example` — environment variables for MySQL connectivity, scraper
  behavior, and the vector index.

## MySQL setup

1. Create a local MySQL Community Server instance.
2. Copy `.env.example` to `.env` and update the connection values,
   including `MYSQL_DATABASE` if you want a database name other than
   `pokemon_rag`.
3. Load the scraped Pokémon data (the loader also creates/updates the
   schema, so this single command is enough for a normal run):

   ```bash
   python database/load_pokemon_data.py
   ```

   Or, to execute the schema directly with the `mysql` CLI, substitute the
   `{{DB_NAME}}` placeholder first:

   ```bash
   sed "s/{{DB_NAME}}/$MYSQL_DATABASE/g" database/schema.sql | mysql -u "$MYSQL_USER" -p
   ```

### Database name handling

`MYSQL_DATABASE` (default `pokemon_rag`) must be a plain identifier:
letters, digits, and underscores only, starting with a letter or
underscore, and no longer than 64 characters
(`^[A-Za-z_][A-Za-z0-9_]{0,63}$`). The loader validates this value and
backtick-quotes it before substituting it into the schema SQL, instead of
interpolating an arbitrary string into SQL text. Invalid values raise a
clear `ValueError` before any SQL runs.

## Tables

- `pokemon_types` keeps the canonical elemental type list. Scraping scope
  stays limited to National Dex #1–151 for speed, but the type list itself
  covers the full modern (post Gen 6) 18-type set — Normal, Fire, Water,
  Electric, Grass, Ice, Fighting, Poison, Ground, Flying, Psychic, Bug,
  Rock, Ghost, Dragon, Dark, Steel, and Fairy — since the live source now
  reports present-day/retconned typings for some Gen 1 Pokémon (e.g. several
  were later given the Fairy type).
- `pokemon` stores each scraped Pokémon record (#1–151), including the
  primary and secondary type as reported by the source today.
- `pokemon_base_stats` stores the six core stats.
- `type_effectiveness` stores present-day attack type vs defender type
  damage multipliers for all 18 modern types.

Re-running `load_pokemon_data.py` is safe: the schema uses
`CREATE ... IF NOT EXISTS`, and Pokémon/stat rows are inserted with
`ON DUPLICATE KEY UPDATE` upserts.

## ChromaDB vector index setup

The vector index stores one tactical document per Pokémon, generated
deterministically from the scraped types and base stats (no invented move
learnsets or unsourced competitive claims). Embeddings are produced locally
with a dependency-light, deterministic hashing embedding function — no
Ollama, no external embedding service, and no network access required.

Build (or refresh) the index:

```bash
python database/build_vector_index.py build
```

This is idempotent: each Pokémon gets a stable ID (`pokemon-###`), and
re-running the command `upsert`s the same IDs instead of creating
duplicates.

Run a semantic retrieval test query:

```bash
python database/build_vector_index.py query "fast special attacker" --n-results 5
```

Each result returns the document text and metadata (`national_dex`, `name`,
`primary_type`, `secondary_type`, `combat_role`, `synergy_tags`, `source`,
`schema_version`).

`chromadb` is imported lazily/optionally in `build_vector_index.py`, so
scraper and MySQL-loader tests can still run in environments where
`chromadb` isn't installed. It is still listed in `requirements.txt` since
it's required to actually build or query the index.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | MySQL connection settings |
| `POKEMON_JSON_PATH` | Path to the scraped `pokemon_gen1.json` |
| `SCRAPER_REQUEST_DELAY_SECONDS` | Delay between Pokémon detail-page requests (the initial list request is never delayed) |
| `SCRAPER_TIMEOUT_SECONDS` | Per-request HTTP timeout |
| `SCRAPER_MAX_RETRIES`, `SCRAPER_BACKOFF_FACTOR` | Retry/backoff for transient HTTP failures (timeouts, connection errors, 429, 5xx) |
| `VECTOR_INDEX_PERSIST_DIRECTORY` | Local directory where ChromaDB persists its data |
| `VECTOR_INDEX_COLLECTION_NAME` | Chroma collection name |
| `VECTOR_INDEX_EMBEDDING_DIMENSIONS` | Dimensionality of the deterministic hashing embedding function |

## Running the tests

The test suite requires no live MySQL server, internet access, Ollama, or a
preexisting Chroma database:

```bash
pip install -r requirements.txt
pytest
```

This gives Week 3 a validated relational foundation *and* a vector index
foundation to build the hybrid RAG query layer on top of.
