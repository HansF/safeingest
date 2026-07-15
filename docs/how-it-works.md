# How SafeIngest works

SafeIngest exists so an LLM can work with a sensitive document without the
personal data in it ever entering the model's context. Everything below runs
locally; no document content leaves the machine.

## Pipeline

```
 document (PDF/DOCX/XLSX/PPTX/HTML/CSV/image/URL/stdin)
    │
    ▼
 1. Convert          markitdown → markdown text        (convert.py)
    │
    ▼
 2. Normalize        strip invisible unicode           (convert.py)
    │
    ▼
 3. Detect ── model  openai/privacy-filter spans       (redact.py)
    │     └── regex  pii-core + Belgian detectors      (patterns.py)
    ▼
 4. Mask             typed numbered placeholders       (redact.py)
    │
    ▼
 sanitized markdown + JSON report (counts only, never values)
```

### 1. Convert — `convert.py`

[microsoft/markitdown](https://github.com/microsoft/markitdown) turns the
input into markdown, preserving headings, tables, and lists. Sources can be a
file path, a URL, or `-` for stdin bytes.

### 2. Normalize — `convert.py`

PDF extraction leaves invisible characters that hide PII from detection: the
test invoice had its IBAN written with non-breaking spaces (U+00A0) between
digit groups and soft hyphens (U+00AD) inside words. Both the regex layer and
the neural model missed identifiers because of them. `normalize()` maps every
Unicode space separator to a plain space and deletes soft hyphens,
zero-width characters, and BOMs — *before* detection, so every span offset
downstream refers to the same normalized text.

### 3. Detect — two independent layers

**Neural layer** (`redact.py`): [openai/privacy-filter](https://github.com/openai/privacy-filter),
a 1.5B-parameter (50M active) bidirectional token classifier with constrained
Viterbi decoding. It detects 8 labels: `private_person`, `private_email`,
`private_phone`, `private_address`, `account_number`, `secret`, `private_url`,
`private_date`. Weights download once to `~/.opf/privacy_filter`; inference
runs on CUDA when available, CPU otherwise. This layer handles the fuzzy
categories no regex can: names, free-form addresses, novel secrets.

**Deterministic layer** (`patterns.py`): structured identifiers are rigidly
formatted and checksum-verifiable, so patterns catch them with full recall
where the model can miss (mangled invoice tables, unusual layouts). Built on
[pii-toolkit/pii-core](https://github.com/pii-toolkit/pii-core):

| Detector | Source | Validation |
|---|---|---|
| Email | pii-core `EmailDetector` | — |
| Credit card | pii-core `CreditCardDetector` | Luhn |
| IBAN (any country) | ours, on pii-core's checksum | mod-97 + SWIFT length registry |
| Belgian rijksregisternummer / INSZ | ours | official modulo-97 check, incl. bis-numbers (month +20/+40) and the +2 000 000 000 rule for births ≥ 2000 |
| Belgian phone | ours | digit-count rules (+32/0032/national; 10-digit must be 04xx mobile, which also rejects enterprise numbers) |
| Belgian street address | ours | Dutch street-suffix + house-number shape, French rue/avenue/… prefix shape |

Design bias: when in doubt, over-redact. A false positive costs a little
readability; a false negative is a leak.

### 4. Mask — `redact.py`

Both span lists merge and sort by position (longest span wins on ties).
Every span label maps to a user-facing category:

`name, email, phone, address, account, secret, rrn` — masked by default
`url, date` — masked only with `--strict` or `--mask` (they usually carry the
document's meaning, not personal identity)

Replacements are typed and numbered: `[NAME_1]`, `[ACCOUNT_3]`. The same
surface text (case-insensitive) within a category always gets the same
number, so an LLM can track entities across the document — "[NAME_1] emailed
[NAME_2], then [NAME_1] replied" stays coherent without revealing anyone.

### Fail closed

If conversion or redaction throws, the pipeline raises and emits **nothing**.
There is no code path that outputs unredacted text on failure. The `--report`
JSON contains per-category counts only, never the detected values.

## The agent skill

`skills/safeingest/SKILL.md` (installable with
`gh skill install HansF/safeingest --agent claude-code --scope user`) teaches
a coding agent the contract: never open the original document with any tool,
run `safeingest`, read only the sanitized output, and report failures instead
of falling back to the original.

## Known limitations

Observed on a real Belgian invoice during development:

- **Bare reference numbers** (customer number, invoice number) are not masked:
  a short digit run has no checksum or shape to validate, and masking every
  number would destroy amounts, quantities, and dates.
- **City/postcode-only mentions** are not matched by the address detector —
  Belgian postcodes are 4 digits and collide with years.
- The neural model can miss unusual names, regional conventions, and novel
  secret formats (see the upstream privacy-filter README). The layers are
  complementary, not perfect: **for high-sensitivity documents, skim the
  sanitized output before sharing it.**
