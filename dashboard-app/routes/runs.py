"""Run tab: provider model catalogues, run validation, execution and run records."""

import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import agents as forge_agents
from core import config
from core import workspace_content as wc
from core.store import _FILE_WRITE_LOCK, _atomic_write
from core.today import current_week_of_year

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Skill runner — fire Claude Code skills headlessly from buttons
# ══════════════════════════════════════════════════════════════
# Security model: the browser sends a skill *id* from config.SKILL_RUNNERS,
# never an arbitrary prompt or command. Inputs are validated and passed as
# subprocess arguments, without shell=True.

RUN_TIMEOUT = 1800  # 30 min — real skill passes take minutes, not seconds
MAX_RUNS_KEPT = 50
RUNS_LOG_TAIL = 262144  # bytes of runs.log read for "last run"


def _last_finished_run(skill: str) -> dict | None:
    """Newest finished runs.log event for one runner card; survives restarts."""
    try:
        with config.RUNS_LOG.open("rb") as fh:
            size = fh.seek(0, 2)
            fh.seek(max(0, size - RUNS_LOG_TAIL))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("skill") == skill and event.get("status") != "running":
            return event
    return None


# ── Model providers for Run executions ───────────────────────────
# Claude keeps its existing aliases; Codex/OpenCode/OpenRouter are
# provider-labelled as "provider:model_id" (e.g. "codex:gpt-6.1-sol",
# "opencode:opencode/beam-free", "openrouter:nvidia/...:free").
PROVIDERS = ("claude", "codex", "opencode", "openrouter")

# `claude --model` takes an alias or a full name. Aliases stay valid as
# models are replaced; pinned full names rot.
ALLOWED_MODELS = ("sonnet", "opus", "fable")
ALLOWED_EFFORT = ("default", "low", "medium", "high")

# Local catalogue locations (no credentials, no network at build time).
CODEX_CACHE = Path.home() / ".codex" / "models_cache.json"
OPENROUTER_CATALOG = Path.home() / ".hermes.bak" / "cache" / "openrouter_curated_catalog.json"
OPENROUTER_METADATA = Path.home() / ".hermes.bak" / "cache" / "openrouter_model_metadata.json"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

# Bounds for workspace text inlined into OpenRouter prompts (no file tools).
CONTEXT_MAX_FILE_CHARS = 80_000
CONTEXT_MAX_CHARS = 160_000


def _is_free_model_id(model_id: str) -> bool:
    """OpenCode/OpenRouter free models are marked with -free or :free."""
    return model_id.endswith(":free") or model_id.endswith("-free")


