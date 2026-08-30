"""Repository for MemorySource persistence."""

from datetime import datetime, timezone
from typing import Any

from second_brain.types.models import MemorySource
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
)
from second_brain.types.enums import VALID_SOURCE_TYPES


class MemorySourceRepository:
    """Persistence for MemorySource entities."""

    def __init__(self) -> None:
        self._store: dict[int, MemorySource] = {}
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        source_type: str,
        external_id: str | None = None,
        title: str = "",
        uri: str | None = None,
        occurred_at: datetime | None = None,
        imported_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> MemorySource:
        """Create a new memory source."""
        validate_enum_value(source_type, VALID_SOURCE_TYPES, "source_type")

        source = MemorySource(
            id=self._next_id,
            source_type=source_type,
            external_id=external_id.strip() if external_id else None,
            title=title.strip(),
            uri=uri.strip() if uri else None,
            occurred_at=occurred_at,
            imported_at=imported_at or self._now(),
            metadata=metadata or {},
            content_hash=content_hash,
        )
        source._exists_in_db = True

        self._store[source.id] = source
        self._next_id += 1
        return source

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, source_id: int) -> MemorySource | None:
        if not isinstance(source_id, int) or source_id <= 0:
            return None
        return self._store.get(source_id)

    # ── list ──────────────────────────────────────────────────────────

    def list(self) -> list[MemorySource]:
        return sorted(self._store.values(), key=lambda s: s.id)

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        source_id: int,
        source_type: str | None = None,
        external_id: str | None = None,
        title: str | None = None,
        uri: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
    ) -> MemorySource:
        source = self.get_by_id(source_id)
        if source is None:
            raise ValueError(f"MemorySource with id {source_id} not found")

        if source_type is not None:
            validate_enum_value(source_type, VALID_SOURCE_TYPES, "source_type")
            source.source_type = source_type

        if external_id is not None:
            source.external_id = external_id.strip() if external_id else None

        if title is not None:
            source.title = title.strip()

        if uri is not None:
            source.uri = uri.strip() if uri else None

        if metadata is not None:
            source.metadata = metadata

        if content_hash is not None:
            source.content_hash = content_hash

        return source
