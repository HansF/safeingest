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
    # Suspected leaks: detections that still fire on the sanitized output.
    # None means the self-check was skipped; {} means it ran clean.
    residual: dict[str, int] | None = None


def ingest(
    source: str,
    *,
    categories: frozenset[str],
    device: str | None = None,
    self_check: bool = True,
) -> IngestResult:
    try:
        raw = to_markdown(source)
    except Exception as exc:
        raise SafeIngestError(f"conversion failed for {source!r}: {exc}") from exc

    redactor = Redactor(device=device)
    try:
        outcome: RedactionOutcome = redactor.redact(raw, categories)
        residual = redactor.self_check(outcome.text, categories) if self_check else None
    except Exception as exc:
        # Fail closed: never fall back to emitting the unredacted markdown.
        raise SafeIngestError(f"PII redaction failed, no output produced: {exc}") from exc

    return IngestResult(
        markdown=outcome.text,
        counts=outcome.counts,
        detected_not_masked=outcome.detected_not_masked,
        warning=outcome.warning,
        residual=residual,
    )
