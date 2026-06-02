#!/usr/bin/env python3
"""smoke_test.py — end-to-end smoke test for the KOS ingest engine.

Builds a throwaway KOS in a temp dir, copies the real scripts/ingest.py into it,
and drives it via subprocess so ROOT resolves to the temp tree. Asserts the five
invariants. Touches NO real repo data.

    python3 scripts/smoke_test.py        # exit 0 = pass, 1 = fail
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REAL_INGEST = Path(__file__).resolve().parent / "ingest.py"

SOURCE = """\
---
title: Smoke Source
origin: smoke-test
ingested: 2026-01-01
reliability: 0.9
summary: A throwaway source for the smoke test.
tags: [smoke]
---

::atom
type: fact
title: Smoke atom alpha
tags: [smoke, alpha]
source_location: "§1"
confidence: 0.9
---
First smoke atom body.
::end

::atom
type: insight
title: Smoke atom beta
tags: [smoke]
source_location: "§2"
confidence: 0.7
---
Second smoke atom body.
::end
"""

EXTRA_ATOM = """
::atom
type: decision
title: Smoke atom gamma
tags: [smoke]
source_location: "§3"
confidence: 0.6
---
Third smoke atom, added to test the delta.
::end
"""

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def run(root: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "ingest.py"), *args],
        cwd=root, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"ingest.py exited {proc.returncode}")
    return proc.stdout


def index_fingerprint(root: Path) -> str:
    parts = []
    for p in sorted((root / "indexes").glob("*.md")):
        parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="kos-smoke-"))
    try:
        for d in ("sources", "atoms", "theses", "projects", "indexes", "logs", "scripts"):
            (tmp / d).mkdir(parents=True)
        shutil.copy(REAL_INGEST, tmp / "scripts" / "ingest.py")
        src = tmp / "sources" / "smoke.md"
        src.write_text(SOURCE, encoding="utf-8")

        # 1. Dry-run writes nothing.
        print("== 1. dry-run ==")
        run(tmp, "--dry-run")
        check("dry-run creates no atom files", not list((tmp / "atoms").glob("ATOM-*.md")))
        check("dry-run writes no index files", not list((tmp / "indexes").glob("*.md")))

        # 2. Real run mints atoms + all 5 indexes + a log.
        print("== 2. real run ==")
        run(tmp)
        atoms = list((tmp / "atoms").glob("ATOM-*.md"))
        check("2 atoms created", len(atoms) == 2, f"got {len(atoms)}")
        idx = {p.name for p in (tmp / "indexes").glob("*.md")}
        expected = {"master_index.md", "topic_index.md", "source_index.md",
                    "thesis_index.md", "tag_index.md"}
        check("all 5 indexes generated", idx == expected, f"got {sorted(idx)}")
        check("ingest log written", bool(list((tmp / "logs").glob("ingest-*.log"))))

        # 3. Provenance: every atom carries source + source_location; back-refs resolve.
        print("== 3. provenance ==")
        prov_ok = True
        atom_ids = set()
        for a in atoms:
            txt = a.read_text(encoding="utf-8")
            atom_ids.add(a.stem)
            if "source: SRC-" not in txt or "source_location:" not in txt:
                prov_ok = False
        check("every atom has source + source_location", prov_ok)
        src_txt = src.read_text(encoding="utf-8")
        back_ok = all(aid in src_txt for aid in atom_ids)
        check("source back-references every atom", back_ok)

        # 4. Idempotency: re-run adds nothing, indexes byte-identical.
        print("== 4. idempotency ==")
        fp1 = index_fingerprint(tmp)
        out = run(tmp)
        fp2 = index_fingerprint(tmp)
        atoms2 = list((tmp / "atoms").glob("ATOM-*.md"))
        check("re-run creates 0 new atoms", len(atoms2) == 2, f"got {len(atoms2)}")
        check("re-run reports skipped=2", "skipped=2" in out)
        check("indexes byte-identical across runs", fp1 == fp2)

        # 5. Delta: adding one atom yields exactly one new.
        print("== 5. delta ==")
        src.write_text(SOURCE + EXTRA_ATOM, encoding="utf-8")
        run(tmp)
        atoms3 = list((tmp / "atoms").glob("ATOM-*.md"))
        check("adding 1 atom yields exactly 3 total", len(atoms3) == 3, f"got {len(atoms3)}")

        # 6. Indexes are derived: deleting an index and re-running restores it.
        print("== 6. derived indexes ==")
        (tmp / "indexes" / "master_index.md").unlink()
        run(tmp)
        check("deleted index regenerated on next run",
              (tmp / "indexes" / "master_index.md").exists())

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
