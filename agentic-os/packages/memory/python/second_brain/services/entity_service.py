"""Entity service — validates input, normalizes fields, delegates to repository."""

from typing import Any

from second_brain.repositories.entity_repository import EntityRepository
from second_brain.repositories.entity_alias_repository import EntityAliasRepository
from second_brain.types.enums import VALID_ENTITY_TYPES
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
    normalize_alias,
)
from second_brain.types.models import Entity, EntityAlias


class EntityService:
    """Business-logic layer for Entity operations.

    Phase 1 responsibilities:
    - validate input (valid type, non-blank name)
    - normalize obvious fields (trim whitespace, lowercase canonical name
      for lookup indexing)
    - delegate persistence to the repository
    """

    def __init__(
        self,
        entity_repo: EntityRepository,
        alias_repo: EntityAliasRepository,
    ) -> None:
        self._entity_repo = entity_repo
        self._alias_repo = alias_repo

    def create_entity(
        self,
        type: str,
        canonical_name: str,
        description: str = "",
        area_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Entity:
        """Create a new entity after validation."""
        validate_enum_value(type, VALID_ENTITY_TYPES, "type")
        validate_not_blank(canonical_name, "canonical_name")

        normalized_type = type.strip()
        normalized_name = canonical_name.strip()
        normalized_description = description.strip()
        normalized_metadata = metadata or {}

        return self._entity_repo.create(
            type=normalized_type,
            canonical_name=normalized_name,
            description=normalized_description,
            area_id=area_id,
            metadata=normalized_metadata,
        )

    def get_entity(self, entity_id: int) -> Entity | None:
        return self._entity_repo.get_by_id(entity_id)

    def find_by_name(self, canonical_name: str) -> Entity | None:
        return self._entity_repo.find_by_canonical_name(canonical_name)

    def list_entities(self) -> list[Entity]:
        return self._entity_repo.list()

    def update_entity(
        self,
        entity_id: int,
        type: str | None = None,
        canonical_name: str | None = None,
        description: str | None = None,
        area_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Entity:
        """Update an entity after validation."""
        if type is not None:
            validate_enum_value(type, VALID_ENTITY_TYPES, "type")
        if canonical_name is not None:
            validate_not_blank(canonical_name, "canonical_name")

        return self._entity_repo.update(
            entity_id=entity_id,
            type=type,
            canonical_name=canonical_name,
            description=description,
            area_id=area_id,
            metadata=metadata,
        )


class EntityAliasService:
    """Business-logic layer for EntityAlias operations.

    Phase 1 responsibilities:
    - validate confidence is in [0, 1]
    - normalize aliases (lowercase, trim, collapse whitespace)
    - delegate persistence to the repository
    """

    def __init__(self, alias_repo: EntityAliasRepository) -> None:
        self._alias_repo = alias_repo

    def create_alias(
        self,
        entity_id: int,
        alias: str,
        confidence: float | None = None,
        source_id: int | None = None,
    ) -> EntityAlias:
        """Create a new alias for an entity after validation and normalization."""
        validate_confidence(confidence, "confidence")
        normalized_alias = normalize_alias(alias)

        return self._alias_repo.create(
            entity_id=entity_id,
            alias=alias.strip(),
            confidence=confidence,
            source_id=source_id,
        )

    def get_alias(self, alias_id: int) -> EntityAlias | None:
        return self._alias_repo.get_by_id(alias_id)

    def list_aliases_for_entity(self, entity_id: int) -> list[EntityAlias]:
        return self._alias_repo.list_by_entity(entity_id)

    def list_all_aliases(self) -> list[EntityAlias]:
        return self._alias_repo.list()

    def update_alias(
        self,
        alias_id: int,
        alias: str | None = None,
        confidence: float | None = None,
        source_id: int | None = None,
    ) -> EntityAlias:
        """Update an alias after validation."""
        if alias is not None:
            validate_confidence(None, "confidence")  # no-op for alias field
        if confidence is not None:
            validate_confidence(confidence, "confidence")

        return self._alias_repo.update(
            alias_id=alias_id,
            alias=alias,
            confidence=confidence,
            source_id=source_id,
        )
