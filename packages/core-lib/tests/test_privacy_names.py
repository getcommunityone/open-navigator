"""#1468: private residents' full names in served meeting text become "First L.", home addresses "[address]".

The excerpts are shaped like the real ones (caption windows, ts_headline output with <mark>), with invented people.
"""

from __future__ import annotations

import pytest

from core_lib.privacy import (
    ADDRESS_MASK,
    NameRedactor,
    official_name_key,
    place_key,
    redact_person_names,
    shorten_full_name,
)

R = NameRedactor(public_figures=frozenset({"trump", "donald trump", "elon musk", "musk", "biden"}))
TUSCALOOSA_OFFICIALS = frozenset({"walt maddox", "kip tyner"})


def red(text: str, officials: frozenset[str] = frozenset()) -> str:
    return R.redact(text, official_names=officials)


def test_the_chair_calling_a_resident_with_their_address():
    out = red("Thank you. Next, Johnathan Pemberton of 412 Elmwood Street, you have three minutes.")
    assert out == f"Thank you. Next, Johnathan P. of {ADDRESS_MASK}, you have three minutes."


def test_the_sign_up_sheet_form():
    assert red("Mike Dunleavy, 96 Maple Street. Uh, I am here about the noise") == (
        f"Mike D., {ADDRESS_MASK} Uh, I am here about the noise"
    )


def test_next_speaker_in_lower_case_captions():
    out = red("okay next speaker is johnathan pemberton and then we will hear from staff")
    assert "pemberton" not in out.lower()
    assert "Johnathan P." in out


def test_self_introduction_with_a_middle_name_never_keeps_the_surname():
    out = red("Good evening. My name is Mary Ann Whitcombe and I live at 1204 Oak Ridge Drive in Ward 3.")
    assert "Whitcombe" not in out and "1204" not in out and "Oak Ridge" not in out
    assert "My name is Mary W." in out
    assert f"I live at {ADDRESS_MASK}" in out


def test_im_and_live_self_introduction():
    out = red("I'm Linda Castellano, a resident of District 4, and I oppose the rezoning.")
    assert out.startswith("I'm Linda C., a resident")


def test_a_neighbour_named_mid_speech():
    out = red("My neighbor Bob Hartwell has had water in his basement every spring since the plant opened.")
    assert "Hartwell" not in out
    assert "neighbor Bob H. has had water" in out


def test_thank_you_and_courtesy_titles():
    assert red("Thank you, Mr. Pemberton. Who is next?") == "Thank you, Mr. P. Who is next?"
    assert red("Thank you, Jane Doolittle.") == "Thank you, Jane D."
    assert red("Dr. Robert Okonkwo testified that") == "Dr. Robert O. testified that"


def test_possessive_surname():
    assert red("we agree with Kevin Marchetti's plan") == "we agree with Kevin M.'s plan"


def test_a_roster_official_of_that_government_keeps_their_name():
    text = "Thank you, Mayor. Walt Maddox said the council would vote. Councilman Kip Tyner agreed with Walt Maddox."
    assert red(text, TUSCALOOSA_OFFICIALS) == text
    # The same name elsewhere, with no roster match, is shortened.
    assert "Walt M." in red("Walt Maddox said the council would vote.")


def test_an_office_title_keeps_the_name_as_a_public_role():
    text = "Commissioner Darlene Fairbanks moved to approve, and Council Member Joe Roebuck seconded."
    assert red(text) == text


def test_a_public_figure_on_the_allow_list_is_kept():
    text = "He said Donald Trump and Elon Musk would bring the data center here."
    assert red(text) == text


def test_mark_highlighting_is_kept_around_the_shortened_name():
    out = red("Next speaker is <mark>Kevin</mark> <mark>Marchetti</mark>, who spoke about the <mark>data center</mark>.")
    assert out == "Next speaker is <mark>Kevin M.</mark>, who spoke about the <mark>data center</mark>."
    out = red("my name is John Pemberton and the <mark>fluoride</mark> in our water")
    assert out == "my name is John P. and the <mark>fluoride</mark> in our water"
    assert out.count("<mark>") == out.count("</mark>")


