"""Cross-platform host snapshot and range history stay truthful about source, absence and time."""

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import metrics  # noqa: E402

NATIVE = "integrations/windows_exporter"


def sample(host, stat, value, job="parrot-node", **labels):
    return {"metric": {"host": host, "dashboard_metric": stat, "job": job, **labels},
            "value": [1793400000, str(value)]}


def native(stat, value, job=NATIVE, **labels):
    return sample("flatbush", stat, value, job, dashboard_source="windows", instance="flatbush", **labels)


def compat(stat, value, **labels):
    return sample("flatbush", stat, value, "flatbush-node", source="windows_exporter", **labels)


def collect(monkeypatch, rows):
    payload = {"status": "success", "data": {"resultType": "vector", "result": rows}}
    monkeypatch.setattr(metrics, "_fetch_json", lambda *args, **kwargs: payload)
    return metrics.collect_infrastructure_metrics()


def test_native_windows_beats_compatibility_series_and_never_shows_linux_load(monkeypatch):
    host = collect(monkeypatch, [
        compat("cpu", 10), native("cpu", 40),
        compat("memory", 55), compat("load1", 3),
        compat("disk", 70), compat("processes_running", 4),
        native("os_info", 1, product="Windows 10 Home", version="10.0.19045"),
        native("cpu_info", 1, architecture="9"),
        native("process_count", 308), native("thread_count", 4153),
    ])["hosts"]["flatbush"]
    assert host["cpu_percent"] == 40
    assert host["memory_percent"] == 55  # compatibility is only a fallback for absent native data
    assert host["platform"] == "windows"
    assert host["system_volume"] == "C:"
    assert host["os_name"] == "Windows 10 Home"
    assert host["kernel"] == "10.0.19045"
    assert host["architecture"] == "x86_64"
    assert host["process_count"] == 308
    assert host["thread_count"] == 4153
    assert host["load1"] is None and host["processes_running"] is None


def test_duplicate_native_jobs_pick_one_exporter_without_averaging(monkeypatch):
    host = collect(monkeypatch, [
        native("cpu", 20, job="integrations/windows"),
        native("cpu", 60),
        native("up", 1, job="integrations/windows"),
        native("up", 1),
    ])["hosts"]["flatbush"]
    assert host["cpu_percent"] == 60
    assert host["exporter_job"] == NATIVE


def test_windows_processor_queue_preserves_zero_and_clears_on_exporter_down(monkeypatch):
    host = collect(monkeypatch, [
        compat("processor_queue_length", 15),
        native("processor_queue_length", 0),
    ])["hosts"]["flatbush"]
    assert host["processor_queue_length"] == 0
    invalid = collect(monkeypatch, [native("processor_queue_length", -1)])["hosts"]["flatbush"]
    assert invalid["processor_queue_length"] is None
    down = collect(monkeypatch, [native("processor_queue_length", 5), native("up", 0)])["hosts"]["flatbush"]
    assert down["processor_queue_length"] is None


def test_compatibility_only_windows_host_is_still_windows_with_drive_volume(monkeypatch):
    host = collect(monkeypatch, [
        compat("cpu", 12),
        compat("disk", 62),
        compat("vol_size", 1000, device="C:", mountpoint="/", fstype="NTFS"),
        compat("vol_avail", 400, device="C:", mountpoint="/", fstype="NTFS"),
    ])["hosts"]["flatbush"]
    assert host["platform"] == "windows"
    assert host["system_volume"] == "C:"
    assert host["volumes"] == [{
        "name": "C:", "device": "C:", "total_bytes": 1000, "available_bytes": 400,
        "used_percent": 60.0, "inode_used_percent": None, "readonly": None,
    }]


def test_exporter_health_is_not_service_or_probe_health(monkeypatch):
    result = collect(monkeypatch, [
        sample("parrot", "up", 1, "prometheus"),
        sample("parrot", "up", 1, "loki"),
        sample("parrot", "probe", 0, "observability-http", service="prometheus"),
        sample("parrot", "probe", 1, "parrot-services", service="loki"),  # wrong job is ignored
        sample("flatbush", "probe", 0, "observability-http", service="loki"),  # another host's probe
    ])
    assert result["services"] == {"prometheus": "down", "loki": "up"}
    assert result["service_sources"] == {"prometheus": "probe", "loki": "scrape"}
    assert result["hosts"]["parrot"]["status"] == "pending"
    assert result["hosts"]["flatbush"]["status"] == "pending"


def test_native_exporter_down_clears_all_readings_even_when_compat_exporter_is_up(monkeypatch):
    host = collect(monkeypatch, [
        native("up", 0), compat("up", 1),
        native("cpu", 40), native("process_count", 300), native("swap_total_bytes", 0),
        native("vol_size", 100, volume="C:"), native("disk_read", 5, disk="0"),
        native("os_info", 1, product="Windows 10 Home", version="10.0.19045"),
    ])["hosts"]["flatbush"]
    assert host["status"] == "down"
    for field in metrics.HOST_READING_FIELDS:
        assert host[field] is None, field
    assert host["volumes"] == [] and host["disks"] == []


