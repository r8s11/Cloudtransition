"""Repository for MemoryEvidence persistence."""

from datetime import datetime, timezone

from second_brain.types.models import MemoryEvidence
from second_brain.types.validation import (
    validate_confidence,
    validate_not_blank,
)


class MemoryEvidenceRepository:
    """Persistence for MemoryEvidence (source ↔ memory links)."""

    def __init__(self) -> None:
        self._store: dict[int, MemoryEvidence] = {}
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        memory_id: int,
        source_id: int,
        evidence_type: str = "",
        excerpt: str = "",
        strength: float | None = None,
        supports: bool | None = None,
    ) -> MemoryEvidence:
        """Create a new evidence entry linking a source to a memory."""
        validate_confidence(strength, "strength")

        evidence = MemoryEvidence(
            id=self._next_id,
            memory_id=memory_id,
            source_id=source_id,
            evidence_type=evidence_type.strip(),
            excerpt=excerpt.strip(),
            strength=strength,
            supports=supports,
            created_at=self._now(),
        )
        evidence._exists_in_db = True

        self._store[evidence.id] = evidence
        self._next_id += 1
        return evidence

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, evidence_id: int) -> MemoryEvidence | None:
        if not isinstance(evidence_id, int) or evidence_id <= 0:
            return None
        return self._store.get(evidence_id)

    # ── list by memory ────────────────────────────────────────────────

    def list_by_memory(self, memory_id: int) -> list[MemoryEvidence]:
        return [
            e for e in self._store.values() if e.memory_id == memory_id
        ]

    # ── list by source ────────────────────────────────────────────────

    def list_by_source(self, source_id: int) -> list[MemoryEvidence]:
        return [
            e for e in self._store.values() if e.source_id == source_id
        ]

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        evidence_id: int,
        evidence_type: str | None = None,
        excerpt: str | None = None,
        strength: float | None = None,
        supports: bool | None = None,
    ) -> MemoryEvidence:
        evidence = self.get_by_id(evidence_id)
        if evidence is None:
            raise ValueError(f"MemoryEvidence with id {evidence_id} not found")

        if evidence_type is not None:
            evidence.evidence_type = evidence_type.strip()

        if excerpt is not None:
            evidence.excerpt = excerpt.strip()

        if strength is not None:
            validate_confidence(strength, "strength")
            evidence.strength = strength

        if supports is not None:
            evidence.supports = supports

        return evidence

    # ── list all ──────────────────────────────────────────────────────

    def list(self) -> list[MemoryEvidence]:
        return sorted(self._store.values(), key=lambda e: e.id)
