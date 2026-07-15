"""Property-based / scale coverage for the checksum-verified detectors.

Hand-picked examples in test_patterns.py catch known shapes; they can't catch
"detection silently drops recall for a whole subclass of valid values" (e.g.
bis-numbers, post-2000 RRNs, a particular IBAN country). These tests generate
hundreds of checksum-valid and checksum-broken values and assert 100% recall
and 100% rejection respectively.
"""

from __future__ import annotations

from faker import Faker

from safeingest.patterns import find_pattern_spans

SEED = 20260715
N = 250


def _spans_of(text, label):
    return [s for s in find_pattern_spans(text) if s.label == label]


def _flip_last_digit(value: str) -> str:
    for i in range(len(value) - 1, -1, -1):
        if value[i].isdigit():
            flipped = str((int(value[i]) + 1) % 10)
            return value[:i] + flipped + value[i + 1 :]
    raise ValueError(f"no digit to flip in {value!r}")


def test_faker_be_ibans_all_detected():
    Faker.seed(SEED)
    fake = Faker("nl_BE")
    misses = []
    for _ in range(N):
        iban = fake.iban()
        found = _spans_of(f"Betaal naar {iban} aub.", "IBAN")
        if not any(s.text.replace(" ", "") == iban for s in found):
            misses.append(iban)
    assert not misses, f"{len(misses)}/{N} valid BE IBANs missed: {misses[:10]}"


def test_faker_fr_be_ibans_all_detected():
    Faker.seed(SEED)
    fake = Faker("fr_BE")
    misses = []
    for _ in range(N):
        iban = fake.iban()
        found = _spans_of(f"Virement vers {iban} svp.", "IBAN")
        if not any(s.text.replace(" ", "") == iban for s in found):
            misses.append(iban)
    assert not misses, f"{len(misses)}/{N} valid FR_BE IBANs missed: {misses[:10]}"


def test_faker_cross_border_ibans_detected():
    Faker.seed(SEED)
    misses = []
    for locale in ("de_DE", "fr_FR", "nl_NL", "en_GB", "es_ES", "it_IT"):
        fake = Faker(locale)
        for _ in range(20):
            iban = fake.iban()
            found = _spans_of(f"IBAN: {iban}", "IBAN")
            if not any(s.text.replace(" ", "") == iban for s in found):
                misses.append((locale, iban))
    assert not misses, f"cross-border IBANs missed: {misses[:10]}"


def test_mutated_ibans_rejected():
    Faker.seed(SEED)
    fake = Faker("nl_BE")
    survivors = []
    for _ in range(N):
        bad = _flip_last_digit(fake.iban())
        if _spans_of(f"IBAN: {bad}", "IBAN"):
            survivors.append(bad)
    assert not survivors, f"checksum-broken IBANs still detected: {survivors[:10]}"


def test_faker_rrns_all_detected():
    Faker.seed(SEED)
    fake = Faker("nl_BE")
    misses = []
    for _ in range(N):
        rrn = fake.ssn()
        if not _spans_of(f"RRN: {rrn}", "BE_RRN"):
            misses.append(rrn)
    assert not misses, f"{len(misses)}/{N} valid RRNs missed: {misses[:10]}"


def test_mutated_rrns_rejected():
    Faker.seed(SEED)
    fake = Faker("nl_BE")
    survivors = []
    for _ in range(N):
        bad = _flip_last_digit(fake.ssn())
        if _spans_of(f"RRN: {bad}", "BE_RRN"):
            survivors.append(bad)
    assert not survivors, f"checksum-broken RRNs still detected: {survivors[:10]}"


# --- Bis-number matrix (Faker's ssn() doesn't generate bis-numbers: month+20/+40) ---


def _make_rrn(year: int, month: int, day: int, serial: int, bis: int = 0) -> str:
    """Reproduce the official RRN algorithm, mirroring patterns.py::_valid_rrn."""
    m = month + bis
    base = int(f"{year % 100:02d}{m:02d}{day:02d}{serial:03d}")
    divisor = 2_000_000_000 + base if year >= 2000 else base
    check = 97 - divisor % 97
    return f"{year % 100:02d}.{m:02d}.{day:02d}-{serial:03d}.{check:02d}"


def test_rrn_matrix_including_bis_numbers():
    from random import Random

    rng = Random(SEED)
    misses = []
    for _ in range(300):
        year = rng.choice([1955, 1972, 1990, 2005, 2020])
        bis = rng.choice([0, 20, 40])
        month, day = rng.randint(1, 12), rng.randint(1, 28)
        serial = rng.randint(1, 998)
        rrn = _make_rrn(year, month, day, serial, bis)
        if not _spans_of(f"RRN: {rrn}", "BE_RRN"):
            misses.append(rrn)
    assert not misses, f"{len(misses)}/300 bis/post-2000 RRNs missed: {misses[:10]}"


# --- Credit card Luhn rejection (missing from the original suite) ---


def test_luhn_invalid_credit_cards_rejected():
    valid_cards = [
        "4111 1111 1111 1111",  # Visa test number, Luhn-valid
        "5500-0000-0000-0004",  # Mastercard test number, Luhn-valid
        "378282246310005",  # Amex test number, Luhn-valid
    ]
    for card in valid_cards:
        assert _spans_of(f"Card: {card}", "CREDIT_CARD"), f"valid card not detected: {card}"
    survivors = []
    for card in valid_cards:
        bad = _flip_last_digit(card)
        if _spans_of(f"Card: {bad}", "CREDIT_CARD"):
            survivors.append(bad)
    assert not survivors, f"Luhn-broken cards still detected: {survivors}"
