"""A tiny example tool. Copy this file to add another one."""
import datetime


def current_time() -> str:
    """Return the current local date and time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


TOOLS = ["current_time"]
