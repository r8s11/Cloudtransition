"""Metrics collector for project health and tailnet host observability."""

import json
import re
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request


def _fetch_json(url: str, timeout: int = 3) -> dict | None:
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def collect_salsatd_metrics() -> dict:
    """Probe local development endpoints, not production availability."""
    base_urls = ["http://localhost:7071", "http://localhost:8080"]
    health = None
    for base in base_urls:
        health = _fetch_json(f"{base}/api/health")
        if health:
            break

    return {
        "status": health.get("status") if health else "unknown",
        "healthy": health is not None,
        "version": health.get("version") if health else None,
        "endpoints_known": ["health", "ratings"],
    }


def collect_project_metrics() -> dict:
    """Collect status of all tracked projects."""
    projects = [
        {"name": "salsatd", "type": "Azure Functions"},
        {"name": "salsasegura-mobile", "type": "React Native"},
        {"name": "Salsa", "type": "React"},
        {"name": "dashboard-app", "type": "FastAPI"},
    ]

    for p in projects:
        if p["name"] == "salsatd":
            m = collect_salsatd_metrics()
            p["status"] = "up" if m["healthy"] else "unknown"
            p["details"] = m
        elif p["name"] == "dashboard-app":
            p["status"] = "up"
            p["details"] = {}
        else:
            p["status"] = "unmonitored"
            p["details"] = {}

    return {"projects": projects}


PARROT_PROMETHEUS = "http://parrot.tail9aa23.ts.net:9091"
PARROT_LOKI = "http://parrot.tail9aa23.ts.net:3100"
HOST_ADDRESSES = {
    "parrot": {"parrot", "parrot.tail9aa23.ts.net", "100.105.235.49"},
    "flatbush": {"flatbush", "flatbush.tail9aa23.ts.net", "100.67.14.72"},
}
HOST_PERCENT_FIELDS = (
    "cpu_percent", "memory_percent", "disk_percent", "cpu_wait_percent",
    "cpu_pressure_percent", "memory_pressure_percent", "io_pressure_percent",
)
HOST_NUMERIC_DETAILS = (
    "memory_total_bytes", "memory_available_bytes",
    "disk_total_bytes", "disk_available_bytes",
    "swap_total_bytes", "swap_used_bytes",
    "uptime_seconds", "cpu_threads", "process_count", "thread_count", "processor_queue_length",
    "processes_running", "processes_blocked", "load1", "load5", "load15",
    "physical_receive_bytes_per_second", "physical_transmit_bytes_per_second",
    "tailscale_receive_bytes_per_second", "tailscale_transmit_bytes_per_second",
    "sample_timestamp",
)
HOST_TEXT_FIELDS = ("os_name", "kernel", "architecture", "platform", "system_volume")
HOST_READING_FIELDS = (*HOST_PERCENT_FIELDS, *HOST_NUMERIC_DETAILS, *HOST_TEXT_FIELDS)
# Linux-only kernel facts; a Windows host never shows them even if a compatibility series carries one.
LINUX_ONLY_FIELDS = (
    "load1", "load5", "load15", "processes_running", "processes_blocked", "cpu_wait_percent",
    "cpu_pressure_percent", "memory_pressure_percent", "io_pressure_percent",
)
# A real host never reports zero of these; zero means a broken or placeholder series.
NONZERO_FIELDS = frozenset((
    "memory_total_bytes", "disk_total_bytes", "cpu_threads", "process_count", "thread_count",
))
SCALAR_STATS = {
    "cpu": "cpu_percent", "memory": "memory_percent", "disk": "disk_percent",
    **{field: field for field in (*HOST_PERCENT_FIELDS[3:], *HOST_NUMERIC_DETAILS)},
}
VOLUME_STATS = ("vol_size", "vol_avail", "vol_readonly", "vol_files", "vol_files_free")
DISK_STATS = ("disk_read", "disk_write", "disk_busy", "disk_queue")
META_STATS = ("os_info", "uname_info", "cpu_info")
SERVICE_PROBE_JOB = "observability-http"
WINDOWS_SYSTEM_VOLUME = "C:"
# Win32_Processor.Architecture codes that windows_cpu_info exposes.
WINDOWS_ARCHITECTURES = {"0": "x86", "5": "arm", "6": "ia64", "9": "x86_64", "12": "arm64"}
MAX_VOLUMES = 24
MAX_DISKS = 16

