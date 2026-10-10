# Highbury — 5-Day MVP Plan

> Goal: a **live, deployed demo** and a **recorded video** (tool, architecture,
> how it works, design trade-offs) delivered in 5 days for the Spektra Systems
> AI Native Full Stack Engineer process.
>
> This plan cuts the 6-week v1 ([highbury-build-plan.md](highbury-build-plan.md))
> down to the parts that prove the core idea. Everything cut is listed in §9 and
> becomes the "what's next" section of the video.

---

## 1. The MVP in one sentence

Ask a question about Arsenal's **2003–04** or **2025–26** season in plain
English and get a short written answer, an interactive pitch chart, and a badge
showing that **every number was checked against the database**. When the data
can't answer, it says so.

### What the demo must prove (in priority order)

1. **It answers correctly**: an agent plans, queries Postgres through tools, and answers.
2. **It doesn't make numbers up**: the claim verifier and the "N/N verified" badge.
3. **It knows what it doesn't know**: the data catalog leads to honest refusals with an alternative.
4. **It's a real product**: streaming steps, a polished pitch chart, deployed at a URL.
5. **It's engineered, not just prompted**: read-only SQL guardrails, evals across models, cost per answer.

If something doesn't serve one of these five, it's out of scope for this week.

---

## 2. Scope: in vs. out

| Area | Full v1 | **MVP (5 days)** |
|---|---|---|
| Seasons | 2003–04 + 2025–26 | **Same two**. They're the hook. |
| Sources | StatsBomb, Understat, FPL, football-data.co.uk | **StatsBomb (2003–04) + Understat (2025–26) only** |
| Entity resolution | rapidfuzz + overrides + review report | **Per-season canonical names + small `aliases.yaml`**; rapidfuzz only inside `resolve_player` |
| Data catalog | Full feature matrix + sanity checks | **Same table, ~10 rows**, plus 3 sanity asserts (goals, points, top scorer) |
| Tools | 5 MCP tools via stdio subprocess | **Same 5 tools, written once**; called in-process by the agent, also exposed as a FastMCP server (shown in Inspector) |
| Agent | create_agent + 3 middleware + memory | **create_agent + tool-call limit + verifier**; scope guard via prompt + `out_of_scope` field; follow-ups kept (cheap with a checkpointer) |
| Claim verifier | Remove or regenerate | **Deterministic check, remove unsupported claims, badge**; no regenerate loop |
| Charts | Shot map, pass network, xG timeline, compare bars, points pace | **Shot map + compare bars** (must); **pass network** (stretch, the 2003–04 wow moment) |
| Pages | Landing, Ask, Season (morph), Player | **One page**: hero + Ask + answer panel + compact "How it works" strip |
| Design | Figma first, full design system | **No Figma.** Reuse the tokens already in `highbury-architecture-standalone.html` |
| Evals | ~50 questions × 2–3 models | **15 questions × 2 models**, a table in the README |
| Deploy | Vercel + container + Neon | **Same**, but deployed on **Day 3**, not at the end |
| Accessibility | Full pass | Text summary under each chart, outcome by shape not only colour, focus states, reduced motion |

---

## 3. Architecture (MVP)

```
Browser (Next.js on Vercel)
   │  POST /api/ask  ──►  SSE stream: step events … final answer
   ▼
FastAPI (Render/Railway container)
   │  rate limit · suggestion cache · cost/latency log
   ▼
LangChain agent (create_agent, model via init_chat_model)
   │  middleware: tool-call limit · tool-output recorder
   │  post-step: claim verifier
   ▼
Tools module  (the same functions are also served by FastMCP)
   get_data_catalog · get_schema · resolve_player · run_sql · build_chart
   ▼
Postgres on Neon  ── agent connects as analyst_ro (SELECT-only, 5s timeout, row cap)

Offline:  ingest/ scripts → StatsBomb + Understat → normalize → load (ingest role)
```

The architecture explainer you already have (`highbury-architecture-standalone.html`)
becomes the architecture section of the video and the README. Edit it for the
MVP cuts (FPL/football-data out, in-process tools); don't rebuild it.

---

## 4. Key MVP design decisions

These are the trade-offs to explain in the video. Each one is a deliberate cut
or bet you can defend.

1. **Tools written once, called in-process; MCP as an interface, not a hop.**
   The same Python functions back both the LangChain tools and a FastMCP server.
   The deployed agent calls them in-process (no stdio subprocess to manage in a
   container, lower latency). *Trade-off:* you give up process isolation but keep
   MCP compatibility. Show the MCP Inspector, or Claude Desktop, calling the
   same tools. That's your "plugs into any agent" moment.

