"""Shared test fixtures for second_brain tests.

The second_brain package lives at packages/memory/python/second_brain/.
This conftest adds the parent directory to sys.path so imports resolve
when running pytest from any working directory.
"""
import os
import sys
import pytest

_HERE = os.path.abspath(os.path.dirname(__file__))
_PACKAGE_PARENT = os.path.abspath(os.path.join(_HERE, ".."))
if _PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, _PACKAGE_PARENT)

from second_brain.repositories.area_repository import AreaRepository
from second_brain.repositories.entity_repository import EntityRepository
from second_brain.repositories.entity_alias_repository import EntityAliasRepository
from second_brain.repositories.memory_repository import MemoryRepository
from second_brain.repositories.memory_source_repository import MemorySourceRepository
from second_brain.repositories.memory_evidence_repository import MemoryEvidenceRepository
from second_brain.repositories.memory_candidate_repository import MemoryCandidateRepository
from second_brain.services.area_service import AreaService
from second_brain.services.entity_service import EntityService, EntityAliasService
from second_brain.services.memory_service import MemoryService
from second_brain.services.memory_candidate_service import MemoryCandidateService
from second_brain.seeding.area_seeder import AreaSeeder


@pytest.fixture
def area_repo() -> AreaRepository:
    return AreaRepository()


@pytest.fixture
def entity_repo() -> EntityRepository:
    return EntityRepository()


@pytest.fixture
def alias_repo() -> EntityAliasRepository:
    return EntityAliasRepository()


@pytest.fixture
def memory_repo() -> MemoryRepository:
    return MemoryRepository()


@pytest.fixture
def source_repo() -> MemorySourceRepository:
    return MemorySourceRepository()


@pytest.fixture
def evidence_repo() -> MemoryEvidenceRepository:
    return MemoryEvidenceRepository()


@pytest.fixture
def candidate_repo() -> MemoryCandidateRepository:
    return MemoryCandidateRepository()


@pytest.fixture
def area_service(area_repo: AreaRepository) -> AreaService:
    return AreaService(area_repo)


@pytest.fixture
def entity_service(entity_repo: EntityRepository, alias_repo: EntityAliasRepository) -> EntityService:
    return EntityService(entity_repo, alias_repo)


@pytest.fixture
def alias_service(alias_repo: EntityAliasRepository) -> EntityAliasService:
    return EntityAliasService(alias_repo)


@pytest.fixture
def memory_service(memory_repo: MemoryRepository) -> MemoryService:
    return MemoryService(memory_repo)


@pytest.fixture
def candidate_service(candidate_repo: MemoryCandidateRepository) -> MemoryCandidateService:
    return MemoryCandidateService(candidate_repo)


@pytest.fixture
def seeder(area_repo: AreaRepository) -> AreaSeeder:
    return AreaSeeder(area_repo)


@pytest.fixture
def default_areas(area_service: AreaService) -> list:
    """Create the 7 default top-level areas for tests that need them."""
    areas = []
    default_names = ["Projects", "Work", "Learning", "Personal", "People", "Goals", "Ideas"]
    for name in default_names:
        area = area_service.create(name=name)
        areas.append(area)
    return areas
