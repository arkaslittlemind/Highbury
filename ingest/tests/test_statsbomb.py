"""Tests use small hand-written records in the StatsBomb shape, never real source data."""

import pytest

from ingest import command, load, statsbomb

ARSENAL = {"id": 1, "name": "Arsenal"}
EVERTON = {"id": 29, "name": "Everton"}
HENRY = {"id": 10, "name": "Thierry Henry"}
PIRES = {"id": 11, "name": "Robert Pires"}
ROONEY = {"id": 20, "name": "Wayne Mark Rooney"}


def raw_match(match_id=100, home="Arsenal", away="Everton", home_score=2, away_score=1):
    return {
        "match_id": match_id,
        "match_date": "2003-08-16",
        "home_team": {"home_team_id": 1, "home_team_name": home},
        "away_team": {"away_team_id": 29, "away_team_name": away},
        "home_score": home_score,
        "away_score": away_score,
        "stadium": {"id": 5, "name": "Arsenal Stadium"},
    }


def span(position="Left Wing", start="00:00", start_period=1, end=None, end_period=None):
    return {
        "position": position,
        "from": start,
        "to": end,
        "from_period": start_period,
        "to_period": end_period,
    }


def lineup_player(player, nickname=None, positions=()):
    return {
        "player_id": player["id"],
        "player_name": player["name"],
        "player_nickname": nickname,
        "cards": [],
        "positions": list(positions),
    }


def raw_event(event_id, kind, team=ARSENAL, player=HENRY, location=(60.0, 40.0), **extra):
    event = {
        "id": event_id,
        "period": 1,
        "minute": 12,
        "second": 30,
        "type": {"name": kind},
        "possession": 7,
        "team": team,
        "player": player,
    }
    if location is not None:
        event["location"] = list(location)
    event.update(extra)
    return event


def raw_shot(event_id, outcome="Goal", xg=0.25, key_pass_id=None, **kwargs):
    shot = {
        "statsbomb_xg": xg,
        "end_location": [120.0, 38.0, 1.2],
        "outcome": {"name": outcome},
        "type": {"name": "Open Play"},
        "body_part": {"name": "Right Foot"},
    }
    if key_pass_id:
        shot["key_pass_id"] = key_pass_id
    return raw_event(event_id, "Shot", shot=shot, **kwargs)


def test_a_cache_miss_writes_the_files_and_a_hit_makes_no_network_call(tmp_path):
    calls = []

    def fetch_matches():
        calls.append("matches")
        return {100: raw_match(100), 200: raw_match(200, home="Chelsea", away="Fulham")}

    def fetch_lineups(match_id):
        calls.append(f"lineups {match_id}")
        return {1: {"team_id": 1, "team_name": "Arsenal", "lineup": []}}

    def fetch_events(match_id):
        calls.append(f"events {match_id}")
        return {"e1": raw_event("e1", "Pass")}

    first = statsbomb.fetch_season(tmp_path, fetch_matches, fetch_lineups, fetch_events)

    # The match without Arsenal is never pulled.
    assert calls == ["matches", "lineups 100", "events 100"]
    assert (tmp_path / "matches-2-44.json").is_file()
    assert (tmp_path / "lineups" / "100.json").is_file()
    assert (tmp_path / "events" / "100.json").is_file()
    assert list(tmp_path.rglob("*.tmp")) == []

    def no_network(*args):
        pytest.fail("a cached file must not be fetched again")

    second = statsbomb.fetch_season(tmp_path, no_network, no_network, no_network)

    assert second == first
    assert [match["match_id"] for match in second.matches] == [100]
    assert second.events[100][0]["id"] == "e1"
    assert second.lineups[100][0]["team_name"] == "Arsenal"


def test_a_failed_download_leaves_no_file_that_looks_cached(tmp_path):
    def fetch_matches():
        raise OSError("connection reset")

    with pytest.raises(command.FetchError):
        statsbomb.fetch_season(tmp_path, fetch_matches, None, None)

    assert list(tmp_path.rglob("*.json")) == []


def test_a_location_maps_to_the_same_pitch_point():
    assert statsbomb.point([91.5, 37.1], "e1") == (91.5, 37.1)


def test_the_pitch_edges_are_in_bounds():
    assert statsbomb.point([0.0, 0.0], "e1") == (0.0, 0.0)
    assert statsbomb.point([120.0, 80.0], "e1") == (120.0, 80.0)


def test_a_missing_location_maps_to_no_point():
    assert statsbomb.point(None, "e1") == (None, None)


