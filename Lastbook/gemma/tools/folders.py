"""Search folders added from the Fieldbook library screen."""
import json
from pathlib import Path

FOLDERS = Path.home() / ".local/share/fieldbook/folders.json"
TEXT = {".txt", ".md", ".markdown"}


def search_folders(query: str) -> str:
    """Search text files in folders added in Fieldbook. Use this for notes the person added, not the Lastbook library."""
    try:
        rows = json.loads(FOLDERS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "No folders have been added."
    words = [w.lower() for w in query.split() if len(w) > 2]
    if not words:
        return "Give some words to search for."
    hits = []
    for row in rows:
        root = Path(row.get("path", ""))
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if len(hits) >= 6:
                break
            if not path.is_file() or path.suffix.lower() not in TEXT:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hay = text.lower()
            if all(w in hay for w in words):
                clip = " ".join(text.split())[:500]
                hits.append(f"{path}\n{clip}")
    if not hits:
        return "No matches in the added folders."
    return "\n\n".join(hits)


TOOLS = ["search_folders"]
