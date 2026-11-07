import json
from pathlib import Path

import pytest

from analyst import evals, landing_data

ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = ROOT / "evals"
COMMITTED = ROOT / landing_data.OUTPUT


@pytest.fixture(scope="module")
def golden() -> dict[str, evals.GoldenItem]:
    return {item.id: item for item in evals.load_golden(EVALS_DIR / "golden.yaml")}


@pytest.fixture(scope="module")
def committed() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def test_each_tile_draws_the_chart_of_its_golden_question(golden):
    assert len(landing_data.TILES) == 7
    for tile in landing_data.TILES:
        assert golden[tile.golden_id].chart == tile.chart_type


def test_the_committed_tiles_ask_their_golden_questions(golden, committed):
    tiles = committed["tiles"]
    assert [tile["id"] for tile in tiles] == [tile.golden_id for tile in landing_data.TILES]
    for tile in tiles:
        assert tile["question"] == golden[tile["id"]].question
        assert tile["chart"]["type"] == golden[tile["id"]].chart


def test_the_committed_proof_equals_the_eval_report(committed):
    # results.md comes from the same runs; a new eval run needs a new landing file.
    items = evals.load_golden(EVALS_DIR / "golden.yaml")
    assert committed["proof"] == landing_data.proof_numbers(EVALS_DIR, items)


def test_the_proof_takes_the_newest_run_of_the_production_model(tmp_path):
    for name in ("golden.yaml", "models.yaml"):
        (tmp_path / name).write_text((EVALS_DIR / name).read_text(encoding="utf-8"), "utf-8")
    runs = tmp_path / "runs"
    runs.mkdir()
    source = json.loads(
        (EVALS_DIR / "runs" / "google-genai-gemini-3-8-flash-run1.json").read_text("utf-8")
    )
    older = {**source, "run": 2, "started_at": "2026-01-01T00:00:00+00:00"}
    older["results"] = [{**result, "correct": False} for result in source["results"]]
    (runs / "new.json").write_text(json.dumps(source), "utf-8")
    (runs / "old.json").write_text(json.dumps(older), "utf-8")

    proof = landing_data.proof_numbers(tmp_path, evals.load_golden(tmp_path / "golden.yaml"))

    assert proof["runDate"] == source["started_at"][:10]
    assert proof["correct"] == proof["correctTotal"] == 32


def test_a_tile_builds_its_chart_from_the_rows(golden):
    tile = next(tile for tile in landing_data.TILES if tile.chart_type == "compare_bars")
    columns = ["player", "season", "goals", "goals_per_90", "xg_per_90"]
    rows = [["Thierry Henry", "2003-04", 30, 0.81, 0.65], ["Bukayo Saka", "2025-26", 7, 0.28, 0.35]]

    data = landing_data.tile_data(tile, golden, lambda sql: (columns, rows))

    assert data["id"] == "q02"
    assert data["chart"]["id"] == "tile_q02"
    assert [metric["values"] for metric in data["chart"]["metrics"]] == [
        [30, 7],
        [0.81, 0.28],
        [0.65, 0.35],
    ]


def test_a_tile_with_the_wrong_chart_type_stops(golden):
    tile = landing_data.Tile("q01", "heatmap", "Title", "Label", "2003-04", "SELECT 1")
    with pytest.raises(landing_data.LandingDataError, match="q01"):
        landing_data.tile_data(tile, golden, lambda sql: ([], []))


def test_a_tile_keeps_only_what_it_draws():
    shot = {
        "x": 103.14, "y": 28.06, "xg": 0.005752, "outcome": "goal", "minute": 30,
        "opponent": "Liverpool", "player": "Thierry Henry", "season": "2003-04",
        "match_date": "2004-04-09",
    }  # fmt: skip
    chart = {"type": "shot_map", "id": "t", "title": "T", "shots": [shot]}

    slim = landing_data.slim(chart)

    assert slim["shots"] == [
        {
            "x": 103.1, "y": 28.1, "xg": 0.006, "outcome": "goal", "minute": 30,
            "opponent": "Liverpool", "player": None, "season": None, "match_date": None,
        }
    ]  # fmt: skip
    # The input stays as it was.
    assert chart["shots"][0]["player"] == "Thierry Henry"


def test_the_same_data_gives_the_same_bytes(committed):
    assert landing_data.to_json(committed) == COMMITTED.read_text(encoding="utf-8")