def test_mark_inside_an_address_stays_balanced():
    out = red("I live at 77 <mark>Water</mark> Street and the bills doubled")
    assert out == f"I live at <mark>{ADDRESS_MASK}</mark> and the bills doubled"


def test_ordinary_words_entities_and_places_are_left_alone():
    for text in (
        "my name is on the list and I am happy to be here",
        "I'm going to talk about the <mark>data center</mark>. This is Main Street.",
        "We met at the John Smith Park pavilion and Jones Construction did the work.",
        "Will Council approve the Grant Funding agreement?",
        "the Cheyenne Senior Center is what a lot of people refer to",
        "Thank you, Madam Chair.",
    ):
        assert red(text) == text, text


def test_a_lone_first_name_is_already_first_l():
    assert red("Thank you, Tatiana. Next item.") == "Thank you, Tatiana. Next item."


def test_segments_split_a_name_across_cues():
    cues = ["thank you. next speaker is Johnathan", "Pemberton of 12 Elm Street.", "I live here"]
    out = R.redact_segments(cues)
    assert out[0] == "thank you. next speaker is Johnathan P."
    assert "Pemberton" not in out[1] and ADDRESS_MASK in out[1]
    assert out[2] == "I live here"


def test_empty_and_none_pass_through():
    assert red("") == ""
    assert R.redact(None) is None


@pytest.mark.parametrize(
    "name,expected",
    [("Dana Ruizworth", "Dana R."), ("Jane Q. Doolittle", "Jane D."), ("Bob E.", "Bob E."), ("Audrey", "Audrey"),
     ("Mr. Carl Benton Jr.", "Carl B.")],
)
def test_shorten_full_name(name, expected):
    assert shorten_full_name(name) == expected


def test_shorten_full_name_keeps_an_official():
    assert shorten_full_name("Walt Maddox", official_names=TUSCALOOSA_OFFICIALS) == "Walt Maddox"


def test_keys():
    assert official_name_key("Walter A. Maddox Jr.") == "walter maddox"
    assert place_key("al", "Tuscaloosa Government") == "AL|tuscaloosa"
    assert place_key("AL", "City of Tuscaloosa") == "AL|tuscaloosa"


def test_default_redactor_reads_the_reviewed_public_figure_seed():
    assert redact_person_names("Donald Trump visited.") == "Donald Trump visited."


def test_the_packaged_public_figure_list_matches_the_reviewed_seed():
    """The API ships without dbt_project/, so the allow-list is a generated copy; it must not drift from the seed."""
    from core_lib.privacy._public_figures_data import PUBLIC_FIGURES
    from core_lib.privacy.given_names import SEED
    from core_lib.privacy.names import load_public_figures_csv

    if not SEED.is_file():
        pytest.skip("dbt seed not in this checkout")
    assert PUBLIC_FIGURES == load_public_figures_csv(SEED), "run: python -m core_lib.privacy.given_names --write"


def test_school_board_text_masks_every_private_name():
    """A resident at a school board may be a student: no name at all, not even "First L." or a lone first name."""
    out = R.redact(
        "Thank you, Emma. Next speaker is Jacob Pemberton, a junior at Central. Mr. Okafor agreed. "
        "Superintendent Dana Whitley responded.",
        school=True,
    )
    assert "Emma" not in out and "Jacob" not in out and "Pemberton" not in out and "Okafor" not in out
    assert out.startswith("Thank you, [name]. Next speaker is [name], a junior")
    assert "Superintendent Dana Whitley" in out  # a public role keeps the name


def test_is_school_board():
    from core_lib.privacy import is_school_board

    assert is_school_board("Tuscaloosa City Schools")
    assert is_school_board(None, "school_district")
    assert is_school_board("Tuscaloosa", None, "Board of Education regular meeting")
    assert not is_school_board("Tuscaloosa", "municipality", "City Council")
