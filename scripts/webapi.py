#!/usr/bin/env python3
"""webapi.py — logic layer behind the KOS web UI.

Pure functions over the file-based knowledge store. No HTTP here (see
serve.py); no parsing/extraction reimplemented either — everything reuses the
CLI engine so the GUI behaves identically to `ingest.py` / `kos.py`:

  read   — list/get/search entities, reverse-compute atom links, preview
           extraction (maps to `ingest --dry-run`).
  write  — add a source (one or many, like `kos add`), create/edit theses and
           projects, then rebuild every index via `ingest.main([])`.

Indexes are never written here directly — they are derived. Mutations edit
entity frontmatter then re-run ingest, honouring the engine's invariants.
"""
from __future__ import annotations

import sys
import threading
from datetime import date
from pathlib import Path

# Sibling engine modules. kos already wires ingest onto sys.path; do the same so
# `import ingest` / `import kos` resolve no matter the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402
import kos  # noqa: E402

# Serializes every mutating operation. Single-user tool: writes never overlap,
# and the shared `kos.INSECURE` global stays consistent within an add.
_LOCK = threading.Lock()

SUPPORTED_TYPES = sorted(kos._TYPE_LOADERS)  # extensible — surfaced to the UI
UPLOAD_EXTS = [".md", ".markdown", ".txt", ".html", ".htm", ".epub", ".docx",
               ".xml", ".rss", ".atom"]
THESIS_STATUSES = ["active", "confirmed", "challenged", "archived"]
PROJECT_STATUSES = ["active", "done", "paused", "archived"]


# ---------------------------------------------------------------------------
# Entity → JSON-safe dict.
# ---------------------------------------------------------------------------
def _entity(fm: dict) -> dict:
    """Convert a loaded entity (frontmatter + `_path`/`_body`) to a plain dict."""
    out = {k: v for k, v in fm.items() if not k.startswith("_")}
    out["body"] = fm.get("_body", "")
    out["path"] = ingest._rel(fm["_path"]) if fm.get("_path") else ""
    return out


def _by_id(entities: list[dict]) -> dict[str, dict]:
    return {str(e.get("id")): e for e in entities if e.get("id")}


def _sort_recent(entities: list[dict], date_key: str) -> list[dict]:
    return sorted(entities, key=lambda e: (str(e.get(date_key, "")),
                                           str(e.get("id", ""))), reverse=True)


# ---------------------------------------------------------------------------
# Reads.
# ---------------------------------------------------------------------------
def stats(recent: int = 8) -> dict:
    atoms = ingest.load_entities(ingest.ATOMS)
    sources = ingest.load_entities(ingest.SOURCES)
    theses = ingest.load_entities(ingest.THESES)
    projects = ingest.load_entities(ingest.PROJECTS)
    by_tag: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for a in atoms:
        for t in ingest._as_list(a.get("tags")):
            by_tag[t] = by_tag.get(t, 0) + 1
        by_type[str(a.get("type", "fact"))] = by_type.get(str(a.get("type", "fact")), 0) + 1
    return {
        "counts": {"sources": len(sources), "atoms": len(atoms),
                   "theses": len(theses), "projects": len(projects),
                   "tags": len(by_tag)},
        "by_type": by_type,
        "recent_atoms": [_entity(a) for a in _sort_recent(atoms, "created")[:recent]],
        "recent_sources": [_entity(s) for s in _sort_recent(sources, "ingested")[:recent]],
    }


def _matches_query(a: dict, q: str) -> bool:
    hay = " ".join([
        str(a.get("title", "")), a.get("_body", ""),
        " ".join(ingest._as_list(a.get("tags"))),
    ]).lower()
    return q.lower() in hay


def list_atoms(tag: str = "", type: str = "", source: str = "",
               q: str = "") -> list[dict]:
    out = []
    for a in ingest.load_entities(ingest.ATOMS):
        if tag and tag not in ingest._as_list(a.get("tags")):
            continue
        if type and str(a.get("type")) != type:
            continue
        if source and str(a.get("source")) != source:
            continue
        if q and not _matches_query(a, q):
            continue
        out.append(_entity(a))
    return out


def _reverse_links(atom_id: str, theses: list[dict],
                   projects: list[dict]) -> tuple[list, list]:
    """Engine leaves atom `linked_*` frontmatter empty; compute the back-links
    as a read-time projection by scanning theses and projects."""
    th = []
    for t in theses:
        sup = ingest._as_list(t.get("supporting_atoms"))
        con = ingest._as_list(t.get("contradicting_atoms"))
        if atom_id in sup or atom_id in con:
            th.append({"id": t.get("id"), "title": t.get("title"),
                       "relation": "supporting" if atom_id in sup else "contradicting"})
    pr = [{"id": p.get("id"), "title": p.get("title")} for p in projects
          if atom_id in ingest._as_list(p.get("linked_atoms"))]
    return th, pr


