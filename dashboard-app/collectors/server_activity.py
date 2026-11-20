"""Read-only server activity for Parrot and Flatbush.

Combines cAdvisor containers, Windows/systemd services, blackbox probes and
recent Loki entries into one compact snapshot per host. Nothing here writes to
a remote system, and nothing infers health from scrape ``up``: every section
carries a status that separates an unreachable source ("unavailable") from a
reachable source that exports nothing ("not_exported"/"empty").

Deliberately never collected: process command lines, service binary paths,
service accounts, Windows event bodies, or any credential-like value.
"""

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

HOSTS = ("parrot", "flatbush")
HOST_ADDRESSES = {
    "parrot": {"parrot", "parrot.tail9aa23.ts.net", "100.105.235.49"},
    "flatbush": {"flatbush", "flatbush.tail9aa23.ts.net", "100.67.14.72"},
}
ADDRESS_TO_HOST = {addr: host for host, addrs in HOST_ADDRESSES.items() for addr in addrs}

LIMITS = {
    "containers": 100,
    "services": 500,
    "processes": 500,
    "probes": 100,
    "log_rows": 8,
    "log_sources": 50,
    "log_only_containers": 50,
    "log_window_minutes": 15,
    "message_chars": 800,
}
QUERY_TIMEOUT_SECONDS = 3
# cAdvisor refreshes container_last_seen every few seconds; Prometheus keeps a
# vanished series visible for its 5 minute lookback, so freshness is checked.
CONTAINER_FRESH_SECONDS = 120
WINDOWS_JOB_PREFERENCE = ("integrations/windows_exporter", "integrations/windows")

PROCESS_COVERAGE_PREFIXES = ("windows_process_", "namedprocess_namegroup_")
GPU_COVERAGE_PREFIXES = ("windows_gpu_", "DCGM_FI_", "nvidia_", "node_drm_", "amdgpu_")


def _tag(name: str, expr: str) -> str:
    return f'label_replace(({expr}), "dashboard_metric", "{name}", "", "")'


def _union(parts: tuple[tuple[str, str], ...]) -> str:
    return " or ".join(_tag(name, expr) for name, expr in parts)


