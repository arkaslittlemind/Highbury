from textwrap import indent

import pytest

from ingest import overrides
from ingest.overrides import AliasEntry, PlayerOverride

ONE_PLAYER = """
- season: "2003-04"
  player: Thierry Henry
  aliases: [Henry, Titi]
"""
ONE_TEAM = """
- team: Manchester City
  spellings: [Man City]
"""
ONE_LINK = """
- source: fpl
  source_id: "123"
  season: "2025-26"
  player: Gabriel
"""


def document(teams="[]", players="[]", nicknames="[]") -> str:
    """Return an overrides file with each section given as YAML text."""

    def section(name: str, body: str) -> str:
        body = body.strip("\n")
        if body.lstrip().startswith("-"):
            return f"{name}:\n{indent(body, '  ')}\n"
        return f"{name}: {body}\n"

    return section("teams", teams) + section("players", players) + section("nicknames", nicknames)


def test_an_overrides_file_becomes_its_three_sections():
    parsed = overrides.parse(document(ONE_TEAM, ONE_LINK, ONE_PLAYER))

    assert parsed.teams == {"Man City": "Manchester City"}
    assert parsed.players == {
        ("fpl", "123"): PlayerOverride("fpl", "123", "2025-26", "Gabriel"),
    }
    assert parsed.nicknames == [AliasEntry("2003-04", "Thierry Henry", ("Henry", "Titi"))]


def test_every_section_can_be_empty():
    parsed = overrides.parse(document())

    assert (parsed.teams, parsed.players, parsed.nicknames) == ({}, {}, [])


def test_a_separate_entry_has_no_player():
    parsed = overrides.parse(document(players='- source: fpl\n  source_id: "9"\n  separate: true'))

    (override,) = parsed.players.values()
    assert override.separate
    assert (override.season, override.player) == (None, None)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("teams: []\nplayers: []", "section nicknames is missing"),
        (document() + "aliases: []\n", "unknown section 'aliases'"),
        ("teams: {}\nplayers: []\nnicknames: []", "section teams must be a list"),
        ("- just text", "must have the sections teams, players, nicknames"),
        ("teams: [unclosed", "not valid YAML: .* at line"),
    ],
)
def test_a_bad_file_shape_is_rejected_with_the_problem(text, problem):
    with pytest.raises(overrides.OverridesError, match=problem):
        overrides.parse(text)


@pytest.mark.parametrize(
    ("teams", "problem"),
    [
        ("- spellings: [Man City]", "teams entry 1: team is missing"),
        ("- team: Manchester City", "Manchester City: has no spelling"),
        ("- team: Manchester City\n  spellings: [7]", "spelling 7 is not text"),
        (ONE_TEAM + ONE_TEAM, "team Manchester City is listed twice"),
        (
            ONE_TEAM + "- team: Manchester United\n  spellings: [man city]",
            "spelling 'man city' is under Manchester City and Manchester United",
        ),
        (
            "- team: Manchester City\n  spellings: [Man City, MAN CITY]",
            "Manchester City: spelling 'MAN CITY' is listed twice",
        ),
        (
            ONE_TEAM + "- team: Manchester United\n  spellings: [Manchester City]",
            "spelling 'Manchester City' is the name of another team",
        ),
        ("- just text", "teams entry 1: must have team and spellings"),
    ],
)
def test_a_bad_team_entry_is_rejected_with_the_problem(teams, problem):
    with pytest.raises(overrides.OverridesError, match=problem):
        overrides.parse(document(teams=teams))


