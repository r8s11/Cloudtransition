"""Server activity must stay truthful: source outage != empty, stale != running, no leaks."""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server_activity  # noqa: E402

NOW = 1793474000.0
PROM, LOKI = "http://prom.test", "http://loki.test"


def prom_payload(rows):
    return {"status": "success", "data": {"resultType": "vector", "result": rows}}


def sample(tag, labels, value=1, key="dashboard_metric"):
    return {"metric": {**labels, key: tag}, "value": [NOW, str(value)]}


def loki_vector(rows):
    return {"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": labels, "value": [NOW, str(count)]} for labels, count in rows]}}


def loki_streams(entries):
    """entries: [(labels, nanosecond string, line)]"""
    return {"status": "success", "data": {"resultType": "streams", "result": [
        {"stream": labels, "values": [[ns, line]]} for labels, ns, line in entries]}}


def activity(containers=(), services=(), probes=(), coverage=(), counts=(), recent=None,
             fail=(), requested=None):
    recent = recent or {}

    def fetch(url, timeout=3):
        parsed = urlparse(url)
        query = parse_qs(parsed.query)["query"][0]
        if parsed.path == "/loki/api/v1/query_range":
            host = "parrot" if 'host="parrot"' in query else "flatbush"
            if requested is not None:
                requested.append((host, parse_qs(parsed.query)))
            key = f"recent_{host}"
            return None if key in fail else loki_streams(recent.get(host, []))
        if parsed.path == "/loki/api/v1/query":
            return None if "counts" in fail else loki_vector(counts)
        if "container_last_seen" in query:
            name, rows = "containers", containers
        elif "windows_service_state" in query:
            name, rows = "services", services
        elif "probe_success" in query:
            name, rows = "probes", probes
        else:
            name, rows = "coverage", coverage
        return None if name in fail else prom_payload(list(rows))

    return server_activity.collect_server_activity(fetch, PROM, LOKI)["hosts"]


def container(host, name, last_seen=NOW - 10, cpu=0.1, memory=1000, health=1, image="img:1", start=NOW - 500):
    base = {"host": host, "name": name}
    return [
        sample("last_seen", {**base, "image": image}, last_seen),
        sample("cpu", base, cpu), sample("memory", base, memory),
        sample("rx", base, 5), sample("tx", base, 7),
        sample("start", base, start), sample("health", base, health),
    ]


def win_service(name, state, job="integrations/windows_exporter", host="flatbush", instance="flatbush", **extra):
    return sample("win_state", {"host": host, "job": job, "instance": instance, "name": name, "state": state, **extra}, 1) \
        if host else sample("win_state", {"job": job, "instance": instance, "name": name, "state": state, **extra}, 1)


def win_meta(tag, name, job="integrations/windows_exporter", host="flatbush", instance="flatbush", value=1, **labels):
    base = {"job": job, "instance": instance, "name": name, **labels}
    if host:
        base["host"] = host
    return sample(tag, base, value)


# ---------------------------------------------------------------- containers

def test_stale_container_rows_are_never_reported_as_running():
    rows = container("parrot", "fresh") + container("parrot", "gone", last_seen=NOW - 600)
    parrot = activity(containers=rows)["parrot"]["containers"]
    assert [r["name"] for r in parrot["rows"]] == ["fresh"]
    assert parrot["total"] == 1 and parrot["stale_excluded"] == 1
    assert parrot["status"] == "ok"
    assert parrot["rows"][0]["uptime_seconds"] == NOW - (NOW - 500)


def test_container_health_is_real_metric_or_unknown_never_invented():
    rows = (container("parrot", "a", health=1) + container("parrot", "b", health=-1)
            + container("parrot", "c", health=0))
    by_name = {r["name"]: r for r in activity(containers=rows)["parrot"]["containers"]["rows"]}
    assert by_name["a"]["health"] == "healthy"
    assert by_name["b"]["health"] is None  # no healthcheck configured
    assert by_name["c"]["health"] is None  # zero conflates starting and unhealthy
    assert "restart_count" not in by_name["a"]


