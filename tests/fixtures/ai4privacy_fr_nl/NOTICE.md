# Provenance and license — `subset.jsonl`

**Source dataset:** [`ai4privacy/open-pii-masking-500k-ai4privacy`](https://huggingface.co/datasets/ai4privacy/open-pii-masking-500k-ai4privacy)
(HuggingFace Hub, `train` split, 464,150 rows).

**License:** CC-BY-4.0, as declared by the dataset card. The dataset's
`source_text` values were themselves generated with Llama 3.1/3.3, so the
Llama Community License's attribution term ("Built with Llama") also applies
to this derived data alongside CC-BY-4.0.

**Why vendored instead of downloaded in CI:** this repo has no network
dependency in its test suite otherwise; freezing a small subset keeps tests
deterministic and offline while still exercising the regex layer against
real-world (LLM-generated but human-review-style) French/Dutch sentence
structure that hand-authored fixtures can't fully approximate.

**Selection parameters** (reproducible from the public dataset with the
`datasets` library):

1. Filter to `language in {"fr", "nl"}` → 110,951 rows.
2. Filter to rows whose `privacy_mask` contains at least one entity labeled
   `EMAIL`, `TELEPHONENUM`, or `CREDITCARDNUMBER` — the only entity types
   SafeIngest's regex layer (`patterns.py`) can plausibly detect; the
   dataset's `GIVENNAME`/`SURNAME`/`CITY`/`STREET`/etc. labels are the neural
   (`opf`) layer's job, not the regex layer's, so rows without a
   regex-relevant entity add no signal here → 29,540 rows.
3. Sort by `uid` ascending (deterministic ordering) within each language,
   then take the first 100 `nl` rows and first 150 `fr` rows → 250 rows.
4. Per row, keep only `uid`, `language`, `region`, `source_text`, and the
   `privacy_mask` entries whose `label` is one of the three relevant types
   (other entity spans, e.g. names/cities, are dropped — not used by any
   test here).

**Row count:** 250 (100 `nl`, 150 `fr`). Entity counts: 131 `TELEPHONENUM`,
128 `EMAIL`, 34 `CREDITCARDNUMBER`.

**Known, expected low recall:** `TELEPHONENUM` values in this dataset are
generic French/Dutch phone numbers, not exclusively Belgian. SafeIngest's
`BE_PHONE` detector only matches Belgian shapes by design (see
`docs/how-it-works.md`), so low recall on `TELEPHONENUM` here is expected and
documents a real, known limitation rather than a bug — see
`tests/test_ai4privacy_regression.py` for the threshold this is scored
against.

To regenerate or resample this subset, see the script recorded in this
repo's implementation history for `tests/test_ai4privacy_regression.py`
(not re-run automatically — vendoring is a one-time, human-triggered step).
