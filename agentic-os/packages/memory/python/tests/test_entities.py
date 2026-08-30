"""Tests for Entity creation, area attachment, aliases, and validation."""

from second_brain.repositories.entity_repository import EntityRepository
from second_brain.repositories.entity_alias_repository import EntityAliasRepository
from second_brain.services.entity_service import EntityService, EntityAliasService
from second_brain.types.enums import EntityType


def _make_entity_service():
    repo = EntityRepository()
    alias_repo = EntityAliasRepository()
    return EntityService(repo, alias_repo), EntityAliasService(alias_repo), repo, alias_repo


class TestEntityCreation:
    """Create entity."""

    def test_create_person_entity(self, entity_service):
        entity = entity_service.create_entity(
            type="person",
            canonical_name="Alice Smith",
        )
        assert entity.id is not None
        assert entity.type == "person"
        assert entity.canonical_name == "Alice Smith"
        assert entity.description == ""
        assert entity.area_id is None
        assert entity.metadata == {}

    def test_create_project_entity(self, entity_service):
        entity = entity_service.create_entity(
            type="project",
            canonical_name="MyCoolApp",
            description="A cool application",
        )
        assert entity.type == "project"
        assert entity.canonical_name == "MyCoolApp"
        assert entity.description == "A cool application"

    def test_create_with_metadata(self, entity_service):
        metadata = {"industry": "finance", "tech_stack": ["Python", "Postgres"]}
        entity = entity_service.create_entity(
            type="organization",
            canonical_name="Acme Corp",
            metadata=metadata,
        )
        assert entity.metadata == metadata


class TestEntityAreaAttachment:
    """Attach entity to an area."""

    def test_entity_with_area(self, entity_service, area_service):
        area = area_service.create(name="People")
        entity = entity_service.create_entity(
            type="person",
            canonical_name="Bob Jones",
            area_id=area.id,
        )
        assert entity.area_id == area.id
        fetched = entity_service.get_entity(entity.id)
        assert fetched is not None
        assert fetched.area_id == area.id


class TestEntityFindByName:
    """Find entity by canonical name."""

    def test_find_by_exact_name(self, entity_service):
        entity = entity_service.create_entity(
            type="person", canonical_name="Carol White"
        )
        found = entity_service.find_by_name("Carol White")
        assert found is not None
        assert found.id == entity.id

    def test_find_by_lowercased_name(self, entity_service):
        entity = entity_service.create_entity(
            type="person", canonical_name="Dave Brown"
        )
        found = entity_service.find_by_name("dave brown")
        assert found is not None

    def test_find_nonexistent(self, entity_service):
        assert entity_service.find_by_name("Nobody") is None

    def test_find_blank_name_returns_none(self, entity_service):
        assert entity_service.find_by_name("") is None


class TestEntityUpdate:
    """Update entity fields."""

    def test_update_type(self, entity_service):
        entity = entity_service.create_entity(
            type="person", canonical_name="Eve Adams"
        )
        updated = entity_service.update_entity(entity.id, type="project")
        assert updated.type == "project"

    def test_update_canonical_name(self, entity_service):
        entity = entity_service.create_entity(
            type="person", canonical_name="Frank Miller"
        )
        updated = entity_service.update_entity(entity.id, canonical_name="Frank Miller Jr.")
        assert updated.canonical_name == "Frank Miller Jr."
        assert entity_service.find_by_name("Frank Miller") is None
        assert entity_service.find_by_name("Frank Miller Jr.") is not None


class TestEntityValidation:
    """Reject invalid entity values."""

    def test_reject_blank_canonical_name(self, entity_service):
        try:
            entity_service.create_entity(type="person", canonical_name="   ")
            assert False, "Expected ValueError for blank name"
        except ValueError:
            pass

    def test_reject_invalid_type_in_service(self, entity_service):
        try:
            entity_service.create_entity(type="invalid_type", canonical_name="Test")
            assert False, "Expected ValueError for invalid type"
        except ValueError as e:
            assert "must be one of" in str(e)


class TestEntityAlias:
    """Create alias and reject invalid confidence."""

    def test_create_alias(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "Test Person")
        alias = alias_service.create_alias(entity.id, "testperson", confidence=0.85)
        assert alias.alias == "testperson"
        assert alias.normalized_alias == "testperson"
        assert alias.confidence == 0.85
        assert alias.entity_id == entity.id

    def test_create_alias_normalizes_whitespace_and_case(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "Normalized Test")
        alias = alias_service.create_alias(
            entity.id, "  AlIce   SmIth  ", confidence=0.9
        )
        assert alias.alias == "AlIce   SmIth"
        assert alias.normalized_alias == "alice smith"
        assert alias.confidence == 0.9

    def test_reject_invalid_confidence_too_high(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "ConfTest")
        try:
            alias_service.create_alias(entity.id, "bad", confidence=1.5)
            assert False, "Expected ValueError for confidence > 1"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_invalid_confidence_negative(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "ConfTest2")
        try:
            alias_service.create_alias(entity.id, "bad", confidence=-0.1)
            assert False, "Expected ValueError for negative confidence"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_confidence_none_allowed(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "ConfNoneTest")
        alias = alias_service.create_alias(entity.id, "unknown", confidence=None)
        assert alias.confidence is None

    def test_list_aliases_for_entity(self, alias_service, entity_service):
        entity = entity_service.create_entity("person", "AliasListTest")
        a1 = alias_service.create_alias(entity.id, "alias1", confidence=0.5)
        a2 = alias_service.create_alias(entity.id, "alias2", confidence=0.7)
        aliases = alias_service.list_aliases_for_entity(entity.id)
        assert len(aliases) == 2
        assert {a.alias for a in aliases} == {"alias1", "alias2"}
