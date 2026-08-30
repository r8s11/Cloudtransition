"""Tests for MemorySource and MemoryEvidence creation and validation."""

from second_brain.types.enums import SourceType
from second_brain.types.models import MemoryEvidence


class TestMemorySourceCreation:
    """Create source."""

    def test_create_conversation_source(self, source_repo):
        source = source_repo.create(
            source_type="conversation",
            title="Team standup on Monday",
            occurred_at=None,
        )
        assert source.id is not None
        assert source.source_type == "conversation"
        assert source.title == "Team standup on Monday"
        assert source.external_id is None
        assert source.uri is None
        assert source.occurred_at is None
        assert source.imported_at is not None
        assert source.metadata == {}
        assert source.content_hash is None

    def test_create_file_source_with_uri(self, source_repo):
        source = source_repo.create(
            source_type="file",
            title="Meeting notes",
            uri="file:///notes/meeting-2024-01-01.md",
            content_hash="sha256:abc123",
        )
        assert source.source_type == "file"
        assert source.uri == "file:///notes/meeting-2024-01-01.md"
        assert source.content_hash == "sha256:abc123"

    def test_create_source_with_external_id(self, source_repo):
        source = source_repo.create(
            source_type="github",
            title="Issue #42",
            external_id="42",
        )
        assert source.external_id == "42"

    def test_create_source_with_metadata(self, source_repo):
        metadata = {"conversation_id": "conv-123", "participant_count": 5}
        source = source_repo.create(
            source_type="conversation",
            title="Call with customer",
            metadata=metadata,
        )
        assert source.metadata == metadata


class TestMemorySourceUpdate:
    """Update source fields."""

    def test_update_title(self, source_repo):
        source = source_repo.create(source_type="file", title="Old Title")
        updated = source_repo.update(source.id, title="New Title")
        assert updated.title == "New Title"

    def test_update_uri(self, source_repo):
        source = source_repo.create(source_type="file", title="Test")
        updated = source_repo.update(source.id, uri="file:///new/path.md")
        assert updated.uri == "file:///new/path.md"

    def test_update_metadata(self, source_repo):
        source = source_repo.create(source_type="manual", title="Test")
        updated = source_repo.update(
            source.id, metadata={"updated": True, "version": 2}
        )
        assert updated.metadata == {"updated": True, "version": 2}


class TestMemoryEvidenceCreation:
    """Attach evidence to memory."""

    def test_evidence_supports_true(self, evidence_repo):
        evidence = evidence_repo.create(
            memory_id=1,
            source_id=1,
            evidence_type="direct_quote",
            excerpt="The system uses PostgreSQL.",
            strength=0.9,
            supports=True,
        )
        assert evidence.supports is True
        assert evidence.strength == 0.9

    def test_evidence_supports_false(self, evidence_repo):
        evidence = evidence_repo.create(
            memory_id=1,
            source_id=1,
            evidence_type="contradiction",
            excerpt="Actually, the system uses MySQL.",
            strength=0.8,
            supports=False,
        )
        assert evidence.supports is False

    def test_evidence_supports_null_contextual(self, evidence_repo):
        evidence = evidence_repo.create(
            memory_id=1,
            source_id=1,
            evidence_type="contextual",
            excerpt="Background information about the project.",
            strength=0.5,
            supports=None,
        )
        assert evidence.supports is None

    def test_evidence_strength_in_range(self, evidence_repo):
        evidence = evidence_repo.create(
            memory_id=1,
            source_id=1,
            excerpt="Some evidence",
            strength=0.0,
        )
        assert evidence.strength == 0.0

        evidence2 = evidence_repo.create(
            memory_id=2,
            source_id=1,
            excerpt="Another evidence",
            strength=1.0,
        )
        assert evidence2.strength == 1.0


class TestEvidenceValidation:
    """Invalid strength rejected."""

    def test_reject_strength_above_one(self, evidence_repo):
        try:
            evidence_repo.create(
                memory_id=1,
                source_id=1,
                excerpt="Bad evidence",
                strength=1.5,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_strength_negative(self, evidence_repo):
        try:
            evidence_repo.create(
                memory_id=1,
                source_id=1,
                excerpt="Bad evidence",
                strength=-0.1,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e) or "strength" in str(e)

    def test_strength_none_allowed(self, evidence_repo):
        evidence = evidence_repo.create(
            memory_id=1,
            source_id=1,
            excerpt="No strength estimate",
            strength=None,
        )
        assert evidence.strength is None


class TestEvidenceListing:
    """List evidence by memory and source."""

    def test_list_by_memory(self, evidence_repo):
        e1 = evidence_repo.create(memory_id=1, source_id=1, excerpt="E1")
        e2 = evidence_repo.create(memory_id=1, source_id=2, excerpt="E2")
        e3 = evidence_repo.create(memory_id=2, source_id=1, excerpt="E3")
        by_memory = evidence_repo.list_by_memory(1)
        assert len(by_memory) == 2
        assert {e.id for e in by_memory} == {e1.id, e2.id}

    def test_list_by_source(self, evidence_repo):
        e1 = evidence_repo.create(memory_id=1, source_id=1, excerpt="E1")
        e2 = evidence_repo.create(memory_id=2, source_id=1, excerpt="E2")
        e3 = evidence_repo.create(memory_id=3, source_id=2, excerpt="E3")
        by_source = evidence_repo.list_by_source(1)
        assert len(by_source) == 2
        assert {e.id for e in by_source} == {e1.id, e2.id}


class TestEvidenceUpdate:
    """Update evidence fields."""

    def test_update_excerpt(self, evidence_repo):
        e = evidence_repo.create(memory_id=1, source_id=1, excerpt="Original")
        updated = evidence_repo.update(e.id, excerpt="Updated excerpt")
        assert updated.excerpt == "Updated excerpt"

    def test_update_strength(self, evidence_repo):
        e = evidence_repo.create(memory_id=1, source_id=1, strength=0.5)
        updated = evidence_repo.update(e.id, strength=0.9)
        assert updated.strength == 0.9

    def test_update_supports(self, evidence_repo):
        e = evidence_repo.create(
            memory_id=1, source_id=1, excerpt="Test", supports=True
        )
        updated = evidence_repo.update(e.id, supports=False)
        assert updated.supports is False
