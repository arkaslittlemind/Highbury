# Build Plan (MVP)

Five-day MVP: ask a question about Arsenal's 2003–04 or 2025–26 season, get a
streamed, verified answer with a pitch chart, deployed at a public URL. Build
the data first, then tools, then the agent and verifier, then the API and
deploy, then the UI, then evals. Each item below is one Blueprint feature
(`/feature → /implement → /check → /complete`). Done-whens are written so
`/check` can prove them.

Items marked **[audit]** get `/audit current` before `/complete`. Item 16 is a
stretch; skip it if Day 4 runs late.

- [ ] 1. **Database schema, views, roles** - migrations for seasons, teams, players, player_aliases, matches, shots, events, player_match_stats, data_catalog; flat views `v_shots`, `v_player_season`, `v_player_match`, `v_matches`, `v_passes` with LLM-facing column comments; `ingest` role and `analyst_ro` role (read-only, 5 s statement timeout); applied to Neon. *Done when:* migrations apply cleanly to an empty DB, and as `analyst_ro` a SELECT works while INSERT fails.
- [ ] 2. **Ingest 2003–04 (StatsBomb)** - pull Arsenal's 38 league matches with statsbombpy, cache raw files, load matches, lineups, events, shots (StatsBomb xG), and player_match_stats; idempotent re-run. *Done when:* tests pass for coordinate mapping, and asserts hold: 26W 12D 0L, 90 points, Henry 30 league goals.
- [ ] 3. **Ingest 2025–26 (Understat)** - shots with x/y + xG, match xG, player match and season stats; scale 0–1 coordinates to 120 × 80; cache raw files; idempotent. *Done when:* coordinate tests pass; team goals and top scorer match a published table; every shot has a player and in-bounds coordinates.
- [ ] 4. **Aliases + data catalog** - `aliases.yaml` for ~25 key players (e.g. "Henry", "Titi", "B. Saka") loaded into player_aliases; populate data_catalog (results, shots, xG, minutes/goals/assists, passes, pressures, pass networks) per season with source and notes. *Done when:* catalog rows match the availability matrix, and every alias resolves to exactly one player.
- [ ] 5. **Data tools + SQL guardrails** [audit] - `get_data_catalog`, `get_schema` (from column comments), `resolve_player` (alias exact match, then rapidfuzz), `run_sql` (sqlglot single-SELECT only, enforced LIMIT, `analyst_ro` connection, returns rows + executed SQL + call id, returns error text instead of raising). *Done when:* tests show DROP/INSERT/multi-statement/CTE-with-write rejected, LIMIT applied, timeout honoured, and "Titi Henry" resolves to Thierry Henry.
- [ ] 6. **Chart specs + MCP server** - `build_chart` returning Pydantic-validated specs for `shot_map`, `compare_bars`, `pass_network` (data included); FastMCP server exposing all five tools from the same functions. *Done when:* spec tests pass, and the MCP Inspector lists and calls all five tools.
- [ ] 7. **Analyst agent + CLI** - `create_agent` with `init_chat_model` (model from env), system prompt (catalog, view schemas, few-shot SQL, "derived numbers from SQL", cross-era xG caveat rule), structured `Answer`, tool-call limit middleware, tool-output recorder middleware, checkpointer for follow-ups; `uv run ask "<question>"`. *Done when:* the 5 demo questions in `../highbury-mvp-plan.md` §8 return correct answers from the CLI, including the follow-up.
- [ ] 8. **Claim verifier** [audit] - checks each claim's value against its cited tool output (exact for counts, ±0.01 for xG/rates), flags summary numbers with no backing claim, removes unsupported claims, attaches `{checked, passed, removed}`. *Done when:* tests cover a correct claim passing, a wrong value removed, a wrong tool_call_id removed, and an unbacked summary number flagged.
- [ ] 9. **Analyst API + streaming** [audit] - FastAPI `POST /api/ask` streaming SSE `step`/`chart`/`answer`/`error` with friendly step labels; `GET /api/suggestions`, `GET /api/health`; per-IP rate limit; suggestion-answer cache; per-request log of tokens, cost, latency (no user text); env validated at startup; CORS. *Done when:* `curl -N` shows steps streaming before the answer, the 6th rapid request gets 429, and a cached suggestion returns in under 300 ms.
- [ ] 10. **Deploy pipeline** [audit] - `/release` config for the API container (Railway/Render) and Vercel web shell; Neon connection as `analyst_ro` only; provider spending cap; `X-Accel-Buffering: no`. *Done when:* the public web URL calls the public API and a question streams end to end in production.
- [ ] 11. **Ask page** - question bar, suggestion chips, live step list via an SSE hook, answer panel (summary, caveats, verification badge expanding to claim checks, "Show the working" with SQL and tools), follow-ups, error and rate-limit states; Zod schemas mirroring chart specs. Run `/prototype` first for the layout. *Done when:* all 5 demo questions work in the deployed UI, and invalid chart specs show a fallback instead of crashing.
- [ ] 12. **Pitch + shot map** - reusable SVG pitch (120 × 80, D3 scales); shot map with xG as size, outcome as shape, hover/focus tooltip (minute, xG, outcome, opponent), text summary below. *Done when:* Henry 2003–04 and Saka 2025–26 shot maps render correctly at 1440 px and 390 px, and are keyboard-navigable.
- [ ] 13. **Compare bars** - two-player comparison on shared metrics, with the era caveat shown inline and a text summary. *Done when:* demo question #2 renders bars whose values match the verified claims.
- [ ] 14. **Visual polish + hero** - tokens from the architecture page, fonts, hero with the era hook, "How it works" strip, step list → answer motion, reduced-motion support, focus states, mobile layout. *Done when:* no horizontal scroll at 390 px, the contrast check passes, and reduced motion disables transitions.
- [ ] 15. **Evals + model comparison** - 15-question golden set with expected values from hand-written SQL; runner scoring correctness, verified-claim rate, chart type, correct refusals, tool calls, latency, cost; run on 2 models; write `evals/results.md`. *Done when:* the table is generated for both models, and the chosen model is set in config with the reason recorded.
- [ ] 16. **Stretch: pass network** - 2003–04 single-match pass network from `v_passes` (average positions, edge weight = pass count). *Done when:* "Show Arsenal's pass network vs Liverpool at home" renders and verifies.

## Schedule

| Day | Items | Focus |
|---|---|---|
| 1 | Setup, 1–4 | Blueprint setup, schema, both ingests, catalog |
| 2 | 5–8 | Tools, MCP, agent, verifier (CLI only) |
| 3 | 9–11 | API, deploy, Ask page |
| 4 | 12–16 | Charts, polish, evals, then feature freeze |
| 5 | none | README, demo rehearsal, video |

## LLM budget (~$10)

| Use | Approach | Rough cost |
|---|---|---|
| Development | Low-cost model | ~$1–3 |
| Evals (15 × 2 models × 2 runs) | Low-cost model + one stronger model | ~$2–4 |
| Demo + recording | Chosen model, cached suggestions, spending cap | ~$1–3 |