@pytest.mark.parametrize("location", [[120.5, 40.0], [60.0, 80.2], [-0.1, 40.0], [60.0, -1.0]])
def test_a_location_off_the_pitch_raises_and_names_the_event(location):
    with pytest.raises(statsbomb.CoordinateError, match="e-off"):
        statsbomb.point(location, "e-off")


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("Goal", "goal"),
        ("Saved", "saved"),
        ("Saved to Post", "saved"),
        ("Saved Off Target", "saved"),
        ("Blocked", "blocked"),
        ("Off T", "off target"),
        ("Wayward", "off target"),
        ("Post", "post"),
    ],
)
def test_a_shot_outcome_maps_to_a_shared_value(raw, stored):
    assert statsbomb.shot_outcome(raw) == stored


def test_an_unknown_shot_outcome_raises():
    with pytest.raises(ValueError, match="Deflected"):
        statsbomb.shot_outcome("Deflected")


def test_a_full_match_is_90_minutes():
    assert statsbomb.minutes_played([span()]) == 90


def test_a_position_change_does_not_change_the_minutes():
    spans = [
        span("Left Wing", end="67:08", end_period=2),
        span("Right Wing", start="67:08", start_period=2),
    ]

    assert statsbomb.minutes_played(spans) == 90


def test_a_substitution_pair_shares_90_minutes():
    off = statsbomb.minutes_played([span(end="67:23", end_period=2)])
    on = statsbomb.minutes_played([span(start="67:23", start_period=2)])

    assert (off, on) == (67, 23)


def test_a_substitution_in_first_half_stoppage_time_counts_as_minute_45():
    off = statsbomb.minutes_played([span(end="46:10", end_period=1)])
    on = statsbomb.minutes_played([span(start="46:10", start_period=1)])

    assert (off, on) == (45, 45)


def test_a_player_who_left_early_stops_at_that_minute():
    assert statsbomb.minutes_played([span()], left_at=24) == 24


def test_a_substitute_who_comes_on_in_stoppage_time_gets_one_minute():
    assert statsbomb.minutes_played([span(start="92:15", start_period=2)]) == 1


def test_an_unused_substitute_has_no_minutes():
    assert statsbomb.minutes_played([]) == 0


WILTORD = {"id": 12, "name": "Sylvain Wiltord"}
KEOWN = {"id": 13, "name": "Martin Keown"}


def small_season():
    """Arsenal 2-1 Everton: Pires sets up Henry, Rooney scores for Everton."""
    lineups = [
        {
            "team_name": "Arsenal",
            "lineup": [
                lineup_player(HENRY, positions=[span("Left Center Forward")]),
                lineup_player(PIRES, positions=[span("Left Wing", end="60:00", end_period=2)]),
                lineup_player(
                    WILTORD, positions=[span("Left Wing", start="60:00", start_period=2)]
                ),
                lineup_player(KEOWN),
            ],
        },
        {
            "team_name": "Everton",
            "lineup": [
                lineup_player(ROONEY, "Wayne Rooney", [span("Center Forward")]),
            ],
        },
    ]
    events = [
        raw_event("start", "Starting XI", player=None, location=None),
        raw_event(
            "p1",
            "Pass",
            player=PIRES,
            location=(80.0, 20.0),
            under_pressure=True,
            **{"pass": {"recipient": HENRY, "end_location": [100.0, 35.0], "goal_assist": True}},
        ),
        raw_shot("s1", "Goal", 0.25, key_pass_id="p1", location=(104.0, 36.0)),
        raw_shot("s2", "Saved", 0.1, location=(98.0, 44.0)),
        raw_event("c1", "Carry", location=(50.0, 30.0), carry={"end_location": [58.0, 33.0]}),
        raw_event("pr1", "Pressure", team=EVERTON, player=ROONEY, location=(70.0, 10.0)),
        raw_event(
            "p2",
            "Pass",
            team=EVERTON,
            player=ROONEY,
            location=(40.0, 40.0),
            **{"pass": {"end_location": [120.0, 80.0], "outcome": {"name": "Incomplete"}}},
        ),
        raw_shot("s3", "Goal", 0.5, team=EVERTON, player=ROONEY, location=(110.0, 40.0)),
        raw_event("r1", "Ball Receipt*"),
    ]
    return statsbomb.RawSeason([raw_match(100)], {100: lineups}, {100: events})


def test_the_season_and_its_match_are_built_from_the_match_record():
    rows = statsbomb.build_rows(small_season())

    assert (rows.season_id, rows.season_label, rows.data_level) == (2003, "2003-04", "EVENT")
    assert rows.source == "statsbomb"
    assert rows.teams == ["Arsenal", "Everton"]
    [match] = rows.matches
    assert match.source_id == "100"
    assert match.match_date.isoformat() == "2003-08-16"
    assert (match.home_team, match.away_team) == ("Arsenal", "Everton")
    assert (match.home_goals, match.away_goals) == (2, 1)
    assert match.venue == "Arsenal Stadium"