# Native windows_exporter jobs first; the older duplicate job only breaks ties deterministically.
JOB_ORDER = {"integrations/windows_exporter": 0, "integrations/windows": 1}

PSEUDO_FILESYSTEMS = (
    "tmpfs|overlay|squashfs|devtmpfs|ramfs|proc|sysfs|cgroup2?|nsfs|autofs|fuse.*|efivarfs|bpf|"
    "tracefs|debugfs|securityfs|configfs|pstore|mqueue|hugetlbfs|devpts|binfmt_misc|fusectl|"
    "rpc_pipefs|iso9660"
)
PSEUDO_FILESYSTEM_RE = re.compile(PSEUDO_FILESYSTEMS)
VIRTUAL_MOUNT_PREFIXES = (
    "/var/lib/docker", "/var/lib/containers", "/run/", "/snap/", "/var/snap/", "/proc", "/sys", "/dev",
)
DERIVED_DISK_RE = re.compile(
    r"loop.*|ram.*|zram.*|fd[0-9]+|dm-.*|(?:h|s|v|xv)d[a-z]+[0-9]+|"
    r"nvme[0-9]+n[0-9]+p[0-9]+|mmcblk[0-9]+p[0-9]+"
)
WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:")

NODE_REAL_FILESYSTEMS = f'{{fstype!~"{PSEUDO_FILESYSTEMS}"}}'
NODE_WHOLE_DISKS = f'{{device!~"{DERIVED_DISK_RE.pattern}"}}'
NODE_SYSTEM_FILESYSTEM = '{mountpoint="/",fstype!~"tmpfs|overlay"}'
WINDOWS_SYSTEM_VOLUME_SELECTOR = f'{{volume="{WINDOWS_SYSTEM_VOLUME}"}}'
WINDOWS_DRIVE_VOLUMES = '{volume=~"[A-Za-z]:"}'
WINDOWS_PHYSICAL_DISKS = '{disk!="_Total"}'
# Adapters that are not the machine's real uplinks; Tailscale is reported separately.
WINDOWS_NON_PHYSICAL_NICS = (
    "(?i).*(virtual|loopback|tailscale|tunnel|hyper-v|vethernet|wsl|isatap|teredo|vpn|pseudo|"
    "bluetooth|miniport).*"
)


IDLE_MODE = '{mode="idle"}'


def _matcher(label: str, operator: str, value: str) -> str:
    return '{%s%s"%s"}' % (label, operator, value)


def _rate(name: str, selector: str, window: str) -> str:
    """Rate of series present now; stale series otherwise keep a rate for the whole window."""
    return f"(rate({name}{selector}[{window}]) and {name}{selector})"


def _core_stats(window: str) -> tuple[tuple, tuple]:
    """CPU/memory/system-disk percentages for (Linux or compatibility, native Windows) sources."""
    node = (
        ("cpu", "clamp(100 * (1 - avg by (host, instance, job, source) "
         f"{_rate('node_cpu_seconds_total', IDLE_MODE, window)}), 0, 100)"),
        ("memory", "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)"),
        ("disk", f"max by (host, instance, job, source) (100 * (1 - "
         f"node_filesystem_avail_bytes{NODE_SYSTEM_FILESYSTEM} / "
         f"node_filesystem_size_bytes{NODE_SYSTEM_FILESYSTEM}))"),
    )
    windows = (
        ("cpu", "clamp(100 * (1 - avg by (host, instance, job) "
         f"{_rate('windows_cpu_time_total', IDLE_MODE, window)}), 0, 100)"),
        ("memory", "100 * (1 - windows_memory_available_bytes / windows_memory_physical_total_bytes)"),
        ("disk", f"100 * (1 - windows_logical_disk_free_bytes{WINDOWS_SYSTEM_VOLUME_SELECTOR} / "
         f"windows_logical_disk_size_bytes{WINDOWS_SYSTEM_VOLUME_SELECTOR})"),
    )
    return node, windows


def _tag(name: str, expr: str, source: str = "node") -> str:
    tagged = f'label_replace(({expr}), "dashboard_metric", "{name}", "", "")'
    if source != "node":
        tagged = f'label_replace({tagged}, "dashboard_source", "{source}", "", "")'
    return tagged


