---
name: safeingest
description: Ingest PII-sensitive documents safely by converting them to markdown and masking personal information locally BEFORE reading them. Use whenever the user asks to read, summarize, analyze, or extract from a document that contains (or may contain) personal data — names, emails, phone numbers, addresses, account numbers, secrets — or says "sensitive", "PII", "private", "safeingest", "ingest this safely", "don't leak". Works on PDF, DOCX, XLSX, PPTX, HTML, CSV, images, URLs.
---

# SafeIngest — PII-safe document ingestion

`safeingest` converts a document to markdown (microsoft/markitdown) and masks
PII with a local model (openai/privacy-filter) that runs entirely on this
machine. The point is that the ORIGINAL content never enters your context.

## Hard rules

1. **Never open the original document** with Read, Bash (`cat`, `head`, `strings`,
   `pdftotext`, python, …), or any other tool. That is the leak this skill prevents.
2. **Read only the sanitized output file** produced by `safeingest`.
3. If `safeingest` fails, report the error to the user — do NOT fall back to
   reading the original document.

## If `safeingest` is not installed

Source repo: **https://github.com/HansF/safeingest** (public).

Check availability before first use: `command -v safeingest` (Linux/macOS) or
`Get-Command safeingest` / `where safeingest` (Windows). If missing, work down
this list — never skip to reading the original document as a "fallback":

1. **Tool missing, `uv` present**:
   ```bash
   uv tool install "safeingest @ git+https://github.com/HansF/safeingest"
   ```
   (from a local checkout: `uv tool install --editable .`).
   If the command isn't found afterwards, the tool bin dir is not on PATH —
   run `uv tool update-shell`, or call it directly: `~/.local/bin/safeingest`
   (Linux/macOS) / `%USERPROFILE%\.local\bin\safeingest.exe` (Windows).

   **One-shot alternative with `uvx`** (no install, works on all platforms;
   good for a single document — note it re-resolves the env on cold cache):
   ```bash
   uvx --from git+https://github.com/HansF/safeingest safeingest <file> -o out.safe.md --report
   ```
   torch only supports Python 3.10–3.12 here; if uvx picks a newer default
   interpreter, add `--python 3.12` (uv downloads it automatically).
2. **`uv` also missing**: confirm with the user, then install it —
   - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
     or `winget install astral-sh.uv`
   - or a package manager: `pacman -S uv`, `brew install uv`, `pipx install uv`

   Then do step 1. If the shell doesn't see `uv` right after install, use the
   full path (`~/.local/bin/uv` / `%USERPROFILE%\.local\bin\uv.exe`) or start
   a new shell.
3. **No uv possible** (locked-down box): fall back to plain pip in a venv
   (needs Python 3.10–3.12; on Windows use `py -3.12` and the `Scripts\` dir):
   ```bash
   python3 -m venv ~/.safeingest-venv
   ~/.safeingest-venv/bin/pip install "git+https://github.com/HansF/safeingest"
   ~/.safeingest-venv/bin/safeingest <file> ...
   ```
4. **Nothing installable**: stop and tell the user the document cannot be
   ingested safely on this machine. Do not read the original.

## Usage

```bash
safeingest <file-or-url> -o <scratchpad-or-project-dir>/<name>.safe.md --report
```

Then Read the `.safe.md` file. The `--report` JSON (stderr) tells you how many
spans were masked per category — relay this to the user.

## Flags

| Flag | Effect |
|---|---|
| (default) | masks name, email, phone, address, account, secret |
| `--strict` | also masks urls and dates (all 8 categories) |
| `--mask CAT,..` | mask exactly these categories |
| `--allow CAT,..` | never mask these (e.g. `--allow name` for public authors) |
| `--device cpu` | force CPU if CUDA misbehaves |

## Reading the output

- Placeholders are typed and numbered: `[NAME_1]`, `[EMAIL_2]`, `[ACCOUNT_1]`.
  The same value always gets the same number, so `[NAME_1]` in two places is
  the same person — you can reason about who did what without knowing who.
- Never ask the user to reveal what a placeholder stands for.
- First-ever run downloads the model checkpoint (~few GB) to `~/.opf/` — expect
  a delay and tell the user why.

## Caveats to relay when it matters

Detection is a model, not a guarantee: unusual names, novel secret formats, or
regional conventions can slip through. For high-sensitivity documents, suggest
the user skim the sanitized file before it goes anywhere else.