def test_players_who_came_on_get_a_canonical_name_and_a_position():
    rows = statsbomb.build_rows(small_season())

    players = {player.source_id: player for player in rows.players}
    # Keown never left the bench, so he is not a player of this data set.
    assert sorted(players) == ["10", "11", "12", "20"]
    assert players["10"].name == "Thierry Henry"
    assert players["10"].position == "Left Center Forward"
    # The nickname is the name fans use; the full name stays as the source name.
    assert players["20"].name == "Wayne Rooney"
    assert players["20"].source_name == "Wayne Mark Rooney"


def test_shots_carry_xg_and_shared_outcomes_for_both_teams():
    rows = statsbomb.build_rows(small_season())

    shots = {shot.source_id: shot for shot in rows.shots}
    assert sorted(shots) == ["s1", "s2", "s3"]
    goal = shots["s1"]
    assert (goal.match, goal.player, goal.team) == ("100", "10", "Arsenal")
    assert (goal.minute, goal.x, goal.y, goal.xg) == (12, 104.0, 36.0, 0.25)
    assert (goal.outcome, goal.body_part, goal.situation) == ("goal", "right foot", "open play")
    assert shots["s2"].outcome == "saved"
    assert shots["s3"].team == "Everton"


def test_only_passes_carries_and_pressures_become_events():
    rows = statsbomb.build_rows(small_season())

    events = {event.source_id: event for event in rows.events}
    assert sorted(events) == ["c1", "p1", "p2", "pr1"]
    assert {event.type for event in rows.events} == {"pass", "carry", "pressure"}

    completed = events["p1"]
    assert (completed.x, completed.y, completed.end_x, completed.end_y) == (80.0, 20.0, 100.0, 35.0)
    assert (completed.player, completed.recipient, completed.outcome) == ("11", "10", None)
    assert completed.under_pressure is True
    assert (completed.minute, completed.second, completed.possession) == (12, 30, 7)

    failed = events["p2"]
    assert (failed.outcome, failed.recipient, failed.under_pressure) == ("incomplete", None, False)

    carry = events["c1"]
    assert (carry.end_x, carry.end_y, carry.outcome) == (58.0, 33.0, None)

    pressure = events["pr1"]
    assert (pressure.x, pressure.y, pressure.end_x, pressure.end_y) == (70.0, 10.0, None, None)


def test_player_match_stats_count_minutes_goals_assists_xg_and_xa():
    rows = statsbomb.build_rows(small_season())

    stats = {stat.player: stat for stat in rows.stats}
    assert sorted(stats) == ["10", "11", "12", "20"]
    henry, pires, wiltord, rooney = stats["10"], stats["11"], stats["12"], stats["20"]
    assert (henry.minutes, henry.goals, henry.assists) == (90, 1, 0)
    assert henry.xg == pytest.approx(0.35)
    assert henry.xa == 0
    assert (pires.minutes, pires.goals, pires.assists) == (60, 0, 1)
    assert pires.xg == 0
    assert pires.xa == pytest.approx(0.25)
    assert (wiltord.minutes, wiltord.goals, wiltord.assists) == (30, 0, 0)
    assert (rooney.team, rooney.match, rooney.goals) == ("Everton", "100", 1)


def test_a_substitution_missing_from_the_lineup_still_ends_the_minutes():
    # The real lineup files miss one substitution that the events file has.
    season = small_season()
    henry_stays_on = season.lineups[100][0]["lineup"][0]
    assert henry_stays_on["positions"] == [span("Left Center Forward")]
    season.events[100].append(
        raw_event(
            "sub",
            "Substitution",
            location=None,
            period=2,
            minute=45,
            substitution={"replacement": KEOWN},
        )
    )

    rows = statsbomb.build_rows(season)

    assert {stat.player: stat.minutes for stat in rows.stats}["10"] == 45


@pytest.mark.parametrize("card_type", ["Red Card", "Second Yellow"])
def test_a_sending_off_ends_the_minutes(card_type):
    # The real lineup spans run to the final whistle for a player who was sent off.
    season = small_season()
    henry = season.lineups[100][0]["lineup"][0]
    henry["cards"] = [{"time": "24:23", "card_type": card_type, "period": 1}]

    rows = statsbomb.build_rows(season)

    assert {stat.player: stat.minutes for stat in rows.stats}["10"] == 24


def test_a_yellow_card_does_not_end_the_minutes():
    season = small_season()
    henry = season.lineups[100][0]["lineup"][0]
    henry["cards"] = [{"time": "24:23", "card_type": "Yellow Card", "period": 1}]

    rows = statsbomb.build_rows(season)

    assert {stat.player: stat.minutes for stat in rows.stats}["10"] == 90