def _load_codex_models():
    """Visible Codex catalogue entries: [{id, label, efforts}], available, reason."""
    if _resolve_codex_exe() is None:
        return [], False, "codex executable not on PATH"
    try:
        raw = json.loads(CODEX_CACHE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"Codex catalogue unreadable: {exc}"
    entries = raw.get("models") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return [], False, "Codex catalogue has no model list"
    seen = set()
    models = []
    for m in entries:
        if not isinstance(m, dict):
            continue
        if m.get("visibility") != "list" or not m.get("supported_in_api"):
            continue
        slug = m.get("slug") or m.get("id")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        levels = m.get("supported_reasoning_levels") or []
        efforts = ["default"]
        for lv in levels:
            if isinstance(lv, dict) and lv.get("effort") and lv["effort"] not in efforts:
                efforts.append(lv["effort"])
        models.append({"id": slug, "label": m.get("display_name") or slug, "efforts": efforts})
    models.sort(key=lambda x: x["label"])
    return (models, True, None) if models else ([], False, "Codex catalogue has no visible entries")


def _resolve_executable(name: str, fallbacks: tuple[Path, ...]) -> str | None:
    """Locate an executable on PATH, then at known install locations.

    launchd starts the dashboard with a minimal PATH that does not include
    per-user bin directories, so PATH alone is not enough.
    """
    try:
        proc = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    for candidate in fallbacks:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _resolve_opencode_exe() -> str | None:
    """Locate the `opencode` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "opencode",
        (
            Path.home() / ".opencode" / "bin" / "opencode",
            Path("/usr/local/bin/opencode"),
            Path("/opt/homebrew/bin/opencode"),
        ),
    )


def _resolve_codex_exe() -> str | None:
    """Locate the `codex` executable, checking PATH then common install spots."""
    return _resolve_executable(
        "codex",
        (
            Path.home() / ".local" / "bin" / "codex",
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
        ),
    )


def _load_opencode_models():
    """Free OpenCode models from `opencode models`: [{id, label, efforts}], available, reason."""
    exe = _resolve_opencode_exe()
    if exe is None:
        return [], False, "opencode executable not on PATH"
    try:
        # --standalone runs a private server per call instead of depending on the
        # shared background service, whose stale registration can make this hang.
        proc = subprocess.run(
            [exe, "models", "--standalone"], capture_output=True, text=True, timeout=15
        )
    except subprocess.TimeoutExpired:
        return [], False, "opencode models timed out"
    except OSError as exc:
        return [], False, f"opencode models failed to start: {exc}"
    if proc.returncode != 0:
        return [], False, f"opencode models exited {proc.returncode}: {proc.stderr.strip()[:200]}"
    ids = [line.strip() for line in proc.stdout.splitlines() if "/" in line.strip() and _is_free_model_id(line.strip()) and "opus" not in line.strip().lower()]
    seen = set()
    models = []
    for mid in ids:
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "opencode catalogue has no free entries")


def _load_openrouter_models():
    """Free OpenRouter models from the curated catalogue: [{id, label, efforts}], available, reason."""
    try:
        raw = json.loads(OPENROUTER_CATALOG.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        return [], False, f"OpenRouter catalogue unreadable: {exc}"
    curated = raw.get("curated") if isinstance(raw, dict) else None
    if not isinstance(curated, list):
        return [], False, "OpenRouter catalogue has no curated list"
    metadata = {}
    try:
        metadata = json.loads(OPENROUTER_METADATA.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    seen = set()
    models = []
    for entry in curated:
        if not isinstance(entry, (list, tuple)) or len(entry) < 1:
            continue
        mid = entry[0]
        if not isinstance(mid, str) or not mid or any(char.isspace() for char in mid):
            continue
        is_free = _is_free_model_id(mid)
        # zero-price confirmation from metadata (listing is not entitlement).
        # Missing pricing is NOT treated as free: only explicitly zero-priced
        # models qualify.
        info = metadata.get(mid) or metadata.get(mid.split(":")[0]) or {}
        if not isinstance(info, dict):
            info = {}
        pricing = info.get("pricing") if isinstance(info.get("pricing"), dict) else None
        if pricing is not None:
            try:
                prompt_price = float(pricing["prompt"])
                comp_price = float(pricing["completion"])
            except (KeyError, TypeError, ValueError):
                prompt_price = comp_price = None
            if prompt_price == 0 and comp_price == 0:
                is_free = True
        if not is_free:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        models.append({"id": mid, "label": mid, "efforts": ["default"]})
    models.sort(key=lambda x: x["id"])
    return (models, True, None) if models else ([], False, "OpenRouter catalogue has no free entries")


def _fetch_skill_catalog():
    """Assemble the full provider-labelled catalogue (fresh on each call)."""
    claude_models = [
        {"id": m, "label": m.capitalize(), "efforts": list(ALLOWED_EFFORT)} for m in ALLOWED_MODELS
    ]
    codex_models, codex_ok, codex_reason = _load_codex_models()
    opencode_models, opencode_ok, opencode_reason = _load_opencode_models()
    openrouter_models, openrouter_ok, openrouter_reason = _load_openrouter_models()
    return {
        "models": list(ALLOWED_MODELS),
        "effort": list(ALLOWED_EFFORT),
        "provider_models": {
            "claude": claude_models,
            "codex": codex_models,
            "opencode": opencode_models,
            "openrouter": openrouter_models,
        },
        "provider_available": {
            "claude": True,
            "codex": codex_ok,
            "opencode": opencode_ok,
            "openrouter": openrouter_ok,
        },
        "provider_unavailable_reason": {
            "codex": codex_reason,
            "opencode": opencode_reason,
            "openrouter": openrouter_reason,
        },
    }

# The catalogue is read by the Run tab on open. OpenCode listing spawns a
# private server (~4 s), so cache the assembled payload and warm it from any
# dashboard visit; "Refresh models" still forces a rebuild.
_SKILL_CATALOG_TTL = 300.0
_SKILL_CATALOG: dict[str, object] = {
    "payload": None,
    "built_at": 0.0,
    "building": False,
}
_SKILL_CATALOG_LOCK = threading.Lock()


def runner_engine(cfg: dict) -> dict:
    """What a runner spends when it runs; cards are tagged and ordered by this.

    A shell runner is local unless it declares the API it calls: `kind` alone
    cannot tell `brain.py index` from `triage_jev.py`, which bills Jev.
    """
    if cfg.get("engine") == "jev":
        return {"tier": "api", "label": "Jev API · paid"}
    if cfg["kind"] == "shell":
        return {"tier": "local", "label": "No model · $0"}
    if cfg.get("providers") == ["opencode"]:
        return {"tier": "model", "label": "Model · OpenCode free"}
    return {"tier": "model", "label": "Model · Claude by default"}


def _skill_catalog_payload() -> dict:
    """The full catalogue response (provider models plus renderable skills)."""
    return {
        **_fetch_skill_catalog(),
        "skills": [
            {
                "id": sid,
                "label": cfg["label"],
                "blurb": cfg["blurb"],
                "icon": cfg["icon"],
                "kind": cfg["kind"],
                "model": cfg.get("model"),
                "options": cfg.get("options", cfg["kind"] == "claude"),
                "input_label": cfg.get("input_label"),
                "input_type": cfg.get("input_type", "url"),
                "providers": cfg.get("providers"),
                "engine": runner_engine(cfg),
            }
            for sid, cfg in config.SKILL_RUNNERS.items()
        ],
    }


def _cached_skill_catalog(force: bool = False) -> dict:
    """Return a cached catalogue, rebuilding it when stale or forced."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            not force
            and cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return cached  # type: ignore[return-value]
        payload = _skill_catalog_payload()
        _SKILL_CATALOG["payload"] = payload
        _SKILL_CATALOG["built_at"] = time.monotonic()
        return payload


def _warm_skill_catalog() -> None:
    """Build the catalogue off the request path so the next Run visit is fast."""
    now = time.monotonic()
    with _SKILL_CATALOG_LOCK:
        cached = _SKILL_CATALOG["payload"]
        if (
            cached is not None
            and now - float(_SKILL_CATALOG["built_at"]) < _SKILL_CATALOG_TTL
        ):
            return
        if _SKILL_CATALOG["building"]:
            return
        _SKILL_CATALOG["building"] = True

    def build() -> None:
        try:
            # Not forced: if a page request filled the cache first, reuse it.
            _cached_skill_catalog()
        except Exception:  # noqa: BLE001 — a failed warm must not break the page
            pass
        finally:
            with _SKILL_CATALOG_LOCK:
                _SKILL_CATALOG["building"] = False

    threading.Thread(target=build, name="skill-catalog-warm", daemon=True).start()


_RUNS: dict[str, dict] = {}
_RUNS_LOCK = threading.Lock()


class RunRequest(BaseModel):
    skill: str
    model: str | None = None
    effort: str | None = None
    input: str | None = None


def _log_run(entry: dict) -> None:
    """Append one JSON event per state change; preserve command and output path."""
    with config.RUNS_LOG.open("a") as fh:
        fh.write(
            json.dumps(
                {
                    "timestamp": datetime.now().astimezone().isoformat(),
                    **entry,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _build_update_sheet_prompt() -> str:
    """Reuse the prompt already embedded in index.html so there is one copy."""
    today = date.today()
    src = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text()
    m = re.search(r'<template id="update-sheet-prompt">(.*?)</template>', src, re.S)
    if not m:
        return (
            "Update the CloudTransition workspace so every dated file reflects today."
        )
    return (
        m.group(1)
        .replace("{{ today }}", today.isoformat())
        .replace("{{ current_week }}", str(current_week_of_year(today)))
    )


def _parse_model(value: str | None) -> tuple[str, str] | None:
    """Parse a model selection into (provider, model_id).

    Accepts "provider:model_id" for any provider, or a bare Claude alias
    (sonnet/opus/fable) treated as "claude:<alias>" for backward compatibility.
    Returns None when the value cannot be parsed.
    """
    if value is None:
        return None
    if value in ALLOWED_MODELS:
        return "claude", value
    if ":" in value:
        provider, _, model_id = value.partition(":")
        if provider in PROVIDERS and model_id:
            return provider, model_id
    return None


def _card_allows_provider(cfg: dict, provider: str) -> tuple[bool, str | None]:
    """Whether a provider may run this card, respecting read/write boundaries.

    A card that declares ``providers`` is restricted to exactly those
    providers; every other card keeps the permissive behavior. For those
    unrestricted cards, Claude is always allowed (its existing per-card tool
    restrictions apply) and every other provider is allowed too: the user
    accepts that the provider cannot machine-enforce the card's read-only or
    file/command allowlist. Boundary enforcement is then the user's
    responsibility when choosing a provider.
    """
    allowed = cfg.get("providers")
    if allowed and provider not in allowed:
        return False, f"{cfg['label']} only supports {', '.join(allowed)} models."
    return True, None


def _run_openrouter(model_id: str, prompt: str) -> dict:
    """Call the OpenRouter chat API. Returns {status, exit_code, body}.

    Never logs the API key. Returns a failed result when
    OPENROUTER_API_KEY is unset, so no model call is made.
    """
    api_key = os.environ.get(OPENROUTER_API_KEY_ENV)
    if not api_key:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": (
                "OpenRouter is not configured: set OPENROUTER_API_KEY. "
                "No model call was made."
            ),
        }
    payload = json.dumps(
        {"model": model_id, "messages": [{"role": "user", "content": prompt}]}
    ).encode()
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=RUN_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", "replace")
            return {"status": "done", "exit_code": 0, "body": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:2000]
        return {"status": "failed", "exit_code": -1, "body": body}
    except urllib.error.URLError as exc:
        return {
            "status": "failed",
            "exit_code": -1,
            "body": f"OpenRouter request failed: {exc}",
        }
    except OSError as exc:
        return {"status": "failed", "exit_code": -1, "body": f"OpenRouter error: {exc}"}


def _workspace_context(files: list[str]) -> str:
    """Inline a card's declared files for providers that cannot read them.

    Paths outside the workspace and privacy-flagged paths are skipped, and the
    rendered text is bounded so a request cannot balloon.
    """
    base = config.WORKSPACE.resolve()
    remaining = CONTEXT_MAX_CHARS
    parts: list[str] = []
    for rel in files:
        rel_path = Path(rel)
        target = (config.WORKSPACE / rel_path).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            continue
        if wc.privacy_violation(rel_path.as_posix()) or not target.is_file():
            continue
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        limited = text[: min(CONTEXT_MAX_FILE_CHARS, max(remaining, 0))]
        if not limited:
            break
        numbered = "\n".join(
            f"{number:>5}| {line}"
            for number, line in enumerate(limited.splitlines(), start=1)
        )
        suffix = "\n… truncated" if len(limited) < len(text) else ""
        parts.append(f"### {rel_path.as_posix()}\n{numbered}{suffix}")
        remaining -= len(numbered)
        if remaining <= 0:
            break
    if not parts:
        return ""
    return (
        "Workspace context follows because this provider cannot read files. "
        "Use it and cite line numbers as path:line.\n\n" + "\n\n".join(parts)
    )

def _provider_skill_prompt(prompt: str, provider: str) -> str:
    """Resolve the allowlisted card's slash skill for non-Claude providers."""
    match = re.match(r"^/([a-z0-9-]+)(?:\s+|$)", prompt)
    if provider == "claude" or not match:
        return prompt
    name = match.group(1)
    roots = (
        config.WORKSPACE / ".claude" / "skills",
        config.WORKSPACE / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
    )
    source = next((root / name / "SKILL.md" for root in roots if (root / name / "SKILL.md").is_file()), None)
    if source is None:
        raise ValueError(f"Skill {name} is not installed; no run started")
    try:
        instructions = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Skill {name} cannot be read; no run started") from exc
    if len(instructions) > CONTEXT_MAX_FILE_CHARS:
        raise ValueError(f"Skill {name} exceeds the prompt limit; no run started")
    access = (
        "You have no local file or command tools. Use the supplied context; report any "
        "missing references or capabilities instead of inventing results."
        if provider == "openrouter"
        else f"Resolve the skill's relative reference and script paths against {source.parent}."
    )
    return f"Apply the {name} skill to this task:\n{prompt[match.end():]}\n\n{access}\n\nSkill instructions ({source}):\n{instructions}"



def _resolve_run(cfg: dict, req: RunRequest, staging: str = "") -> tuple[dict, str]:
    """Build a run specification. Returns (run_spec, human-readable command).

    run_spec has a "kind" key: "shell", "claude", "codex", "opencode", or
    "openrouter". Subprocess kinds carry an "argv" list; OpenRouter carries
    "model" and "prompt" and is dispatched over HTTP in _execute_run.
    """
    if cfg["kind"] == "shell":
        argv = list(cfg["argv"])
        if cfg.get("input_argv") and req.input:
            argv.append(req.input)
        return {"kind": "shell", "argv": argv}, shlex.join(argv)

    today = date.today()
    if cfg.get("prompt") is None:
        prompt = _build_update_sheet_prompt()
    else:
        # Placeholders: {input} (validated form value), {today}, {week}, and
        # {staging} (a per-run folder path the server chose, never user input).
        prompt = cfg["prompt"].format(
            input=req.input or "",
            today=today.isoformat(),
            week=current_week_of_year(today),
            staging=staging,
        )

    options = cfg.get("options", True)
    if options and req.model is not None:
        parsed = _parse_model(req.model)
        if parsed is None:
            provider, model_id = "claude", cfg.get("model", "sonnet")
        else:
            provider, model_id = parsed
    else:
        provider, model_id = "claude", cfg.get("model", "sonnet")

    effort = req.effort if req.effort and req.effort != "default" else None
    prompt = _provider_skill_prompt(prompt, provider)


    # OpenRouter chats cannot read files, so inline the card's declared
    # workspace context for it. Local CLIs (claude/codex/opencode) read the
    # files themselves and must not get a copy in the prompt.
    if provider == "openrouter" and cfg.get("context_files"):
        if context := _workspace_context(cfg["context_files"]):
            prompt = f"{prompt}\n\n{context}"

    if provider == "claude":
        argv = [
            "claude",
            "-p",
            prompt,
            "--model",
            model_id,
            "--permission-mode",
            "dontAsk" if cfg.get("read_only") or cfg.get("permissions") else "acceptEdits",
            "--permission-prompts",
            "none",
        ]
        if cfg.get("read_only"):
            argv += [
                "--tools",
                "Read,Glob,Grep,Skill",
                "--allowedTools",
                "Read,Glob,Grep,Skill",
            ]
        if perms := cfg.get("permissions"):
            argv += ["--tools", ",".join(perms["tools"]), "--allowedTools", *perms["allow"]]
            for d in perms.get("add_dirs", []):
                argv += ["--add-dir", d]
        if effort:
            argv += ["--effort", effort]
        return {"kind": "claude", "argv": argv}, shlex.join(argv)

    if provider == "codex":
        exe = _resolve_codex_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "codex executable not on PATH"},
                "codex exec -m <model> <prompt>",
            )
        sandbox = "read-only" if cfg.get("read_only") else "workspace-write"
        argv = [
            exe,
            "exec",
            "-m",
            model_id,
            "-s",
            sandbox,
            "-C",
            str(config.WORKSPACE),
            "--color",
            "never",
            prompt,
        ]
        if effort:
            argv += ["-c", f"model_reasoning_effort={effort}"]
        return {"kind": "codex", "argv": argv}, shlex.join(argv)

    if provider == "opencode":
        exe = _resolve_opencode_exe()
        if exe is None:
            return (
                {"kind": "error", "error": "opencode executable not on PATH"},
                "opencode run --standalone -m <model> <prompt>",
            )
        # --standalone avoids the shared background service so a stale service
        # registration cannot make the run hang.
        argv = [exe, "run", "--standalone"]
        if cfg.get("kind") == "opencode-agent":
            agent = cfg.get("agent")
            if not agent:
                return (
                    {
                        "kind": "error",
                        "error": "opencode-agent card has no agent configured",
                    },
                    "opencode run --standalone --agent <agent> -m <model> <prompt>",
                )
            argv += ["--agent", agent]
        argv += ["-m", model_id, prompt]
        return {"kind": "opencode", "argv": argv}, shlex.join(argv)

    # openrouter — dispatched over HTTP in _execute_run
    return (
        {"kind": "openrouter", "model": model_id, "prompt": prompt},
        f"openrouter {model_id} <prompt>",
    )


