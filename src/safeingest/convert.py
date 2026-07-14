"""Document-to-markdown conversion via microsoft/markitdown."""

from __future__ import annotations

import io
import re
import sys

# PDF extraction leaves invisible characters (NBSP between IBAN digit groups,
# soft hyphens inside words) that break both regex and model detection.
# Normalizing BEFORE detection keeps all span offsets consistent.
_UNICODE_SPACES = re.compile("[\\u00a0\\u1680\\u2000-\\u200a\\u202f\\u205f\\u3000]")
_INVISIBLES = re.compile("[\\u00ad\\u200b-\\u200d\\u2060\\ufeff]")


def normalize(text: str) -> str:
    return _INVISIBLES.sub("", _UNICODE_SPACES.sub(" ", text))


def to_markdown(source: str) -> str:
    """Convert a local file path, URL, or '-' (stdin bytes) to markdown text."""
    from markitdown import MarkItDown

    md = MarkItDown(enable_plugins=False)
    if source == "-":
        result = md.convert_stream(io.BytesIO(sys.stdin.buffer.read()))
    else:
        result = md.convert(source)
    return normalize(result.text_content)
