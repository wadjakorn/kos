#!/usr/bin/env python3
"""kos.py — source intake for the Knowledge Operating System.

Normalizes many input types into a `sources/<slug>.md` file (frontmatter +
plaintext body), then runs the ingest pipeline. One pluggable `Loader` per
type; adding a type is one subclass, no pipeline change.

Supported today:
    url / .html   — web page or local HTML        (stdlib)
    rss / atom    — feed, expands to one source per entry  (stdlib)
    .md / .txt    — markdown / plaintext           (stdlib)
    .epub         — book (zipped xhtml)            (stdlib)
    .docx         — Word doc (zipped xml)          (stdlib)
    youtube url   — video transcript via yt-dlp    (needs `yt-dlp` on PATH)

Usage:
    python3 scripts/kos.py add <input> [--tags a,b] [--title T]
                                       [--type url|feed|md|html|epub|docx|youtube]
                                       [--reliability 0.7] [--no-ingest]
    python3 scripts/kos.py add https://example.com/post --tags web,notes
    python3 scripts/kos.py add https://example.com/feed.xml --type feed
    python3 scripts/kos.py add paper.epub
"""
from __future__ import annotations

import argparse
import html
import html.parser
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

# Reuse the ingest engine's helpers + paths (sibling module).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

USER_AGENT = "kos-intake/1.0 (+https://github.com/; knowledge-base)"


# ---------------------------------------------------------------------------
# Text helpers.
# ---------------------------------------------------------------------------
def _localname(tag: str) -> str:
    """Strip an XML namespace: '{ns}title' -> 'title'."""
    return tag.rsplit("}", 1)[-1]


def _clean_text(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _slugify(value: str, fallback: str = "source") -> str:
    s = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (s or fallback)[:60].strip("-") or fallback


class _HTMLToText(html.parser.HTMLParser):
    """Strip tags to text; drop script/style; capture <title>."""

    _SKIP = {"script", "style", "noscript", "template"}
    _BREAK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
              "tr", "article", "section"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.title = ""
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in self._BREAK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in self._BREAK:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        self._parts.append(data)

    def text(self) -> str:
        return _clean_text("".join(self._parts))


def html_to_text(markup: str) -> tuple[str, str]:
    p = _HTMLToText()
    p.feed(markup)
    return p.title.strip(), p.text()


# ---------------------------------------------------------------------------
# Fetch.
# ---------------------------------------------------------------------------
INSECURE = False  # set by --insecure; skips TLS cert verification


def fetch(url: str) -> tuple[bytes, str]:
    ctx = ssl.create_default_context()
    if INSECURE:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=60, context=ctx)
    except urllib.error.URLError as e:
        # urlopen wraps the SSL cert error inside URLError.reason.
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            raise SystemExit(
                f"TLS certificate verification failed for {url}.\n"
                "  Your Python has no CA certificates. Fix it once:\n"
                "    /Applications/Python\\ 3.11/Install\\ Certificates.command\n"
                "  Or bypass for a trusted/self-hosted host: re-run with --insecure."
            )
        raise SystemExit(f"failed to fetch {url}: {e.reason}")
    with resp:
        raw = resp.read()
        ctype = resp.headers.get_content_type()
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw, ctype, charset  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Loaders — each returns a list of (metadata, text) docs.
# ---------------------------------------------------------------------------
class Loader:
    def load(self, src: str) -> list[tuple[dict, str]]:
        raise NotImplementedError


class UrlLoader(Loader):
    """Web page. Sniffs for a feed and delegates to FeedLoader if so."""

    def load(self, src):
        raw, ctype, charset = fetch(src)
        text = raw.decode(charset, errors="replace")
        head = text.lstrip()[:512].lower()
        if "xml" in ctype and ("<rss" in head or "<feed" in head) or \
           "rss" in ctype or "atom" in ctype:
            return FeedLoader().parse(text, src)
        title, body = html_to_text(text)
        return [({"title": title or src, "origin": src}, body)]


class HtmlFileLoader(Loader):
    def load(self, src):
        title, body = html_to_text(Path(src).read_text(encoding="utf-8", errors="replace"))
        return [({"title": title or Path(src).stem, "origin": str(src)}, body)]