2. **Denormalized views for the LLM.** Expose `v_shots`, `v_player_season`,
   `v_player_match`, `v_matches`, `v_passes` (2003–04 only), each already joined
   with player name, season label and opponent. The agent writes simple SQL
   against flat views instead of 5-table joins. This is the cheapest accuracy win
   available. *Trade-off:* less flexible querying, far fewer wrong joins.

3. **"Derived numbers come from SQL, never from the model."** The prompt
   requires per-90s, percentages and differences to be computed in SQL. That's
   what makes deterministic verification possible: every claimed value must
   appear in a recorded tool output.

4. **Verifier is code, not another LLM call.** It parses `claims[]`, finds the
   cited tool call, and checks the value within tolerance (±0.01 for xG,
   exact for counts). It also regex-scans the summary for any number that isn't
   backed by a claim. *Trade-off:* rejects some correct but derived phrasing
   ("nearly double"); it's cheaper, faster, testable, and explainable.

5. **Two independent SQL locks.** sqlglot allows only a single SELECT and
   appends a `LIMIT`; Postgres enforces the `analyst_ro` role,
   `statement_timeout`, and `default_transaction_read_only`. Either lock alone
   is enough.

6. **Charts are data.** `build_chart` returns a Pydantic-validated spec with the
   rows; the frontend validates it with Zod and renders it with D3. The model
   picks *what* to show, the UI owns *how*.

7. **Model is config.** `init_chat_model("provider:model")`. Evals run the same
   15 questions on two models and pick on accuracy, latency and cost. (Spektra
   is a Microsoft-ecosystem company, so if their stack is Azure-centric, it's
   worth showing that Azure OpenAI is a one-line config change. Check this
   before you say it.)

8. **Fewer sources, honest catalog.** Dropping FPL and football-data.co.uk
   removes most of the entity-resolution work. Understat alone gives 2025–26
   shots, xG/xA, minutes, goals and assists. The catalog states clearly what's
   missing (passes, pressures for 2025–26), which feeds demo moment #3.

---

## 5. Data plan

### Sources

| Season | Source | How | What you get |
|---|---|---|---|
| 2003–04 | StatsBomb Open Data (competition 2, season 44: Arsenal's 38 league matches) | `statsbombpy` | Matches, lineups, all events with coordinates, StatsBomb xG |
| 2025–26 | Understat (Arsenal team page + match pages) | `understat` package / `soccerdata`, cached to `ingest/raw/` (git-ignored) | Shots with x/y + xG, match xG, player match & season stats |

**Day 1 spike, first 90 minutes:** confirm both pulls work before writing
anything else. Understat is the riskiest dependency. **Fallback:** if Understat
can't be pulled reliably, 2025–26 becomes aggregate-only (FPL GitHub archive:
goals, assists, minutes, xG per gameweek), the shot map becomes 2003–04 only,
and the catalog says so. The demo still works, and the refusal story gets stronger.

### Schema (trimmed)

`seasons`, `teams`, `players`, `player_aliases`, `matches`, `shots`,
`events` (2003–04 only; passes/carries/pressures), `player_match_stats`,
`data_catalog`, plus the `v_*` views above. Column `COMMENT`s are written for the
LLM; `get_schema` returns them.

### Coordinates

Everything goes to 120 × 80, attacking left→right. StatsBomb is already in
that system; Understat is 0–1 normalized, so scale it (x × 120, y × 80). One
unit test per source, and a visual check of Henry's and Saka's shot maps.

### Sanity asserts (run after ingest)

- 2003–04: 26 W, 12 D, 0 L, 90 points; Henry has 30 league goals
- 2025–26: total goals and top scorer match a published table
- Every shot has a player_id and coordinates inside the pitch

---

## 6. Agent contract

```python
class Claim(BaseModel):
    text: str            # "Henry scored 30 league goals"
    value: float         # 30
    unit: str            # "goals"
    tool_call_id: str    # the run_sql call whose rows contain 30

class Answer(BaseModel):
    status: Literal["answered", "unavailable", "out_of_scope"]
    summary: str                      # 2–4 sentences
    claims: list[Claim]
    charts: list[ChartRef]            # ids returned by build_chart
    caveats: list[str]                # e.g. xG model differences across eras
    alternative: str | None           # used when status == "unavailable"
```

