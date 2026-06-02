# Agent — Start Here

**You are operating inside a Knowledge Operating System (KOS).** Read this file
before touching anything else. It is the contract.

## What this repo is

A git-native, file-based knowledge store. Sources are atomized into the
smallest reusable knowledge units (**atoms**), linked into **theses** (claims)
and **projects** (goals), and surfaced through **auto-generated indexes**. You
retrieve via indexes — you do not scan the repo.

## The five invariants (do not violate)

1. **Indexes are derived, never hand-edited.** Everything in `indexes/` is
   regenerated from entity frontmatter by `scripts/ingest.py`. Editing an index
   is a no-op at best and a lie at worst — change the underlying entity, then
   re-run ingest.
2. **Index-first retrieval. Never full-repo scan.** Follow the workflow below.
3. **Every atom carries provenance.** `source` + `source_location` are required;
   the source's `atoms:` field back-references it.
4. **Ingest is idempotent.** Atoms dedupe by content hash. Re-running on an
   unchanged source adds nothing.
5. **This file is the mandatory first read.**

## Retrieval workflow

```
1. Read docs/agent_start_here.md      ← you are here
2. Read indexes/master_index.md       ← what exists, grouped by kind
3. Read the relevant scoped index:
     topic_index.md   — by tag
     source_index.md  — by source
     thesis_index.md  — by claim + status
     tag_index.md     — tag vocabulary
4. Read candidate atoms (atoms/ATOM-*.md)
5. Read source material (sources/) ONLY when an atom is insufficient
```

Stop at the earliest step that answers the question.

## Where the db lives (data root)

The paths above (`indexes/`, `atoms/`, `sources/`, …) live in the **data repo**,
not this code repo. Standard layout is two sibling repos: `knowledge-base/kos/`
(code, this repo) and `knowledge-base/db/` (data). The engine resolves the data
root in order: `KOS_DATA_ROOT` env var → `config/paths.json` → sibling `../db`
(default). The root is the single entry point — it doubles as the Obsidian vault
(links `[[ID]]` resolve to `{ID}.md` files under it). To find the active root:
`python3 -c "import sys; sys.path.insert(0,'scripts'); import ingest; print(ingest.ROOT)"`.
Templates, scripts, and `config/extractor.json` always stay in the code repo.

## Entity conventions

| Kind | ID | Authored by | Lives in |
|------|----|-----------|---------|
| Atom | `ATOM-YYYYMMDD-<hash8>` | ingest.py | `atoms/` |
| Source | `SRC-YYYYMMDD-<hash8>` | author + ingest.py | `sources/` |
| Thesis | `THESIS-<slug>` | human | `theses/` |
| Project | `PROJ-<slug>` | human | `projects/` |

- Every entity = YAML frontmatter + markdown body.
- Tags: lowercase kebab-case. Cross-links: `[[ID]]`.
- Atom types: `fact | insight | decision | procedure`.
- Thesis status: `active | confirmed | challenged | archived`.

## Extractor (current default)

Default ingest extractor = **`llm` via the `claude -p` CLI** (set in the local,
gitignored `config/extractor.json`). The model is fed each source body and emits
`::atom` blocks in the format below — so sources **need no hand-written markers**
to produce atoms. LLM output is cached by source hash, preserving idempotency.
To force deterministic, marker-only parsing, set `"extractor": "marker"` (or
delete `config/extractor.json`).

## Authoring atoms (the `::atom` format)

Atoms are not written by hand into `atoms/`. The configured extractor emits them
(the `claude -p` model does so automatically; in marker mode you embed them by
hand). Either way they live inside a source file and are extracted by ingest:

```
::atom
type: insight
title: One-line claim
tags: [tag-a, tag-b]
source_location: "§3"
confidence: 0.8
---
The atom body — one self-contained idea.
::end
```

`id`, `source`, `created`, and `hash` are injected by `ingest.py`.

## Running ingest

```bash
python3 scripts/ingest.py --dry-run --verbose   # preview, writes nothing
python3 scripts/ingest.py                        # materialize atoms + rebuild indexes
```

See `templates/` for the full frontmatter schema of each entity kind.
