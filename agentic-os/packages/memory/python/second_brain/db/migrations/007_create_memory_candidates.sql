-- ============================================================================
-- 007_create_memory_candidates.sql
-- Phase 1: Memory candidates table — proposed memories awaiting review.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_candidates (
    id                      BIGSERIAL PRIMARY KEY,
    proposed_type           VARCHAR(50) NOT NULL,
    proposed_area_id        BIGINT REFERENCES areas(id) ON DELETE SET NULL,
    proposed_entity_id      BIGINT REFERENCES entities(id) ON DELETE SET NULL,
    title                   VARCHAR(500),
    content                 TEXT NOT NULL DEFAULT '',
    claim_type              VARCHAR(50) NOT NULL DEFAULT 'fact',
    suggested_importance    DOUBLE PRECISION CHECK (suggested_importance IS NULL OR (suggested_importance >= 0 AND suggested_importance <= 1)),
    confidence_baseline     DOUBLE PRECISION CHECK (confidence_baseline IS NULL OR (confidence_baseline >= 0 AND confidence_baseline <= 1)),
    confidence_final        DOUBLE PRECISION CHECK (confidence_final IS NULL OR (confidence_final >= 0 AND confidence_final <= 1)),
    confidence_reason       TEXT DEFAULT '',
    source_id               BIGINT REFERENCES memory_sources(id) ON DELETE SET NULL,
    detection_reason        TEXT DEFAULT '',
    review_status           VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at             TIMESTAMPTZ,
    reviewed_by             VARCHAR(255)
);

-- Index for area grouping
CREATE INDEX IF NOT EXISTS idx_memory_candidates_area_id ON memory_candidates(proposed_area_id);
-- Index for entity grouping
CREATE INDEX IF NOT EXISTS idx_memory_candidates_entity_id ON memory_candidates(proposed_entity_id);
-- Index for review status filtering
CREATE INDEX IF NOT EXISTS idx_memory_candidates_review_status ON memory_candidates(review_status);
-- Index for pending candidates (fast listing)
CREATE INDEX IF NOT EXISTS idx_memory_candidates_pending ON memory_candidates(review_status)
    WHERE review_status = 'pending';
-- Index for source provenance
CREATE INDEX IF NOT EXISTS idx_memory_candidates_source_id ON memory_candidates(source_id);

-- Check constraints
ALTER TABLE memory_candidates ADD CONSTRAINT memory_candidates_type_check
    CHECK (proposed_type IN (
        'fact', 'decision', 'preference', 'knowledge',
        'procedure', 'episode', 'goal', 'open_loop',
        'hypothesis', 'observation'
    ));

ALTER TABLE memory_candidates ADD CONSTRAINT memory_candidates_claim_type_check
    CHECK (claim_type IN (
        'fact', 'inference', 'opinion', 'decision', 'hypothesis'
    ));

ALTER TABLE memory_candidates ADD CONSTRAINT memory_candidates_review_status_check
    CHECK (review_status IN (
        'pending', 'approved', 'edited_and_approved', 'rejected',
        'deferred', 'conflict'
    ));

COMMENT ON TABLE memory_candidates IS 'Second Brain Phase 1 — Memory candidates: proposed memories awaiting review.';
COMMENT ON COLUMN memory_candidates.review_status IS 'MemoryCandidateReviewStatus: pending, approved, edited_and_approved, rejected, deferred, conflict';
