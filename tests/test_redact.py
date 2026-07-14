from dataclasses import dataclass

import pytest

from safeingest.redact import (
    ALL_CATEGORIES,
    DEFAULT_CATEGORIES,
    apply_placeholders,
    resolve_categories,
)


@dataclass
class Span:
    label: str
    start: int
    end: int
    text: str
    placeholder: str = ""


TEXT = "Alice Smith (alice@example.com) met Alice Smith on 2024-01-02, see https://x.com"
SPANS = [
    Span("private_person", 0, 11, "Alice Smith"),
    Span("private_email", 13, 30, "alice@example.com"),
    Span("private_person", 36, 47, "Alice Smith"),
    Span("private_date", 51, 61, "2024-01-02"),
    Span("private_url", 67, 80, "https://x.com"),
]


def test_default_masks_personal_keeps_url_date():
    out = apply_placeholders(TEXT, SPANS, DEFAULT_CATEGORIES)
    assert out.text == "[NAME_1] ([EMAIL_1]) met [NAME_1] on 2024-01-02, see https://x.com"
    assert out.counts == {"name": 2, "email": 1}
    assert out.detected_not_masked == {"date": 1, "url": 1}


def test_strict_masks_everything():
    out = apply_placeholders(TEXT, SPANS, ALL_CATEGORIES)
    assert "2024-01-02" not in out.text
    assert "https://x.com" not in out.text
    assert "[DATE_1]" in out.text and "[URL_1]" in out.text


def test_same_entity_same_number_distinct_entities_increment():
    spans = [
        Span("private_person", 0, 5, "Alice"),
        Span("private_person", 10, 13, "Bob"),
        Span("private_person", 20, 25, "alice"),  # case-insensitive match
    ]
    out = apply_placeholders("Alice and Bob, then alice again", spans, DEFAULT_CATEGORIES)
    assert out.text == "[NAME_1] and [NAME_2], then [NAME_1] again"


def test_unknown_label_left_intact():
    spans = [Span("something_new", 0, 5, "Alice")]
    out = apply_placeholders("Alice here", spans, ALL_CATEGORIES)
    assert out.text == "Alice here"


def test_resolve_categories():
    assert resolve_categories() == DEFAULT_CATEGORIES
    assert resolve_categories(strict=True) == ALL_CATEGORIES
    assert resolve_categories(mask={"email"}) == frozenset({"email"})
    assert resolve_categories(strict=True, allow={"date"}) == ALL_CATEGORIES - {"date"}
    with pytest.raises(ValueError, match="Unknown categories"):
        resolve_categories(mask={"ssn"})
