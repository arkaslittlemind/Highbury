-- Roles are cluster-wide, so they are created only when absent. Passwords are
-- set by the migration runner from the environment, never here.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ingest') THEN
        CREATE ROLE ingest LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analyst_ro') THEN
        CREATE ROLE analyst_ro LOGIN;
    END IF;
    -- Grants are per database: use the one being migrated, not a fixed name.
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO ingest, analyst_ro', current_database());
END
$$;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO ingest, analyst_ro;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON
    seasons, teams, players, player_aliases, matches, shots, events,
    player_match_stats, data_catalog
TO ingest;

GRANT SELECT ON
    seasons, teams, players, player_aliases, matches, shots, events,
    player_match_stats, data_catalog,
    v_matches, v_shots, v_player_match, v_player_season, v_passes
TO analyst_ro;

-- The missing write grants are the real lock. These two settings are defaults a
-- session could change, so the SQL guard in the analyst service must reject SET.
ALTER ROLE analyst_ro SET default_transaction_read_only = on;
ALTER ROLE analyst_ro SET statement_timeout = '5s';
