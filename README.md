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
scripts/serve.py           # web UI server (stdlib http.server)
scripts/webapi.py          # web UI logic layer (reuses ingest.py + kos.py)
web/                       # vanilla HTML/JS/CSS front end
config/                    # extractor + paths config (copy *.example.json to enable)
logs/                      # ingest run logs
examples/                  # pointers to the worked example
```

The **data directories** (`sources/ atoms/ theses/ projects/ indexes/ logs/`)
are *the db* — by default they sit in this repo, but they can live in their own
directory outside it (see **Data root** below).

## Data root — where the db lives

Code (this repo) and knowledge (the db) can version independently. The engine
resolves a single **data root**, in order:

1. `KOS_DATA_ROOT` environment variable
2. `config/paths.json` → `{"data_root": "..."}` (machine-local, gitignored)
3. the repo root itself (backward-compatible default — no setup needed)

That data root is the **single entry point** for everything else: it is the KOS
data dir, it can be its own git repo, and it is the **Obsidian vault root**.
Because atom files are named `{ID}.md` and links use `[[ID]]`, Obsidian resolves
cross-links by basename as long as every entity folder sits under one root —
which this guarantees.

**One-time setup — externalize the db:**

```bash
# 1. pick a root and move any existing local data into it
mkdir -p ~/knowledge-base-data
mv sources atoms theses projects indexes logs ~/knowledge-base-data/ 2>/dev/null || true

# 2. point the engine at it (either mechanism works)
cp config/paths.example.json config/paths.json   # then edit data_root, OR:
export KOS_DATA_ROOT=~/knowledge-base-data

# 3. give the data its own git history
cd ~/knowledge-base-data && git init && \
  printf '.cache/\nlogs/*.log\n' > .gitignore && \
  git add . && git commit -m "init knowledge data"

# 4. open ~/knowledge-base-data in Obsidian as a vault (optional)
```

With a data root configured, the in-repo `sources/ atoms/ …` skeleton is unused
(it only serves the default no-config mode). `config/extractor.json` stays in
the code repo — it is engine config, not knowledge.

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

`kos.py` resolves its real path through the symlink and writes to the configured
**data root** (see above) no matter where you invoke `kos`. (Alternative: `alias
kos="python3 /abs/path/to/scripts/kos.py"`.)

## Web UI

A browser front end over the same engine — zero third-party deps (stdlib
`http.server` + vanilla JS), so it runs anywhere the CLI does.

```bash
python3 scripts/serve.py            # → http://127.0.0.1:8000/
python3 scripts/serve.py --port 9000 --host 0.0.0.0   # expose on the LAN
```

What it does:

- **Dashboard** — counts, atom-type breakdown, recent atoms/sources; empty-state
  onboarding on a fresh install.
- **Add source** — the `kos add` flow with a friendly face: paste a URL/feed/YouTube
  link or upload a file, set tags/title/reliability, watch async progress, then see the
  sources written and atoms minted. Feeds expand to many sources; a re-add of unchanged
  content is shown as *"already captured"* (idempotency), not an error. Bypassing TLS
  verification is a guarded, explicit confirmation — never default-on.
- **Browse & search** — index-first lenses (all atoms, by tag, by source) with
  composable filters (tag + type + source + text), mirroring `indexes/`. Read-only —
  indexes are derived, never editable.
- **Atom / source detail** — every atom always shows its provenance (source +
  `source_location`) and reverse-linked theses/projects.
- **Curate** — create/edit theses (attach supporting/contradicting atoms) and projects
  (link atoms/theses, track open questions, decisions, deliverables). Curation edits
  entity frontmatter and re-runs ingest to rebuild indexes — the engine invariants hold.

The logic lives in `scripts/webapi.py` (pure functions reusing `ingest.py`/`kos.py`);
`scripts/serve.py` is the HTTP glue. Smoke-test it with
`python3 scripts/web_smoke_test.py`.

## Updating & deleting knowledge

Re-ingest **reconciles** atoms against their sources — it is no longer
append-only:

- **Edit an atom's metadata** (tags, type, confidence, source_location) in its
  `::atom` block, re-run ingest → the atom file is updated in place. Its `id`,
  `created` date, `hash`, and links are preserved.
- **Edit an atom's title or body** → content hash changes, so a new atom is
  minted and the stale one is **pruned** (net update).
- **Remove an `::atom` block** → its atom is pruned and every back-reference
  (source `atoms`, thesis `supporting_atoms`/`contradicting_atoms`, project
  `linked_atoms`) is scrubbed.

```bash
python3 scripts/ingest.py              # reconcile + prune orphans (default)
python3 scripts/ingest.py --no-prune   # keep orphans (old append-only behavior)
python3 scripts/ingest.py --dry-run    # report would-prune, write nothing
```

**Prune is guarded against accidental wipes.** It skips entirely on an empty
scan, and prunes an orphan only if its source produced **≥1 live atom** this
run. A source that drops to zero atoms — most often because it was ingested with
a *different extractor* than minted its atoms (e.g. plain marker mode over
sources whose atoms came from `--extractor llm`) — has its atoms **retained**
with a warning, not deleted. Remove those deliberately via the web UI or by
re-running with the extractor that created them.

**Web UI:** a source's detail page has **Delete source** (removes the source,
the atoms it produced, and all references) and an atom's page has **Delete
atom** — both confirm first and durably strip the originating `::atom` block so
re-ingest can't resurrect them.

## LLM extraction

> **Default ingest (current):** this repo ships a local, gitignored
> `config/extractor.json` set to **`llm` via the `claude -p` CLI**. Every
> `ingest.py` run and every web-UI add mints atoms from raw prose by piping the
> extraction prompt to `claude -p` on stdin — no `::atom` markers required.
> Output is cached by source hash, so re-runs stay idempotent. Revert to
> deterministic marker-only parsing by setting `"extractor": "marker"` (or
> deleting `config/extractor.json`).

The marker extractor parses human-authored `::atom` blocks (deterministic, zero
deps). The LLM extractor asks a model to emit those same `::atom` blocks, so one
parser serves humans and models alike. Configure it in `config/extractor.json`
(copy `config/extractor.example.json` to start) with `"extractor": "llm"`. Three
backends ship:

```bash
# configured default — Claude CLI, prompt on stdin:
#   config/extractor.json → {"extractor":"llm","backend":"cli","cli":{"cmd":["claude","-p"]}}

# one-off override, no config file:
python3 scripts/ingest.py --extractor llm --backend cli --cmd "claude -p"
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
workflows, knowledge-graph generation. The **Obsidian vault** seam is now live —
the data root *is* the vault (see **Data root**). Two seams are already
populated: the `Extractor` interface (`scripts/ingest.py`) ships `Marker` + `LLM`
extractors, and the `Loader` interface (`scripts/kos.py`) ships six intake
formats — PDF and others slot in as new subclasses.
