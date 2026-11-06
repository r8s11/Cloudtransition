"""Chart history collectors: separation, bucketing, gaps, failures and bounds."""
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import metric_charts  # noqa: E402
import metrics  # noqa: E402

NOW = 1_800_000_000.0
STEP = metrics.HISTORY_WINDOWS["6h"][1]
END = int(NOW // STEP * STEP)
START = END - metrics.HISTORY_WINDOWS["6h"][0]


def matrix(series):
    return {"status": "success", "data": {"resultType": "matrix", "result": series}}


def clock():
    return {"status": "success", "data": {"resultType": "scalar", "result": [NOW, str(NOW)]}}


def series(labels, values):
    return {"metric": labels, "values": [[t, str(v)] for t, v in values]}


def fake(range_payload=None, loki_payload=None, clock_ok=True, raise_on=None):
    calls = []

    def fetch(url, timeout=3):
        calls.append(url)
        if raise_on and raise_on in url:
            raise TimeoutError("slow")
        if "query_range" in url and "/loki/" in url:
            return loki_payload
        if "query_range" in url:
            query = parse_qs(urlparse(url).query)["query"][0]
            return range_payload(query) if callable(range_payload) else range_payload
        return clock() if clock_ok else None

    fetch.calls = calls
    return fetch


def steps(n, value, start=START):
    return [(start + i * STEP, value) for i in range(n)]


def test_rate_history_keeps_interface_groups_separate():
    payload = matrix([
        series({"host": "parrot", "dashboard_metric": "net_physical_receive", "job": "node"}, steps(5, 1000)),
        series({"host": "parrot", "dashboard_metric": "net_physical_transmit", "job": "node"}, steps(5, 200)),
        series({"host": "parrot", "dashboard_metric": "net_tailscale_receive", "job": "node"}, steps(5, 70)),
        series({"host": "parrot", "dashboard_metric": "net_tailscale_transmit", "job": "node"}, steps(5, 9)),
        series({"host": "parrot", "dashboard_metric": "disk_read", "device": "sda", "job": "node"}, steps(5, 4096)),
        series({"host": "parrot", "dashboard_metric": "disk_write", "device": "sda", "job": "node"}, steps(5, 512)),
        series({"host": "parrot", "dashboard_metric": "disk_read", "device": "sdb", "job": "node"}, steps(5, 0)),
        series({"host": "parrot", "dashboard_metric": "disk_write", "device": "sdb", "job": "node"}, steps(5, 0)),
    ])
    result = metric_charts.collect_rate_history("6h", fetch=fake(payload))
    assert result["status"] == "ok" and (result["start"], result["end"]) == (START, END)
    net = result["hosts"]["parrot"]["network"]
    assert [v for _, v in net["physical"]["receive"]] == [1000] * 5
    assert [v for _, v in net["tailscale"]["receive"]] == [70] * 5
    assert [v for _, v in net["tailscale"]["transmit"]] == [9] * 5
    assert list(result["hosts"]["parrot"]["disks"]) == ["sda"]
    assert result["hosts"]["parrot"]["idle_disks"] == ["sdb"]
    assert result["hosts"]["flatbush"]["network"]["physical"]["receive"] == []


def test_probe_history_distinguishes_up_down_and_missing():
    payload = matrix([
        series({"instance": "http://100.105.235.49:8090/api/health", "service": "beszel"}, steps(4, 1)),
        series({"instance": "100.105.235.49:22", "service": "ssh"}, [(START, 1), (START + STEP, 0), (START + 2 * STEP, 1)]),
        series({"instance": "100.105.235.49:9090", "service": "cockpit"}, [(START + 3 * STEP, 1)]),
    ])
    result = metric_charts.collect_probe_history("6h", fetch=fake(payload))
    rows = {r["service"]: r for r in result["hosts"]["parrot"]}
    assert rows["beszel"]["kind"] == "http" and rows["ssh"]["kind"] == "tcp"
    assert rows["beszel"]["values"][:4] == [1, 1, 1, 1]
    assert rows["ssh"]["values"][:4] == [1, 0, 1, None]
    assert rows["cockpit"]["values"][:4] == [None, None, None, 1]
    assert all(v in (0, 1, None) for r in rows.values() for v in r["values"])


def test_log_volume_buckets_by_timestamp_and_keeps_unknown():
    loki_start = END - metrics.HISTORY_WINDOWS["6h"][0]
    offset = STEP // 3  # Loki timestamps that do not line up with the window step
    payload = matrix([
        series({"host": "flatbush", "level": "Error"}, [(loki_start + 2 * STEP + offset, 3)]),
        series({"host": "flatbush", "level": "Warning"}, [(loki_start + offset, 5), (loki_start + 10 * STEP, 7)]),
        series({"host": "flatbush"}, [(loki_start + STEP, 11)]),
    ])
    result = metric_charts.collect_log_volume("6h", fetch=fake(loki_payload=payload), now=NOW)
    levels = result["hosts"]["flatbush"]["levels"]
    assert set(levels) == {"Error", "Warning", "unknown"}
    assert levels["Error"][2] == 3 and sum(levels["Error"]) == 3
    assert levels["Warning"][0] == 5 and levels["Warning"][10] == 7 and sum(levels["Warning"]) == 12
    assert levels["unknown"][1] == 11
    assert result["hosts"]["parrot"]["levels"] == {}


def test_range_failures_are_unavailable_not_zero():
    fetch = fake(range_payload=None)
    for collector in (metric_charts.collect_rate_history, metric_charts.collect_probe_history):
        result = collector("1h", fetch=fetch)
        assert result["status"] == "unavailable"
    rates = metric_charts.collect_rate_history("1h", fetch=fetch)
    assert rates["hosts"]["parrot"]["network"]["physical"]["receive"] == []
    assert metric_charts.collect_probe_history("1h", fetch=fetch)["hosts"]["parrot"] == []
    assert metric_charts.collect_rate_history("1h", fetch=fake(range_payload=matrix([]), clock_ok=False))["status"] == "unavailable"


def test_loki_failure_isolated_from_prometheus_charts():
    payload = matrix([series({"host": "parrot", "dashboard_metric": "net_physical_receive"}, steps(3, 10))])
    result = metric_charts.collect_chart_history("6h", fetch=fake(range_payload=payload, loki_payload=None))
    assert result["logs"]["status"] == "unavailable"
    assert result["rates"]["status"] == "ok" and result["probes"]["status"] == "ok"


@pytest.mark.parametrize("window", ["7d", "1h;drop", "", None])
def test_chart_endpoints_reject_unknown_windows(window):
    from fastapi.testclient import TestClient
    import app as module
    called = []
    original = metrics._fetch_json
    metrics._fetch_json = lambda *a, **k: called.append(a)
    try:
        with TestClient(module.app) as client:
            response = client.get("/api/metrics/rates", params={"window": window} if window is not None else {"window": "bad"})
        assert response.status_code == 400 and "error" in response.json()
        assert called == []
        with pytest.raises(ValueError):
            metric_charts.collect_chart_history(window, fetch=lambda *a, **k: called.append(a))
        assert called == []
    finally:
        metrics._fetch_json = original


def test_invalid_samples_dropped_and_gaps_preserved():
    bad = [(START, "NaN"), (START + STEP, "+Inf"), (START + 2 * STEP, -5), (START - STEP, 9),
           (START + 3 * STEP, 40), (START + 7 * STEP, 50)]
    payload = matrix([
        series({"host": "parrot", "dashboard_metric": "net_physical_receive"}, bad),
        series({"instance": "100.105.235.49:22", "service": "ssh"}, [(START, "NaN"), (START + STEP, 2), (START + 2 * STEP, 1)]),
    ])
    rates = metric_charts.collect_rate_history("6h", fetch=fake(payload))
    assert rates["hosts"]["parrot"]["network"]["physical"]["receive"] == [[START + 3 * STEP, 40], [START + 7 * STEP, 50]]
    probes = metric_charts.collect_probe_history("6h", fetch=fake(payload))
    assert probes["hosts"]["parrot"][0]["values"][:3] == [None, None, 1]


def test_slow_source_only_blanks_its_section():
    payload = matrix([series({"instance": "100.105.235.49:22", "service": "ssh"}, steps(2, 1))])
    began = time.monotonic()
    result = metric_charts.collect_chart_history("1h", fetch=fake(range_payload=payload, loki_payload=matrix([]), raise_on="loki"))
    assert time.monotonic() - began < 5
    assert result["logs"]["status"] == "unavailable"
    assert result["probes"]["status"] == "ok" and result["rates"]["status"] == "ok"


def test_large_inputs_are_bounded():
    window = "24h"
    seconds, step = metrics.HISTORY_WINDOWS[window]
    end = int(NOW // step * step)
    start = end - seconds
    many = [(start + i * step, 1 + i) for i in range(seconds // step + 1)]
    disks = [series({"host": "parrot", "dashboard_metric": "disk_read", "device": f"sd{i:02d}"}, many) for i in range(40)]
    probes = [series({"instance": f"100.105.235.49:{1000 + i}", "service": f"svc{i:02d}"}, many[:3]) for i in range(30 + 10)]
    rates = metric_charts.collect_rate_history(window, fetch=fake(matrix(disks)))
    host = rates["hosts"]["parrot"]
    assert len(host["disks"]) == metric_charts.MAX_CHART_DISKS
    assert len(host["more_disks"]) == 40 - metric_charts.MAX_CHART_DISKS
    assert all(len(d["read"]) <= metrics.HISTORY_MAX_POINTS for d in host["disks"].values())
    probe_rows = metric_charts.collect_probe_history(window, fetch=fake(matrix(probes)))["hosts"]["parrot"]
    assert len(probe_rows) == metric_charts.MAX_CHART_PROBES
    assert all(len(r["values"]) <= metrics.HISTORY_MAX_POINTS for r in probe_rows)
