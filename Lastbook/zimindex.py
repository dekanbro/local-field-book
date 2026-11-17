"""Full-text index for ZIM files Fieldbook has downloaded.

A downloaded cookbook is one file. Chat cannot see it until the articles
are copied into this index. The index is rebuilt when a ZIM changes.
"""
import html
import html.parser
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

ZIM_DIR = Path("/sdcard/Documents/Lastbook/zim")
DB = Path.home() / ".local/share/fieldbook/zim.sqlite"
FILLER = set("recipe recipes cookbook library please need want make cook cooking dish meal".split())
NAMES = {
    "publicdomainrecipes.com": "Public Domain Recipes",
}


def _prefix(domain):
    if "publicdomainrecipes" in domain:
        return "pdr"
    stem = re.sub(r"[^a-z0-9]", "", domain.split(".")[0].lower())
    return (stem or "zim")[:8]


def _html_text(raw):
    class Pull(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "aside", "header", "footer", "noscript"):
                self.skip += 1
            if tag in ("p", "h1", "h2", "h3", "li", "br", "tr"):
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "aside", "header", "footer", "noscript") and self.skip:
                self.skip -= 1
            if tag in ("p", "li", "h1", "h2", "h3", "div"):
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    piece = raw
    for tag in ("article", "main"):
        match = re.search(rf"<{tag}\b[^>]*>(.*)</{tag}>", raw, re.I | re.S)
        if match and len(match.group(1)) > 200:
            piece = match.group(1)
            break
    pull = Pull()
    pull.feed(piece)
    lines = []
    for line in "".join(pull.parts).splitlines():
        line = " ".join(line.split())
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines).strip()


def _title_of(raw, fallback):
    match = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
    if not match:
        match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    if not match:
        return fallback
    text = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
    text = " ".join(text.split())
    return text or fallback


def _recipe_pages(root):
    """HTML articles dumped by zimdump. Tag lists and the front page are skipped."""
    exc = root / "_exceptions"
    if not exc.is_dir():
        return
    for path in exc.iterdir():
        if not path.is_file():
            continue
        url = urllib.parse.unquote(path.name).strip("/")
        parts = [p for p in url.split("/") if p]
        if len(parts) != 2 or parts[1] in ("tags", "categories", "index.html"):
            continue
        if parts[0].startswith("_"):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if "<html" not in raw.lower():
            continue
        body = _html_text(raw)
        if len(body) < 80:
            continue
        domain, slug = parts
        yield domain, slug, _title_of(raw, slug.replace("-", " ")), body


def _signature(zims):
    return [(str(p), p.stat().st_size, p.stat().st_mtime_ns) for p in zims]


def _current(con, sig):
    try:
        rows = con.execute("SELECT path, size, mtime FROM files ORDER BY path").fetchall()
    except sqlite3.OperationalError:
        return False
    return rows == [(p, s, int(m)) for p, s, m in sig]


def _index_one(zim, cur):
    tmp = tempfile.mkdtemp(prefix="fieldbook-zim-")
    try:
        proc = subprocess.run(
            ["zimdump", "dump", f"--dir={tmp}", str(zim)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.returncode not in (0, 2):
            raise RuntimeError(f"zimdump failed on {zim.name}")
        for domain, slug, title, body in _recipe_pages(Path(tmp)):
            doc_id = f"{_prefix(domain)}-{slug}"
            collection = NAMES.get(domain, domain)
            cur.execute(
                "INSERT OR REPLACE INTO docs (doc_id, title, collection, zim, url, body) VALUES (?,?,?,?,?,?)",
                (doc_id, title, collection, str(zim), f"{domain}/{slug}/", body),
            )
            cur.execute(
                "INSERT INTO docs_fts (doc_id, title, body) VALUES (?,?,?)",
                (doc_id, title, body),
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ensure():
    """Build the index when a ZIM is new or has changed. Returns the article count."""
    if not ZIM_DIR.is_dir() or shutil.which("zimdump") is None:
        return 0
    zims = sorted(p for p in ZIM_DIR.glob("*.zim") if p.is_file())
    if not zims:
        return 0
    DB.parent.mkdir(parents=True, exist_ok=True)
    sig = _signature(zims)
    con = sqlite3.connect(DB)
    try:
        if _current(con, sig):
            return con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        con.executescript(
            """
            DROP TABLE IF EXISTS files;
            DROP TABLE IF EXISTS docs;
            DROP TABLE IF EXISTS docs_fts;
            CREATE TABLE files (path TEXT PRIMARY KEY, size INTEGER, mtime INTEGER);
            CREATE TABLE docs (
                doc_id TEXT PRIMARY KEY,
                title TEXT,
                collection TEXT,
                zim TEXT,
                url TEXT,
                body TEXT
            );
            CREATE VIRTUAL TABLE docs_fts USING fts5(doc_id, title, body, tokenize='porter unicode61');
            """
        )
        for zim in zims:
            _index_one(zim, con)
        con.executemany("INSERT INTO files (path, size, mtime) VALUES (?,?,?)", [(p, s, int(m)) for p, s, m in sig])
        con.commit()
        return con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    finally:
        con.close()


def _connect():
    if not DB.is_file():
        return None
    return sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)


def _match(con, expr, limit):
    return con.execute(
        "SELECT doc_id, title, snippet(docs_fts, 2, '[', ']', '…', 24), bm25(docs_fts, 0, 8, 1) "
        "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY bm25(docs_fts, 0, 8, 1) LIMIT ?",
        (expr, limit),
    ).fetchall()


def search(terms, limit_docs=8):
    """Search indexed ZIMs. terms are already the content words."""
    try:
        ensure()
    except Exception:
        return []
    con = _connect()
    if con is None or not terms:
        return []
    safe = [t.replace('"', "") for t in terms if t.replace('"', "")]
    if not safe:
        return []

    def expr(words, op):
        return f" {op} ".join('"%s"' % w for w in words)

    rows = _match(con, expr(safe, "AND"), 40)
    if not rows:
        core = [w for w in safe if w.lower() not in FILLER]
        if core and core != safe:
            rows = _match(con, expr(core, "AND"), 40)
    if not rows and len(safe) > 1:
        rows = _match(con, expr(safe, "OR"), 40)
    grouped = {}
    for doc_id, title, snip, score in rows:
        rec = con.execute("SELECT collection FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
        collection = rec[0] if rec else ""
        grouped.setdefault(doc_id, [title, collection, score, []])
        grouped[doc_id][3].append((1, snip))
    ranked = sorted(grouped.items(), key=lambda kv: kv[1][2])
    return ranked[:limit_docs]


def body(doc_id):
    con = _connect()
    if con is None:
        return None
    row = con.execute("SELECT body FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
    return row[0] if row else None


def catalog():
    """Records in the same shape as a Lastbook catalog entry."""
    try:
        ensure()
    except Exception:
        return {}
    con = _connect()
    if con is None:
        return {}
    out = {}
    for doc_id, title, collection in con.execute("SELECT doc_id, title, collection FROM docs"):
        out[doc_id] = {
            "id": doc_id,
            "title": title,
            "kind": "text",
            "collection": collection,
            "path": "",
        }
    return out
