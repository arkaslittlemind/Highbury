-- PostgreSQL gives every role TEMPORARY on a database through PUBLIC. Without
-- this revoke, analyst_ro can create and fill temporary tables.
DO $$
BEGIN
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
END
$$;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ingest;

-- The views match 'goal' and 'pass' exactly, so a loader must store lowercase.
ALTER TABLE shots ADD CONSTRAINT shots_outcome_lowercase CHECK (outcome = lower(outcome));
ALTER TABLE events ADD CONSTRAINT events_type_lowercase CHECK (type = lower(type));
