# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **git-native, file-based Knowledge Operating System (KOS)** — not a flat note store. Sources are ingested, atomized into the smallest reusable knowledge units, tagged, linked into theses and projects, and surfaced through auto-generated indexes. The system is built so AI agents retrieve precisely via indexes instead of scanning the whole repo.

Status: greenfield. Architecture below is the build contract — see the handoff spec for full rationale.

## Core model

- **Atom** — smallest reusable knowledge unit. `type: fact | insight | decision | procedure`. Always carries provenance back to a source.
- **Thesis** — a claim under evaluation. Has `supporting_atoms`, `contradicting_atoms`, confidence, and a lifecycle `status: active | confirmed | challenged | archived`.
- **Project** — goal-oriented workspace linking atoms, theses, decisions, deliverables.
- **Source** — an ingested document; origin of atoms; carries a reliability assessment.
- **Index** — derived registry under `indexes/`.

## Non-negotiable invariants

These are the contract every agent and script must hold:

1. **Indexes are derived, never hand-edited.** `indexes/*.md` are full rebuilds from entity frontmatter. Append-on-edit is a bug — regenerate from source of truth.
2. **Index-first retrieval. Never full-repo scan.** Retrieval order: `docs/agent_start_here.md` → `master_index.md` → relevant scoped index → candidate atoms → source material only when an atom is insufficient.
3. **Every atom has provenance.** `source` + `source_location` are required. Atom↔source links are bidirectional.
4. **Ingest is idempotent.** Dedupe by content hash. Re-running on an unchanged source produces no new atoms.
5. **`docs/agent_start_here.md` is the mandatory first read** for any agent operating here.

## ID & frontmatter conventions

- Atom: `ATOM-YYYYMMDD-<shorthash>`
- Source: `SRC-YYYYMMDD-<shorthash>`
- Thesis: `THESIS-<slug>` · Project: `PROJ-<slug>`
- Every entity = YAML frontmatter + markdown body.
- Tags: lowercase kebab-case; vocabulary lives in generated `tag_index.md`.
- Cross-links use `[[ID]]` wikilink style (Obsidian-compatible).

## Layout

```
docs/agent_start_here.md   # mandatory agent entry point
templates/                 # atom / thesis / project / source templates
atoms/  theses/  projects/  sources/
indexes/                   # master, topic, source, thesis, tag — ALL generated
scripts/ingest.py          # ingest pipeline
logs/                      # ingest operation logs
examples/                  # example data + worked workflow
```

## ingest.py pipeline (ordered, idempotent, dry-run capable)

scan sources (by hash) → generate IDs → extract candidate atoms → write atom files from template → **full-rebuild all indexes** → resolve tags → write bidirectional provenance → append structured log.

Keep it stdlib-first — low dependency footprint for NAS / self-host targets.

## Design seams (don't build yet, don't block)

Keep frontmatter machine-parseable and IDs stable so these bolt on without migration: vector DB, local embeddings, MCP knowledge server, multi-agent workflows, Obsidian vault, Claude Code memory layer, knowledge-graph generation.
