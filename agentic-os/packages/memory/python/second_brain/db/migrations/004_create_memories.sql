-- ============================================================================
-- 004_create_memories.sql
-- Phase 1: Memories table — structured memory records.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS memories (
    id                      BIGSERIAL PRIMARY KEY,
    type                    VARCHAR(50) NOT NULL,
    area_id                 BIGINT REFERENCES areas(id) ON DELETE SET NULL,
    entity_id               BIGINT REFERENCES entities(id) ON DELETE SET NULL,
    title                   VARCHAR(500),
    content                 TEXT NOT NULL DEFAULT '',
    claim_type              VARCHAR(50) NOT NULL DEFAULT 'fact',
    status                  VARCHAR(50) NOT NULL DEFAULT 'candidate',
    importance              DOUBLE PRECISION CHECK (importance IS NULL OR (importance >= 0 AND importance <= 1)),
    confidence_baseline     DOUBLE PRECISION CHECK (confidence_baseline IS NULL OR (confidence_baseline >= 0 AND confidence_baseline <= 1)),
    confidence_final        DOUBLE PRECISION CHECK (confidence_final IS NULL OR (confidence_final >= 0 AND confidence_final <= 1)),
    confidence_reason       TEXT DEFAULT '',
    valid_from              TIMESTAMPTZ,
    valid_until             TIMESTAMPTZ,
    superseded_by           BIGINT REFERENCES memories(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at             TIMESTAMPTZ
);

-- Index for area grouping
CREATE INDEX IF NOT EXISTS idx_memories_area_id ON memories(area_id);
-- Index for entity grouping
CREATE INDEX IF NOT EXISTS idx_memories_entity_id ON memories(entity_id);
-- Index for type filtering
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
-- Index for status filtering
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
-- Index for superseded chain traversal
CREATE INDEX IF NOT EXISTS idx_memories_superseded_by ON memories(superseded_by);
-- Index for listing active memories
CREATE INDEX IF NOT EXISTS idx_memories_archived_at ON memories(archived_at)
    WHERE archived_at IS NULL;
-- Index for title search (future full-text)
CREATE INDEX IF NOT EXISTS idx_memories_title ON memories(LOWER(title));

-- Check constraints for memory types, claim types, statuses
ALTER TABLE memories ADD CONSTRAINT memories_type_check
    CHECK (type IN (
        'fact', 'decision', 'preference', 'knowledge',
        'procedure', 'episode', 'goal', 'open_loop',
        'hypothesis', 'observation'
    ));

ALTER TABLE memories ADD CONSTRAINT memories_claim_type_check
    CHECK (claim_type IN (
        'fact', 'inference', 'opinion', 'decision', 'hypothesis'
    ));

ALTER TABLE memories ADD CONSTRAINT memories_status_check
    CHECK (status IN (
        'candidate', 'active', 'superseded', 'conflicted',
        'archived', 'rejected'
    ));

COMMENT ON TABLE memories IS 'Second Brain Phase 1 — Memories: structured memory records.';
COMMENT ON COLUMN memories.superseded_by IS 'Self-reference: id of memory that superseded this one (soft chain, not enforced)';
