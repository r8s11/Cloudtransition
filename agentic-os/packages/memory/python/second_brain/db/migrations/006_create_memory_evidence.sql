-- ============================================================================
-- 006_create_memory_evidence.sql
-- Phase 1: Memory evidence table — links sources to memories with support info.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_evidence (
    id                  BIGSERIAL PRIMARY KEY,
    memory_id           BIGINT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    source_id           BIGINT NOT NULL REFERENCES memory_sources(id) ON DELETE CASCADE,
    evidence_type       VARCHAR(100) NOT NULL DEFAULT '',
    excerpt             TEXT DEFAULT '',
    strength            DOUBLE PRECISION CHECK (strength IS NULL OR (strength >= 0 AND strength <= 1)),
    supports            BOOLEAN,  -- TRUE = supports, FALSE = contradicts, NULL = contextual
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for memory lookups
CREATE INDEX IF NOT EXISTS idx_memory_evidence_memory_id ON memory_evidence(memory_id);
-- Index for source lookups
CREATE INDEX IF NOT EXISTS idx_memory_evidence_source_id ON memory_evidence(source_id);
-- Index for supports filtering
CREATE INDEX IF NOT EXISTS idx_memory_evidence_supports ON memory_evidence(supports)
    WHERE supports IS NOT NULL;

COMMENT ON TABLE memory_evidence IS 'Second Brain Phase 1 — Memory evidence: links sources to memories.';
COMMENT ON COLUMN memory_evidence.supports IS 'TRUE=supports, FALSE=contradicts, NULL=contextual only';
