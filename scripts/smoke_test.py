#!/usr/bin/env python3
"""smoke_test.py — end-to-end smoke test for the KOS ingest engine.

Builds a throwaway KOS in a temp dir, copies the real scripts/ingest.py into it,
and drives it via subprocess so ROOT resolves to the temp tree. Asserts the five
invariants. Touches NO real repo data.

    python3 scripts/smoke_test.py        # exit 0 = pass, 1 = fail
"""
from __future__ import annotations

import json
import re
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


def atom_by_title(root: Path, title: str):
    for p in (root / "atoms").glob("ATOM-*.md"):
        txt = p.read_text(encoding="utf-8")
        if f"title: {title}" in txt:
            return p, txt
    return None, ""


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

        # Reconcile tests edit the ON-DISK source (which carries its assigned
        # SRC id) — rebuilding from the template would drop the id and churn
        # every atom's `source` field. State here: 3 atoms (alpha/beta/gamma).

        # 7. Update-in-place: a metadata edit (tags) lands without re-minting.
        print("== 7. update-in-place (metadata) ==")
        p_alpha, t_alpha = atom_by_title(tmp, "Smoke atom alpha")
        hash_alpha = re.search(r"hash: (\w+)", t_alpha).group(1)
        src.write_text(src.read_text().replace(
            "tags: [smoke, alpha]", "tags: [smoke, alpha, edited]"), encoding="utf-8")
        out7 = run(tmp)
        p2, t2 = atom_by_title(tmp, "Smoke atom alpha")
        check("update-in-place keeps same atom id", bool(p2) and p2.name == p_alpha.name)
        check("update-in-place keeps same hash", f"hash: {hash_alpha}" in t2)
        check("update-in-place applies new tag", "edited" in t2)
        check("update-in-place mints no new atom",
              len(list((tmp / "atoms").glob("ATOM-*.md"))) == 3)
        check("update-in-place reports updated=1", "updated=1" in out7)

        # 8. Content edit: new hash mints a new atom, old orphan is pruned.
        print("== 8. content edit re-mints + prunes orphan ==")
        src.write_text(src.read_text().replace(
            "First smoke atom body.", "First smoke atom body, revised."), encoding="utf-8")
        out8 = run(tmp)
        atoms8 = list((tmp / "atoms").glob("ATOM-*.md"))
        check("content edit keeps total at 3 (re-mint + prune)", len(atoms8) == 3, f"got {len(atoms8)}")
        check("old alpha atom pruned", not (tmp / "atoms" / p_alpha.name).exists())
        check("exactly one alpha atom remains",
              sum("Smoke atom alpha" in p.read_text() for p in atoms8) == 1)
        check("prune reported (pruned=1)", "pruned=1" in out8)

        # 9. Removing a block prunes its atom and scrubs the source back-ref.
        print("== 9. block removal prunes + scrubs back-ref ==")
        p_gamma, t_gamma = atom_by_title(tmp, "Smoke atom gamma")
        id_gamma = re.search(r"id: (ATOM-\S+)", t_gamma).group(1)
        src.write_text(src.read_text().replace(EXTRA_ATOM.strip(), ""), encoding="utf-8")
        run(tmp)
        atoms9 = list((tmp / "atoms").glob("ATOM-*.md"))
        check("removing a block prunes its atom (3->2)", len(atoms9) == 2, f"got {len(atoms9)}")
        check("gamma atom gone",
              not any("Smoke atom gamma" in p.read_text() for p in atoms9))
        check("source back-ref scrubbed of pruned atom", id_gamma not in src.read_text())

        # 10. --no-prune retains orphans; --dry-run prune writes nothing.
        print("== 10. --no-prune + dry-run prune ==")
        src.write_text(src.read_text().replace(
            "First smoke atom body, revised.", "First smoke atom body, revised twice."),
            encoding="utf-8")
        before10 = len(list((tmp / "atoms").glob("ATOM-*.md")))  # 2
        run(tmp, "--no-prune")
        after10 = len(list((tmp / "atoms").glob("ATOM-*.md")))
        check("--no-prune retains orphan (re-mint grows 2->3)",
              after10 == before10 + 1, f"{before10}->{after10}")
        out_dry = run(tmp, "--dry-run")
        check("dry-run prune writes nothing",
              len(list((tmp / "atoms").glob("ATOM-*.md"))) == after10)
        check("dry-run reports would-prune (pruned=1)", "pruned=1" in out_dry)
        run(tmp)  # default prune cleans the orphan left by --no-prune
        check("default prune cleans orphan after --no-prune",
              len(list((tmp / "atoms").glob("ATOM-*.md"))) == 2)

        # 11. Empty-scan guard: no sources must never wipe the atom store.
        print("== 11. empty-scan guard ==")
        src.unlink()
        out11 = run(tmp)
        check("empty scan keeps atoms intact",
              len(list((tmp / "atoms").glob("ATOM-*.md"))) == 2)
        check("empty scan logs guard", "prune=skipped(no-sources)" in out11)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    llm_smoke()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


# Stub "model": ignores stdin, prints a fixed ::atom block. Stands in for a
# real LLM/CLI backend so the llm extractor path is exercised offline.
STUB_MODEL = '''\
import sys
sys.stdin.read()
print("""preamble the model rambles
::atom
type: insight
title: LLM-extracted atom
tags: [llm, smoke]
source_location: "auto"
confidence: 0.8
---
Body the model produced.
::end
trailing chatter""")
'''

LLM_SOURCE = """\
---
title: LLM Source
origin: smoke-test
ingested: 2026-01-01
reliability: 0.9
summary: Source with no hand-authored atoms; the llm extractor mints them.
tags: [smoke]
---

Free-form prose with no ::atom markers. The configured model invents the atoms.
"""


def llm_smoke() -> None:
    """End-to-end llm extractor via a stub CLI backend: config-file load,
    extraction, and cross-process cache idempotency."""
    tmp = Path(tempfile.mkdtemp(prefix="kos-smoke-llm-"))
    try:
        for d in ("sources", "atoms", "theses", "projects", "indexes", "logs",
                  "scripts", "config"):
            (tmp / d).mkdir(parents=True)
        shutil.copy(REAL_INGEST, tmp / "scripts" / "ingest.py")
        (tmp / "scripts" / "stub_model.py").write_text(STUB_MODEL, encoding="utf-8")
        (tmp / "sources" / "llm.md").write_text(LLM_SOURCE, encoding="utf-8")
        (tmp / "config" / "extractor.json").write_text(json.dumps({
            "extractor": "llm",
            "backend": "cli",
            "cli": {"cmd": [sys.executable, str(tmp / "scripts" / "stub_model.py")]},
        }), encoding="utf-8")

        print("== 7. llm extractor (stub backend) ==")
        out = run(tmp)
        check("llm config selected", "extractor=llm" in out)
        atoms = list((tmp / "atoms").glob("ATOM-*.md"))
        check("llm extractor minted 1 atom", len(atoms) == 1, f"got {len(atoms)}")
        if atoms:
            check("atom carries model-supplied content",
                  "LLM-extracted atom" in atoms[0].read_text(encoding="utf-8"))
        check("extraction cached", bool(list((tmp / ".cache" / "extract").glob("*.json"))))

        # Re-run: cache hit + hash dedupe → no new atoms (idempotent).
        out2 = run(tmp)
        atoms2 = list((tmp / "atoms").glob("ATOM-*.md"))
        check("llm re-run creates 0 new atoms", len(atoms2) == 1, f"got {len(atoms2)}")
        check("llm re-run reports skipped=1", "skipped=1" in out2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