# Aggregations drop labels we must never receive (path_name carries command
# lines, run_as carries accounts) rather than discarding them client-side.
CONTAINER_QUERY = _union((
    ("last_seen", 'max by (host, name, id, job, instance, image) (container_last_seen{name!=""})'),
    ("cpu", 'sum by (host, name, id, job, instance) '
     '(rate(container_cpu_usage_seconds_total{name!=""}[5m]) and container_cpu_usage_seconds_total{name!=""})'),
    ("memory", 'max by (host, name, id, job, instance) (container_memory_working_set_bytes{name!=""})'),
    ("rx", 'sum by (host, name, id, job, instance) '
     '(rate(container_network_receive_bytes_total{name!=""}[5m]) and container_network_receive_bytes_total{name!=""})'),
    ("tx", 'sum by (host, name, id, job, instance) '
     '(rate(container_network_transmit_bytes_total{name!=""}[5m]) and container_network_transmit_bytes_total{name!=""})'),
    ("start", 'max by (host, name, id, job, instance) (container_start_time_seconds{name!=""})'),
    ("health", 'max by (host, name, id, job, instance) (container_health_state{name!=""})'),
))
SERVICE_QUERY = _union((
    ("win_state", 'max by (host, instance, job, name, state) '
                  '(windows_service_state{job=~"integrations/windows.*"} == 1)'),
    ("win_mode", 'max by (host, instance, job, name, start_mode) '
                 '(windows_service_start_mode{job=~"integrations/windows.*"} == 1)'),
    ("win_info", 'max by (host, instance, job, name, display_name) '
                 '(windows_service_info{job=~"integrations/windows.*"})'),
    ("win_proc", 'max by (host, instance, job, name, process_id) '
                 '(windows_service_process{job=~"integrations/windows.*"})'),
    ("systemd", 'max by (host, instance, job, name, state) '
                '(node_systemd_unit_state{name=~".+\\\\.service"} == 1)'),
))
PROBE_QUERY = _union((
    ("success", "probe_success"),
    ("duration", "probe_duration_seconds"),
    ("http", "probe_http_status_code"),
))
COVERAGE_QUERY = (
    'count by (__name__, host, instance) ({__name__=~"'
    + "|".join(re.escape(p) + ".+" for p in PROCESS_COVERAGE_PREFIXES + GPU_COVERAGE_PREFIXES)
    + '"})'
)
# Aggregate before transport so command lines, executable paths and accounts never leave Prometheus.
_PROCESS_SELECTOR = '{process!~"(?i)idle|_total|system idle process"}'
_PROCESS_LABELS = "host,instance,job,process,process_id"
PROCESS_QUERY = _union(tuple(
    (name, f"topk by(host,instance,job) ({LIMITS['processes']}, {expression})")
    for name, expression in (
        ("process_cpu", f"sum by({_PROCESS_LABELS}) "
         f"(rate(windows_process_cpu_time_total{_PROCESS_SELECTOR}[5m]) "
         f"and windows_process_cpu_time_total{_PROCESS_SELECTOR})"),
        ("process_memory", f"max by({_PROCESS_LABELS}) (windows_process_working_set_private_bytes{_PROCESS_SELECTOR})"),
        ("process_threads", f"max by({_PROCESS_LABELS}) (windows_process_threads{_PROCESS_SELECTOR})"),
        ("process_uptime", f"time() - max by({_PROCESS_LABELS}) (windows_process_start_time_seconds_timestamp{_PROCESS_SELECTOR})"),
        ("process_sample", f"max by({_PROCESS_LABELS}) (timestamp(windows_process_working_set_private_bytes{_PROCESS_SELECTOR}))"),
        ("process_total", f"count by(host,instance,job) (windows_process_working_set_private_bytes{_PROCESS_SELECTOR})"),
    )
))
LOKI_COUNT_QUERY = (
    "sum by(host,job,container,service_name,level)"
    '(count_over_time({host=~"parrot|flatbush"}[15m]))'
)


# ---------------------------------------------------------------- sanitizing

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b.")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
_INVISIBLE = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\ufffe\uffff\ud800-\udfff]")
_SPACES = re.compile(r"\s+")

_SECRET_NAME = (
    r"(?:[\w.-]*?(?:password|passwd|pwd|passphrase|secret|token|apikey|api[_-]?key|"
    r"access[_-]?key|private[_-]?key|authorization|credentials?|cookie|session[_-]?id)[\w.-]*"
    r"|[\w.-]*[_.-]key|key)"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?<![\w.-])([\"']?" + _SECRET_NAME + r"[\"']?\s*[:=]\s*)"
    r"""((?:(?:bearer|basic|token)\s+)?(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;&}"']+))""",
    re.IGNORECASE,
)
_CREDENTIAL_URL = re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^\s/@:]+(?::[^\s/@]*)?@", re.IGNORECASE)
_AUTH_SCHEME = re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.DOTALL)
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{16,}|"
    r"xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,})\b"
)
_MAX_INPUT_CHARS = 20000


