# Build Plan

v1 is an AI football analyst for Arsenal's 2003–04 and 2025–26 seasons: ask a
question in plain English, get an interactive, verified answer. Build the data
foundation first (ingestion, schema, entity resolution, data catalog), then the
MCP tool server, then the LangChain agent with verification, then the design
system and UI, then evals and deployment. More seasons, similarity search, and a
published MCP package are bonus features and should only be attempted after v1
is stable.

Estimated effort: **~6 weeks at 1.5–2 hours/day (~70 hours)**. Plan to start
after Upstream is deployed.

- [ ] 1. **Repository + project foundation** - monorepo with `apps/web` (Next.js, TypeScript, Tailwind, shadcn/ui), `services/analyst` (Python 3.12, uv, FastAPI), and `ingest/` (Python scripts); Docker Compose for local PostgreSQL; `.env.example`, ruff/eslint/prettier, a task runner, README skeleton with the unofficial-fan-project notice
- [ ] 2. **Database schema + roles** - SQL migrations for seasons, teams, players, player_aliases, matches, events, shots, player_match_stats, data_catalog; indexes for common filters (season, player, match); `ingest` role with write access and `analyst_ro` read-only role with statement timeout; column comments written for the LLM (these become `get_schema` output)
- [ ] 3. **Ingest 2003–04 (StatsBomb)** - load matches, lineups, and events for the season via `statsbombpy`; normalize coordinates to the shared pitch system; populate events, shots (with StatsBomb xG), matches, and player_match_stats; tests for coordinate conversion and row counts
- [ ] 4. **Ingest 2025–26 (Understat, FPL, football-data.co.uk)** - shots with xG and coordinates, match xG, per-gameweek player stats, results; cache raw files locally (git-ignored); normalize coordinates; respect each source's terms; idempotent re-runs
- [ ] 5. **Entity resolution** - map every source player and team to canonical IDs using source IDs, rapidfuzz name matching, and a hand-maintained `overrides.yaml`; output a review report of low-confidence matches; tests for known tricky names
- [ ] 6. **Data catalog** - populate `data_catalog` per season and feature (events, pass maps, pressures, shots, xG, minutes, assists…); a sanity-check script that verifies totals against known season facts (goals scored, points, top scorers)
- [ ] 7. **MCP tool server** - FastMCP server exposing `get_data_catalog`, `get_schema`, `resolve_player`, `run_sql`, and `build_chart`; `run_sql` parses with sqlglot, rejects non-SELECT statements, enforces a LIMIT and the read-only role, and returns rows + the executed SQL; `build_chart` returns Pydantic-validated chart specs (shot_map, pass_network, xg_timeline, compare_bars, points_pace); test standalone with the MCP inspector
- [ ] 8. **LangChain agent** - `create_agent` with MCP tools via `langchain-mcp-adapters`, model from `init_chat_model` config, system prompt with schema and catalog context (prompt-cached), structured output (`summary`, `claims[]`, `charts[]`, `caveats[]`); middleware for scope guard and tool-call budget; conversation memory for follow-ups
- [ ] 9. **Claim verifier** - middleware/post-step that records every tool output, checks each claim's value against those outputs (with numeric tolerance), removes or regenerates unsupported claims once, and attaches a verification summary; tests with deliberately wrong claims
- [ ] 10. **FastAPI service + streaming** - `POST /api/ask` streaming agent steps and the final answer over SSE; `GET /api/seasons`, `/api/seasons/:id/overview`, `/api/players/:id`, `/api/suggestions`, `/api/health`; per-IP rate limiting; answer cache for suggested questions; structured logging with cost and latency per request
- [ ] 11. **Design in Figma first** - moodboard and mockups for the landing page, Ask page (streaming + answer), Season page with the switcher, and one chart of each type; settle palette, type scale, spacing, and chart styling before coding
- [ ] 12. **Web: design system** - tokens (dark canvas, red accent, neutrals), Barlow Condensed + body sans + mono, buttons, chips, cards, badges, step list, data tables, skeletons; chart theme shared by all D3/visx components
- [ ] 13. **Web: pitch + chart components** - reusable SVG pitch; shot map (xG size, outcome shape, hover details, filters), pass network, xG timeline, compare bars, points pace; each renders from the chart-spec JSON validated with Zod, with a text summary and data table for accessibility
- [ ] 14. **Web: Ask the Analyst** - question bar with suggestion chips; live step list from SSE; answer panel with analysis, charts, verification badge (expandable claim checks), caveats, and "Show the working" (SQL, tools, sources); follow-up questions; error and rate-limit states
- [ ] 15. **Web: landing + season + player pages** - landing hero with the era hook, live example answer, architecture and evals sections; Season page with the Invincibles ↔ 2025–26 morphing switcher; Player pages for key players
- [ ] 16. **Evals + model comparison** - golden set of ~50 questions (single-season facts, player comparisons, cross-era comparisons, chart requests, unavailable-data questions, out-of-scope questions) with expected answers from hand-written SQL; runner measuring correctness, claim verification rate, chart choice, correct refusals, tool calls, latency, and cost; run on 2–3 models; publish the comparison table in the README and on the landing page
- [ ] 17. **Responsive + accessibility polish** - mobile chart sizing, filter sheets, collapsed steps; keyboard navigation for charts; focus states; contrast checks on the dark theme; reduced motion
- [ ] 18. **Deployment + production hardening** - managed PostgreSQL (Neon or Supabase) with migrations and a one-off ingest load; FastAPI container on AWS ECS Express Mode; web on Vercel; provider spending limits; CORS, rate limits, health checks; warm the suggested-question cache; record a 2-minute demo video
- [ ] 19. **Bonus: more seasons, similarity, MCP package** - add seasons as free data allows, player similarity with embeddings (pgvector), verified match reports, and publish the MCP server as a standalone package; do not start until 1–18 are done

