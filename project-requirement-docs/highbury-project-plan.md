# Highbury — Project Plan

> Working name: **Highbury** (the ground where the Invincibles played). See the
> name shortlist in the chat; swap it everywhere once chosen.
>
> Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the
> Premier League. No club crests, logos, or player photos are used.

## 1. Problem - What problem are we solving?

Football data is richer than ever, but answering a simple fan or analyst
question — *"How did Henry's shooting in 2003–04 compare with Saka's in
2025–26?"* — still means finding the right dataset, writing queries, cleaning
names, and drawing pitch charts by hand.

General-purpose chatbots answer these questions confidently and often wrongly:
they invent numbers, mix up seasons, and never say when data doesn't exist.

**Highbury** is an AI football analyst for Arsenal's history. A user asks a
question in plain English; an agent plans the analysis, queries a curated
database through tools, draws interactive pitch visuals, and writes an answer in
which **every number is verified against the data** before it is shown. When the
data cannot answer a question, the agent says so and offers what it can show
instead.

The product focuses on two seasons at launch:

- **2003–04, The Invincibles** — full event-level data (every pass, carry,
  pressure, and shot with coordinates)
- **2025–26, the title-winning season** — shot-level data with xG, match and
  player aggregates

## 2. Users - Who is this for?

### Fans

- Ask questions in plain English without knowing any query language
- Explore the two seasons through suggested questions
- See interactive pitch visuals: shot maps, pass networks, xG timelines
- Compare players and eras on shared metrics
- Share an answer card

### Analysts and data-curious users

- See exactly which data and tools the answer used
- Inspect the generated SQL
- Trust that numbers are checked, not generated

### Hiring managers (the portfolio audience)

- Understand the architecture from the landing page and README
- See eval results, model comparison, and cost per answer

## 3. Features - What does v1 need?

### Ask the Analyst

