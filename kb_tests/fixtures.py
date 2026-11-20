"""Synthetic personal-KB fixtures. Never read real accounts or source history."""
from __future__ import annotations
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile


@contextmanager
def workspace():
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory)


def session(root: Path, *, text="Orca Pomodoro timer uses a focused work interval.",
            name="project/session.jsonl", timestamp="2026-11-04T12:00:00Z"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {"type": "user", "sessionId": "fixture-session", "timestamp": timestamp,
         "cwd": "/synthetic/public-project", "message": {"role": "user", "content": text}},
        {"type": "assistant", "sessionId": "fixture-session", "timestamp": timestamp,
         "message": {"role": "assistant", "content": [{"type": "text", "text": "Use --interval 25; preserve the original configuration."}]}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    return path


def row(content="Synthetic evidence", *, source_path="/synthetic/original.jsonl"):
    return {"kind": "raw", "ts": "2026-11-04T12:00:00Z", "title": "Synthetic work",
            "content": content, "metadata": {"path": source_path, "chunk": 0}}
