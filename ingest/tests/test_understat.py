"""Tests use small hand-written records in the Understat shape, never real source data."""

import pytest
from test_load import two_matches

from ingest import command, load, understat


def side(team_id, title):
    return {"id": team_id, "title": title, "short_title": title[:3].upper()}


def raw_date(match_id="500", home="Arsenal", away="Tottenham", goals=("2", "1"), result=True):
    return {
        "id": match_id,
        "isResult": result,
        "h": side("83", home),
        "a": side("82", away),
        "goals": {"h": goals[0], "a": goals[1]},
        "xG": {"h": "0.5", "a": "0.5"},
        "datetime": "2025-11-23 16:30:00",
    }


def test_a_cache_miss_writes_the_files_and_a_hit_makes_no_network_call(tmp_path):
    calls = []

    def fetch_team():
        calls.append("team")
        return {
            "dates": [raw_date("500"), raw_date("501", result=False)],
            "players": [],
            "statistics": {},
        }

    def fetch_match(match_id):
        calls.append(f"match {match_id}")
        return {"rosters": {"h": {}, "a": {}}, "shots": {"h": [], "a": []}}

    first = understat.fetch_season(tmp_path, fetch_team, fetch_match)

    # A fixture that has no result yet has no match data to pull.
    assert calls == ["team", "match 500"]
    assert (tmp_path / "team-Arsenal-2025.json").is_file()
    assert (tmp_path / "matches" / "500.json").is_file()
    assert list(tmp_path.rglob("*.tmp")) == []

    def no_network(*args):
        pytest.fail("a cached file must not be fetched again")

    second = understat.fetch_season(tmp_path, no_network, no_network)

    assert second == first
    assert [match["id"] for match in second.matches] == ["500"]
    assert second.match_data["500"]["shots"] == {"h": [], "a": []}


def test_a_failed_download_leaves_no_file_that_looks_cached(tmp_path):
    def fetch_team():
        raise command.FetchError("cannot download the season: HTTPStatusError")

    with pytest.raises(command.FetchError):
        understat.fetch_season(tmp_path, fetch_team, None)

    assert list(tmp_path.rglob("*.json")) == []


def test_the_pitch_centre_scales_to_60_40():
    assert understat.point("0.5", "0.5", "s1") == (60.0, 40.0)


def test_x_runs_towards_the_goal_that_the_shooter_attacks():
    x, _ = understat.point("0.885", "0.5", "s1")

    assert x == pytest.approx(106.2)


def test_y_is_mirrored_so_that_zero_is_the_left_touchline_of_the_attacker():
    # Understat counts Y from the attacker's right. The stored pitch, as in the
    # 2003-04 data, counts y from the attacker's left.
    assert understat.point("1", "0", "s1") == (120.0, 80.0)
    assert understat.point("0", "1", "s1") == (0.0, 0.0)
    _, y = understat.point("0.9", "0.25", "s1")
    assert y == pytest.approx(60.0)


@pytest.mark.parametrize(("x", "y"), [("1.01", "0.5"), ("0.5", "1.2"), ("-0.1", "0.5")])
def test_a_shot_off_the_pitch_raises_and_names_the_shot(x, y):
    with pytest.raises(load.CoordinateError, match="s-off"):
        understat.point(x, y, "s-off")


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("Goal", "goal"),
        ("SavedShot", "saved"),
        ("BlockedShot", "blocked"),
        ("MissedShots", "off target"),
        ("ShotOnPost", "post"),
    ],
)
def test_a_shot_result_maps_to_a_shared_outcome(raw, stored):
    assert understat.SHOT_OUTCOMES[raw] == stored


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("RightFoot", "right foot"),
        ("LeftFoot", "left foot"),
        ("Head", "head"),
        ("OtherBodyPart", "other"),
    ],
)
def test_a_shot_type_maps_to_a_body_part(raw, stored):
    assert understat.BODY_PARTS[raw] == stored


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("OpenPlay", "open play"),
        ("Penalty", "penalty"),
        ("DirectFreekick", "free kick"),
        ("FromCorner", "corner"),
        ("SetPiece", "set piece"),
    ],
)
def test_a_situation_maps_to_a_stored_value(raw, stored):
    assert understat.SITUATIONS[raw] == stored


@pytest.mark.parametrize(
    ("title", "name"),
    [
        ("Tottenham", "Tottenham Hotspur"),
        ("Leeds", "Leeds United"),
        ("Manchester United", "Manchester United"),
        ("Brighton", "Brighton"),
    ],
)
def test_a_club_from_2003_04_keeps_the_name_it_already_has(title, name):
    assert understat.team_name(title) == name


