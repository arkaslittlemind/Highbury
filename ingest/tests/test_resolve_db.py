"""Entity resolution in the loader: a second source's players link to the first's."""

from datetime import date

import pytest

from ingest import command, load
from ingest.overrides import PlayerOverride

# (source id, name, team, goals). One Arsenal 2-1 Everton match in each source.
UNDERSTAT = [
    ("1", "Gabriel", "Arsenal", 1),
    ("2", "Gabriel Jesus", "Arsenal", 0),
    ("3", "Gabriel Martinelli", "Arsenal", 1),
    ("4", "Jordan Pickford", "Everton", 0),
]


def season(source, players, season_id=2025, label="2025-26") -> load.SeasonRows:
    return load.SeasonRows(
        season_id=season_id,
        season_label=label,
        data_level="SHOT",
        source=source,
        teams=["Arsenal", "Everton"],
        players=[load.PlayerRow(pid, name, name, None) for pid, name, _, _ in players],
        matches=[load.MatchRow("m1", date(season_id, 9, 20), "Arsenal", "Everton", 2, 1, None)],
        shots=[],
        events=[],
        stats=[
            load.StatRow(pid, "m1", team, 90, goals, 0, None, None)
            for pid, _, team, goals in players
        ],
    )


def fpl(*players, **kwargs) -> load.SeasonRows:
    return season("fpl", list(players), **kwargs)


def owner(conn, source, source_id) -> str:
    """Return the canonical name of the player that a source record is linked to."""
    (name,) = conn.execute(
        "SELECT p.name FROM player_aliases a JOIN players p ON p.id = a.player_id"
        " WHERE a.source = %s AND a.source_player_id = %s",
        (source, source_id),
    ).fetchone()
    return name


def players(conn) -> int:
    return load.table_counts(conn)["players"]


@pytest.fixture
def first(ingest):
    """The ingest connection with the Understat season loaded."""
    load.load(ingest, season("understat", UNDERSTAT))
    return ingest


def test_a_second_source_links_by_name_to_the_player_of_the_first(first):
    review = load.load(first, fpl(("10", "Gabriel Magalhães", "Arsenal", 1)))

    assert owner(first, "fpl", "10") == "Gabriel"
    assert players(first) == len(UNDERSTAT)
    # A fuzzy link is not certain, so it is in the review.
    ((row),) = review
    assert (row.source_id, row.match.outcome, row.match.player) == ("10", "fuzzy", "Gabriel")


def test_an_exact_name_links_and_is_not_reviewed(first):
    review = load.load(first, fpl(("11", "Gabriel Jesus", "Arsenal", 0)))

    assert owner(first, "fpl", "11") == "Gabriel Jesus"
    assert review == []


def test_a_name_that_fits_two_players_becomes_a_new_player_and_is_reviewed(first):
    review = load.load(first, fpl(("12", "Gabriel Martinelli Silva", "Arsenal", 0)))

    assert owner(first, "fpl", "12") == "Gabriel Martinelli Silva"
    assert players(first) == len(UNDERSTAT) + 1
    assert [row.match.outcome for row in review] == ["ambiguous"]


def test_the_same_name_in_another_team_is_not_a_candidate(first):
    review = load.load(first, fpl(("13", "Gabriel", "Everton", 0)))

    assert owner(first, "fpl", "13") == "Gabriel"
    assert players(first) == len(UNDERSTAT) + 1
    # Everton's only candidate is far from the name: a new player, in the review.
    assert [(row.match.outcome, row.match.player) for row in review] == [
        ("unmatched", "Jordan Pickford")
    ]


def test_the_same_name_in_another_season_is_not_a_candidate(first):
    review = load.load(first, fpl(("14", "Gabriel", "Arsenal", 0), season_id=2003, label="2003-04"))

    assert players(first) == len(UNDERSTAT) + 1
    # No candidate at all is the normal case for a season's first source.
    assert review == []