class FeedLoader(Loader):
    """RSS or Atom. Expands to one source per entry."""

    def load(self, src):
        if src.startswith(("http://", "https://")):
            raw, _, charset = fetch(src)
            return self.parse(raw.decode(charset, errors="replace"), src)
        return self.parse(Path(src).read_text(encoding="utf-8", errors="replace"), str(src))

    def parse(self, xml_text: str, origin: str) -> list[tuple[dict, str]]:
        root = ET.fromstring(xml_text)
        docs = []
        # RSS: channel/item ; Atom: feed/entry
        items = [e for e in root.iter() if _localname(e.tag) in ("item", "entry")]
        for it in items:
            title = link = ""
            tags, body_parts = [], []
            for child in it:
                name = _localname(child.tag)
                if name == "title":
                    title = (child.text or "").strip()
                elif name == "link":
                    link = (child.get("href") or child.text or "").strip()
                elif name in ("description", "summary", "content", "encoded"):
                    body_parts.append(child.text or "")
                elif name in ("category", "subject"):
                    val = (child.get("term") or child.text or "").strip()
                    if val:
                        tags.append(_slugify(val))
            _, body = html_to_text("".join(body_parts))
            meta = {"title": title or link or origin,
                    "origin": link or origin, "tags": tags}
            docs.append((meta, body))
        return docs


class MarkdownLoader(Loader):
    def load(self, src):
        text = Path(src).read_text(encoding="utf-8", errors="replace")
        fm, body = ingest.parse_frontmatter(text)
        meta = {"title": fm.get("title") or Path(src).stem,
                "origin": str(src)}
        for k in ("tags", "summary", "reliability"):
            if fm.get(k):
                meta[k] = fm[k]
        return [(meta, body)]


class EpubLoader(Loader):
    """EPUB = zipped XHTML. Reads spine order from the OPF, strips each doc."""

    def load(self, src):
        with zipfile.ZipFile(src) as z:
            container = ET.fromstring(z.read("META-INF/container.xml"))
            opf_path = next(
                e.get("full-path") for e in container.iter()
                if _localname(e.tag) == "rootfile"
            )
            opf = ET.fromstring(z.read(opf_path))
            base = opf_path.rsplit("/", 1)[0] if "/" in opf_path else ""
            title, tags, manifest = "", [], {}
            for e in opf.iter():
                n = _localname(e.tag)
                if n == "title" and not title:
                    title = (e.text or "").strip()
                elif n == "subject" and e.text:
                    tags.append(_slugify(e.text))
                elif n == "item":
                    manifest[e.get("id")] = e.get("href")
            order = [manifest.get(ref.get("idref")) for ref in opf.iter()
                     if _localname(ref.tag) == "itemref"]
            parts = []
            for href in order:
                if not href:
                    continue
                path = f"{base}/{href}" if base else href
                try:
                    _, body = html_to_text(z.read(path).decode("utf-8", "replace"))
                    parts.append(body)
                except KeyError:
                    continue
        meta = {"title": title or Path(src).stem, "origin": str(src), "tags": tags}
        return [(meta, _clean_text("\n\n".join(parts)))]


class DocxLoader(Loader):
    """DOCX = zipped XML. Extracts paragraph text from word/document.xml."""

    def load(self, src):
        with zipfile.ZipFile(src) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            title = Path(src).stem
            try:
                core = ET.fromstring(z.read("docProps/core.xml"))
                for e in core.iter():
                    if _localname(e.tag) == "title" and (e.text or "").strip():
                        title = e.text.strip()
                        break
            except KeyError:
                pass
        lines, buf = [], []
        for e in doc.iter():
            n = _localname(e.tag)
            if n == "t":
                buf.append(e.text or "")
            elif n == "p":
                lines.append("".join(buf))
                buf = []
        if buf:
            lines.append("".join(buf))
        return [({"title": title, "origin": str(src)}, _clean_text("\n".join(lines)))]