def get_atom(atom_id: str) -> dict | None:
    atoms = _by_id(ingest.load_entities(ingest.ATOMS))
    fm = atoms.get(atom_id)
    if not fm:
        return None
    out = _entity(fm)
    th, pr = _reverse_links(atom_id, ingest.load_entities(ingest.THESES),
                            ingest.load_entities(ingest.PROJECTS))
    out["linked_theses"] = th
    out["linked_projects"] = pr
    src = _by_id(ingest.load_entities(ingest.SOURCES)).get(str(fm.get("source")))
    out["source_title"] = src.get("title") if src else None
    return out


def get_source(source_id: str) -> dict | None:
    fm = _by_id(ingest.load_entities(ingest.SOURCES)).get(source_id)
    if not fm:
        return None
    out = _entity(fm)
    out["atoms"] = [_entity(a) for a in ingest.load_entities(ingest.ATOMS)
                    if str(a.get("source")) == source_id]
    return out


def _resolve_atoms(ids: list[str], atoms_by_id: dict) -> list[dict]:
    res = []
    for aid in ids:
        a = atoms_by_id.get(aid)
        res.append(_entity(a) if a else {"id": aid, "title": aid, "missing": True})
    return res


def get_thesis(thesis_id: str) -> dict | None:
    fm = _by_id(ingest.load_entities(ingest.THESES)).get(thesis_id)
    if not fm:
        return None
    out = _entity(fm)
    atoms_by_id = _by_id(ingest.load_entities(ingest.ATOMS))
    out["supporting"] = _resolve_atoms(ingest._as_list(fm.get("supporting_atoms")), atoms_by_id)
    out["contradicting"] = _resolve_atoms(ingest._as_list(fm.get("contradicting_atoms")), atoms_by_id)
    return out


def get_project(project_id: str) -> dict | None:
    fm = _by_id(ingest.load_entities(ingest.PROJECTS)).get(project_id)
    if not fm:
        return None
    out = _entity(fm)
    atoms_by_id = _by_id(ingest.load_entities(ingest.ATOMS))
    theses_by_id = _by_id(ingest.load_entities(ingest.THESES))
    out["atoms"] = _resolve_atoms(ingest._as_list(fm.get("linked_atoms")), atoms_by_id)
    out["theses"] = [
        _entity(theses_by_id[t]) if t in theses_by_id else {"id": t, "title": t, "missing": True}
        for t in ingest._as_list(fm.get("linked_theses"))
    ]
    return out


def list_theses() -> list[dict]:
    return [_entity(t) for t in ingest.load_entities(ingest.THESES)]


def list_projects() -> list[dict]:
    return [_entity(p) for p in ingest.load_entities(ingest.PROJECTS)]


def list_sources() -> list[dict]:
    out = []
    by_source: dict[str, int] = {}
    for a in ingest.load_entities(ingest.ATOMS):
        sid = str(a.get("source"))
        by_source[sid] = by_source.get(sid, 0) + 1
    for s in ingest.load_entities(ingest.SOURCES):
        d = _entity(s)
        d["atom_count"] = by_source.get(str(s.get("id")), 0)
        out.append(d)
    return out


def tags() -> list[dict]:
    by_tag: dict[str, int] = {}
    for a in ingest.load_entities(ingest.ATOMS):
        for t in ingest._as_list(a.get("tags")):
            by_tag[t] = by_tag.get(t, 0) + 1
    return [{"tag": t, "count": by_tag[t]} for t in sorted(by_tag)]


def search(q: str) -> dict:
    q = (q or "").strip()
    if not q:
        return {"atoms": [], "sources": [], "theses": [], "projects": []}
    ql = q.lower()

    def title_hit(entities):
        return [_entity(e) for e in entities if ql in str(e.get("title", "")).lower()]

    return {
        "atoms": list_atoms(q=q),
        "sources": title_hit(ingest.load_entities(ingest.SOURCES)),
        "theses": title_hit(ingest.load_entities(ingest.THESES)),
        "projects": title_hit(ingest.load_entities(ingest.PROJECTS)),
    }