def _union(node_stats, windows_stats) -> str:
    return " or ".join(
        [_tag(name, expr) for name, expr in node_stats]
        + [_tag(name, expr, "windows") for name, expr in windows_stats]
    )


def _host_stats(window: str = "5m") -> tuple[tuple, tuple]:
    core_node, core_windows = _core_stats(window)
    idle = '{mode="idle"}'
    iowait = '{mode="iowait"}'
    by_node = "by (host, instance, job, source)"
    by_windows = "by (host, instance, job)"
    node = (
        ("up", 'up{job=~"prometheus|loki|.*node.*|integrations/windows(_exporter)?"}'),
        ("probe", f'probe_success{{job="{SERVICE_PROBE_JOB}",service=~"prometheus|loki"}}'),
        *core_node,
        ("memory_total_bytes", "node_memory_MemTotal_bytes"),
        ("memory_available_bytes", "node_memory_MemAvailable_bytes"),
        ("disk_total_bytes", f"max {by_node} (node_filesystem_size_bytes{NODE_SYSTEM_FILESYSTEM})"),
        ("disk_available_bytes", f"max {by_node} (node_filesystem_avail_bytes{NODE_SYSTEM_FILESYSTEM})"),
        ("swap_total_bytes", "node_memory_SwapTotal_bytes"),
        ("swap_used_bytes", "node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes"),
        ("uptime_seconds", "time() - node_boot_time_seconds"),
        ("cpu_threads", f"count {by_node} (node_cpu_seconds_total{idle})"),
        ("processes_running", "node_procs_running"),
        ("processes_blocked", "node_procs_blocked"),
        ("cpu_wait_percent",
         f"clamp(100 * avg {by_node} {_rate('node_cpu_seconds_total', iowait, window)}, 0, 100)"),
        *(
            (f"{kind}_pressure_percent",
             f"clamp(100 * {_rate(f'node_pressure_{kind}_waiting_seconds_total', '', window)}, 0, 100)")
            for kind in ("cpu", "memory", "io")
        ),
        ("load1", "node_load1"),
        ("load5", "node_load5"),
        ("load15", "node_load15"),
        ("os_info", "node_os_info"),
        ("uname_info", "node_uname_info"),
        ("sample_timestamp", "timestamp(node_uname_info)"),
        *(
            (f"{scope}_{direction}_bytes_per_second",
             f"sum {by_node} "
             f"({_rate(f'node_network_{direction}_bytes_total', _matcher('device', '=~', devices), window)})")
            for scope, devices in (("physical", "en.*|eth.*|wl.*"), ("tailscale", "tailscale.*"))
            for direction in ("receive", "transmit")
        ),
        ("vol_size", f"node_filesystem_size_bytes{NODE_REAL_FILESYSTEMS}"),
        ("vol_avail", f"node_filesystem_avail_bytes{NODE_REAL_FILESYSTEMS}"),
        ("vol_readonly", f"node_filesystem_readonly{NODE_REAL_FILESYSTEMS}"),
        ("vol_files", f"node_filesystem_files{NODE_REAL_FILESYSTEMS}"),
        ("vol_files_free", f"node_filesystem_files_free{NODE_REAL_FILESYSTEMS}"),
        ("disk_read", _rate("node_disk_read_bytes_total", NODE_WHOLE_DISKS, window)),
        ("disk_write", _rate("node_disk_written_bytes_total", NODE_WHOLE_DISKS, window)),
        ("disk_busy",
         f"clamp(100 * {_rate('node_disk_io_time_seconds_total', NODE_WHOLE_DISKS, window)}, 0, 100)"),
        ("disk_queue", f"node_disk_io_now{NODE_WHOLE_DISKS}"),
    )
    windows = (
        *core_windows,
        ("memory_total_bytes", "windows_memory_physical_total_bytes"),
        ("memory_available_bytes", "windows_memory_available_bytes"),
        ("disk_total_bytes", f"windows_logical_disk_size_bytes{WINDOWS_SYSTEM_VOLUME_SELECTOR}"),
        ("disk_available_bytes", f"windows_logical_disk_free_bytes{WINDOWS_SYSTEM_VOLUME_SELECTOR}"),
        ("swap_total_bytes", f"sum {by_windows} (windows_pagefile_limit_bytes)"),
        ("swap_used_bytes",
         f"sum {by_windows} (windows_pagefile_limit_bytes - windows_pagefile_free_bytes)"),
        ("uptime_seconds", "time() - windows_system_boot_time_timestamp"),
        ("cpu_threads", "windows_cpu_logical_processor"),
        ("process_count", "windows_system_processes"),
        ("thread_count", "windows_system_threads"),
        ("processor_queue_length", "windows_system_processor_queue_length"),
        ("os_info", "windows_os_info"),
        ("cpu_info", "windows_cpu_info"),
        ("sample_timestamp", "timestamp(windows_os_info)"),
        *(
            (f"{scope}_{receive}_bytes_per_second",
             f"sum {by_windows} "
             f"({_rate(f'windows_net_bytes_{metric}_total', _matcher('nic', operator, nics), window)})")
            for scope, operator, nics in (
                ("physical", "!~", WINDOWS_NON_PHYSICAL_NICS),
                ("tailscale", "=~", "(?i).*tailscale.*"),
            )
            for receive, metric in (("receive", "received"), ("transmit", "sent"))
        ),
        ("vol_size", f"windows_logical_disk_size_bytes{WINDOWS_DRIVE_VOLUMES}"),
        ("vol_avail", f"windows_logical_disk_free_bytes{WINDOWS_DRIVE_VOLUMES}"),
        ("disk_read", _rate("windows_physical_disk_read_bytes_total", WINDOWS_PHYSICAL_DISKS, window)),
        ("disk_write", _rate("windows_physical_disk_write_bytes_total", WINDOWS_PHYSICAL_DISKS, window)),
        ("disk_busy",
         "clamp(100 * (1 - "
         f"{_rate('windows_physical_disk_idle_seconds_total', WINDOWS_PHYSICAL_DISKS, window)}), 0, 100)"),
        ("disk_queue", f"windows_physical_disk_requests_queued{WINDOWS_PHYSICAL_DISKS}"),
    )
    return node, windows


