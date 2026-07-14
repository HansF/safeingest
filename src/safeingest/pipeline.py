"""Convert -> redact pipeline. Fails closed: no unredacted text ever leaves here."""

from __future__ import annotations

from dataclasses import dataclass

from .convert import to_markdown
from .redact import RedactionOutcome, Redactor


class SafeIngestError(Exception):
    """Raised when the pipeline cannot produce a sanitized document."""


@dataclass
class IngestResult:
    markdown: str
    counts: dict[str, int]
    detected_not_masked: dict[str, int]
    warning: str | None


def ingest(source: str, *, categories: frozenset[str], device: str | None = None) -> IngestResult:
    try:
        raw = to_markdown(source)
    except Exception as exc:
        raise SafeIngestError(f"conversion failed for {source!r}: {exc}") from exc

    try:
        outcome: RedactionOutcome = Redactor(device=device).redact(raw, categories)
    except Exception as exc:
        # Fail closed: never fall back to emitting the unredacted markdown.
        raise SafeIngestError(f"PII redaction failed, no output produced: {exc}") from exc

    return IngestResult(
        markdown=outcome.text,
        counts=outcome.counts,
        detected_not_masked=outcome.detected_not_masked,
        warning=outcome.warning,
    )
