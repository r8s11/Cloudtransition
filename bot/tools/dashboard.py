#!/usr/bin/env python3
"""Read live Command Center state for the Brain assistant. Read-only, loopback-only.

    python3 tools/dashboard.py state [--include tasks,interviews,runs,missions,calendar]
                                     [--url http://127.0.0.1:8000]

Prints the endpoint JSON unchanged on stdout. Errors go to stderr as one line,
exit code 2. No writes, no credentials, no non-loopback hosts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import NoReturn
from urllib.parse import urlsplit

LOOPBACK = {"127.0.0.1", "localhost", "::1"}
DEFAULT_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8000")
SECTIONS = ("tasks", "interviews", "runs", "missions", "calendar")


def fail(message: str) -> NoReturn:
    sys.stderr.write(message + "\n")
    raise SystemExit(2)


def state(url: str, include: str) -> str:
    parts = urlsplit(url)
    if parts.hostname not in LOOPBACK or parts.scheme not in ("http", "https"):
        fail(f"refusing non-loopback URL {url}; Command Center state is loopback-only")
    wanted = [part.strip() for part in include.split(",") if part.strip()]
    unknown = [part for part in wanted if part not in SECTIONS]
    if unknown or not wanted:
        fail(f"unknown section: {', '.join(unknown) or include}")
    target = f"{parts.scheme}://{parts.netloc}/api/assistant/state?include={','.join(wanted)}"
    try:
        with urllib.request.urlopen(target, timeout=5) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        fail(f"Command Center at {url} answered {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}")
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        fail(f"Command Center is not running at {url} ({reason})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["state"])
    parser.add_argument("--include", default="tasks,interviews,runs,missions")
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()
    body = state(args.url, args.include)
    json.loads(body)  # never print a partial or non-JSON body
    sys.stdout.write(body)


if __name__ == "__main__":
    main()
