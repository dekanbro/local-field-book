#!/usr/bin/env python3
"""Fieldbook: offline chat, libraries and tools for the omalauncher app.

  fieldbook.py libs                 print the library board as JSON
  fieldbook.py ask "question"       ask Gemma, searching the libraries
  fieldbook.py fetch <id>           download a catalog entry that fits
  fieldbook.py add <folder>         add a folder of text as a knowledge base
  fieldbook.py remove <id>          drop an added folder from the list
"""
import datetime
import importlib.util
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/share/fieldbook"
ROOT = Path("/sdcard/Documents/Lastbook")
DATA = ROOT / "LastbookData" / "library-data"
MODEL = ROOT / "models" / "gemma-4-E2B-it.litertlm"
PRESET = ROOT / "gemma" / "preset.py"
TOOLS = ROOT / "gemma" / "tools"
LITERT = HOME / ".local/litert-venv/bin/litert-lm"
FOLDERS = STATE / "folders.json"
THREAD = STATE / "thread.json"
STATUS = STATE / "status.json"
LOG = STATE / "ask.log"
READING = STATE / "reading.json"

SMALL = 7691528852
SMALL_SHA = "bfe8b0b66d898cac18b7f979dd5e560b8fd653f03244b6186e0436306cf96291"
MODEL_BYTES = 2588147712
WIKIBOOKS_BYTES = 3544612812
WIKIBOOKS_SHA = "bda3410005656daeb523c81774e151b750cd5a8828f081ded0848cd7fdccba7c"
VIKIDIA_BYTES = 77565163
VIKIDIA_SHA = "16728e6be34081f6c627b3cbf2c36ff31823defb0f30b68fab146b5ca68e591e"
RECIPES_BYTES = 17143913
RECIPES_SHA = "dc1593da2f990c31b583b4d00e3219d8efae6f2f1f51629f2d3d5a79d4984839"
ZIM = ROOT / "zim"

CATALOG = [
    {
        "id": "lastbook-small",
        "name": "Lastbook Small",
        "blurb": "First aid, water, food, shelter and repairs. 148 documents and 41 videos.",
        "bytes": SMALL,
        "url": "https://downloads.lastbook.org/Lastbook-Small-20261113.zip",
        "sha256": SMALL_SHA,
        "zip": "Lastbook-Small-20261113.zip",
        "kind": "zip",
    },
    {
        "id": "wikibooks-en",
        "name": "English Wikibooks",
        "blurb": "Open textbooks, text only. School through college, October 2026.",
        "bytes": WIKIBOOKS_BYTES,
        "url": "https://download.kiwix.org/zim/wikibooks/wikibooks_en_all_nopic_2026-10.zim",
        "sha256": WIKIBOOKS_SHA,
        "file": "wikibooks_en_all_nopic_2026-10.zim",
        "kind": "zim",
    },
    {
        "id": "vikidia-en",
        "name": "Vikidia English",
        "blurb": "A children's encyclopedia, with pictures. Ages about 8 to 13, September 2026.",
        "bytes": VIKIDIA_BYTES,
        "url": "https://download.kiwix.org/zim/vikidia/vikidia_en_all_maxi_2026-09.zim",
        "sha256": VIKIDIA_SHA,
        "file": "vikidia_en_all_maxi_2026-09.zim",
        "kind": "zim",
    },
    {
        "id": "recipes-en",
        "name": "Public Domain Recipes",
        "blurb": "A plain English cookbook. Public-domain recipes, November 2026.",
        "bytes": RECIPES_BYTES,
        "url": "https://download.kiwix.org/zim/zimit/publicdomainrecipes.com_en_all_2026-11.zim",
        "sha256": RECIPES_SHA,
        "file": "publicdomainrecipes.com_en_all_2026-11.zim",
        "kind": "zim",
    },
    {
        "id": "lastbook-medium",
        "name": "Lastbook Medium",
        "blurb": "Small, plus the core videos, all documents and Wikibooks.",
        "bytes": 67492034038,
        "url": "https://downloads.lastbook.org/Lastbook-Medium.zip",
        "sha256": "",
        "zip": "Lastbook-Medium.zip",
        "kind": "skip",
    },
]


