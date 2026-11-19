#!/usr/bin/env python3
"""Personal knowledge base CLI: init | stats | search.  Standard library only.

Works from any directory: the database defaults to `kb.sqlite` next to this file.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

import kb_store  # noqa: E402

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]+")


def _clean(value):
    return _CONTROL.sub(" ", "" if value is None else str(value)).strip()


def _limit(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid limit {text!r}: expected an integer") from None
    if not 1 <= value <= kb_store.MAX_LIMIT:
        raise argparse.ArgumentTypeError(f"invalid limit {value}: must be 1-{kb_store.MAX_LIMIT}")
    return value


def _day(text):
    try:
        return kb_store.parse_day(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _age(hours):
    if hours is None:
        return ""
    return f"{hours * 60:.0f}m ago" if hours < 1 else f"{hours:.1f}h ago" if hours < 48 else f"{hours / 24:.1f}d ago"


def format_header(header):
    lines = [f"KB: {header['rows']} rows, {header['items']} items"]
    if header["last_ingest"]:
        tail = f" (STALE: over {kb_store.STALE_HOURS:g}h old)" if (header["last_ingest_age_hours"] or 0) > kb_store.STALE_HOURS else ""
        lines[0] += f" | last ingest: {header['last_ingest']} ({_age(header['last_ingest_age_hours'])}){tail}"
    else:
        lines[0] += " | last ingest: never recorded"
    for name, s in header["sources"].items():
        if s["status"] == "fresh":
            continue
        detail = {
            "failed": f"last run FAILED ({s['last_error']})",
            "incomplete": "last run did not finish",
            "stale": f"STALE, over {kb_store.STALE_HOURS:g}h since last success",
            "never": "no successful ingest recorded",
        }[s["status"]]
        last = f"; last success {s['last_success']} ({_age(s['age_hours'])})" if s["last_success"] else ""
        lines.append(f"  ! {_clean(name)}: {detail}{last}")
    return "\n".join(lines)


def format_results(result):
    out = [format_header(result["header"])]
    if not result["terms"]:
        out.append("No searchable terms in query (use letters or digits).")
        return "\n".join(out)
    if not result["results"]:
        out.append("No matches.")
        return "\n".join(out)
    out.append(f"{len(result['results'])} result(s) for: {' OR '.join(result['terms'])}")
    for r in result["results"]:
        flag = " [superseded]" if r["superseded"] else ""
        out.append(f"{r['rank']}. {_clean(r['ts'])[:10]} | {_clean(r['source'])} | {_clean(r['title']) or '(untitled)'} ({_clean(r['kind'])}){flag}")
        out.append(f"   {_clean(r['snippet'])}")
        out.append(f"   -> {_clean(r['pointer']) or '(no pointer)'}")
    return "\n".join(out)


def format_stats(st):
    lines = [f"KB: {st['rows']} rows, {st['items']} items | pending summaries: {st['pending_summaries']} | skipped: {st['skipped']}"]
    if st["last_ingest"]:
        lines.append(f"Last successful ingest: {st['last_ingest']} ({_age(st['last_ingest_age_hours'])})")
    else:
        lines.append("Last successful ingest: never recorded")
    if st["by_kind"]:
        lines.append("Rows by kind: " + ", ".join(f"{k}={v}" for k, v in sorted(st["by_kind"].items())))
    for name, s in sorted(st["by_source"].items()):
        cov = f"{_clean(s['first_ts'])[:10]}..{_clean(s['last_ts'])[:10]}" if s["first_ts"] else "no rows"
        kinds = ", ".join(f"{k}={v}" for k, v in sorted(s["kinds"].items()))
        lines.append(f"- {_clean(name)}: {s['items']} items, {s['rows']} rows ({kinds}); coverage {cov}")
        extra = f"status {s['status']}"
        if s["last_success"]:
            extra += f", last success {s['last_success']}"
        if s["last_error"]:
            extra += f", last error {_clean(s['last_error'])}"
        lines.append(f"    {extra}; pending summaries {s['pending_summaries']}; skipped {s['skipped']}")
    return "\n".join(lines)


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", default=argparse.SUPPRESS, help="database file (default: kb.sqlite beside kb.py)")
    parser = argparse.ArgumentParser(prog="kb.py", description="Personal knowledge base.", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", parents=[common], help="create the database (safe to repeat)")
    p = sub.add_parser("stats", parents=[common], help="show counts, coverage and freshness")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p = sub.add_parser("search", parents=[common], help="keyword search")
    p.add_argument("query", help="words to look for")
    p.add_argument("--after", type=_day, metavar="YYYY-MM-DD", help="only items dated on/after this day")
    p.add_argument("--source", help="only this source name")
    p.add_argument("--limit", type=_limit, default=10, help="maximum results (default 10)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    db = getattr(args, "db", None)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        conn = kb_store.connect(db, create=args.command == "init")
    except FileNotFoundError as exc:
        print(f"{exc}\nRun: python3 {os.path.realpath(__file__)} init", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"cannot open knowledge base: {exc.strerror or exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # sqlite3.Error etc.; never echo row content
        print(f"cannot open knowledge base: {type(exc).__name__}", file=sys.stderr)
        return 1
    try:
        if args.command == "init":
            path = conn.execute("PRAGMA database_list").fetchone()[2]
            print(f"Knowledge base ready: {path}")
            return 0
        if args.command == "stats":
            st = kb_store.stats(conn)
            print(json.dumps(st, indent=2, ensure_ascii=False) if args.json else format_stats(st))
            return 0
        result = kb_store.search(conn, args.query, after=args.after, source=args.source, limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else format_results(result))
        return 0
    except Exception as exc:
        print(f"{args.command} failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
