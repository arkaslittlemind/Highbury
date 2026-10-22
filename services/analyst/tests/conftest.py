import os
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import date
from urllib.parse import urlsplit, urlunsplit

import pytest

from analyst.settings import get_settings
from ingest import curated, load


def shot(source_id, player, outcome, xg, team="Arsenal", minute=12):
    return load.ShotRow(
        source_id, "m1", player, team, minute, 104.0, 36.0, xg, outcome, "right foot", "open play"
    )


def pass_event(source_id, player, recipient, x, y):
    """A pass of Arsenal in the first half. With no recipient, the pass failed."""
    outcome = None if recipient else "incomplete"
    return load.EventRow(
        source_id,
        "m1",
        player,
        "Arsenal",
        "pass",
        5,
        0,
        x,
        y,
        x,
        y,
        outcome,
        False,
        1,
        recipient,
        1,
    )


def substitution(source_id, player_off, player_on, period, minute, second):
    """A substitution of Arsenal. StatsBomb gives it no location."""
    return replace(
        pass_event(source_id, player_off, player_on, 0.0, 0.0),
        type="substitution",
        period=period,
        minute=minute,
        second=second,
        x=None,
        y=None,
        end_x=None,
        end_y=None,
        outcome="tactical",
    )


LIVERPOOL_PLAYERS = [
    ("10", "Thierry Henry", "Thierry Henry", "Arsenal"),
    ("11", "Robert Pirès", "Robert Pirès", "Arsenal"),
    ("12", "Edu Gaspar", "Edu Gaspar", "Arsenal"),
    ("14", "Steven Gerrard", "Steven Gerrard", "Liverpool"),
    ("15", "Jamie Carragher", "Jamie Carragher", "Liverpool"),
]


def load_liverpool_home(ingest, events, shots=()):
    """Load the 2003-04 home match against Liverpool with these events and shots."""
    load.load(
        ingest,
        season(
            2003,
            "2003-04",
            "statsbomb",
            LIVERPOOL_PLAYERS,
            shots=shots,
            events=events,
            opponent="Liverpool",
        ),
    )
    ingest.commit()


def season(
    season_id, label, source, players, shots=(), events=(), opponent="Everton"
) -> load.SeasonRows:
    """One Arsenal home match. Each player is (source id, name, source name, team)."""
    return load.SeasonRows(
        season_id=season_id,
        season_label=label,
        data_level="SHOT",
        source=source,
        teams=["Arsenal", opponent],
        players=[load.PlayerRow(pid, name, alias, None) for pid, name, alias, _ in players],
        matches=[load.MatchRow("m1", date(season_id, 8, 16), "Arsenal", opponent, 2, 1, None)],
        shots=list(shots),
        events=list(events),
        stats=[load.StatRow(pid, "m1", team, 90, 0, 0, None, None) for pid, _, _, team in players],
    )


@pytest.fixture
def no_database(analyst_url):
    """A URL that the server refuses at once, so the test does not wait for a timeout."""
    url = urlsplit(os.environ["ANALYST_DATABASE_URL"])._replace(path="/highbury_no_such_database")
    analyst_url(urlunsplit(url))


@pytest.fixture
def analyst_model(monkeypatch) -> Iterator[Callable[[str | None], None]]:
    """Set the model name that the analyst service reads, for one test."""

    def use(name: str | None) -> None:
        if name is None:
            monkeypatch.delenv("ANALYST_MODEL", raising=False)
        else:
            monkeypatch.setenv("ANALYST_MODEL", name)
        # The settings are read one time and kept, so drop the kept ones.
        get_settings.cache_clear()

    yield use
    get_settings.cache_clear()


API_VARIABLES = {
    "CORS_ORIGINS": "http://localhost:3000",
    "RATE_LIMIT_PER_MINUTE": "5",
    "ANALYST_INPUT_USD_PER_MTOK": None,
    "ANALYST_OUTPUT_USD_PER_MTOK": None,
}


@pytest.fixture
def api_env(monkeypatch) -> Iterator[Callable[..., None]]:
    """Set the variables that only the API reads, for one test. None takes one out."""

    def use(**changes: str | None) -> None:
        for name, value in {**API_VARIABLES, **changes}.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        get_settings.cache_clear()

    yield use
    get_settings.cache_clear()


