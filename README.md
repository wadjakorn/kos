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

1. Copy `templates/source_template.md` into `sources/` and fill it in, embedding
   `::atom` blocks for each reusable idea (see the template for the format).
2. Run `python3 scripts/ingest.py`.
3. Atoms are minted with provenance; all indexes regenerate. Link atoms into a
   thesis or project by adding their IDs to the relevant frontmatter, then
   re-run ingest.

## Requirements

Python 3.11+. Stdlib only — no third-party dependencies (NAS / self-host
friendly).

## Design seams (not yet built)

Frontmatter is machine-parseable and IDs are stable so these can bolt on without
migration: vector DB, local embeddings, MCP knowledge server, multi-agent
workflows, Obsidian vault sync, knowledge-graph generation. Atom extraction is
behind a pluggable `Extractor` interface (`scripts/ingest.py`) — the current
`MarkerExtractor` can be joined by LLM or heuristic extractors later.