def redact(text: str) -> str:
    """Mask common credential shapes. Order matters: URLs and keys first."""
    text = _PRIVATE_KEY.sub("[redacted]", text)
    text = _CREDENTIAL_URL.sub(r"\1[redacted]@", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1[redacted]", text)
    text = _AUTH_SCHEME.sub("Bearer [redacted]", text)
    text = _JWT.sub("[redacted]", text)
    return _KNOWN_TOKEN.sub("[redacted]", text)


def clean_text(value, limit: int = LIMITS["message_chars"]) -> str:
    """One display-safe line: no ANSI/control/bidi characters, redacted, bounded.

    HTML is intentionally left alone; the consumer renders with textContent.
    """
    if not isinstance(value, str):
        return ""
    text = _ANSI.sub(" ", value[:_MAX_INPUT_CHARS])
    text = _INVISIBLE.sub("", _CONTROL.sub(" ", text))
    text = redact(_SPACES.sub(" ", text).strip())
    if len(text) > limit:
        text = text[: max(limit - 1, 0)].rstrip() + "\u2026"
    return text


_LEVELS = {
    "trace": "trace", "verbose": "trace", "debug": "debug",
    "info": "info", "information": "info", "informational": "info", "notice": "info",
    "warn": "warning", "warning": "warning",
    "err": "error", "error": "error",
    "crit": "critical", "critical": "critical", "fatal": "critical",
    "alert": "critical", "emerg": "critical", "emergency": "critical", "panic": "critical",
}
_ERROR_LEVELS = {"error", "critical"}
UNKNOWN_LEVEL = "unknown"


def _normalize_level(*labels) -> str:
    """First meaningful severity label; 'unknown' stays unknown, never 'info'."""
    for label in labels:
        if not isinstance(label, str) or not label.strip():
            continue
        key = label.strip().lower()
        if key == UNKNOWN_LEVEL:
            continue
        return _LEVELS.get(key) or clean_text(key, 24).lower() or UNKNOWN_LEVEL
    return UNKNOWN_LEVEL


# ------------------------------------------------------------------- helpers

def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _non_negative(value) -> float | None:
    number = _number(value)
    return number if number is not None and number >= 0 else None


def _count(value) -> int | float | None:
    number = _non_negative(value)
    if number is None:
        return None
    return int(number) if number == int(number) else number


def _address(instance: str) -> str:
    match = re.match(r"^(?:[a-z][a-z0-9+.-]*://)?\[?([^/:\]]+)", instance.strip().lower())
    return match.group(1) if match else ""


def resolve_host(labels: dict) -> str | None:
    """Host from the host label, else the instance address; contradictions are dropped."""
    by_instance = ADDRESS_TO_HOST.get(_address(labels.get("instance", "")))
    declared = labels.get("host")
    if declared is not None:
        host = declared.strip().lower() if isinstance(declared, str) else None
        if host not in HOSTS or (by_instance and by_instance != host):
            return None
        return host
    return by_instance


def _prometheus_samples(payload) -> list[tuple[dict, float, float | None]] | None:
    """Parsed (labels, evaluation_time, finite value|None); None means source failure."""
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None
    data = payload.get("data")
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, list):
        return None
    samples = []
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("metric"), dict):
            continue
        value = item.get("value")
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            continue
        timestamp = _number(value[0])
        if timestamp is None:
            continue
        labels = {k: v for k, v in item["metric"].items() if isinstance(k, str) and isinstance(v, str)}
        samples.append((labels, timestamp, _number(value[1])))
    return samples


def _by_metric(samples) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for labels, timestamp, value in samples:
        grouped.setdefault(labels.get("dashboard_metric", ""), []).append((labels, timestamp, value))
    return grouped


def _section(status: str, rows: list, total: int, limit: int, **extra) -> dict:
    return {"status": status, "rows": rows[:limit], "total": total, "limited": total > limit, **extra}


def _unavailable_section(limit: int, **extra) -> dict:
    return _section("unavailable", [], 0, limit, **extra)


# ---------------------------------------------------------------- containers

def _container_health(value: float | None) -> str | None:
    # cAdvisor v0.55.1 getContainerHealthState: 1 healthy, -1 unconfigured,
    # 0 starting OR unhealthy. Zero alone cannot establish an unhealthy container.
    # https://github.com/google/cadvisor/blob/v0.55.1/metrics/prometheus.go#L2179-L2192
    if value == 1:
        return "healthy"
    return None