@pytest.fixture
def seeded(analyst_env, ingest):
    """Two small seasons with aliases and the catalog, as the analyst can read them."""
    load.load(
        ingest,
        season(
            2003,
            "2003-04",
            "statsbomb",
            [
                ("10", "Thierry Henry", "Thierry Henry", "Arsenal"),
                ("11", "Robert Pirès", "Robert Pirès", "Arsenal"),
                ("12", "Ashley Cole", "Ashley Cole", "Arsenal"),
                ("13", "Joe Cole", "Joseph John Cole", "Everton"),
            ],
            [shot("s1", "10", "goal", 0.25), shot("s2", "10", "saved", 0.5)],
            [
                pass_event("e1", "10", "11", 60.0, 40.0),
                pass_event("e2", "10", "11", 80.0, 20.0),
                pass_event("e3", "11", "10", 50.0, 30.0),
                pass_event("e4", "10", None, 100.0, 70.0),
            ],
        ),
    )
    load.load(
        ingest,
        season(
            2025,
            "2025-26",
            "understat",
            [
                ("7", "Bukayo Saka", "Bukayo Saka", "Arsenal"),
                ("9", "Micky van de Ven", "Micky van de Ven", "Everton"),
            ],
        ),
    )
    curated.load_aliases(
        ingest,
        [
            curated.AliasEntry("2003-04", "Thierry Henry", ("Henry", "Titi")),
            curated.AliasEntry("2003-04", "Robert Pirès", ("Pires",)),
            curated.AliasEntry("2025-26", "Bukayo Saka", ("Saka", "B. Saka")),
        ],
    )
    curated.load_catalog(ingest)
    # The tools open their own connections, so they must see these rows.
    ingest.commit()


@pytest.fixture
def liverpool_home(analyst_env, ingest):
    """The 2003-04 home match against Liverpool: a small pass network, shots of both teams."""
    load_liverpool_home(
        ingest,
        [
            pass_event("e1", "10", "11", 60.0, 40.0),
            pass_event("e2", "10", "11", 80.0, 20.0),
            pass_event("e3", "11", "10", 50.0, 30.0),
            pass_event("e4", "10", None, 100.0, 70.0),
            # Completed and received, so only the team leaves it out.
            replace(pass_event("e5", "14", "15", 40.0, 40.0), team="Liverpool"),
            # Pirès goes off at 71:42, so the starting XI ends there.
            substitution("sub1", "11", "12", 2, 71, 42),
            # One second after the substitution: completed, but not of the starting XI.
            replace(pass_event("e6", "12", "10", 70.0, 40.0), period=2, minute=71, second=43),
        ],
        [
            shot("s1", "10", "goal", 0.42, minute=31),
            shot("s2", "11", "saved", 0.13, minute=9),
            shot("s3", "14", "off target", 0.07, team="Liverpool", minute=55),
        ],
    )


@pytest.fixture
def liverpool_home_half_time(analyst_env, ingest):
    """The same match with a change at half time, where the clock starts again at 45:00."""
    load_liverpool_home(
        ingest,
        [
            pass_event("e1", "11", "10", 40.0, 20.0),
            # First-half stoppage time: later on the clock than the change, but before it.
            replace(pass_event("e2", "10", "11", 70.0, 40.0), minute=46, second=10),
            replace(pass_event("e3", "10", "11", 90.0, 20.0), minute=30),
            substitution("sub1", "11", "12", 2, 45, 0),
            # The first pass of the second half: Edu is on, so it is not of the starting XI.
            replace(pass_event("e4", "12", "10", 60.0, 40.0), period=2, minute=45, second=30),
        ],
    )


@pytest.fixture
def liverpool_home_no_substitution(analyst_env, ingest):
    """The same match with no Arsenal substitution: the network keeps every pass."""
    load_liverpool_home(
        ingest,
        [
            pass_event("e1", "10", "11", 60.0, 40.0),
            replace(pass_event("e2", "11", "10", 80.0, 20.0), period=2, minute=89),
        ],
    )
