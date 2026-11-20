"""The Run tab catalogue cache: page loads reuse it, Refresh models forces it."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routes import runs as run_routes  # noqa: E402


def _reset_cache() -> None:
    with run_routes._SKILL_CATALOG_LOCK:
        run_routes._SKILL_CATALOG.update(payload=None, built_at=0.0, building=False)


def test_catalog_reuses_cache_until_forced(monkeypatch):
    calls = 0

    def fake_payload() -> dict:
        nonlocal calls
        calls += 1
        return {"skills": [{"id": f"skill-{calls}"}]}

    monkeypatch.setattr(run_routes, "_skill_catalog_payload", fake_payload)
    _reset_cache()
    try:
        first = run_routes._cached_skill_catalog()
        second = run_routes._cached_skill_catalog()
        assert calls == 1
        assert second is first

        forced = run_routes._cached_skill_catalog(force=True)
        assert calls == 2
        assert forced is not first
        assert forced["skills"][0]["id"] == "skill-2"
    finally:
        _reset_cache()
