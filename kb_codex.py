"""Explicit Claude-only Codex summaries; never called by ingestion or scheduling."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

import connectors
import kb_privacy
import kb_store
import kb_summaries as summaries
from kb_runtime import ingest_lock, private_directory, private_write

CODEX_CACHE = Path.home() / ".codex" / "models_cache.json"
MODEL = "gpt-6-luna"
STATE = "codex-summaries"
# Reserve response space, not a promised hard output-token or subscription-dollar cap.
OUTPUT_RESERVE = 8192
DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "multi_agent", "multi_agent_v2", "apps", "plugins",
    "hooks", "browser_use", "browser_use_external", "computer_use", "image_generation",
    "view_image", "code_mode_host", "code_mode_only", "sleep_tool", "skill_search",
    "skill_mcp_dependency_install", "plugin_discovery_prefetch", "remote_plugin",
    "workspace_dependencies", "memories", "shell_snapshot", "goals", "tool_suggest",
    "unbounded_connection_retries",
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _context(model):
    if model != MODEL:
        raise ValueError("Only the explicit Luna fallback is supported")
    try:
        catalogue = json.loads(CODEX_CACHE.read_text())
        entries = catalogue.get("models") if isinstance(catalogue, dict) else catalogue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("slug") != model or entry.get("visibility") != "list" or not entry.get("supported_in_api"):
                continue
            window = entry.get("context_window")
            percent = entry.get("effective_context_window_percent", 95)
            if type(window) is not int or type(percent) is not int or window <= 0 or not 1 <= percent <= 100:
                break
            return window * percent // 100
    except (OSError, ValueError, TypeError):
        pass
    raise ValueError("Visible Luna catalogue entry with a valid context bound is required")


def _item(conn, source, source_id, context, *, allow_done=False):
    if source != "claude" or not isinstance(source_id, str) or not source_id:
        raise ValueError("Select an explicit Claude identity; Gmail is not supported")
    raw = sorted((r for r in connectors.read_item_rows(conn, source, source_id) if r["kind"] == "raw"), key=lambda r: r["metadata"].get("chunk_index", 0))
    permitted = (*summaries.PENDING_STATUSES, "done") if allow_done else summaries.PENDING_STATUSES
    if not raw or any(r["metadata"].get("summary_status") not in permitted for r in raw):
        raise ValueError("Selected item is missing or not pending")
    title, chunks = raw[0]["title"], [r["content"] for r in raw]
    item_hash = raw[0]["metadata"].get("item_hash")
    if not isinstance(item_hash, str) or not item_hash:
        raise ValueError("Source item has no version hash")
    payload = summaries.build_payload(title, chunks, item_hash)
    if kb_privacy.redact(payload) != payload:
        raise ValueError("Payload contains secret-looking data; no transfer permitted")
    upper = len((summaries.SYSTEM_PROMPT + payload).encode("utf-8")) + 4096
    if upper + OUTPUT_RESERVE > context:
        raise ValueError("Selected item exceeds the conservative one-request context bound; not truncated")
    item = {"source": source, "source_id": source_id, "item_hash": item_hash,
            "content_hash": _digest([title, chunks]), "title": title, "chars": sum(map(len, chunks)),
            "input_tokens_upper": upper, "payload": payload}
    return item, raw


def preview(conn, identities, model=MODEL):
    """Build an exact, local-only review object. No process or provider request."""
    context = _context(model)
    identities = list(identities)
    if not identities or len(identities) != len(set(tuple(i) for i in identities)):
        raise ValueError("Select a nonempty set of distinct Claude identities")
    items = [_item(conn, *identity, context)[0] for identity in identities]
    manifest = {"version": 1, "provider": "codex", "model": model, "context_window": context,
                "system_prompt_hash": _digest(summaries.SYSTEM_PROMPT), "preview_id": secrets.token_hex(16),
                "calls": len(items), "items": items}
    manifest["fingerprint"] = _digest(manifest)
    return manifest


def save_preview(path, manifest):
    """Source-bearing previews must stay owner-only, outside shared evidence."""
    private_write(Path(path), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def command(executable, directory, model):
    """Shared by the real transport and installed-CLI loopback verification."""
    args = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
            "--skip-git-repo-check", "-C", str(directory), "-s", "read-only", "--json", "-m", model,
            "-o", str(directory / "response")]
    settings = {"approval_policy": "never", "project_doc_max_bytes": 0, "web_search": "disabled",
                "skills.bundled.enabled": False, "skills.include_instructions": False,
                "agents.enabled": False, "features.code_mode.enabled": False,
                "model_provider": "kb_codex", "model_instructions_file": str(directory.parent / "instructions"),
                "developer_instructions": "",
                "model_providers.kb_codex.name": "KB Codex",
                "model_providers.kb_codex.wire_api": "responses",
                "model_providers.kb_codex.requires_openai_auth": True,
                "model_providers.kb_codex.request_max_retries": 0,
                "model_providers.kb_codex.stream_max_retries": 0}
    for key, value in settings.items():
        args += ["-c", key + "=" + json.dumps(value)]
    for feature in DISABLED_FEATURES:
        args += ["--disable", feature]
    return args + ["-"]


def _invoke(payload, model, timeout):
    exe = shutil.which("codex")
    if not exe:
        raise ValueError("Codex executable unavailable")
    root = private_directory(kb_privacy.private_dir() / "codex-work")
    with tempfile.TemporaryDirectory(prefix="item-", dir=root) as tmp:
        temp_root = Path(tmp)
        directory = temp_root / "empty"
        directory.mkdir(mode=0o700)
        private_write(temp_root / "instructions", summaries.SYSTEM_PROMPT)
        private_directory(temp_root / "home")
        env = os.environ.copy()
        env["CODEX_HOME"] = env.get("CODEX_HOME", str(Path.home() / ".codex"))
        env["HOME"] = str(temp_root / "home")
        env["TMPDIR"] = tmp
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_BASE_URL"):
            env.pop(key, None)
        proc = subprocess.run(command(exe, directory, model), input=payload, text=True,
                              capture_output=True, cwd=directory, env=env, timeout=timeout)
        if proc.returncode or "unsupported call:" in proc.stderr:
            raise ValueError("Codex failed; no automatic retry")
        usage = None
        for line in proc.stdout.splitlines():
            event = json.loads(line)
            if event.get("type") == "error" or event.get("type") == "turn.failed":
                raise ValueError("Codex reported failure")
            item = event.get("item", {})
            # The CLI reports intentional disabled Code Mode as an error item,
            # even for a successful text-only turn. Other diagnostics fail closed.
            if item.get("type") == "error" and item.get("message", "").startswith(
                "Code Mode is unavailable because code-mode host is disabled."
            ):
                continue
            if item and item.get("type") not in ("agent_message", "reasoning"):
                raise ValueError("Unsupported Codex tool event; response refused")
            if event.get("type") == "turn.completed":
                usage = event.get("usage")
        if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
            raise ValueError("Codex did not report valid actual token usage")
        text = (directory / "response").read_text()
        if kb_privacy.redact(text) != text:
            raise ValueError("Secret-looking output refused")
        return json.loads(text), usage


def run(conn, manifest, fingerprint, *, transfer_ack=False, usage_ack=False, scheduled=False, timeout=180):
    """One explicit approval, no retries. Dollar cost is unknown, never zero."""
    if scheduled or transfer_ack is not True or usage_ack is not True:
        raise ValueError("Explicit OpenAI transfer and subscription-usage acknowledgments required; no scheduled mode")
    body = {k: v for k, v in manifest.items() if k != "fingerprint"}
    if not fingerprint or manifest.get("fingerprint") != fingerprint or _digest(body) != fingerprint:
        raise ValueError("Exact reviewed preview fingerprint required")
    if manifest.get("version") != 1 or manifest.get("provider") != "codex" or manifest.get("system_prompt_hash") != _digest(summaries.SYSTEM_PROMPT):
        raise ValueError("Preview contract changed; review a new preview")
    context = _context(manifest.get("model"))
    items = manifest.get("items")
    if context != manifest.get("context_window") or not isinstance(items, list) or not items or manifest.get("calls") != len(items):
        raise ValueError("Preview model or bounds changed")
    with ingest_lock(kb_privacy.private_dir()):
        prepared = []
        for approved in items:
            current, raw = _item(conn, approved.get("source"), approved.get("source_id"), context, allow_done=True)
            if current != approved:
                raise ValueError("Source changed since preview; review a new preview")
            done = all(r["metadata"].get("summary_status") == "done" for r in raw)
            if done and any(r["metadata"].get("summary", {}).get("approval_id") != fingerprint for r in raw):
                raise ValueError("Selected item was already completed outside this approval")
            prepared.append((approved, raw, done))
        report = {"provider": "codex", "model": manifest["model"], "approval_id": fingerprint,
                  "cost_usd": None, "summarized": 0, "cached": 0, "failed": 0, "items": []}
        for approved, raw, done in prepared:
            ident = approved["source_id"]
            attempt_key = "attempt:" + _digest([fingerprint, ident])
            cache_key = "cache:" + _digest([summaries.PROMPT_VERSION, manifest["model"], approved["content_hash"]])
            if done:
                report["cached"] += 1
                continue
            cached = kb_store.get_state(conn, STATE, cache_key)
            if not cached and kb_store.get_state(conn, STATE, attempt_key):
                raise ValueError("This preview was already attempted; review a fresh preview for an explicit retry")
            try:
                if cached:
                    payload, usage_meta = cached["result"], {**cached["usage"], "cached": True, "approval_id": fingerprint}
                    report["cached"] += 1
                else:
                    kb_store.set_state(conn, STATE, attempt_key, {"outcome": "attempted", "cost_usd": None})
                    payload, usage = _invoke(approved["payload"], manifest["model"], timeout)
                    usage_meta = {"provider": "codex", "model": manifest["model"], "prompt_version": summaries.PROMPT_VERSION,
                                  "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"],
                                  "cost_usd": None, "approval_id": fingerprint, "cached": False,
                                  "at": connectors.to_iso(connectors.utcnow())}
                result = summaries.validate_summary(payload, "".join(r["content"] for r in raw), len(raw))
                if kb_privacy.redact_obj(result) != result:
                    raise ValueError("Secret-looking summary refused")
                with kb_store.transaction(conn):
                    current, _ = _item(conn, "claude", ident, context, allow_done=True)
                    if current != approved:
                        raise ValueError("Source changed during summary; result refused")
                    kb_store.set_state(conn, STATE, cache_key, {"result": payload, "usage": usage_meta})
                    kb_store.replace_rows(conn, "claude", ident, summaries._build_rows(raw, result, usage_meta))
                report["summarized"] += 1
                report["items"].append({"source_id": ident, "outcome": "summarized", "usage": usage_meta})
            except (ValueError, OSError, subprocess.TimeoutExpired, summaries.SummaryError, KeyError, TypeError):
                report["failed"] += 1
                report["items"].append({"source_id": ident, "outcome": "failed", "error": "Codex/output/source check failed; raw remains pending; explicit new preview required"})
        return report


def _cli(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("preview", help="Local-only exact Claude-item review")
    p.add_argument("--item", action="append", required=True, help="Claude source_id; repeat for selected items")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--model", default=MODEL)
    p = sub.add_parser("run", help="Explicit OpenAI transfer; no automatic retry")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--fingerprint", required=True)
    p.add_argument("--ack-openai-transfer", action="store_true")
    p.add_argument("--ack-subscription-usage", action="store_true")
    args = parser.parse_args(argv)
    conn = None
    try:
        conn = kb_store.connect(args.db)
        if args.action == "preview":
            result = preview(conn, [("claude", i) for i in args.item], args.model)
            save_preview(args.manifest, result)
            print(json.dumps({"manifest": str(args.manifest), "fingerprint": result["fingerprint"], "model": result["model"], "calls": result["calls"], "cost_usd": None}))
        else:
            result = run(conn, json.loads(args.manifest.read_text()), args.fingerprint,
                         transfer_ack=args.ack_openai_transfer, usage_ack=args.ack_subscription_usage)
            print(json.dumps(result))
            return int(bool(result["failed"]))
        return 0
    except (ValueError, OSError, RuntimeError):
        print("Codex preview/run refused; check private manifest, source versions, catalogue and explicit consent", file=sys.stderr)
        return 2
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(_cli())
