"""Repository for Memory persistence."""

from datetime import datetime, timezone

from second_brain.types.models import Memory
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
    validate_importance,
)
from second_brain.types.enums import (
    VALID_MEMORY_TYPES,
    VALID_CLAIM_TYPES,
    VALID_MEMORY_STATUSES,
)


class MemoryRepository:
    """Persistence for Memory entities."""

    def __init__(self) -> None:
        self._store: dict[int, Memory] = {}
        self._by_area: dict[int, list[int]] = {}
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        type: str,
        area_id: int | None = None,
        entity_id: int | None = None,
        title: str = "",
        content: str = "",
        claim_type: str = "",
        status: str = "candidate",
        importance: float | None = None,
        confidence_baseline: float | None = None,
        confidence_final: float | None = None,
        confidence_reason: str = "",
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        superseded_by: int | None = None,
    ) -> Memory:
        """Create a new memory."""
        validate_enum_value(type, VALID_MEMORY_TYPES, "type")
        if claim_type:
            validate_enum_value(claim_type, VALID_CLAIM_TYPES, "claim_type")
        validate_enum_value(status, VALID_MEMORY_STATUSES, "status")
        validate_confidence(confidence_baseline, "confidence_baseline")
        validate_confidence(confidence_final, "confidence_final")
        validate_importance(importance, "importance")

        if title:
            validate_not_blank(title, "title")

        memory = Memory(
            id=self._next_id,
            type=type,
            area_id=area_id,
            entity_id=entity_id,
            title=title.strip(),
            content=content.strip(),
            claim_type=claim_type,
            status=status,
            importance=importance,
            confidence_baseline=confidence_baseline,
            confidence_final=confidence_final,
            confidence_reason=confidence_reason.strip(),
            valid_from=valid_from,
            valid_until=valid_until,
            superseded_by=superseded_by,
            created_at=self._now(),
            updated_at=self._now(),
        )
        memory._exists_in_db = True

        self._store[memory.id] = memory
        if area_id is not None:
            self._by_area.setdefault(area_id, []).append(memory.id)

        self._next_id += 1
        return memory

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, memory_id: int) -> Memory | None:
        if not isinstance(memory_id, int) or memory_id <= 0:
            return None
        return self._store.get(memory_id)

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        memory_id: int,
        type: str | None = None,
        area_id: int | None = None,
        entity_id: int | None = None,
        title: str | None = None,
        content: str | None = None,
        claim_type: str | None = None,
        status: str | None = None,
        importance: float | None = None,
        confidence_baseline: float | None = None,
        confidence_final: float | None = None,
        confidence_reason: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        superseded_by: int | None = None,
    ) -> Memory:
        memory = self.get_by_id(memory_id)
        if memory is None:
            raise ValueError(f"Memory with id {memory_id} not found")

        if type is not None:
            validate_enum_value(type, VALID_MEMORY_TYPES, "type")
            memory.type = type

        if area_id is not None:
            old_area = memory.area_id
            memory.area_id = area_id
            if old_area is not None and old_area != area_id:
                if old_area in self._by_area:
                    self._by_area[old_area] = [
                        mid for mid in self._by_area[old_area] if mid != memory_id
                    ]
            self._by_area.setdefault(area_id, []).append(memory_id)

        if entity_id is not None:
            memory.entity_id = entity_id

        if title is not None:
            if title:
                validate_not_blank(title, "title")
            memory.title = title.strip()

        if content is not None:
            memory.content = content.strip()

        if claim_type is not None:
            validate_enum_value(claim_type, VALID_CLAIM_TYPES, "claim_type")
            memory.claim_type = claim_type

        if status is not None:
            validate_enum_value(status, VALID_MEMORY_STATUSES, "status")
            memory.status = status

        if importance is not None:
            validate_importance(importance)
            memory.importance = importance

        if confidence_baseline is not None:
            validate_confidence(confidence_baseline, "confidence_baseline")
            memory.confidence_baseline = confidence_baseline

        if confidence_final is not None:
            validate_confidence(confidence_final, "confidence_final")
            memory.confidence_final = confidence_final

        if confidence_reason is not None:
            memory.confidence_reason = confidence_reason.strip()

        if valid_from is not None:
            memory.valid_from = valid_from

        if valid_until is not None:
            memory.valid_until = valid_until

        if superseded_by is not None:
            # Allow any positive integer; we don't enforce existence check here
            if not isinstance(superseded_by, int) or superseded_by <= 0:
                raise ValueError(
                    f"superseded_by must be a positive integer, got {superseded_by}"
                )
            memory.superseded_by = superseded_by

        memory.updated_at = self._now()
        return memory

    # ── list by area ──────────────────────────────────────────────────

    def list_by_area(self, area_id: int) -> list[Memory]:
        ids = self._by_area.get(area_id, [])
        return [self._store[mid] for mid in ids if mid in self._store]

    # ── list by entity ────────────────────────────────────────────────

    def list_by_entity(self, entity_id: int) -> list[Memory]:
        return [
            m for m in self._store.values() if m.entity_id == entity_id
        ]

    # ── list all ──────────────────────────────────────────────────────

    def list(self) -> list[Memory]:
        return sorted(self._store.values(), key=lambda m: m.id)

    # ── archive ───────────────────────────────────────────────────────

    def archive(self, memory_id: int) -> Memory:
        memory = self.get_by_id(memory_id)
        if memory is None:
            raise ValueError(f"Memory with id {memory_id} not found")
        memory.archived_at = self._now()
        memory.status = "archived"
        memory.updated_at = self._now()
        return memory
