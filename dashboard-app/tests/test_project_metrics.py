"""An absent local dev server must not imply a production service outage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import metrics  # noqa: E402


def test_missing_local_health_is_unavailable_not_production_down(monkeypatch):
    monkeypatch.setattr(metrics, "_fetch_json", lambda *args, **kwargs: None)
    projects = {p["name"]: p for p in metrics.collect_project_metrics()["projects"]}
    assert projects["salsatd"]["status"] == "unknown"
    assert projects["dashboard-app"]["status"] == "up"
    assert projects["Salsa"]["status"] == "unmonitored"
    assert projects["salsasegura-mobile"]["status"] == "unmonitored"


def test_local_health_can_respond_on_second_development_port(monkeypatch):
    def fetch(url, **kwargs):
        return {"status": "ok"} if url == "http://localhost:8080/api/health" else None

    monkeypatch.setattr(metrics, "_fetch_json", fetch)
    projects = {p["name"]: p for p in metrics.collect_project_metrics()["projects"]}
    assert projects["salsatd"]["status"] == "up"
    assert projects["Salsa"]["status"] == "unmonitored"
