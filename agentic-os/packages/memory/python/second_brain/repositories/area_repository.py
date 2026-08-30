"""Repository for Area persistence."""

from datetime import datetime, timezone
from typing import Any

from second_brain.types.models import Area
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_parent_id,
    validate_confidence,
)
from second_brain.types.enums import VALID_AREA_KINDS


class AreaRepository:
    """Persistence for Area entities.

    Uses an in-memory dict as a stand-in for Postgres. In production this
    would be backed by psycopg2/sqlalchemy/SQLModel against the actual tables.
    """

    def __init__(self) -> None:
        self._store: dict[int, Area] = {}
        self._by_slug: dict[str, int] = {}
        self._next_id = 1

    # ── helpers ──────────────────────────────────────────────────────

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _slug_from_name(self, name: str) -> str:
        """Derive a slug from a name: lowercase, replace spaces with hyphens,
        strip non-alphanumeric characters."""
        lowered = name.lower().strip()
        slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in lowered)
        # collapse repeated hyphens
        parts = slug.split("-")
        slug = "-".join(p for p in parts if p)
        return slug

    # ── create ────────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        slug: str | None = None,
        parent_id: int | None = None,
        kind: str = "default",
        description: str = "",
    ) -> Area:
        """Create a new area and persist it."""
        validate_not_blank(name, "name")

        if slug is None:
            slug = self._slug_from_name(name)

        validate_not_blank(slug, "slug")
        validate_enum_value(kind, VALID_AREA_KINDS, "kind")
        validate_parent_id(parent_id)

        # Ensure slug uniqueness (within this repository instance)
        if slug in self._by_slug:
            raise ValueError(f"Area with slug '{slug}' already exists")

        area = Area(
            id=self._next_id,
            name=name.strip(),
            slug=slug.strip().lower(),
            parent_id=parent_id,
            kind=kind,
            description=description.strip(),
            created_at=self._now(),
            updated_at=self._now(),
        )
        area._exists_in_db = True

        self._store[area.id] = area
        self._by_slug[area.slug] = area.id
        self._next_id += 1
        return area

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, area_id: int) -> Area | None:
        """Fetch an area by its primary key."""
        if not isinstance(area_id, int) or area_id <= 0:
            return None
        return self._store.get(area_id)

    # ── get by slug ───────────────────────────────────────────────────

    def get_by_slug(self, slug: str) -> Area | None:
        """Fetch an area by its unique slug."""
        area_id = self._by_slug.get(slug.strip().lower())
        if area_id is None:
            return None
        return self._store.get(area_id)

    # ── list ──────────────────────────────────────────────────────────

    def list(self, include_archived: bool = False) -> list[Area]:
        """List all areas, optionally excluding archived ones."""
        areas = list(self._store.values())
        if not include_archived:
            areas = [a for a in areas if a.archived_at is None]
        # Return in insertion order
        return sorted(areas, key=lambda a: a.id)

    # ── update ────────────────────────────────────────────────────────

    def update(
        self,
        area_id: int,
        name: str | None = None,
        slug: str | None = None,
        parent_id: int | None = None,
        kind: str | None = None,
        description: str | None = None,
    ) -> Area:
        """Update an existing area's fields. Returns the updated area."""
        area = self.get_by_id(area_id)
        if area is None:
            raise ValueError(f"Area with id {area_id} not found")

        if name is not None:
            validate_not_blank(name, "name")
            area.name = name.strip()

        if slug is not None:
            validate_not_blank(slug, "slug")
            new_slug = slug.strip().lower()
            old_slug = area.slug
            if new_slug != old_slug:
                if new_slug in self._by_slug and self._by_slug[new_slug] != area_id:
                    raise ValueError(f"Area with slug '{new_slug}' already exists")
                if old_slug in self._by_slug:
                    del self._by_slug[old_slug]
                self._by_slug[new_slug] = area_id
                area.slug = new_slug

        if parent_id is not None:
            validate_parent_id(parent_id, area.id)
            area.parent_id = parent_id

        if kind is not None:
            validate_enum_value(kind, VALID_AREA_KINDS, "kind")
            area.kind = kind

        if description is not None:
            area.description = description.strip()

        area.updated_at = self._now()
        return area

    # ── archive ───────────────────────────────────────────────────────

    def archive(self, area_id: int) -> Area:
        """Soft-archive an area."""
        area = self.get_by_id(area_id)
        if area is None:
            raise ValueError(f"Area with id {area_id} not found")
        area.archived_at = self._now()
        area.updated_at = self._now()
        return area

    # ── children ─────────────────────────────────────────────────────

    def list_children(self, parent_id: int) -> list[Area]:
        """List direct children of a given area."""
        return [a for a in self._store.values() if a.parent_id == parent_id]
