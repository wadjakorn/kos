---
id: PROJ-kos-bootstrap
title: Bootstrap the Knowledge Operating System core engine
status: active
linked_atoms: [ATOM-20260602-81765c18, ATOM-20260602-22ec8e1c]
linked_theses: [THESIS-index-first-retrieval]
created: 2026-06-02
updated: 2026-06-02
---

## Objective

Stand up the KOS core: ingest pipeline, entity templates, generated indexes, and
a worked example — stdlib-only, idempotent, ready to extend toward RAG / MCP /
Obsidian later.

## Linked Knowledge

Authoring workflow captured in [[ATOM-20260602-81765c18]]; the idempotency
mechanism in [[ATOM-20260602-22ec8e1c]] underpins safe re-ingestion. Tests
[[THESIS-index-first-retrieval]].

## Open Questions

- When does marker-based extraction stop scaling, warranting the LLM extractor seam?
- Do theses/projects need their own index beyond `master_index.md`?

## Decisions

- 2026-06-02 — Atom extraction is marker-based + stdlib-only, behind a pluggable
  `Extractor` interface (decision recorded as [[ATOM-20260602-f50e09e5]]'s sibling design).

## Deliverables

- [x] Folder structure + templates
- [x] `scripts/ingest.py` (extract + idempotent index rebuild)
- [x] Worked example (source + thesis + project)
- [ ] LLM / heuristic extractor (deferred seam)
