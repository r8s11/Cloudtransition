"""Secret masking, security-mail detection and source exclusion for the personal KB.

Pattern masking reduces risk; it cannot guarantee that every secret is found.
Everything here is standard library only and safe to import on the search path.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

MASKING_NOTICE = (
    "Pattern-based masking reduces risk but cannot guarantee that every secret is detected."
)

PRIVATE_DIR_ENV = "KB_HOME"
EXCLUDE_ENV = "KB_EXCLUDE_PATH_PATTERNS"
EXCLUDE_FILE = "exclude-paths.txt"


def private_dir() -> Path:
    """Internal private directory for tokens, logs, locks and approvals (never inside the workspace)."""
    override = os.environ.get(PRIVATE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local-routines" / "personal-kb"


def _marker(kind: str) -> str:
    return f"[REDACTED:{kind}]"


_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\Z)"
)
_PGP_BLOCK = re.compile(r"-----BEGIN PGP PRIVATE KEY BLOCK-----[\s\S]*?(?:-----END PGP PRIVATE KEY BLOCK-----|\Z)")

# (kind, compiled regex) for self-identifying token formats.
_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{6,}")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{10,}")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,})")),
    ("aws-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("google-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("google-oauth", re.compile(r"\bya29\.[A-Za-z0-9_\-]{16,}")),
    ("google-refresh", re.compile(r"(?<![A-Za-z0-9])1//[A-Za-z0-9_\-]{20,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}")),
)

_BEARER = re.compile(r"(?i)\b(bearer)(\s+)(?!\[REDACTED)(?=[A-Za-z0-9._~+/=\-]*[\d._+/=\-])[A-Za-z0-9._~+/=\-]{12,}")
_BASIC = re.compile(r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?basic\s+)(?!\[REDACTED)[A-Za-z0-9+/=]{8,}")
_URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^\s/@:'\"]+:[^\s/@'\"]+@")
_URL_SECRET_PARAM = re.compile(
    r"(?i)([?&](?:access_token|refresh_token|id_token|token|api[_-]?key|apikey|key|secret|client_secret|password|passwd|sig|signature|auth)=)(?!\[REDACTED)[^&\s#\"'<>]+"
)
_LABEL_WORDS = (
    r"password|passwd|passphrase|pwd|secret|api[_-]?key|apikey|access[_-]?key|private[_-]?key|"
    r"access[_-]?token|auth[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|token"
)
# name containing a secret word, then = or :, then the value. "password is X" is also treated as a label.
_LABELLED = re.compile(
    r"(?i)(?<![A-Za-z0-9_.\-])(?P<label>[A-Za-z0-9_.\-]*(?:" + _LABEL_WORDS + r")[A-Za-z0-9_.\-]*)"
    r"(?P<sep>[\"']?\s*(?:=|:|\bis\b)\s*[\"']?)"
    r"(?!\[REDACTED)(?P<value>[^\s\"',;)\]}<>]{4,})"
)
_BENIGN_VALUES = frozenset(
    {
        "required", "missing", "invalid", "expired", "revoked", "denied", "unauthorized", "undefined",
        "optional", "provided", "null", "none", "false", "true", "empty", "present", "configured",
        "stored", "generated", "rotated", "mismatch", "incorrect", "correct", "supplied", "needed",
        "expected", "failed", "unknown", "hidden", "masked", "redacted",
    }
)


def _labelled_sub(match: re.Match[str]) -> str:
    value = match.group("value")
    if value.lower().strip(".") in _BENIGN_VALUES or value.startswith("$") or value.startswith("{{"):
        return match.group(0)
    # counters/limits such as "max_tokens: 4096" are not secrets
    if value.rstrip(".").isdigit() and re.fullmatch(r"(?i)(?:(?:max|min|input|output|total)[_-]?)?tokens|token[_-]?(?:count|limit|size|ttl|expires?)", match.group("label")):
        return match.group(0)
    # a value that is just another word of an identifier (e.g. "token_count") is not a secret
    if re.fullmatch(r"[a-z_]+", value) and "_" in value and len(value) < 24 and match.group("sep").strip().lower() == "is":
        return match.group(0)
    return f"{match.group('label')}{match.group('sep')}{_marker('secret')}"


def redact(text: Any) -> str:
    """Mask secret-looking substrings. Idempotent; keeps surrounding context intact."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    out = _PRIVATE_KEY.sub(_marker("private-key"), text)
    out = _PGP_BLOCK.sub(_marker("private-key"), out)
    for kind, pattern in _TOKEN_PATTERNS:
        out = pattern.sub(_marker(kind), out)
    out = _BEARER.sub(lambda m: f"{m.group(1)}{m.group(2)}{_marker('token')}", out)
    out = _BASIC.sub(lambda m: f"{m.group(1)}{_marker('token')}", out)
    out = _URL_CREDENTIALS.sub(lambda m: f"{m.group(1)}{_marker('credentials')}@", out)
    out = _URL_SECRET_PARAM.sub(lambda m: f"{m.group(1)}{_marker('secret')}", out)
    out = _LABELLED.sub(_labelled_sub, out)
    return out


