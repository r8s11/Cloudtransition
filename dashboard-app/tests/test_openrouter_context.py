"""OpenRouter prompts carry declared workspace text because the API cannot read files."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "TASKS.md").write_text("# Tasks\n\n- [ ] one\n", encoding="utf-8")
    (tmp_path / "College Planning").mkdir()
    (tmp_path / "College Planning" / "notes.md").write_text(
        "private notes\n", encoding="utf-8"
    )
    monkeypatch.setattr(app, "WORKSPACE", tmp_path)
    return tmp_path


def test_context_is_numbered_and_skips_unsafe_paths(workspace):
    context = app._workspace_context(
        ["TASKS.md", "missing.md", "../escape.md", "College Planning/notes.md"]
    )
    assert "### TASKS.md" in context
    assert "    1| # Tasks" in context
    assert "missing.md" not in context
    assert "private notes" not in context


def test_context_respects_the_file_cap(workspace, monkeypatch):
    (workspace / "big.md").write_text(
        "\n".join(f"line {number}" for number in range(50)), encoding="utf-8"
    )
    monkeypatch.setattr(app, "CONTEXT_MAX_FILE_CHARS", 40)
    monkeypatch.setattr(app, "CONTEXT_MAX_CHARS", 10_000)
    context = app._workspace_context(["big.md"])
    assert "… truncated" in context
    assert "line 49" not in context


def test_openrouter_prompt_inlines_context(workspace):
    cfg = dict(app.SKILL_RUNNERS["plan-today"])
    req = app.RunRequest(
        skill="plan-today", model="openrouter:nvidia/nemotron-3.5-lightning:free"
    )
    spec, _ = app._resolve_run(cfg, req)
    assert spec["kind"] == "openrouter"
    assert "Workspace context follows" in spec["prompt"]
    assert "    1| # Tasks" in spec["prompt"]


def test_local_provider_prompt_gets_no_inlined_context(workspace):
    cfg = dict(app.SKILL_RUNNERS["plan-today"])
    spec, _ = app._resolve_run(cfg, app.RunRequest(skill="plan-today", model="sonnet"))
    assert spec["kind"] == "claude"
    assert "Workspace context follows" not in spec["argv"][2]