def _build_containers(samples) -> dict[str, dict]:
    grouped = _by_metric(samples)
    evaluated_at = max((ts for _, ts, _ in samples), default=None)
    per_host: dict[str, dict] = {host: {"seen": 0, "stale": 0, "rows": {}} for host in HOSTS}
    metrics = {}
    def identity(labels, host, name):
        return host, name, labels.get("id", ""), labels.get("job", ""), labels.get("instance", "")
    for key in ("cpu", "memory", "rx", "tx", "start", "health"):
        for labels, _, value in grouped.get(key, []):
            host, name = resolve_host(labels), labels.get("name", "")
            if host and name:
                metrics.setdefault(identity(labels, host, name), {})[key] = value
    choices = {}
    for labels, _, value in grouped.get("last_seen", []):
        host, name = resolve_host(labels), labels.get("name", "")
        if not host or not name:
            continue
        bucket = per_host[host]
        bucket["seen"] += 1
        last_seen = _non_negative(value)
        if last_seen is None or evaluated_at is None or not 0 <= evaluated_at - last_seen <= CONTAINER_FRESH_SECONDS:
            bucket["stale"] += 1
            continue
        found = metrics.get(identity(labels, host, name), {})
        start = _non_negative(found.get("start"))
        rank = (-last_seen, -(start or 0), labels.get("job", ""), labels.get("instance", ""), labels.get("id", ""))
        if (host, name) in choices and rank >= choices[(host, name)]:
            continue
        choices[(host, name)] = rank
        bucket["rows"][name] = {
            "name": clean_text(name, 128),
            "image": clean_text(labels.get("image", "").split("@", 1)[0], 200) or None,
            "cpu_cores": _non_negative(found.get("cpu")),
            "memory_bytes": _non_negative(found.get("memory")),
            "receive_bytes_per_second": _non_negative(found.get("rx")),
            "transmit_bytes_per_second": _non_negative(found.get("tx")),
            "uptime_seconds": max(evaluated_at - start, 0.0) if start else None,
            "last_seen": last_seen,
            "health": _container_health(found.get("health")),
        }
    return per_host


def _container_section(bucket: dict) -> dict:
    rows = sorted(
        bucket["rows"].values(),
        key=lambda r: (
            -(r["cpu_cores"] if r["cpu_cores"] is not None else -1.0),
            -(r["memory_bytes"] if r["memory_bytes"] is not None else -1.0),
            r["name"],
        ),
    )
    status = "ok" if bucket["seen"] else "not_exported"
    return _section(status, rows, len(rows), LIMITS["containers"],
                    stale_excluded=bucket["stale"], freshness_seconds=CONTAINER_FRESH_SECONDS)


# ------------------------------------------------------------------ services

def _active_states(host: str, samples) -> dict[tuple[str, str], dict[str, set]]:
    """{(job, instance): {service: {active states}}}; only value==1 one-hot rows count."""
    sources: dict[tuple[str, str], dict[str, set]] = {}
    for labels, _, value in samples:
        if value == 1 and resolve_host(labels) == host and labels.get("name"):
            source = (labels.get("job", ""), labels.get("instance", ""))
            sources.setdefault(source, {}).setdefault(labels["name"], set()).add(labels.get("state", ""))
    return sources


def _preferred_source(host: str, sources) -> tuple[str, str]:
    """Duplicate exporter jobs describe one machine: pick one deterministically, never merge."""
    def rank(source):
        job, instance = source
        known = WINDOWS_JOB_PREFERENCE.index(job) if job in WINDOWS_JOB_PREFERENCE else len(WINDOWS_JOB_PREFERENCE)
        return (known, 0 if _address(instance) == host else 1, job, instance)
    return min(sources, key=rank)


def _metadata(host: str, source: tuple[str, str], samples, label: str, active_only: bool = False) -> dict[str, set]:
    """Values of one label per service name, joined by exact (host, job, instance, name)."""
    found: dict[str, set] = {}
    for labels, _, value in samples:
        if (labels.get("job", ""), labels.get("instance", "")) == source and resolve_host(labels) == host \
                and labels.get("name") and (value == 1 or not active_only):
            found.setdefault(labels["name"], set()).add(labels.get(label, ""))
    return found


def _single(values: set | None) -> str | None:
    return next(iter(values)) if values and len(values) == 1 else None


