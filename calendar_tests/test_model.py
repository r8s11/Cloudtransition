from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest


class CalendarModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "TASKS.md"
        self.source.write_text("## Work\n- [ ] Review plan\n- [ ] Read notes\n- [x] Finished\n")

    def preview(self, items=None):
        from calendar_model import make_preview
        return make_preview(self.source, items or [("2", "2026-11-10")], "chosen-list")

    def test_list_checklist_items(self):
        from calendar_model import list_items
        self.source.write_text("## 🌿 Work\n  - [ ] Réviser plan\n- [X] Finished\n```md\n- [ ] Example\n```\n~~~\n# False heading\n- [ ] Another example\n~~~\n- [?] Malformed\n- [ ] Read notes\n")
        items = list_items(self.source)
        self.assertEqual([(x["id"], x["title"], x["heading"]) for x in items], [("2", "Réviser plan", "Work"), ("12", "Read notes", "Work")])
        self.source.write_text("- [x] Done\n")
        self.assertEqual(list_items(self.source), [])

    def test_preview_selected_batch(self):
        from calendar_model import validate_preview
        original = self.source.read_bytes()
        preview = self.preview()
        self.assertEqual(preview["tasklist"], "chosen-list")
        self.assertEqual([x["body"]["title"] for x in preview["items"]], ["Review plan"])
        self.assertEqual(preview["items"][0]["body"]["due"], "2026-11-10T00:00:00.000Z")
        self.assertNotIn("Read notes", json.dumps(preview))
        validate_preview(preview)
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_and_ambiguous_source(self):
        from calendar_model import CalendarError, list_items, make_preview
        with self.assertRaises(CalendarError):
            list_items(self.source.parent / "missing.md")
        for selections in ([], [("99", "2026-11-10")], [("4", "2026-11-10")], [("2", "2026-11-10"), ("2", "2026-11-11")]):
            with self.subTest(selections=selections), self.assertRaises(CalendarError):
                make_preview(self.source, selections, "chosen-list")

    def test_stale_preview_rejected(self):
        from calendar_model import CalendarError, validate_preview
        preview = self.preview()
        for field, value in (("title", "Changed"), ("due", "2026-11-11T00:00:00.000Z"), ("notes", "different-marker")):
            altered = deepcopy(preview)
            altered["items"][0]["body"][field] = value
            with self.subTest(field=field), self.assertRaises(CalendarError):
                validate_preview(altered)
        for text in ("## Work\n- [ ] Changed\n", "## Work\n- [x] Review plan\n", "## Work\n- [ ] Review plan\n- [ ] Review plan\n"):
            self.source.write_text(text)
            with self.subTest(text=text), self.assertRaises(CalendarError):
                validate_preview(preview)
        self.source.write_text("An unrelated paragraph\n## Work\n- [ ] Review plan\n")
        validate_preview(preview)
        self.source.unlink()
        with self.assertRaises(CalendarError):
            validate_preview(preview)

    def test_date_and_payload_boundaries(self):
        from calendar_model import CalendarError, make_preview, validate_preview
        for day in ("", "today", "2026-02-29", "20261110", "2026-11-10T12:00:00Z", None):
            with self.subTest(day=day), self.assertRaises(CalendarError):
                make_preview(self.source, [("2", day)], "chosen-list")
        leap = make_preview(self.source, [("2", "2028-02-29")], "chosen-list")
        self.assertEqual(leap["items"][0]["body"]["due"], "2028-02-29T00:00:00.000Z")
        validate_preview(leap)
        self.source.write_text("- [ ] " + "a" * 1025 + "\n")
        with self.assertRaises(CalendarError):
            make_preview(self.source, [("1", "2026-11-10")], "chosen-list")

    def test_duplicate_identity_and_movement(self):
        from calendar_model import CalendarError, make_preview, validate_preview
        self.source.write_text("## Work\n- [ ] Repeat\n- [ ] Repeat\n## Home\n- [ ] Repeat\n")
        preview = make_preview(self.source, [("2", "2026-11-10"), ("3", "2026-11-11"), ("5", "2026-11-12")], "chosen-list")
        self.assertEqual(len({x["key"] for x in preview["items"]}), 3)
        validate_preview(preview)
        self.source.write_text("An inserted line\n" + self.source.read_text())
        with self.assertRaises(CalendarError):
            validate_preview(preview)

    def test_preview_rejects_extra_fields_and_masks_secrets(self):
        from calendar_model import CalendarError, make_preview, validate_preview
        preview = self.preview()
        preview["items"][0]["body"]["attendees"] = ["unexpected"]
        with self.assertRaises(CalendarError):
            validate_preview(preview)
        self.source.write_text("- [ ] Rotate password=CalendarCanarySecret123456\n")
        masked = make_preview(self.source, [("1", "2026-11-10")], "chosen-list")
        self.assertNotIn("CalendarCanarySecret123456", json.dumps(masked))
        validate_preview(masked)

    def test_dashboard_schedule_metadata_stays_local(self):
        from calendar_model import CalendarError, validate_preview
        self.source.write_text('## Work\n- [ ] Review plan <!-- calendar: {"date":"2026-11-16","id":"' + "a" * 32 + '"} -->\n')
        preview = self.preview()
        self.assertEqual(preview["items"][0]["body"]["title"], "Review plan")
        self.assertNotIn("calendar:", json.dumps(preview["items"][0]["body"]))
        validate_preview(preview)
        self.source.write_text(self.source.read_text().replace("2026-11-16", "2026-11-17"))
        with self.assertRaises(CalendarError):
            validate_preview(preview)
