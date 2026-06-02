#!/usr/bin/env python3
"""web_smoke_test.py — smoke test for the web UI's logic layer (webapi.py).

Drives webapi functions against a throwaway KOS in a temp dir (engine globals
repointed there) — touches NO real repo data. Asserts the GUI-specific behaviour
the spec demands: add → counts, idempotent re-add framed as success, curation
writes + index rebuild, reverse-linked theses/projects, structured errors.

    python3 scripts/web_smoke_test.py      # exit 0 = pass, 1 = fail
"""
from __future__ import annotations

import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def repoint(tmp: Path) -> None:
    """Point the engine's module-level paths at the temp tree."""
    ingest.ROOT = tmp
    ingest.SOURCES = tmp / "sources"
    ingest.ATOMS = tmp / "atoms"
    ingest.THESES = tmp / "theses"
    ingest.PROJECTS = tmp / "projects"
    ingest.INDEXES = tmp / "indexes"
    ingest.LOGS = tmp / "logs"
    ingest.CONFIG = tmp / "config" / "extractor.json"
    ingest.CACHE = tmp / ".cache" / "extract"
    for d in ("sources", "atoms", "theses", "projects", "indexes", "logs"):
        (tmp / d).mkdir(parents=True, exist_ok=True)


SOURCE_MD = """\
---
title: Web Smoke Source
origin: web-smoke
reliability: 0.9
summary: Throwaway source for the web smoke test.
tags: [smoke]
---

::atom
type: fact
title: Web smoke fact
tags: [smoke, web]
source_location: "§1"
confidence: 0.9
---
A fact captured by the web layer.
::end

::atom
type: insight
title: Web smoke insight
tags: [smoke]
source_location: "§2"
confidence: 0.7
---
An insight captured by the web layer.
::end
"""


def quiet(fn, *a, **k):
    with redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="kos-web-smoke-"))
    try:
        repoint(tmp)
        # import AFTER repoint so webapi binds to the patched ingest module.
        import webapi

        md = tmp / "input.md"
        md.write_text(SOURCE_MD, encoding="utf-8")

        # 1. add_source mints atoms + reports counts.
        print("== 1. add source ==")
        r = quiet(webapi.add_source, str(md), tags="extra")
        check("no error on add", not r.get("error"), r.get("error", ""))
        check("2 new atoms reported", r.get("new_count") == 2, f"got {r.get('new_count')}")
        check("1 source written", len(r.get("sources", [])) == 1)
        atom_ids = [a["id"] for a in r["new_atoms"]]

        # 2. idempotent re-add → 0 new (success framing, not error).
        print("== 2. idempotent re-add ==")
        r2 = quiet(webapi.add_source, str(md))
        check("re-add not an error", not r2.get("error"))
        check("re-add reports 0 new atoms", r2.get("new_count") == 0, f"got {r2.get('new_count')}")

        # 3. reads.
        print("== 3. reads ==")
        st = webapi.stats()
        check("stats counts atoms=2", st["counts"]["atoms"] == 2, str(st["counts"]))
        check("list_atoms type filter works", len(webapi.list_atoms(type="fact")) == 1)
        check("list_atoms tag filter works", len(webapi.list_atoms(tag="web")) == 1)
        check("search finds atom", len(webapi.search("insight")["atoms"]) >= 1)
        a = webapi.get_atom(atom_ids[0])
        check("get_atom carries provenance", bool(a.get("source")) and a.get("source_location") is not None)

        # 4. create thesis + rebuild + reverse link.
        print("== 4. curation: thesis ==")
        th = quiet(webapi.create_thesis, {
            "title": "Web layer works", "status": "active", "confidence": "0.8",
            "statement": "The web API mints and links correctly.",
            "reasoning": "Backed by the smoke atom.",
            "supporting_atoms": [atom_ids[0]],
        })
        check("thesis created", bool(th.get("id")), th.get("error", ""))
        check("thesis file written", (ingest.THESES / f"{th['id']}.md").exists())
        check("thesis in thesis_index", th["id"] in (ingest.INDEXES / "thesis_index.md").read_text())
        got = webapi.get_thesis(th["id"])
        check("thesis resolves supporting atom", len(got["supporting"]) == 1)
        rev = webapi.get_atom(atom_ids[0])
        check("atom shows reverse-linked thesis",
              any(t["id"] == th["id"] for t in rev["linked_theses"]))

        # 5. create project + reverse link.
        print("== 5. curation: project ==")
        pr = quiet(webapi.create_project, {
            "title": "Smoke project", "objective": "Prove project writes.",
            "linked_atoms": [atom_ids[1]], "open_questions": ["does it link?"],
            "deliverables": ["ship it"],
        })
        check("project created", bool(pr.get("id")), pr.get("error", ""))
        proj = webapi.get_project(pr["id"])
        check("project resolves linked atom", len(proj["atoms"]) == 1)
        check("atom shows reverse-linked project",
              any(p["id"] == pr["id"] for p in webapi.get_atom(atom_ids[1])["linked_projects"]))

        # 6. update thesis (status/confidence) + rebuild.
        print("== 6. update thesis ==")
        quiet(webapi.update_thesis, th["id"], {"status": "confirmed", "confidence": "0.95"})
        check("thesis status updated", webapi.get_thesis(th["id"])["status"] == "confirmed")

        # 7. error path: unsupported input doesn't crash.
        print("== 7. structured errors ==")
        bad = quiet(webapi.add_source, "/nonexistent/file.xyz")
        check("unsupported input returns error, not crash", bool(bad.get("error")), str(bad))

        # 8. preview writes nothing.
        print("== 8. preview ==")
        before = len(list((tmp / "atoms").glob("*.md")))
        prev = webapi.preview_extraction(SOURCE_MD)
        after = len(list((tmp / "atoms").glob("*.md")))
        check("preview returns candidate atoms", len(prev) == 2, f"got {len(prev)}")
        check("preview writes no atoms", before == after)

    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