def test_container_rows_are_sorted_capped_and_flag_the_limit():
    rows = []
    for i in range(101):
        rows += container("parrot", f"c{i:03}", cpu=i / 1000)
    section = activity(containers=rows)["parrot"]["containers"]
    assert section["total"] == 101 and section["limited"] is True and len(section["rows"]) == 100
    assert section["rows"][0]["name"] == "c100"  # highest CPU first
    assert "c000" not in {r["name"] for r in section["rows"]}


def test_same_name_replacement_and_duplicate_exporters_do_not_mix_container_usage():
    def identified(identifier, job, seen, cpu, start):
        samples = container("parrot", "worker", last_seen=seen, cpu=cpu, start=start)
        for row in samples:
            row["metric"].update(id=identifier, job=job, instance=job)
        return samples
    rows = (identified("old", "a", NOW - 60, 7, NOW - 1000)
            + identified("new", "a", NOW - 5, 0.2, NOW - 30)
            + identified("new", "b", NOW - 5, 8, NOW - 30))
    result = activity(containers=rows)["parrot"]["containers"]
    assert result["total"] == 1
    assert result["rows"][0]["cpu_cores"] == 0.2
    assert result["rows"][0]["uptime_seconds"] == 30


def test_missing_container_metric_stays_null_not_zero():
    rows = [sample("last_seen", {"host": "parrot", "name": "bare", "image": "x"}, NOW - 5)]
    row = activity(containers=rows)["parrot"]["containers"]["rows"][0]
    assert row["cpu_cores"] is None and row["memory_bytes"] is None and row["uptime_seconds"] is None


def test_flatbush_docker_logs_without_cadvisor_are_an_explicit_gap():
    counts = [({"host": "flatbush", "job": "docker", "container": "calibre", "service_name": "calibre"}, 5)]
    result = activity(containers=container("parrot", "web"), counts=counts)
    flatbush = result["flatbush"]["containers"]
    assert flatbush["status"] == "not_exported" and flatbush["rows"] == []
    assert flatbush["coverage_gap"] == "logs_without_performance_metrics"
    assert flatbush["log_only"] == {"status": "ok", "total": 1, "names": ["calibre"]}
    assert result["parrot"]["containers"]["coverage_gap"] is None


# ------------------------------------------------------------------ services

def test_duplicate_windows_exporter_jobs_are_deterministically_deduplicated():
    native = [win_service("Spooler", "running"), win_meta("win_info", "Spooler", display_name="Print Spooler"),
              win_service("Dhcp", "stopped")]
    legacy = [win_service("Spooler", "stopped", job="integrations/windows", host=None),
              win_meta("win_info", "Spooler", job="integrations/windows", host=None, display_name="Legacy Spooler"),
              win_service("Extra", "running", job="integrations/windows", host=None)]
    forward = activity(services=native + legacy)["flatbush"]["services"]
    backward = activity(services=list(reversed(native + legacy)))["flatbush"]["services"]
    assert forward == backward
    assert forward["total"] == 2 and {r["name"] for r in forward["rows"]} == {"Spooler", "Dhcp"}
    spooler = next(r for r in forward["rows"] if r["name"] == "Spooler")
    assert spooler["state"] == "running" and spooler["display_name"] == "Print Spooler"


