-- ============================================================================
-- 001_create_areas.sql
-- Phase 1: Areas table — top-level and nested categories for memories.
-- Review required before applying to production.
-- ============================================================================

CREATE TABLE IF NOT EXISTS areas (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL UNIQUE,
    parent_id       BIGINT REFERENCES areas(id) ON DELETE SET NULL,
    kind            VARCHAR(50) NOT NULL DEFAULT 'default',
    description     TEXT DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);

-- Index for slug lookups
CREATE INDEX IF NOT EXISTS idx_areas_slug ON areas(slug);
-- Index for parent hierarchy traversal
CREATE INDEX IF NOT EXISTS idx_areas_parent_id ON areas(parent_id);
-- Index for listing active areas
CREATE INDEX IF NOT EXISTS idx_areas_archived_at ON areas(archived_at)
    WHERE archived_at IS NULL;

-- Comment for documentation
COMMENT ON TABLE areas IS 'Second Brain Phase 1 — Areas: top-level and nested categories for memories.';
COMMENT ON COLUMN areas.kind IS 'AreaKind: default or custom';
COMMENT ON COLUMN areas.parent_id IS 'Self-referencing FK for nested areas; NULL for top-level';
COMMENT ON COLUMN areas.archived_at IS 'Soft-delete timestamp; NULL means active';
