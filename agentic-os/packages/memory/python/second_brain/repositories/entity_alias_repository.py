"""Repository for EntityAlias persistence."""

from datetime import datetime, timezone

from second_brain.types.models import EntityAlias
from second_brain.types.validation import (
    validate_confidence,
    validate_not_blank,
    normalize_alias,
)


class EntityAliasRepository:
    """Persistence for EntityAlias (alias → entity mapping)."""

    def __init__(self) -> None:
        self._store: dict[int, EntityAlias] = {}
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        entity_id: int,
        alias: str,
        confidence: float | None = None,
        source_id: int | None = None,
    ) -> EntityAlias:
        """Create a new alias for an entity."""
        validate_not_blank(alias, "alias")
        validate_confidence(confidence, "confidence")

        normalized = normalize_alias(alias)

        alias_model = EntityAlias(
            id=self._next_id,
            entity_id=entity_id,
            alias=alias.strip(),
            normalized_alias=normalized,
            confidence=confidence,
            source_id=source_id,
            created_at=self._now(),
        )
        alias_model._exists_in_db = True

        self._store[alias_model.id] = alias_model
        self._next_id += 1
        return alias_model

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, alias_id: int) -> EntityAlias | None:
        if not isinstance(alias_id, int) or alias_id <= 0:
            return None
        return self._store.get(alias_id)

    # ── list by entity ────────────────────────────────────────────────

    def list_by_entity(self, entity_id: int) -> list[EntityAlias]:
        return [
            a for a in self._store.values() if a.entity_id == entity_id
        ]

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        alias_id: int,
        alias: str | None = None,
        confidence: float | None = None,
        source_id: int | None = None,
    ) -> EntityAlias:
        entry = self.get_by_id(alias_id)
        if entry is None:
            raise ValueError(f"EntityAlias with id {alias_id} not found")

        if alias is not None:
            validate_not_blank(alias, "alias")
            entry.alias = alias.strip()
            entry.normalized_alias = normalize_alias(alias)

        if confidence is not None:
            validate_confidence(confidence, "confidence")
            entry.confidence = confidence

        if source_id is not None:
            entry.source_id = source_id

        return entry

    # ── list all ──────────────────────────────────────────────────────

    def list(self) -> list[EntityAlias]:
        return sorted(self._store.values(), key=lambda a: a.id)