def _service_row(name: str, states: set, display: str | None, start_mode: str | None, pid: str | None) -> dict:
    state = _single(states)
    return {
        "name": clean_text(name, 128),
        "display_name": clean_text(display or name, 200),
        # Conflicting active states break the one-hot contract: say unknown, never guess.
        "state": (clean_text(state.lower(), 40) if state else "") or UNKNOWN_LEVEL,
        "start_mode": (clean_text(start_mode.lower(), 40) or None) if start_mode else None,
        "pid": int(pid) if pid and pid.isdigit() and int(pid) > 0 else None,
    }


def _host_services(host: str, grouped: dict) -> list[dict] | None:
    windows = _active_states(host, grouped.get("win_state", []))
    if windows:
        source = _preferred_source(host, windows)
        modes = _metadata(host, source, grouped.get("win_mode", []), "start_mode", active_only=True)
        names = _metadata(host, source, grouped.get("win_info", []), "display_name")
        pids = _metadata(host, source, grouped.get("win_proc", []), "process_id")
        return [
            _service_row(name, states, min(names[name]) if name in names else None,
                         _single(modes.get(name)), min(pids[name]) if name in pids else None)
            for name, states in windows[source].items()
        ]
    # Linux systemd only counts when the exporter actually emits unit state.
    systemd = _active_states(host, grouped.get("systemd", []))
    if systemd:
        return [_service_row(name, states, None, None, None)
                for name, states in systemd[_preferred_source(host, systemd)].items()]
    return None


def _service_priority(state: str) -> int:
    return 0 if state == "running" else 2 if state == "stopped" else 1


def _build_services(samples) -> dict[str, dict]:
    grouped = _by_metric(samples)
    sections = {}
    for host in HOSTS:
        rows = _host_services(host, grouped)
        if rows is None:
            sections[host] = _section("not_exported", [], 0, LIMITS["services"])
            continue
        rows.sort(key=lambda r: (_service_priority(r["state"]), r["name"].casefold(), r["name"]))
        sections[host] = _section("ok", rows, len(rows), LIMITS["services"])
    return sections


# -------------------------------------------------------------------- probes

_PROBE_STATUS_ORDER = {"down": 0, "unknown": 1, "up": 2}
_HOST_PORT = re.compile(r"^[^/\s:]+:\d{1,5}$")


def _identity(labels: dict) -> frozenset:
    return frozenset((k, v) for k, v in labels.items() if k not in ("__name__", "dashboard_metric"))


def _build_probes(samples) -> dict[str, dict]:
    grouped = _by_metric(samples)
    durations = {_identity(labels): _non_negative(value) for labels, _, value in grouped.get("duration", [])}
    http_identities = {_identity(labels) for labels, _, _ in grouped.get("http", [])}
    rows: dict[str, dict[frozenset, dict]] = {host: {} for host in HOSTS}
    for labels, _, value in grouped.get("success", []):
        host = resolve_host(labels)
        if not host:
            continue
        identity = _identity(labels)
        instance = labels.get("instance", "")
        if instance.lower().startswith(("http://", "https://")) or identity in http_identities:
            kind = "http"
        elif _HOST_PORT.match(instance):
            kind = "tcp"
        else:
            kind = None
        # Probes without a distinct target (bare host instance) must not invent one.
        target = None if _address(instance) in HOST_ADDRESSES[host] and "/" not in instance and ":" not in instance else (
            clean_text(instance, 200) or None)
        rows[host][identity] = {
            "service": clean_text(labels.get("service") or instance, 128) or UNKNOWN_LEVEL,
            "target": target,
            "kind": kind,
            "status": "up" if value == 1 else "down" if value == 0 else "unknown",
            "duration_seconds": durations.get(identity),
        }
    sections = {}
    for host in HOSTS:
        ordered = sorted(
            rows[host].values(),
            key=lambda r: (_PROBE_STATUS_ORDER[r["status"]], r["service"].casefold(), r["kind"] or "", r["target"] or ""),
        )
        sections[host] = _section("ok" if ordered else "not_exported", ordered, len(ordered), LIMITS["probes"])
    return sections


# ------------------------------------------------------------------ coverage

