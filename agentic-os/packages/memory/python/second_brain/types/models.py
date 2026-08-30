"""Domain types for Phase 1 — dataclasses representing the structured memory model.

 claim_type is now MemoryClaimType | None (was empty-string "").
 None means "not provided"; when set it must be a valid MemoryClaimType value.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from second_brain.types.enums import MemoryClaimType


@dataclass
class Area:
    """A top-level or nested category bucket for memories.

    Areas are hierarchical: each area may optionally have a parent.
    The seven default areas (Projects, Work, Learning, Personal, People,
    Goals, Ideas) are seeded as top-level DEFAULT areas.
    """

    id: int | None = None
    name: str = ""
    slug: str = ""
    parent_id: int | None = None
    kind: str = "default"
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    # Internal tracking for repository use
    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class Entity:
    """A real-world thing that memories can be about: a person, a project,
    a technology, etc."""

    id: int | None = None
    type: str = ""
    canonical_name: str = ""
    description: str = ""
    area_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class EntityAlias:
    """An alternative name for an entity, with an estimated confidence."""

    id: int | None = None
    entity_id: int | None = None
    alias: str = ""
    normalized_alias: str = ""
    confidence: float | None = None
    source_id: int | None = None
    created_at: datetime | None = None

    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class Memory:
    """A structured memory — a fact, decision, preference, etc.

    Memories belong to an area (for organisational grouping) and optionally
    to an entity (for semantic anchoring). Confidence and importance are
    bounded 0..1. Superseded_by supports a soft chain without enforcing it.

    claim_type is optional: None means "not specified". When set it must be
    a valid MemoryClaimType value.
    """

    id: int | None = None
    type: str = ""
    area_id: int | None = None
    entity_id: int | None = None
    title: str = ""
    content: str = ""
    claim_type: MemoryClaimType | None = None
    status: str = "candidate"
    importance: float | None = None
    confidence_baseline: float | None = None
    confidence_final: float | None = None
    confidence_reason: str = ""
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    superseded_by: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class MemorySource:
    """A provenance source for memories: a conversation, a file, an email,
    a GitHub issue, etc."""

    id: int | None = None
    source_type: str = ""
    external_id: str | None = None
    title: str = ""
    uri: str | None = None
    occurred_at: datetime | None = None
    imported_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str | None = None

    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class MemoryEvidence:
    """A piece of evidence linking a source to a memory.

    supports:
      - True  → the evidence supports the memory
      - False → the evidence contradicts the memory
      - None  → the evidence is contextual only
    """

    id: int | None = None
    memory_id: int | None = None
    source_id: int | None = None
    evidence_type: str = ""
    excerpt: str = ""
    strength: float | None = None
    supports: bool | None = None
    created_at: datetime | None = None

    _exists_in_db: bool = field(default=False, repr=False)


@dataclass
class MemoryCandidate:
    """A proposed memory awaiting review.

    Candidates are separate from permanent memories. Their schema supports a
    later approval workflow; in Phase 1 they are created and stored but not
    automatically promoted.

    claim_type is optional: None means "not specified".
    """

    id: int | None = None
    proposed_type: str = ""
    proposed_area_id: int | None = None
    proposed_entity_id: int | None = None
    title: str = ""
    content: str = ""
    claim_type: MemoryClaimType | None = None
    suggested_importance: float | None = None
    confidence_baseline: float | None = None
    confidence_final: float | None = None
    confidence_reason: str = ""
    source_id: int | None = None
    detection_reason: str = ""
    review_status: str = "pending"
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None

    _exists_in_db: bool = field(default=False, repr=False)
