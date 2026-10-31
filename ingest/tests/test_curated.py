from datetime import date

import pytest

from ingest import curated, load
from ingest.overrides import AliasEntry

ONE_PLAYER = """
teams: []
players: []
nicknames:
  - season: "2003-04"
    player: Thierry Henry
    aliases: [Henry, Titi]
"""


def season(season_id, label, source, players) -> load.SeasonRows:
    """One Arsenal home match in which every given player has a stats row."""
    return load.SeasonRows(
        season_id=season_id,
        season_label=label,
        data_level="SHOT",
        source=source,
        teams=["Arsenal", "Everton"],
        players=[
            load.PlayerRow(pid, name, source_name, None) for pid, name, source_name in players
        ],
        matches=[load.MatchRow("m1", date(season_id, 8, 16), "Arsenal", "Everton", 2, 1, None)],
        shots=[],
        events=[],
        stats=[load.StatRow(pid, "m1", "Arsenal", 90, 0, 0, None, None) for pid, _, _ in players],
    )


def invincibles(*extra) -> load.SeasonRows:
    players = [
        ("10", "Thierry Henry", "Thierry Henry"),
        ("11", "Robert Pirès", "Robert Pirès"),
        *extra,
    ]
    return season(2003, "2003-04", "statsbomb", players)


def current() -> load.SeasonRows:
    return season(2025, "2025-26", "understat", [("7", "Bukayo Saka", "Bukayo Saka")])


def entry(player="Thierry Henry", aliases=("Henry", "Titi"), season="2003-04"):
    return AliasEntry(season, player, tuple(aliases))


def manual_aliases(conn):
    return conn.execute(
        "SELECT p.name, a.source_name, a.source_player_id FROM player_aliases a"
        " JOIN players p ON p.id = a.player_id WHERE a.source = 'manual' ORDER BY 1, 2"
    ).fetchall()


def loader_aliases(conn):
    return conn.execute(
        "SELECT id, player_id, source, source_player_id, source_name FROM player_aliases"
        " WHERE source <> 'manual' ORDER BY id"
    ).fetchall()


def test_aliases_are_written_as_manual_rows(ingest):
    load.load(ingest, invincibles())

    curated.load_aliases(ingest, [entry(), entry("Robert Pirès", ("Pires",))])

    assert manual_aliases(ingest) == [
        ("Robert Pirès", "Pires", None),
        ("Thierry Henry", "Henry", None),
        ("Thierry Henry", "Titi", None),
    ]


def test_a_second_alias_load_leaves_the_same_rows(ingest):
    load.load(ingest, invincibles())
    curated.load_aliases(ingest, [entry()])
    before = manual_aliases(ingest)

    curated.load_aliases(ingest, [entry()])

    assert manual_aliases(ingest) == before


def test_an_alias_removed_from_the_file_is_removed_from_the_table(ingest):
    load.load(ingest, invincibles())
    curated.load_aliases(ingest, [entry()])

    curated.load_aliases(ingest, [entry(aliases=("Titi",))])

    assert manual_aliases(ingest) == [("Thierry Henry", "Titi", None)]


def test_an_alias_load_keeps_the_rows_of_the_season_loaders(ingest):
    load.load(ingest, invincibles())
    before = load.table_counts(ingest)["player_aliases"]
    loader_rows = loader_aliases(ingest)

    curated.load_aliases(ingest, [entry()])
    curated.load_aliases(ingest, [entry()])

    assert load.table_counts(ingest)["player_aliases"] == before + 2
    assert loader_aliases(ingest) == loader_rows
    # The season loader still finds its players, so it adds none.
    load.load(ingest, invincibles())
    assert load.table_counts(ingest)["players"] == 2


def test_the_season_tells_two_players_of_one_name_apart(ingest):
    load.load(ingest, invincibles(("12", "Gabriel", "Gabriel Fernando")))
    load.load(ingest, season(2025, "2025-26", "understat", [("5", "Gabriel", "Gabriel")]))

    curated.load_aliases(ingest, [entry("Gabriel", ("Big Gabi",), season="2025-26")])

    (source,) = ingest.execute(
        "SELECT own.source FROM player_aliases a"
        " JOIN player_aliases own ON own.player_id = a.player_id AND own.source <> 'manual'"
        " WHERE a.source_name = 'Big Gabi'"
    ).fetchone()
    assert source == "understat"