# One instant query keeps an unavailable tailnet to one network timeout.
HOST_QUERY = _union(*_host_stats())

HISTORY_WINDOWS = {"1h": (3600, 30), "6h": (21600, 150), "24h": (86400, 600)}
HISTORY_METRICS = {"cpu": "cpu_percent", "memory": "memory_percent", "disk": "disk_percent"}
HISTORY_MAX_POINTS = 150


def _host_of(labels: dict) -> str:
    host_name = str(labels.get("host") or "").lower()
    if host_name:
        return host_name
    address = str(labels.get("instance") or "").split(":")[0].lower()
    return next((name for name, addresses in HOST_ADDRESSES.items() if address in addresses), "")


def _rank(source: str, job, instance) -> tuple:
    """Native Windows first, then a stable job order; never merged or summed across candidates."""
    return (0 if source == "windows" else 1, JOB_ORDER.get(job, len(JOB_ORDER)),
            str(job or ""), str(instance or ""))


def _scalar_value(field: str, value: float) -> float | None:
    if field in HOST_PERCENT_FIELDS:
        return round(value, 1) if 0 <= value <= 100 else None
    if value < 0 or (value == 0 and field in NONZERO_FIELDS):
        return None
    return value


def _preferred_exporter(items: list) -> list:
    """Keep one exporter's rows (native Windows, then best job) so duplicates never mix."""
    if not items:
        return []
    best = min(item[0] for item in items)
    return [item for item in items if item[0] == best]


def _nonnegative(value) -> float | None:
    return value if value is not None and value >= 0 else None


