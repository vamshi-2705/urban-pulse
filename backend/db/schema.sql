-- =============================================================================
-- UrbanPulse - PostgreSQL Database Schema
--
-- Decision-support tool for municipal authorities.
-- Schema supports:
--   - urban_observations: Comprehensive multi-temporal cell observations & metrics
--   - evidence: Detailed dossiers and 7-stage evidence pipelines
--   - hotspots: Prioritized, ranked field investigation targets
--   - metadata: System metadata and provenance information
--
-- Note on PostGIS:
--   PostGIS geometry column (geom) is conditionally added ONLY IF the postgis
--   extension is available in the PostgreSQL environment. Standard GeoJSON
--   geometry is always stored in the geometry JSONB column.
-- =============================================================================

-- 1. Optional PostGIS Extension
DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS postgis;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'PostGIS extension not available in this environment. Proceeding with standard GeoJSON columns.';
    END;
END $$;

-- 2. Metadata Table
CREATE TABLE IF NOT EXISTS metadata (
    key VARCHAR(64) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Urban Observations Table
-- Stores spatial grid cells and multi-temporal land cover metrics (built-up, veg, water, bare land)
CREATE TABLE IF NOT EXISTS urban_observations (
    grid_id VARCHAR(64) PRIMARY KEY,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    geometry JSONB,
    built_up_2020 DOUBLE PRECISION,
    built_up_2023 DOUBLE PRECISION,
    built_up_2026 DOUBLE PRECISION,
    vegetation_2020 DOUBLE PRECISION,
    vegetation_2023 DOUBLE PRECISION,
    vegetation_2026 DOUBLE PRECISION,
    water_2020 DOUBLE PRECISION,
    water_2023 DOUBLE PRECISION,
    water_2026 DOUBLE PRECISION,
    bare_land_2020 DOUBLE PRECISION,
    bare_land_2023 DOUBLE PRECISION,
    bare_land_2026 DOUBLE PRECISION,
    historical_change DOUBLE PRECISION,
    local_percentile DOUBLE PRECISION,
    temporal_anomaly DOUBLE PRECISION,
    spatial_anomaly DOUBLE PRECISION,
    persistence DOUBLE PRECISION,
    priority_score INTEGER,
    priority_level VARCHAR(32),
    reasons JSONB,
    score_breakdown JSONB,
    ward_name VARCHAR(255),
    zone VARCHAR(255),
    category VARCHAR(64),
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_urban_obs_priority_level ON urban_observations (priority_level);
CREATE INDEX IF NOT EXISTS idx_urban_obs_priority_score ON urban_observations (priority_score DESC);

-- 4. Evidence Table
-- Stores verifiable observation dossiers, pipeline audit trails, and image links
CREATE TABLE IF NOT EXISTS evidence (
    grid_id VARCHAR(64) PRIMARY KEY,
    hotspot_id VARCHAR(64),
    cell_id VARCHAR(64),
    ward_name VARCHAR(255),
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    coordinates JSONB,
    category VARCHAR(64),
    category_label VARCHAR(255),
    summary TEXT,
    recommendation TEXT,
    pipeline JSONB,
    observed_change JSONB,
    historical_change DOUBLE PRECISION,
    local_percentile DOUBLE PRECISION,
    temporal_anomaly DOUBLE PRECISION,
    spatial_anomaly DOUBLE PRECISION,
    persistence DOUBLE PRECISION,
    priority_score INTEGER,
    priority_level VARCHAR(32),
    image_urls JSONB,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_priority_level ON evidence (priority_level);

-- 5. Hotspots Table
-- Stores prioritized field investigation queue with rankings and deviations
CREATE TABLE IF NOT EXISTS hotspots (
    id VARCHAR(64) PRIMARY KEY,
    grid_id VARCHAR(64),
    cell_id VARCHAR(64),
    rank INTEGER,
    ward_name VARCHAR(255),
    zone VARCHAR(255),
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    coordinates JSONB,
    category VARCHAR(64),
    category_label VARCHAR(255),
    priority_score INTEGER,
    priority_level VARCHAR(32),
    anomaly_level VARCHAR(32),
    persistence VARCHAR(64),
    change_summary TEXT,
    reasons JSONB,
    score_breakdown JSONB,
    key_metric VARCHAR(255),
    baseline_deviation VARCHAR(255),
    neighborhood_percentile VARCHAR(255),
    last_observed_date VARCHAR(64),
    recommendation TEXT,
    geometry JSONB,
    raw_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hotspots_rank ON hotspots (rank);
CREATE INDEX IF NOT EXISTS idx_hotspots_priority_level ON hotspots (priority_level);
CREATE INDEX IF NOT EXISTS idx_hotspots_priority_score ON hotspots (priority_score DESC);

-- 6. Conditional PostGIS Geometry Columns
-- Only added if the PostGIS extension is installed and active
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        -- Add geom column to urban_observations if not present
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'urban_observations' AND column_name = 'geom'
        ) THEN
            ALTER TABLE urban_observations ADD COLUMN geom geometry(Polygon, 4326);
            CREATE INDEX IF NOT EXISTS idx_urban_obs_geom ON urban_observations USING GIST (geom);
            RAISE NOTICE 'Added PostGIS geometry column to urban_observations.';
        END IF;

        -- Add geom column to hotspots if not present
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'hotspots' AND column_name = 'geom'
        ) THEN
            ALTER TABLE hotspots ADD COLUMN geom geometry(Polygon, 4326);
            CREATE INDEX IF NOT EXISTS idx_hotspots_geom ON hotspots USING GIST (geom);
            RAISE NOTICE 'Added PostGIS geometry column to hotspots.';
        END IF;
    END IF;
END $$;
