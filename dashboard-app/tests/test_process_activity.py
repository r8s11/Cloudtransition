"""Process performance keeps native identities, real zero and freshness boundaries."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import server_activity  # noqa: E402


def process(stat, value, name="worker", pid="12", job="integrations/windows_exporter"):
    return {"metric": {"host": "flatbush", "instance": "flatbush", "job": job,
                       "process": name, "process_id": pid, "dashboard_metric": stat},
            "value": [1000, str(value)]}


def build(rows):
    payload = {"status": "success", "data": {"result": rows}}
    return server_activity._build_processes(server_activity._prometheus_samples(payload))


def test_processes_use_one_native_exporter_and_rank_cpu_without_losing_zero():
    rows = [process("process_sample", 995), process("process_cpu", 0),
            process("process_memory", 1024), process("process_threads", 0),
            process("process_sample", 995, job="integrations/windows"),
            process("process_cpu", 8, job="integrations/windows"),
            process("process_sample", 995, name="busy", pid="14"),
            process("process_cpu", 2, name="busy", pid="14")]
    result = build(rows)
    assert [row["name"] for row in result["flatbush"]["rows"]] == ["busy", "worker"]
    worker = result["flatbush"]["rows"][1]
    assert worker["cpu_cores"] == 0 and worker["memory_bytes"] == 1024
    assert worker["threads"] == 0
    assert result["parrot"]["status"] == "not_exported"


def test_old_process_samples_are_not_current_workloads():
    result = build([process("process_sample", 879), process("process_cpu", 4)])
    assert result["flatbush"]["rows"] == []


def test_nonfinite_and_missing_process_fields_stay_unavailable():
    result = build([process("process_sample", 995), process("process_cpu", "NaN"),
                    process("process_memory", -1)])
    row = result["flatbush"]["rows"][0]
    assert row["cpu_cores"] is None
    assert row["memory_bytes"] is None
    assert row["threads"] is None