def _build_volumes(items: list) -> list:
    volumes = {}
    for rank, labels, stat, value in _preferred_exporter(items):
        if rank[0] == 0:
            device = mount = labels.get("volume")
            if not isinstance(device, str) or not WINDOWS_DRIVE_RE.fullmatch(device):
                continue
            name = device
        else:
            device, mount = labels.get("device"), labels.get("mountpoint")
            fstype = labels.get("fstype") or ""
            if (not isinstance(device, str) or not isinstance(mount, str)
                    or "device_error" in labels
                    or PSEUDO_FILESYSTEM_RE.fullmatch(fstype)
                    or device.startswith(("overlay", "/dev/loop"))
                    or mount.startswith(VIRTUAL_MOUNT_PREFIXES)):
                continue
            # Windows compatibility series mount everything at "/"; the drive letter is the identity.
            name = device if labels.get("source") == "windows_exporter" and WINDOWS_DRIVE_RE.fullmatch(device) else mount
        entry = volumes.setdefault((device, mount), {"name": name, "device": device, "mount": mount})
        entry.setdefault(stat, value)

    unique = {}
    for entry in volumes.values():
        size = entry.get("vol_size")
        if not size or size <= 0:
            continue
        # Bind mounts and subvolumes of one filesystem report the same device and size.
        key = (entry["device"], size)
        current = unique.get(key)
        order = (entry["mount"] != "/", len(entry["mount"]), entry["mount"])
        if current is None or order < current[0]:
            unique[key] = (order, entry)

    rows = []
    for _, entry in unique.values():
        size = entry["vol_size"]
        avail = _nonnegative(entry.get("vol_avail"))
        if avail is not None and avail > size:
            avail = None
        files, files_free = entry.get("vol_files"), entry.get("vol_files_free")
        inode = None
        if files and files > 0 and files_free is not None and 0 <= files_free <= files:
            inode = round(100 * (1 - files_free / files), 1)
        readonly = entry.get("vol_readonly")
        rows.append({
            "name": entry["name"],
            "device": entry["device"],
            "total_bytes": size,
            "available_bytes": avail,
            "used_percent": None if avail is None else round(100 * (1 - avail / size), 1),
            "inode_used_percent": inode,
            "readonly": None if readonly not in (0, 1) else bool(readonly),
        })
    rows.sort(key=lambda row: (row["name"] not in ("/", WINDOWS_SYSTEM_VOLUME), row["name"]))
    return rows[:MAX_VOLUMES]


def _build_disks(items: list) -> list:
    disks = {}
    for rank, labels, stat, value in _preferred_exporter(items):
        if value < 0:
            continue
        if rank[0] == 0:
            raw = labels.get("disk")
            if not isinstance(raw, str) or not raw or raw == "_Total":
                continue
            device = f"Disk {raw}" if raw.isdigit() else raw
        else:
            device = labels.get("device")
            if not isinstance(device, str) or DERIVED_DISK_RE.fullmatch(device):
                continue
        disks.setdefault(device, {}).setdefault(stat, value)

    rows = []
    for device, entry in disks.items():
        busy = entry.get("disk_busy")
        row = {
            "device": device,
            "read_bytes_per_second": entry.get("disk_read"),
            "write_bytes_per_second": entry.get("disk_write"),
            "busy_percent": round(busy, 1) if busy is not None and busy <= 100 else None,
            "io_in_progress": entry.get("disk_queue"),
        }
        if any(value is not None for key, value in row.items() if key != "device"):
            rows.append(row)
    rows.sort(key=lambda row: [int(part) if part.isdigit() else part
                               for part in re.split(r"(\d+)", row["device"])])
    return rows[:MAX_DISKS]