def test_one_hot_service_state_and_exact_identity_metadata_join():
    rows = [
        win_service("Spooler", "running"),
        sample("win_state", {"host": "flatbush", "job": "integrations/windows_exporter", "instance": "flatbush",
                             "name": "Idle", "state": "stopped"}, 0),  # inactive one-hot slot
        win_service("Split", "running"), win_service("Split", "paused"),  # violates one-hot
        win_meta("win_mode", "Spooler", start_mode="auto"),
        win_meta("win_info", "Spooler", display_name="Print Spooler", path_name="C:\\evil.exe --token=abc",
                 run_as="LocalSystem"),
        win_meta("win_proc", "Spooler", process_id="4321", value=1793000000),
        win_meta("win_info", "Spooler", job="integrations/windows", host=None, display_name="Other job"),
        win_meta("win_mode", "Spooler", instance="other", start_mode="disabled"),
    ]
    result = activity(services=rows)["flatbush"]["services"]
    by_name = {r["name"]: r for r in result["rows"]}
    assert set(by_name) == {"Spooler", "Split"}  # inactive state slot is not a service row
    assert by_name["Spooler"] == {"name": "Spooler", "display_name": "Print Spooler", "state": "running",
                                  "start_mode": "auto", "pid": 4321}
    assert by_name["Split"]["state"] == "unknown"
    assert by_name["Split"]["pid"] is None and by_name["Split"]["start_mode"] is None
    dump = json.dumps(result)
    assert "evil.exe" not in dump and "LocalSystem" not in dump


def test_service_rows_are_capped_and_running_first():
    rows = [win_service(f"s{i:03}", "stopped") for i in range(501)] + [win_service("zzz", "running")]
    section = activity(services=rows)["flatbush"]["services"]
    assert section["total"] == 502 and section["limited"] is True and len(section["rows"]) == 500
    assert section["rows"][0]["name"] == "zzz"


def test_parrot_without_service_collector_is_not_exported_not_empty_ok():
    result = activity(services=[win_service("Spooler", "running")])
    assert result["parrot"]["services"]["status"] == "not_exported"
    assert result["parrot"]["services"]["rows"] == []
    assert result["flatbush"]["services"]["status"] == "ok"


# -------------------------------------------------------------------- probes

def test_probe_success_is_authoritative_and_duration_pairs_by_full_identity():
    tcp = {"host": "parrot", "job": "parrot-services", "instance": "100.105.235.49:8090", "service": "beszel"}
    http = {"host": "parrot", "job": "observability-http", "instance": "http://100.105.235.49:8090/api/health",
            "service": "beszel"}
    rows = [
        sample("success", tcp, 1), sample("duration", tcp, 0.001),
        sample("success", http, 0), sample("duration", http, 0.5),
        sample("duration", {**tcp, "job": "unrelated"}, 99),
    ]
    section = activity(probes=rows)["parrot"]["probes"]
    by_kind = {r["kind"]: r for r in section["rows"]}
    assert by_kind["tcp"]["status"] == "up" and by_kind["tcp"]["duration_seconds"] == 0.001
    assert by_kind["http"]["status"] == "down" and by_kind["http"]["duration_seconds"] == 0.5
    assert section["rows"][0]["status"] == "down"  # failures sort first
    assert section["total"] == 2


def test_flatbush_probe_without_target_infers_http_only_from_http_metrics():
    labels = {"host": "flatbush", "job": "integrations/blackbox", "instance": "flatbush", "service": "loki"}
    section = activity(probes=[sample("success", labels, 1), sample("http", labels, 200),
                               sample("success", {**labels, "service": "mystery"}, 1)])["flatbush"]["probes"]
    by_service = {r["service"]: r for r in section["rows"]}
    assert by_service["loki"]["kind"] == "http" and by_service["loki"]["target"] is None
    assert by_service["mystery"]["kind"] is None and by_service["mystery"]["duration_seconds"] is None


# ---------------------------------------------------------------------- logs

def entry(host, line, ns="1793474000000000000", job="docker", **labels):
    return ({"host": host, "job": job, "container": "app", **labels}, ns, line)


def messages(result, host="parrot"):
    return [row["message"] for row in result[host]["logs"]["rows"]]


