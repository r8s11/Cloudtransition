"""Default area seeder — idempotent creation of the seven top-level areas."""

from second_brain.repositories.area_repository import AreaRepository
from second_brain.types.enums import AreaKind
from second_brain.types.validation import validate_enum_value


DEFAULT_AREA_DEFS = [
    ("Projects", "projects"),
    ("Work", "work"),
    ("Learning", "learning"),
    ("Personal", "personal"),
    ("People", "people"),
    ("Goals", "goals"),
    ("Ideas", "ideas"),
]


class AreaSeeder:
    """Idempotent seeder for the seven default top-level areas.

    Safe to run multiple times: skips areas whose slug already exists.
    """

    def __init__(self, repo: AreaRepository) -> None:
        self._repo = repo

    def seed_defaults(self) -> list[str]:
        """Ensure all default areas exist. Returns names of newly created areas."""
        created: list[str] = []
        for name, slug in DEFAULT_AREA_DEFS:
            existing = self._repo.get_by_slug(slug)
            if existing is None:
                try:
                    area = self._repo.create(
                        name=name,
                        slug=slug,
                        kind=AreaKind.DEFAULT.value,
                        description="",
                    )
                    created.append(area.name)
                except ValueError:
                    # If another thread/process created it between check and insert,
                    # just skip (idempotency without locking).
                    existing = self._repo.get_by_slug(slug)
                    if existing is not None:
                        continue
                    raise
        return created

    def ensure_area_exists(self, name: str, slug: str, kind: str = "default") -> bool:
        """Ensure a single named area exists; create if missing.

        Returns True if a new area was created, False if it already existed.
        """
        validate_enum_value(kind, {e.value for e in AreaKind}, "kind")
        existing = self._repo.get_by_slug(slug)
        if existing is not None:
            return False
        self._repo.create(name=name, slug=slug, kind=kind, description="")
        return True
