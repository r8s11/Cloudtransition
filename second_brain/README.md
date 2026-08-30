# Second Brain — Phase 1: Structured Memory Foundation

Language: Python 3.14
Framework: none (plain Python with pydantic models)
Database: PostgreSQL (migrations provided); SQLite for in-test use
ORM: none — dataclasses + manual SQL
Test framework: pytest
"""

# Directory structure:
#
# second-brain/
# ├── __init__.py
# ├── types/
# │   ├── __init__.py
# │   ├── enums.py          # All Phase 1 enum values
# │   ├── models.py         # Dataclass models (Area, Entity, Memory, ...)
# │   └── validation.py     # Validation helpers
# ├── db/
# │   ├── __init__.py
# │   └── migrations/
# │       ├── 001_create_areas.sql
# │       ├── 002_create_entities.sql
# │       ├── 003_create_entity_aliases.sql
# │       ├── 004_create_memories.sql
# │       ├── 005_create_memory_sources.sql
# │       ├── 006_create_memory_evidence.sql
# │       └── 007_create_memory_candidates.sql
# ├── repositories/
# │   ├── __init__.py
# │   ├── area_repository.py
# │   ├── entity_repository.py
# │   ├── entity_alias_repository.py
# │   ├── memory_repository.py
# │   ├── memory_source_repository.py
# │   ├── memory_evidence_repository.py
# │   └── memory_candidate_repository.py
# ├── services/
# │   ├── __init__.py
# │   ├── area_service.py
# │   ├── entity_service.py
# │   ├── memory_service.py
# │   └── memory_candidate_service.py
# ├── seeding/
# │   ├── __init__.py
# │   └── area_seeder.py
# └── tests/
#     ├── __init__.py
#     ├── conftest.py
#     ├── test_areas.py
#     ├── test_entities.py
#     ├── test_memories.py
#     ├── test_sources_evidence.py
#     └── test_memory_candidates.py
