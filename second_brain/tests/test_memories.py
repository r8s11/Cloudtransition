"""Tests for Memory creation, area/entity references, confidence bounds, validity, and self-reference."""

from datetime import datetime, timezone

from second_brain.types.enums import MemoryType, MemoryClaimType, MemoryStatus


class TestMemoryCreation:
    """Create memory."""

    def test_create_fact_memory(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="Water boils at 100°C at sea level",
            content="At standard atmospheric pressure, water boils at 100°C.",
        )
        assert memory.id is not None
        assert memory.type == "fact"
        assert memory.title == "Water boils at 100°C at sea level"
        assert memory.content == "At standard atmospheric pressure, water boils at 100°C."
        assert memory.status == "candidate"
        assert memory.claim_type == ""
        assert memory.importance is None
        assert memory.confidence_baseline is None
        assert memory.confidence_final is None
        assert memory.superseded_by is None

    def test_create_memory_with_all_fields(self, memory_service):
        now = datetime.now(timezone.utc)
        memory = memory_service.create_memory(
            type="decision",
            area_id=1,
            entity_id=2,
            title="Choose Postgres",
            content="We chose Postgres for the structured storage tier.",
            claim_type="decision",
            status="active",
            importance=0.9,
            confidence_baseline=0.7,
            confidence_final=0.85,
            confidence_reason="Team consensus after evaluation",
            valid_from=now,
            valid_until=now,
            superseded_by=None,
        )
        assert memory.type == "decision"
        assert memory.area_id == 1
        assert memory.entity_id == 2
        assert memory.claim_type == "decision"
        assert memory.status == "active"
        assert memory.importance == 0.9
        assert memory.confidence_baseline == 0.7
        assert memory.confidence_final == 0.85
        assert memory.confidence_reason == "Team consensus after evaluation"
        assert memory.valid_from == now
        assert memory.valid_until == now
        assert memory.superseded_by is None


class TestMemoryAreaReference:
    """Memory can reference area."""

    def test_memory_with_area(self, memory_service, area_service):
        area = area_service.create(name="Work")
        memory = memory_service.create_memory(
            type="fact",
            area_id=area.id,
            title="We use FastAPI",
            content="The backend is built with FastAPI.",
        )
        assert memory.area_id == area.id
        # Round trip
        fetched = memory_service.get_memory(memory.id)
        assert fetched is not None
        assert fetched.area_id == area.id

    def test_memory_without_area(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="Orphan memory",
            content="No area assigned.",
        )
        assert memory.area_id is None


class TestMemoryEntityReference:
    """Memory can reference entity."""

    def test_memory_with_entity(self, memory_service, entity_service):
        entity = entity_service.create_entity("person", "Alice")
        memory = memory_service.create_memory(
            type="fact",
            entity_id=entity.id,
            title="Alice works on backend",
            content="Alice is a backend engineer.",
        )
        assert memory.entity_id == entity.id
        fetched = memory_service.get_memory(memory.id)
        assert fetched.entity_id == entity.id

    def test_memory_without_entity(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="Entity-less memory",
            content="No entity assigned.",
        )
        assert memory.entity_id is None


