"""The rules of v_player_match_advanced, on hand-written rows and on the real season."""

import json
from collections import Counter
from dataclasses import replace
from datetime import date

import pytest

from ingest import load, overrides, statsbomb

COLUMNS = (
    "chances_created",
    "duels",
    "duels_won",
    "aerial_duels",
    "aerial_duels_won",
    "aerial_duels_won_pct",
    "passes",
    "passes_completed",
    "pass_completion_pct",
    "long_balls",
    "long_balls_completed",
    "long_ball_completion_pct",
)
VIEIRA = "14"


def event(source_id, kind, player=VIEIRA, team="Arsenal", outcome=None, **details):
    return load.EventRow(
        source_id, "100", player, team, kind, 10, 0, 60.0, 40.0, None, None,
        outcome, False, 1, None, 1, **details,
    )  # fmt: skip


def shot(source_id, player=VIEIRA, aerial_won=False):
    return load.ShotRow(
        source_id, "100", player, "Arsenal", 30, 110.0, 40.0, 0.1, "saved", "head", "open play",
        aerial_won,
    )  # fmt: skip


def season() -> load.SeasonRows:
    """Arsenal 2-1 Everton. Vieira has one of each case; Keown played with no event."""
    return load.SeasonRows(
        season_id=2003,
        season_label="2003-04",
        data_level="EVENT",
        source="statsbomb",
        teams=["Arsenal", "Everton"],
        players=[
            load.PlayerRow(VIEIRA, "Patrick Vieira", "Patrick Vieira", "Center Midfield"),
            load.PlayerRow("15", "Martin Keown", "Martin Keown", "Center Back"),
            load.PlayerRow("20", "Wayne Rooney", "Wayne Mark Rooney", "Center Forward"),
        ],
        matches=[
            load.MatchRow("100", date(2003, 8, 16), "Arsenal", "Everton", 2, 1, "Arsenal Stadium")
        ],
        shots=[shot("s1", aerial_won=True), shot("s2")],
        events=[
            # Tackles: three won by their outcome, two lost.
            event("t1", "duel", outcome="won", duel_type="tackle"),
            event("t2", "duel", outcome="success in play", duel_type="tackle"),
            event("t3", "duel", outcome="success out", duel_type="tackle"),
            event("t4", "duel", outcome="lost in play", duel_type="tackle"),
            event("t5", "duel", outcome="lost out", duel_type="tackle"),
            event("a1", "duel", duel_type="aerial lost"),
            # Aerial wins on a clearance and a miscontrol, and on the pass p1 below.
            event("c1", "clearance", aerial_won=True),
            event("m1", "miscontrol", aerial_won=True),
            # The long-ball line is 35: p1 is in, p2 is not.
            event("p1", "pass", pass_length=35.0, shot_assist=True, aerial_won=True),
            event("p2", "pass", outcome="incomplete", pass_length=34.9),
            event("p3", "pass", pass_length=10.0, goal_assist=True, pass_type="free kick"),
            event("p4", "pass", outcome="out", pass_length=50.0),
            # A throw-in is not a pass of pass accuracy or long balls, also when it is long.
            event("p5", "pass", pass_length=40.0, pass_type="throw-in", shot_assist=True),
            # Events of another player stay with that player.
            event("x1", "duel", player="20", team="Everton", outcome="won", duel_type="tackle"),
        ],
        stats=[
            load.StatRow(VIEIRA, "100", "Arsenal", 90, 0, 1, 0.1, 0.2),
            load.StatRow("15", "100", "Arsenal", 90, 0, 0, 0.0, 0.0),
            load.StatRow("20", "100", "Everton", 90, 1, 0, 0.5, 0.0),
        ],
    )


def load_committed(conn, rows, player_overrides=None):
    # Only analyst_ro can read the views, and it sees committed rows only.
    load.load(conn, rows, player_overrides)
    conn.commit()


def metrics(conn, player):
    return dict(
        zip(
            COLUMNS,
            conn.execute(
                f"SELECT {', '.join(COLUMNS)} FROM v_player_match_advanced WHERE player = %s",
                (player,),
            ).fetchone(),
            strict=True,
        )
    )