@pytest.mark.parametrize(
    ("players", "problem"),
    [
        ('- source_id: "1"\n  separate: true', "players entry 1: source is missing"),
        ("- source: fpl\n  separate: true", "players entry 1: source_id is missing"),
        ("- source: fpl\n  source_id: 123\n  separate: true", "source_id 123 is a number"),
        (
            '- source: fpl\n  source_id: "1"\n  player: Gabriel',
            "players entry 1: season is missing",
        ),
        ('- source: fpl\n  source_id: "1"\n  season: "2025-26"', "player is missing"),
        ('- source: fpl\n  source_id: "1"\n  separate: false', "separate must be true"),
        (
            ONE_LINK + '- source: fpl\n  source_id: "123"\n  separate: true',
            "fpl 123 is listed twice",
        ),
        (ONE_LINK.rstrip() + "\n  separate: true", "has both a player and separate"),
        ("- just text", "players entry 1: must have source, source_id"),
    ],
)
def test_a_bad_player_entry_is_rejected_with_the_problem(players, problem):
    with pytest.raises(overrides.OverridesError, match=problem):
        overrides.parse(document(players=players))


@pytest.mark.parametrize(
    ("nicknames", "problem"),
    [
        ("- player: Thierry Henry\n  aliases: [Henry]", "nicknames entry 1: season is missing"),
        ('- season: "2003-04"\n  aliases: [Henry]', "nicknames entry 1: player is missing"),
        ('- season: "2003-04"\n  player: Thierry Henry', "Thierry Henry: has no alias"),
        ('- season: "2003-04"\n  player: Thierry Henry\n  aliases: []', "has no alias"),
        ('- season: "2003-04"\n  player: Thierry Henry\n  aliases: ["  "]', "an empty alias"),
        ('- season: "2003-04"\n  player: Thierry Henry\n  aliases: [14]', "alias 14 is not text"),
        (ONE_PLAYER + ONE_PLAYER, r"Thierry Henry \(2003-04\) is listed twice"),
        (
            ONE_PLAYER + '- season: "2003-04"\n  player: Karl Henry\n  aliases: [henry]',
            "alias 'henry' is under Thierry Henry and Karl Henry",
        ),
        (
            '- season: "2003-04"\n  player: Thierry Henry\n  aliases: [Titi, titi]',
            "Thierry Henry: alias 'titi' is listed twice",
        ),
        ("{season: 2003-04}", "section nicknames must be a list"),
        ("- just text", "nicknames entry 1: must have season, player, and aliases"),
        (
            ONE_PLAYER + '- season: "2025-26"\n  player: Thierry Henry\n  aliases: [TITI]',
            "alias 'TITI' is under Thierry Henry and Thierry Henry",
        ),
    ],
)
def test_a_bad_nickname_entry_is_rejected_with_the_problem(nicknames, problem):
    with pytest.raises(overrides.OverridesError, match=problem):
        overrides.parse(document(nicknames=nicknames))


def test_every_problem_in_the_file_is_named_at_once():
    text = document(
        teams="- team: Manchester City",
        players="- source: fpl\n  separate: true",
        nicknames=(
            '- season: "2003-04"\n  aliases: [Henry]\n- player: Robert Pirès\n  aliases: [Pires]'
        ),
    )

    with pytest.raises(overrides.OverridesError) as error:
        overrides.parse(text)

    for problem in (
        "Manchester City: has no spelling",
        "players entry 1: source_id is missing",
        "nicknames entry 1: player is missing",
        "nicknames entry 2: season is missing",
    ):
        assert problem in str(error.value)


def test_a_file_that_cannot_be_read_is_an_overrides_error(tmp_path):
    with pytest.raises(overrides.OverridesError, match="cannot read absent.yaml"):
        overrides.read(tmp_path / "absent.yaml")


def test_the_shipped_overrides_file_is_valid():
    parsed = overrides.read()

    # The nicknames of aliases.yaml, which this file replaced, all moved unchanged.
    assert len(parsed.nicknames) == 26
    assert sum(len(entry.aliases) for entry in parsed.nicknames) == 71
    assert {entry.season for entry in parsed.nicknames} == {"2003-04", "2025-26"}
    assert AliasEntry("2003-04", "Thierry Henry", ("Henry", "Titi", "T. Henry")) in (
        parsed.nicknames
    )
    # The spellings of the two maps that the code held before.
    assert parsed.teams["Man United"] == "Manchester United"
    assert parsed.teams["Tottenham"] == "Tottenham Hotspur"
    assert parsed.players == {}