def preview_extraction(body: str) -> list[dict]:
    """Candidate atoms for a body, writing nothing (maps to ingest --dry-run)."""
    extractor = ingest.build_extractor(ingest.load_config(), write_cache=False)
    out = []
    for meta in extractor.extract(body or ""):
        out.append({
            "type": meta.get("type", "fact"),
            "title": str(meta.get("title", "")).strip(),
            "tags": ingest._as_list(meta.get("tags")),
            "source_location": meta.get("source_location", ""),
            "confidence": meta.get("confidence", ""),
            "body": meta.get("_body", ""),
        })
    return out


def config_info() -> dict:
    cfg = ingest.load_config()
    return {
        "extractor": cfg.get("extractor", "marker"),
        "supported_types": SUPPORTED_TYPES,
        "upload_exts": UPLOAD_EXTS,
        "thesis_statuses": THESIS_STATUSES,
        "project_statuses": PROJECT_STATUSES,
    }


# ---------------------------------------------------------------------------
# Writes — each rebuilds indexes via the engine, never by hand.
# ---------------------------------------------------------------------------
def _atom_ids() -> set[str]:
    return {str(a.get("id")) for a in ingest.load_entities(ingest.ATOMS)}


def _rebuild() -> None:
    ingest.main([])  # mint atoms (idempotent) + full index rebuild


def add_source(input: str, type: str | None = None, tags: str = "",
               title: str | None = None, reliability: float = 0.7,
               no_ingest: bool = False, insecure: bool = False,
               progress=None) -> dict:
    """Mirror of `kos add`. Returns a structured result; never raises for the
    expected failure modes (TLS, missing yt-dlp, unsupported type)."""
    def step(s):
        if progress:
            progress(s)

    with _LOCK:
        try:
            step("fetching")
            loader = kos.pick_loader(input, type)
            kos.INSECURE = insecure
            docs = loader.load(input)
        except SystemExit as e:
            return {"error": str(e.code) if e.code is not None else "failed"}
        except Exception as e:  # noqa: BLE001 — surface any loader failure to the UI
            return {"error": f"{type or 'auto'} loader failed: {e}"}
        finally:
            kos.INSECURE = False

        if not docs:
            return {"error": f"no content extracted from {input!r}"}

        extra_tags = [kos._slugify(t) for t in tags.split(",") if t.strip()]
        before = _atom_ids()
        written, empty_skipped = [], []
        step("writing")
        for meta, body in docs:
            if not (body or "").strip():
                empty_skipped.append(meta.get("title") or input)
                continue
            p = kos.write_source(meta, body, extra_tags, reliability,
                                 title if len(docs) == 1 else None)
            written.append(p)

        if not written:
            return {"error": "nothing written (all inputs had empty bodies)",
                    "empty_skipped": empty_skipped}

        result_sources = []
        if not no_ingest:
            step("extracting")
            _rebuild()
        # Re-read source frontmatter to report ingest-assigned ids/titles.
        for p in written:
            fm, _ = ingest.parse_frontmatter(p.read_text(encoding="utf-8"))
            result_sources.append({"id": fm.get("id"), "title": fm.get("title"),
                                   "path": ingest._rel(p)})

        new_ids = sorted(_atom_ids() - before)
        all_atoms = ingest.load_entities(ingest.ATOMS)
        atoms_by_id = _by_id(all_atoms)
        # Atoms attributed to the just-written sources. Lets the UI tell apart
        # "already captured" (source has atoms, none new) from "nothing extracted"
        # (source written but produced zero atoms — e.g. no ::atom markers in
        # marker mode, or the model emitted none).
        written_ids = {s["id"] for s in result_sources}
        source_atom_count = sum(1 for a in all_atoms
                                if str(a.get("source")) in written_ids)
        return {
            "sources": result_sources,
            "new_atoms": [_entity(atoms_by_id[i]) for i in new_ids if i in atoms_by_id],
            "new_count": len(new_ids),
            "source_atom_count": source_atom_count,
            "extractor": ingest.load_config().get("extractor", "marker"),
            "empty_skipped": empty_skipped,
            "no_ingest": no_ingest,
        }


def rebuild() -> dict:
    with _LOCK:
        _rebuild()
    return {"ok": True}


def delete_atom(atom_id: str) -> dict:
    """Delete one atom + scrub its back-refs, then rebuild indexes."""
    with _LOCK:
        if str(atom_id) not in _atom_ids():
            return {"error": f"atom {atom_id!r} not found"}
        removed = ingest.delete_atoms({atom_id})
        _rebuild()
    return {"ok": True, "deleted_atoms": removed}


def delete_source(source_id: str) -> dict:
    """Delete a source, the atoms it produced, and all references, then rebuild."""
    with _LOCK:
        result = ingest.delete_source(source_id)
        if result.get("error"):
            return result
        _rebuild()
    return {"ok": True, **result}


