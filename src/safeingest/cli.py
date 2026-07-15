"""safeingest CLI: sanitized markdown to stdout (or -o), PII never printed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .redact import ALL_CATEGORIES, DEFAULT_CATEGORIES, resolve_categories


def _category_set(value: str) -> set[str]:
    return {c.strip().lower() for c in value.split(",") if c.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safeingest",
        description=(
            "Convert a document to markdown (markitdown) and mask PII with a local "
            "model (openai/privacy-filter) before any LLM reads it. "
            f"Categories: {', '.join(sorted(ALL_CATEGORIES))}. "
            f"Masked by default: {', '.join(sorted(DEFAULT_CATEGORIES))}."
        ),
    )
    parser.add_argument("source", help="file path, URL, or '-' for stdin")
    parser.add_argument("-o", "--output", type=Path, help="write sanitized markdown to this file instead of stdout")
    parser.add_argument("--strict", action="store_true", help="also mask urls and dates (all categories)")
    parser.add_argument("--mask", type=_category_set, metavar="CAT,..", help="mask exactly these categories")
    parser.add_argument("--allow", type=_category_set, metavar="CAT,..", help="never mask these categories")
    parser.add_argument("--report", action="store_true", help="print a JSON redaction summary (counts only) to stderr")
    parser.add_argument("--device", choices=["cpu", "cuda"], help="inference device (default: auto-detect)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="gate on the self-check: if residual PII is detected in the sanitized "
        "output, emit nothing and exit 3",
    )
    parser.add_argument(
        "--no-self-check",
        action="store_true",
        help="skip re-running detection on the sanitized output (faster, less safe)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        categories = resolve_categories(strict=args.strict, mask=args.mask, allow=args.allow)
    except ValueError as exc:
        print(f"safeingest: {exc}", file=sys.stderr)
        return 2

    if args.check and args.no_self_check:
        print("safeingest: --check requires the self-check; drop --no-self-check", file=sys.stderr)
        return 2

    from .pipeline import SafeIngestError, ingest

    try:
        result = ingest(
            args.source,
            categories=categories,
            device=args.device,
            self_check=not args.no_self_check,
        )
    except SafeIngestError as exc:
        print(f"safeingest: {exc}", file=sys.stderr)
        return 1

    if result.residual:
        detail = ", ".join(f"{cat}: {n}" for cat, n in sorted(result.residual.items()))
        print(
            f"safeingest: self-check found {sum(result.residual.values())} suspected "
            f"residual PII span(s) in the sanitized output ({detail})",
            file=sys.stderr,
        )
        if args.check:
            print("safeingest: --check active, no output emitted (exit 3)", file=sys.stderr)
            _print_report(args, result, categories, wrote_output=False)
            return 3

    if args.output:
        args.output.write_text(result.markdown, encoding="utf-8")
    else:
        sys.stdout.write(result.markdown)
        if result.markdown and not result.markdown.endswith("\n"):
            sys.stdout.write("\n")

    _print_report(args, result, categories, wrote_output=True)
    return 0


def _print_report(args, result, categories, *, wrote_output: bool) -> None:
    if not args.report:
        return
    report = {
        "masked_categories": sorted(categories),
        "masked_spans": result.counts,
        "detected_but_allowed": result.detected_not_masked,
    }
    if result.residual is not None:
        report["self_check_residual"] = result.residual
    if result.warning:
        report["warning"] = result.warning
    if args.output and wrote_output:
        report["output"] = str(args.output)
    print(json.dumps(report, indent=2), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
