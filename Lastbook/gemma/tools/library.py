"""Library tools. Each public function listed in TOOLS is offered to Gemma."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("lbsearch", ROOT / "lbsearch.py")
lb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lb)


def search_library(query: str) -> str:
    """Search the offline library, including Lastbook and downloaded cookbooks. Use this before answering questions about recipes, food, water, health, shelter, repairs, or power. Returns document ids, titles, and short page excerpts."""
    hits = lb.search(query, limit_docs=5)
    if not hits:
        return "No matches."
    con = lb.connect()
    parts = []
    for doc_id, (title, collection, _score, pages) in hits:
        rec = lb.cat().get(doc_id, {})
        parts.append(f"{doc_id} | {title} | {collection} | file {rec.get('path', '')}")
        for page, _snip in pages[:2]:
            body = lb.page_body(con, doc_id, page).strip()
            if body:
                parts.append(f"[page {page}]\n{body[:1200]}")
        parts.append("")
    return "\n".join(parts)[:7000]


def read_page(doc_id: str, page: int) -> str:
    """Read one page from a Lastbook document. doc_id and page come from search_library."""
    con = lb.connect()
    body = lb.page_body(con, doc_id, int(page)).strip()
    if not body:
        return f"No text for {doc_id} page {page}."
    rec = lb.cat().get(doc_id, {})
    return f"{rec.get('title', doc_id)} | {doc_id} | page {page} | file {rec.get('path', '')}\n\n{body[:6000]}"


TOOLS = ["search_library", "read_page"]
