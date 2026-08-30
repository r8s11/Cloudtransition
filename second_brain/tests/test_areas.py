"""Tests for Area creation, hierarchy, slug uniqueness, and seeding."""

from second_brain.types.enums import AreaKind


class TestAreaCreation:
    """Create top-level area."""

    def test_create_top_level_area(self, area_service):
        area = area_service.create(name="Projects")
        assert area.id is not None
        assert area.name == "Projects"
        assert area.slug == "projects"
        assert area.kind == "default"
        assert area.parent_id is None
        assert area.description == ""
        assert area.archived_at is None

    def test_create_area_with_custom_slug(self, area_service):
        area = area_service.create(name="My Area", slug="custom-slug")
        assert area.slug == "custom-slug"

    def test_create_area_auto_slug_lowercase_hyphens(self, area_service):
        area = area_service.create(name="Learning & Development")
        assert area.slug == "learning-development"


class TestChildArea:
    """Create child area."""

    def test_create_child_area(self, area_service):
        parent = area_service.create(name="Parent")
        child = area_service.create(name="Child", parent_id=parent.id)
        assert child.parent_id == parent.id

    def test_create_child_without_parent_fails_not_really(self, area_service):
        # parent_id=None is valid (top-level), we just test it doesn't crash
        area = area_service.create(name="TopLevel")
        assert area.parent_id is None

    def test_self_reference_rejected(self, area_service):
        area = area_service.create(name="SelfRefTest")
        # Attempting to set parent_id to own id should be rejected by repo
        # The service passes validation, but the repo's update() checks.
        # Actually create() doesn't set parent_id to self, so test update.
        try:
            area_service.update(area.id, parent_id=area.id)
            assert False, "Expected ValueError for self-reference"
        except ValueError as e:
            assert "self-reference" in str(e).lower() or "parent_id" in str(e).lower()


class TestDuplicateSlug:
    """Duplicate slug behavior."""

    def test_duplicate_slug_rejected(self, area_service):
        area_service.create(name="Projects")
        try:
            area_service.create(name="Other Projects", slug="projects")
            assert False, "Expected ValueError for duplicate slug"
        except ValueError as e:
            assert "already exists" in str(e)

    def test_duplicate_slug_case_insensitive(self, area_service):
        area_service.create(name="Projects")
        try:
            area_service.create(name="projects", slug="PROJECTS")
            assert False, "Expected ValueError for case-insensitive duplicate"
        except ValueError:
            pass


class TestSeeding:
    """Seed default areas idempotently."""

    def test_seed_default_areas_creates_all(self, seeder):
        created = seeder.seed_defaults()
        assert len(created) == 7
        assert set(created) == {
            "Projects", "Work", "Learning", "Personal", "People", "Goals", "Ideas"
        }

    def test_seed_idempotent(self, seeder):
        first = seeder.seed_defaults()
        assert len(first) == 7
        second = seeder.seed_defaults()
        assert len(second) == 0  # Nothing new created


class TestAreaListing:
    """Area list/filter operations."""

    def test_list_returns_all_active(self, area_service, default_areas):
        all_areas = area_service.list()
        assert len(all_areas) == 7

    def test_list_excludes_archived(self, area_service, default_areas):
        area_service.archive(default_areas[0].id)
        all_areas = area_service.list(include_archived=False)
        assert len(all_areas) == 6
        archived_in_list = [a for a in all_areas if a.id == default_areas[0].id]
        assert len(archived_in_list) == 0

    def test_list_includes_archived_when_requested(self, area_service, default_areas):
        area_service.archive(default_areas[0].id)
        all_areas = area_service.list(include_archived=True)
        assert len(all_areas) == 7


class TestAreaRetrieval:
    """get_by_id and get_by_slug."""

    def test_get_by_id(self, area_service):
        area = area_service.create(name="RetrievalTest")
        found = area_service.get_by_id(area.id)
        assert found is not None
        assert found.name == "RetrievalTest"

    def test_get_by_id_nonexistent(self, area_service):
        assert area_service.get_by_id(99999) is None

    def test_get_by_slug(self, area_service):
        area = area_service.create(name="SlugTest", slug="slug-test")
        found = area_service.get_by_slug("slug-test")
        assert found is not None
        assert found.id == area.id

    def test_get_by_slug_case_insensitive(self, area_service):
        area = area_service.create(name="SlugTest", slug="slug-test")
        found = area_service.get_by_slug("SLUG-TEST")
        assert found is not None


class TestAreaUpdate:
    """Update area fields."""

    def test_update_name(self, area_service):
        area = area_service.create(name="OldName")
        updated = area_service.update(area.id, name="NewName")
        assert updated.name == "NewName"

    def test_update_slug(self, area_service):
        area = area_service.create(name="OldSlug", slug="old-slug")
        updated = area_service.update(area.id, slug="new-slug")
        assert updated.slug == "new-slug"
        assert area_service.get_by_slug("old-slug") is None
        assert area_service.get_by_slug("new-slug") is not None

    def test_update_kind(self, area_service):
        area = area_service.create(name="KindTest", kind="default")
        updated = area_service.update(area.id, kind="custom")
        assert updated.kind == "custom"


class TestAreaArchive:
    """Soft-archive area."""

    def test_archive_sets_timestamp(self, area_service):
        area = area_service.create(name="ArchiveTest")
        archived = area_service.archive(area.id)
        assert archived.archived_at is not None
        assert archived.archived_at.tzinfo is not None
        assert area_service.get_by_id(area.id).archived_at is not None


class TestAreaChildren:
    """List children of an area."""

    def test_list_children_empty(self, area_service):
        parent = area_service.create(name="ParentNoKids")
        children = area_service.list_children(parent.id)
        assert len(children) == 0

    def test_list_children_populated(self, area_service):
        parent = area_service.create(name="ParentWithKids")
        child1 = area_service.create(name="Child1", parent_id=parent.id)
        child2 = area_service.create(name="Child2", parent_id=parent.id)
        children = area_service.list_children(parent.id)
        assert len(children) == 2
        assert {c.id for c in children} == {child1.id, child2.id}