@pytest.mark.parametrize(
    ("bad", "problem"),
    [
        (entry("Thierry Henri"), r"Thierry Henri \(2003-04\): no such player"),
        (entry(season="2025-26"), r"Thierry Henry \(2025-26\): no such player"),
        (entry("Gabriel", ("Gabi",)), r"Gabriel \(2003-04\): 2 players have this name"),
        # Another player's canonical name, in another letter case.
        (entry(aliases=("robert pirès",)), "alias 'robert pirès' is the name of another player"),
        # The alias of an entry before it, in another letter case.
        (entry(aliases=("bobby",)), "alias 'bobby' is also the alias of another player"),
        # Another player's name in the source.
        (entry(aliases=("Gabriel Fernando",)), "alias 'Gabriel Fernando' is the name of another"),
    ],
)
def test_a_bad_entry_stops_the_alias_load_and_writes_nothing(ingest, bad, problem):
    load.load(
        ingest,
        invincibles(("12", "Gabriel", "Gabriel Fernando"), ("13", "Gabriel", "Gabriel Paulista")),
    )
    curated.load_aliases(ingest, [entry(aliases=("Titi",))])

    with pytest.raises(curated.CuratedError, match=problem):
        curated.load_aliases(ingest, [entry("Robert Pirès", ("Bobby",)), bad])

    assert manual_aliases(ingest) == [("Thierry Henry", "Titi", None)]


def test_an_alias_can_repeat_the_name_of_its_own_player(ingest):
    load.load(ingest, invincibles())

    curated.load_aliases(ingest, [entry(aliases=("thierry henry",))])

    assert manual_aliases(ingest) == [("Thierry Henry", "thierry henry", None)]


# The availability matrix of build-plan features 4, 19, and 24: what each season can answer.
MATRIX = {
    ("2003-04", "results"): True,
    ("2003-04", "shots"): True,
    ("2003-04", "xg"): True,
    ("2003-04", "player_stats"): True,
    ("2003-04", "passes"): True,
    ("2003-04", "pressures"): True,
    ("2003-04", "pass_networks"): True,
    ("2003-04", "pass_maps"): True,
    ("2003-04", "substitutions"): True,
    ("2003-04", "league_results"): True,
    ("2003-04", "team_match_stats"): True,
    ("2003-04", "league_table"): True,
    ("2003-04", "fpl_player_stats"): False,
    ("2025-26", "results"): True,
    ("2025-26", "shots"): True,
    ("2025-26", "xg"): True,
    ("2025-26", "player_stats"): True,
    ("2025-26", "passes"): False,
    ("2025-26", "pressures"): False,
    ("2025-26", "pass_networks"): False,
    ("2025-26", "pass_maps"): False,
    ("2025-26", "substitutions"): False,
    ("2025-26", "league_results"): True,
    ("2025-26", "team_match_stats"): True,
    ("2025-26", "league_table"): True,
    ("2025-26", "fpl_player_stats"): True,
}


def catalog(conn):
    return conn.execute(
        "SELECT s.label, c.metric, c.available, c.source, c.notes FROM data_catalog c"
        " JOIN seasons s ON s.id = c.season_id ORDER BY 1, 2"
    ).fetchall()


def test_the_catalog_matches_the_availability_matrix(ingest):
    load.load(ingest, invincibles())
    load.load(ingest, current())

    curated.load_catalog(ingest)

    rows = catalog(ingest)
    assert {(label, metric): available for label, metric, available, _, _ in rows} == MATRIX
    assert len(rows) == len(MATRIX)


def test_an_available_row_has_a_source_and_an_unavailable_row_says_why(ingest):
    load.load(ingest, invincibles())
    load.load(ingest, current())

    curated.load_catalog(ingest)

    for label, metric, available, source, notes in catalog(ingest):
        assert notes, (label, metric)
        league = metric in {name for name, _ in curated.LEAGUE_ROWS}
        if available and league:
            assert source == "football-data.co.uk", (label, metric)
        elif available and metric == curated.FPL_METRIC:
            assert "vaastav/Fantasy-Premier-League" in source
        elif available:
            assert source == {"2003-04": "StatsBomb Open Data", "2025-26": "Understat"}[label]
        else:
            assert source is None, (label, metric)


