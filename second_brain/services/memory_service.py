"""Memory service — validates input, normalizes fields, delegates to repository."""

from datetime import datetime

from second_brain.repositories.memory_repository import MemoryRepository
from second_brain.types.enums import (
    VALID_MEMORY_TYPES,
    VALID_CLAIM_TYPES,
    VALID_MEMORY_STATUSES,
)
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
    validate_importance,
)
from second_brain.types.models import Memory


class MemoryService:
    """Business-logic layer for Memory operations.

    Phase 1 responsibilities:
    - validate input (valid type/claim/status, confidence/importance bounds)
    - normalize obvious fields (trim whitespace)
    - allow optional validity dates and self-reference fields
    - delegate persistence to the repository
    """

    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    def create_memory(
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
        """Create a new memory after validation and normalization."""
        validate_enum_value(type, VALID_MEMORY_TYPES, "type")
        if claim_type:
            validate_enum_value(claim_type, VALID_CLAIM_TYPES, "claim_type")
        validate_enum_value(status, VALID_MEMORY_STATUSES, "status")
        validate_confidence(confidence_baseline, "confidence_baseline")
        validate_confidence(confidence_final, "confidence_final")
        validate_importance(importance)
        if title:
            validate_not_blank(title, "title")

        return self._repo.create(
            type=type.strip(),
            area_id=area_id,
            entity_id=entity_id,
            title=title.strip(),
            content=content.strip(),
            claim_type=claim_type.strip(),
            status=status.strip(),
            importance=importance,
            confidence_baseline=confidence_baseline,
            confidence_final=confidence_final,
            confidence_reason=confidence_reason.strip(),
            valid_from=valid_from,
            valid_until=valid_until,
            superseded_by=superseded_by,
        )

    def get_memory(self, memory_id: int) -> Memory | None:
        return self._repo.get_by_id(memory_id)

    def update_memory(
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
        """Update a memory after validation."""
        if type is not None:
            validate_enum_value(type, VALID_MEMORY_TYPES, "type")
        if claim_type is not None:
            validate_enum_value(claim_type, VALID_CLAIM_TYPES, "claim_type")
        if status is not None:
            validate_enum_value(status, VALID_MEMORY_STATUSES, "status")
        if confidence_baseline is not None:
            validate_confidence(confidence_baseline, "confidence_baseline")
        if confidence_final is not None:
            validate_confidence(confidence_final, "confidence_final")
        if importance is not None:
            validate_importance(importance)
        if title is not None and title:
            validate_not_blank(title, "title")

        return self._repo.update(
            memory_id=memory_id,
            type=type,
            area_id=area_id,
            entity_id=entity_id,
            title=title,
            content=content,
            claim_type=claim_type,
            status=status,
            importance=importance,
            confidence_baseline=confidence_baseline,
            confidence_final=confidence_final,
            confidence_reason=confidence_reason,
            valid_from=valid_from,
            valid_until=valid_until,
            superseded_by=superseded_by,
        )

    def list_by_area(self, area_id: int) -> list[Memory]:
        return self._repo.list_by_area(area_id)

    def list_by_entity(self, entity_id: int) -> list[Memory]:
        return self._repo.list_by_entity(entity_id)

    def list_all(self) -> list[Memory]:
        return self._repo.list()

    def archive(self, memory_id: int) -> Memory:
        return self._repo.archive(memory_id)