The verifier attaches `verification = {checked, passed, removed[]}`. The
recorder middleware also captures every tool call, SQL string and row count.
That record becomes the "Show the working" panel.

**System prompt essentials:** the data catalog (inline, it's short), view
schemas, 4–6 few-shot SQL examples, the rule "derived numbers must come from
SQL", the rule "consult the catalog before season-specific claims", and the
rule "cross-era xG comparisons must include the StatsBomb vs Understat model
caveat".

**SSE events:** `step` (`{kind: "tool", name, label}`, e.g. "Resolving
players…", "Querying shots…"), `chart` (spec), `answer` (final + verification),
`error`. Stream from `agent.astream(..., stream_mode="updates")`.

---

## 7. Workflow and day-by-day plan (AI Blueprint)

The build runs on [AI Blueprint](https://ai-blueprint.dev/) with Claude Code.
The Blueprint plan files are ready in [`mvp/`](mvp/):

- [`mvp/project-plan.md`](mvp/project-plan.md): MVP product, data, tech, UI, security
- [`mvp/build-plan.md`](mvp/build-plan.md): 16 features, each with done-whens that `/check` can prove, grouped by day

Assumes ~10–12 focused hours a day. If a day's features aren't done, apply the
cut lines in §9 before starting the next day.

### Day 1 morning: setup (outside the feature loop, ~2 h)

1. **Data spike first (30–60 min, throwaway script).** Pull StatsBomb 2003–04
   and Understat 2025–26 into `ingest/raw/`. If Understat fails, switch to the
   FPL-archive fallback (§5) *before* writing plans into Blueprint.
2. **Scaffold the monorepo at the `Highbury/` root.** `git init`; `apps/web`
   with `create-next-app` (TS, Tailwind, App Router) + shadcn init;
   `services/analyst` with `uv init`; empty `ingest/`; `.gitignore` covering
   `ingest/raw/` and `.env*`; `.env.example`. Blueprint doesn't scaffold, and
   it has no documented monorepo guidance, so give it a real, working tree.
3. **Install Blueprint at the root:** `npx create-ai-blueprint@latest`,
   selecting Claude Code. Run `/onboard` and choose the **Efficient** preset
   (one review per feature, no per-step pauses). Five days can't absorb the
   overhead of per-step approvals.
4. **Copy in the plans:** `mvp/project-plan.md` → `blueprint/project-plan.md`,
   `mvp/build-plan.md` → `blueprint/build-plan.md`.
5. **`/overview`**, then read `blueprint/context/project-overview.md` and fix
   anything it got wrong. Every later session reads from it.
6. **`/tests`** to set up pytest (analyst + ingest) and Vitest (web). Then
   **`/ci`** for one Verify command (ruff + pytest + tsc + vitest + build).
   It's cheap now and gives a green check to show in the video.

### Per-feature loop

`/feature` → read the spec (≤5 min) → `/implement` → `/check` →
(`/audit current` on items marked **[audit]**) → `/complete`.

Tips for keeping the loop fast:
- **The spec review is the only gate you can't skip.** It's where you catch
  scope creep. Reject anything not in the item's text.
- **`/audit` only on the guardrail features** (5 SQL tools, 8 verifier,
  9 API, 10 deploy). That's where a bug would undermine the demo's credibility.
- **Use `/fix` for small breakages** found while demoing, not a new feature.
- **`/prototype` before item 11** replaces Figma: generate 2–3 throwaway Ask
  page layouts, pick one, and put the choice in the item 11 spec.
- **`/release` for item 10** generates the Render/Vercel config and readiness
  checks. Approve the deploy yourself; Blueprint never pushes without approval.
- **`/continuous` is optional, Day 4 only.** Once the API and Ask page are
  stable, it can run items 12–14 back to back while you build the eval golden
  set by hand. Expected values must come from SQL *you* wrote, not the agent.
  Don't use it for items 1–10.
- **Start every session with `/status`.** Blueprint resumes from its files,
  not from chat history, so a fresh session per feature keeps context small.

### Daily targets

| Day | Features | End-of-day proof |
|---|---|---|
| 1 | Setup, 1–4 | As `analyst_ro`, `SELECT` from `v_shots` works and `INSERT` fails; season asserts pass |
| 2 | 5–8 | The 5 demo questions (§8) answer correctly and verified from the CLI |
| 3 | 9–11 | On the public URL, a question streams steps and returns a verified answer |
| 4 | 12–16 | Feature freeze; all 5 demo questions look good at 1440 px and 390 px; eval table generated |
| 5 | none | Morning: `/fix` only what evals and rehearsal exposed, warm the cache, README, update the architecture HTML, record backup clips. Afternoon: rehearse twice, record, send. |

Optional: LangSmith tracing via env vars from item 7 onward gives you trace
screenshots for the video.

---

## 8. Demo script (the five questions)

Each question shows a different capability. Test these from Day 2 onward;
they're your acceptance tests.

| # | Question | Shows |
|---|---|---|
| 1 | "Show me Thierry Henry's shots in 2003–04." | Streaming steps → shot map → 6/6 verified |
| 2 | "Compare Henry in 2003–04 with Saka in 2025–26 on goals and xG per 90." | Cross-era SQL, compare bars, **xG model caveat** |
| 3 | "Show Saka's pass map from 2025–26." | Catalog check → **honest "not available"** → offers his shot map |
| 4 | Follow-up: "Only the ones inside the box." | Conversation memory, filtered chart |
| 5 | "Who will win the Champions League?" | Scope guard, no tools called |

Then open **Show the working** on #2 (SQL + tool calls) and expand the
verification badge claim by claim.

**Bonus moment for the video:** run the verifier test that feeds a deliberately
wrong number and show it being removed. It proves the badge is real.

---

## 9. Cut lines (if you're behind, cut in this order)

1. Pass network → mention as next step
2. Follow-up memory → single-turn only
3. Second eval model → one model, still report accuracy/cost/latency
4. Hero/"How it works" strip → the README and video cover it
5. FastMCP wrapper → describe it, show the tools module

**Never cut:** verifier + badge, honest refusal, read-only SQL guardrails, shot
map, deployed URL, evals (even 10 questions).

---

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Understat pull fails or blocks | Medium | Day 1 spike first; cache raw files; FPL-archive fallback (§5) |
| LLM writes wrong SQL | High | Flat views, column comments, few-shot SQL, `run_sql` returns error text so the agent can retry within budget |
| Verifier rejects correct answers | Medium | "Derived numbers from SQL" rule; tolerance per unit; eval tracks verified-claim rate |
| SSE buffered in production | Medium | Deploy on Day 3; call the backend directly; `X-Accel-Buffering: no` header |
| Cold start / flaky live demo | Medium | Paid tier for the week; cached suggestions; backup recordings |
| LLM cost overrun | Low | Provider spending cap, rate limit, tool-call limit, cache |
| Scope creep | High | §1's five proofs are the filter; §9 cut order |

---

## 11. The video (~8–10 min)

Audience: the COO, then likely the engineering team. Lead with the product,
go deeper as you go, and keep each section tight.

| Time | Section | Content |
|---|---|---|
| 0:00 | Hook | The problem: chatbots invent football stats. Ask question #1 live. |
| 0:45 | Demo | Questions #2–#5, "Show the working", verification badge |
| 3:30 | Architecture | Walk through the system map; trace one question end to end |
| 5:30 | Trade-offs | §4: in-process tools vs MCP hop, flat views, code verifier vs LLM judge, two SQL locks, charts as data, model as config |
| 7:30 | Evals + cost | Eval table, model choice, cost per answer, latency |
| 8:15 | How I built it AI-natively | The Blueprint loop on screen: `project-plan.md` → `build-plan.md` → one feature's `context/current-feature.md` spec (approved before code) → `/check` proving its done-whens → `/audit` findings on the SQL guardrails → the `history/features/` archive and CI Verify check. Message: *the agent writes the code; I own scope, specs, verification, and judgement.* This is the job title, so make it concrete. |
| 9:15 | What's next | §9 cuts + v1 roadmap (more seasons, similarity search, published MCP package) |

Record with the browser at 1440 px, 125% zoom, and the terminal font large.
Put chapter timestamps in the description.

---

## 12. Definition of done (MVP)

- [ ] Public URL answers the 5 demo questions correctly with streaming steps
- [ ] Every answer shows a verification badge; the verifier has tests
- [ ] Unavailable-data and out-of-scope questions are refused gracefully
- [ ] Agent DB access is read-only at both the parser and the role level
- [ ] Shot map + compare bars render from validated specs, on desktop and mobile
- [ ] Eval table (≥15 questions) with accuracy, latency, cost in the README
- [ ] README with architecture, decisions, and the unofficial-fan-project notice
- [ ] Video recorded and sent
