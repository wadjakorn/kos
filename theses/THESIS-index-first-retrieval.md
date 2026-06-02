---
id: THESIS-index-first-retrieval
title: Index-first retrieval scales knowledge access independent of repo size
status: active
confidence: 0.8
supporting_atoms: [ATOM-20260602-b81ac728, ATOM-20260602-f50e09e5]
contradicting_atoms: []
created: 2026-06-02
updated: 2026-06-02
---

## Thesis Statement

An agent that navigates via generated indexes — master → scoped → atoms → source
— spends bounded context regardless of how large the knowledge base grows,
because it never scans the full repository.

## Reasoning

[[ATOM-20260602-b81ac728]] establishes the retrieval order that stops at the
earliest sufficient layer. [[ATOM-20260602-f50e09e5]] guarantees the indexes are
always an accurate projection of the entities, so the agent can trust them
instead of re-reading sources.

Open risk: if indexes drift (e.g. an index is hand-edited despite the
invariant), retrieval silently degrades. Promote a contradicting atom here if
that failure mode is ever observed in practice.