def test_each_metric_follows_its_definition(ingest, analyst):
    load_committed(ingest, season())

    vieira = metrics(analyst, "Patrick Vieira")

    # p1, p3, and p5 led to a shot or a goal. The throw-in rule is for pass accuracy only.
    assert vieira["chances_created"] == 3
    # Aerial: won on p1, c1, m1, and the shot s1; lost on a1.
    assert (vieira["aerial_duels"], vieira["aerial_duels_won"]) == (5, 4)
    assert float(vieira["aerial_duels_won_pct"]) == 80.0
    # Duels: 5 tackles and 5 aerial duels. Won: 3 tackles and 4 aerials.
    assert (vieira["duels"], vieira["duels_won"]) == (10, 7)
    assert (vieira["passes"], vieira["passes_completed"]) == (4, 2)
    assert float(vieira["pass_completion_pct"]) == 50.0
    assert (vieira["long_balls"], vieira["long_balls_completed"]) == (2, 1)
    assert float(vieira["long_ball_completion_pct"]) == 50.0
    assert metrics(analyst, "Wayne Rooney")["duels_won"] == 1


def test_a_player_with_no_event_has_zeros_and_no_percentage(ingest, analyst):
    load_committed(ingest, season())

    keown = metrics(analyst, "Martin Keown")

    assert {name: value for name, value in keown.items() if not name.endswith("_pct")} == {
        name: 0 for name in COLUMNS if not name.endswith("_pct")
    }
    assert [keown[name] for name in COLUMNS if name.endswith("_pct")] == [None, None, None]


def test_a_season_with_no_event_data_has_no_row(ingest, analyst):
    rows = season()
    load_committed(ingest, replace(rows, data_level="SHOT", events=[], shots=[]))

    assert analyst.execute("SELECT count(*) FROM v_player_match_advanced").fetchone() == (0,)


def raw_events():
    """The events of the cached season, or a skip: raw data is never committed."""
    files = sorted((statsbomb.RAW_DIR / "events").glob("*.json"))
    if not files:
        pytest.skip(f"no StatsBomb cache in {statsbomb.RAW_DIR}: run ingest.statsbomb once")
    for path in files:
        yield from json.loads(path.read_text(encoding="utf-8")).values()


def counted_from_raw(name: str) -> Counter:
    """The season totals of one player, counted from the raw JSON without the loader."""
    totals: Counter = Counter()
    for raw in raw_events():
        if (raw.get("player") or {}).get("name") != name:
            continue
        kind = raw["type"]["name"]
        detail = raw.get(kind.lower(), {})
        if detail.get("aerial_won"):
            totals["aerials_won"] += 1
        if kind == "Duel":
            duel_type = detail["type"]["name"]
            outcome = detail.get("outcome", {}).get("name")
            if duel_type == "Aerial Lost":
                totals["aerials_lost"] += 1
            elif outcome in ("Won", "Success In Play", "Success Out"):
                totals["tackles_won"] += 1
            elif outcome in ("Lost In Play", "Lost Out"):
                totals["tackles_lost"] += 1
        if kind == "Pass":
            if detail.get("shot_assist") or detail.get("goal_assist"):
                totals["chances_created"] += 1
            if detail.get("type", {}).get("name") == "Throw-in":
                continue
            completed = "outcome" not in detail
            long_ball = detail["length"] >= 35
            totals["passes"] += 1
            totals["passes_completed"] += completed
            totals["long_balls"] += long_ball
            totals["long_balls_completed"] += long_ball and completed
    return totals


@pytest.mark.parametrize(
    ("source_name", "player"),
    [("Thierry Henry", "Thierry Henry"), ("Patrick Vieira", "Patrick Vieira")],
)
def test_the_season_totals_match_the_raw_files(ingest, analyst, source_name, player):
    raw = counted_from_raw(source_name)
    rows = statsbomb.build_rows(statsbomb.fetch_season(statsbomb.RAW_DIR, *[pytest.fail] * 3))
    load_committed(ingest, rows, overrides.read().players)

    view = analyst.execute(
        "SELECT sum(chances_created), sum(duels), sum(duels_won), sum(aerial_duels),"
        " sum(aerial_duels_won), sum(passes), sum(passes_completed), sum(long_balls),"
        " sum(long_balls_completed) FROM v_player_match_advanced WHERE player = %s",
        (player,),
    ).fetchone()

    duels = raw["tackles_won"] + raw["tackles_lost"] + raw["aerials_won"] + raw["aerials_lost"]
    assert raw["passes"] > 0
    assert view == (
        raw["chances_created"],
        duels,
        raw["tackles_won"] + raw["aerials_won"],
        raw["aerials_won"] + raw["aerials_lost"],
        raw["aerials_won"],
        raw["passes"],
        raw["passes_completed"],
        raw["long_balls"],
        raw["long_balls_completed"],
    )
