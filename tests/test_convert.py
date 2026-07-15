"""Integration tests for convert.py -- previously zero coverage.

Exercises the real markitdown call (no mocking) against the fixtures already
in tests/fixtures/ (sample.html, sample.md), which existed unused by any test
until now, plus normalize() unit coverage for the invisible-character corpus.
"""

from __future__ import annotations

from pathlib import Path

from safeingest.convert import normalize, to_markdown
from safeingest.patterns import find_pattern_spans

FIXTURES = Path(__file__).parent / "fixtures"


def test_html_fixture_converts_to_markdown_with_heading():
    text = to_markdown(str(FIXTURES / "sample.html"))
    assert text.startswith("# Quarterly Review")
    assert "jan.peeters@acme.be" in text
    assert "BE71 0961 2345 6769" in text


def test_markdown_fixture_passes_through():
    text = to_markdown(str(FIXTURES / "sample.md"))
    assert text.startswith("# Quarterly Review")
    assert "Maria Gonzalez" in text


def test_to_markdown_output_is_already_normalized():
    """convert.to_markdown applies normalize() internally; a document with
    invisible characters should come out clean and detectable."""
    text = to_markdown(str(FIXTURES / "sample.html"))
    assert find_pattern_spans(text)  # IBAN etc. still detectable post-normalize


def test_normalize_strips_nbsp_and_soft_hyphens():
    dirty = "IBAN: BE18 3632 2574 0965 Sint­Amandsberg"
    clean = normalize(dirty)
    assert " " not in clean
    assert "­" not in clean
    assert clean == "IBAN: BE18 3632 2574 0965 SintAmandsberg"


def test_normalize_strips_zero_width_and_bom():
    dirty = "email​@‌example.com﻿"
    assert normalize(dirty) == "email@example.com"


def test_normalize_is_idempotent():
    dirty = "BE18 3632­2574​0965"
    once = normalize(dirty)
    assert normalize(once) == once
