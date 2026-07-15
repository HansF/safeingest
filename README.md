# SafeIngest

[![test](https://github.com/HansF/safeingest/actions/workflows/test.yml/badge.svg)](https://github.com/HansF/safeingest/actions/workflows/test.yml)

PII-safe document ingestion for LLMs. Converts any document to Markdown with
[microsoft/markitdown](https://github.com/microsoft/markitdown), then masks
personal information locally — with the
[openai/privacy-filter](https://github.com/openai/privacy-filter) neural model
*and* a deterministic checksum-validated regex layer — before the text ever
reaches an LLM. Everything runs on your machine — no document content leaves it.

```
Prepared by Jan Peeters (jan.peeters@acme.be,      Prepared by [NAME_1] ([EMAIL_1], [PHONE_1]).
+32 478 12 34 56). Customer Maria Gonzalez    →    Customer [NAME_2] lives at [ADDRESS_1].
lives at Kerkstraat 12, 9000 Gent. Payment         Payment to IBAN [ACCOUNT_1] confirmed
to IBAN BE71 0961 2345 6769 confirmed on            on 2024-03-15.
2024-03-15.
```

## Usage

```bash
safeingest report.pdf                      # sanitized markdown to stdout
safeingest report.pdf -o report.safe.md    # ... to a file
safeingest https://example.com/page        # URLs work too
cat file.docx | safeingest -               # stdin
safeingest scan.pdf --strict               # also mask urls + dates
safeingest scan.pdf --mask email,phone     # mask only these
safeingest scan.pdf --allow name --report  # keep names, print JSON summary to stderr
safeingest scan.pdf --device cpu           # force CPU inference
```

Input formats: PDF, DOCX, PPTX, XLSX/XLS, Outlook MSG, HTML, CSV, JSON, XML,
Markdown, plain text, URLs, stdin — anything markitdown converts.

`--report` prints a JSON summary to stderr with **counts only, never values**:

```json
{
  "masked_categories": ["account", "address", "email", "name", "phone", "rrn", "secret"],
  "masked_spans": {"name": 2, "email": 1, "account": 7},
  "detected_but_allowed": {"date": 6}
}
```

## How it detects

Two independent layers (see [docs/how-it-works.md](docs/how-it-works.md)):

1. **Neural**: openai/privacy-filter, a 1.5B-parameter (50M active) local
   token classifier — handles names, free-form addresses, secrets.
2. **Deterministic**: regex + checksum detectors built on
   [pii-toolkit/pii-core](https://github.com/pii-toolkit/pii-core) —
   IBANs (mod-97 + SWIFT registry, any country), Luhn credit cards, emails,
   and Belgian identifiers: rijksregisternummer/INSZ (official modulo-97
   check incl. bis-numbers and post-2000 births), phone numbers, and street
   addresses. Full recall on structured identifiers the model can miss.

Markdown is Unicode-normalized before detection, so invisible PDF artifacts
(non-breaking spaces, soft hyphens) can't hide identifiers from either layer.

Categories: `name`, `email`, `phone`, `address`, `account`, `secret`, `rrn`
(masked by default) plus `url`, `date` (masked only with `--strict`/`--mask`).

PII is replaced by typed, numbered placeholders — `[NAME_1]`, `[EMAIL_2]` —
stable per unique value, so an LLM can still follow who did what.

The pipeline **fails closed**: if redaction cannot run, nothing is emitted.

## Install

```bash
uv tool install "safeingest @ git+https://github.com/HansF/safeingest"
# or from a local checkout:
uv tool install --editable .
# or one-shot without installing (Linux/macOS/Windows):
uvx --python 3.12 --from git+https://github.com/HansF/safeingest safeingest <file>
```

No `uv`? Get it with `curl -LsSf https://astral.sh/uv/install.sh | sh`
(Linux/macOS) or `winget install astral-sh.uv` (Windows). Python 3.10–3.12 is
required (torch constraint) — `--python 3.12` makes uv fetch it automatically.

First run downloads the privacy-filter checkpoint (~1.5B params, MoE with 50M
active) to `~/.opf/privacy_filter`; it runs on GPU when available, CPU otherwise.

## Agent skill

The repo ships an [Agent Skill](https://agentskills.io/specification) at
`skills/safeingest/SKILL.md` that teaches a coding agent to route sensitive
documents through this tool and read only the sanitized output — never the
original. Install it for your agent of choice with the GitHub CLI:

```bash
gh skill install HansF/safeingest --agent claude-code --scope user
# other agents: --agent github-copilot | cursor | codex | gemini-cli | ...
```

## Development

```bash
uv sync --group dev
uv run pytest            # full suite
uv run pytest -m "not slow"   # what CI runs (no torch/opf needed)
```

The suite covers placeholder logic, category resolution, every regex detector
(including property-based tests: hundreds of Faker-generated IBANs/RRNs plus
checksum-mutation rejection), Unicode normalization, and the fail-closed
pipeline wiring with a mocked model. CI runs it torch-free on every push.

## Caveat

Detection is layered but not guaranteed (unusual names, novel secret formats,
and regional conventions can slip past the model; bare reference numbers have
no shape to match). For high-sensitivity documents, review the sanitized
output before sharing it. See
[known limitations](docs/how-it-works.md#known-limitations) and the
[improvement backlog](docs/improvement-ideas.md).