def test_log_messages_redact_common_credentials():
    lines = [
        "Authorization: Bearer abcdef1234567890xyz",
        "login password=hunter2 user=bob",
        'cfg {"api_key": "sk-live-abc123", "name": "ok"}',
        "GET https://user:pa55@example.com/path?token=zzz&x=1",
        "client_secret: topsecretvalue and eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
        "basic configuration finished",
    ]
    recent = {"parrot": [entry("parrot", line, ns=str(1793474000000000000 + i)) for i, line in enumerate(lines)]}
    text = "\n".join(messages(activity(recent=recent)))
    for secret in ("abcdef1234567890xyz", "hunter2", "sk-live-abc123", "pa55", "zzz", "topsecretvalue",
                   "eyJhbGciOiJIUzI1", "MIIEow"):
        assert secret not in text
    assert "user=bob" in text and "basic configuration finished" in text and "[redacted]" in text


def test_log_redaction_masks_alphabetic_bearer_and_escaped_json_password():
    message = r'ordinary message Bearer abcdefghijklmnop {"password":"prefix\"suffix"}'
    result = activity(recent={"parrot": [entry("parrot", message)]})
    rendered = result["parrot"]["logs"]["rows"][0]["message"]
    assert "abcdefghijklmnop" not in rendered
    assert "prefix" not in rendered and "suffix" not in rendered
    assert "ordinary message" in rendered


def test_log_messages_drop_terminal_controls_and_cap_length_but_keep_markup_as_text():
    hostile = "\x1b[31m<script>alert(1)</script>\x1b[0m\r\nline2\x00\u202egnp.exe\u200b\ud800" + "x" * 2000
    recent = {"parrot": [entry("parrot", hostile)]}
    message = activity(recent=recent)["parrot"]["logs"]["rows"][0]["message"]
    assert len(message) <= 800 and message.endswith("\u2026")
    assert "\x1b" not in message and "\x00" not in message and "\n" not in message
    assert "\u202e" not in message and "\u200b" not in message and "\ud800" not in message
    assert message.startswith("<script>alert(1)</script> line2")  # untouched: consumer uses textContent


def test_windows_event_json_is_summarized_without_event_body():
    body = json.dumps({"source": "Microsoft-Windows-PowerShell", "channel": "Operational", "event_id": 4104,
                       "taskText": "Execute a Remote Command", "message": "Invoke-X -Password hunter2",
                       "event_data": "<Data Name='CommandLine'>net use /user:a pw=hunter3</Data>"})
    recent = {"flatbush": [
        entry("flatbush", body, job="windows-events", level="Warning"),
        entry("flatbush", "<Event><Data>raw xml</Data></Event>", job="windows-events",
              ns="1793474000000000001"),
    ]}
    rows = activity(recent=recent)["flatbush"]["logs"]["rows"]
    texts = " | ".join(r["message"] for r in rows)
    assert "Execute a Remote Command" in texts and "event 4104" in texts
    assert "hunter" not in texts and "raw xml" not in texts
    assert {r["level"] for r in rows} == {"warning", "unknown"}


def test_log_rows_are_newest_first_and_bounded_to_eight_per_host():
    recent = {"parrot": [entry("parrot", f"p{i}", ns=str(1793474000000000000 + i)) for i in range(12)],
              "flatbush": [entry("flatbush", "f0")]}
    requested = []
    result = activity(recent=recent, requested=requested)
    rows = result["parrot"]["logs"]["rows"]
    assert len(rows) == 8 and rows[0]["message"] == "p11" and result["parrot"]["logs"]["limited"] is True
    assert messages(result, "flatbush") == ["f0"]  # a noisy host cannot starve the other
    assert {h for h, _ in requested} == {"parrot", "flatbush"}
    assert all(q["limit"] == ["8"] and q["since"] == ["15m"] for _, q in requested)


def test_severity_is_never_fabricated_and_unknown_is_preserved():
    counts = [({"host": "parrot", "job": "docker", "container": "a", "service_name": "a"}, 40),
              ({"host": "flatbush", "job": "windows-events", "service_name": "windows-events", "level": "Error"}, 3),
              ({"host": "flatbush", "job": "windows-events", "service_name": "windows-events", "level": "Information"}, 7)]
    result = activity(counts=counts, recent={"parrot": [entry("parrot", "plain")]})
    assert result["parrot"]["logs"]["total_count"] == 40
    assert result["parrot"]["logs"]["error_count"] is None  # no indexed severity at all
    assert result["parrot"]["logs"]["rows"][0]["level"] == "unknown"
    assert result["flatbush"]["logs"]["error_count"] == 3 and result["flatbush"]["logs"]["total_count"] == 10
    assert result["flatbush"]["logs"]["severity_known_count"] == 10