def roster_entry(player_id, player, position="FW", time="90", **stats):
    entry = {
        "player_id": player_id,
        "player": player,
        "position": position,
        "time": time,
        "goals": "0",
        "own_goals": "0",
        "assists": "0",
        "xG": "0",
        "xA": "0",
    }
    entry.update(stats)
    return entry


def raw_shot(shot_id, player_id, player, result, **fields):
    shot = {
        "id": shot_id,
        "player_id": player_id,
        "player": player,
        "result": result,
        "minute": "10",
        "X": "0.9",
        "Y": "0.25",
        "xG": "0.4",
        "situation": "OpenPlay",
        "shotType": "LeftFoot",
    }
    shot.update(fields)
    return shot


def rosters(*entries):
    # Understat keys each roster by its own row id.
    return {str(900 + index): entry for index, entry in enumerate(entries)}


def small_season():
    """Arsenal 2-1 Tottenham: Saka scores, Romero scores an own goal, Richarlison replies."""
    match_data = {
        "rosters": {
            "h": rosters(
                roster_entry("1", "Bukayo Saka", "AMR", goals="1", xG="0.4", xA="0.1"),
                roster_entry("2", "Viktor Gyokeres", "FW", time="70", assists="1", xG="0.76"),
                roster_entry("3", "Ethan Nwaneri", "Sub", time="20"),
            ),
            "a": rosters(
                roster_entry("9", "Richarlison", "FW", goals="1", xG="0.3"),
                roster_entry("8", "Cristian Romero", "DC", own_goals="1"),
            ),
        },
        "shots": {
            "h": [
                raw_shot("s1", "1", "Bukayo Saka", "Goal"),
                raw_shot(
                    "s2", "2", "Viktor Gyokeres", "SavedShot",
                    minute="55", X="0.885", Y="0.5", xG="0.76",
                    situation="Penalty", shotType="RightFoot",
                ),
            ],
            "a": [
                raw_shot(
                    "s3", "9", "Richarlison", "Goal",
                    xG="0.3", situation="FromCorner", shotType="Head",
                ),
                # Understat lists an own goal with the team of the player who scored it.
                raw_shot("s4", "8", "Cristian Romero", "OwnGoal", X="0.03", xG="0"),
            ],
        },
    }  # fmt: skip
    return understat.RawSeason([raw_date("500")], {"500": match_data})


def test_the_season_and_its_match_are_built_from_the_match_record():
    rows = understat.build_rows(small_season())

    assert (rows.season_id, rows.season_label, rows.data_level) == (2025, "2025-26", "SHOT")
    assert rows.source == "understat"
    assert rows.teams == ["Arsenal", "Tottenham Hotspur"]
    assert rows.events == []
    [match] = rows.matches
    assert match.source_id == "500"
    assert match.match_date.isoformat() == "2025-11-23"
    assert (match.home_team, match.away_team) == ("Arsenal", "Tottenham Hotspur")
    assert (match.home_goals, match.away_goals) == (2, 1)
    assert match.venue is None


def test_shots_are_scaled_and_mapped_for_both_teams():
    rows = understat.build_rows(small_season())

    shots = {shot.source_id: shot for shot in rows.shots}
    goal = shots["s1"]
    assert (goal.match, goal.player, goal.team, goal.minute) == ("500", "1", "Arsenal", 10)
    assert (goal.x, goal.y, goal.xg) == pytest.approx((108.0, 60.0, 0.4))
    assert (goal.outcome, goal.body_part, goal.situation) == ("goal", "left foot", "open play")
    penalty = shots["s2"]
    assert (penalty.outcome, penalty.situation, penalty.minute) == ("saved", "penalty", 55)
    away = shots["s3"]
    assert (away.team, away.body_part, away.situation) == ("Tottenham Hotspur", "head", "corner")


def test_an_own_goal_is_not_a_shot():
    rows = understat.build_rows(small_season())

    assert sorted(shot.source_id for shot in rows.shots) == ["s1", "s2", "s3"]


def test_player_match_stats_are_the_roster_values():
    rows = understat.build_rows(small_season())

    stats = {stat.player: stat for stat in rows.stats}
    assert sorted(stats) == ["1", "2", "3", "8", "9"]
    saka, gyokeres, romero = stats["1"], stats["2"], stats["8"]
    assert (saka.match, saka.team, saka.minutes, saka.goals, saka.assists) == (
        "500", "Arsenal", 90, 1, 0,
    )  # fmt: skip
    assert (saka.xg, saka.xa) == pytest.approx((0.4, 0.1))
    assert (gyokeres.minutes, gyokeres.goals, gyokeres.assists) == (70, 0, 1)
    assert stats["3"].minutes == 20
    # An own goal is credited to no player.
    assert (romero.team, romero.goals) == ("Tottenham Hotspur", 0)


