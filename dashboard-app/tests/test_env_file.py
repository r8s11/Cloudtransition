"""dashboard-app/.env supplies local keys without overriding the process environment."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import _load_env_file  # noqa: E402


def test_loads_quoted_values_comments_and_export(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local keys\n"
        'CT_ONE="spaced value"\n'
        "\n"
        "export CT_TWO='single'\n"
        "CT_THREE=plain\n"
        "not-an-assignment\n",
        encoding="utf-8",
    )
    target: dict[str, str] = {}
    _load_env_file(env_file, target)
    assert target == {"CT_ONE": "spaced value", "CT_TWO": "single", "CT_THREE": "plain"}


def test_real_environment_wins(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CT_EXISTING=file\n", encoding="utf-8")
    target = {"CT_EXISTING": "process"}
    _load_env_file(env_file, target)
    assert target["CT_EXISTING"] == "process"


def test_missing_file_is_ignored(tmp_path):
    target = {"CT_UNTOUCHED": "keep"}
    _load_env_file(tmp_path / "absent.env", target)
    assert target == {"CT_UNTOUCHED": "keep"}
