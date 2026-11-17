"""Tools Gemma can call. Add a .py file in tools/ with a TOOLS list.

A tool is a function with type hints and a docstring:

    def my_tool(query: str) -> str:
        \"\"\"What this tool does, in one sentence.\"\"\"
        return "result"

    TOOLS = ["my_tool"]
"""
import importlib.util
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent / "tools"


def _load():
    found = []
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"lbtool_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in getattr(mod, "TOOLS", []):
            found.append(getattr(mod, name))
    return found


tools = _load()
system_instruction = (
    "You are a local offline assistant on this phone. "
    "For a recipe, or a question about food, cooking, survival, health, water, shelter, repairs, or power, "
    "call search_library before you answer. "
    "The library includes Lastbook and any cookbook downloaded in Fieldbook. "
    "Base the answer on the tool result, cite the document id and page, "
    "and say when the pages do not cover it. "
    "Call read_page when you need more of a page that search already found. "
    "Call search_folders for notes the person added, and current_time only for the time."
)