## Suggested schedule

| Week | Steps | Focus |
|---|---|---|
| 1 | 1–4 | Foundation, schema, ingestion of both seasons |
| 2 | 5–7 | Entity resolution, data catalog, MCP tool server |
| 3 | 8–10 | Agent, claim verifier, streaming API |
| 4 | 11–12 | Figma design, design system |
| 5 | 13–15 | Pitch visuals, Ask page, landing and season pages |
| 6 | 16–18 | Evals and model comparison, polish, deployment, demo |

## LLM budget (~$10–15)

| Use | Model approach | Rough cost |
|---|---|---|
| Daily development | Low-cost Flash-tier model (free tier where possible) | ~$0–3 |
| Eval runs (50 questions × 2–3 models × 2–3 runs) | Compare a low-cost model, a mid-tier model, and one stronger model | ~$5–8 |
| Public demo | Chosen model, cached suggested questions, rate limits, hard spending cap | ~$2–4 |

Set a hard monthly spending limit with the provider before deploying the public demo.

## Deployment notes

Decisions settled up front so deployment does not become a separate
architectural problem at the end:

- **Three deployables** - Next.js on Vercel, the FastAPI container (MCP server inside as a stdio subprocess), and managed PostgreSQL
- **Database roles** - the deployed agent connects only as `analyst_ro`; the `ingest` credentials are never deployed
- **Data loading** - ingestion runs locally or as a one-off job against the managed database; the runtime never scrapes
- **Environment variables** - model provider keys, model name, database URL, CORS origins, and rate limits stay out of source control; validate at startup
- **Cost controls** - provider spending caps, per-IP rate limits, tool-call budget, answer cache for suggested questions
- **Streaming** - confirm SSE works through the hosting provider's proxy (disable buffering) before building the full UI on it
- **Deploy early** - deploy as soon as `/api/ask` returns a verified answer end to end (after step 10), then keep every later change flowing through the same pipeline

## Later (not v1)

Only if Highbury grows beyond the portfolio demo. Not scheduled; revisit after
v1 ships.

- More historical and recent seasons
- Player similarity scout (pgvector embeddings)
- Verified match report generator
- Published MCP server package and docs
- Opponent and league-wide context
- User accounts with saved questions and shareable answer links
- Light theme
