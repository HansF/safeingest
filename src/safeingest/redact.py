"""Selective PII redaction on top of the openai/privacy-filter (opf) model.

opf detects spans for 8 labels; we replace only the categories the caller wants
masked, using typed numbered placeholders that stay stable per unique value so
downstream LLMs can track entities ("[NAME_1] emailed [NAME_2]").
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Span label (opf model or safeingest.patterns regex layer) -> user-facing category.
LABEL_TO_CATEGORY: dict[str, str] = {
    # opf model labels
    "private_person": "name",
    "private_email": "email",
    "private_phone": "phone",
    "private_address": "address",
    "account_number": "account",
    "secret": "secret",
    "private_url": "url",
    "private_date": "date",
    # regex-layer labels (patterns.py)
    "EMAIL": "email",
    "CREDIT_CARD": "account",
    "IBAN": "account",
    "BE_RRN": "rrn",
    "BE_PHONE": "phone",
    "BE_ADDRESS": "address",
}

ALL_CATEGORIES = frozenset(LABEL_TO_CATEGORY.values())
# Masked by default; url/date only under --strict (they usually carry the
# document's meaning, not personal identity).
DEFAULT_CATEGORIES = ALL_CATEGORIES - {"url", "date"}

_PLACEHOLDER = re.compile(
    r"\[(?:" + "|".join(sorted(c.upper() for c in ALL_CATEGORIES)) + r")_\d+\]"
)


@dataclass
class RedactionOutcome:
    text: str
    counts: dict[str, int] = field(default_factory=dict)
    detected_not_masked: dict[str, int] = field(default_factory=dict)
    warning: str | None = None


def resolve_categories(
    *,
    strict: bool = False,
    mask: set[str] | None = None,
    allow: set[str] | None = None,
) -> frozenset[str]:
    """Compute the active mask-set from CLI-style options."""
    for cats in (mask, allow):
        unknown = (cats or set()) - ALL_CATEGORIES
        if unknown:
            raise ValueError(
                f"Unknown categories: {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(sorted(ALL_CATEGORIES))}"
            )
    if mask is not None:
        active = frozenset(mask)
    elif strict:
        active = ALL_CATEGORIES
    else:
        active = DEFAULT_CATEGORIES
    if allow:
        active -= frozenset(allow)
    return active


def apply_placeholders(text: str, spans, categories: frozenset[str]) -> RedactionOutcome:
    """Replace detected spans of the chosen categories with [TYPE_n] placeholders.

    ``spans`` are opf DetectedSpan-like objects (label/start/end/text) sorted by
    position over ``text``. The same surface text within a category always gets
    the same number.
    """
    entity_ids: dict[tuple[str, str], int] = {}
    per_category_next: dict[str, int] = {}
    counts: dict[str, int] = {}
    skipped: dict[str, int] = {}

    pieces: list[str] = []
    cursor = 0
    # Longest span wins when two start at the same offset (model vs regex).
    for span in sorted(spans, key=lambda s: (s.start, s.start - s.end)):
        if span.start < cursor:  # overlapping span; earlier one already covers it
            continue
        category = LABEL_TO_CATEGORY.get(span.label)
        if category is None or category not in categories:
            if category is not None:
                skipped[category] = skipped.get(category, 0) + 1
            continue
        key = (category, span.text.strip().lower())
        if key not in entity_ids:
            per_category_next[category] = per_category_next.get(category, 0) + 1
            entity_ids[key] = per_category_next[category]
        pieces.append(text[cursor : span.start])
        pieces.append(f"[{category.upper()}_{entity_ids[key]}]")
        cursor = span.end
        counts[category] = counts.get(category, 0) + 1
    pieces.append(text[cursor:])
    return RedactionOutcome(text="".join(pieces), counts=counts, detected_not_masked=skipped)


def residual_counts(text: str, spans, categories: frozenset[str]) -> dict[str, int]:
    """Count detections in already-sanitized text — each one is a suspected leak.

    Spans overlapping a placeholder token are the detectors reacting to our own
    substitutions, not leaks, and are ignored. Only actively-masked categories
    count: url/date hits on a default run are policy, not leakage.
    """
    placeholder_ranges = [(m.start(), m.end()) for m in _PLACEHOLDER.finditer(text)]
    counts: dict[str, int] = {}
    for span in spans:
        category = LABEL_TO_CATEGORY.get(span.label)
        if category is None or category not in categories:
            continue
        if any(span.start < end and span.end > start for start, end in placeholder_ranges):
            continue
        counts[category] = counts.get(category, 0) + 1
    return counts


class Redactor:
    """Lazy wrapper around the opf model; loads weights on first use."""

    def __init__(self, device: str | None = None):
        self._device = device
        self._opf = None

    def _load(self):
        if self._opf is None:
            device = self._device or _detect_device()
            from opf import OPF

            self._opf = OPF(device=device, output_mode="typed")
        return self._opf

    def redact(self, text: str, categories: frozenset[str]) -> RedactionOutcome:
        from .patterns import find_pattern_spans

        result = self._load().redact(text)
        spans = list(result.detected_spans) + find_pattern_spans(result.text)
        outcome = apply_placeholders(result.text, spans, categories)
        outcome.warning = result.warning
        return outcome

    def self_check(self, sanitized: str, categories: frozenset[str]) -> dict[str, int]:
        """Re-run both detection layers on sanitized output; return leak counts."""
        from .patterns import find_pattern_spans

        result = self._load().redact(sanitized)
        spans = list(result.detected_spans) + find_pattern_spans(result.text)
        return residual_counts(result.text, spans, categories)


def _detect_device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"