def test_two_players_of_one_source_never_link_to_each_other(first):
    review = load.load(
        first, season("understat", [*UNDERSTAT, ("5", "Gabriel Paulista", "Arsenal", 0)])
    )

    assert owner(first, "understat", "5") == "Gabriel Paulista"
    assert players(first) == len(UNDERSTAT) + 1
    assert review == []


def test_a_link_override_wins_over_the_name(first):
    override = PlayerOverride("fpl", "10", "2025-26", "Gabriel Jesus")

    review = load.load(
        first, fpl(("10", "Gabriel Magalhães", "Arsenal", 1)), {("fpl", "10"): override}
    )

    assert owner(first, "fpl", "10") == "Gabriel Jesus"
    assert players(first) == len(UNDERSTAT)
    assert review == []


def test_a_separate_override_makes_a_new_player_where_the_name_would_link(first):
    override = PlayerOverride("fpl", "11", None, None)

    load.load(first, fpl(("11", "Gabriel Jesus", "Arsenal", 0)), {("fpl", "11"): override})

    assert players(first) == len(UNDERSTAT) + 1
    assert first.execute(
        "SELECT count(*) FROM players WHERE name = 'Gabriel Jesus'"
    ).fetchone() == (2,)


def test_an_override_for_another_source_is_ignored(first):
    override = PlayerOverride("statsbomb", "10", None, None)

    load.load(
        first, fpl(("10", "Gabriel Magalhães", "Arsenal", 1)), {("statsbomb", "10"): override}
    )

    assert owner(first, "fpl", "10") == "Gabriel"


@pytest.mark.parametrize(
    ("override", "problem"),
    [
        (
            PlayerOverride("fpl", "10", "2025-26", "Gabriel Jesus"),
            "override fpl 10 links it to Gabriel Jesus, but the database links it to Gabriel;"
            " reload into a fresh database",
        ),
        (
            PlayerOverride("fpl", "10", None, None),
            "override fpl 10 is separate, but the database links it to Gabriel",
        ),
        (
            PlayerOverride("fpl", "10", "2025-26", "Gabriel Magalhaes"),
            r"override fpl 10: Gabriel Magalhaes \(2025-26\): no such player",
        ),
    ],
)
def test_an_override_that_disagrees_with_the_database_stops_the_load(first, override, problem):
    rows = fpl(("10", "Gabriel Magalhães", "Arsenal", 1))
    load.load(first, rows)
    before = load.table_counts(first)

    with pytest.raises(ValueError, match=problem):
        load.load(first, rows, {("fpl", "10"): override})

    assert load.table_counts(first) == before
    assert owner(first, "fpl", "10") == "Gabriel"


def goals(conn, source) -> list[tuple[str, str, int]]:
    """Return (source id, player, goals) of every stats row of a source's matches."""
    return conn.execute(
        "SELECT a.source_player_id, p.name, pms.goals FROM player_match_stats pms"
        " JOIN matches m ON m.id = pms.match_id"
        " JOIN players p ON p.id = pms.player_id"
        " JOIN player_aliases a ON a.player_id = p.id AND a.source = m.source"
        " WHERE m.source = %s ORDER BY 1",
        (source,),
    ).fetchall()


def test_two_records_that_pick_one_player_never_share_it(first):
    review = load.load(
        first,
        fpl(("10", "Gabriel Magalhães", "Arsenal", 1), ("11", "Gabriel", "Arsenal", 0)),
    )

    # The exact name wins; the fuzzy one becomes a new player, and both goals stay.
    assert goals(first, "fpl") == [("10", "Gabriel Magalhães", 1), ("11", "Gabriel", 0)]
    assert [(row.source_id, row.match.outcome, row.match.player) for row in review] == [
        ("10", "ambiguous", "Gabriel")
    ]