def _build_coverage(samples) -> dict[str, dict]:
    found = {host: {"process_detail": False, "gpu": False} for host in HOSTS}
    for labels, _, _ in samples:
        host = resolve_host(labels)
        name = labels.get("__name__", "")
        if not host:
            continue
        if name.startswith(PROCESS_COVERAGE_PREFIXES):
            found[host]["process_detail"] = True
        elif name.startswith(GPU_COVERAGE_PREFIXES):
            found[host]["gpu"] = True
    return {host: {k: "available" if v else "not_exported" for k, v in flags.items()} for host, flags in found.items()}


def _build_processes(samples) -> dict[str, dict]:
    """Rank current Windows processes without retrieving process command lines."""
    sources = {host: {} for host in HOSTS}
    fields = {
        "process_cpu": "cpu_cores", "process_memory": "memory_bytes",
        "process_threads": "threads", "process_uptime": "uptime_seconds",
        "process_sample": "sample_timestamp",
    }
    for labels, evaluation_time, value in samples:
        host = resolve_host(labels)
        stat = labels.get("dashboard_metric")
        if not host or value is None or value < 0 or stat not in (*fields, "process_total"):
            continue
        source = (labels.get("job", ""), labels.get("instance", ""))
        bucket = sources[host].setdefault(source, {"total": None, "rows": {}})
        if stat == "process_total":
            bucket["total"] = int(value)
            continue
        name, pid = labels.get("process", ""), labels.get("process_id", "")
        if not name or not pid.isdigit():
            continue
        row = bucket["rows"].setdefault((pid, name), {
            "name": clean_text(name, 128), "pid": int(pid), "cpu_cores": None,
            "memory_bytes": None, "threads": None, "uptime_seconds": None,
            "sample_timestamp": None, "_evaluation_time": evaluation_time,
        })
        row[fields[stat]] = value
    result = {}
    for host, candidates in sources.items():
        if not candidates:
            result[host] = _section("not_exported", [], 0, LIMITS["processes"])
            continue
        source = _preferred_source(host, candidates)
        bucket = candidates[source]
        current = []
        for row in bucket["rows"].values():
            observed = row["sample_timestamp"]
            if observed is None or not 0 <= row["_evaluation_time"] - observed <= CONTAINER_FRESH_SECONDS:
                continue
            current.append({key: value for key, value in row.items() if not key.startswith("_")})
        current.sort(key=lambda row: (-(row["cpu_cores"] or 0), -(row["memory_bytes"] or 0), row["name"], row["pid"]))
        total = max(len(current), bucket["total"] or 0)
        result[host] = _section("ok", current, total, LIMITS["processes"], ranking="CPU cores, then private working set")
    return result


# ---------------------------------------------------------------------- logs

def _loki_vector(payload) -> list[tuple[dict, int | float]] | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(data, dict):
        return None
    result = data.get("result")
    if not isinstance(result, list):
        return None
    series = []
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("metric"), dict):
            continue
        value = item.get("value")
        count = _count(value[1]) if isinstance(value, (list, tuple)) and len(value) == 2 else None
        if count is not None:
            series.append(({k: v for k, v in item["metric"].items() if isinstance(v, str)}, count))
    return series


def _loki_entries(payload) -> list[dict] | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(data, dict):
        return None
    streams = data.get("result")
    if not isinstance(streams, list):
        return None
    entries = []
    for stream in streams:
        labels = stream.get("stream") if isinstance(stream, dict) else None
        values = stream.get("values") if isinstance(stream, dict) else None
        if not isinstance(labels, dict) or not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, (list, tuple)) or len(value) < 2 or not isinstance(value[1], str):
                continue
            try:
                timestamp_ns = int(value[0])
                if timestamp_ns < 0:
                    continue
                timestamp = timestamp_ns / 1e9
            except (TypeError, ValueError):
                continue
            entries.append({"timestamp": timestamp, "timestamp_ns": timestamp_ns, "labels": labels, "line": value[1]})
    return entries