def now():
    return datetime.datetime.now().strftime("%H:%M")


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(path, value):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def free_bytes():
    return shutil.disk_usage("/").free


def gb(n):
    if n < 1e9:
        return f"{round(n / (1024 * 1024))} MB"
    return f"{n / 1e9:.1f} GB"


def status():
    return load(STATUS, {"busy": False, "step": "", "error": ""})


def set_status(**kw):
    cur = status()
    cur.update(kw)
    save(STATUS, cur)


def append_message(role, text, note="", sources=None):
    thread = load(THREAD, [])
    msg = {"role": role, "text": text.strip(), "note": note, "at": now()}
    if sources:
        msg["sources"] = sources
    thread.append(msg)
    save(THREAD, thread[-40:])


def tool_list():
    found = []
    if not TOOLS.is_dir():
        return found
    for path in sorted(TOOLS.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"fb_{path.stem}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for name in getattr(mod, "TOOLS", []):
                fn = getattr(mod, name)
                doc = (fn.__doc__ or "").strip().split("\n")[0]
                found.append({"name": name, "doc": doc, "file": path.name})
        except Exception as e:
            found.append({"name": path.stem, "doc": f"could not load: {e}", "file": path.name})
    return found


def installed_small():
    return (DATA / "catalog.json").is_file() and (DATA / "search.sqlite").is_file()


def library_dest(item):
    if item.get("kind") == "zim":
        return ZIM / item["file"]
    return ROOT / item["zip"]


def library_installed(item):
    if item.get("kind") == "zim":
        dest = library_dest(item)
        return dest.is_file() and dest.stat().st_size == item["bytes"]
    if item["id"] == "lastbook-small":
        return installed_small()
    return False


def library_room(item):
    # A zip needs room for the archive and the unpacked library.
    if item.get("kind") == "zim":
        return item["bytes"] + 500_000_000
    return item["bytes"] * 2 + 2 * 1e9


def progress_for(item_id):
    p = STATE / f"progress-{item_id}.json"
    if not p.is_file():
        return None
    age = time.time() - p.stat().st_mtime
    info = load(p, None)
    if not info:
        return None
    if age > 3600 and not info.get("busy"):
        return None
    return info


def board():
    free = free_bytes()
    libraries = []
    for item in CATALOG:
        got = progress_for(item["id"])
        installed = library_installed(item)
        need = library_room(item)
        offered = item.get("kind") in ("zip", "zim")
        if installed:
            note, action = "on this phone", ""
        elif not offered:
            note, action = f"needs {gb(need)} free", ""
        elif got and got.get("busy"):
            note, action = got.get("step") or "downloading", ""
        elif free < need:
            note, action = f"needs {gb(need)} free, {gb(free)} free", ""
        else:
            note, action = "", "download"
        libraries.append({
            "id": item["id"],
            "name": item["name"],
            "blurb": item["blurb"],
            "size": gb(item["bytes"]),
            "installed": installed,
            "note": note,
            "action": action,
        })
    model_got = progress_for("gemma-e2b")
    model_ok = MODEL.is_file() and MODEL.stat().st_size == MODEL_BYTES
    if model_ok:
        model_note, model_action = "on this phone", ""
    elif model_got and model_got.get("busy"):
        model_note, model_action = model_got.get("step") or "downloading", ""
    elif free < MODEL_BYTES + 1e9:
        model_note, model_action = f"needs {gb(MODEL_BYTES + 1e9)} free", ""
    else:
        model_note, model_action = gb(MODEL_BYTES), "download"
    folders = []
    for folder in load(FOLDERS, []):
        path = Path(folder.get("path", ""))
        folders.append({
            "id": folder.get("id", ""),
            "name": folder.get("name", path.name),
            "path": str(path),
            "note": "text files in this folder" if path.is_dir() else "folder is missing",
        })
    return {
        "free": gb(free),
        "model": {
            "id": "gemma-e2b",
            "name": "Gemma 4 E2B",
            "blurb": "The on-phone model. Runs on CPU. One question at a time.",
            "size": gb(MODEL_BYTES),
            "installed": model_ok,
            "note": model_note,
            "action": model_action,
        },
        "libraries": libraries,
        "folders": folders,
        "tools": tool_list(),
        "error": status().get("error") or "",
    }


def spawn(args):
    STATE.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "a", encoding="utf-8")
    env = os.environ.copy()
    env["FIELDBOOK_WORKER"] = "1"
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *args],
        env=env,
        start_new_session=True,
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd="/",
    )


