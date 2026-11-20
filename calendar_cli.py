#!/usr/bin/env python3
"""Preview selected Markdown tasks locally; explicitly publish approved Google Tasks."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

from calendar_model import CalendarError, list_items, make_preview, validate_preview
from kb_privacy import redact

ROOT = Path(__file__).resolve().parent
RUNTIME = Path.home() / ".local-routines" / "personal-kb" / "calendar"


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    local = commands.add_parser("list", help="List unchecked source items; no network or writes")
    local.add_argument("--source", type=Path, default=ROOT / "TASKS.md")
    preview = commands.add_parser("preview", help="Print an exact batch as JSON; no network or writes")
    preview.add_argument("--source", type=Path, default=ROOT / "TASKS.md")
    preview.add_argument("--task-list", required=True)
    preview.add_argument("--item", action="append", required=True, metavar="LINE=YYYY-MM-DD")
    login = commands.add_parser("login", help="Explicit separate Google Tasks OAuth login")
    login.add_argument("--credentials", type=Path)
    for command in (login, commands.add_parser("lists", help="Read existing Google task-list choices")):
        command.add_argument("--runtime", type=Path, default=RUNTIME)
    publish = commands.add_parser("publish", help="Publish only an exact approved private preview")
    publish.add_argument("--runtime", type=Path, default=RUNTIME)
    publish.add_argument("--preview-file", type=Path, required=True)
    publish.add_argument("--approve", required=True, metavar="EXACT_PREVIEW_HASH")
    return parser


def _read_preview(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        path = Path(path).expanduser()
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise CalendarError("Preview path must not contain symlinks.")
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077 or metadata.st_uid != os.getuid():
                raise CalendarError("Preview must be a regular owner-only file (chmod 600), not a shared or symlink file.")
            preview = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        raise CalendarError("Cannot read a valid owner-only preview file.") from None
    validate_preview(preview)
    return preview


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            items = list_items(args.source)
            for item in items:
                item["title"], item["heading"] = redact(item["title"]), redact(item["heading"])
            print(json.dumps(items, ensure_ascii=False, indent=2))
            if not items:
                print("No unchecked checklist items.", file=sys.stderr)
            return 0
        if args.command == "preview":
            selections = []
            for item in args.item:
                parts = item.split("=", 1)
                if len(parts) != 2:
                    raise CalendarError("Each --item requires LINE=YYYY-MM-DD.")
                selections.append(tuple(parts))
            print(json.dumps(make_preview(args.source, selections, args.task_list), ensure_ascii=False, indent=2))
            return 0
        # Optional SDK is never imported for list/preview, and login is never implicit.
        import calendar_google
        if args.command == "login":
            print("Google Tasks access can create, edit, organize and delete all Tasks. This app only lists/reconciles and creates explicitly approved items. Gmail access remains read-only and separate.", file=sys.stderr)
            calendar_google.login(args.runtime, args.credentials)
            print("Separate Google Tasks login saved privately.")
            return 0
        if args.command == "lists":
            choices = calendar_google.list_tasklists(calendar_google.build_service(args.runtime))
            print(json.dumps(choices, ensure_ascii=False, indent=2))
            return 0
        preview = _read_preview(args.preview_file)
        outcome = calendar_google.publish(preview, args.approve, args.runtime)
        print(json.dumps(outcome, ensure_ascii=False, indent=2))
        return 1 if outcome["failed"] or outcome["uncertain"] else 0
    except CalendarError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Calendar operation failed ({type(exc).__name__}); no implicit login or retry was attempted.", file=sys.stderr)
        return 1
    except Exception as exc:
        # SDK exceptions can contain credential URLs and source bodies.
        print(f"Calendar operation failed ({type(exc).__name__}); inspect private configuration, not provider exception text.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
