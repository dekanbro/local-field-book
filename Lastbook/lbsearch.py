#!/usr/bin/env python3
"""Offline keyword search for a Lastbook data folder. No network.

  lbsearch.py "boil water"
  lbsearch.py --prompt "how do I make drinking water safe"
  lbsearch.py page <id> <n>
  lbsearch.py doc <id>

Looks for library-data/ next to this script, then under LASTBOOK_DATA,
then under /sdcard/Documents/Lastbook. Prints passages Gemma can read.
"""
import json, os, re, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def find_lib():
    env = os.environ.get("LASTBOOK_DATA")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates += [HERE, HERE / "LastbookData", Path("/sdcard/Documents/Lastbook"),
                   Path("/sdcard/Documents/Lastbook/LastbookData")]
    for c in candidates:
        lib = c / "library-data" if (c / "library-data" / "catalog.json").is_file() else c
        if (lib / "catalog.json").is_file() and (lib / "search.sqlite").is_file():
            return lib
    sys.exit("No Lastbook library found. Unpack the Small pack, or set LASTBOOK_DATA to the folder that holds library-data/.")

LIB = find_lib()
DB = LIB / "search.sqlite"

def _zim():
    import importlib.util
    spec = importlib.util.spec_from_file_location("zimindex", HERE / "zimindex.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_cat = None
def cat():
    global _cat
    if _cat is None:
        rows = json.loads((LIB / "catalog.json").read_text(encoding="utf-8"))
        _cat = {r["id"]: r for r in rows}
        try:
            _cat.update(_zim().catalog())
        except Exception:
            pass
    return _cat

def pages_of(doc_id):
    r = cat()[doc_id]
    rel = r.get("text_path") or f"text/{doc_id}.txt"
    p = LIB / rel
    if not p.is_file():
        sys.exit(f"No extracted text for {doc_id} ({rel}).")
    t = p.read_text(encoding="utf-8", errors="replace")
    if r.get("kind") != "pdf" or "\n\f\n" in t:
        return t.split("\n\f\n") if "\n\f\n" in t else t.split("\f")
    return t.split("\f")

def connect():
    return sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)

def ensure_indexed():
    """Index downloaded ZIM files so search can read them."""
    return _zim().ensure()

STOP = set("a an the of to and in is are be for on with as by or that this it from at not can if your you when should may will have has which all but more they their each must do does how what who why where i me my we our".split())

def _terms(query):
    terms = re.findall(r"[\w-]+", query)
    content = [t for t in terms if t.lower() not in STOP]
    if len(content) >= 2:
        terms = content
    return terms

def _lastbook_search(terms, limit_docs):
    expr = " AND ".join('"%s"' % t.replace('"', "") for t in terms)
    con = connect()
    rows = con.execute(
        "SELECT doc_id, title, collection, page, "
        "snippet(pages, 6, '[', ']', '…', 24), "
        "bm25(pages, 0, 5, 2, 1, 0, 0, 1) AS s "
        "FROM pages WHERE pages MATCH ? ORDER BY s LIMIT 400",
        (expr,),
    ).fetchall()
    grouped = {}
    for doc_id, title, collection, page, snip, score in rows:
        if str(doc_id).startswith("metadata-"):
            continue
        grouped.setdefault(doc_id, [title, collection, score, []])
        grouped[doc_id][3].append((page, snip))
    return sorted(grouped.items(), key=lambda kv: kv[1][2])[:limit_docs]

def _merge(terms, lastbook, zim, limit_docs):
    """A cookbook whose title contains the query comes before Lastbook."""
    def covers(hit):
        title = (hit[1][0] or "").lower()
        return all(t.lower() in title for t in terms)
    front = [h for h in zim if covers(h)]
    rest = [h for h in zim if h not in front]
    out, seen = [], set()
    for group in (front, lastbook, rest):
        for hit in group:
            if hit[0] in seen:
                continue
            seen.add(hit[0])
            out.append(hit)
            if len(out) >= limit_docs:
                return out
    return out

def search(query, limit_docs=8):
    terms = _terms(query)
    if not terms:
        sys.exit("Give some words to search for.")
    lastbook = _lastbook_search(terms, limit_docs)
    try:
        zim = _zim().search(terms, limit_docs)
    except Exception:
        zim = []
    return _merge(terms, lastbook, zim, limit_docs)

def cmd_search(query):
    hits = search(query)
    if not hits:
        print("No matches.")
        return
    for doc_id, (title, collection, _score, ps) in hits:
        rec = cat().get(doc_id, {})
        kind = rec.get("kind", "")
        path = rec.get("path", "")
        pages = [p for p, _ in ps[:8]]
        print(f"{doc_id} | {kind} | {title} | {collection}")
        print(f"    file: {path}")
        print(f"    pages: {pages}")
        print("   ", ps[0][1].replace("\n", " ")[:240])
        print()

def cmd_page(doc_id, n, chars=4000):
    ps = pages_of(doc_id)
    n = int(n)
    if not 1 <= n <= len(ps):
        sys.exit(f"{doc_id} has {len(ps)} pages; there is no page {n}.")
    rec = cat().get(doc_id, {})
    print(f"# {rec.get('title', doc_id)}")
    print(f"# id {doc_id}  page {n} of {len(ps)}  file {rec.get('path', '')}")
    print(ps[n - 1][:chars])

def cmd_doc(doc_id):
    r = cat().get(doc_id)
    if not r:
        sys.exit(f"No record {doc_id}.")
    keep = ("id", "title", "kind", "publisher", "collection", "category", "path", "pages", "duration", "text_path")
    print(json.dumps({k: r.get(k) for k in keep}, indent=2))

def page_body(con, doc_id, page):
    try:
        found = _zim().body(doc_id)
    except Exception:
        found = None
    if found:
        return found
    row = con.execute(
        "SELECT body FROM pages WHERE doc_id=? AND page=? LIMIT 1",
        (doc_id, page),
    ).fetchone()
    return row[0] if row else ""

def cmd_prompt(query, docs=4, chars=1800):
    hits = search(query, limit_docs=docs)
    if not hits:
        print("No matches.")
        return
    con = connect()
    print("Answer only from the passages below. If they do not say, say you cannot tell from these pages. Cite the document id and page after each claim.")
    print()
    print(f"Question: {query}")
    print()
    for doc_id, (title, collection, _score, ps) in hits:
        rec = cat().get(doc_id, {})
        print(f"--- {doc_id} | {title} | {collection} | {rec.get('path', '')}")
        for page, _snip in ps[:2]:
            body = page_body(con, doc_id, page).strip()
            if not body:
                continue
            print(f"[page {page}]")
            print(body[:chars])
            print()

def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    if args[0] == "--prompt":
        if len(args) < 2:
            sys.exit(__doc__)
        cmd_prompt(" ".join(args[1:]))
    elif args[0] == "page" and len(args) >= 3:
        cmd_page(args[1], args[2], int(args[3]) if len(args) > 3 else 4000)
    elif args[0] == "doc" and len(args) >= 2:
        cmd_doc(args[1])
    else:
        cmd_search(" ".join(args))

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main(sys.argv)
