"""Run cards must say truthfully what a run spends."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402
from core import config  # noqa: E402


def calls_jev(cfg: dict) -> bool:
    return any(str(arg).endswith("_jev.py") for arg in cfg.get("argv", []))


def test_a_shell_runner_that_bills_jev_is_never_tagged_no_model():
    jev_runners = [sid for sid, cfg in config.SKILL_RUNNERS.items() if calls_jev(cfg)]
    assert jev_runners, "triage-inbox runs triage_jev.py; the fixture for this test is gone"
    for sid in jev_runners:
        assert app.runner_engine(config.SKILL_RUNNERS[sid])["tier"] == "api", sid


def test_tier_follows_what_the_runner_executes():
    for sid, cfg in config.SKILL_RUNNERS.items():
        tier = app.runner_engine(cfg)["tier"]
        if calls_jev(cfg):
            continue
        assert tier == ("local" if cfg["kind"] == "shell" else "model"), sid
