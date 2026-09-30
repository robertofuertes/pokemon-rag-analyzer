-- Week 2 relational database schema for the Pokémon Gen 1 battle analyzer.

CREATE DATABASE IF NOT EXISTS pokemon_rag
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE pokemon_rag;

CREATE TABLE IF NOT EXISTS pokemon_types (
    id SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(32) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_pokemon_type_name (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pokemon (
    national_dex SMALLINT UNSIGNED NOT NULL,
    name VARCHAR(64) NOT NULL,
    primary_type_id SMALLINT UNSIGNED NOT NULL,
    secondary_type_id SMALLINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (national_dex),
    UNIQUE KEY uq_pokemon_name (name),
    KEY idx_pokemon_primary_type (primary_type_id),
    KEY idx_pokemon_secondary_type (secondary_type_id),
    CONSTRAINT fk_pokemon_primary_type
        FOREIGN KEY (primary_type_id) REFERENCES pokemon_types (id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_pokemon_secondary_type
        FOREIGN KEY (secondary_type_id) REFERENCES pokemon_types (id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pokemon_base_stats (
    national_dex SMALLINT UNSIGNED NOT NULL,
    hp SMALLINT UNSIGNED NOT NULL,
    attack SMALLINT UNSIGNED NOT NULL,
    defense SMALLINT UNSIGNED NOT NULL,
    sp_atk SMALLINT UNSIGNED NOT NULL,
    sp_def SMALLINT UNSIGNED NOT NULL,
    speed SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (national_dex),
    CONSTRAINT fk_base_stats_pokemon
        FOREIGN KEY (national_dex) REFERENCES pokemon (national_dex)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS type_effectiveness (
    attack_type_id SMALLINT UNSIGNED NOT NULL,
    defender_type_id SMALLINT UNSIGNED NOT NULL,
    multiplier DECIMAL(3,2) NOT NULL,
    PRIMARY KEY (attack_type_id, defender_type_id),
    CONSTRAINT fk_effectiveness_attack_type
        FOREIGN KEY (attack_type_id) REFERENCES pokemon_types (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_effectiveness_defender_type
        FOREIGN KEY (defender_type_id) REFERENCES pokemon_types (id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_effectiveness_multiplier
        CHECK (multiplier >= 0.00 AND multiplier <= 4.00)
) ENGINE=InnoDB;

CREATE INDEX idx_effectiveness_defender_multiplier
    ON type_effectiveness (defender_type_id, multiplier);

CREATE OR REPLACE VIEW v_pokemon_profiles AS
SELECT
    p.national_dex,
    p.name,
    primary_type.name AS primary_type,
    secondary_type.name AS secondary_type,
    s.hp,
    s.attack,
    s.defense,
    s.sp_atk,
    s.sp_def,
    s.speed,
    (s.hp + s.attack + s.defense + s.sp_atk + s.sp_def + s.speed) AS base_stat_total
FROM pokemon p
JOIN pokemon_types primary_type ON primary_type.id = p.primary_type_id
LEFT JOIN pokemon_types secondary_type ON secondary_type.id = p.secondary_type_id
JOIN pokemon_base_stats s ON s.national_dex = p.national_dex;
