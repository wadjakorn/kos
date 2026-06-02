---
id: ATOM-YYYYMMDD-xxxxxxxx          # auto-assigned by ingest.py (do not hand-set)
type: fact                          # fact | insight | decision | procedure
title: One-line claim or statement
tags: [tag-a, tag-b]                # lowercase kebab-case
source: SRC-YYYYMMDD-xxxxxxxx       # provenance, required
source_location: "p.12 / §3 / 04:21"  # where in the source it came from
created: YYYY-MM-DD                 # auto-assigned by ingest.py
confidence: 0.8                     # 0.0–1.0
hash: <sha256-of-title+body>        # dedupe key, auto-assigned
linked_theses: []                   # [[THESIS-...]] this atom supports/contradicts
linked_projects: []                 # [[PROJ-...]] this atom informs
---

The atom body: the smallest self-contained, reusable unit of knowledge.
One idea. Stands alone. Traceable to its source via the `source` field.
