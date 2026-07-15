"""False-positive / false-negative characterization tests for BE_ADDRESS.

BE_ADDRESS (patterns.py) has no checksum -- it's a shape-only detector that
deliberately accepts over-redaction (see its validator: `lambda candidate:
True`). These tests pin down *exactly* which shapes it does and doesn't
match today, so a future regex change shows up as a diff here instead of an
unnoticed behavior shift. Cases marked "accepted over-match" are not bugs.
"""

from __future__ import annotations

from safeingest.patterns import find_pattern_spans


def _labels(text):
    return {(s.label, s.text) for s in find_pattern_spans(text)}


def test_company_name_attached_to_street_is_overmatched_by_design():
    # Up to 2 leading capitalized words are swept into the match -- a company
    # name immediately before a real street address gets redacted along with
    # it. Accepted trade-off: the alternative (missing real addresses that
    # follow a capitalized word) is worse for a PII-safety tool.
    found = _labels("Firma Meubelfabriek Eikenlaan 8 exporteert naar Frankrijk.")
    assert ("BE_ADDRESS", "Firma Meubelfabriek Eikenlaan 8") in found


def test_street_and_year_look_alike_number_overmatched():
    # "Nieuwstraat 2024" is shape-valid (word + street suffix + 1-4 digit
    # number) even when the number is actually a year, not a house number.
    found = _labels("De nieuwe fietsroute langs Nieuwstraat 2024 werd geopend.")
    assert ("BE_ADDRESS", "Nieuwstraat 2024") in found


def test_street_name_and_adjacent_postcode_only_number_matches_as_address():
    # "Rue Neuve 2000" grabs the postcode as if it were a house number when
    # a postcode immediately follows a real street name with no comma.
    found = _labels("Rue Neuve 2000 Bruxelles centre commercial.")
    assert ("BE_ADDRESS", "Rue Neuve 2000") in found


def test_space_separated_compound_place_name_not_matched():
    # "Grote Markt" (two words) is NOT matched: the suffix list requires the
    # suffix fused onto the preceding word (e.g. "Grotemarkt"), so a
    # space-separated square/market name slips through undetected. This is
    # a real recall gap, not a precision one -- documented here so it's a
    # conscious backlog item rather than a silent surprise.
    assert not _labels("Bedrijf gevestigd op Grote Markt 1 in Brussel.")


def test_fused_compound_place_name_is_matched():
    # The fused form of the same name above DOES match.
    found = _labels("Winkel op Grotemarkt 1 in Gent.")
    assert ("BE_ADDRESS", "Grotemarkt 1") in found


def test_unrelated_capitalized_phrase_with_number_not_matched():
    # A person's name followed by an unrelated number must not look like an
    # address just because both are capitalized-word-then-digits.
    assert not _labels("Jan Peeters 12")


def test_postcode_and_city_alone_not_matched():
    # No street suffix present at all -- correctly not matched (matches the
    # documented "postcode-only mentions aren't detected" limitation, but
    # from the other direction: no spurious address either).
    assert not _labels("Postcode 9000 Gent zonder straat.")


def test_street_suffix_word_generic_sentence_not_matched():
    assert not _labels("ik woon in een klein huisje zonder adres.")


def test_house_number_letter_suffix_matched():
    found = _labels("Kantoor: Kerkstraat 12A, derde verdieping.")
    assert ("BE_ADDRESS", "Kerkstraat 12A") in found


def test_french_street_with_multiword_particle_name_matched():
    found = _labels("Adres kantoor: Avenue des Champs 22, 1000 Bruxelles.")
    assert ("BE_ADDRESS", "Avenue des Champs 22") in found