def test_a_second_catalog_load_leaves_the_same_rows(ingest):
    load.load(ingest, invincibles())
    load.load(ingest, current())
    ingest.execute(
        "INSERT INTO data_catalog (season_id, metric, available) VALUES (2003, 'old', true)"
    )
    curated.load_catalog(ingest)
    before = catalog(ingest)

    curated.load_catalog(ingest)

    assert catalog(ingest) == before
    assert len(before) == len(MATRIX)


def test_a_missing_season_stops_the_catalog_load_and_writes_nothing(ingest):
    load.load(ingest, invincibles())

    with pytest.raises(curated.CuratedError, match="season 2025-26 is not loaded"):
        curated.load_catalog(ingest)

    assert catalog(ingest) == []


def env(db):
    return {"INGEST_DATABASE_URL": db.ingest_url}


def alias_file(tmp_path, text=ONE_PLAYER):
    path = tmp_path / "overrides.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def both_seasons(ingest):
    load.load(ingest, invincibles())
    load.load(ingest, current())
    # The command opens its own connection, so it must see these rows.
    ingest.commit()


def test_the_command_loads_both_and_the_analyst_can_read_them(
    tmp_path, db, ingest, analyst, capsys
):
    both_seasons(ingest)

    assert curated.run(alias_file(tmp_path), env(db)) == 0
    first = capsys.readouterr().out
    assert curated.run(alias_file(tmp_path), env(db)) == 0

    assert capsys.readouterr().out == first
    assert first.splitlines() == ["player_aliases: 2 aliases for 1 players", "data_catalog: 26"]
    assert analyst.execute("SELECT count(*) FROM data_catalog").fetchone() == (
        len(curated.CATALOG),
    )
    assert analyst.execute(
        "SELECT source_name FROM player_aliases WHERE source = 'manual' ORDER BY 1"
    ).fetchall() == [("Henry",), ("Titi",)]


def test_the_command_loads_nothing_when_one_half_fails(tmp_path, db, ingest, capsys):
    # Only 2003-04 is there: the aliases are valid, the catalog is not.
    load.load(ingest, invincibles())
    ingest.commit()

    assert curated.run(alias_file(tmp_path), env(db)) == 1

    assert "season 2025-26 is not loaded" in capsys.readouterr().err
    assert manual_aliases(ingest) == []


def test_the_command_names_a_missing_variable(tmp_path, capsys):
    assert curated.run(alias_file(tmp_path), {}) == 1
    assert capsys.readouterr().err == "Settings error: INGEST_DATABASE_URL is not set\n"


def test_the_command_names_a_missing_overrides_file(tmp_path, db, capsys):
    assert curated.run(tmp_path / "absent.yaml", env(db)) == 1
    assert capsys.readouterr().err.startswith(
        "Overrides file is not valid, nothing was loaded: cannot read absent.yaml"
    )


def test_the_command_names_the_problem_of_a_bad_overrides_file(tmp_path, db, ingest, capsys):
    both_seasons(ingest)

    bad = ONE_PLAYER.replace("player: Thierry Henry", "name: Thierry Henry")
    assert curated.run(alias_file(tmp_path, bad), env(db)) == 1

    error = capsys.readouterr().err
    assert error.startswith(
        "Overrides file is not valid, nothing was loaded: nicknames entry 1: player is missing"
    )
    assert error.count("\n") == 1


def test_the_command_reports_an_overrides_file_that_is_not_text(tmp_path, db, capsys):
    path = tmp_path / "overrides.yaml"
    path.write_bytes(b"\xff\xfe not utf-8")

    assert curated.run(path, env(db)) == 1
    assert capsys.readouterr().err.startswith(
        "Overrides file is not valid, nothing was loaded: cannot read overrides.yaml"
    )


def test_the_command_never_prints_the_database_password(tmp_path, capsys):
    # psycopg repeats a URL it cannot parse in its own error text.
    malformed = {"INGEST_DATABASE_URL": "postgresql//ingest:hunter2@localhost:5433/highbury"}

    assert curated.run(alias_file(tmp_path), malformed) == 1

    error = capsys.readouterr().err
    assert error.startswith("Load failed, nothing was loaded")
    assert "hunter2" not in error
