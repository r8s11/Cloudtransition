"""Host status must not borrow another host's telemetry or hide missing data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import metrics  # noqa: E402


def sample(host, stat, value, job="node"):
    return {"metric": {"host": host, "dashboard_metric": stat, "job": job},
            "value": [1793400000, str(value)]}


def collect(monkeypatch, rows=None, unavailable=False):
    payload = None if unavailable else {
        "status": "success", "data": {"resultType": "vector", "result": rows or []}}
    monkeypatch.setattr(metrics, "_fetch_json", lambda *args, **kwargs: payload)
    return metrics.collect_infrastructure_metrics()


def test_parrot_services_do_not_make_flatbush_or_host_exporter_healthy(monkeypatch):
    result = collect(monkeypatch, [sample("parrot", "up", 1, "prometheus")])
    assert result["services"]["prometheus"] == "up"
    assert result["hosts"]["parrot"]["status"] == "pending"
    assert result["hosts"]["flatbush"]["status"] == "pending"
    assert result["hosts"]["flatbush"]["cpu_percent"] is None


def test_down_exporter_does_not_display_old_utilization(monkeypatch):
    result = collect(monkeypatch, [sample("parrot", "up", 0, "parrot-node"),
                                   sample("parrot", "cpu", 8.5)])
    assert result["hosts"]["parrot"]["status"] == "down"
    assert result["hosts"]["parrot"]["cpu_percent"] is None


def test_zero_utilization_is_data_but_nonfinite_is_not(monkeypatch):
    result = collect(monkeypatch, [sample("flatbush", "cpu", 0),
                                   sample("flatbush", "memory", "NaN"),
                                   sample("flatbush", "disk", "+Inf"),
                                   sample("parrot", "cpu", 23)])
    assert result["hosts"]["flatbush"]["status"] == "up"
    assert result["hosts"]["flatbush"]["cpu_percent"] == 0
    assert result["hosts"]["flatbush"]["memory_percent"] is None
    assert result["hosts"]["flatbush"]["disk_percent"] is None
    assert result["hosts"]["parrot"]["cpu_percent"] == 23


def test_unreachable_prometheus_is_unknown_not_host_down(monkeypatch):
    result = collect(monkeypatch, unavailable=True)
    assert {host["status"] for host in result["hosts"].values()} == {"unknown"}
    assert set(result["services"].values()) == {"unknown"}


def test_capacity_and_network_details_keep_units_and_real_zero(monkeypatch):
    result = collect(monkeypatch, [
        sample("parrot", "memory_total_bytes", 16 * 1024**3),
        sample("parrot", "memory_available_bytes", 0),
        sample("parrot", "uptime_seconds", 86400),
        sample("parrot", "cpu_threads", 8),
        sample("parrot", "physical_receive_bytes_per_second", 0),
        sample("parrot", "physical_transmit_bytes_per_second", 2048),
        sample("parrot", "disk_available_bytes", -1),
        sample("parrot", "tailscale_receive_bytes_per_second", "NaN"),
    ])
    host = result["hosts"]["parrot"]
    assert host["memory_total_bytes"] == 16 * 1024**3
    assert host["memory_available_bytes"] == 0
    assert host["cpu_threads"] == 8
    assert host["uptime_seconds"] == 86400
    assert host["physical_receive_bytes_per_second"] == 0
    assert host["physical_transmit_bytes_per_second"] == 2048
    assert host["disk_available_bytes"] is None
    assert host["tailscale_receive_bytes_per_second"] is None
    assert result["hosts"]["flatbush"]["memory_total_bytes"] is None


def test_down_exporter_clears_detailed_readings_too(monkeypatch):
    result = collect(monkeypatch, [
        sample("parrot", "up", 0, "parrot-node"),
        sample("parrot", "memory_total_bytes", 16 * 1024**3),
        sample("parrot", "uptime_seconds", 86400),
        sample("parrot", "physical_receive_bytes_per_second", 1024),
    ])
    host = result["hosts"]["parrot"]
    assert host["status"] == "down"
    assert host["memory_total_bytes"] is None
    assert host["uptime_seconds"] is None
    assert host["physical_receive_bytes_per_second"] is None


def test_host_metadata_is_not_borrowed_from_another_host(monkeypatch):
    os_info = sample("parrot", "os_info", 1)
    os_info["metric"]["pretty_name"] = "Parrot Security 7.4 (echo)"
    uname = sample("parrot", "uname_info", 1)
    uname["metric"].update(release="7.1.13", machine="x86_64")
    result = collect(monkeypatch, [os_info, uname])
    assert result["hosts"]["parrot"]["os_name"] == "Parrot Security 7.4 (echo)"
    assert result["hosts"]["parrot"]["kernel"] == "7.1.13"
    assert result["hosts"]["parrot"]["architecture"] == "x86_64"
    assert result["hosts"]["flatbush"]["os_name"] is None
    assert result["hosts"]["flatbush"]["status"] == "pending"
