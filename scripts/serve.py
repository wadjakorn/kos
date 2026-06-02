#!/usr/bin/env python3
"""serve.py — stdlib web server for the KOS GUI.

Zero third-party deps (http.server). Serves the vanilla-JS front end in `web/`
and a small JSON API backed by `webapi.py`, which in turn reuses the CLI engine
(`ingest.py` / `kos.py`). Source adds run in a background thread tracked by an
in-memory job registry the client polls — feeds and YouTube transcripts can take
seconds, so the UI shows real progress instead of a frozen button.

    python3 scripts/serve.py [--port 8000] [--host 127.0.0.1]

Then open http://127.0.0.1:8000/.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import webapi

WEB = Path(__file__).resolve().parent.parent / "web"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".ico": "image/x-icon",
}

# job_id -> {"status": str, "result": dict|None, "error": str|None}
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


def _set_job(job_id: str, **fields) -> None:
    with _JOBS_LOCK:
        _JOBS.setdefault(job_id, {}).update(fields)


def _run_add_job(job_id: str, kwargs: dict, tmp_path: str | None) -> None:
    def progress(stage: str) -> None:
        _set_job(job_id, status=stage)

    try:
        result = webapi.add_source(progress=progress, **kwargs)
        if result.get("error"):
            _set_job(job_id, status="error", error=result["error"], result=result)
        else:
            _set_job(job_id, status="done", result=result, error=None)
    except Exception as e:  # noqa: BLE001 — last-resort guard; report, don't crash
        _set_job(job_id, status="error", error=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class Handler(BaseHTTPRequestHandler):
    server_version = "kos-serve/1.0"

    # -- response helpers ---------------------------------------------------
    def _json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self) -> None:
        self._json({"error": "not found"}, 404)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def log_message(self, fmt, *args):  # quieter default logging
        pass

    # -- GET ----------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            return self._api_get(path, parse_qs(parsed.query))
        return self._static(path)

    def _q1(self, query: dict, key: str, default: str = "") -> str:
        return query.get(key, [default])[0]

    def _api_get(self, path: str, query: dict):
        parts = path.strip("/").split("/")  # ['api', ...]
        rest = parts[1:]
        try:
            if rest == ["stats"]:
                return self._json(webapi.stats())
            if rest == ["config"]:
                return self._json(webapi.config_info())
            if rest == ["tags"]:
                return self._json(webapi.tags())
            if rest == ["search"]:
                return self._json(webapi.search(self._q1(query, "q")))
            if rest == ["atoms"]:
                return self._json(webapi.list_atoms(
                    tag=self._q1(query, "tag"), type=self._q1(query, "type"),
                    source=self._q1(query, "source"), q=self._q1(query, "q")))
            if rest == ["sources"]:
                return self._json(webapi.list_sources())
            if rest == ["theses"]:
                return self._json(webapi.list_theses())
            if rest == ["projects"]:
                return self._json(webapi.list_projects())
            if len(rest) == 2:
                kind, ident = rest[0], unquote(rest[1])
                getter = {"atoms": webapi.get_atom, "sources": webapi.get_source,
                          "theses": webapi.get_thesis, "projects": webapi.get_project}.get(kind)
                if getter:
                    obj = getter(ident)
                    return self._json(obj) if obj else self._not_found()
                if kind == "jobs":
                    with _JOBS_LOCK:
                        job = _JOBS.get(ident)
                    return self._json(job) if job else self._not_found()
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)
        return self._not_found()

    def _static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (WEB / rel).resolve()
        try:
            target.relative_to(WEB.resolve())  # block path traversal
        except ValueError:
            return self._not_found()
        if not target.is_file():
            # Unknown non-API path → SPA entry point.
            target = WEB / "index.html"
            if not target.is_file():
                return self._not_found()
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # -- POST / PUT ---------------------------------------------------------
    def do_POST(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        try:
            if path == "/api/sources/add":
                return self._add_source(query)
            if path == "/api/preview":
                return self._json(webapi.preview_extraction(self._read_json().get("body", "")))
            if path == "/api/ingest":
                return self._json(webapi.rebuild())
            if path == "/api/theses":
                return self._mutate(webapi.create_thesis(self._read_json()))
            if path == "/api/projects":
                return self._mutate(webapi.create_project(self._read_json()))
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)
        return self._not_found()

    def do_PUT(self):
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[0] == "api":
                kind, ident = parts[1], unquote(parts[2])
                if kind == "theses":
                    return self._mutate(webapi.update_thesis(ident, self._read_json()))
                if kind == "projects":
                    return self._mutate(webapi.update_project(ident, self._read_json()))
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)
        return self._not_found()

    def _mutate(self, result: dict):
        return self._json(result, 400 if result.get("error") else 200)

    def _add_source(self, query: dict):
        """JSON body (URL/feed/YouTube) or raw file bytes (upload via query meta)."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        tmp_path = None
        if ctype == "application/json":
            data = self._read_json()
            kwargs = {
                "input": data.get("input", ""),
                "type": data.get("type") or None,
                "tags": data.get("tags", ""),
                "title": data.get("title") or None,
                "reliability": float(data.get("reliability", 0.7)),
                "no_ingest": bool(data.get("no_ingest", False)),
                "insecure": bool(data.get("insecure", False)),
            }
            if not kwargs["input"].strip():
                return self._json({"error": "input is required"}, 400)
        else:
            # Raw file upload. Metadata rides in the query string.
            raw = self._read_body()
            filename = self._q1(query, "filename", "upload")
            suffix = Path(filename).suffix or ".txt"
            fd, tmp_path = tempfile.mkstemp(prefix="kos-upload-", suffix=suffix)
            with os.fdopen(fd, "wb") as f:
                f.write(raw)
            kwargs = {
                "input": tmp_path,
                "type": self._q1(query, "type") or None,
                "tags": self._q1(query, "tags"),
                "title": self._q1(query, "title") or Path(filename).stem,
                "reliability": float(self._q1(query, "reliability", "0.7")),
                "no_ingest": self._q1(query, "no_ingest") == "true",
                "insecure": False,
            }

        job_id = uuid.uuid4().hex
        _set_job(job_id, status="queued", result=None, error=None)
        threading.Thread(target=_run_add_job, args=(job_id, kwargs, tmp_path),
                         daemon=True).start()
        return self._json({"job_id": job_id}, 202)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KOS web server")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"KOS web UI → {url}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping…")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
