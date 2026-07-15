"""Integration tests for pipeline.py -- previously zero coverage.

Redactor._load is monkeypatched to a fake opf model (returns no spans) so
these stay fast and torch-free while still exercising the real wiring:
convert -> regex layer -> placeholder masking -> fail-closed on exception.
The regex layer itself (patterns.py) runs unmocked, so IBAN/RRN/etc. in the
fixtures are still genuinely detected and masked here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from safeingest import pipeline
from safeingest.redact import DEFAULT_CATEGORIES, Redactor, resolve_categories

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class _FakeOpfResult:
    text: str
    detected_spans: list = None
    warning: str | None = None

    def __post_init__(self):
        if self.detected_spans is None:
            self.detected_spans = []


class _FakeOpf:
    def redact(self, text):
        return _FakeOpfResult(text=text)


@pytest.fixture(autouse=True)
def stub_opf(monkeypatch):
    monkeypatch.setattr(Redactor, "_load", lambda self: _FakeOpf())


def test_ingest_masks_regex_detected_pii_from_html_fixture():
    result = pipeline.ingest(
        str(FIXTURES / "sample.html"), categories=DEFAULT_CATEGORIES
    )
    assert "jan.peeters@acme.be" not in result.markdown
    assert "BE71 0961 2345 6769" not in result.markdown
    assert "[EMAIL_1]" in result.markdown
    assert "[ACCOUNT_1]" in result.markdown
    assert result.counts.get("email") == 1
    assert result.counts.get("account") == 1


def test_ingest_respects_allow_list():
    categories = resolve_categories(allow={"email"})
    result = pipeline.ingest(str(FIXTURES / "sample.html"), categories=categories)
    assert "jan.peeters@acme.be" in result.markdown
    assert "email" not in result.counts


def test_ingest_fails_closed_on_conversion_error(monkeypatch):
    def _boom(source):
        raise RuntimeError("corrupt file")

    monkeypatch.setattr(pipeline, "to_markdown", _boom)
    with pytest.raises(pipeline.SafeIngestError, match="conversion failed"):
        pipeline.ingest("nonexistent.pdf", categories=DEFAULT_CATEGORIES)


def test_ingest_fails_closed_on_redaction_error(monkeypatch):
    def _boom(self, text, categories):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(Redactor, "redact", _boom)
    with pytest.raises(pipeline.SafeIngestError, match="PII redaction failed"):
        pipeline.ingest(str(FIXTURES / "sample.html"), categories=DEFAULT_CATEGORIES)


def test_ingest_never_returns_unredacted_text_on_failure(monkeypatch):
    """Fail-closed guarantee: an exception during redaction must not leak
    the converted-but-unredacted markdown anywhere in the raised error path."""

    def _boom(self, text, categories):
        raise RuntimeError("boom")

    monkeypatch.setattr(Redactor, "redact", _boom)
    try:
        pipeline.ingest(str(FIXTURES / "sample.html"), categories=DEFAULT_CATEGORIES)
    except pipeline.SafeIngestError as exc:
        assert "jan.peeters@acme.be" not in str(exc)
    else:
        pytest.fail("expected SafeIngestError")
