# Design documents

One study document for each finished piece of work, written to the rules of
Simplified Technical English.

- [01 Database schema, views, roles](01-database-schema-views-roles.md) - the tables, the views for the agent, the two database roles, and the migration runner
- [02 Ingest 2003-04 (StatsBomb)](02-ingest-2003-04-statsbomb.md) - the command that loads the 2003-04 season: the raw cache, the transforms, the idempotent loader, and the sanity check before the commit
- [03 Ingest 2025-26 (Understat)](03-ingest-2025-26-understat.md) - the command that loads the 2025-26 season: the mirrored y axis, the shared values of the two seasons, the facts from a second source, and the shared command parts
- [Harden roles and schema checks](2026-10-11-harden-roles-and-schema-checks.md) - the fix for the seven review findings: one default permission removed, one grant added, two checks, and a settings repair