def _run_env() -> dict:
    """Child environment with PWD matching cwd.

    `opencode run` finds its project (agents, and the Location its relative
    permission paths are matched against) from $PWD, not the process cwd. The
    server's own PWD (e.g. dashboard-app/) would otherwise leak into runs.
    """
    return {**os.environ, "PWD": str(config.WORKSPACE)}


def _opencode_resolved_agents() -> list | None:
    """`opencode debug agents` from the workspace root: OpenCode's own resolution
    of every agent's instructions and permission rules, or None if it gives no
    readable answer."""
    try:
        proc = subprocess.run(
            [_resolve_opencode_exe() or "opencode", "debug", "agents", "--standalone"],
            cwd=config.WORKSPACE,
            env=_run_env(),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        resolved = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return resolved if isinstance(resolved, list) else None


def _verify_opencode_agent(run_id: str, verify: dict) -> dict | None:
    """Check OpenCode's resolved agent against the definition hashed at launch.

    Records the outcome on the run. Fails closed: anything but "matched"
    (file changed, other instructions, unknown agent, a permission probe with
    the wrong effect, or no readable answer from OpenCode) returns a failed
    result and nothing launches. Returns None to go ahead.
    """
    expected = verify["expected"]
    current = forge_agents.launch_definition(verify["agent"])
    if current is None or current["sha256"] != expected["sha256"]:
        check = {"check": "mismatch", "detail": f"{expected['path']} changed or vanished after the run was requested."}
    else:
        resolved = _opencode_resolved_agents()
        if resolved is not None:
            check = forge_agents.check_resolved_agent(verify["agent"], resolved, expected, verify.get("policy"))
        else:
            check = {
                "check": "unverified",
                "detail": "opencode debug agents gave no readable answer, so the definition could not be verified.",
            }
    with _RUNS_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry["definition"].update(check)
    if check["check"] != "matched":
        return {"status": "failed", "exit_code": -1, "body": f"Not started: {check['detail']}"}
    return None


def _append_agent_event(agent: str, event: dict) -> str | None:
    """Append one JSON line to an agent's existing memory log; None on success.

    Never creates the memory folder (a missing one usually means the drive or
    workspace is not what we expect). Adds a newline first if the log lacks one.
    """
    log = Path(forge_agents.AGENT_STATE) / agent / "memory" / "log.jsonl"
    if not log.parent.is_dir():
        return f"{log.parent} is missing; memory event not recorded and nothing was created."
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        with _FILE_WRITE_LOCK, log.open("a+b") as fh:
            fh.seek(0, 2)
            if fh.tell():
                fh.seek(-1, 2)
                if fh.read(1) != b"\n":
                    line = "\n" + line
            fh.write(line.encode("utf-8"))
    except OSError as exc:
        return f"Memory event not recorded: {exc}"
    return None


def _stage_job_reading(job: dict) -> str | None:
    """Create this run's empty staging folder; None on success, else why not.

    Only under an existing workspace/agents/job-reader/ (never recreated if the
    drive or agent folder is missing).
    """
    root = Path(forge_agents.AGENT_STATE) / "job-reader"
    if not root.is_dir():
        return f"{root} is missing; nothing was created."
    try:
        (root / "staging" / job["run_id"]).mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        return f"Cannot create the staging folder: {exc}"
    return None


def _discard_staging(job: dict) -> None:
    """Remove this run's staging folder only; other runs' folders are untouched."""
    shutil.rmtree(Path(forge_agents.AGENT_STATE) / "job-reader" / "staging" / job["run_id"], ignore_errors=True)


def _finish_job_reading(run_id: str, job: dict, result: dict, launched_at: datetime, exited_at: datetime) -> dict:
    """Validate the staged reading, publish it, then record the memory event.

    The agent can write only staging/<run id>/; publishing to outputs/ and the
    memory event are done here, so the agent cannot overwrite another job's
    output or its memory. Timestamps come from this process, never the model.
    A missing or invalid staged file fails the run visibly.
    """
    staged = Path(forge_agents.AGENT_STATE) / "job-reader" / "staging" / run_id
    data, error = forge_agents.validate_staged_reading(staged, job["job_id"])
    extras = sorted(p.name for p in staged.glob("*") if p.name != f"{job['job_id']}.json") if staged.is_dir() else []
    with _RUNS_LOCK:
        run = dict(_RUNS.get(run_id) or {"id": run_id})
    final = None
    if data:
        final = forge_agents.finalize_reading(data, run, launched_at, exited_at, datetime.now().astimezone())
        target = Path(forge_agents.AGENT_STATE) / "job-reader" / "outputs" / f"{job['job_id']}.json"
        try:
            with _FILE_WRITE_LOCK:
                _atomic_write(target, json.dumps(final, ensure_ascii=False, indent=2) + "\n")
        except OSError as exc:
            final, error = None, f"Could not publish the output: {exc}"
    _discard_staging(job)
    event = forge_agents.job_reader_event(run, job["job_id"], job["url"], final, error)
    memory_error = _append_agent_event("job-reader", event)
    check = (
        f"Output published: workspace/agents/job-reader/outputs/{job['job_id']}.json"
        if final
        else f"Output rejected: {error}"
    )
    if extras:
        check += f" (ignored other staged files: {', '.join(extras)})"
    memory = memory_error or f"Memory event recorded: {event['event']}"
    status = result["status"] if final and not memory_error else "failed"
    with _RUNS_LOCK:
        if run_id in _RUNS:
            _RUNS[run_id]["output_check"] = check
    return {**result, "status": status, "body": f"{result['body']}\n\n--- dashboard check ---\n{check}\n{memory}\n"}


def _execute_run(run_id: str, run_spec: dict) -> None:
    """Run the command to completion in a worker thread; record the result.

    run_spec["kind"] is "shell"/"claude"/"codex"/"opencode" (subprocess via
    run_spec["argv"]) or "openrouter" (HTTP via run_spec["model"]/prompt).
    """
    config.RUNS_DIR.mkdir(exist_ok=True)
    out_path = config.RUNS_DIR / f"{run_id}.txt"
    started = time.time()
    try:
        if run_spec["kind"] == "error":
            result = {
                "status": "failed",
                "exit_code": -1,
                "body": run_spec.get("error", "run spec error"),
            }
        elif run_spec["kind"] == "openrouter":
            result = _run_openrouter(run_spec["model"], run_spec["prompt"])
        elif run_spec.get("verify_agent") and (
            refused := _verify_opencode_agent(run_id, run_spec["verify_agent"])
        ):
            result = refused
        else:
            job = run_spec.get("job_reading")
            staging_error = _stage_job_reading(job) if job else None
            if staging_error:
                result = {"status": "failed", "exit_code": -1, "body": f"Not started: {staging_error}"}
            else:
                argv = run_spec["argv"]
                launched_at = datetime.now().astimezone()
                try:
                    proc = subprocess.run(
                        argv,
                        cwd=config.WORKSPACE,
                        env=_run_env(),
                        capture_output=True,
                        text=True,
                        timeout=RUN_TIMEOUT,
                        check=False,
                    )
                except BaseException:
                    if job:
                        _discard_staging(job)
                    raise
                body = proc.stdout + (
                    f"\n\n--- stderr ---\n{proc.stderr}" if proc.stderr.strip() else ""
                )
                result = {
                    "status": "done" if proc.returncode == 0 else "failed",
                    "exit_code": proc.returncode,
                    "body": body,
                }
                if job:
                    result = _finish_job_reading(run_id, job, result, launched_at, datetime.now().astimezone())
    except subprocess.TimeoutExpired:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Timed out after {RUN_TIMEOUT}s.",
        }
    except FileNotFoundError:
        result = {
            "status": "failed",
            "exit_code": -1,
            "body": f"Command not found: {run_spec['argv'][0]}. Is it on PATH?",
        }
    except OSError as exc:
        result = {"status": "failed", "exit_code": -1, "body": f"Failed to start: {exc}"}

    out_path.write_text(result["body"])
    duration = f"{time.time() - started:.1f}s"

    with _RUNS_LOCK:
        entry = _RUNS.get(run_id)
        if entry is not None:
            entry.update(
                status=result["status"],
                exit_code=result["exit_code"],
                duration=duration,
                finished=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                output=str(out_path.relative_to(config.WORKSPACE)),
                preview=result["body"].strip()[-400:],
            )
            _log_run(entry)