def cmd_ask(prompt):
    prompt = prompt.strip()
    if not prompt:
        return
    if status().get("busy"):
        set_status(error="Still answering the last question.")
        return
    if not (MODEL.is_file() and LITERT.is_file()):
        append_message("user", prompt)
        append_message("assistant", "Gemma is not on this phone yet. Open library and download it.")
        set_status(busy=False, step="", error="", since=None)
        return
    append_message("user", prompt)
    set_status(busy=True, step="thinking", error="", since=time.time())
    spawn(["ask", prompt])


STEP_FOR_TOOL = {
    "search_library": "searching the library",
    "read_page": "reading a page",
    "search_folders": "searching your notes",
    "current_time": "checking the time",
}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _touch_step(step):
    cur = status()
    if cur.get("step") == step and cur.get("busy"):
        return
    cur["busy"] = True
    cur["step"] = step
    cur["error"] = ""
    save(STATUS, cur)


def _parse_answer(raw):
    """Drop the preset banner and tool logs. Keep the answer, including lines that start with '-'."""
    tools, lines = [], []
    header = True
    for line in raw.splitlines():
        line = _ANSI.sub("", line).strip("\r")
        if line.startswith("[tool_call]"):
            header = False
            try:
                tools.append(json.loads(line[len("[tool_call]"):].strip()).get("name", ""))
            except json.JSONDecodeError:
                tools.append("tool")
            continue
        if line.startswith("[tool_response]"):
            continue
        if header and (
            not line.strip()
            or line.startswith("Loading preset")
            or line.startswith("- System instruction")
            or line.startswith("- Tools:")
            or line.startswith("  - ")
        ):
            continue
        header = False
        lines.append(line)
    return "\n".join(lines).strip(), [t for t in tools if t]


def _watch_line(line):
    line = _ANSI.sub("", line).strip("\r")
    if line.startswith("[tool_call]"):
        try:
            name = json.loads(line[len("[tool_call]"):].strip()).get("name", "")
        except json.JSONDecodeError:
            name = ""
        _touch_step(STEP_FOR_TOOL.get(name, "using a tool"))
    elif line.startswith("[tool_response]"):
        _touch_step("thinking")
    elif line.strip() and not (
        line.startswith("Loading preset")
        or line.startswith("- System instruction")
        or line.startswith("- Tools:")
        or line.startswith("  - ")
    ):
        _touch_step("writing the answer")


def _read_pty(master, proc, on_line, timeout_s):
    buf = b""
    deadline = time.time() + timeout_s

    def take(chunk):
        nonlocal buf
        buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            on_line(raw.decode("utf-8", "replace"))

    while time.time() < deadline:
        if proc.poll() is not None:
            while True:
                ready, _, _ = select.select([master], [], [], 0.1)
                if not ready:
                    break
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    chunk = b""
                if not chunk:
                    break
                take(chunk)
            break
        ready, _, _ = select.select([master], [], [], 0.5)
        if not ready:
            continue
        try:
            chunk = os.read(master, 8192)
        except OSError:
            break
        if not chunk:
            break
        take(chunk)
    else:
        proc.kill()
        raise TimeoutError("Gemma took more than 10 minutes")
    if buf.strip():
        on_line(buf.decode("utf-8", "replace"))
    return proc.wait(timeout=10)


