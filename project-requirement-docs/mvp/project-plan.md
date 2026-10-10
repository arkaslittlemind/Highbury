# Highbury — Project Plan (MVP)

> 5-day MVP of the full plan in `../highbury-project-plan.md`. This file is the
> Blueprint `project-plan.md`: it defines what the MVP is. The order of work is
> in `build-plan.md`. The reasoning behind the cuts is in `../highbury-mvp-plan.md`.
>
> Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the
> Premier League. No club crests, logos, or player photos.

## 1. Problem

General-purpose chatbots answer football questions confidently and often
wrongly: they invent numbers, mix up seasons, and never say when data doesn't
exist.

**Highbury** is an AI football analyst for two Arsenal seasons: **2003–04 (The
Invincibles)** and **2025–26**. A user asks a question in plain English. An
agent queries a curated database through tools, returns a short written answer
with an interactive pitch chart, and checks **every number against the data**
before showing it. When the data can't answer, it says so and offers what it
can show instead.

## 2. Users

- **Fans:** ask in plain English, see shot maps and comparisons
- **Analysts:** see the SQL, tools, and sources behind each answer
- **Reviewers (the demo audience):** understand the architecture, guardrails,
  eval results, and cost per answer

## 3. MVP features

### Ask the Analyst (single page)
- Question bar with suggestion chips
- Agent steps streamed live ("Resolving players… Querying shots… Verifying 6 claims ✓")
- Answer panel: summary, chart(s), caveats, verification badge (expands claim by claim)
- "Show the working": executed SQL, tool calls, row counts
- Follow-up questions in the same conversation
- Clear states for unavailable data, out-of-scope questions, errors, and rate limits

### Season-aware data
- A data catalog the agent reads before answering
- Honest "not available" answers with a suggested alternative (e.g. no pass data for 2025–26)
- Cross-era comparisons use only shared metrics and state the xG-model caveat (StatsBomb vs Understat)

### Visuals (rendered by the frontend from validated chart specs)
- Shot map: size = xG, shape = outcome, hover details
- Compare bars: two players, shared metrics
- Stretch: pass network (2003–04)

### Page chrome
- Hero with the Invincibles ↔ 2025–26 hook
- Compact "How it works" strip: read-only SQL, data catalog, claim verifier

## 4. Data

Read-only at runtime. Offline scripts load the data; the agent only reads.

| Season | Source | Data |
|---|---|---|
| 2003–04 | StatsBomb Open Data (comp 2, season 44) | Matches, lineups, events with coordinates, StatsBomb xG |
| 2025–26 | Understat | Shots with coordinates + xG, match xG, player match/season stats |

Fallback if Understat can't be pulled: 2025–26 becomes aggregate-only from the
FPL community GitHub archive, and the catalog says so.

Raw files are cached in `ingest/raw/` (git-ignored) and never committed.

### Tables
`seasons`, `teams`, `players`, `player_aliases`, `matches`, `shots`, `events`
(2003–04 only), `player_match_stats`, `data_catalog`.

### Views for the agent
`v_shots`, `v_player_season`, `v_player_match`, `v_matches`, `v_passes`. These
are flat and pre-joined, with player name, season label, and opponent. Column
comments are written for the LLM.

### Rules
- Coordinates normalized to 120 × 80, attacking left → right (tested)
- The agent connects as `analyst_ro`: read-only transaction, 5 s statement timeout, row cap
- `run_sql` accepts only a single SELECT (sqlglot) and enforces a LIMIT
- Derived numbers (per 90, %, differences) are computed in SQL, never by the model
- Every number in an answer must trace to a recorded tool output

## 5. Tech

### Repository (monorepo)
- `apps/web`: Next.js (App Router), TypeScript, Tailwind, shadcn/ui, D3, Framer Motion, Zod
- `services/analyst`: Python 3.12 (uv), FastAPI, LangChain v1 (`create_agent`, middleware), `init_chat_model`, Pydantic, SQLAlchemy/psycopg, sqlglot, rapidfuzz, FastMCP
- `ingest/`: Python scripts (statsbombpy, understat), run locally
- Database: PostgreSQL on Neon, with `ingest` and `analyst_ro` roles

### Tools (one module, two interfaces)
`get_data_catalog`, `get_schema`, `resolve_player`, `run_sql`, `build_chart`.
The agent calls them in-process; the same functions are also served by a
FastMCP server for external agents and the MCP Inspector.

### Agent
- `create_agent` + structured output:
  `Answer{status, summary, claims[{text, value, unit, tool_call_id}], charts[], caveats[], alternative}`
- Middleware: tool-call limit, tool-output recorder
- Claim verifier (deterministic code): checks each claim against the cited
  tool output within tolerance, flags summary numbers with no claim behind
  them, removes unsupported claims, and attaches `{checked, passed, removed}`
- Scope guard via system prompt + `out_of_scope` status
- Checkpointer for follow-ups

### API
- `POST /api/ask`: SSE events `step`, `chart`, `answer`, `error`
- `GET /api/suggestions`, `GET /api/health`
- Per-IP rate limit, cache for suggestion answers, logs of tokens/cost/latency (never user text)

### Evals
15 questions: 5 facts, 3 comparisons, 3 chart requests, 2 unavailable-data,
2 out-of-scope. Expected values come from hand-written SQL. Run on 2 models;
report accuracy, verified-claim rate, correct refusals, latency, and cost.

### Deployment
Vercel (web); Railway or Render paid tier (FastAPI container, no cold starts);
Neon (Postgres). The browser calls the API directly so SSE isn't buffered. LLM
provider spending cap set before the URL goes public.

## 6. UI/UX

Premium matchday data journalism, not a chatbot.

- Dark pitch canvas, matchday-red accent, off-white text. Reuse tokens from
  `../highbury-architecture-standalone.html`
- Barlow Condensed for headlines and big numbers; Source Sans 3 for body; JetBrains Mono for SQL
- Pitch charts are the hero; motion only for step list → answer transitions
- Desktop-first, usable at phone width
- Accessibility: text summary under each chart, outcome by shape not only
  colour, visible focus, reduced motion respected
- Avoid crests, logos, kit imagery, player photos, chart-junk

## 7. Security

- No accounts, no personal data
- API keys server-side only; provider spending cap
- Two SQL locks: sqlglot SELECT-only + the read-only role
- Questions and generated SQL treated as untrusted
- Per-IP rate limits; tool-call limit per question

## 8. Out of scope for the MVP

FPL and football-data.co.uk sources, full entity-resolution pipeline, Season
and Player pages, era-morphing switcher, xG timeline and points-pace charts,
Figma, regenerate-on-failed-verification, 50-question evals, similarity search,
a published MCP package.