def test_a_player_gets_the_understat_name_and_a_position_that_is_not_sub():
    rows = understat.build_rows(small_season())

    players = {player.source_id: player for player in rows.players}
    assert sorted(players) == ["1", "2", "3", "8", "9"]
    assert (players["1"].name, players["1"].source_name) == ("Bukayo Saka", "Bukayo Saka")
    assert players["1"].position == "AMR"
    # Nwaneri only came on as a substitute, which is not a position.
    assert players["3"].position is None


def test_a_player_gets_the_position_of_the_most_starts():
    first, second, third = small_season(), small_season(), small_season()
    second.match_data["500"]["rosters"]["h"]["900"]["position"] = "FWR"
    third.match_data["500"]["rosters"]["h"]["900"]["position"] = "Sub"
    season = understat.RawSeason(
        [raw_date("500"), raw_date("501"), raw_date("502"), raw_date("503")],
        {
            "500": first.match_data["500"],
            "501": second.match_data["500"],
            "502": second.match_data["500"],
            "503": third.match_data["500"],
        },
    )

    players = {player.source_id: player for player in understat.build_rows(season).players}

    assert players["1"].position == "FWR"


def test_a_shot_by_a_player_outside_the_roster_stops_the_build():
    season = small_season()
    season.match_data["500"]["shots"]["h"].append(raw_shot("s9", "77", "Nobody", "MissedShots"))

    with pytest.raises(ValueError, match="s9"):
        understat.build_rows(season)


@pytest.mark.parametrize(
    "field", [{"result": "Deflected"}, {"shotType": "Knee"}, {"situation": "ThrowIn"}]
)
def test_an_unknown_shot_value_stops_the_build(field):
    season = small_season()
    season.match_data["500"]["shots"]["h"].append(
        raw_shot("s9", "1", "Bukayo Saka", "MissedShots") | field
    )

    with pytest.raises(ValueError, match=next(iter(field.values()))):
        understat.build_rows(season)


def test_a_tie_between_positions_takes_the_first_by_name():
    first, second = small_season(), small_season()
    second.match_data["500"]["rosters"]["h"]["900"]["position"] = "AMC"
    season = understat.RawSeason(
        [raw_date("500"), raw_date("501")],
        {"500": first.match_data["500"], "501": second.match_data["500"]},
    )

    players = {player.source_id: player for player in understat.build_rows(season).players}

    assert players["1"].position == "AMC"


# The 20 club titles of the 2025-26 season, as Understat spells them.
UNDERSTAT_TITLES = [
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley", "Chelsea",
    "Crystal Palace", "Everton", "Fulham", "Leeds", "Liverpool", "Manchester City",
    "Manchester United", "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham",
    "West Ham", "Wolverhampton Wanderers",
]  # fmt: skip
# The club names that the 2003-04 load already stores.
NAMES_FROM_2003_04 = {
    "Arsenal", "Aston Villa", "Birmingham City", "Blackburn Rovers", "Bolton Wanderers",
    "Charlton Athletic", "Chelsea", "Everton", "Fulham", "Leeds United", "Leicester City",
    "Liverpool", "Manchester City", "Manchester United", "Middlesbrough", "Newcastle United",
    "Portsmouth", "Southampton", "Tottenham Hotspur", "Wolverhampton Wanderers",
}  # fmt: skip


def test_no_club_of_2025_26_gets_a_second_name():
    names = {understat.team_name(title) for title in UNDERSTAT_TITLES}

    # Twelve clubs played in both seasons, and each keeps its stored name.
    assert len(names & NAMES_FROM_2003_04) == 12
    assert names - NAMES_FROM_2003_04 == {
        "Bournemouth", "Brentford", "Brighton", "Burnley", "Crystal Palace",
        "Nottingham Forest", "Sunderland", "West Ham",
    }  # fmt: skip


def test_goals_that_do_not_add_up_to_the_score_stop_the_build():
    season = small_season()
    season.matches[0]["goals"]["h"] = "3"

    with pytest.raises(ValueError, match="500"):
        understat.build_rows(season)


