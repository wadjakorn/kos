# Knowledge Operating System (KOS)

A git-native, file-based knowledge store. Sources are atomized into the
smallest reusable knowledge units (**atoms**), linked into **theses** and
**projects**, and surfaced through **auto-generated indexes** so that AI agents
(and you) retrieve precisely via indexes instead of scanning the whole repo.

> **AI agents:** read [`docs/agent_start_here.md`](docs/agent_start_here.md)
> first. It is the operating contract.

## Layout

```
docs/agent_start_here.md   # mandatory agent entry point
templates/                 # atom / thesis / project / source schemas
sources/                   # ingested documents (atoms embedded as ::atom blocks)
atoms/                     # generated atom files (one idea each)
theses/                    # claims under evaluation
projects/                  # goal-oriented workspaces
indexes/                   # GENERATED — never hand-edit
scripts/ingest.py          # the ingest + index-rebuild pipeline
scripts/kos.py             # source intake — `kos add <url|file>`
config/                    # extractor.example.json (copy to extractor.json to enable LLM)
logs/                      # ingest run logs
examples/                  # pointers to the worked example
```

## The five invariants

1. Indexes are **derived, never hand-edited** — `ingest.py` rebuilds them every run.
2. **Index-first retrieval** — never full-repo scan.
3. Every atom carries **provenance** (`source` + `source_location`), bidirectional.
4. Ingest is **idempotent** — atoms dedupe by content hash.
5. `docs/agent_start_here.md` is the mandatory agent entry point.

## Worked example

A source documenting this system's own design ships in
[`sources/source_kos_design.md`](sources/source_kos_design.md), with a linked
thesis and project. Run the pipeline and inspect the result:

```bash
# Preview what would be extracted — writes nothing.
python3 scripts/ingest.py --dry-run --verbose

# Materialize atoms and rebuild all indexes.
python3 scripts/ingest.py

# Re-run: 0 new atoms (idempotency).
python3 scripts/ingest.py --verbose

# Read the generated navigation.
cat indexes/master_index.md
```

## Adding knowledge

Two paths:

**Manual** — for markdown you already wrote. Copy `templates/source_template.md`
into `sources/` (or drop any `.md`), optionally embedding `::atom` blocks for
each reusable idea, then run `python3 scripts/ingest.py`. Atoms are minted with
provenance and all indexes regenerate. Link atoms into a thesis or project by
adding their IDs to the relevant frontmatter, then re-run ingest.

**Automated (`kos add`)** — for URLs, feeds, PDFs of other formats. Detects the
type, extracts text, scaffolds the source frontmatter, writes `sources/<slug>.md`,
and runs ingest — all in one command. See below.

## Source intake — `kos add`

```bash
kos add https://example.com/post --tags web,ml   # web article
kos add https://blog.com/feed.xml                 # RSS/Atom → one source per entry
kos add notes.md                                  # markdown / plaintext
kos add paper.epub                                # book
kos add report.docx                               # Word doc
kos add https://youtu.be/VIDEO_ID                 # video transcript (needs yt-dlp)
kos add file.md --no-ingest                       # scaffold only, ingest later
```

Supported types and how they are read:

| Input              | Extraction                          | Needs        |
|--------------------|-------------------------------------|--------------|
| URL / `.html`      | `urllib` + `html.parser` strip      | stdlib       |
| RSS / Atom feed    | `xml.etree`, one source per entry   | stdlib       |
| `.md` / `.txt`     | read, keeps existing frontmatter    | stdlib       |
| `.epub`            | `zipfile` + spine order + strip     | stdlib       |
| `.docx`            | `zipfile` + `word/document.xml`     | stdlib       |
| YouTube URL        | `yt-dlp` → subtitles → text         | `yt-dlp`     |

Unsupported types report a clear error; force a loader with `--type`. A new type
is one `Loader` subclass in `scripts/kos.py` — no pipeline change.

### Installing the `kos` command

```bash
chmod +x scripts/kos.py
mkdir -p ~/.local/bin
ln -s "$(pwd)/scripts/kos.py" ~/.local/bin/kos     # symlink onto PATH
# ensure ~/.local/bin is on PATH (zsh):
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

`kos.py` resolves its real path through the symlink, so `sources/` always land in
this repo no matter where you invoke `kos`. (Alternative: `alias kos="python3
/abs/path/to/scripts/kos.py"`.)

## LLM extraction (optional)

By default the marker extractor parses human-authored `::atom` blocks
(deterministic, zero deps). To have a model mint atoms from raw prose instead,
copy `config/extractor.example.json` to `config/extractor.json` and set
`"extractor": "llm"`. Two backends ship:

```bash
# one-off, no config file:
python3 scripts/ingest.py --extractor llm --backend cli --cmd "ollama run llama3.1"
```

- **cli** — shells out to any command (ollama, `claude -p`, `llm`, llama.cpp);
  prompt on stdin, completion on stdout.
- **http-local** — POSTs a local model server (ollama / LM Studio / llama.cpp).

The model is told to emit `::atom` blocks in the same marker format, so one
parser serves humans and models alike. LLM output is **cached by source hash**
(`.cache/`) so re-running an unchanged source returns identical atoms —
idempotency holds despite model non-determinism. API tokens, if any, are read
from an env var (`auth_env`), never the config file.

## Requirements

Python 3.11+. Stdlib only for the core engine and all intake loaders except
YouTube. Optional: `yt-dlp` (YouTube transcripts), a local model runner such as
`ollama` (LLM extraction). No third-party Python packages — NAS / self-host
friendly.

## Design seams (not yet built)

Frontmatter is machine-parseable and IDs are stable so these can bolt on without
migration: vector DB, local embeddings, MCP knowledge server, multi-agent
workflows, Obsidian vault sync, knowledge-graph generation. Two seams are already
populated: the `Extractor` interface (`scripts/ingest.py`) ships `Marker` + `LLM`
extractors, and the `Loader` interface (`scripts/kos.py`) ships six intake
formats — PDF and others slot in as new subclasses.