def test_zero_missing_and_impossible_values_are_distinguished(monkeypatch):
    host = collect(monkeypatch, [
        sample("parrot", "swap_total_bytes", 0),
        sample("parrot", "swap_used_bytes", "NaN"),
        sample("parrot", "process_count", 0),
        sample("parrot", "thread_count", -3),
        sample("parrot", "cpu_pressure_percent", 0),
        sample("parrot", "memory_pressure_percent", 101),
        sample("parrot", "processes_blocked", 0),
        sample("parrot", "io_pressure_percent", "+Inf"),
    ])["hosts"]["parrot"]
    assert host["swap_total_bytes"] == 0
    assert host["processes_blocked"] == 0
    assert host["cpu_pressure_percent"] == 0
    assert host["swap_used_bytes"] is None
    assert host["process_count"] is None
    assert host["thread_count"] is None
    assert host["memory_pressure_percent"] is None
    assert host["io_pressure_percent"] is None
    assert host["platform"] == "linux" and host["system_volume"] is None


def test_linux_volumes_exclude_pseudo_and_duplicate_mounts(monkeypatch):
    def fs(stat, value, mount, device="/dev/sda2", fstype="btrfs", **extra):
        return sample("parrot", stat, value, device=device, mountpoint=mount, fstype=fstype, **extra)

    rows = []
    for mount, device, fstype in (
        ("/", "/dev/sda2", "btrfs"), ("/home", "/dev/sda2", "btrfs"),
        ("/boot/efi", "/dev/sda1", "vfat"), ("/run", "tmpfs", "tmpfs"),
        ("/var/lib/docker/overlay2/x/merged", "overlay", "overlay"),
        ("/var/lib/docker/vol", "/dev/sdb1", "ext4"),
        ("/mnt/zero", "/dev/sdc1", "ext4"),
    ):
        size = 0 if mount == "/mnt/zero" else 1000 if device == "/dev/sda2" else 100
        rows += [fs("vol_size", size, mount, device, fstype), fs("vol_avail", size / 4, mount, device, fstype)]
    rows += [
        fs("vol_files", 200, "/boot/efi", "/dev/sda1", "vfat"),
        fs("vol_files_free", 50, "/boot/efi", "/dev/sda1", "vfat"),
        fs("vol_readonly", 1, "/boot/efi", "/dev/sda1", "vfat"),
        fs("vol_files", 0, "/", "/dev/sda2"),
        fs("vol_files_free", 0, "/", "/dev/sda2"),
    ]
    volumes = collect(monkeypatch, rows)["hosts"]["parrot"]["volumes"]
    assert [volume["name"] for volume in volumes] == ["/", "/boot/efi"]
    assert volumes[0]["used_percent"] == 75.0
    assert volumes[0]["inode_used_percent"] is None  # btrfs reports no inode count
    assert volumes[1]["inode_used_percent"] == 75.0
    assert volumes[1]["readonly"] is True and volumes[0]["readonly"] is None


def test_windows_volumes_keep_drive_letters_only_and_disks_skip_partitions(monkeypatch):
    host = collect(monkeypatch, [
        native("vol_size", 1000, volume="C:"), native("vol_avail", 250, volume="C:"),
        native("vol_size", 100, volume="HarddiskVolume1"), native("vol_avail", 10, volume="HarddiskVolume1"),
        native("disk_read", 0, disk="0"), native("disk_write", 12, disk="0"),
        native("disk_busy", 140, disk="0"), native("disk_queue", 0, disk="0"),
        native("disk_write", 5, disk="_Total"),
        sample("parrot", "disk_read", 10, device="sda"),
        sample("parrot", "disk_read", 10, device="sda1"),
        sample("parrot", "disk_read", 10, device="loop3"),
        sample("parrot", "disk_busy", 1.26, device="sda"),
    ])["hosts"]
    assert [volume["name"] for volume in host["flatbush"]["volumes"]] == ["C:"]
    assert host["flatbush"]["disks"] == [{
        "device": "Disk 0", "read_bytes_per_second": 0, "write_bytes_per_second": 12,
        "busy_percent": None, "io_in_progress": 0,
    }]
    assert [(d["device"], d["busy_percent"]) for d in host["parrot"]["disks"]] == [("sda", 1.3)]


def test_unreachable_prometheus_still_has_empty_lists_and_unknown_sources(monkeypatch):
    monkeypatch.setattr(metrics, "_fetch_json", lambda *args, **kwargs: None)
    result = metrics.collect_infrastructure_metrics()
    assert all(host["volumes"] == [] and host["disks"] == [] and host["platform"] is None
               for host in result["hosts"].values())
    assert set(result["service_sources"].values()) == {None}


def test_host_query_is_single_bounded_and_names_only_expected_native_sources():
    assert len(metrics.HOST_QUERY) < 20_000
    assert "windows_logical_disk_size_bytes" in metrics.HOST_QUERY
    assert 'volume="C:"' in metrics.HOST_QUERY and 'volume=~"[A-Za-z]:"' in metrics.HOST_QUERY
    assert "windows_physical_disk_idle_seconds_total" in metrics.HOST_QUERY


