---
title: KOS Design Notes
origin: Project handoff — Knowledge Operating System spec
ingested: 2026-06-02
reliability: 0.9
reliability_note: Firsthand design decisions agreed with the project owner.
summary: Core architectural decisions behind this Knowledge Operating System.
tags: [architecture, kos]
id: SRC-20260602-4db8b345
atoms: [ATOM-20260602-22ec8e1c, ATOM-20260602-81765c18, ATOM-20260602-b81ac728, ATOM-20260602-f50e09e5]
---

## Summary

Design notes for the KOS itself — recorded as a source so the system documents
its own foundations. Atoms below are extracted by `scripts/ingest.py`.

## Content / Notes

::atom
type: insight
title: Index-first retrieval avoids full-repo scans
tags: [retrieval, architecture]
source_location: "§Retrieval workflow"
confidence: 0.9
---
Agents read the master index, then a scoped index, then candidate atoms — and
only open raw source material when an atom is insufficient. This bounds context
cost regardless of repo size.
::end

::atom
type: decision
title: Indexes are derived artifacts, never hand-edited
tags: [architecture, indexing]
source_location: "§Invariants"
confidence: 1.0
---
Every file under indexes/ is regenerated from entity frontmatter on each ingest
run. The source of truth is the entity files; indexes are a projection of them.
::end

::atom
type: fact
title: Atom IDs embed a content hash for idempotent dedupe
tags: [indexing, provenance]
source_location: "§ID conventions"
confidence: 0.95
---
An atom's ID is ATOM-YYYYMMDD-<hash8>, where hash8 is the first 8 hex chars of
the sha256 over its normalized title+body. Re-ingesting an unchanged source
produces the same hash, so no duplicate atom is created.
::end

::atom
type: procedure
title: How to add knowledge to the KOS
tags: [workflow, kos]
source_location: "§Lifecycle"
confidence: 0.85
---
Write a source file in sources/ with inline ::atom blocks, run
`python3 scripts/ingest.py`, then inspect the regenerated indexes/ to confirm
the new atoms are linked and tagged.
::end
