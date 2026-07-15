"""Precision/recall scoring for the PII evaluation corpus (tests/fixtures/eval_corpus).

Mirrors the overlap-resolution rule in redact.apply_placeholders (longest
span wins when candidates start at/before the same offset) so scores reflect
what the real pipeline would actually redact, not raw unmerged detector
output.
"""

from __future__ import annotations

from dataclasses import dataclass

from safeingest.redact import LABEL_TO_CATEGORY


def merge_overlapping(spans):
    winners = []
    cursor = 0
    for span in sorted(spans, key=lambda s: (s.start, s.start - s.end)):
        if span.start < cursor:
            continue
        winners.append(span)
        cursor = span.end
    return winners


@dataclass
class CategoryScore:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def score_document(spans, ground_truth: list[dict]) -> dict[str, CategoryScore]:
    """``ground_truth``: list of ``{"category": str, "text": str}`` dicts."""
    merged = merge_overlapping(spans)
    detected = [
        (LABEL_TO_CATEGORY.get(s.label), s.text.strip())
        for s in merged
        if LABEL_TO_CATEGORY.get(s.label) is not None
    ]
    truth = [(g["category"], g["text"].strip()) for g in ground_truth]

    scores: dict[str, CategoryScore] = {
        cat: CategoryScore() for cat in {c for c, _ in detected} | {c for c, _ in truth}
    }

    remaining_detected = list(detected)
    for item in list(truth):
        if item in remaining_detected:
            remaining_detected.remove(item)
            scores[item[0]].tp += 1
        else:
            scores[item[0]].fn += 1
    for cat, _ in remaining_detected:
        scores[cat].fp += 1
    return scores


def aggregate(all_scores: list[dict[str, CategoryScore]]) -> dict[str, CategoryScore]:
    total: dict[str, CategoryScore] = {}
    for doc_scores in all_scores:
        for cat, s in doc_scores.items():
            agg = total.setdefault(cat, CategoryScore())
            agg.tp += s.tp
            agg.fp += s.fp
            agg.fn += s.fn
    return total
