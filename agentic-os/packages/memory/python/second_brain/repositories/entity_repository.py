"""Repository for Entity persistence."""

from datetime import datetime, timezone
from typing import Any

from second_brain.types.models import Entity, EntityAlias
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
)
from second_brain.types.enums import VALID_ENTITY_TYPES


class EntityRepository:
    """Persistence for Entity entities."""

    def __init__(self) -> None:
        self._store: dict[int, Entity] = {}
        self._by_name: dict[str, int] = {}
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        type: str,
        canonical_name: str,
        description: str = "",
        area_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Entity:
        """Create a new entity."""
        validate_enum_value(type, VALID_ENTITY_TYPES, "type")
        validate_not_blank(canonical_name, "canonical_name")

        entity = Entity(
            id=self._next_id,
            type=type,
            canonical_name=canonical_name.strip(),
            description=description.strip(),
            area_id=area_id,
            metadata=metadata or {},
            created_at=self._now(),
            updated_at=self._now(),
        )
        entity._exists_in_db = True

        self._store[entity.id] = entity
        # Index by canonical name (lowercased) for lookup
        key = canonical_name.strip().lower()
        if key not in self._by_name:
            self._by_name[key] = entity.id

        self._next_id += 1
        return entity

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, entity_id: int) -> Entity | None:
        if not isinstance(entity_id, int) or entity_id <= 0:
            return None
        return self._store.get(entity_id)

    # ── find by canonical name ────────────────────────────────────────

    def find_by_canonical_name(self, canonical_name: str) -> Entity | None:
        key = canonical_name.strip().lower() if canonical_name else ""
        if not key:
            return None
        entity_id = self._by_name.get(key)
        if entity_id is None:
            return None
        return self._store.get(entity_id)

    # ── list ──────────────────────────────────────────────────────────

    def list(self) -> list[Entity]:
        return sorted(self._store.values(), key=lambda e: e.id)

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        entity_id: int,
        type: str | None = None,
        canonical_name: str | None = None,
        description: str | None = None,
        area_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Entity:
        entity = self.get_by_id(entity_id)
        if entity is None:
            raise ValueError(f"Entity with id {entity_id} not found")

        if type is not None:
            validate_enum_value(type, VALID_ENTITY_TYPES, "type")
            entity.type = type

        if canonical_name is not None:
            validate_not_blank(canonical_name, "canonical_name")
            old_key = entity.canonical_name.strip().lower()
            new_name = canonical_name.strip()
            entity.canonical_name = new_name
            new_key = new_name.lower()
            if old_key in self._by_name and self._by_name[old_key] == entity_id:
                del self._by_name[old_key]
            self._by_name[new_key] = entity_id

        if description is not None:
            entity.description = description.strip()

        if area_id is not None:
            entity.area_id = area_id

        if metadata is not None:
            entity.metadata = metadata

        entity.updated_at = self._now()
        return entity