class TestConfidenceBounds:
    """Confidence bounds enforced."""

    def test_reject_baseline_above_one(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact",
                title="Bad conf",
                confidence_baseline=1.5,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_baseline_negative(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact",
                title="Bad conf",
                confidence_baseline=-0.2,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e) or "confidence_baseline" in str(e)

    def test_reject_final_above_one(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact",
                title="Bad conf",
                confidence_final=2.0,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_confidence_none_allowed(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="No confidence",
        )
        assert memory.confidence_baseline is None
        assert memory.confidence_final is None


class TestImportanceBounds:
    """Importance bounds enforced."""

    def test_reject_importance_above_one(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact",
                title="Bad importance",
                importance=1.2,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_importance_negative(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact",
                title="Bad importance",
                importance=-0.1,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_importance_none_allowed(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="No importance",
        )
        assert memory.importance is None


class TestValidityFields:
    """Optional validity fields work."""

    def test_valid_from_until_optional(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="Valid period",
            content="Some fact with a validity window.",
            valid_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            valid_until=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )
        assert memory.valid_from is not None
        assert memory.valid_until is not None

    def test_no_validity_fields(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="No validity",
        )
        assert memory.valid_from is None
        assert memory.valid_until is None


class TestSelfReference:
    """Superseded_by self-reference can be stored."""

    def test_superseded_by_stored(self, memory_service):
        m1 = memory_service.create_memory(
            type="fact",
            title="Old fact",
            content="This was our original understanding.",
        )
        m2 = memory_service.create_memory(
            type="fact",
            title="Updated fact",
            content="Our updated understanding supersedes the old one.",
            superseded_by=m1.id,
        )
        assert m2.superseded_by == m1.id

    def test_superseded_by_can_be_updated(self, memory_service):
        m1 = memory_service.create_memory(
            type="fact",
            title="First",
        )
        m2 = memory_service.create_memory(
            type="fact",
            title="Second",
        )
        updated = memory_service.update_memory(m2.id, superseded_by=m1.id)
        assert updated.superseded_by == m1.id

    def test_superseded_by_none_stored(self, memory_service):
        memory = memory_service.create_memory(
            type="fact",
            title="No supersession",
            superseded_by=None,
        )
        assert memory.superseded_by is None


class TestMemoryUpdate:
    """Update memory fields."""

    def test_update_title(self, memory_service):
        memory = memory_service.create_memory(
            type="fact", title="Old Title", content="Content"
        )
        updated = memory_service.update_memory(memory.id, title="New Title")
        assert updated.title == "New Title"

    def test_update_status(self, memory_service):
        memory = memory_service.create_memory(
            type="fact", title="Status test", status="candidate"
        )
        updated = memory_service.update_memory(memory.id, status="active")
        assert updated.status == "active"

    def test_update_importance(self, memory_service):
        memory = memory_service.create_memory(
            type="fact", title="Imp test", importance=0.5
        )
        updated = memory_service.update_memory(memory.id, importance=0.9)
        assert updated.importance == 0.9

    def test_update_content(self, memory_service):
        memory = memory_service.create_memory(
            type="fact", title="Content test", content="Original"
        )
        updated = memory_service.update_memory(memory.id, content="Revised")
        assert updated.content == "Revised"


class TestMemoryList:
    """List memories by area/entity."""

    def test_list_by_area(self, memory_service, area_service):
        area = area_service.create(name="TestArea")
        m1 = memory_service.create_memory(
            type="fact", area_id=area.id, title="First"
        )
        m2 = memory_service.create_memory(
            type="fact", area_id=area.id, title="Second"
        )
        m3 = memory_service.create_memory(
            type="fact", title="Orphan"
        )
        by_area = memory_service.list_by_area(area.id)
        assert len(by_area) == 2
        assert {m.id for m in by_area} == {m1.id, m2.id}

    def test_list_by_entity(self, memory_service, entity_service):
        entity = entity_service.create_entity("person", "TestEntity")
        m1 = memory_service.create_memory(
            type="fact", entity_id=entity.id, title="First"
        )
        m2 = memory_service.create_memory(
            type="fact", entity_id=entity.id, title="Second"
        )
        m3 = memory_service.create_memory(
            type="fact", title="Orphan"
        )
        by_entity = memory_service.list_by_entity(entity.id)
        assert len(by_entity) == 2
        assert {m.id for m in by_entity} == {m1.id, m2.id}


class TestMemoryValidation:
    """Reject invalid memory values."""

    def test_reject_invalid_type(self, memory_service):
        try:
            memory_service.create_memory(type="invalid_type", title="Test")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_invalid_claim_type(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact", title="Test", claim_type="invalid_claim"
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_invalid_status(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact", title="Test", status="invalid_status"
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_blank_title_when_provided(self, memory_service):
        try:
            memory_service.create_memory(
                type="fact", title="   ", content="Content"
            )
            assert False, "Expected ValueError for blank title"
        except ValueError:
            pass

    def test_empty_title_allowed_when_not_provided(self, memory_service):
        # Title can be empty when not provided, but if provided, must be non-blank
        memory = memory_service.create_memory(
            type="fact", content="Just content, no title"
        )
        assert memory.title == ""
