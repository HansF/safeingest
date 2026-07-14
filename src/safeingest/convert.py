"""Document-to-markdown conversion via microsoft/markitdown."""

from __future__ import annotations

import io
import sys


def to_markdown(source: str) -> str:
    """Convert a local file path, URL, or '-' (stdin bytes) to markdown text."""
    from markitdown import MarkItDown

    md = MarkItDown(enable_plugins=False)
    if source == "-":
        result = md.convert_stream(io.BytesIO(sys.stdin.buffer.read()))
    else:
        result = md.convert(source)
    return result.text_content