- Plain-English question input with suggested questions per season
- Streaming agent steps shown live ("Resolving players… Querying shots…
  Drawing shot map… Verifying 6 claims ✓")
- Final answer: short written analysis + one or more interactive charts
- "Show the working": the SQL that ran, the tools called, and data sources
- Follow-up questions in the same conversation

### Season-aware data handling

- A data-availability catalog the agent consults before answering
- Clear, honest responses when data is unavailable for a season (e.g. pass
  maps for 2025–26), with a suggested alternative
- Era comparisons restricted to metrics both seasons share

### Interactive visuals (rendered in the frontend)

- Shot map (location, xG as size, outcome as style, filters)
- Pass network (2003–04 only)
- xG timeline / cumulative xG per match
- Player comparison bars and radar
- Season points-pace chart

### Claim verification

- Every numeric claim in an answer must trace back to a tool result
- Unsupported claims are removed or the answer is regenerated once
- A verification badge on every answer (e.g. "6/6 claims verified")

### Explore pages (no question needed)

- Season overview for 2003–04 and 2025–26
- Season switcher that morphs the same view between eras
- Player pages for key players (stats, shot map, trend)

### Landing page

- Hero with the core hook (Invincibles ↔ 2025–26)
- Live demo question
- Architecture explainer
- Eval results summary

### Bonus

After v1 is stable:

- More seasons (as free data allows)
- Player similarity search with vector embeddings
- Match report generator with verified claims
- Public MCP server package that others can plug into their own agents

## 4. Data - What are we storing?

The database is **read-only at runtime**: data is ingested offline by scripts,
and the agent only reads.

### Sources

| Source | Season | Data |
|---|---|---|
| StatsBomb Open Data | 2003–04 | Matches, lineups, full events with coordinates, StatsBomb xG |
| Understat | 2025–26 | Shots with coordinates and xG, match xG, player season xG |
| FPL API + community GitHub archives | 2025–26 | Per-gameweek player stats, minutes, positions |
| football-data.co.uk | Both | Results, basic match stats |

Raw scraped files stay local and are **not** committed. The repository publishes
ingestion scripts, schema, and migrations.

### Core tables

- `seasons` — id, label, data_level (EVENT / SHOT / AGGREGATE)
- `teams` — id, canonical name
- `players` — id, canonical name, position, known_as
- `player_aliases` — player_id, source, source_player_id, source_name
- `matches` — id, season_id, date, home/away team, score, venue
- `events` — 2003–04 only: match_id, player_id, type, minute, second,
  x, y, end_x, end_y, outcome, under_pressure, possession id
- `shots` — both seasons: match_id, player_id, minute, x, y, xg, outcome,
  body_part, situation, source
- `player_match_stats` — player_id, match_id, minutes, goals, assists,
  xg, xa, and other shared metrics
- `data_catalog` — season_id, metric/feature, available (bool), source, notes

### Coordinate normalization

All sources are converted to one pitch coordinate system (e.g. 120 × 80,
attacking left to right). Conversions are tested.

### Entity resolution

The same player appears with different names and IDs across sources
(e.g. "Bukayo Saka", "B. Saka", source-specific IDs). A resolution step maps
every source record to one canonical `players.id`, using exact ID matches,
fuzzy name matching, and a hand-maintained overrides file.

### Important business rules

- The agent's database role is **read-only** with a statement timeout and row cap
- Only `SELECT` queries are executed; anything else is rejected before it runs
- Every number in an answer must be traceable to a tool result
- The agent consults the data catalog before answering season-specific questions
- Cross-era comparisons use only metrics available in both seasons

## 5. Tech - What stack are we using?

### Front-end

- Next.js with App Router
- React + TypeScript
- Tailwind CSS + shadcn/ui (heavily customized)
- D3 or visx for pitch visuals and charts
- Framer Motion for transitions (season switcher, streaming steps)
- Zod schemas mirroring the chart-spec contract
- Server-sent events for streaming agent steps

### Back-end (analyst service)

- Python 3.12, managed with uv
- FastAPI
- **LangChain v1** — `create_agent` with tools and middleware
- `init_chat_model` so the model is a config value, not a code change
- MCP Python SDK (FastMCP) for the football data tool server
- `langchain-mcp-adapters` to load MCP tools into the agent
- Pydantic for structured output and API models
- SQLAlchemy / psycopg for database access
- sqlglot to parse and enforce SELECT-only SQL
- rapidfuzz for entity resolution
- polars or pandas for ingestion

### Database

- **PostgreSQL** (managed: Neon or Supabase free tier; Docker locally)
- Separate roles: an `ingest` role for loading, an `analyst_ro` read-only role
  for the agent
- Statement timeout and maximum returned rows for `analyst_ro`

### LLM

- Model-agnostic via `init_chat_model`; budget ~$10–15 total
- Develop on a low-cost model (e.g. Gemini Flash tier)
- Run the eval suite across 2–3 models and choose the demo model by
  accuracy, cost, and latency
- Prompt caching for the schema and data-catalog context

### MCP tool server

- `get_data_catalog(season?)` — what data exists for each season
- `get_schema(tables?)` — table and column descriptions for query writing
- `resolve_player(name, season?)` — fuzzy name → canonical player
- `run_sql(query)` — validated, read-only, timed-out, row-capped query
- `build_chart(spec_request)` — returns a validated chart spec with data
  (shot_map, pass_network, xg_timeline, compare_bars, points_pace)

### Agent middleware

- Scope guard: politely refuses non-football or out-of-scope questions
- Tool-call budget: caps tool calls per question
- Claim verifier: checks each numeric claim in the structured answer against
  recorded tool outputs before the answer is returned

### Structured answer contract

- `summary` — short written analysis
- `claims[]` — text, value, and the tool call it came from
- `charts[]` — validated chart specs
- `caveats[]` — data limitations
- `verification` — claims checked, passed, removed

### Suggested REST resources

- `POST /api/ask` — question (+ conversation id) → SSE stream of steps + final answer
- `GET /api/seasons` — seasons and data catalog
- `GET /api/seasons/:id/overview` — precomputed season overview
- `GET /api/players/:id` — player profile and season stats
- `GET /api/suggestions` — suggested questions per season
- `GET /api/health`

### Evals

- Golden set of ~50 questions with expected answers computed by
  hand-written SQL
- Metrics: answer correctness, claim verification rate, correct chart
  type, correct refusal for unavailable data, tool calls, latency, cost
- Model comparison table published in the README

### Deployment

- Vercel for the Next.js app
- Render / Railway / Fly for the FastAPI container (MCP server runs inside it)
- Managed PostgreSQL (Neon or Supabase)

## 6. UI/UX - How should this look and feel?

Highbury should feel like **premium matchday data journalism**: the confidence of
a great sports-analytics feature, with the interactivity of a product.

### Visual system

- Dark canvas (near-black / deep pitch green) with a bold red accent and
  off-white text; a light theme is optional, not v1
- Condensed sports display font for headlines and big numbers
  (e.g. Barlow Condensed), a clean sans for body text, and a mono font for SQL
- Big numbers as a design element
- Pitch visuals as the hero of every screen
- Restrained motion: smooth transitions, no gimmicks

Avoid:

- Club crests, logos, kit imagery, or player photos
- Generic chatbot layout (a lone text box in a white page)
- Chart-junk and 3D effects

### Core screens

1. **Landing** — hero headline, season switcher teaser, one live example
   answer, "Ask the Analyst" CTA, architecture and evals sections
2. **Ask** — question bar with suggestion chips; streaming step list;
   answer panel with analysis, interactive charts, verification badge,
   and "Show the working"
3. **Season** — overview with the Invincibles ↔ 2025–26 switcher
4. **Player** — key stats, shot map, trend chart

### Signature interactions

- Season switcher that morphs charts between eras
- Hover/tap shots for minute, xG, outcome, and opponent
- Streaming agent steps that become the "working" panel once done
- Verification badge expandable into claim-by-claim checks

### Responsive design

Desktop-first for the analyst view (charts need room), fully usable on mobile:
charts resize, filters collapse into a sheet, the step list collapses.

### Accessibility

- Charts have text summaries and accessible data tables
- Outcome encoded by shape and label, not only color
- Visible focus, keyboard navigation for charts and filters
- Strong contrast on the dark theme
- Respect reduced-motion preferences

## 7. Security and Privacy

- No user accounts in v1; no personal data stored
- LLM API keys server-side only, with a hard spending limit set at the provider
- Read-only database role; SELECT-only enforcement; statement timeout; row cap
- Treat generated SQL and user questions as untrusted input
- Per-IP rate limiting on `/api/ask`
- Cache answers to suggested questions to control cost
- Respect each data source's terms; do not redistribute raw scraped data
- Clear unofficial-fan-project notice

## 8. MVP Scope

The v1 is focused on a polished, trustworthy question → verified answer flow.

It should support:

1. Ingestion of 2003–04 and 2025–26 data into PostgreSQL
2. Unified schema, coordinate normalization, and entity resolution
3. Data-availability catalog
4. MCP tool server (catalog, schema, player resolution, SQL, charts)
5. LangChain agent with scope guard, tool budget, and claim verifier
6. Structured answers with chart specs
7. Streaming agent steps in the UI
8. Interactive shot map, pass network, xG timeline, comparison charts
9. Landing page, Ask page, Season page with the era switcher
10. Golden eval set and model comparison
11. Deployed frontend, backend, and database

More seasons, similarity search, match reports, and a published MCP package
remain bonus scope.

This document defines the **product scope and technical direction**. Detailed
implementation phases, contracts, and deployment steps are captured in the
Highbury Build Plan.
