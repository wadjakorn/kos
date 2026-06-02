# Worked Example

The KOS ships with a self-documenting example — the system describing its own
design. The files live in their normal homes (not here), so the example doubles
as real, queryable knowledge:

| File | Role |
|------|------|
| [`sources/source_kos_design.md`](../sources/source_kos_design.md) | Source with 4 inline `::atom` blocks (one per atom type) |
| `atoms/ATOM-2026*.md` | The 4 atoms ingest extracted from that source |
| [`theses/THESIS-index-first-retrieval.md`](../theses/THESIS-index-first-retrieval.md) | A claim linking two of the atoms as supporting evidence |
| [`projects/PROJ-kos-bootstrap.md`](../projects/PROJ-kos-bootstrap.md) | A project linking atoms + the thesis |
| `indexes/*.md` | All five indexes, generated from the above |

## Reproduce it

```bash
python3 scripts/ingest.py --dry-run --verbose   # preview
python3 scripts/ingest.py                        # build atoms + indexes
python3 scripts/ingest.py                        # re-run → 0 new atoms (idempotent)
cat indexes/master_index.md                      # the generated map
```
