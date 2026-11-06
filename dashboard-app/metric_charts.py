"""Bounded, read-only history for the Metrics page charts.

Network and disk rates, blackbox probe results and Loki log volume over the
same allowlisted windows as the performance history. Every section carries its
own status, so one unreachable or slow source never blanks the others. Missing
samples stay missing: nothing is interpolated or filled with zero.
"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import metrics
from server_activity import HOSTS, clean_text, resolve_host

MAX_CHART_DISKS = 8
MAX_CHART_PROBES = 30
MAX_LOG_LEVELS = 8
RANGE_TIMEOUT = 6
NETWORK_SCOPES = ("physical", "tailscale")
DIRECTIONS = ("receive", "transmit")


def _fetch():
    # Looked up at call time so tests can replace metrics._fetch_json.
    return metrics._fetch_json


def _window(window: str) -> tuple[int, int]:
    if not isinstance(window, str) or window not in metrics.HISTORY_WINDOWS:
        raise ValueError(f"window must be one of {', '.join(metrics.HISTORY_WINDOWS)}")
    return metrics.HISTORY_WINDOWS[window]


def _bounds(now: float, seconds: int, step: int) -> tuple[int, int]:
    end = int(now // step * step)
    return end - seconds, end


def _prometheus_now(fetch) -> float | None:
    clock = fetch(f"{metrics.PARROT_PROMETHEUS}/api/v1/query?" + urlencode({"query": "time()"}), timeout=2)
    try:
        if clock["status"] != "success" or clock["data"]["resultType"] != "scalar":
            return None
        now = float(clock["data"]["result"][0])
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return now if math.isfinite(now) and now > 0 else None


def _matrix(fetch, query: str, start: int, end: int, step: int) -> list | None:
    payload = fetch(
        f"{metrics.PARROT_PROMETHEUS}/api/v1/query_range?"
        + urlencode({"query": query, "start": start, "end": end, "step": step,
                     "timeout": "5s", "lookback_delta": f"{max(2 * step, 90)}s"}),
        timeout=RANGE_TIMEOUT,
    )
    try:
        if payload["status"] != "success" or payload["data"]["resultType"] != "matrix":
            return None
        result = payload["data"]["result"]
    except (KeyError, TypeError):
        return None
    return result if isinstance(result, list) else None


def _points(values, start: int, end: int, *, upper: float | None = None) -> dict[float, float]:
    """Finite, non-negative samples inside the window; invalid ones are dropped, never zeroed."""
    out = {}
    for item in values if isinstance(values, list) else []:
        try:
            moment, value = float(item[0]), float(item[1])
        except (IndexError, TypeError, ValueError):
            continue
        if not (math.isfinite(moment) and math.isfinite(value)) or not start <= moment <= end or value < 0:
            continue
        if upper is not None and value > upper:
            continue
        out[moment] = value
    return out


def _as_list(samples: dict[float, float], digits: int = 1) -> list:
    points = sorted(samples.items())[-metrics.HISTORY_MAX_POINTS:]
    return [[int(t) if t.is_integer() else t, round(v, digits)] for t, v in points]


def _merge(candidates: list[tuple[tuple, dict]]) -> dict[float, float]:
    merged: dict[float, float] = {}
    for _, samples in sorted(candidates, key=lambda item: item[0]):
        for moment, value in samples.items():
            merged.setdefault(moment, value)
    return merged


def _section(status: str, start=None, end=None, step=None, **extra) -> dict:
    return {"status": status, "start": start, "end": end, "step_seconds": step, **extra}


# ------------------------------------------------------------------ network & disk rates

def _rate_query(rate_window: str) -> str:
    node, windows = [], []
    for scope, devices in (("physical", "en.*|eth.*|wl.*"), ("tailscale", "tailscale.*")):
        for direction in DIRECTIONS:
            node.append((f"net_{scope}_{direction}",
                         "sum by (host, instance, job, source) ("
                         + metrics._rate(f"node_network_{direction}_bytes_total",
                                         metrics._matcher("device", "=~", devices), rate_window) + ")"))
    for scope, operator, nics in (("physical", "!~", metrics.WINDOWS_NON_PHYSICAL_NICS),
                                  ("tailscale", "=~", "(?i).*tailscale.*")):
        for direction, metric in (("receive", "received"), ("transmit", "sent")):
            windows.append((f"net_{scope}_{direction}",
                            "sum by (host, instance, job) ("
                            + metrics._rate(f"windows_net_bytes_{metric}_total",
                                            metrics._matcher("nic", operator, nics), rate_window) + ")"))
    node += [
        ("disk_read", metrics._rate("node_disk_read_bytes_total", metrics.NODE_WHOLE_DISKS, rate_window)),
        ("disk_write", metrics._rate("node_disk_written_bytes_total", metrics.NODE_WHOLE_DISKS, rate_window)),
    ]
    windows += [
        ("disk_read", metrics._rate("windows_physical_disk_read_bytes_total", metrics.WINDOWS_PHYSICAL_DISKS, rate_window)),
        ("disk_write", metrics._rate("windows_physical_disk_write_bytes_total", metrics.WINDOWS_PHYSICAL_DISKS, rate_window)),
    ]
    return metrics._union(node, windows)


def _empty_host_rates() -> dict:
    return {"network": {scope: {d: [] for d in DIRECTIONS} for scope in NETWORK_SCOPES},
            "disks": {}, "idle_disks": [], "more_disks": []}


def collect_rate_history(window: str = "1h", fetch=None, now: float | None = None) -> dict:
    seconds, step = _window(window)
    fetch = fetch or _fetch()
    result = _section("unavailable", window=window, hosts={h: _empty_host_rates() for h in HOSTS})
    now = now if now is not None else _prometheus_now(fetch)
    if now is None:
        return result
    start, end = _bounds(now, seconds, step)
    series_list = _matrix(fetch, _rate_query(f"{max(300, step)}s"), start, end, step)
    if series_list is None:
        return result

    net: dict = {h: {(s, d): [] for s in NETWORK_SCOPES for d in DIRECTIONS} for h in HOSTS}
    disks: dict = {h: {} for h in HOSTS}
    for series in series_list:
        try:
            labels = series["metric"]
            host = metrics._host_of(labels)
            stat = labels.get("dashboard_metric", "")
            source = "windows" if labels.get("dashboard_source") == "windows" else "node"
            rank = metrics._rank(source, labels.get("job"), labels.get("instance"))
            samples = _points(series["values"], start, end)
        except (KeyError, TypeError, AttributeError):
            continue
        if host not in net:
            continue
        if stat.startswith("net_"):
            _, scope, direction = stat.split("_", 2)
            if (scope, direction) in net[host]:
                net[host][(scope, direction)].append((rank, samples))
        elif stat in ("disk_read", "disk_write"):
            device = clean_text(labels.get("device") or labels.get("disk") or "", 64)
            if device:
                disks[host].setdefault(device, {"read": [], "write": []})[stat[5:]].append((rank, samples))

    hosts = {}
    for host in HOSTS:
        entry = _empty_host_rates()
        for (scope, direction), candidates in net[host].items():
            entry["network"][scope][direction] = _as_list(_merge(candidates), 0)
        active = []
        for device, pair in disks[host].items():
            read, write = _merge(pair["read"]), _merge(pair["write"])
            total = sum(read.values()) + sum(write.values())
            if total <= 0:
                entry["idle_disks"].append(device)
            else:
                active.append((total, device, read, write))
        active.sort(key=lambda item: (-item[0], item[1]))
        for _, device, read, write in active[:MAX_CHART_DISKS]:
            entry["disks"][device] = {"read": _as_list(read, 0), "write": _as_list(write, 0)}
        entry["more_disks"] = sorted(device for _, device, _, _ in active[MAX_CHART_DISKS:])
        entry["idle_disks"].sort()
        hosts[host] = entry
    return _section("ok", start, end, step, window=window, hosts=hosts)


# ------------------------------------------------------------------ probe timeline

def collect_probe_history(window: str = "1h", fetch=None, now: float | None = None) -> dict:
    seconds, step = _window(window)
    fetch = fetch or _fetch()
    result = _section("unavailable", window=window, hosts={h: [] for h in HOSTS})
    now = now if now is not None else _prometheus_now(fetch)
    if now is None:
        return result
    start, end = _bounds(now, seconds, step)
    series_list = _matrix(fetch, "probe_success", start, end, step)
    if series_list is None:
        return result
    slots = list(range(start, end + 1, step))[-metrics.HISTORY_MAX_POINTS:]
    hosts: dict = {h: [] for h in HOSTS}
    for series in series_list:
        try:
            labels = series["metric"]
            samples = _points(series["values"], start, end, upper=1)
        except (KeyError, TypeError):
            continue
        host = resolve_host(labels) if isinstance(labels, dict) else None
        if host not in hosts:
            continue
        instance = str(labels.get("instance", ""))
        kind = "http" if instance.lower().startswith(("http://", "https://")) else "tcp" if ":" in instance else None
        by_slot = {}
        for moment, value in samples.items():
            index = round((moment - slots[0]) / step)
            if 0 <= index < len(slots) and value in (0.0, 1.0):
                by_slot[index] = int(value)
        hosts[host].append({
            "service": clean_text(labels.get("service") or instance, 128) or "unknown",
            "kind": kind,
            "target": clean_text(instance, 200) or None,
            "values": [by_slot.get(i) for i in range(len(slots))],
        })
    for host in HOSTS:
        hosts[host].sort(key=lambda r: (r["service"].casefold(), r["kind"] or "", r["target"] or ""))
        hosts[host] = hosts[host][:MAX_CHART_PROBES]
    return _section("ok", slots[0], end, step, window=window, hosts=hosts)


# ------------------------------------------------------------------ log volume

def collect_log_volume(window: str = "1h", fetch=None, now: float | None = None) -> dict:
    seconds, step = _window(window)
    fetch = fetch or _fetch()
    result = _section("unavailable", window=window, hosts={h: {"levels": {}} for h in HOSTS})
    # Loki is independent of Prometheus, so its window uses local time when needed.
    now = now if now is not None else time.time()
    start, end = _bounds(now, seconds, step)
    slots = list(range(start, end + 1, step))[-metrics.HISTORY_MAX_POINTS:]
    query = f'sum by (host, level) (count_over_time({{host=~"{"|".join(HOSTS)}"}}[{step}s]))'
    payload = fetch(
        f"{metrics.PARROT_LOKI}/loki/api/v1/query_range?"
        + urlencode({"query": query, "start": slots[0], "end": end, "step": step}),
        timeout=RANGE_TIMEOUT,
    )
    try:
        if payload["status"] != "success" or payload["data"]["resultType"] != "matrix":
            return result
        series_list = payload["data"]["result"]
        if not isinstance(series_list, list):
            return result
    except (KeyError, TypeError):
        return result
    hosts = {h: {"levels": {}} for h in HOSTS}
    for series in series_list:
        try:
            labels = series["metric"]
            host = str(labels.get("host") or "").lower()
            samples = _points(series["values"], slots[0] - step, end)
        except (KeyError, TypeError, AttributeError):
            continue
        if host not in hosts:
            continue
        # Severity is whatever the source reported; an absent label is "unknown", never guessed.
        level = clean_text(labels.get("level") or "", 32) or "unknown"
        levels = hosts[host]["levels"]
        if level not in levels and len(levels) >= MAX_LOG_LEVELS:
            level = "other"
        counts = levels.setdefault(level, [0] * len(slots))
        for moment, value in samples.items():
            index = round((moment - slots[0]) / step)
            if 0 <= index < len(slots):
                counts[index] += int(value)
    return _section("ok", slots[0], end, step, window=window, hosts=hosts)


# ------------------------------------------------------------------ combined endpoint

def collect_chart_history(window: str = "1h", fetch=None) -> dict:
    seconds, step = _window(window)
    fetch = fetch or _fetch()

    def guarded(collector, empty_hosts):
        try:
            return collector(window, fetch=fetch)
        except Exception:
            return _section("unavailable", window=window, hosts=empty_hosts)

    with ThreadPoolExecutor(max_workers=3) as pool:
        rates = pool.submit(guarded, collect_rate_history, {h: _empty_host_rates() for h in HOSTS})
        probes = pool.submit(guarded, collect_probe_history, {h: [] for h in HOSTS})
        logs = pool.submit(guarded, collect_log_volume, {h: {"levels": {}} for h in HOSTS})
        return {"window": window, "step_seconds": step,
                "rates": rates.result(), "probes": probes.result(), "logs": logs.result()}
