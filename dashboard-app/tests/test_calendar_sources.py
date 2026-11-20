"""Source-only Calendar contracts. Fixtures never touch Google or private runtime."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import calendar_sources as cs
from core import interview_editor as ie


@pytest.fixture
def sources(tmp_path):
    realms = [{"id": "tasks", "name": "Tasks", "file": "TASKS.md"},
              {"id": "extra", "name": "Extra", "file": "plans/extra.md"}]
    (tmp_path / "plans").mkdir()
    (tmp_path / "interviews").mkdir()
    (tmp_path / "TASKS.md").write_text("# Tasks\n- [ ] Local work\n", encoding="utf-8")
    (tmp_path / "plans/extra.md").write_text("- [ ] Extra work\n", encoding="utf-8")
    jobs = tmp_path / "interviews/jobs.yml"
    jobs.write_text(
        "# Preserve tracker header\n"
        "active_applications:\n"
        "  - company: Example\n"
        "    role: Engineer\n"
        "    status: interviewing\n"
        "    contacts:\n"
        "      - email: private-contact@example.invalid\n"
        "    timeline:\n"
        "      - date: 2026-11-14\n"
        "        notes: private-history-canary\n"
        "    next_steps:\n"
        "      - task: First action\n"
        "        date: 2026-11-16 # keep first comment\n"
        "      # Preserve action divider\n"
        "      - task: Second action\n"
        "        date: # keep empty-date comment\n"
        "        custom: keep-me\n"
        "      - task: Third action\n"
        "        date: 2026-11-18\n"
        "    notes: |\n"
        "      private-notes-canary\n"
        "      Next line stays exactly.\n"
        "past_applications: []\n", encoding="utf-8")
    return tmp_path, realms, jobs


def test_schedule_sources(sources):
    root, realms, jobs = sources
    original = (root / "TASKS.md").read_text()
    path, changed = cs.schedule_item(root, realms, jobs, {
        "source": "tasks", "line": 2, "text": "Local work", "schedule": {"date": "2026-11-16"}})
    assert path == root / "TASKS.md"
    assert path.read_text() == original  # Only the app's locked writer may persist.
    path.write_text(changed)
    raw = changed.splitlines()[1].split("] ", 1)[1]
    assert cs.split_metadata(raw) == ("Local work", {"date": "2026-11-16"})
    item = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert item["status"] == "eligible"
    assert "id" not in item["schedule"]
    assert len(item["key"]) == 64

    path.write_text("# Unrelated line movement\n" + changed)
    moved = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert moved["key"] == item["key"] and moved["binding"] == item["binding"]
    _, rescheduled = cs.schedule_item(root, realms, jobs, {
        "source": "tasks", "line": 2, "text": raw,
        "schedule": {"start": "2026-11-16T14:00", "end": "2026-11-16T15:00",
                     "timezone": "America/New_York"}})
    path.write_text(rescheduled.replace("Local work", "Unicode café 日 task"))
    edited = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert edited["key"] == item["key"] and edited["binding"] != item["binding"]
    assert edited["title"] == "Unicode café 日 task"
    path.write_text(path.read_text().replace("- [ ]", "- [x]"))
    assert cs.collect(root, realms, jobs, ["tasks"]) == []
    assert "calendar:" in path.read_text()  # Checkbox toggle leaves identity/schedule intact.

    extra = root / "plans/extra.md"
    extra.write_text("- [ ] Do on November 20\n```md\n- [ ] Example\n```\n"
                     "- [x] Completed\n- [ ] Broken <!-- calendar: nope -->\n")
    items = cs.collect(root, realms, jobs, ["extra"])
    assert [(i["title"], i["status"]) for i in items] == [("Do on November 20", "needs_date")]


def test_schedule_sources_annotations_and_identity(sources):
    root, realms, jobs = sources
    raw = "Review <!-- keep: exact text -->"
    dated = cs.annotate(raw, {"date": "2028-02-29"})
    assert cs.split_metadata(dated) == (raw, {"date": "2028-02-29"})
    assert "<!-- keep: exact text -->" in dated
    assert cs.annotate(dated, {"date": "2028-02-29"}) == dated
    identity = json.loads(dated.split("<!-- calendar: ", 1)[1].split(" -->", 1)[0])["id"]
    assert identity in cs.annotate(dated, {})
    assert cs.split_metadata(cs.annotate(dated, {})) == (raw, {})
    assert cs.annotate("Undated", {}) == "Undated"
    (root / "TASKS.md").write_text("- [ ] " + dated + "\n")
    # Two configured views of one file cannot create two source identities.
    aliases = realms + [{"id": "same", "name": "Same", "file": "TASKS.md"}]
    assert len(cs.collect(root, aliases, jobs, ["tasks", "same"])) == 1


def test_schedule_sources_interviews_preserve_all_bytes(sources):
    root, realms, jobs = sources
    original = jobs.read_text()
    before = yaml.safe_load(original)
    actions = cs.collect(root, realms, jobs, ["interviews"])
    assert [i["title"] for i in actions] == ["First action", "Second action", "Third action"]
    assert [i["status"] for i in actions] == ["eligible", "needs_date", "eligible"]
    schedule = {"start": "2026-11-17T09:15", "end": "2026-11-17T09:45", "timezone": "UTC"}
    _, updated = cs.schedule_item(root, realms, jobs, {
        "source": "interviews", "company": "Example", "role": "Engineer", "index": 1,
        "text": "Second action", "schedule": schedule})
    assert jobs.read_text() == original
    after = yaml.safe_load(updated)
    assert after["active_applications"][0]["next_steps"][0] == before["active_applications"][0]["next_steps"][0]
    assert after["active_applications"][0]["next_steps"][2] == before["active_applications"][0]["next_steps"][2]
    assert after["active_applications"][0]["next_steps"][1]["custom"] == "keep-me"
    assert original.split("    notes: |", 1)[1] == updated.split("    notes: |", 1)[1]
    for comment in ("# Preserve tracker header", "# keep first comment", "# Preserve action divider",
                    "# keep empty-date comment"):
        assert comment in updated
    jobs.write_text(updated)
    item = cs.collect(root, realms, jobs, ["interviews"])[1]
    assert item["schedule"] == schedule
    assert "private-contact" not in json.dumps(item)
    assert "private-notes" not in json.dumps(item)
    assert "private-history" not in json.dumps(item)
    _, date_only = cs.schedule_item(root, realms, jobs, {
        "source": "interviews", "company": "Example", "role": "Engineer", "index": 1,
        "text": "Second action", "schedule": {"date": "2026-11-19"}})
    jobs.write_text(date_only)
    edited = cs.collect(root, realms, jobs, ["interviews"])[1]
    assert edited["key"] == item["key"]
    assert edited["schedule"] == {"date": "2026-11-19"}


@pytest.mark.parametrize("schedule", [
    {"date": "2026-02-29"}, {"date": "2026-1-01"}, {"date": "2026-13-01"},
    {"date": "2026-11-16", "start": "2026-11-16T09:00"}, {"id": "f" * 32},
    {"start": "2026-11-16T10:00", "end": "2026-11-16T09:00", "timezone": "UTC"},
    {"start": "2026-11-16T09:00", "end": "2026-11-16T09:00", "timezone": "UTC"},
    {"start": "2026-11-16T09:00", "end": "2026-11-16T10:00"},
    {"start": "2026-11-16T09:00", "end": "2026-11-16T10:00", "timezone": "Unknown/Place"},
    {"start": "2026-03-08T02:15", "end": "2026-03-08T03:30", "timezone": "America/New_York"},
    {"start": "2026-11-01T01:15", "end": "2026-11-01T02:30", "timezone": "America/New_York"},
    {"start": "2026-11-16T09:00Z", "end": "2026-11-16T10:00Z", "timezone": "UTC"},
])
def test_schedule_privacy_invalid_schedules(sources, schedule):
    root, realms, jobs = sources
    original = (root / "TASKS.md").read_bytes()
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "tasks", "line": 2, "text": "Local work",
                                              "schedule": schedule})
    assert (root / "TASKS.md").read_bytes() == original


def test_schedule_privacy_source_allowlist(sources, tmp_path):
    root, realms, jobs = sources
    for folder, name in (("College Planning", "records.md"), ("employer", "private.md"),
                         ("allowed", "credentials.json")):
        (root / folder).mkdir()
        (root / folder / name).write_text("- [ ] private-source-canary\n")
        realms.append({"id": folder.split()[0], "name": folder, "file": f"{folder}/{name}"})
    (root / "alias.md").symlink_to(root / "TASKS.md")
    realms.append({"id": "alias", "name": "Alias", "file": "alias.md"})
    realms.append({"id": "outside", "name": "Outside", "file": "../outside.md"})
    choices = {c["id"]: c for c in cs.source_choices(root, realms, jobs)}
    assert choices["tasks"]["available"]
    assert all(not choices[key]["available"] and choices[key]["reason"]
               for key in ("College", "employer", "allowed", "alias", "outside"))
    for source in ("College", "employer", "allowed", "alias", "outside", "TASKS.md", "../TASKS.md"):
        with pytest.raises(cs.CalendarSourceError):
            cs.collect(root, realms, jobs, [source])
    with pytest.raises(cs.CalendarSourceError):
        cs.collect(root, realms, jobs, ["tasks", "tasks"])


def test_schedule_privacy_duplicates_stale_and_sanitization(sources):
    root, realms, jobs = sources
    tasks = root / "TASKS.md"
    tasks.write_text("- [ ] Same\n- [ ] Same\n")
    items = cs.collect(root, realms, jobs, ["tasks"])
    assert len(items) == 2 and all(i["status"] == "needs_review" for i in items)
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "tasks", "line": 1, "text": "Same",
                                              "schedule": {"date": "2026-11-16"}})
    tasks.write_text("- [ ] Changed\n")
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "tasks", "line": 1, "text": "Same", "schedule": {}})
    tasks.write_text('- [ ] Deploy password=super-secret-canary <!-- local: private-comment-canary -->\n'
                     '- [ ] ' + 'x' * 1025 + '\n'
                     '- [ ] -----BEGIN PRIVATE KEY-----private-key-canary\n')
    items = cs.collect(root, realms, jobs, ["tasks"])
    assert len(items) == 1
    payload = json.dumps(items)
    assert "super-secret-canary" not in payload and "private-comment-canary" not in payload
    assert "private-key-canary" not in payload
    assert "REDACTED" in items[0]["title"]
    for malformed in ('X <!-- calendar: {} --> <!-- calendar: {} -->',
                      'X <!-- calendar: {"date":"2026-11-16","date":"2026-11-17"} -->',
                      'X <!-- calendar: {"id":"not-an-opaque-id"} -->',
                      'X <!-- calendar: {}', 'X <!-- calendar: {"attendees":[]} -->'):
        with pytest.raises(cs.CalendarSourceError):
            cs.split_metadata(malformed)


def test_schedule_privacy_binding_and_yaml_ambiguity(sources):
    root, realms, jobs = sources
    tasks = root / "TASKS.md"
    raw = cs.annotate("Bound", {"date": "2026-11-16"})
    tasks.write_text("- [ ] " + raw + "\n")
    item = cs.collect(root, realms, jobs, ["tasks"])[0]
    changed_raw = cs.annotate(raw, {"date": "2026-11-17"})
    tasks.write_text("- [ ] " + changed_raw + "\n")
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "tasks", "line": 1, "text": changed_raw,
                                              "binding": item["binding"], "schedule": {}})
    original = jobs.read_text()
    jobs.write_text(original.replace("task: Second action", "task: First action"))
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "interviews", "company": "Example", "role": "Engineer",
                                              "index": 1, "text": "First action", "schedule": {}})
    duplicate = "active_applications:\n  - company: Example\n    role: Engineer\n    next_steps:\n      - task: Action\n"
    jobs.write_text(duplicate + duplicate.split("active_applications:\n", 1)[1])
    with pytest.raises(cs.CalendarSourceError):
        cs.schedule_item(root, realms, jobs, {"source": "interviews", "company": "Example", "role": "Engineer",
                                              "index": 0, "text": "Action", "schedule": {}})


def test_schedule_sources_pin_legacy_identity(sources):
    root, realms, jobs = sources
    original = jobs.read_text()
    legacy = cs.collect(root, realms, jobs, ["interviews"])[0]
    assert legacy["binding"]["identity"] is None
    path, pinned_text = cs.pin_item(root, realms, jobs, legacy)
    assert path == jobs and jobs.read_text() == original
    jobs.write_text(pinned_text)
    pinned = cs.collect(root, realms, jobs, ["interviews"])[0]
    assert pinned["key"] == legacy["key"]
    assert pinned["binding"]["identity"] == legacy["key"]
    assert cs.pin_item(root, realms, jobs, pinned) == (jobs, pinned_text)
    jobs.write_text(pinned_text.replace("First action", "Changed action"))
    changed = cs.collect(root, realms, jobs, ["interviews"])[0]
    assert changed["key"] == legacy["key"] and changed["binding"] != pinned["binding"]
    with pytest.raises(cs.CalendarSourceError):
        cs.pin_item(root, realms, jobs, pinned)

    tasks = root / "TASKS.md"
    tasks.write_text('- [ ] Legacy <!-- local: comment-canary --> <!-- calendar: {"date":"2026-11-16"} -->\n')
    legacy = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert "comment-canary" not in json.dumps(legacy)
    _, pinned_text = cs.pin_item(root, realms, jobs, legacy)
    tasks.write_text(pinned_text)
    pinned = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert pinned["key"] == legacy["key"]
    assert pinned["binding"]["identity"] == legacy["key"]
    assert "local: comment-canary" in pinned_text
    tasks.write_text(pinned_text.replace("Legacy", "Changed").replace("2026-11-16", "2026-11-17"))
    changed = cs.collect(root, realms, jobs, ["tasks"])[0]
    assert changed["key"] == legacy["key"] and changed["binding"] != pinned["binding"]


def test_schedule_sources_existing_next_action_editor_keeps_identity(sources):
    root, realms, jobs = sources
    timed = {"start": "2026-11-16T09:00", "end": "2026-11-16T09:30", "timezone": "UTC"}
    _, scheduled = cs.schedule_item(root, realms, jobs, {
        "source": "interviews", "company": "Example", "role": "Engineer", "index": 0,
        "text": "First action", "schedule": timed})
    jobs.write_text(scheduled)
    first = cs.collect(root, realms, jobs, ["interviews"])[0]
    before = yaml.safe_load(scheduled)["active_applications"][0]
    edited = ie.set_next_step(scheduled, "Example", "Engineer", "New first action", "")
    after = yaml.safe_load(edited)["active_applications"][0]
    assert after["next_steps"][1:] == before["next_steps"][1:]
    assert after["next_steps"][0]["calendar_id"] == before["next_steps"][0]["calendar_id"]
    assert after["notes"] == before["notes"] and after["contacts"] == before["contacts"]
    assert "# keep first comment" in edited and "# Preserve action divider" in edited
    jobs.write_text(edited)
    changed = cs.collect(root, realms, jobs, ["interviews"])[0]
    assert changed["key"] == first["key"] and changed["schedule"] == timed
    dated = ie.set_next_step(edited, "Example", "Engineer", "New first action", "2026-11-20")
    jobs.write_text(dated)
    changed = cs.collect(root, realms, jobs, ["interviews"])[0]
    assert changed["key"] == first["key"] and changed["schedule"] == {"date": "2026-11-20"}
    empty = ("active_applications:\n  - company: Empty\n    role: Engineer\n"
             "    next_steps: [] # preserve empty comment\n"
             "    notes: Keep notes\n")
    created = ie.set_next_step(empty, "Empty", "Engineer", "Apply", "")
    assert created.count("next_steps:") == 1
    assert "# preserve empty comment" in created and "notes: Keep notes" in created
    assert yaml.safe_load(created)["active_applications"][0]["next_steps"] == [{"task": "Apply", "date": None}]
