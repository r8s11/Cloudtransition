"""Workspace file I/O shared by readers and writers: YAML load, locked atomic write."""

import os
import tempfile
import threading
from pathlib import Path

import yaml


# ── YAML Loader ────────────────────────────────────────────────
def load_yaml(path: Path) -> dict:
    """Load a YAML file, return empty dict if missing or invalid."""
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


# One writer at a time for workspace markdown: toggle and capture both
# read-modify-write TASKS.md, and FastAPI runs sync handlers in a thread pool.
_FILE_WRITE_LOCK = threading.Lock()


def _atomic_write(target: Path, text: str) -> None:
    """Temp-file + os.replace: a crash mid-write never corrupts the source."""
    with tempfile.NamedTemporaryFile(
        "w", dir=target.parent, delete=False, suffix=".tmp"
    ) as tf:
        tf.write(text)
    os.replace(tf.name, target)
