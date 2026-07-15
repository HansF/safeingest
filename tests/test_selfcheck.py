"""Second-pass self-check: re-detect on sanitized output, flag residual PII."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from safeingest import cli, pipeline
from safeingest.redact import DEFAULT_CATEGORIES, Redactor, residual_counts

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class Span:
    label: str
    start: int
    end: int
    text: str
    placeholder: str = ""


class TestResidualCounts:
    def test_leak_in_active_category_counted(self):
        text = "Contact [NAME_1] or Maria directly."
        spans = [Span("private_person", 20, 25, "Maria")]
        assert residual_counts(text, spans, DEFAULT_CATEGORIES) == {"name": 1}

    def test_detection_overlapping_placeholder_ignored(self):
        text = "Contact [NAME_1] please."
        spans = [Span("private_person", 8, 16, "[NAME_1]")]
        assert residual_counts(text, spans, DEFAULT_CATEGORIES) == {}

    def test_allowed_category_not_a_leak(self):
        text = "Meeting on 2024-01-02."
        spans = [Span("private_date", 11, 21, "2024-01-02")]
        assert residual_counts(text, spans, DEFAULT_CATEGORIES) == {}
        assert residual_counts(text, spans, frozenset({"date"})) == {"date": 1}


@dataclass
class _FakeOpfResult:
    text: str
    detected_spans: list = field(default_factory=list)
    warning: str | None = None


class _LeakyOpf:
    """Misses 'Maria' on the first pass; the self-check pass then finds it —
    simulating a model miss that the second pass catches."""

    def __init__(self):
        self.calls = 0

    def redact(self, text):
        self.calls += 1
        if self.calls == 1:
            return _FakeOpfResult(text=text)
        i = text.find("Maria")
        spans = [Span("private_person", i, i + 5, "Maria")] if i >= 0 else []
        return _FakeOpfResult(text=text, detected_spans=spans)


@pytest.fixture
def leaky_opf(monkeypatch):
    fake = _LeakyOpf()
    monkeypatch.setattr(Redactor, "_load", lambda self: fake)
    return fake


@pytest.fixture
def leaky_doc(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Notes\n\nMaria called about the delivery.\n")
    return doc


def test_pipeline_reports_residual(leaky_opf, leaky_doc):
    result = pipeline.ingest(str(leaky_doc), categories=DEFAULT_CATEGORIES)
    assert result.residual == {"name": 1}
    assert "Maria" in result.markdown  # first pass missed it; only flagged, not masked


def test_pipeline_skips_self_check_when_disabled(leaky_opf, leaky_doc):
    result = pipeline.ingest(str(leaky_doc), categories=DEFAULT_CATEGORIES, self_check=False)
    assert result.residual is None
    assert leaky_opf.calls == 1


def test_pipeline_residual_empty_when_clean(monkeypatch, tmp_path):
    class _CleanOpf:
        def redact(self, text):
            return _FakeOpfResult(text=text)

    monkeypatch.setattr(Redactor, "_load", lambda self: _CleanOpf())
    doc = tmp_path / "doc.md"
    doc.write_text("Mail jan@acme.be please.\n")
    result = pipeline.ingest(str(doc), categories=DEFAULT_CATEGORIES)
    assert "[EMAIL_1]" in result.markdown  # regex layer masked it in pass 1
    assert result.residual == {}  # and pass 2 found nothing left


def test_cli_check_gates_with_exit_3(leaky_opf, leaky_doc, tmp_path, capsys):
    out = tmp_path / "out.safe.md"
    rc = cli.main([str(leaky_doc), "-o", str(out), "--check", "--report"])
    captured = capsys.readouterr()
    assert rc == 3
    assert not out.exists()  # gated: nothing emitted
    assert captured.out == ""
    assert "self-check found 1 suspected residual" in captured.err
    assert '"self_check_residual"' in captured.err
    assert '"output"' not in captured.err  # no file was written


def test_cli_warns_but_emits_without_check(leaky_opf, leaky_doc, tmp_path, capsys):
    out = tmp_path / "out.safe.md"
    rc = cli.main([str(leaky_doc), "-o", str(out)])
    captured = capsys.readouterr()
    assert rc == 0
    assert out.exists()
    assert "suspected residual" in captured.err


def test_cli_check_conflicts_with_no_self_check(capsys):
    rc = cli.main(["whatever.md", "--check", "--no-self-check"])
    assert rc == 2
    assert "requires the self-check" in capsys.readouterr().err
