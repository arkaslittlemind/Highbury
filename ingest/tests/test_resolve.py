import pytest

from ingest import resolve
from ingest.resolve import Candidate, NameMatch, ReviewRow

ARSENAL_2025 = [
    Candidate(390, "Gabriel", ("Gabriel",)),
    Candidate(392, "Martin Odegaard", ("Martin Odegaard",)),
    Candidate(397, "Gabriel Martinelli", ("Gabriel Martinelli",)),
    Candidate(627, "Gabriel Jesus", ("Gabriel Jesus",)),
]
# StatsBomb gives the full name; the canonical name is the nickname of the lineup.
ARSENAL_2003 = [
    Candidate(25, "Kolo Touré", ("Kolo Touré", "Kolo Habib Touré")),
    Candidate(26, "Thierry Henry", ("Thierry Henry",)),
]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Ødegaard", "odegaard"),
        ("Kolo Touré", "kolo toure"),
        ("Gabriel Magalhães", "gabriel magalhaes"),
        ("Viktor Gyökeres", "viktor gyokeres"),
        ("N'Golo Kanté", "n golo kante"),
        ("J. Lehmann", "j lehmann"),
        ("  Jean-Philippe   MATETA ", "jean philippe mateta"),
        ("Łukasz Fabiański", "lukasz fabianski"),
    ],
)
def test_a_name_is_normalized(name, expected):
    assert resolve.normalize(name) == expected


@pytest.mark.parametrize(
    ("name", "player", "outcome"),
    [
        ("Gabriel Magalhães", "Gabriel", "fuzzy"),
        ("Gabriel dos Santos Magalhães", "Gabriel", "fuzzy"),
        ("Gabriel Jesus", "Gabriel Jesus", "exact"),
        ("Gabriel Martinelli", "Gabriel Martinelli", "exact"),
        ("Ødegaard", "Martin Odegaard", "fuzzy"),
        ("Odegaard", "Martin Odegaard", "fuzzy"),
        ("Martin Ødegaard", "Martin Odegaard", "exact"),
    ],
)
def test_the_tricky_names_of_2025_26_link_to_the_right_player(name, player, outcome):
    match = resolve.match_name(name, ARSENAL_2025)

    assert (match.player, match.outcome) == (player, outcome)
    assert match.linked


def test_a_name_that_fits_two_gabriels_equally_is_never_linked():
    match = resolve.match_name("Gabriel Martinelli Silva", ARSENAL_2025)

    assert match.outcome == "ambiguous"
    assert not match.linked


@pytest.mark.parametrize("name", ["Kolo Toure", "Kolo Habib Toure", "KOLO TOURÉ"])
def test_kolo_toure_links_by_either_name(name):
    match = resolve.match_name(name, ARSENAL_2003)

    assert (match.player_id, match.outcome) == (25, "exact")


def test_a_name_far_from_every_candidate_is_unmatched():
    match = resolve.match_name("Bukayo Saka", ARSENAL_2025)

    assert match.outcome == "unmatched"
    assert not match.linked
    assert match.score is not None and match.score < resolve.CUTOFF


def test_no_candidates_is_unmatched_with_no_closest_player():
    assert resolve.match_name("Gabriel", []) == NameMatch("unmatched")


def test_two_candidates_with_one_normalized_name_are_ambiguous():
    twins = [
        Candidate(1, "Kolo Touré", ("Kolo Touré",)),
        Candidate(2, "Kolo Toure", ("Kolo Toure",)),
    ]

    match = resolve.match_name("kolo toure", twins)

    assert match.outcome == "ambiguous"
    assert not match.linked


@pytest.mark.parametrize("name", ["Gabriel Magalhães", "Gabriel Martinelli Silva", "Odegaard"])
def test_the_order_of_the_candidates_does_not_change_the_result(name):
    assert resolve.match_name(name, ARSENAL_2025) == resolve.match_name(
        name, list(reversed(ARSENAL_2025))
    )


EXACT = NameMatch("exact", 390, "Gabriel", 100.0)
FUZZY = NameMatch("fuzzy", 390, "Gabriel", 100.0, "Gabriel Jesus", 70.0)


def test_a_match_to_a_free_player_keeps_its_link():
    assert resolve.settle_claims({"10": FUZZY}, {}) == {"10": FUZZY}


def test_two_records_that_pick_one_player_are_both_unlinked():
    settled = resolve.settle_claims({"10": FUZZY, "11": FUZZY}, {})

    assert {match.outcome for match in settled.values()} == {"ambiguous"}
    assert not any(match.linked for match in settled.values())
    # The report still names the player that both records picked.
    assert {match.player for match in settled.values()} == {"Gabriel"}


def test_one_exact_match_wins_over_fuzzy_matches_to_the_same_player():
    settled = resolve.settle_claims({"10": FUZZY, "11": EXACT}, {})

    assert settled["11"] == EXACT
    assert (settled["10"].outcome, settled["10"].linked) == ("ambiguous", False)


def test_two_exact_matches_to_one_player_are_both_unlinked():
    settled = resolve.settle_claims({"10": EXACT, "11": EXACT}, {})

    assert not any(match.linked for match in settled.values())


def test_a_player_taken_by_another_record_is_not_linked_again():
    settled = resolve.settle_claims({"11": EXACT}, {390: "10"})

    assert (settled["11"].outcome, settled["11"].linked) == ("ambiguous", False)


def test_unlinked_matches_are_left_as_they_are():
    unmatched = NameMatch("unmatched", None, "Gabriel", 60.0)

    assert resolve.settle_claims({"10": unmatched}, {390: "9"}) == {"10": unmatched}


def test_the_order_of_the_records_does_not_change_the_claims():
    first = resolve.settle_claims({"10": FUZZY, "11": EXACT, "12": FUZZY}, {})
    second = resolve.settle_claims({"12": FUZZY, "11": EXACT, "10": FUZZY}, {})

    assert first == second


def test_an_empty_report_says_that_nothing_needs_review():
    text = resolve.render_report("understat", "2025-26", [])

    assert text == "# Entity review: understat 2025-26\n\nNo records need review.\n"


def test_a_report_row_escapes_the_source_text():
    match = resolve.match_name("Gabriel Magalhães", ARSENAL_2025)
    row = ReviewRow("5613", "Gabriel | Big\nGabi", ("Arsenal", "Leeds United"), match)

    text = resolve.render_report("fpl", "2025-26", [row])

    assert "| 5613 | Gabriel \\| Big Gabi | Arsenal, Leeds United | fuzzy: linked | Gabriel |" in (
        text
    )
    assert text.count("\n|") == 3


def test_a_score_just_under_the_cutoff_does_not_print_as_the_cutoff():
    match = NameMatch("unmatched", None, "Gabriel", 89.6, "Gabriel Jesus", 70.0)
    row = ReviewRow("7", "Gabi", ("Arsenal",), match)

    text = resolve.render_report("fpl", "2025-26", [row])

    assert "| unmatched: new player | Gabriel | 89.6 | Gabriel Jesus | 70.0 |" in text


def test_the_report_file_is_replaced_not_appended(tmp_path):
    path = tmp_path / "review" / "statsbomb.md"

    resolve.write_report(path, "first\n")
    resolve.write_report(path, "second\n")

    assert path.read_text(encoding="utf-8") == "second\n"