def collect_infrastructure_metrics() -> dict:
    """Read Parrot's Prometheus; absent telemetry is not evidence of a down host."""
    hosts = {
        name: {"status": "unknown", **dict.fromkeys(HOST_READING_FIELDS),
               "volumes": [], "disks": [], "exporter_job": None, "exporter_instance": None}
        for name in HOST_ADDRESSES
    }
    services = {"prometheus": "unknown", "loki": "unknown"}
    result = {"hosts": hosts, "services": services,
              "service_sources": dict.fromkeys(services)}
    payload = _fetch_json(
        f"{PARROT_PROMETHEUS}/api/v1/query?"
        + urlencode({"query": HOST_QUERY, "timeout": "2s", "lookback_delta": "2m"})
    )
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return result
    data = payload.get("data", {})
    if not isinstance(data, dict) or data.get("resultType") != "vector":
        return result
    rows = data.get("result")
    if not isinstance(rows, list):
        return result

    for host in hosts.values():
        host["status"] = "pending"
    exporter_up = {name: [] for name in hosts}
    readings = {name: {} for name in hosts}
    meta = {name: {stat: [] for stat in META_STATS} for name in hosts}
    lists = {name: {"volumes": [], "disks": []} for name in hosts}
    evidence = {name: {"windows": False, "any": False, "best": None} for name in hosts}
    probes, scrapes = {}, {}
    for row in rows:
        try:
            labels = row["metric"]
            value = float(row["value"][1])
            if not math.isfinite(value):
                continue
            host_name = _host_of(labels)
            if host_name not in hosts:
                continue
            stat = labels.get("dashboard_metric")
            job = labels.get("job")
            instance = labels.get("instance")
            if stat == "up":
                if value not in (0, 1):
                    continue
                if job in services:
                    if host_name == "parrot":
                        scrapes[job] = value == 1
                    continue
                source = "windows" if str(job).startswith("integrations/windows") else "node"
                exporter_up[host_name].append((_rank(source, job, instance), value == 1))
                continue
            if stat == "probe":
                service = labels.get("service")
                if (value in (0, 1) and host_name == "parrot" and job == SERVICE_PROBE_JOB
                        and service in services):
                    probes[service] = value == 1
                continue
            source = "windows" if labels.get("dashboard_source") == "windows" else "node"
            rank = _rank(source, job, instance)
            field = SCALAR_STATS.get(stat)
            if field:
                reading = _scalar_value(field, value)
                if reading is None:
                    continue
                readings[host_name].setdefault(field, []).append((rank, reading))
            elif stat in META_STATS:
                if value != 1:
                    continue
                meta[host_name][stat].append((rank, labels))
            elif stat in VOLUME_STATS:
                lists[host_name]["volumes"].append((rank, labels, stat, value))
            elif stat in DISK_STATS:
                lists[host_name]["disks"].append((rank, labels, stat, value))
            else:
                continue
            seen = evidence[host_name]
            seen["any"] = True
            seen["windows"] = seen["windows"] or source == "windows" or labels.get("source") == "windows_exporter"
            if seen["best"] is None or rank < seen["best"]:
                seen["best"] = rank
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            continue

    for name, host in hosts.items():
        for field, candidates in readings[name].items():
            host[field] = min(candidates, key=lambda candidate: candidate[0])[1]
        seen = evidence[name]
        host["platform"] = "windows" if seen["windows"] else "linux" if seen["any"] else None
        if host["platform"] == "windows":
            for field in LINUX_ONLY_FIELDS:
                host[field] = None

        os_info = min(meta[name]["os_info"], key=lambda item: item[0], default=None)
        uname = min(meta[name]["uname_info"], key=lambda item: item[0], default=None)
        cpu_info = min(meta[name]["cpu_info"], key=lambda item: item[0], default=None)
        if os_info:
            labels = os_info[1]
            host["os_name"] = labels.get("pretty_name") or labels.get("name") or labels.get("product")
            if os_info[0][0] == 0:
                host["kernel"] = labels.get("version")
        if uname and host["kernel"] is None:
            host["kernel"] = uname[1].get("release")
        if cpu_info:
            host["architecture"] = WINDOWS_ARCHITECTURES.get(str(cpu_info[1].get("architecture")))
        if uname and host["architecture"] is None:
            host["architecture"] = uname[1].get("machine")

        host["volumes"] = _build_volumes(lists[name]["volumes"])
        host["disks"] = _build_disks(lists[name]["disks"])
        if host["platform"] and (host["disk_percent"] is not None or host["disk_total_bytes"] is not None
                                 or any(volume["name"] in ("/", WINDOWS_SYSTEM_VOLUME)
                                        for volume in host["volumes"])):
            host["system_volume"] = WINDOWS_SYSTEM_VOLUME if host["platform"] == "windows" else "/"

        # Exporter health and identity come from one deterministic exporter, never an average.
        exporter = min(exporter_up[name], key=lambda item: item[0], default=None)
        identity = exporter[0] if exporter else seen["best"]
        if identity:
            host["exporter_job"], host["exporter_instance"] = identity[2] or None, identity[3] or None

        if exporter and not exporter[1]:
            host.update(dict.fromkeys(HOST_READING_FIELDS))
            host["volumes"], host["disks"] = [], []
            host["status"] = "down"
        elif exporter or any(host[field] is not None for field in HOST_READING_FIELDS) \
                or host["volumes"] or host["disks"]:
            host["status"] = "up"

    # A probe is application health; scrape success only says Prometheus reached that target.
    for name in services:
        if name in probes:
            services[name], result["service_sources"][name] = ("up" if probes[name] else "down"), "probe"
        elif name in scrapes:
            services[name], result["service_sources"][name] = ("up" if scrapes[name] else "down"), "scrape"
    return result


