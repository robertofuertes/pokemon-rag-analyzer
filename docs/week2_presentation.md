# Week 2 Progress Presentation: Database Schema & Hybrid Storage Setup

## Slide 1 — Project overview

**Project:** Pokémon Gen 1 AI Battle Analyzer  
**Repository:** `robertofuertes/pokemon-rag-analyzer`  
**Current stage:** Week 2 of the four-week roadmap  
**Primary goal:** Turn scraped Pokémon data into a reliable relational foundation for exact battle analysis and the later hybrid RAG pipeline.

The project is designed to combine:

- structured SQL queries for exact facts such as stats and comparisons;
- retrieval-based context for tactical explanations;
- an AI layer that turns those results into useful battle recommendations.

---

## Slide 2 — Roadmap position

### Week 1: completed foundation

The repository already contains a scraper that:

- requests the PokémonDB Gen 1 Pokédex page;
- parses rows with BeautifulSoup and `lxml`;
- captures national Pokédex number, name, and primary/secondary type;
- follows each Pokémon link to collect HP, Attack, Defense, Special Attack, Special Defense, and Speed;
- validates that exactly 151 records are collected;
- writes the result to `pokemon_gen1.json`.

### Week 2: current work

This week adds the MySQL relational data layer and the import process.

### Week 3: next stage

The SQL layer will be combined with vector retrieval and Ollama-based generation for hybrid RAG responses.

### Week 4: final delivery

The project will receive a CLI or lightweight UI, tests, and final polish.

---

## Slide 3 — Why a relational database?

A database is needed because the analyzer must answer exact questions consistently.

Examples:

- Which Gen 1 Pokémon has the highest Speed?
- Compare Charizard and Blastoise by total base stats.
- Which Pokémon have a Water or Electric weakness?
- What damage multiplier applies when Fire attacks Grass?
- Which candidates resist a selected attacking type?

These are structured questions. MySQL is a better fit than asking a language model to remember numeric facts because it provides:

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

This separates reusable reference data from Pokémon records and keeps statistics normalized instead of storing repeated type names in every row.

---

## Slide 5 — `pokemon_types`

The type table provides stable IDs for the original 15 Gen 1 types:

- Normal
- Fire
- Water
- Electric
- Grass
- Ice
- Fighting
- Poison
- Ground
- Flying
- Psychic
- Bug
- Rock
- Ghost
- Dragon

The `name` column is unique, so duplicate type records cannot be inserted accidentally.

Using IDs instead of repeated strings gives the rest of the schema consistent foreign-key relationships and makes type-chart joins straightforward.

---

## Slide 6 — `pokemon` profile table

The profile table stores:

- `national_dex` as the primary key;
- Pokémon name as a unique value;
- a required primary type;
- an optional secondary type;
- a creation timestamp.

The schema intentionally allows a missing secondary type because many Gen 1 Pokémon are single-type Pokémon.

Foreign keys enforce that both type references point to valid rows in `pokemon_types`.

Indexes on the primary and secondary type columns support matchup and filtering queries.

---

## Slide 7 — `pokemon_base_stats`

The stat table stores one row per Pokémon:

- HP
- Attack
- Defense
- Special Attack
- Special Defense
- Speed

Its primary key is also a foreign key to `pokemon.national_dex`.

This is a one-to-one relationship. Deleting a Pokémon automatically deletes its stats through `ON DELETE CASCADE`, preventing orphaned stat rows.

The schema uses unsigned small integers because Gen 1 base stats are non-negative and comfortably fit within that range.

---

## Slide 8 — `type_effectiveness`

This table models the battle type chart:

- `attack_type_id`
- `defender_type_id`
- `multiplier`

Example values:

- Fire → Grass = `2.00`
- Water → Fire = `2.00`
- Electric → Ground = `0.00`
- Normal → Ghost = `0.00`
- Fire → Water = `0.50`

The composite primary key prevents duplicate attack/defender pairs. The multiplier constraint prevents invalid negative or excessively large values.

Pairs not explicitly listed by the loader are neutral at `1.0`; the seeded rows focus on non-neutral Gen 1 interactions.

---

## Slide 9 — Readable reporting view

The schema includes `v_pokemon_profiles`, a view that joins the profile and stat tables.

It exposes:

- Pokédex number;
- name;
- readable type names;
- all six base stats;
- calculated base-stat total.

This view gives Week 3 a clean read model for SQL queries and avoids repeating the same joins throughout application code.

Example future query:

