# SafeIngest

PII-safe document ingestion for LLMs. Converts any document to Markdown with
[microsoft/markitdown](https://github.com/microsoft/markitdown), then masks
personal information locally with
[openai/privacy-filter](https://github.com/openai/privacy-filter) before the
text ever reaches an LLM. Everything runs on your machine — no document
content leaves it.

## Usage

```bash
safeingest report.pdf                      # sanitized markdown to stdout
safeingest report.pdf -o report.safe.md    # ... to a file
safeingest https://example.com/page        # URLs work too
cat file.docx | safeingest -               # stdin
safeingest scan.pdf --strict               # also mask urls + dates
safeingest scan.pdf --mask email,phone     # mask only these
safeingest scan.pdf --allow name --report  # keep names, print JSON summary to stderr
```

Categories: `name`, `email`, `phone`, `address`, `account`, `secret`, `rrn`
(masked by default) plus `url`, `date` (masked only with `--strict`/`--mask`).

Detection is two layers deep: the neural model, plus a deterministic regex
pass built on [pii-toolkit/pii-core](https://github.com/pii-toolkit/pii-core)
(checksum-validated IBANs, Luhn credit cards, emails) extended with Belgian
identifiers — rijksregisternummer/INSZ (official modulo-97 check, incl.
bis-numbers and post-2000 births), phone numbers, and street addresses.
Invisible PDF artifacts (non-breaking spaces, soft hyphens) are normalized
before detection so they can't hide identifiers from either layer.

PII is replaced by typed, numbered placeholders — `[NAME_1]`, `[EMAIL_2]` —
stable per unique value, so an LLM can still follow who did what.

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

The pipeline **fails closed**: if redaction cannot run, nothing is emitted.

## Caveat

The detection model is good but not perfect (unusual names, novel secret
formats, regional conventions can slip through). For high-sensitivity
documents, review the sanitized output before sharing it.

## Agent skill

The repo ships an [Agent Skill](https://agentskills.io/specification) at
`skills/safeingest/SKILL.md` that teaches a coding agent to route sensitive
documents through this tool and read only the sanitized output. Install it for
your agent of choice with the GitHub CLI:

```bash
gh skill install HansF/safeingest --agent claude-code --scope user
# other agents: --agent github-copilot | cursor | codex | gemini-cli | ...
```
