# AGENTS.md

Instructions for AI coding agents working in this project. This is the cross-tool
entry point: any tool that reads `AGENTS.md` gets the same project description,
commands, and conventions.

AI tools must not add AI attribution to commits or pull requests, including AI
`Co-Authored-By` trailers or generated-by signatures. Preserve genuine human
attribution.

## What this is

**Highbury** is an AI football analyst for Arsenal's 2003-04 (Invincibles) and
2025-26 seasons. A user asks a question in plain English; an agent queries a
curated Postgres database through tools, returns a short answer with an
interactive pitch chart, and checks every number against the data before showing
it. When the data cannot answer, it says so.

Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the
Premier League. No club crests, logos, or player photos. Raw source data is
never committed.

## Layout

| Path | What |
|---|---|
| `apps/web` | Next.js 16 (App Router), React 19, TypeScript, Tailwind v4, shadcn/ui. Package manager: pnpm |
| `services/analyst` | Analyst service (Python 3.12): FastAPI, agent, data tools |
| `ingest` | Offline loaders for StatsBomb and Understat (Python 3.12) |
| `db/migrations` | SQL schema, views, and roles |
| `deploy/ecs` | Config of the API service on AWS ECS Express Mode, with names only |
| `project-requirement-docs` | Product and build plans |
| `design-docs` | One study document per finished feature, in Simplified Technical English |

The Python side is one uv workspace rooted at `pyproject.toml` with members
`services/analyst` and `ingest`. The web app is a standalone pnpm project in
`apps/web`; there is no root `package.json`.

`apps/web/AGENTS.md` carries Next.js-specific rules. Read it, and the docs it
points to in `node_modules/next/dist/docs/`, before writing web code.

## Proportional engineering

Build for established requirements, not hypothetical scale, threats, or future
flexibility. Reuse existing code, the standard library, native platform features,
and installed dependencies before adding machinery.

- Unknown scale or extensibility defaults to the smaller reversible design. Do
  not infer enterprise, multi-tenant, hostile-user, or compliance requirements.
- Derive trust and data-integrity boundaries from actual reachability: untrusted
  input, auth/session/ownership, shared persisted data, destructive operations,
  payments, secrets, and sensitive data.
- Ask only when an unknown materially changes behavior, architecture, persisted
  data, interoperability, a real security boundary, or cost. Otherwise choose the
  simplest repository-native implementation.
- Add an abstraction, dependency, service, configuration surface, compatibility
  layer, or security mechanism only for a current requirement.
- Simplicity never removes real trust-boundary validation, data-loss prevention,
  accessibility, explicit security requirements, configured tests, or project rules.
- Stack-specific template standards apply only when the project uses that stack.


## Commands

Run Python and database commands from the repository root.