def redact_obj(value: Any) -> Any:
    """Recursively mask strings (and dict keys) in JSON-compatible data."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {redact(str(k)): redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(v) for v in value]
    return value


def contains_private_key(text: str) -> bool:
    return bool(_PRIVATE_KEY.search(text) or _PGP_BLOCK.search(text))


def safe_error(exc: BaseException, limit: int = 300) -> str:
    """Sanitized one-line description of an exception: type name plus masked, bounded message."""
    message = redact(str(exc)).replace("\n", " ").strip()
    if len(message) > limit:
        message = message[:limit] + "..."
    name = type(exc).__name__
    return f"{name}: {message}" if message else name


def diagnostic(category: str, exc: BaseException | str) -> dict[str, str]:
    """Stored/logged failure record. Always carries the masking caveat."""
    message = safe_error(exc) if isinstance(exc, BaseException) else redact(str(exc))
    return {"category": category, "message": message, "notice": MASKING_NOTICE}


# --- security mail -----------------------------------------------------------------------

_SECURITY_SUBJECT = re.compile(
    r"(?i)(password[\s\-]*(?:reset|recovery|change)|reset(?:ting)?\s+(?:your\s+)?password|forgot(?:ten)?\s+(?:your\s+)?password|"
    r"(?:verification|security|authentication|confirmation|login|log[\s\-]?in|sign[\s\-]?in|one[\s\-]?time|access)\s+(?:pass)?code|"
    r"\botp\b|\b2fa\b|\bmfa\b|two[\s\-]?(?:factor|step)|2[\s\-]?step|magic\s+link|(?:sign[\s\-]?in|log[\s\-]?in)\s+link)"
)
_SECURITY_BODY = re.compile(
    r"(?i)(reset\s+(?:your\s+)?password|password\s+reset|"
    r"your\s+(?:verification|security|authentication|login|one[\s\-]?time|sign[\s\-]?in)\s+(?:pass)?code|"
    r"(?:verification|security|authentication)\s+code\s+(?:is|:)|use\s+(?:this|the\s+following)\s+code|"
    r"two[\s\-]?factor\s+(?:code|authentication\s+code)|\b2fa\s+code\b)"
)


def is_security_email(subject: str, body: str = "") -> bool:
    """Password-reset / 2FA / one-time-code mail: never stored, never sent anywhere."""
    if _SECURITY_SUBJECT.search(subject or ""):
        return True
    return bool(_SECURITY_BODY.search((body or "")[:1500]))


# --- source eligibility ---------------------------------------------------------------------

DEFAULT_EXCLUDED_PATH_PATTERNS: tuple[str, ...] = (
    r"employer",
    r"college[-_ ]?planning",
    r"academic",
    r"snhu",
    r"sophia[-_ ]?learning",
    r"(?:^|[-_/ ])transcripts?[-_ ]official",
)


def _compile(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    compiled = []
    for raw in patterns:
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        try:
            compiled.append(re.compile(raw, re.IGNORECASE))
        except re.error:
            # fail closed: a malformed pattern excludes literal matches rather than being ignored
            compiled.append(re.compile(re.escape(raw), re.IGNORECASE))
    return compiled


def load_exclusion_patterns(extra: Iterable[str] | None = None, *, environ: dict[str, str] | None = None) -> list[re.Pattern[str]]:
    """Default employer/academic patterns + $KB_EXCLUDE_PATH_PATTERNS (newline/comma separated)
    + <private dir>/exclude-paths.txt + explicit extras. Never reads patterns from source content."""
    env = os.environ if environ is None else environ
    patterns = list(DEFAULT_EXCLUDED_PATH_PATTERNS)
    raw_env = env.get(EXCLUDE_ENV, "")
    patterns.extend(p for p in re.split(r"[\n,]", raw_env) if p.strip())
    override = env.get(PRIVATE_DIR_ENV)
    base = Path(override).expanduser() if override else Path.home() / ".local-routines" / "personal-kb"
    cfg = base / EXCLUDE_FILE
    try:
        if cfg.is_file():
            patterns.extend(cfg.read_text(encoding="utf-8").splitlines())
    except OSError:
        pass
    if extra:
        patterns.extend(extra)
    return _compile(patterns)


def exclusion_fingerprint(patterns: Iterable[re.Pattern[str]]) -> str:
    import hashlib

    joined = "\n".join(sorted(p.pattern for p in patterns))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def is_excluded_path(value: str | os.PathLike[str] | None, patterns: Iterable[re.Pattern[str]] | None = None) -> bool:
    """True when a path / encoded project directory name / cwd matches an employer or academic boundary."""
    if not value:
        return False
    pats = load_exclusion_patterns() if patterns is None else list(patterns)
    text = str(value)
    return any(p.search(text) for p in pats)


_SECRET_PATH = re.compile(
    r"(?ix)(?:^|[/\\\s'\"=])(?:"
    r"\.env(?:\.[\w\-]+)?|\.netrc|\.npmrc|\.pypirc|\.pgpass|\.git-credentials|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?|[\w\-.]*\.(?:pem|key|p12|pfx|jks|keystore|ovpn)|"
    r"[\w\-.]*(?:credentials?|secrets?)[\w\-.]*\.(?:json|ya?ml|toml|txt|ini|env)|"
    r"[\w\-.]*(?:token|apikey|api-key)[\w\-.]*\.(?:json|txt|ya?ml)|"
    r"\.(?:ssh|aws|gnupg|kube|docker)(?:[/\\]|$)|kb\.sqlite(?:-wal|-shm)?"
    r")(?=$|[/\\\s'\"])"
)


def is_secret_path(value: str | None) -> bool:
    """File path (or shell command text) that names a credential/secret store."""
    return bool(value and _SECRET_PATH.search(str(value)))
