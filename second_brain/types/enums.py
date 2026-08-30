"""Shared enums for Phase 1 domain types."""

from enum import Enum


class AreaKind(str, Enum):
    """Area categorization."""

    DEFAULT = "default"
    CUSTOM = "custom"


class EntityType(str, Enum):
    """Supported entity types."""

    PERSON = "person"
    PROJECT = "project"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    TECHNOLOGY = "technology"
    TOPIC = "topic"
    PLACE = "place"
    DOCUMENT = "document"
    REPOSITORY = "repository"
    SYSTEM = "system"


class MemoryType(str, Enum):
    """Memory categorization."""

    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    KNOWLEDGE = "knowledge"
    PROCEDURE = "procedure"
    EPISODE = "episode"
    GOAL = "goal"
    OPEN_LOOP = "open_loop"
    HYPOTHESIS = "hypothesis"
    OBSERVATION = "observation"


class MemoryClaimType(str, Enum):
    """Type of claim a memory represents."""

    FACT = "fact"
    INFERENCE = "inference"
    OPINION = "opinion"
    DECISION = "decision"
    HYPOTHESIS = "hypothesis"


class MemoryStatus(str, Enum):
    """Lifecycle status of a memory."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class SourceType(str, Enum):
    """Source of a memory."""

    CONVERSATION = "conversation"
    AGENT_RUN = "agent_run"
    FILE = "file"
    EMAIL = "email"
    CALENDAR = "calendar"
    GITHUB = "github"
    WEB = "web"
    MANUAL = "manual"
    SYSTEM = "system"


class MemoryCandidateReviewStatus(str, Enum):
    """Review state for memory candidates."""

    PENDING = "pending"
    APPROVED = "approved"
    EDITED_AND_APPROVED = "edited_and_approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CONFLICT = "conflict"


# Convenience sets for validation
VALID_AREA_KINDS = {e.value for e in AreaKind}
VALID_ENTITY_TYPES = {e.value for e in EntityType}
VALID_MEMORY_TYPES = {e.value for e in MemoryType}
VALID_CLAIM_TYPES = {e.value for e in MemoryClaimType}
VALID_MEMORY_STATUSES = {e.value for e in MemoryStatus}
VALID_SOURCE_TYPES = {e.value for e in SourceType}
VALID_CANDIDATE_REVIEW_STATUSES = {e.value for e in MemoryCandidateReviewStatus}