def _windows_event_summary(line: str) -> str | None:
    """Known Windows event fields only; event_data/message bodies can hold secrets."""
    if not line.lstrip().startswith("{"):
        return None
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict) or "event_id" not in event or "source" not in event:
        return None
    task = event.get("taskText")
    parts = [
        clean_text(task, 120) if isinstance(task, str) and task.strip() else "Event",
        clean_text(event.get("source"), 120),
        f"event {clean_text(str(event.get('event_id')), 12)}",
        clean_text(event.get("channel"), 120),
    ]
    return " \u00b7 ".join(part for part in parts if part)


def _log_message(labels: dict, line: str) -> str:
    if labels.get("job") == "windows-events":
        summary = _windows_event_summary(line)
        if summary:
            return summary
        if line.lstrip().startswith("<"):
            return "Windows event (structured details omitted)"
    return clean_text(line)


def _log_source(labels: dict) -> str:
    return clean_text(labels.get("container") or labels.get("service_name") or labels.get("job") or "", 128) or UNKNOWN_LEVEL


def _build_logs(host: str, counts, entries) -> tuple[dict, dict]:
    """(logs section, docker log-source summary). None inputs mean query failure."""
    host_series = [(labels, n) for labels, n in counts or [] if labels.get("host") == host]
    total = sum(n for _, n in host_series) if counts is not None else None
    known = [(labels, n) for labels, n in host_series if _normalize_level(labels.get("level")) != UNKNOWN_LEVEL]
    if counts is None:
        error_count = None
    elif known:
        error_count = sum(n for labels, n in known if _normalize_level(labels.get("level")) in _ERROR_LEVELS)
    else:
        error_count = 0 if total == 0 else None
    by_source: dict[tuple[str, str], int | float] = {}
    for labels, n in host_series:
        key = (_log_source(labels), clean_text(labels.get("job", ""), 64))
        by_source[key] = by_source.get(key, 0) + n
    sources = [{"name": name, "job": job, "count": n}
               for (name, job), n in sorted(by_source.items(), key=lambda kv: (-kv[1], kv[0]))]
    rows = []
    if entries is not None:
        ordered = sorted(entries, key=lambda e: (-e["timestamp_ns"], e["line"]))[: LIMITS["log_rows"]]
        rows = [{
            "timestamp": entry["timestamp"],
            "id": str(entry["timestamp_ns"]) + ":" + _log_source(entry["labels"]),
            "source": _log_source(entry["labels"]),
            "level": _normalize_level(entry["labels"].get("level"), entry["labels"].get("detected_level")),
            "message": _log_message(entry["labels"], entry["line"]),
        } for entry in ordered]
    if counts is None and entries is None:
        status = "unavailable"
    elif rows or (total or 0) > 0:
        status = "ok"
    else:
        status = "empty"
    limited = (total is not None and total > len(rows)) or (entries is not None and len(entries) >= LIMITS["log_rows"])
    logs = {
        "status": status,
        "window_minutes": LIMITS["log_window_minutes"],
        "total_count": total,
        "error_count": error_count,
        "severity_known_count": sum(n for _, n in known) if counts is not None else None,
        "sources": sources[: LIMITS["log_sources"]],
        "sources_total": len(sources),
        "rows": rows,
        "limited": bool(limited),
        "queries": {"counts": "ok" if counts is not None else "unavailable",
                    "recent": "ok" if entries is not None else "unavailable"},
    }
    docker = sorted({labels["container"] for labels, _ in host_series
                     if labels.get("job") == "docker" and labels.get("container")})
    return logs, {"known": counts is not None, "containers": [clean_text(name, 128) for name in docker]}


def _apply_log_only(containers: dict, docker: dict, present: set[str] | None) -> None:
    """Make 'logs exist, performance metrics do not' explicit instead of silent.

    present: names of every fresh cAdvisor container (before the row cap); None when
    container metrics are unavailable, in which case the comparison is unknowable.
    """
    if not docker["known"] or present is None:
        containers["log_only"] = {"status": "unavailable", "total": None, "names": []}
        containers["coverage_gap"] = None
        return
    names = [name for name in docker["containers"] if name not in present]
    containers["log_only"] = {"status": "ok", "total": len(names), "names": names[: LIMITS["log_only_containers"]]}
    containers["coverage_gap"] = (
        "logs_without_performance_metrics" if containers["status"] == "not_exported" and names else None)