```sql
SELECT name, primary_type, secondary_type, base_stat_total
FROM v_pokemon_profiles
ORDER BY base_stat_total DESC
LIMIT 10;
```

---

## Slide 10 — Import pipeline

`database/load_pokemon_data.py` automates the database setup:

1. Loads connection values from `.env`.
2. Connects to MySQL without assuming the database already exists.
3. Executes `database/schema.sql`.
4. Inserts the canonical Gen 1 type list using duplicate-safe inserts.
5. Seeds non-neutral type-effectiveness relationships.
6. Reads `pokemon_gen1.json` produced by the Week 1 scraper.
7. Upserts Pokémon profiles.
8. Upserts all six base stats.
9. Commits the transaction and reports the imported record count.
10. Closes the connection in a `finally` block.

The upsert behavior makes the loader safe to run again after refreshing scraped data.

---

## Slide 11 — Configuration and reproducibility

`.env.example` documents the required configuration:

```text
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=change-me
MYSQL_DATABASE=pokemon_rag
POKEMON_JSON_PATH=./pokemon_gen1.json
```

The actual `.env` file should remain local and should not be committed.

The existing `requirements.txt` already includes the required dependencies:

- `mysql-connector-python` for MySQL access;
- `python-dotenv` for environment loading;
- the existing scraping dependencies for Week 1.

---

## Slide 12 — How to run Week 2

From the repository root:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env with the local MySQL credentials
python scraper.py
python database/load_pokemon_data.py
```

Optional direct schema execution:

```bash
mysql -u root -p < database/schema.sql
```

The loader itself also executes the schema, so the direct MySQL command is useful for inspection or manual database setup but is not required for the normal flow.

---

## Slide 13 — Validation checklist

Before considering Week 2 complete, verify:

- MySQL is running and the credentials in `.env` are correct.
- `pokemon_gen1.json` exists and contains 151 records.
- The loader finishes without a foreign-key error.
- `SELECT COUNT(*) FROM pokemon;` returns 151.
- `SELECT COUNT(*) FROM pokemon_base_stats;` returns 151.
- `SELECT COUNT(*) FROM pokemon_types;` returns 15.
- Type-effectiveness rows exist for non-neutral matchups.
- The profile view returns Pokémon names, types, stats, and totals.
- Re-running the loader does not create duplicates.

Example checks:

```sql
SELECT COUNT(*) FROM pokemon;
SELECT COUNT(*) FROM pokemon_base_stats;
SELECT COUNT(*) FROM pokemon_types;
SELECT * FROM v_pokemon_profiles LIMIT 5;
```

---

## Slide 14 — What has been completed so far

### Existing foundation

- Repository created and organized as a Python project.
- Scraping dependencies pinned in `requirements.txt`.
- Gen 1 scraper implemented with HTTP handling, HTML parsing, special-name handling, stat extraction, and 151-record validation.
- Four-week roadmap documented.

### Week 2 implementation

- Normalized MySQL schema added.
- Foreign keys, indexes, uniqueness rules, and cascading behavior added.
- Type-effectiveness model added.
- Readable aggregate view added.
- Repeatable JSON-to-MySQL loader added.
- Environment template added.
- Database setup documentation added.

---

## Slide 15 — Current limitations and honest status

The repository currently contains the Week 2 implementation files, but successful execution still depends on the local environment:

- a running MySQL server;
- valid credentials in `.env`;
- a generated `pokemon_gen1.json` file;
- installed Python dependencies.

The database has not been claimed as populated until those environment-dependent checks are run.

Also, vector storage and Ollama integration are intentionally not part of this week. They belong to Week 3.

---

## Slide 16 — Transition to Week 3

The relational layer now gives the future AI pipeline reliable structured facts.

Week 3 will add:

1. SQL query helpers for exact stat comparisons.
2. Type-matchup retrieval for tactical context.
3. ChromaDB or another vector store for unstructured strategy knowledge.
4. Query routing between structured SQL and semantic retrieval.
5. Ollama integration to produce battle recommendations grounded in retrieved data.

The key design principle is that the language model should explain verified results rather than inventing numeric battle facts.

---

## Slide 17 — Summary

Week 2 converts the scraper output into a reusable data foundation.

The system can now be structured around:

- normalized Pokémon profiles;
- validated base stats;
- reusable elemental types;
- explicit battle multipliers;
- repeatable imports;
- a clean SQL view for downstream queries.

This is the bridge between data collection in Week 1 and the hybrid RAG intelligence planned for Week 3.
