"""Repository for MemoryCandidate persistence."""
from datetime import datetime, timezone

from second_brain.types.models import MemoryCandidate, MemoryClaimType
from second_brain.types.validation import (
    validate_enum_value,
    validate_not_blank,
    validate_confidence,
    validate_importance,
    validate_claim_type,
)
from second_brain.types.enums import (
    VALID_MEMORY_TYPES,
    VALID_CANDIDATE_REVIEW_STATUSES,
)


class MemoryCandidateRepository:
    """Persistence for MemoryCandidate entities.

    Candidates are proposals that may later be reviewed and promoted to
    permanent memories. In Phase 1 they are stored but not automatically
    approved or processed.
    """

    def __init__(self) -> None:
        self._store: dict[int, MemoryCandidate] = {}
        self._pending_order: list[int] = []
        self._next_id = 1

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ── create ────────────────────────────────────────────────────────

    def create(
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
        """Create a new memory candidate."""
        validate_enum_value(proposed_type, VALID_MEMORY_TYPES, "proposed_type")
        validate_claim_type(claim_type)
        validate_enum_value(review_status, VALID_CANDIDATE_REVIEW_STATUSES, "review_status")
        validate_confidence(confidence_baseline, "confidence_baseline")
        validate_confidence(confidence_final, "confidence_final")
        validate_importance(suggested_importance, "suggested_importance")

        if title:
            validate_not_blank(title, "title")

        candidate = MemoryCandidate(
            id=self._next_id,
            proposed_type=proposed_type,
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
            review_status=review_status,
            created_at=self._now(),
        )
        candidate._exists_in_db = True

        self._store[candidate.id] = candidate
        if review_status == "pending":
            self._pending_order.append(candidate.id)

        self._next_id += 1
        return candidate

    # ── get by id ─────────────────────────────────────────────────────

    def get_by_id(self, candidate_id: int) -> MemoryCandidate | None:
        if not isinstance(candidate_id, int) or candidate_id <= 0:
            return None
        return self._store.get(candidate_id)

    # ── list pending ──────────────────────────────────────────────────

    def list_pending(self) -> list[MemoryCandidate]:
        """Return candidates still in 'pending' review state, in creation order."""
        return [
            self._store[cid]
            for cid in self._pending_order
            if cid in self._store and self._store[cid].review_status == "pending"
        ]

    # ── list all ──────────────────────────────────────────────────────

    def list(self) -> list[MemoryCandidate]:
        return sorted(self._store.values(), key=lambda c: c.id)

    # ── update review status ──────────────────────────────────────────

    def update_review(
        self,
        candidate_id: int,
        review_status: str,
        reviewed_by: str | None = None,
    ) -> MemoryCandidate:
        """Mark a candidate as reviewed with a given status."""
        candidate = self.get_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"MemoryCandidate with id {candidate_id} not found")

        validate_enum_value(review_status, VALID_CANDIDATE_REVIEW_STATUSES, "review_status")

        candidate.review_status = review_status
        candidate.reviewed_at = self._now()
        candidate.reviewed_by = reviewed_by

        # Keep pending order accurate
        if candidate_id in self._pending_order:
            self._pending_order.remove(candidate_id)

        return candidate
