# Improvement ideas

Roughly ordered by value-for-effort. Nothing here is scheduled; this is a
backlog of directions that came up during development.

## Detection quality

- **Context-keyword detector for reference numbers.** The remaining leak on
  the test invoice: `Klantnr: 266243`. Bare digit runs can't be masked
  blindly, but a keyword-proximity rule can — `(klantnr|klantnummer|lidnr|
  dossiernr|mandaatref\w*|referentie)\s*[:.]?\s*(\|?\s*)?\d{4,14}` masks the
  number only when an identifying label precedes it (also across a markdown
  table cell boundary).
- **Postcode + municipality with context.** `9040 Sint-Amandsberg` is
  currently kept because 4-digit postcodes collide with years. Masking only
  when it directly follows a masked street span would close this without
  false positives.
- **Belgian ondernemingsnummer / BTW** (`BE 0xxx.xxx.xxx`, mod-97-validatable)
  as an opt-in category — it identifies sole proprietors (eenmanszaken),
  where the enterprise number *is* personal data.
- **More country packs.** The Belgian detectors are one file; Dutch BSN
  (11-proef), German Steuer-ID, French NIR all follow the same
  pattern-plus-checksum recipe. pii-core's Polish detectors (PESEL, NIP,
  REGON) could simply be enabled for Polish documents.
- **Presidio as an opt-in breadth layer** (`safeingest[presidio]`, via
  pii-toolkit's `pii-presidio` plugin): dozens of country-specific
  recognizers (US SSN, passports, crypto wallets) for multi-jurisdiction
  ingestion. Kept out of core deliberately — heavy spaCy stack, third engine
  to reconcile, and its NER is weaker than the opf model already in place.
- **Fine-tune privacy-filter on Dutch/Belgian documents.** opf ships a
  training CLI (`opf train`). A few hundred annotated Belgian invoices,
  contracts, and letters would likely fix the model's address misses at the
  source instead of patching around them.

## Verification & trust

- ~~**Second-pass self-check**~~ — **implemented**: detection re-runs on the
  sanitized output by default; residual hits warn on stderr and appear as
  `self_check_residual` in `--report`. `--check` gates (no output, exit 3).
  Follow-up idea: an auto-remediation loop that masks residuals and
  re-checks until a fixed point, instead of only flagging.
- **Evaluation corpus:** a set of synthetic documents (invoice, CV, medical
  letter, email thread — per language) with known PII annotations, scored in
  CI for precision/recall per category. Guards against regressions when
  detectors change.

## Reversibility

- **`pii-veil`-style mapping file** (pii-toolkit has a library for exactly
  this): optionally write an encrypted `placeholder → original` mapping next
  to the output, so a *trusted local* post-processing step can re-insert real
  values into LLM answers ("write a reply to [NAME_1]" → letter addressed to
  the real person). The mapping must never travel with the sanitized text.

## Pipeline & UX

- **Chunking for large documents:** opf has a context window; very long
  markdown should be windowed with overlap and the spans stitched, keeping
  placeholder numbering global across chunks.
- **Batch mode:** `safeingest *.pdf -d out/` for folder ingestion in one
  model load (model init dominates single-file latency).
- **Structured formats:** for XLSX/CSV, per-cell redaction (markitdown
  flattens tables to text first; column-aware masking, e.g. presidio-structured,
  would be more precise).
- **Image-only PDFs / scans:** wire up OCR (markitdown supports it) and
  document the accuracy caveat — OCR errors degrade PII detection.
- **MCP server** exposing `ingest_document`, so non-Claude-Code clients
  (or claude.ai remote sessions) can use the same pipeline.
- **Quieter GPU startup:** first CUDA run compiles a triton helper and prints
  compiler noise to stderr; capture it so `--report` output stays clean.

## Packaging

- **Publish to PyPI** (`pip install safeingest`), removing the git-dependency
  wart — opf itself isn't on PyPI, which currently blocks a clean sdist;
  vendoring or an extras split would solve it.
- **Tagged releases** so `gh skill install` resolves a stable version instead
  of `main` HEAD.
- **CPU-only torch extra** (`safeingest[cpu]`) to spare non-GPU machines the
  multi-GB CUDA wheel download.