- Local database: `docker compose up -d` (Postgres 17 on `localhost:5433`)
- Environment: `cp .env.example .env`
- Python install: `uv sync --all-packages` (plain `uv sync` skips the workspace members)
- Migrate: `uv run --env-file .env python -m ingest.migrate` (applies pending files in `db/migrations`)
- Ingest 2003-04: `uv run --env-file .env python -m ingest.statsbomb` (StatsBomb; caches raw files in `ingest/raw/statsbomb/`, safe to re-run)
- Ingest 2025-26: `uv run --env-file .env python -m ingest.understat` (Understat; caches raw files in `ingest/raw/understat/`, safe to re-run)
- Aliases and data catalog: `uv run --env-file .env python -m ingest.curated` (loads `ingest/aliases.yaml` and the catalog; needs both seasons loaded first, safe to re-run)
- Ask the analyst: `uv run --env-file .env ask "<question>" ["<follow-up>"]` (the agent on the command line; each extra argument is a follow-up in the same conversation; needs `ANALYST_MODEL` and the key of its provider in `.env`, and each call costs money; `--debug` shows the traceback of an error)
- Analyst API: `uv run --env-file .env uvicorn analyst.api:create_app --factory --port 8000` (http://localhost:8000; needs the local database, `ANALYST_MODEL` with the key of its provider, `CORS_ORIGINS`, and `RATE_LIMIT_PER_MINUTE` in `.env`; each question that is not cached costs money)
- API container: `docker build -t highbury-api .`, then `docker run --rm -p 8000:8000 --env-file .env -e ANALYST_DATABASE_URL=postgresql://analyst_ro:analyst_ro_local@host.docker.internal:5433/highbury highbury-api` (the image of production; inside a container `localhost` is the container, so the database host is `host.docker.internal`)
- Deploy the API: tag the image with a new tag and `docker push` it to the `highbury-api` repository in Amazon ECR. Copy `deploy/ecs/service.example.json` to `service.json` (ignored), fill it in, and put the new tag in `image`. Then `aws ecs update-express-gateway-service --service-arn <arn> --primary-container <the primaryContainer object of service.json>` (the first time: `aws ecs create-express-gateway-service --cli-input-json file://deploy/ecs/service.json`). The two secrets are SecureString parameters under `/highbury/` in AWS Systems Manager. Each command changes production, so ask first
- Evals: `uv run --env-file .env evals` (asks the 15 questions of `evals/golden.yaml` on each model of `evals/models.yaml`, 2 runs each, and writes `evals/runs/` and `evals/results.md`; needs the local database and the key of each provider; every question costs money. `--only q01 --runs 1` for one question, `--model <id>` for one model, `--pause 60` between questions for a per-minute limit, `--report` to write `results.md` again with no model call)
- MCP server: `uv run --env-file .env python -m analyst.mcp_server` (the five data tools over stdio; it waits for an MCP client and prints nothing by itself)
- MCP Inspector: `npx @modelcontextprotocol/inspector --config services/analyst/mcp.json --server highbury` (web UI; needs Node. For terminal output add `--cli --method tools/list` after `inspector`. The config file is needed because the Inspector does not pass flags such as `--env-file` from an inline command)
- Python lint: `uv run ruff check .`
- Python format: `uv run ruff format .`
- Test: `uv run --env-file .env pytest` (Python only; needs the local database running)

Run web commands from `apps/web`.

- Web install: `pnpm install`
- Web environment: `cp .env.example .env.local` (`NEXT_PUBLIC_API_URL`, the origin of the analyst API; it goes into the bundle at build time)
- Dev server: `pnpm dev` (http://localhost:3000)
- Build: `pnpm build`
- Production server: `pnpm start`
- Lint: `pnpm lint`
- Web test: `pnpm test` (Vitest, one run; the unit tests are the `src/**/*.test.ts` files and need no database and no API)
- Web test watch: `pnpm test:watch`
- Deploy the web: push to `main`. The Vercel project `highbury` is connected to the GitHub repository, and each push to `main` builds `apps/web` (the Root Directory of the project) and replaces production. `NEXT_PUBLIC_API_URL` for production is set on the project; `vercel.json` names the framework because the project was not made by auto-detection. A push to `main` changes production, so ask first. Do not run `vercel deploy` from `apps/web`: with the Root Directory set, the command looks for `apps/web/apps/web`

Not configured yet: a web typecheck script, browser tests, a combined `Verify`
command, and CI.

## Testing

- Python logic is gated by the Test command. A step that adds Python logic ships
  a passing test in the same diff. Database tests create a throwaway database
  and fail, not skip, when Postgres is unreachable.
- Web logic (parsers, validators, formatters) is gated by the Web test command.
  A step that adds web logic ships a passing test in the same diff, next to the
  file as `<name>.test.ts`.
- Components and pages have no unit tests. Verify them with `pnpm lint`,
  `pnpm build`, and the running app.

## Conventions

- Python: 3.12, ruff with line length 100 and rules `E`, `F`, `I`, `B`, `UP`.
  Packages use the `src/` layout.
- Web: TypeScript strict mode, `@/*` maps to `apps/web/src/*`, server components
  by default, Tailwind v4 configured in `src/app/globals.css`, shadcn/ui
  components in `src/components/ui`.
- Database access is split by role: the admin URL for migrations only, an
  `ingest` role for offline loaders, and a read-only `analyst_ro` role for the
  agent at runtime. See `.env.example`.
- Secrets live in `.env`, which is ignored. Keep `.env.example` in step with any
  new variable.
- Comment the why, not the what. No em dashes in generated docs, comments, or
  commit messages.
- Conventional commit messages (`feat:`, `fix:`, `chore:`), one focused change
  per commit. Ask before committing.
