#!/usr/bin/env python3
"""Start one agent run through the running dashboard's own runner.

Posts to the dashboard's POST /api/skills/run, so the run gets the same
catalogue, free-model gate, definition check, job-reader staging and publish
step, memory event and Run-tab record as a button press. Nothing executes in
this process, and the dashboard must be running on 127.0.0.1:8000.

  scout                        Scout scan
  job-reader JOB_ID URL        read one posting (both arguments required)
  cv-adapter base              build the base CV
  cv-adapter tailor JOB_ID     tailor the CV to one job (job id required)
  forge                        refused: Forge has no dashboard runner

Add --wait to block until the run finishes and exit 1 if it failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DASHBOARD = "http://127.0.0.1:8000"
CSRF = {"X-Requested-With": "XMLHttpRequest"}
POLL_SECONDS = 10

# Command -> (Run-tab card id, card input). Cards and their gates live in
# dashboard-app/core/config.py SKILL_RUNNERS; the server re-validates everything.
FORGE_REFUSAL = "Forge is the coordinator and has no dashboard runner. Nothing ran."


def _call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {**CSRF, "Content-Type": "application/json"} if body is not None else dict(CSRF)
    req = urllib.request.Request(DASHBOARD + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}").get("error", exc.reason)
        except (ValueError, AttributeError):
            detail = exc.reason
        raise SystemExit(f"Refused by dashboard ({exc.code}): {detail}. Nothing ran.")
    except (urllib.error.URLError, OSError) as exc:
        raise SystemExit(f"Dashboard not reachable at {DASHBOARD} ({exc}). Nothing ran.")


def _free_opencode_model() -> str:
    """First model in the dashboard's OpenCode catalogue; the catalogue is free-only."""
    catalog = _call("GET", "/api/skills/catalog")
    if not catalog.get("provider_available", {}).get("opencode"):
        reason = catalog.get("provider_unavailable_reason", {}).get("opencode")
        raise SystemExit(f"OpenCode unavailable on the dashboard: {reason}. Nothing ran.")
    models = catalog["provider_models"]["opencode"]
    return f"opencode:{models[0]['id']}"


def _build(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.agent == "forge":
        raise SystemExit(FORGE_REFUSAL)
    if args.agent == "scout":
        return "scout-scan", None
    if args.agent == "job-reader":
        return "job-reader", f"{args.job_id} {args.url}"
    if args.step == "base":
        return "cv-base", None
    return "cv-tailor", args.job_id


def _wait(run_id: str) -> int:
    while True:
        time.sleep(POLL_SECONDS)
        runs = _call("GET", "/api/skills/runs").get("runs", [])
        run = next((r for r in runs if r["id"] == run_id), None)
        if run is None:
            raise SystemExit(f"Run {run_id} is no longer tracked by the dashboard.")
        if run["status"] != "running":
            print(json.dumps(run, indent=2))
            return 0 if run["status"] == "done" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="agent", required=True)
    sub.add_parser("scout")
    jr = sub.add_parser("job-reader")
    jr.add_argument("job_id", help="job id, e.g. acme-support-1")
    jr.add_argument("url", help="one posting URL")
    cv = sub.add_parser("cv-adapter")
    steps = cv.add_subparsers(dest="step", required=True)
    steps.add_parser("base")
    tailor = steps.add_parser("tailor")
    tailor.add_argument("job_id", help="job id whose Job Reader output exists")
    sub.add_parser("forge")
    parser.add_argument("--wait", action="store_true", help="wait for the run to finish")
    args = parser.parse_args(argv)

    card, card_input = _build(args)
    body: dict = {"skill": card, "model": _free_opencode_model()}
    if card_input is not None:
        body["input"] = card_input
    started = _call("POST", "/api/skills/run", body)["run"]
    print(json.dumps({k: started[k] for k in ("id", "label", "status", "model", "output")}, indent=2))
    if not args.wait:
        return 0
    return _wait(started["id"])


if __name__ == "__main__":
    sys.exit(main())
