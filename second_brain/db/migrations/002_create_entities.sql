-- ============================================================================
-- 002_create_entities.sql
-- Phase 1: Entities table — real-world things memories can reference.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id                  BIGSERIAL PRIMARY KEY,
    type                VARCHAR(50) NOT NULL,
    canonical_name      VARCHAR(500) NOT NULL,
    description         TEXT DEFAULT '',
    area_id             BIGINT REFERENCES areas(id) ON DELETE SET NULL,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for canonical name lookups
CREATE INDEX IF NOT EXISTS idx_entities_canonical_name ON entities(LOWER(canonical_name));
-- Index for area grouping
CREATE INDEX IF NOT EXISTS idx_entities_area_id ON entities(area_id);
-- Index for type filtering
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);

-- Check constraint for entity types (initial set; can be extended)
ALTER TABLE entities ADD CONSTRAINT entities_type_check
    CHECK (type IN (
        'person', 'project', 'organization', 'product',
        'technology', 'topic', 'place', 'document',
        'repository', 'system'
    ));

COMMENT ON TABLE entities IS 'Second Brain Phase 1 — Entities: real-world things memories can reference.';
COMMENT ON COLUMN entities.type IS 'EntityType: person, project, organization, product, technology, topic, place, document, repository, system';
COMMENT ON COLUMN entities.metadata IS 'JSONB flexible structured data';
