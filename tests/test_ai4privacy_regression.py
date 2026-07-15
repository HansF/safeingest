"""Real-world FR/NL free-text regression using a vendored ai4privacy subset.

See tests/fixtures/ai4privacy_fr_nl/NOTICE.md for provenance, license, and
exactly how subset.jsonl was derived. Only the regex layer (find_pattern_spans)
is exercised here -- ground truth was filtered to the entity types it can
plausibly detect (EMAIL, TELEPHONENUM, CREDITCARDNUMBER); no torch/opf needed.

Two documented, *expected* low scores below are not bugs:
  - TELEPHONENUM: this dataset's phone numbers are generic FR/NL numbers, not
    exclusively Belgian, but BE_PHONE only matches Belgian shapes by design.
  - CREDITCARDNUMBER: most synthetic values in this dataset aren't Luhn-valid,
    but pii-core's CreditCardDetector requires a valid Luhn checksum by design.
    Recall is scored against the Luhn-valid subset of ground truth instead.
"""

from __future__ import annotations

import json
from pathlib import Path

from pii_core.checksums.luhn import is_valid_luhn

from safeingest.patterns import find_pattern_spans

FIXTURE = Path(__file__).parent / "fixtures" / "ai4privacy_fr_nl" / "subset.jsonl"
LABEL_MAP = {"EMAIL": "EMAIL", "TELEPHONENUM": "BE_PHONE", "CREDITCARDNUMBER": "CREDIT_CARD"}


def _rows():
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]


def _score(rows, entity_filter=None):
    tp = fn = 0
    for row in rows:
        detected_by_label: dict[str, list[str]] = {}
        for s in find_pattern_spans(row["source_text"]):
            detected_by_label.setdefault(s.label, []).append(s.text)
        for e in row["privacy_mask"]:
            if entity_filter is not None and not entity_filter(e):
                continue
            candidates = detected_by_label.get(LABEL_MAP[e["label"]], [])
            if e["value"] in candidates:
                tp += 1
                candidates.remove(e["value"])
            else:
                fn += 1
    return tp, fn


def test_fixture_present_and_balanced():
    rows = _rows()
    assert len(rows) == 250
    languages = {r["language"] for r in rows}
    assert languages == {"fr", "nl"}


def test_email_recall_high():
    rows = [r for r in _rows() if r["language"] in ("fr", "nl")]
    email_rows = [
        r for r in rows if any(e["label"] == "EMAIL" for e in r["privacy_mask"])
    ]
    tp, fn = _score(email_rows, entity_filter=lambda e: e["label"] == "EMAIL")
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    assert recall >= 0.9, f"EMAIL recall {recall:.2f} on real-world FR/NL text (tp={tp}, fn={fn})"


def test_be_phone_recall_stays_low_on_non_belgian_numbers():
    """Sanity ceiling, not a floor: BE_PHONE is Belgian-only by design, so
    recall on this general FR/NL corpus should stay low. A big jump upward
    would mean the pattern got loose enough to match non-Belgian shapes --
    worth a second look, not a silent pass."""
    rows = _rows()
    tp, fn = _score(rows, entity_filter=lambda e: e["label"] == "TELEPHONENUM")
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    assert recall <= 0.2, f"BE_PHONE recall {recall:.2f} on non-Belgian numbers -- pattern may have loosened"


def test_credit_card_recall_high_on_luhn_valid_subset():
    """pii-core's CreditCardDetector requires a valid Luhn checksum; most of
    this dataset's synthetic card numbers aren't checksum-valid. Score only
    against the subset that is -- that's the fair comparison."""
    rows = _rows()
    tp, fn = _score(
        rows,
        entity_filter=lambda e: e["label"] == "CREDITCARDNUMBER" and is_valid_luhn(e["value"]),
    )
    assert tp + fn > 0, "no Luhn-valid credit card numbers in fixture -- fixture may be stale"
    recall = tp / (tp + fn)
    assert recall >= 0.9, f"Luhn-valid credit card recall {recall:.2f} (tp={tp}, fn={fn})"
