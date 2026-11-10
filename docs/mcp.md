# Highbury MCP server

Highbury's five data tools, served over the
[Model Context Protocol](https://modelcontextprotocol.io) to any MCP client on
your own machine. Your client's model asks the questions; the tools read a
local Postgres database that you build from the public sources. Highbury runs
no server for you, so the model cost, if any, is your client's.

The server:

- speaks stdio only. It opens no network port, and there is no hosted endpoint.
- reads the database as the read-only `analyst_ro` role.
- needs no model key. It needs one environment variable,
  `ANALYST_DATABASE_URL`.

Unofficial fan project. Not affiliated with or endorsed by Arsenal FC or the
Premier League.

## What you need

- [Docker](https://www.docker.com/), for the local Postgres 17.
- [uv](https://docs.astral.sh/uv/), which installs Python 3.12 and the packages.
- [Git](https://git-scm.com/), to clone the repository.
- [Node](https://nodejs.org/) 20 or newer, only for the MCP Inspector check.

## 1. Build the database

The database is built from a clone of the repository: the migrations and the
loaders live there, not in the package. Run every command from the root of the
clone.

```bash
git clone https://github.com/arkaslittlemind/Highbury.git
cd Highbury
cp .env.example .env                 # the local URLs work as they are
docker compose up -d                 # Postgres 17 on localhost:5433
uv sync --all-packages               # Python 3.12 and the packages
uv run --env-file .env python -m ingest.migrate      # tables, views, roles
```

Then run the loaders in this order: the last three stop when a season they
need is not loaded yet. Each loader checks its data before it commits, and
loads nothing when a check fails. Each one is safe to run again.

```bash
uv run --env-file .env python -m ingest.statsbomb    # 2003-04 events and shots
uv run --env-file .env python -m ingest.understat    # 2025-26 shots and player stats
uv run --env-file .env python -m ingest.footballdata # all 380 league matches of both seasons
uv run --env-file .env python -m ingest.fpl          # FPL player data, 2025-26
uv run --env-file .env python -m ingest.curated      # nicknames and the data catalog
```

The loaders download the raw files into `ingest/raw/` and keep them there, so a
second run downloads nothing. If a download fails, the loader names the file
and stops. For a network error such as `ChunkedEncodingError` or
`ConnectError`, run the same command again: it keeps the files it has and
downloads only the rest. If a source keeps failing:

- **football-data.co.uk:** save `E0.csv` of each season by hand into
  `ingest/raw/football-data/` as `E0-0304.csv` and `E0-2526.csv`.
- **FPL archive:** save `merged_gw.csv`, `fixtures.csv`, and `teams.csv` of
  `data/2025-26/` of the
  [archive](https://github.com/vaastav/Fantasy-Premier-League) into
  `ingest/raw/fpl/`.
- **Understat:** there is no file to save by hand. When the site is down for
  maintenance, run the loader again later.

The `.env.example` passwords (`ingest_local`, `analyst_ro_local`) are for a
database on your own machine. Change them in `.env` before you run the
migrations against any database that other people can reach.

## 2. Install the server

From the root of the clone:

```bash
uv tool install ./services/analyst
```

This puts the `highbury-mcp` command on your `PATH`. If uv says that its tool
folder is not on `PATH`, run `uv tool update-shell` and open a new terminal.
`uv tool dir --bin` shows the folder. The install also adds the `ask` and
`evals` commands of the same package. The MCP server does not need them, and
they need a model key.

To update after a `git pull`, run `uv tool install --reinstall ./services/analyst`.
To remove it, run `uv tool uninstall analyst`.

## 3. Check it with the MCP Inspector

The URL below is the local read-only URL of `.env.example`. Use your own if you
changed it.

```bash
npx @modelcontextprotocol/inspector --cli --method tools/list -e ANALYST_DATABASE_URL=postgresql://analyst_ro:analyst_ro_local@localhost:5433/highbury highbury-mcp
```

The result lists five tools. To call one:

```bash
npx @modelcontextprotocol/inspector --cli --method tools/call --tool-name resolve_player --tool-arg name=Henry -e ANALYST_DATABASE_URL=postgresql://analyst_ro:analyst_ro_local@localhost:5433/highbury highbury-mcp
```

Leave out `--cli --method ...` to open the Inspector's web UI instead.

## 4. Connect your client

Each client starts `highbury-mcp` itself and passes the URL in `env`. A desktop
app does not always read your shell's `PATH`. If the client cannot find the
command, put the full path in `command`: the folder that `uv tool dir --bin`
shows, plus `highbury-mcp` (`highbury-mcp.exe` on Windows).

**Claude Desktop:** edit `claude_desktop_config.json` (Settings, Developer, Edit
Config), then restart the app.

```json
{
  "mcpServers": {
    "highbury": {
      "command": "highbury-mcp",
      "env": {
        "ANALYST_DATABASE_URL": "postgresql://analyst_ro:analyst_ro_local@localhost:5433/highbury"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add highbury -e ANALYST_DATABASE_URL=postgresql://analyst_ro:analyst_ro_local@localhost:5433/highbury -- highbury-mcp
```

**Cursor:** the same `mcpServers` object as Claude Desktop, in `~/.cursor/mcp.json`
(all projects) or `.cursor/mcp.json` (one project).

**VS Code:** `.vscode/mcp.json` in the workspace.

```json
{
  "servers": {
    "highbury": {
      "type": "stdio",
      "command": "highbury-mcp",
      "env": {
        "ANALYST_DATABASE_URL": "postgresql://analyst_ro:analyst_ro_local@localhost:5433/highbury"
      }
    }
  }
}
```

These configs follow each client's own documentation. Only the MCP Inspector
check above is part of this project's tests.

## The five tools

A tool does not fail on a SQL, chart, or database problem. It returns a result
with an `error` text, so that the model can read the problem and try again. A
missing or wrongly typed argument is different: the MCP layer rejects the call
before the tool runs, and the client gets an error result with the
validation message instead.

| Tool | Inputs | What it returns |
|---|---|---|
| `get_data_catalog` | `season` (optional, such as `2003-04`) | What data each season has: one row for each metric, with `available`, the source, and notes. Ask it first: the two seasons have different data. |
| `get_schema` | none | The views that `run_sql` can read, with a description of each column. |
| `resolve_player` | `name` | The player that a name or a fan nickname means (`Titi`, `Henry`): `found`, `ambiguous`, or `not_found`, with each match's exact `player` value, seasons, and teams. Use that value in SQL. |
| `run_sql` | `sql` | The columns and rows of one read-only `SELECT`, the statement that ran, and `limit_reached` when the row limit cut the result. |
| `build_chart` | `chart_type`, `sql`, `title` | A chart spec that holds its own data, built from the rows of one `SELECT`. The types are `shot_map`, `compare_bars`, `pass_network`, `xg_timeline`, `points_pace`, `pass_map`, and `heatmap`. The tool's description names the columns that each type needs. |

The views are `v_matches`, `v_shots`, `v_player_match`, `v_player_season`,
`v_passes`, `v_substitutions`, `v_league_matches`, `v_league_table`,
`v_fpl_player_match`, `v_player_match_advanced`, `v_touches`, and
`v_player_similarity`. For example:

```sql
SELECT player, count(*) AS shots, sum(xg) AS xg
FROM v_shots
WHERE season = '2003-04' AND team = 'Arsenal'
GROUP BY player
ORDER BY shots DESC
```

A chart spec is JSON. Your client shows it as text; the pitch drawings are part
of the Highbury web app, not of the server.

## Limits

- **Two seasons.** Arsenal's 2003-04 and 2025-26 league seasons, plus the league
  table and team match stats of every match of both. Shots, events, and player
  stats are for Arsenal's matches; FPL data covers every 2025-26 player.
  2025-26 has no pass events, so no pass map, pass network, or heatmap.
  `get_data_catalog` has the full list.
- **Read-only, three times.** The SQL guard lets through one `SELECT` on the
  views above and nothing else: no writes, no other tables, no `pg_` functions.
  Each statement runs in a read-only transaction, as the `analyst_ro` role,
  which has no write grant on any table.
- **500 rows and 5 seconds.** The guard caps each result at 500 rows, and the
  database stops a statement after 5 seconds.
- **stdio only.** One client starts one server process on your machine. There
  is no HTTP or remote mode.

## Data sources and terms

The package and the repository hold no raw data. The loaders download it from
the sources below into `ingest/raw/` on your machine. You are responsible for
your use of it under each source's terms, so read them before you publish
anything made with it.

- **[StatsBomb Open Data](https://github.com/statsbomb/open-data)**, 2003-04
  events and shots. The terms are in the repository's
  [LICENSE.pdf](https://github.com/hudl/open-data/blob/master/LICENSE.pdf).
  If you publish or share work based on the data, StatsBomb asks you to state
  the data source as StatsBomb and to use its logo, from its
  [media pack](https://statsbomb.com/media-pack/).
- **[Understat](https://understat.com)**, 2025-26 shots, xG, and per-match
  player stats. The site states no license for its data. Use it for your own
  analysis and credit Understat.
- **[football-data.co.uk](https://www.football-data.co.uk)**, the results and
  team match stats of all 380 matches of both seasons. The site states no data
  license. Its [disclaimer](https://www.football-data.co.uk/disclaimer.php) says
  that it cannot guarantee the data is correct. Credit football-data.co.uk.
- **[Fantasy Premier League archive](https://github.com/vaastav/Fantasy-Premier-League)**
  of Vaastav Anand, the 2025-26 per-match FPL data. MIT License. The README asks
  that a website or blog post that uses the data links back to the repository.

The code is under the [MIT License](../LICENSE). The fan nicknames and the data
catalog in `ingest/overrides.yaml` are part of this repository.
