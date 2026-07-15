"""Precision/recall regression test over the hand-authored evaluation corpus.

Implements the "evaluation corpus" idea from docs/improvement-ideas.md:
synthetic Belgian documents (invoice, CV, medical referral, email thread) in
NL/FR with known PII annotations, scored per category so a regression in
patterns.py shows up as a failing threshold instead of shipping silently.

Scores the regex layer only (find_pattern_spans) -- the opf neural layer
covers "name"/"secret"/"url"/"date" and isn't exercised by this corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation import CategoryScore, aggregate, score_document
from safeingest.patterns import find_pattern_spans

FIXTURES = Path(__file__).parent / "fixtures" / "eval_corpus"
DOC_NAMES = sorted(p.stem for p in FIXTURES.glob("*.md"))

# Checksum-backed categories must be found with (near-)perfect recall.
# BE_ADDRESS is shape-only by design (no checksum) so it gets a looser bar.
MIN_RECALL = {
    "email": 1.0,
    "account": 1.0,
    "rrn": 1.0,
    "phone": 1.0,
    "address": 0.9,
}
MIN_PRECISION = {
    "email": 1.0,
    "account": 1.0,
    "rrn": 1.0,
    "phone": 0.9,  # RRNs can spuriously overlap phone shape before merge; merge resolves most
    "address": 0.5,  # deliberately over-matching detector, see patterns.py
}


def _load(name: str):
    text = (FIXTURES / f"{name}.md").read_text(encoding="utf-8")
    ground_truth = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return text, ground_truth


@pytest.mark.parametrize("name", DOC_NAMES)
def test_document_hits_minimum_recall(name):
    text, ground_truth = _load(name)
    scores = score_document(find_pattern_spans(text), ground_truth)
    failures = [
        f"{cat}: recall={s.recall:.2f} (tp={s.tp} fn={s.fn})"
        for cat, s in scores.items()
        if s.recall < MIN_RECALL.get(cat, 1.0)
    ]
    assert not failures, f"{name}: recall below threshold -> {failures}"


def test_corpus_aggregate_precision_recall_report():
    assert DOC_NAMES, "no documents found in tests/fixtures/eval_corpus"
    all_scores = []
    for name in DOC_NAMES:
        text, ground_truth = _load(name)
        all_scores.append(score_document(find_pattern_spans(text), ground_truth))

    total = aggregate(all_scores)
    print("\nPII evaluation corpus -- aggregate scores by category:")
    print(f"{'category':10s} {'precision':>10s} {'recall':>8s} {'f1':>6s} {'tp':>4s} {'fp':>4s} {'fn':>4s}")
    for cat in sorted(total):
        s: CategoryScore = total[cat]
        print(f"{cat:10s} {s.precision:10.2f} {s.recall:8.2f} {s.f1:6.2f} {s.tp:4d} {s.fp:4d} {s.fn:4d}")

    failures = []
    for cat, s in total.items():
        min_r = MIN_RECALL.get(cat, 1.0)
        min_p = MIN_PRECISION.get(cat, 1.0)
        if s.recall < min_r:
            failures.append(f"{cat}: recall {s.recall:.2f} < {min_r}")
        if s.precision < min_p:
            failures.append(f"{cat}: precision {s.precision:.2f} < {min_p}")
    assert not failures, "\n".join(failures)
