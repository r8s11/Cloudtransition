"""Tests for MemoryCandidate creation, review states, and validation."""

from second_brain.types.enums import MemoryCandidateReviewStatus


class TestMemoryCandidateCreation:
    """Create candidate."""

    def test_create_pending_candidate(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="The sky is blue",
            content="Based on observation, the sky appears blue during the day.",
            claim_type="fact",
        )
        assert candidate.id is not None
        assert candidate.proposed_type == "fact"
        assert candidate.title == "The sky is blue"
        assert candidate.content == "Based on observation, the sky appears blue during the day."
        assert candidate.claim_type == "fact"
        assert candidate.suggested_importance is None
        assert candidate.confidence_baseline is None
        assert candidate.review_status == "pending"
        assert candidate.reviewed_at is None
        assert candidate.reviewed_by is None

    def test_create_candidate_with_all_fields(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="decision",
            proposed_area_id=1,
            proposed_entity_id=2,
            title="Choose React for UI",
            content="React was selected after comparing with Vue and Svelte.",
            claim_type="decision",
            suggested_importance=0.85,
            confidence_baseline=0.7,
            confidence_final=0.8,
            confidence_reason="Team evaluation, community support",
            source_id=1,
            detection_reason="From team conversation on Monday",
            review_status="pending",
        )
        assert candidate.proposed_type == "decision"
        assert candidate.proposed_area_id == 1
        assert candidate.proposed_entity_id == 2
        assert candidate.claim_type == "decision"
        assert candidate.suggested_importance == 0.85
        assert candidate.confidence_baseline == 0.7
        assert candidate.confidence_final == 0.8
        assert candidate.source_id == 1
        assert candidate.detection_reason == "From team conversation on Monday"
        assert candidate.review_status == "pending"


class TestCandidateReviewState:
    """Default/pending review state, nullable review metadata."""

    def test_default_status_is_pending(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Default status test",
        )
        assert candidate.review_status == "pending"

    def test_reviewed_at_null_when_pending(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Pending review",
        )
        assert candidate.reviewed_at is None
        assert candidate.reviewed_by is None

    def test_approved_candidate(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Approved fact",
        )
        updated = candidate_service.update_review(
            candidate.id, review_status="approved", reviewed_by="reviewer1"
        )
        assert updated.review_status == "approved"
        assert updated.reviewed_at is not None
        assert updated.reviewed_at.tzinfo is not None
        assert updated.reviewed_by == "reviewer1"

    def test_edited_and_approved(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Edited fact",
        )
        updated = candidate_service.update_review(
            candidate.id,
            review_status="edited_and_approved",
            reviewed_by="reviewer2",
        )
        assert updated.review_status == "edited_and_approved"
        assert updated.reviewed_by == "reviewer2"

    def test_rejected_candidate(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Rejected fact",
        )
        updated = candidate_service.update_review(
            candidate.id, review_status="rejected", reviewed_by="admin"
        )
        assert updated.review_status == "rejected"

    def test_deferred_candidate(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="hypothesis",
            title="Deferred hypothesis",
        )
        updated = candidate_service.update_review(
            candidate.id, review_status="deferred", reviewed_by="lead"
        )
        assert updated.review_status == "deferred"

    def test_conflict_candidate(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact",
            title="Conflicted fact",
        )
        updated = candidate_service.update_review(
            candidate.id, review_status="conflict", reviewed_by="arbiter"
        )
        assert updated.review_status == "conflict"


class TestCandidateValidation:
    """Invalid review status rejected."""

    def test_reject_invalid_review_status(self, candidate_service):
        try:
            candidate_service.create_candidate(
                proposed_type="fact",
                title="Bad status",
                review_status="invalid_status",
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_invalid_proposed_type(self, candidate_service):
        try:
            candidate_service.create_candidate(
                proposed_type="invalid_type",
                title="Test",
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_invalid_claim_type(self, candidate_service):
        try:
            candidate_service.create_candidate(
                proposed_type="fact",
                title="Test",
                claim_type="invalid_claim",
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)

    def test_reject_confidence_above_one(self, candidate_service):
        try:
            candidate_service.create_candidate(
                proposed_type="fact",
                title="Bad conf",
                confidence_baseline=1.5,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_importance_above_one(self, candidate_service):
        try:
            candidate_service.create_candidate(
                proposed_type="fact",
                title="Bad importance",
                suggested_importance=1.2,
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "between 0 and 1" in str(e)

    def test_reject_invalid_status_in_update_review(self, candidate_service):
        candidate = candidate_service.create_candidate(
            proposed_type="fact", title="Status update test"
        )
        try:
            candidate_service.update_review(
                candidate.id, review_status="invalid_status"
            )
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be one of" in str(e)


class TestCandidateListing:
    """List pending candidates."""

    def test_list_pending_returns_only_pending(self, candidate_service):
        c1 = candidate_service.create_candidate(
            proposed_type="fact", title="Pending 1"
        )
        c2 = candidate_service.create_candidate(
            proposed_type="fact", title="Pending 2"
        )
        c3 = candidate_service.create_candidate(
            proposed_type="fact", title="To be approved"
        )
        candidate_service.update_review(c3.id, review_status="approved")

        pending = candidate_service.list_pending()
        assert len(pending) == 2
        assert {c.id for c in pending} == {c1.id, c2.id}

    def test_pending_list_empty_when_all_reviewed(self, candidate_service):
        c1 = candidate_service.create_candidate(
            proposed_type="fact", title="Will be approved"
        )
        candidate_service.update_review(c1.id, review_status="approved")
        pending = candidate_service.list_pending()
        assert len(pending) == 0

    def test_list_all_candidates(self, candidate_service):
        c1 = candidate_service.create_candidate(
            proposed_type="fact", title="All 1"
        )
        c2 = candidate_service.create_candidate(
            proposed_type="fact", title="All 2"
        )
        all_candidates = candidate_service.list_all()
        assert len(all_candidates) == 2
