"""Deterministic regex layer under the model pass (defense in depth).

Structured identifiers (IBANs, emails, card numbers, Belgian national
numbers, phone numbers) are rigidly formatted and checksum-verifiable, so a
pattern pass catches them with full recall where the NER model can miss
(e.g. mangled invoice tables). Reuses pii-toolkit/pii-core detectors and
checksums where they exist; adds Belgian detectors it doesn't ship.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from pii_core.checksums.iban import is_valid_iban
from pii_core.cross.detectors import CreditCardDetector, EmailDetector
from pii_core.detector import RegexDetector
from pii_core.types import PIIType

_NON_ALNUM = re.compile(r"[^A-Z0-9]")
_NON_DIGIT = re.compile(r"\D")


@dataclass(frozen=True)
class PatternSpan:
    """Shape-compatible with opf DetectedSpan so both merge in one pass."""

    label: str
    start: int
    end: int
    text: str
    placeholder: str = ""


class IbanDetector(RegexDetector):
    """Any-country IBAN, mod-97 + SWIFT length registry via pii-core.

    pii-core v0.1.0 reserves PIIType.IBAN but ships no generic detector;
    this fills that slot. Accepts space/dot-grouped forms (BE18 3632 ...).
    """

    pii_type: ClassVar[PIIType] = PIIType.IBAN
    name: ClassVar[str] = "iban"
    pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[A-Z]{2}\d{2}(?:[ .]?[A-Z0-9]{1,4}){3,8}\b"
    )

    def _is_valid(self, candidate: str) -> bool:
        return is_valid_iban(_NON_ALNUM.sub("", candidate))


def _valid_rrn(candidate: str) -> bool:
    """Belgian rijksregisternummer / INSZ checksum (11 digits).

    yy mm dd | serial(3) | check(2). Months 1-12, or +20/+40 for
    bis-numbers, or 00 when the birth date is unknown; day 0-31. The check
    equals 97 minus (first 9 digits mod 97); for people born in or after
    2000 the 9 digits are prefixed with a 2 before the division. A candidate
    passing either variant is accepted.
    """
    digits = _NON_DIGIT.sub("", candidate)
    if len(digits) != 11:
        return False
    month, day = int(digits[2:4]), int(digits[4:6])
    if month > 52 or month % 20 > 12 or day > 31:
        return False
    base, check = int(digits[:9]), int(digits[9:])
    return check in (97 - base % 97, 97 - (2_000_000_000 + base) % 97)


def _valid_be_phone(candidate: str) -> bool:
    digits = _NON_DIGIT.sub("", candidate)
    if digits.startswith("0032"):
        digits = "0" + digits[4:]
    elif digits.startswith("32"):
        digits = "0" + digits[2:]
    if digits.startswith("00"):  # "+32 (0)x..." keeps the optional zero
        digits = digits[1:]
    if len(digits) == 10:  # mobiles are 04xx; excludes e.g. enterprise numbers 0xxx.xxx.xxx
        return digits.startswith("04")
    return len(digits) == 9 and digits[0] == "0" and digits[1] != "0"


# Dutch street suffixes / French street prefixes followed by a house number.
# High-signal shape; city/postcode-only mentions are deliberately not matched
# (4-digit postcodes collide with years). Company addresses match too — the
# safe direction is over-redaction.
_NL_STREET = (
    r"\b(?:[A-Z][\w'.-]*[ ]){0,2}[A-Z][a-zà-ü'-]*"
    r"(?:straat|laan|weg|steenweg|lei|dreef|plein|baan|kaai|markt|dijk|gracht|hof|singel)"
    r"[ ]\d{1,4}[a-zA-Z]?(?:[ ]?(?:bus|/)[ ]?\w{1,4})?\b"
)
_FR_STREET = (
    r"\b(?:[Rr]ue|[Aa]venue|[Bb]oulevard|[Cc]haussée|[Pp]lace|[Qq]uai)"
    r"(?:[ ](?:de[ns]?|du|la|le|l'|d')?[ ]?[A-Za-zà-ü'-]+){1,4}[ ,]+\d{1,4}[a-zA-Z]?\b"
)

_BE_DETECTORS: tuple[tuple[str, re.Pattern[str], object], ...] = (
    (
        "BE_ADDRESS",
        re.compile(f"{_NL_STREET}|{_FR_STREET}"),
        lambda candidate: True,
    ),
    (
        "BE_RRN",
        re.compile(r"\b\d{2}[. ]?\d{2}[. ]?\d{2}[-–. ]?\d{3}[-–. ]?\d{2}\b"),
        _valid_rrn,
    ),
    (
        "BE_PHONE",
        re.compile(
            r"(?:\+32|0032)[\s./-]?(?:\(0\))?[\s./-]?\d(?:[\s./-]?\d){7,8}"
            r"|\b0\d{1,3}(?:[\s./-]\d{2,3}){2,4}\b"
        ),
        _valid_be_phone,
    ),
)

_PII_CORE_DETECTORS = (EmailDetector(), CreditCardDetector(), IbanDetector())


def find_pattern_spans(text: str) -> list[PatternSpan]:
    spans = [
        PatternSpan(label=m.type.value, start=m.start, end=m.end, text=m.value)
        for detector in _PII_CORE_DETECTORS
        for m in detector.detect(text)
    ]
    for label, pattern, validator in _BE_DETECTORS:
        spans.extend(
            PatternSpan(label=label, start=m.start(), end=m.end(), text=m.group(0))
            for m in pattern.finditer(text)
            if validator(m.group(0))
        )
    return spans
