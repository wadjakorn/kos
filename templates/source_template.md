---
id: SRC-YYYYMMDD-xxxxxxxx           # auto-assigned by ingest.py if omitted
title: Source title
origin: "URL / book / conversation / file path"
ingested: YYYY-MM-DD
reliability: 0.7                    # 0.0–1.0
reliability_note: "why this score (author authority, peer review, firsthand, …)"
summary: One-line summary of the source.
atoms: []                          # back-refs, auto-maintained by ingest.py
tags: [tag-a]
---

## Summary

A short prose summary of the source.

## Content / Notes

The source material (or notes on it). Embed atoms inline as marker blocks —
ingest.py extracts each into its own atom file with provenance back to this
source:

::atom
type: insight
title: A reusable claim found in this source
tags: [example]
source_location: "§2"
confidence: 0.8
---
The body of the atom — one self-contained idea.
::end