def _run_litert(prompt, on_line):
    import pty
    master, slave = pty.openpty()
    try:
        proc = subprocess.Popen(
            [
                str(LITERT), "run", str(MODEL),
                "--backend=cpu", "--cache=disk",
                "--max-num-tokens=4096", "--thinking=false",
                "--cpu-thread-count=4",
                "--preset", str(PRESET),
                "--prompt", prompt,
            ],
            stdin=subprocess.DEVNULL,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
        os.close(slave)
        slave = -1
        # Keep a copy of what was printed so the answer can be parsed after.
        captured = []

        def both(line):
            captured.append(line)
            on_line(line)

        code = _read_pty(master, proc, both, 600)
        return code, "\n".join(captured)
    finally:
        if slave >= 0:
            os.close(slave)
        os.close(master)


def run_ask(prompt):
    try:
        if not status().get("since"):
            set_status(busy=True, step="thinking", error="", since=time.time())
        _touch_step("loading Gemma")
        code, raw = _run_litert(prompt, _watch_line)
        text, tools = _parse_answer(raw)
        if code != 0 and not text:
            text = (raw or "Gemma stopped.").strip()[:2000]
        if not text:
            text = "No answer came back."
        note = "used " + ", ".join(tools) if tools else ""
        append_message("assistant", text[:8000], note, cited_sources(text, raw))
        set_status(busy=False, step="", error="", since=None)
    except Exception as e:
        append_message("assistant", f"Could not ask Gemma: {e}")
        set_status(busy=False, step="", error="", since=None)


def download(url, dest, expect=None, sha=None, label="file"):
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest
    item_id = label
    def tick(step):
        got = part.stat().st_size if part.is_file() else 0
        save(STATE / f"progress-{item_id}.json", {"busy": True, "step": step, "got": got})
    tick("starting")
    cmd = [
        "curl", "-L", "--fail", "--retry", "8", "--retry-delay", "3", "--retry-all-errors",
        "--continue-at", "-", "-o", str(dest), url,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        got = dest.stat().st_size if dest.is_file() else 0
        step = f"downloading {gb(got)}"
        if expect:
            step = f"downloading {gb(got)} of {gb(expect)}"
        save(STATE / f"progress-{item_id}.json", {"busy": True, "step": step, "got": got})
        time.sleep(2)
    if proc.returncode != 0:
        raise RuntimeError(f"download failed ({proc.returncode})")
    if expect and dest.stat().st_size != expect:
        raise RuntimeError(f"size is {dest.stat().st_size}, expected {expect}")
    if sha:
        import hashlib
        h = hashlib.sha256()
        with dest.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != sha:
            raise RuntimeError("checksum did not match")
    save(STATE / f"progress-{item_id}.json", {"busy": False, "step": "done", "got": dest.stat().st_size})


def run_fetch(item_id):
    try:
        if item_id == "gemma-e2b":
            download(
                "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm",
                MODEL, MODEL_BYTES, None, "gemma-e2b",
            )
            return
        item = next(x for x in CATALOG if x["id"] == item_id)
        if item.get("kind") not in ("zip", "zim"):
            raise RuntimeError("that library does not fit on this phone")
        if library_installed(item):
            return
        dest = library_dest(item)
        download(item["url"], dest, item["bytes"], item["sha256"] or None, item_id)
        if item.get("kind") == "zip":
            subprocess.run(["bsdtar", "-xf", str(dest), "-C", str(ROOT)], check=True)
            dest.unlink(missing_ok=True)
        if item.get("kind") == "zim":
            try:
                _lb().ensure_indexed()
            except Exception:
                pass
        save(STATE / f"progress-{item_id}.json", {"busy": False, "step": "installed", "got": item["bytes"]})
    except Exception as e:
        save(STATE / f"progress-{item_id}.json", {"busy": False, "step": str(e), "got": 0})
        set_status(error=str(e))


def cmd_add(path):
    folder = Path(path).expanduser()
    if not folder.is_dir():
        set_status(error=f"No folder at {folder}")
        return
    rows = load(FOLDERS, [])
    ident = str(folder)
    rows = [r for r in rows if r.get("path") != ident]
    rows.append({"id": ident, "name": folder.name or ident, "path": ident})
    save(FOLDERS, rows)
    set_status(error="")


def cmd_remove(ident):
    rows = [r for r in load(FOLDERS, []) if r.get("id") != ident and r.get("path") != ident]
    save(FOLDERS, rows)


_LIB = None
_IMG = re.compile(r"""<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.I)
_IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _lb():
    global _LIB
    if _LIB is None:
        spec = importlib.util.spec_from_file_location("lbsearch", ROOT / "lbsearch.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _LIB = mod
    return _LIB


def _args_of(call):
    if not isinstance(call, dict):
        return "", {}
    args = call.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return call.get("name") or "", args


def _pages_from_trace(raw, catalog):
    """Pages Gemma actually read, from the tool log."""
    found = {}
    for line in raw.splitlines():
        line = _ANSI.sub("", line).strip("\r")
        kind = None
        payload = None
        if line.startswith("[tool_call]"):
            kind, payload = "call", line[len("[tool_call]"):].strip()
        elif line.startswith("[tool_response]"):
            kind, payload = "response", line[len("[tool_response]"):].strip()
        else:
            continue
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if kind == "call":
            name, args = _args_of(payload)
            if name == "read_page" and args.get("doc_id") in catalog:
                try:
                    found.setdefault(args["doc_id"], int(args.get("page") or 0) or None)
                except (TypeError, ValueError):
                    found.setdefault(args["doc_id"], None)
            continue
        text = payload if isinstance(payload, str) else json.dumps(payload)
        current = None
        for row in text.splitlines():
            page_m = re.match(r"\[page (\d+)\]", row.strip())
            if page_m and current and current not in found:
                found[current] = int(page_m.group(1))
                continue
            id_m = re.match(r"(\S+) \| ", row)
            if id_m and id_m.group(1) in catalog:
                current = id_m.group(1)
                found.setdefault(current, None)
                continue
            both = re.search(r"\| (\S+) \| page (\d+) \|", row)
            if both and both.group(1) in catalog:
                found.setdefault(both.group(1), int(both.group(2)))
                current = both.group(1)
    return found


def _page_near(answer, start, doc_id):
    window = answer[max(0, start - 24): start + len(doc_id) + 32]
    match = re.search(r"(?:page|p\.)\s*(\d+)", window, re.I)
    return int(match.group(1)) if match else None


def cited_sources(answer, raw=""):
    """The library pages named in the answer, ready to open."""
    lb = _lb()
    catalog = lb.cat()
    from_tools = _pages_from_trace(raw, catalog)
    chosen = []
    seen = set()
    for match in re.finditer(r"(?<![\w-])([\w-]{6,})(?![\w-])", answer or ""):
        doc_id = match.group(1)
        if doc_id not in catalog:
            continue
        page = _page_near(answer, match.start(), doc_id) or from_tools.get(doc_id)
        key = (doc_id, page)
        if key in seen:
            continue
        seen.add(key)
        chosen.append((match.start(), doc_id, page))
        if len(chosen) >= 4:
            break
    if not chosen:
        for doc_id, page in from_tools.items():
            chosen.append((0, doc_id, page))
            if len(chosen) >= 3:
                break
    sources = []
    for _, doc_id, page in chosen:
        rec = catalog[doc_id]
        kind = rec.get("kind") or ""
        if kind == "zim":
            continue
        sources.append({
            "key": f"{doc_id}@{page or 0}",
            "id": doc_id,
            "title": rec.get("title") or doc_id,
            "kind": kind,
            "page": page or None,
        })
    return sources


def _images_for(rec):
    if rec.get("kind") != "html":
        return []
    path = _lb().LIB / rec.get("path", "")
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    found = []
    for src in _IMG.findall(text):
        if src.startswith(("http://", "https://", "data:")):
            continue
        dest = (path.parent / src).resolve()
        # Skip icons and drawings the page cannot show. A tiny file is a logo.
        if (
            dest.is_file()
            and dest.suffix.lower() in _IMG_EXT
            and dest.stat().st_size >= 15000
            and str(dest) not in found
        ):
            found.append(str(dest))
        if len(found) >= 8:
            break
    return found


def _html_text(path):
    """Words from the chapter, without the side menu or the page chrome."""
    import html.parser

    class Pull(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip = 0
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "aside", "header", "footer", "noscript"):
                self.skip += 1
            if tag in ("p", "h1", "h2", "h3", "h4", "li", "br", "tr"):
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "aside", "header", "footer", "noscript") and self.skip:
                self.skip -= 1
            if tag in ("p", "h1", "h2", "h3", "li", "div"):
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.skip:
                self.parts.append(data)

    raw = path.read_text(encoding="utf-8", errors="replace")
    # Prefer the article. The saved pages wrap a whole site menu around it.
    piece = raw
    for tag in ("article", "main"):
        match = re.search(rf"<{tag}\b[^>]*>(.*)</{tag}>", raw, re.I | re.S)
        if match and len(match.group(1)) > 400:
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


def build_reading(key):
    doc_id, _, page_s = (key or "").partition("@")
    page = int(page_s) if page_s.isdigit() and int(page_s) > 0 else None
    lb = _lb()
    rec = lb.cat().get(doc_id)
    if not rec:
        return {"key": key, "title": "page", "kind": "", "page": None, "path": "", "images": [], "text": "That page isn't in the library."}
    kind = rec.get("kind") or ""
    rel = rec.get("path") or ""
    file_path = lb.LIB / rel if rel else None
    path = str(file_path) if file_path and file_path.is_file() else ""
    text = ""
    if kind == "html" and file_path and file_path.is_file():
        text = _html_text(file_path)
    elif page:
        text = (lb.page_body(lb.connect(), doc_id, page) or "").strip()
        if not text:
            try:
                parts = lb.pages_of(doc_id)
                if 1 <= page <= len(parts):
                    text = parts[page - 1].strip()
            except SystemExit:
                text = ""
    if not text:
        text = "Open the file to read this one. The library has no extracted text for it."
    return {
        "key": f"{doc_id}@{page or 0}",
        "title": rec.get("title") or doc_id,
        "kind": kind,
        "page": page,
        "path": path,
        "images": _images_for(rec),
        "text": text[:8000],
    }


def cmd_read(key):
    save(READING, build_reading(key))


def main(argv):
    STATE.mkdir(parents=True, exist_ok=True)
    if not THREAD.is_file():
        save(THREAD, [])
    if not STATUS.is_file():
        save(STATUS, {"busy": False, "step": "", "error": ""})
    cmd = argv[1] if len(argv) > 1 else "libs"
    rest = argv[2:]
    worker = os.environ.get("FIELDBOOK_WORKER") == "1"
    if cmd == "libs":
        json.dump(board(), sys.stdout, ensure_ascii=False)
        print()
        return
    if cmd == "ask" and rest:
        text = " ".join(rest)
        if worker:
            run_ask(text)
        else:
            cmd_ask(text)
        return
    if cmd == "fetch" and rest:
        if worker:
            run_fetch(rest[0])
        else:
            spawn(["fetch", rest[0]])
        return
    if cmd == "add" and rest:
        cmd_add(" ".join(rest))
        return
    if cmd == "remove" and rest:
        cmd_remove(" ".join(rest))
        return
    if cmd == "read" and rest:
        cmd_read(rest[0])
        return
    sys.exit("use libs, ask, fetch, add, remove or read")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main(sys.argv)