def _unique_path(directory: Path, base: str) -> tuple[str, Path]:
    slug, path = base, directory / f"{base}.md"
    n = 2
    while path.exists():
        slug = f"{base}-{n}"
        path = directory / f"{slug}.md"
        n += 1
    return slug, path


def _list_field(value) -> list:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _thesis_body(statement: str, reasoning: str) -> str:
    return (f"## Thesis Statement\n\n{statement.strip() or 'TODO'}\n\n"
            f"## Reasoning\n\n{reasoning.strip() or 'TODO'}\n")


def create_thesis(data: dict) -> dict:
    with _LOCK:
        title = (data.get("title") or "").strip()
        if not title:
            return {"error": "title is required"}
        ingest.THESES.mkdir(exist_ok=True)
        slug, path = _unique_path(ingest.THESES,
                                  f"THESIS-{kos._slugify(title, 'claim')}")
        today = date.today().isoformat()
        fm = {
            "id": slug, "title": title,
            "status": data.get("status", "active"),
            "confidence": data.get("confidence", "0.5"),
            "supporting_atoms": _list_field(data.get("supporting_atoms")),
            "contradicting_atoms": _list_field(data.get("contradicting_atoms")),
            "created": today, "updated": today,
        }
        path.write_text(ingest.dump_frontmatter(
            fm, _thesis_body(data.get("statement", ""), data.get("reasoning", ""))),
            encoding="utf-8")
        _rebuild()
        return {"id": slug}


def update_thesis(thesis_id: str, data: dict) -> dict:
    with _LOCK:
        path = ingest.THESES / f"{thesis_id}.md"
        if not path.exists():
            return {"error": f"thesis {thesis_id} not found"}
        fm, body = ingest.parse_frontmatter(path.read_text(encoding="utf-8"))
        for key in ("title", "status", "confidence"):
            if data.get(key) is not None:
                fm[key] = data[key]
        for key in ("supporting_atoms", "contradicting_atoms"):
            if data.get(key) is not None:
                fm[key] = _list_field(data[key])
        if data.get("statement") is not None or data.get("reasoning") is not None:
            body = _thesis_body(data.get("statement", ""), data.get("reasoning", ""))
        fm["updated"] = date.today().isoformat()
        path.write_text(ingest.dump_frontmatter(fm, body), encoding="utf-8")
        _rebuild()
        return {"id": thesis_id}


def _project_body(data: dict) -> str:
    def bullets(items, prefix="- "):
        items = _list_field(items)
        return "\n".join(f"{prefix}{i}" for i in items) if items else f"{prefix}TODO"
    return (
        f"## Objective\n\n{(data.get('objective') or 'TODO').strip()}\n\n"
        f"## Open Questions\n\n{bullets(data.get('open_questions'))}\n\n"
        f"## Decisions\n\n{bullets(data.get('decisions'))}\n\n"
        f"## Deliverables\n\n{bullets(data.get('deliverables'), '- [ ] ')}\n"
    )


def create_project(data: dict) -> dict:
    with _LOCK:
        title = (data.get("title") or "").strip()
        if not title:
            return {"error": "title is required"}
        ingest.PROJECTS.mkdir(exist_ok=True)
        slug, path = _unique_path(ingest.PROJECTS,
                                  f"PROJ-{kos._slugify(title, 'project')}")
        today = date.today().isoformat()
        fm = {
            "id": slug, "title": title,
            "status": data.get("status", "active"),
            "linked_atoms": _list_field(data.get("linked_atoms")),
            "linked_theses": _list_field(data.get("linked_theses")),
            "created": today, "updated": today,
        }
        path.write_text(ingest.dump_frontmatter(fm, _project_body(data)), encoding="utf-8")
        _rebuild()
        return {"id": slug}


def update_project(project_id: str, data: dict) -> dict:
    with _LOCK:
        path = ingest.PROJECTS / f"{project_id}.md"
        if not path.exists():
            return {"error": f"project {project_id} not found"}
        fm, body = ingest.parse_frontmatter(path.read_text(encoding="utf-8"))
        for key in ("title", "status"):
            if data.get(key) is not None:
                fm[key] = data[key]
        for key in ("linked_atoms", "linked_theses"):
            if data.get(key) is not None:
                fm[key] = _list_field(data[key])
        if any(data.get(k) is not None for k in
               ("objective", "open_questions", "decisions", "deliverables")):
            body = _project_body(data)
        fm["updated"] = date.today().isoformat()
        path.write_text(ingest.dump_frontmatter(fm, body), encoding="utf-8")
        _rebuild()
        return {"id": project_id}