def collect_metric_history(window: str = "1h") -> dict:
    """Range history for CPU, memory and system disk, using Prometheus's own clock."""
    if not isinstance(window, str) or window not in HISTORY_WINDOWS:
        raise ValueError(f"window must be one of {', '.join(HISTORY_WINDOWS)}")
    seconds, step = HISTORY_WINDOWS[window]
    result = {
        "status": "unavailable", "window": window, "step_seconds": step,
        "start": None, "end": None,
        "hosts": {name: {field: [] for field in HISTORY_METRICS.values()} for name in HOST_ADDRESSES},
    }
    clock = _fetch_json(f"{PARROT_PROMETHEUS}/api/v1/query?" + urlencode({"query": "time()"}), timeout=2)
    try:
        if clock["status"] != "success" or clock["data"]["resultType"] != "scalar":
            return result
        now = float(clock["data"]["result"][0])
    except (KeyError, IndexError, TypeError, ValueError):
        return result
    if not math.isfinite(now) or now <= 0:
        return result

    # Aligned to the step so each refresh draws the same sample times.
    end = int(now // step * step)
    start = end - seconds
    node, windows = _core_stats(f"{max(300, step)}s")
    payload = _fetch_json(
        f"{PARROT_PROMETHEUS}/api/v1/query_range?"
        + urlencode({
            "query": _union(node, windows), "start": start, "end": end, "step": step,
            "timeout": "5s", "lookback_delta": f"{max(2 * step, 90)}s",
        }),
        timeout=6,
    )
    try:
        if payload["status"] != "success" or payload["data"]["resultType"] != "matrix":
            return result
        series_list = payload["data"]["result"]
        if not isinstance(series_list, list):
            return result
    except (KeyError, TypeError):
        return result

    candidates = {name: {stat: [] for stat in HISTORY_METRICS} for name in HOST_ADDRESSES}
    for series in series_list:
        try:
            labels = series["metric"]
            host_name = _host_of(labels)
            stat = labels.get("dashboard_metric")
            if host_name not in candidates or stat not in HISTORY_METRICS:
                continue
            source = "windows" if labels.get("dashboard_source") == "windows" else "node"
            samples = {}
            for timestamp, raw in series["values"]:
                moment, value = float(timestamp), float(raw)
                if math.isfinite(moment) and math.isfinite(value) and start <= moment <= end and 0 <= value <= 100:
                    samples[moment] = round(value, 1)
            candidates[host_name][stat].append((_rank(source, labels.get("job"), labels.get("instance")), samples))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue

    for host_name, stats in candidates.items():
        for stat, series in stats.items():
            merged = {}
            # Best source wins each timestamp; a gap in every source stays a gap.
            for _, samples in sorted(series, key=lambda item: item[0]):
                for moment, value in samples.items():
                    merged.setdefault(moment, value)
            points = sorted(merged.items())[-HISTORY_MAX_POINTS:]
            result["hosts"][host_name][HISTORY_METRICS[stat]] = [
                [int(moment) if moment.is_integer() else moment, value] for moment, value in points
            ]
    result.update(status="ok", start=start, end=end)
    return result


def collect_all_metrics() -> dict:
    """Collect independent monitoring sources concurrently within their timeouts."""
    from collectors.server_activity import collect_server_activity

    with ThreadPoolExecutor(max_workers=2) as pool:
        infrastructure_job = pool.submit(collect_infrastructure_metrics)
        activity_job = pool.submit(collect_server_activity, _fetch_json, PARROT_PROMETHEUS, PARROT_LOKI)
        projects = collect_project_metrics()["projects"]
        infrastructure = infrastructure_job.result()
        activity = activity_job.result()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "projects": projects,
        "infrastructure": infrastructure,
        "activity": activity,
    }