def source_rows(conn, source):
    """Every match, shot, and player match row of one source, with its content."""
    return (
        conn.execute("SELECT * FROM matches WHERE source = %s ORDER BY id", (source,)).fetchall(),
        conn.execute("SELECT * FROM shots WHERE source = %s ORDER BY id", (source,)).fetchall(),
        conn.execute(
            "SELECT pms.* FROM player_match_stats pms JOIN matches m ON m.id = pms.match_id"
            " WHERE m.source = %s ORDER BY pms.match_id, pms.player_id",
            (source,),
        ).fetchall(),
    )


def test_an_understat_season_loads_beside_a_statsbomb_season(ingest):
    load.load(ingest, two_matches())
    before = load.table_counts(ingest)
    statsbomb_rows = source_rows(ingest, "statsbomb")

    load.load(ingest, understat.build_rows(small_season()))
    load.load(ingest, understat.build_rows(small_season()))
    load.load(ingest, two_matches())

    assert load.table_counts(ingest) == {
        "seasons": before["seasons"] + 1,
        # Arsenal is in both seasons and stays one row.
        "teams": before["teams"] + 1,
        "players": before["players"] + 5,
        "player_aliases": before["player_aliases"] + 5,
        "matches": before["matches"] + 1,
        "shots": before["shots"] + 3,
        "events": before["events"],
        "player_match_stats": before["player_match_stats"] + 5,
    }
    assert ingest.execute(
        "SELECT s.label, count(*) FROM matches m JOIN seasons s ON s.id = m.season_id"
        " GROUP BY s.label ORDER BY s.label"
    ).fetchall() == [("2003-04", 2), ("2025-26", 1)]
    assert ingest.execute("SELECT count(*) FROM teams WHERE name = 'Arsenal'").fetchone() == (1,)
    assert source_rows(ingest, "statsbomb") == statsbomb_rows


def stub_command(monkeypatch, tmp_path, season, url):
    """Point the command at a temporary cache, stub fetchers, and the given URL."""
    monkeypatch.setattr(understat, "RAW_DIR", tmp_path)
    monkeypatch.setattr(
        understat,
        "understat_fetchers",
        lambda: (
            lambda: {"dates": season.matches, "players": [], "statistics": {}},
            lambda match_id: season.match_data[match_id],
        ),
    )
    if url is None:
        monkeypatch.delenv("INGEST_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("INGEST_DATABASE_URL", url)


def test_the_command_names_a_missing_variable(monkeypatch, tmp_path, capsys):
    stub_command(monkeypatch, tmp_path, small_season(), url=None)

    assert understat.main() == 1
    assert "INGEST_DATABASE_URL is not set" in capsys.readouterr().err


def test_the_command_reports_unexpected_source_data_without_a_traceback(
    monkeypatch, tmp_path, capsys
):
    season = small_season()
    del season.match_data["500"]["shots"]["h"][0]["xG"]
    stub_command(monkeypatch, tmp_path, season, url="postgresql://ingest:x@localhost:1/none")

    assert understat.main() == 1
    assert capsys.readouterr().err.startswith("Unexpected source data, nothing was loaded")


def test_the_command_reports_a_field_of_the_wrong_type_without_a_traceback(
    monkeypatch, tmp_path, capsys
):
    season = small_season()
    season.match_data["500"]["shots"]["h"][0]["xG"] = None
    stub_command(monkeypatch, tmp_path, season, url="postgresql://ingest:x@localhost:1/none")

    assert understat.main() == 1
    assert capsys.readouterr().err.startswith("Unexpected source data, nothing was loaded")


def test_the_command_reports_a_record_of_the_wrong_shape_without_a_traceback(
    monkeypatch, tmp_path, capsys
):
    season = small_season()
    # Some sites send an empty list where a full record is an object.
    season.match_data["500"]["rosters"]["a"] = []
    stub_command(monkeypatch, tmp_path, season, url="postgresql://ingest:x@localhost:1/none")

    assert understat.main() == 1
    assert capsys.readouterr().err.startswith("Unexpected source data, nothing was loaded")


def test_a_season_that_fails_the_sanity_check_is_not_committed(db, ingest):
    # One match can never be the 38-match season the command expects.
    with pytest.raises(load.SanityError):
        command.load_season(db.ingest_url, understat.build_rows(small_season()), understat.FACTS)

    assert set(load.table_counts(ingest).values()) == {0}


def test_the_2025_26_facts_are_the_published_table():
    facts = understat.FACTS

    assert (facts.season, facts.team) == ("2025-26", "Arsenal")
    assert (facts.matches, facts.wins, facts.draws, facts.losses) == (38, 26, 7, 5)
    assert (facts.points, facts.goals_for) == (85, 71)
    assert facts.top_scorer_goals == 14