# --- history -----------------------------------------------------------------------------------

PROM_NOW = 1793474197.736


def history_fetch(monkeypatch, matrix, now=PROM_NOW, range_status="success"):
    calls = []

    def fake(url, timeout=3):
        calls.append((url, timeout))
        query = parse_qs(urlparse(url).query)
        if urlparse(url).path.endswith("/query"):
            assert query["query"] == ["time()"]
            return None if now is None else {
                "status": "success", "data": {"resultType": "scalar", "result": [now, str(now)]}}
        return None if matrix is None else {
            "status": range_status, "data": {"resultType": "matrix", "result": matrix}}

    monkeypatch.setattr(metrics, "_fetch_json", fake)
    return calls


def series(host, stat, values, job="parrot-node", source=None, **labels):
    metric = {"host": host, "dashboard_metric": stat, "job": job, **labels}
    if source:
        metric["dashboard_source"] = source
    return {"metric": metric, "values": [[t, str(v)] for t, v in values]}


@pytest.mark.parametrize("window", ["", "2h", "1H", "1h ", None, 3600, "24h;"])
def test_history_window_is_allowlisted(monkeypatch, window):
    calls = history_fetch(monkeypatch, [])
    with pytest.raises(ValueError):
        metrics.collect_metric_history(window)
    assert calls == []


@pytest.mark.parametrize("window,seconds,step", [("1h", 3600, 30), ("6h", 21600, 150), ("24h", 86400, 600)])
def test_history_uses_prometheus_clock_aligned_bounded_range(monkeypatch, window, seconds, step):
    calls = history_fetch(monkeypatch, [])
    result = metrics.collect_metric_history(window)
    end = int(PROM_NOW // step * step)
    assert (result["status"], result["window"], result["step_seconds"]) == ("ok", window, step)
    assert (result["start"], result["end"]) == (end - seconds, end)
    query = parse_qs(urlparse(calls[1][0]).query)
    assert query["start"] == [str(end - seconds)] and query["end"] == [str(end)]
    assert query["step"] == [str(step)]
    assert seconds // step + 1 <= metrics.HISTORY_MAX_POINTS
    assert all(timeout and timeout <= 10 for _, timeout in calls)
    assert all(not any(result["hosts"][h].values()) for h in result["hosts"])


def test_history_failures_are_unavailable_with_empty_series(monkeypatch):
    for now, matrix in ((None, []), (PROM_NOW, None)):
        history_fetch(monkeypatch, matrix, now=now)
        result = metrics.collect_metric_history("1h")
        assert result["status"] == "unavailable"
        assert result["hosts"]["parrot"] == {"cpu_percent": [], "memory_percent": [], "disk_percent": []}
    history_fetch(monkeypatch, [], range_status="error")
    assert metrics.collect_metric_history("1h")["status"] == "unavailable"


def test_history_drops_invalid_samples_keeps_gaps_and_prefers_native(monkeypatch):
    end = int(PROM_NOW // 30 * 30)
    t = [end - 120, end - 90, end - 60, end - 30, end]
    matrix = [
        series("flatbush", "cpu", [(t[0], 11), (t[1], 12), (t[3], 14), (t[4], 15)], "flatbush-node"),
        series("flatbush", "cpu", [(t[1], 50), (t[2], "NaN"), (t[3], 101), (t[4], -1)],
               NATIVE, source="windows", instance="flatbush"),
        series("parrot", "memory", [(t[0], 0), (t[2], 33.33), (end + 30, 40), (t[1] - 10_000, 41)]),
        series("elsewhere", "cpu", [(t[0], 1)]),
        series("parrot", "unknown_stat", [(t[0], 1)]),
    ]
    history_fetch(monkeypatch, matrix)
    hosts = metrics.collect_metric_history("1h")["hosts"]
    # native wins where it has a valid sample; compat fills only otherwise; missing steps stay missing.
    assert hosts["flatbush"]["cpu_percent"] == [[t[0], 11.0], [t[1], 50.0], [t[3], 14.0], [t[4], 15.0]]
    assert hosts["parrot"]["memory_percent"] == [[t[0], 0.0], [t[2], 33.3]]
    assert hosts["parrot"]["cpu_percent"] == [] and hosts["flatbush"]["disk_percent"] == []


def test_history_survives_current_exporter_down_and_caps_points(monkeypatch):
    end = int(PROM_NOW // 30 * 30)
    many = [(end - 30 * i, i % 100) for i in range(400)]  # more than the bounded count
    history_fetch(monkeypatch, [series("parrot", "disk", many)])
    points = metrics.collect_metric_history("1h")["hosts"]["parrot"]["disk_percent"]
    assert len(points) <= metrics.HISTORY_MAX_POINTS
    assert points == sorted(points)
    assert all(0 <= value <= 100 for _, value in points)