class YouTubeLoader(Loader):
    """Video transcript via yt-dlp (must be on PATH). Pulls English subs."""

    def load(self, src):
        if not shutil.which("yt-dlp"):
            raise SystemExit(
                "youtube loader needs yt-dlp on PATH — install it "
                "(pip install yt-dlp) or pass a different source"
            )
        title = subprocess.run(
            ["yt-dlp", "--skip-download", "--get-title", src],
            capture_output=True, text=True,
        ).stdout.strip() or src
        tmp = Path(tempfile.mkdtemp(prefix="kos-yt-"))
        try:
            subprocess.run(
                ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
                 "--sub-langs", "en.*", "--sub-format", "vtt",
                 "-o", str(tmp / "sub"), src],
                capture_output=True, text=True, timeout=300,
            )
            vtts = list(tmp.glob("*.vtt"))
            if not vtts:
                raise SystemExit(f"no English subtitles found for {src}")
            body = _vtt_to_text(vtts[0].read_text(encoding="utf-8", errors="replace"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return [({"title": title, "origin": src, "tags": ["video"]}, body)]


def _vtt_to_text(vtt: str) -> str:
    out, seen = [], set()
    for line in vtt.splitlines():
        line = line.strip()
        if (not line or line == "WEBVTT" or "-->" in line
                or line.isdigit() or line.startswith(("NOTE", "Kind:", "Language:"))):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # strip inline cue tags
        if line and line not in seen:        # caption rolls repeat lines
            seen.add(line)
            out.append(line)
    return _clean_text("\n".join(out))


# ---------------------------------------------------------------------------
# Dispatch.
# ---------------------------------------------------------------------------
_EXT_LOADERS = {
    ".md": MarkdownLoader, ".markdown": MarkdownLoader, ".txt": MarkdownLoader,
    ".html": HtmlFileLoader, ".htm": HtmlFileLoader,
    ".xml": FeedLoader, ".rss": FeedLoader, ".atom": FeedLoader,
    ".epub": EpubLoader, ".docx": DocxLoader,
}
_TYPE_LOADERS = {
    "url": UrlLoader, "feed": FeedLoader, "md": MarkdownLoader,
    "html": HtmlFileLoader, "epub": EpubLoader, "docx": DocxLoader,
    "youtube": YouTubeLoader,
}


def _is_youtube(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", url, re.I))


def pick_loader(src: str, type_override: str | None) -> Loader:
    if type_override:
        return _TYPE_LOADERS[type_override]()
    if src.startswith(("http://", "https://")):
        return YouTubeLoader() if _is_youtube(src) else UrlLoader()
    ext = Path(src).suffix.lower()
    if ext in _EXT_LOADERS:
        return _EXT_LOADERS[ext]()
    raise SystemExit(
        f"unsupported source {src!r}. Supported: url, feed, .md/.txt, .html, "
        f".epub, .docx, youtube. Use --type to force."
    )


# ---------------------------------------------------------------------------
# Source-file writer.
# ---------------------------------------------------------------------------
def write_source(meta: dict, body: str, extra_tags: list[str],
                 reliability: float, title_override: str | None) -> Path:
    title = title_override or meta.get("title") or "Untitled"
    tags = sorted(set(ingest._as_list(meta.get("tags")) + extra_tags))
    fm = {
        "title": title,
        "origin": meta.get("origin", ""),
        "ingested": date.today().isoformat(),
        "reliability": meta.get("reliability", reliability),
        "summary": meta.get("summary", ""),
        "tags": tags,
    }
    slug = _slugify(title, fallback="source")
    path = ingest.SOURCES / f"{slug}.md"
    # Distinct origin under same slug → suffix so we don't clobber.
    if path.exists():
        prev, _ = ingest.parse_frontmatter(path.read_text(encoding="utf-8"))
        if prev.get("origin") and prev.get("origin") != fm["origin"]:
            slug = f"{slug}-{ingest.content_hash(fm['origin'])[:6]}"
            path = ingest.SOURCES / f"{slug}.md"
    ingest.SOURCES.mkdir(exist_ok=True)
    path.write_text(ingest.dump_frontmatter(fm, body or ""), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KOS source intake")
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add a source and ingest it")
    add.add_argument("input", help="url, feed, or file path")
    add.add_argument("--type", choices=sorted(_TYPE_LOADERS), help="force loader type")
    add.add_argument("--tags", default="", help="comma-separated tags to attach")
    add.add_argument("--title", help="override inferred title")
    add.add_argument("--reliability", type=float, default=0.7, help="0-1 source trust")
    add.add_argument("--no-ingest", action="store_true", help="write source, skip ingest")
    add.add_argument("--insecure", action="store_true",
                     help="skip TLS cert verification (trusted/self-hosted hosts only)")
    args = ap.parse_args(argv)

    global INSECURE
    INSECURE = args.insecure
    extra_tags = [_slugify(t) for t in args.tags.split(",") if t.strip()]
    loader = pick_loader(args.input, args.type)
    docs = loader.load(args.input)
    if not docs:
        raise SystemExit(f"no content extracted from {args.input!r}")

    written = []
    for meta, body in docs:
        if not (body or "").strip():
            print(f"  [skip] empty body: {meta.get('title')!r}")
            continue
        p = write_source(meta, body, extra_tags, args.reliability,
                         args.title if len(docs) == 1 else None)
        written.append(p)
        print(f"  [source] {p.relative_to(ingest.ROOT).as_posix()}  ({len(body)} chars)")

    if not written:
        raise SystemExit("nothing written")
    print(f"\n{len(written)} source(s) written to sources/")

    if args.no_ingest:
        print("--no-ingest: skipping pipeline. Run `python3 scripts/ingest.py` later.")
        return 0
    print("\n== running ingest ==")
    return ingest.main([])


if __name__ == "__main__":
    sys.exit(main())