# ------------------------------------------------------------------- collect

def _source_status(results: dict) -> dict:
    values = list(results.values())
    status = "ok" if all(values) else "unavailable" if not any(values) else "partial"
    return {"status": status, "queries": {k: "ok" if v else "unavailable" for k, v in results.items()}}


def collect_server_activity(fetch_json, prometheus_url: str, loki_url: str) -> dict:
    """Return {hosts: {parrot: activity, flatbush: activity}}; see module docstring."""
    prom = prometheus_url.rstrip("/")
    loki = loki_url.rstrip("/")

    def prom_url(query: str) -> str:
        return f"{prom}/api/v1/query?{urlencode({'query': query, 'timeout': '2s', 'lookback_delta': '2m'})}"

    def loki_range_url(host: str) -> str:
        params = {"query": f'{{host="{host}"}}', "since": f"{LIMITS['log_window_minutes']}m",
                  "limit": LIMITS["log_rows"], "direction": "backward"}
        return f"{loki}/loki/api/v1/query_range?{urlencode(params)}"

    requests = {
        "containers": prom_url(CONTAINER_QUERY),
        "services": prom_url(SERVICE_QUERY),
        "processes": prom_url(PROCESS_QUERY),
        "probes": prom_url(PROBE_QUERY),
        "coverage": prom_url(COVERAGE_QUERY),
        "loki_counts": f"{loki}/loki/api/v1/query?{urlencode({'query': LOKI_COUNT_QUERY})}",
        **{f"loki_recent_{host}": loki_range_url(host) for host in HOSTS},
    }

    def fetch(url: str):
        try:
            return fetch_json(url, timeout=QUERY_TIMEOUT_SECONDS)
        except Exception:
            return None

    # Independent reads: concurrent so the slowest source, not the sum, bounds latency.
    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        futures = {key: pool.submit(fetch, url) for key, url in requests.items()}
        payloads = {key: future.result() for key, future in futures.items()}

    prom_results = {key: _prometheus_samples(payloads[key]) for key in ("containers", "services", "probes", "coverage", "processes")}
    containers = _build_containers(prom_results["containers"]) if prom_results["containers"] is not None else None
    services = _build_services(prom_results["services"]) if prom_results["services"] is not None else None
    probes = _build_probes(prom_results["probes"]) if prom_results["probes"] is not None else None
    coverage = _build_coverage(prom_results["coverage"]) if prom_results["coverage"] is not None else None
    processes = _build_processes(prom_results["processes"]) if prom_results["processes"] is not None else None
    counts = _loki_vector(payloads["loki_counts"])

    hosts = {}
    for host in HOSTS:
        entries = _loki_entries(payloads[f"loki_recent_{host}"])
        logs, docker = _build_logs(host, counts, entries)
        container_section = (_container_section(containers[host]) if containers is not None
                             else _unavailable_section(LIMITS["containers"], stale_excluded=None,
                                                       freshness_seconds=CONTAINER_FRESH_SECONDS))
        present = {row["name"] for row in containers[host]["rows"].values()} if containers is not None else None
        _apply_log_only(container_section, docker, present)
        unavailable = "unavailable"
        hosts[host] = {
            "containers": container_section,
            "processes": processes[host] if processes is not None else _unavailable_section(LIMITS["processes"]),
            "services": services[host] if services is not None else _unavailable_section(LIMITS["services"]),
            "probes": probes[host] if probes is not None else _unavailable_section(LIMITS["probes"]),
            "logs": logs,
            "coverage": coverage[host] if coverage is not None else {"process_detail": unavailable, "gpu": unavailable},
            "sources": {
                "prometheus": _source_status({k: v is not None for k, v in prom_results.items()}),
                "loki": _source_status({"counts": counts is not None, "recent": entries is not None}),
            },
            "limits": dict(LIMITS),
        }
    return {"hosts": hosts}
