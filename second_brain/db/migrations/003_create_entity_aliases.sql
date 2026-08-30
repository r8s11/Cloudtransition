-- ============================================================================
-- 003_create_entity_aliases.sql
-- Phase 1: Entity aliases table — alternative names for entities.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_aliases (
    id                  BIGSERIAL PRIMARY KEY,
    entity_id           BIGINT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    alias               VARCHAR(500) NOT NULL,
    normalized_alias    VARCHAR(500) NOT NULL,
    confidence          DOUBLE PRECISION CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    source_id           BIGINT REFERENCES memory_sources(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for entity lookups
CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity_id ON entity_aliases(entity_id);
-- Index for normalized alias matching (future fuzzy/resolution use)
CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized ON entity_aliases(normalized_alias);
-- Index for source provenance
CREATE INDEX IF NOT EXISTS idx_entity_aliases_source_id ON entity_aliases(source_id);

COMMENT ON TABLE entity_aliases IS 'Second Brain Phase 1 — Entity aliases: alternative names for entities.';
COMMENT ON COLUMN entity_aliases.confidence IS 'Estimated confidence 0..1; NULL means unknown';
COMMENT ON COLUMN entity_aliases.normalized_alias IS 'Lowercased, trimmed, whitespace-collapsed alias for efficient matching';