def test_legitimate_zero_counts_are_kept_and_distinct_from_unavailable():
    zero = [({"host": "flatbush", "job": "windows-events", "service_name": "w", "level": "Error"}, 0)]
    empty = activity(counts=zero)
    assert empty["flatbush"]["logs"]["error_count"] == 0 and empty["flatbush"]["logs"]["total_count"] == 0
    assert empty["flatbush"]["logs"]["status"] == "empty"
    assert empty["parrot"]["logs"]["status"] == "empty" and empty["parrot"]["logs"]["error_count"] == 0
    down = activity(fail={"counts", "recent_parrot", "recent_flatbush"})
    assert down["parrot"]["logs"]["status"] == "unavailable"
    assert down["parrot"]["logs"]["total_count"] is None and down["parrot"]["logs"]["error_count"] is None


# ------------------------------------------------- source status and isolation

def test_full_source_outage_is_distinct_from_reachable_but_nothing_exported():
    outage = activity(fail={"containers", "services", "probes", "coverage", "counts", "recent_parrot",
                            "recent_flatbush"})
    quiet = activity()
    for host in ("parrot", "flatbush"):
        for key in ("containers", "services", "probes"):
            assert outage[host][key]["status"] == "unavailable" and outage[host][key]["total"] == 0
            assert quiet[host][key]["status"] == "not_exported"
        assert outage[host]["coverage"] == {"process_detail": "unavailable", "gpu": "unavailable"}
        assert quiet[host]["coverage"] == {"process_detail": "not_exported", "gpu": "not_exported"}
        assert outage[host]["sources"]["prometheus"]["status"] == "unavailable"
        assert outage[host]["sources"]["loki"]["status"] == "unavailable"
        assert quiet[host]["sources"]["prometheus"]["status"] == "ok"
        assert outage[host]["containers"]["log_only"]["status"] == "unavailable"
        assert outage[host]["containers"]["coverage_gap"] is None


def test_partial_failure_marks_only_the_affected_sections_and_hosts():
    result = activity(fail={"probes", "recent_parrot"}, services=[win_service("Spooler", "running")])
    parrot, flatbush = result["parrot"], result["flatbush"]
    assert parrot["probes"]["status"] == "unavailable" and flatbush["probes"]["status"] == "unavailable"
    assert flatbush["services"]["status"] == "ok"
    assert parrot["sources"]["prometheus"]["status"] == "partial"
    assert parrot["sources"]["prometheus"]["queries"]["probes"] == "unavailable"
    assert parrot["sources"]["loki"]["queries"] == {"counts": "ok", "recent": "unavailable"}
    assert flatbush["sources"]["loki"]["queries"] == {"counts": "ok", "recent": "ok"}


def test_host_labels_isolate_hosts_and_contradictions_are_dropped():
    rows = (container("parrot", "p-only") + container("flatbush", "f-only")
            + [sample("last_seen", {"host": "parrot", "instance": "100.67.14.72", "name": "confused", "image": "x"},
                      NOW - 1),
               sample("last_seen", {"host": "elsewhere", "name": "stranger", "image": "x"}, NOW - 1)])
    result = activity(containers=rows)
    assert [r["name"] for r in result["parrot"]["containers"]["rows"]] == ["p-only"]
    assert [r["name"] for r in result["flatbush"]["containers"]["rows"]] == ["f-only"]
    assert server_activity.resolve_host({"instance": "100.105.235.49:443"}) == "parrot"
    assert server_activity.resolve_host({"instance": "cadvisor:8080"}) is None


