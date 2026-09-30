# Week 2: Database Schema & Hybrid Storage Setup

This stage adds the relational storage layer for the Pokémon battle analyzer.

## What is included

- `database/schema.sql` — DDL for the core MySQL tables.
- `database/load_pokemon_data.py` — loader that creates the schema, seeds type matchups, and imports scraped Pokémon data.
- `.env.example` — environment variables for MySQL connectivity.

## MySQL setup

1. Create a local MySQL database instance.
2. Copy `.env.example` to `.env` and update the connection values.
3. Run the schema:

   ```bash
   mysql -u "$MYSQL_USER" -p "$MYSQL_DATABASE" < database/schema.sql
   ```

4. Load the scraped Pokémon data:

   ```bash
   python database/load_pokemon_data.py
   ```

## Tables

- `pokemon_types` keeps the canonical elemental type list.
- `pokemon` stores each Gen 1 Pokémon record, including the primary and secondary type.
- `pokemon_base_stats` stores the six core stats.
- `type_effectiveness` stores attack type vs defender type damage multipliers.

This creates the relational foundation that the hybrid RAG layer can query in Week 3.
