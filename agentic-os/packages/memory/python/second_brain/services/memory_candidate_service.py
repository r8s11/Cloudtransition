"""MemoryCandidate service — validates input, delegates to repository.

Phase 1: candidates are stored and listed but not automatically approved.
"""
from second_brain.repositories.memory_candidate_repository import (
    MemoryCandidateRepository,
)
from second_brain.types.enums import (
    VALID_MEMORY_TYPES,
    VALID_CANDIDATE_REVIEW_STATUSES,
)
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
    validate_importance,
    validate_claim_type,
)
from second_brain.types.models import MemoryCandidate, MemoryClaimType


class MemoryCandidateService:
    """Business-logic layer for MemoryCandidate operations.

    Phase 1 responsibilities:
    - validate input
    - normalize obvious fields (trim whitespace)
    - delegate persistence to the repository
    - do NOT implement approval/automatic promotion behavior
    """

    def __init__(self, repo: MemoryCandidateRepository) -> None:
        self._repo = repo

    def create_candidate(
        self,
        proposed_type: str,
        proposed_area_id: int | None = None,
        proposed_entity_id: int | None = None,
        title: str = "",
        content: str = "",
        claim_type: MemoryClaimType | None = None,
        suggested_importance: float | None = None,
        confidence_baseline: float | None = None,
        confidence_final: float | None = None,
        confidence_reason: str = "",
        source_id: int | None = None,
        detection_reason: str = "",
        review_status: str = "pending",
    ) -> MemoryCandidate:
        """Create a new memory candidate after validation and normalization.

        claim_type is optional: None means "not specified".
        """
        validate_enum_value(proposed_type, VALID_MEMORY_TYPES, "proposed_type")
        validate_claim_type(claim_type)
        validate_enum_value(review_status, VALID_CANDIDATE_REVIEW_STATUSES, "review_status")
        validate_confidence(confidence_baseline, "confidence_baseline")
        validate_confidence(confidence_final, "confidence_final")
        validate_importance(suggested_importance)
        if title:
            validate_not_blank(title, "title")

        return self._repo.create(
            proposed_type=proposed_type.strip(),
            proposed_area_id=proposed_area_id,
            proposed_entity_id=proposed_entity_id,
            title=title.strip(),
            content=content.strip(),
            claim_type=claim_type,
            suggested_importance=suggested_importance,
            confidence_baseline=confidence_baseline,
            confidence_final=confidence_final,
            confidence_reason=confidence_reason.strip(),
            source_id=source_id,
            detection_reason=detection_reason.strip(),
            review_status=review_status.strip(),
        )

    def get_candidate(self, candidate_id: int) -> MemoryCandidate | None:
        return self._repo.get_by_id(candidate_id)

    def list_pending(self) -> list[MemoryCandidate]:
        return self._repo.list_pending()

    def list_all(self) -> list[MemoryCandidate]:
        return self._repo.list()

    def update_review(
        self,
        candidate_id: int,
        review_status: str,
        reviewed_by: str | None = None,
    ) -> MemoryCandidate:
        """Update the review status of a candidate after validation."""
        validate_enum_value(review_status, VALID_CANDIDATE_REVIEW_STATUSES, "review_status")
        return self._repo.update_review(
            candidate_id=candidate_id,
            review_status=review_status,
            reviewed_by=reviewed_by,
        )
