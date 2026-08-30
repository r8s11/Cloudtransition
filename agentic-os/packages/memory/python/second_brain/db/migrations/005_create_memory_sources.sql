-- ============================================================================
-- 005_create_memory_sources.sql
-- Phase 1: Memory sources table — provenance for memories.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS memory_sources (
    id                  BIGSERIAL PRIMARY KEY,
    source_type         VARCHAR(50) NOT NULL,
    external_id         VARCHAR(500),
    title               VARCHAR(500) NOT NULL DEFAULT '',
    uri                 VARCHAR(2000),
    occurred_at         TIMESTAMPTZ,
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata            JSONB DEFAULT '{}',
    content_hash        VARCHAR(128)
);

-- Index for type filtering
CREATE INDEX IF NOT EXISTS idx_memory_sources_source_type ON memory_sources(source_type);
-- Index for external_id lookups (when present)
CREATE INDEX IF NOT EXISTS idx_memory_sources_external_id ON memory_sources(external_id)
    WHERE external_id IS NOT NULL;
-- Index for URI lookups
CREATE INDEX IF NOT EXISTS idx_memory_sources_uri ON memory_sources(uri)
    WHERE uri IS NOT NULL;

-- Check constraint for source types
ALTER TABLE memory_sources ADD CONSTRAINT memory_sources_type_check
    CHECK (source_type IN (
        'conversation', 'agent_run', 'file', 'email',
        'calendar', 'github', 'web', 'manual', 'system'
    ));

COMMENT ON TABLE memory_sources IS 'Second Brain Phase 1 — Memory sources: provenance for memories.';
COMMENT ON COLUMN memory_sources.metadata IS 'JSONB flexible structured data';
