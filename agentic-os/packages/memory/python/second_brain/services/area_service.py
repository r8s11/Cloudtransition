"""Area service — validates input, normalizes fields, delegates to repository."""

from second_brain.repositories.area_repository import AreaRepository
from second_brain.types.enums import VALID_AREA_KINDS
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_parent_id,
)
from second_brain.types.models import Area


class AreaService:
    """Business-logic layer for Area operations.

    Phase 1 responsibilities:
    - validate input (non-blank names, valid kinds, non-self parent refs)
    - normalize obvious fields (trim whitespace, lowercase slugs)
    - compute a slug from a name when none is supplied
    - delegate persistence to the repository
    """

    def __init__(self, repo: AreaRepository) -> None:
        self._repo = repo

    def create(
        self,
        name: str,
        slug: str | None = None,
        parent_id: int | None = None,
        kind: str = "default",
        description: str = "",
    ) -> Area:
        """Create a new area after validation."""
        validate_not_blank(name, "name")
        if slug is not None:
            validate_not_blank(slug, "slug")
        validate_enum_value(kind, VALID_AREA_KINDS, "kind")
        validate_parent_id(parent_id)

        # Normalize
        normalized_name = name.strip()
        if slug is None:
            slug = self._slug_from_name(normalized_name)
        else:
            slug = slug.strip().lower()
        normalized_description = description.strip()

        return self._repo.create(
            name=normalized_name,
            slug=slug,
            parent_id=parent_id,
            kind=kind,
            description=normalized_description,
        )

    def get_by_id(self, area_id: int) -> Area | None:
        return self._repo.get_by_id(area_id)

    def get_by_slug(self, slug: str) -> Area | None:
        return self._repo.get_by_slug(slug)

    def list(self, include_archived: bool = False) -> list[Area]:
        return self._repo.list(include_archived=include_archived)

    def update(
        self,
        area_id: int,
        name: str | None = None,
        slug: str | None = None,
        parent_id: int | None = None,
        kind: str | None = None,
        description: str | None = None,
    ) -> Area:
        """Update an area after validation."""
        # Pre-validate before delegating
        if name is not None:
            validate_not_blank(name, "name")
        if slug is not None:
            validate_not_blank(slug, "slug")
        if kind is not None:
            validate_enum_value(kind, VALID_AREA_KINDS, "kind")
        if parent_id is not None:
            validate_parent_id(parent_id, area_id)

        return self._repo.update(
            area_id=area_id,
            name=name,
            slug=slug,
            parent_id=parent_id,
            kind=kind,
            description=description,
        )

    def archive(self, area_id: int) -> Area:
        return self._repo.archive(area_id)

    def list_children(self, parent_id: int) -> list[Area]:
        return self._repo.list_children(parent_id)

    # ── internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _slug_from_name(name: str) -> str:
        """Derive a URL-friendly slug from a human-readable name.

        Lowercase, replace spaces with hyphens, strip non-alphanumeric chars,
        collapse repeated hyphens.
        """
        lowered = name.lower().strip()
        slug = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in lowered)
        parts = slug.split("-")
        slug = "-".join(p for p in parts if p)
        return slug