def test_an_event_off_the_pitch_stops_the_build():
    season = small_season()
    season.events[100].append(raw_event("bad", "Pressure", location=(121.0, 40.0)))

    with pytest.raises(statsbomb.CoordinateError, match="bad"):
        statsbomb.build_rows(season)


def test_a_season_that_fails_the_sanity_check_is_not_committed(tmp_path, db, ingest):
    season = small_season()
    fetchers = (
        lambda: {100: season.matches[0]},
        lambda match_id: dict(enumerate(season.lineups[match_id])),
        lambda match_id: {event["id"]: event for event in season.events[match_id]},
    )

    # One match can never be the 38-match season the command expects.
    with pytest.raises(load.SanityError):
        rows = statsbomb.build_rows(statsbomb.fetch_season(tmp_path, *fetchers))
        command.load_season(db.ingest_url, rows, statsbomb.FACTS)

    assert set(load.table_counts(ingest).values()) == {0}


def test_a_partial_download_is_not_read_as_a_cached_file(tmp_path):
    # A download that stopped half way leaves only the temporary file behind.
    (tmp_path / "matches-2-44.tmp").write_text('{"100": {"match_id"', encoding="utf-8")
    calls = []

    def fetch_matches():
        calls.append("matches")
        return {200: raw_match(200, home="Chelsea", away="Fulham")}

    season = statsbomb.fetch_season(tmp_path, fetch_matches, None, None)

    assert calls == ["matches"]
    assert season.matches == []
    assert list(tmp_path.rglob("*.tmp")) == []


def test_a_shot_outside_the_two_halves_is_not_stored():
    season = small_season()
    season.events[100].append(raw_shot("shootout", "Goal", 0.76, period=5))

    rows = statsbomb.build_rows(season)

    assert "shootout" not in {shot.source_id for shot in rows.shots}
    assert {stat.player: stat.goals for stat in rows.stats}["10"] == 1


def season_with_positions(*positions):
    """One match for each position Henry starts in."""
    match_ids = range(100, 100 + len(positions))
    lineups = {
        match_id: [
            {"team_name": "Arsenal", "lineup": [lineup_player(HENRY, positions=[span(position)])]}
        ]
        for match_id, position in zip(match_ids, positions, strict=True)
    }
    return statsbomb.RawSeason(
        [raw_match(match_id) for match_id in match_ids], lineups, dict.fromkeys(match_ids, [])
    )


def test_a_player_gets_the_position_of_the_most_matches():
    season = season_with_positions("Left Wing", "Center Forward", "Left Wing")

    [henry] = statsbomb.build_rows(season).players

    assert henry.position == "Left Wing"


def test_a_tie_between_positions_takes_the_first_by_name():
    season = season_with_positions("Left Wing", "Center Forward")

    [henry] = statsbomb.build_rows(season).players

    assert henry.position == "Center Forward"


def stub_command(monkeypatch, tmp_path, season, url):
    """Point the command at a temporary cache, stub fetchers, and the given URL."""
    monkeypatch.setattr(statsbomb, "RAW_DIR", tmp_path)
    monkeypatch.setattr(
        statsbomb,
        "statsbomb_fetchers",
        lambda: (
            lambda: {match["match_id"]: match for match in season.matches},
            lambda match_id: dict(enumerate(season.lineups[match_id])),
            lambda match_id: {event["id"]: event for event in season.events[match_id]},
        ),
    )
    if url is None:
        monkeypatch.delenv("INGEST_DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("INGEST_DATABASE_URL", url)


def test_the_command_names_a_missing_variable(monkeypatch, tmp_path, capsys):
    stub_command(monkeypatch, tmp_path, small_season(), url=None)

    assert statsbomb.main() == 1
    assert "INGEST_DATABASE_URL is not set" in capsys.readouterr().err


def test_the_command_never_prints_the_database_password(monkeypatch, tmp_path, capsys):
    # psycopg repeats a URL it cannot parse in its own error text.
    malformed = "postgresql//ingest:hunter2@localhost:5433/highbury"
    stub_command(monkeypatch, tmp_path, small_season(), url=malformed)

    assert statsbomb.main() == 1
    error = capsys.readouterr().err
    assert error.startswith("Load failed")
    assert "hunter2" not in error


@pytest.mark.parametrize(
    "broken",
    [
        raw_shot("odd", "Deflected"),
        {"id": "no-type", "period": 1},
    ],
)
def test_the_command_reports_unexpected_source_data_without_a_traceback(
    monkeypatch, tmp_path, capsys, broken
):
    season = small_season()
    season.events[100].append(broken)
    stub_command(monkeypatch, tmp_path, season, url="postgresql://ingest:x@localhost:1/none")

    assert statsbomb.main() == 1
    assert capsys.readouterr().err.startswith("Unexpected source data, nothing was loaded")