def test_a_name_link_never_takes_the_player_of_a_link_override(first):
    override = PlayerOverride("fpl", "10", "2025-26", "Gabriel Jesus")

    review = load.load(
        first,
        fpl(("10", "Gabriel Magalhães", "Arsenal", 1), ("11", "Gabriel Jesus", "Arsenal", 0)),
        {("fpl", "10"): override},
    )

    assert goals(first, "fpl") == [("10", "Gabriel Jesus", 1), ("11", "Gabriel Jesus", 0)]
    assert owner(first, "fpl", "11") == "Gabriel Jesus"
    assert players(first) == len(UNDERSTAT) + 1
    assert [(row.source_id, row.match.outcome) for row in review] == [("11", "ambiguous")]


def test_two_link_overrides_to_one_player_stop_the_load(first):
    overrides = {
        ("fpl", source_id): PlayerOverride("fpl", source_id, "2025-26", "Gabriel")
        for source_id in ("10", "12")
    }
    rows = fpl(("10", "Gabriel Magalhães", "Arsenal", 1), ("12", "Gabi", "Arsenal", 0))

    with pytest.raises(ValueError, match="records fpl 10, 12 all link to Gabriel"):
        load.load(first, rows, overrides)


def test_an_override_to_a_player_that_a_record_of_its_source_has_stops_the_load(first):
    load.load(first, fpl(("11", "Gabriel Jesus", "Arsenal", 0)))
    override = PlayerOverride("fpl", "10", "2025-26", "Gabriel Jesus")

    with pytest.raises(ValueError, match="records fpl 10, 11 all link to Gabriel Jesus"):
        load.load(first, fpl(("10", "Gabriel Magalhães", "Arsenal", 1)), {("fpl", "10"): override})


def test_a_second_run_finds_each_player_by_source_id_and_changes_nothing(first):
    rows = fpl(("10", "Gabriel Magalhães", "Arsenal", 1), ("15", "Kai Havertz", "Arsenal", 0))
    load.load(first, rows)
    before = load.table_counts(first)

    review = load.load(first, rows)

    assert load.table_counts(first) == before
    assert review == []


# After both loads, each source holds one Arsenal 2-1 win, so the season has two.
BOTH = load.SeasonFacts("2025-26", "Arsenal", 2, 2, 0, 0, 6, 4, "Gabriel", 2)


def env(db):
    return {"INGEST_DATABASE_URL": db.ingest_url}


def test_the_command_writes_the_review_report_and_names_it(db, first, tmp_path, capsys):
    first.commit()
    rows = fpl(("10", "Gabriel Magalhães", "Arsenal", 1))

    assert command.run(lambda: rows, BOTH, env(db), review_dir=tmp_path) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == f"review: 1 records to check in {(tmp_path / 'fpl.md').as_posix()}"
    report = (tmp_path / "fpl.md").read_text(encoding="utf-8")
    assert report.startswith("# Entity review: fpl 2025-26\n")
    assert "| 10 | Gabriel Magalhães | Arsenal | fuzzy: linked | Gabriel |" in report


def test_a_run_with_nothing_to_review_says_so_in_the_report(db, ingest, tmp_path, capsys):
    facts = load.SeasonFacts("2025-26", "Arsenal", 1, 1, 0, 0, 3, 2, "Gabriel", 1)

    assert command.run(lambda: season("understat", UNDERSTAT), facts, env(db), tmp_path) == 0

    assert capsys.readouterr().out.splitlines()[-1].startswith("review: 0 records to check in")
    assert (tmp_path / "understat.md").read_text(encoding="utf-8") == (
        "# Entity review: understat 2025-26\n\nNo records need review.\n"
    )


def test_a_load_that_fails_writes_no_report(db, ingest, tmp_path, capsys):
    wrong = load.SeasonFacts("2025-26", "Arsenal", 9, 1, 0, 0, 3, 2, "Gabriel", 1)

    assert command.run(lambda: season("understat", UNDERSTAT), wrong, env(db), tmp_path) == 1

    assert "Sanity check failed" in capsys.readouterr().err
    assert not (tmp_path / "understat.md").exists()
