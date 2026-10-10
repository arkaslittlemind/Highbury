# Highbury

An AI football analyst for Arsenal's **2003–04 Invincibles** and **2025–26**
seasons. Ask a question in plain English; an agent queries a curated database
through tools, draws an interactive pitch chart, and checks every number
against the data before showing it.

> **Unofficial fan project.** Not affiliated with or endorsed by Arsenal FC or
> the Premier League. No club crests, logos, or player photos are used.
> Data: StatsBomb Open Data (2003–04), Understat (2025–26). Raw data is not
> redistributed in this repository.

## Layout

| Path | What |
|---|---|
| `apps/web` | Next.js frontend (TypeScript, Tailwind, shadcn/ui, D3) |
| `services/analyst` | FastAPI + LangChain agent + data tools (Python 3.12, uv) |
| `ingest` | Offline loaders for StatsBomb and Understat |
| `db/migrations` | SQL schema, views, and roles |
| `project-requirement-docs` | Product and build plans |

## Local setup

```bash
cp .env.example .env
docker compose up -d          # Postgres on localhost:5433
uv sync --all-packages        # Python workspace
uv run --env-file .env python -m ingest.migrate   # create tables, views, roles
cd apps/web && pnpm install && pnpm dev
```