@router.get("/api/skills/catalog")
def api_skill_catalog():
    """The buttons the UI should render, with provider-labelled model catalogues."""
    return JSONResponse(_cached_skill_catalog())


@router.post("/api/skills/catalog/refresh")
def api_skill_catalog_refresh():
    """Force a fresh read of the provider catalogues (Refresh models button)."""
    return JSONResponse(_cached_skill_catalog(force=True))


@router.post("/api/skills/run")
def api_skill_run(req: RunRequest, x_requested_with: str = Header(default="")):
    """Start one skill run in the background; return its id immediately."""
    if x_requested_with != "XMLHttpRequest":
        return JSONResponse({"error": "Missing CSRF header"}, status_code=403)

    cfg = config.SKILL_RUNNERS.get(req.skill)
    if cfg is None:
        return JSONResponse({"error": "Unknown skill"}, status_code=400)

    # Validate the selected model against its provider, not just its prefix.
    # Allowing a provider on a card does not allow arbitrary or paid model IDs.
    if cfg["kind"] == "shell":
        if req.model is not None or req.effort not in (None, "default"):
            return JSONResponse({"error": "Shell tools do not accept model or effort selections"}, status_code=400)
        provider, model_id = None, None
        valid_efforts = ["default"]
    else:
        selection = req.model if cfg.get("options", True) and req.model is not None else cfg.get("model", "sonnet")
        parsed = _parse_model(selection)
        if parsed is None:
            return JSONResponse({"error": "Unknown model"}, status_code=400)
        provider, model_id = parsed
        if provider == "claude":
            models = [{"id": model, "efforts": list(ALLOWED_EFFORT)} for model in ALLOWED_MODELS]
        else:
            loader = {
                "codex": _load_codex_models,
                "opencode": _load_opencode_models,
                "openrouter": _load_openrouter_models,
            }[provider]
            models, available, reason = loader()
            if not available:
                return JSONResponse({"error": reason}, status_code=400)
        selected = next((model for model in models if model["id"] == model_id), None)
        if selected is None:
            return JSONResponse({"error": f"Unknown model for {provider}"}, status_code=400)
        valid_efforts = selected["efforts"]
    effort = req.effort if req.effort is not None else "default"
    if effort not in valid_efforts:
        return JSONResponse({"error": "Unsupported effort for this model"}, status_code=400)

    # Permission parity: refuse provider/card pairings that cannot enforce the
    # card's read-only or command/template boundary.
    allowed, reason = _card_allows_provider(cfg, provider)
    if not allowed:
        return JSONResponse({"error": reason}, status_code=400)

    # OpenRouter requires a configured API key before anything launches.
    if provider == "openrouter" and not os.environ.get(OPENROUTER_API_KEY_ENV):
        return JSONResponse(
            {
                "error": "OpenRouter is not configured: set OPENROUTER_API_KEY. No model call was made."
            },
            status_code=400,
        )

    if cfg.get("input_label"):
        value = (req.input or "").strip()
        if not value and cfg.get("input_optional"):
            req.input = None
        elif not value:
            return JSONResponse(
                {"error": f"{cfg['input_label']} is required"}, status_code=400
            )
        elif not re.match(cfg["input_pattern"], value):
            return JSONResponse(
                {"error": f"Not a valid {cfg['input_label']}"}, status_code=400
            )
        else:
            req.input = value

    run_id = uuid4().hex
    # Job Reader writes only to this run's staging folder; the server picks it.
    staging = f"workspace/agents/job-reader/staging/{run_id}" if cfg.get("post_run") == "job-reading" else ""
    try:
        run_spec, shown = _resolve_run(cfg, req, staging)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # Agent cards: hash the definition OpenCode should load before anything runs.
    agent_id = cfg.get("agent") if cfg["kind"] == "opencode-agent" else None
    definition = None
    if agent_id:
        definition = forge_agents.launch_definition(agent_id)
        if definition is None:
            return JSONResponse(
                {"error": f".opencode/agents/{agent_id}.md is missing; run not started"}, status_code=400
            )

    entry = {
        "id": run_id,
        "skill": req.skill,
        "label": cfg["label"],
        "provider": provider,
        "model": model_id,
        "effort": effort,
        "status": "running",
        "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "command": shown,
        "output": None,
        "duration": None,
        "preview": None,
    }
    if agent_id and run_spec["kind"] == "opencode":
        # The dashboard resolves this path; OpenCode's own resolution is checked
        # in _verify_opencode_agent just before launch.
        entry.update(
            agent=agent_id,
            runner="opencode-agent",
            cwd=str(config.WORKSPACE),
            log=str(config.RUNS_LOG.relative_to(config.WORKSPACE)),
            finished=None,
            definition={**definition, "check": "pending", "detail": "Not yet compared with OpenCode."},
        )
        run_spec["verify_agent"] = {"agent": agent_id, "expected": definition, "policy": cfg.get("policy")}
        if cfg.get("post_run") == "job-reading":
            # input_pattern already guarantees "<job id> <http(s) URL>".
            jid, url = req.input.split(" ", 1)
            run_spec["job_reading"] = {"job_id": jid, "url": url, "run_id": run_id}
    with _RUNS_LOCK:
        # Check and reserve together: double-clicks must not start two processes,
        # and one agent runs one task at a time (its memory has one writer).
        for r in _RUNS.values():
            if r["status"] != "running":
                continue
            if r["skill"] == req.skill:
                return JSONResponse({"error": "Already running"}, status_code=409)
            if agent_id and r.get("agent") == agent_id:
                return JSONResponse(
                    {"error": f"{agent_id} is already running {r['label']}"}, status_code=409
                )
        try:
            _log_run(entry)
        except OSError:
            return JSONResponse(
                {"error": "Cannot write runs.log; run not started"}, status_code=503
            )
        _RUNS[run_id] = entry
        completed = sorted(
            (key for key, run in _RUNS.items() if run["status"] != "running"),
            key=lambda key: _RUNS[key]["started"],
        )
        for stale in completed[:-MAX_RUNS_KEPT]:
            _RUNS.pop(stale, None)

    threading.Thread(target=_execute_run, args=(run_id, run_spec), daemon=True).start()
    return JSONResponse({"ok": True, "run": entry})


@router.get("/api/skills/runs")
def api_skill_runs():
    """Current status of every tracked run, newest first."""
    with _RUNS_LOCK:
        runs = sorted(_RUNS.values(), key=lambda r: r["started"], reverse=True)
    return JSONResponse({"runs": runs})
