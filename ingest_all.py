#!/usr/bin/env python3
"""Read-only personal KB ingestion. Paid summarization is never implicit."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from kb_runtime import ROOT, RUNTIME, ingest_lock, load_env


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def run_all(conn, selected=None, *, runtime=RUNTIME):
    """Commit healthy sources even when another fails; log only safe counts/types."""
    from connectors import ingest_claude, ingest_gmail
    from kb_store import set_state
    selected = selected if selected is not None else {
        "claude": ingest_claude, "gmail": ingest_gmail,
    }
    outcomes = {}
    with ingest_lock(Path(runtime)):
        for source, function in selected.items():
            start = time.monotonic()
            attempted = timestamp()
            set_state(conn, source, "last_attempt", attempted)
            try:
                counts = function(conn)
                safe_counts = {str(k): v for k, v in counts.items()
                               if isinstance(v, (int, float, bool))}
                set_state(conn, source, "last_success", timestamp())
                set_state(conn, source, "last_error", None)
                outcomes[source] = {"status": "ok", "counts": safe_counts}
            except Exception as exc:
                # A remote exception can include credentials or private request text.
                # Log only safe categories/counts and whitelisted Google quota labels.
                conn.rollback()
                error_type = type(exc).__name__
                category = getattr(exc, "category", "error")
                record = {"type": error_type, "category": category, "at": attempted}
                if getattr(exc, "api_details", None):
                    record["api"] = exc.api_details
                set_state(conn, source, "last_error", record)
                outcomes[source] = {"status": "failed", "error": error_type}
                if record.get("api"):
                    outcomes[source]["api"] = record["api"]
                if getattr(exc, "counts", None):
                    outcomes[source]["counts"] = {
                        str(k): v for k, v in exc.counts.items() if isinstance(v, (int, float, bool))
                    }
                if source == "gmail":
                    outcomes[source]["hint"] = (
                        "Finish explicit readonly Gmail setup; scheduled runs never open login."
                        if category == "auth" else
                        "Rate-limited; saved page/item progress will resume. Check the recorded Google quota reason."
                        if category == "quota" else
                        "Check the Google error category; completed page/item progress is retained."
                    )
            outcomes[source]["seconds"] = round(time.monotonic() - start, 3)
            print(json.dumps({"at": timestamp(), "source": source, **outcomes[source]}), flush=True)
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="Explicit isolated database; default is workspace kb.sqlite")
    parser.add_argument("--source", choices=["all", "claude", "gmail"], default="all")
    parser.add_argument("--claude-root", type=Path, help="Alternate local session directory")
    parser.add_argument("--runtime", type=Path, default=RUNTIME, help="Private operational directory")
    parser.add_argument("--gmail-login", action="store_true", help="Explicit interactive readonly OAuth setup; never used by the schedule")
    args = parser.parse_args(argv)
    if not ROOT.is_dir():
        parser.exit(1, "KB workspace unavailable; mount the USB volume\n")
    from kb_store import connect
    from connectors import ingest_claude, ingest_gmail
    functions = {}
    if args.source in {"all", "claude"}:
        functions["claude"] = lambda conn: ingest_claude(conn, root=args.claude_root)
    if args.gmail_login:
        from connectors import authorize_gmail_interactive
        try:
            print(authorize_gmail_interactive())
            return 0
        except Exception as exc:
            print(f"Gmail authorization failed: {type(exc).__name__}; check private client configuration", file=sys.stderr)
            return 1
    if args.source in {"all", "gmail"}:
        functions["gmail"] = ingest_gmail
    conn = None
    try:
        load_env()
        conn = connect(args.db)
        outcomes = run_all(conn, functions, runtime=args.runtime)
        return int(any(item["status"] != "ok" for item in outcomes.values()))
    except Exception as exc:
        print(f"KB ingestion failed: {type(exc).__name__}; check private setup and mounted storage", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
