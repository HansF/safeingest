from safeingest.patterns import find_pattern_spans


def labels(text):
    return {(s.label, s.text) for s in find_pattern_spans(text)}


def test_iban_with_spaces_and_compact():
    found = labels("Betaal op IBAN: BE18 3632 2574 0965 of DE89370400440532013000.")
    assert ("IBAN", "BE18 3632 2574 0965") in found
    assert ("IBAN", "DE89370400440532013000") in found


def test_invalid_iban_checksum_rejected():
    assert not labels("BE18 3632 2574 0966")  # last digit off -> mod-97 fails


def test_rrn_formatted_and_bare():
    # Example from the official spec: man born 1990-02-01, serial 997, check 04.
    found = labels("RRN 90.02.01-997.04 en ook 90020199704 zonder opmaak.")
    assert ("BE_RRN", "90.02.01-997.04") in found
    assert ("BE_RRN", "90020199704") in found


def test_rrn_born_after_2000_and_bisnummer():
    assert ("BE_RRN", "04.03.05-123.55") in labels("nr 04.03.05-123.55")  # +2000000000 variant
    assert ("BE_RRN", "90.22.01-997.47") in labels("bis 90.22.01-997.47")  # month +20


def test_rrn_bad_checksum_or_month_rejected():
    # (fragments may still match the phone pattern — over-redaction is fine)
    assert not {l for l, _ in labels("90.02.01-997.05")} & {"BE_RRN"}  # wrong check digit
    assert not {l for l, _ in labels("90.13.01-997.55")} & {"BE_RRN"}  # month 13 impossible


def test_be_phone_formats():
    found = labels("Bel +32 (0)3 265 67 00 of 0478 12 34 56.")
    assert any(label == "BE_PHONE" for label, _ in found)
    assert ("BE_PHONE", "0478 12 34 56") in found


def test_enterprise_number_not_a_phone():
    # BTW/ondernemingsnummer looks phone-shaped but 10 digits must start 04.
    assert not labels("BTW: BE 0799.091.641")


def test_email_and_credit_card_via_pii_core():
    found = labels("Mail jan@acme.be, kaart 4111 1111 1111 1111.")
    assert ("EMAIL", "jan@acme.be") in found
    assert ("CREDIT_CARD", "4111 1111 1111 1111") in found


def test_pdf_invisible_chars_normalized_before_detection():
    from safeingest.convert import normalize

    dirty = "IBAN: BE18 3632 2574 0965 Sint­Amandsberg"
    assert ("IBAN", "BE18 3632 2574 0965") in labels(normalize(dirty))


def test_belgian_street_addresses():
    found = labels("Klant woont Emiel Lossystraat 37, kantoor Bellestraat 30 bus 2.")
    assert ("BE_ADDRESS", "Emiel Lossystraat 37") in found
    assert any(l == "BE_ADDRESS" and t.startswith("Bellestraat 30") for l, t in found)
    assert ("BE_ADDRESS", "Rue de la Loi 16") in labels("Adres: Rue de la Loi 16, Bruxelles")


def test_street_suffix_words_without_number_not_matched():
    assert not {l for l, _ in labels("De hoofdweg naar de markt was druk.")} & {"BE_ADDRESS"}
