/**
 * UrbanPulse - PostgreSQL Data Provider
 *
 * Serves observations directly from PostgreSQL persistence.
 * Activated when DATA_PROVIDER=postgres and DATABASE_URL is defined.
 *
 * Rules:
 * - Uses the "pg" package (pg.Pool).
 * - Never calculates or adjusts priority or anomaly scores.
 * - Simple subtraction for metric differences.
 * - If the DB is unreachable, fails with a clear message.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import pg from 'pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '../../..');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

function maskDatabaseUrl(url) {
  if (!url) return '<unset>';
  try {
    const parsed = new URL(url);
    if (parsed.password) {
      parsed.password = '****';
    }
    return parsed.toString();
  } catch {
    return url.replace(/:([^:@]+)@/, ':****@');
  }
}

let poolInstance = null;

function getPool() {
  if (!poolInstance) {
    const dbUrl = process.env.DATABASE_URL;
    if (!dbUrl) {
      const msg = 'DATA_PROVIDER=postgres requires DATABASE_URL to be set.';
      console.error(`[PostgresProvider] ERROR: ${msg}`);
      throw new Error(msg);
    }

    poolInstance = new pg.Pool({
      connectionString: dbUrl,
      connectionTimeoutMillis: 5000,
      idleTimeoutMillis: 10000,
      max: 10
    });

    poolInstance.on('error', (err) => {
      console.error('[PostgresProvider] Unexpected database pool error:', err.message);
    });
  }
  return poolInstance;
}

export const postgresProvider = {
  getMode() {
    return 'postgres';
  },

  async verifyConnection() {
    const dbUrl = process.env.DATABASE_URL;
    if (!dbUrl) {
      const msg = 'DATA_PROVIDER=postgres is set but DATABASE_URL is missing. Please provide a valid DATABASE_URL.';
      console.error(`\n[UrbanPulse DB ERROR] ${msg}\n`);
      throw new Error(msg);
    }

    const pool = getPool();
    try {
      const client = await pool.connect();
      try {
        await client.query('SELECT 1');
      } finally {
        client.release();
      }
      return true;
    } catch (err) {
      const errorDetail = err.message || err.code || String(err);
      const masked = maskDatabaseUrl(dbUrl);
      const errorMsg = `Database unreachable: Unable to connect to PostgreSQL at ${masked}. (${errorDetail}). Please check that the PostgreSQL server is running and DATABASE_URL is correct.`;
      console.error(`\n=======================================================`);
      console.error(`[UrbanPulse DB FATAL] ${errorMsg}`);
      console.error(`=======================================================\n`);
      throw new Error(errorMsg);
    }
  },

  async query(text, params) {
    const pool = getPool();
    try {
      return await pool.query(text, params);
    } catch (err) {
      const errorDetail = err.message || err.code || String(err);
      console.error(`[PostgresProvider] Query execution failed: ${errorDetail}`);
      throw new Error(`PostgreSQL Query Error: ${errorDetail}`);
    }
  },

  async getMeta() {
    try {
      const res = await this.query("SELECT value FROM metadata WHERE key = 'meta' LIMIT 1;");
      if (res.rows.length > 0 && res.rows[0].value) {
        return res.rows[0].value;
      }
    } catch {
      // Fallback if metadata table is empty
    }

    // Default metadata for postgres provider
    let count = 0;
    try {
      const countRes = await this.query("SELECT COUNT(*) FROM urban_observations;");
      count = parseInt(countRes.rows[0].count, 10) || 0;
    } catch {
      count = 0;
    }

    return {
      source: "postgres",
      is_mock: false,
      warning: "Production PostgreSQL persistence active.",
      city: "Hyderabad",
      generated_at: new Date().toISOString(),
      imagery_years: [2020, 2023, 2026],
      analyzed_cells: count
    };
  },

  async isMockActive() {
    try {
      const meta = await this.getMeta();
      return meta.is_mock === true;
    } catch {
      return false;
    }
  },

  async getOverview() {
    const meta = await this.getMeta();
    let totalCells = meta.analyzed_cells || 0;
    let highCount = 0;
    let mediumCount = 0;

    try {
      const countRes = await this.query(`
        SELECT 
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE priority_level = 'HIGH') AS high,
          COUNT(*) FILTER (WHERE priority_level = 'MEDIUM') AS medium
        FROM urban_observations;
      `);
      if (countRes.rows.length > 0) {
        const row = countRes.rows[0];
        totalCells = parseInt(row.total, 10);
        highCount = parseInt(row.high, 10);
        mediumCount = parseInt(row.medium, 10);
      }
    } catch {
      // Keep defaults if table not yet populated
    }

    return {
      meta,
      regionName: "Hyderabad Metropolitan Growth Corridor",
      city: "Hyderabad",
      baselinePeriod: "2020–2023",
      currentPeriod: "2023–2026",
      totalMonitoredCells: totalCells,
      activeHotspotsCount: highCount + mediumCount,
      isMock: meta.is_mock === true,
      timestamp: new Date().toISOString()
    };
  },

  async getPipeline() {
    // Pipeline stage definitions
    return {
      title: "Evidence-Based Urban Change Pipeline",
      stages: [
        { id: "change", name: "Change", description: "Multi-temporal land cover change indicators" },
        { id: "historical_baseline", name: "Historical baseline", description: "Comparison against 2020-2023 trajectory" },
        { id: "local_baseline", name: "Local baseline", description: "Divergence from immediate 500m neighborhood" },
        { id: "anomaly", name: "Anomaly", description: "Statistical deviation and multi-temporal persistence" },
        { id: "evidence", name: "Evidence", description: "Verifiable observation audit trail and imagery" },
        { id: "priority", name: "Priority", description: "Explainable additive scoring factors" },
        { id: "investigation_list", name: "Investigation list", description: "Actionable ranked inspector deployment queue" }
      ]
    };
  },

  async getInvestigationList() {
    const meta = await this.getMeta();
    const res = await this.query(`
      SELECT * FROM urban_observations 
      ORDER BY priority_score DESC NULLS LAST, grid_id ASC;
    `);

    const records = res.rows.map(r => ({
      grid_id: r.grid_id,
      lat: r.lat,
      lng: r.lng,
      geometry: r.geometry,
      built_up_2020: r.built_up_2020,
      built_up_2023: r.built_up_2023,
      built_up_2026: r.built_up_2026,
      vegetation_2020: r.vegetation_2020,
      vegetation_2023: r.vegetation_2023,
      vegetation_2026: r.vegetation_2026,
      water_2020: r.water_2020,
      water_2023: r.water_2023,
      water_2026: r.water_2026,
      bare_land_2020: r.bare_land_2020,
      bare_land_2023: r.bare_land_2023,
      bare_land_2026: r.bare_land_2026,
      historical_change: r.historical_change,
      local_percentile: r.local_percentile,
      temporal_anomaly: r.temporal_anomaly,
      spatial_anomaly: r.spatial_anomaly,
      persistence: r.persistence,
      priority_score: r.priority_score,
      priority_level: r.priority_level,
      reasons: r.reasons,
      score_breakdown: r.score_breakdown
    }));

    return {
      meta,
      records
    };
  },

  async getGridCells(filters = {}) {
    let sql = 'SELECT * FROM urban_observations WHERE 1=1';
    const params = [];

    if (filters.priorityLevel) {
      params.push(filters.priorityLevel.toUpperCase());
      sql += ` AND priority_level = $${params.length}`;
    }

    sql += ' ORDER BY grid_id ASC;';
    const res = await this.query(sql, params);

    return res.rows.map(r => ({
      cellId: r.grid_id,
      grid_id: r.grid_id,
      hotspotId: r.grid_id,
      wardName: r.ward_name || `Zone ${r.grid_id}`,
      center: [r.lat, r.lng],
      geometry: r.geometry,
      priorityLevel: (r.priority_level || '').toLowerCase(),
      priority_level: r.priority_level,
      priorityScore: r.priority_score,
      priority_score: r.priority_score,
      score_breakdown: r.score_breakdown,
      anomalyStatus: (r.priority_level === 'HIGH' || r.priority_level === 'MEDIUM') ? 'flagged' : 'nominal'
    }));
  },

  async getHotspots(filters = {}) {
    let sql = 'SELECT * FROM hotspots WHERE 1=1';
    const params = [];

    if (filters.priorityLevel) {
      params.push(filters.priorityLevel.toUpperCase());
      sql += ` AND priority_level = $${params.length}`;
    }
    if (filters.category) {
      params.push(filters.category);
      sql += ` AND category = $${params.length}`;
    }
    if (filters.zone) {
      params.push(filters.zone.toLowerCase());
      sql += ` AND LOWER(zone) = $${params.length}`;
    }

    sql += ' ORDER BY rank ASC NULLS LAST, priority_score DESC NULLS LAST;';
    const res = await this.query(sql, params);

    return res.rows.map(r => ({
      id: r.id,
      rank: r.rank,
      cellId: r.cell_id || r.grid_id,
      grid_id: r.grid_id || r.id,
      wardName: r.ward_name,
      zone: r.zone,
      coordinates: r.coordinates || [r.lat, r.lng],
      category: r.category,
      categoryLabel: r.category_label,
      priorityScore: r.priority_score,
      priority_score: r.priority_score,
      priorityLevel: (r.priority_level || '').toLowerCase(),
      priority_level: r.priority_level,
      anomalyLevel: r.anomaly_level,
      persistence: r.persistence,
      changeSummary: r.change_summary,
      reasons: r.reasons,
      score_breakdown: r.score_breakdown,
      keyMetric: r.key_metric,
      baselineDeviation: r.baseline_deviation,
      neighborhoodPercentile: r.neighborhood_percentile,
      lastObservedDate: r.last_observed_date,
      recommendation: r.recommendation || 'Unusual spatial change detected. Field verification recommended.'
    }));
  },

  async getHotspotById(id) {
    if (!id) return null;
    const cleanId = String(id).trim();
    const res = await this.query(
      'SELECT * FROM hotspots WHERE LOWER(id) = LOWER($1) OR LOWER(grid_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    if (res.rows.length === 0) {
      // Fallback to urban_observations if not in hotspots table
      const obsRes = await this.query(
        'SELECT * FROM urban_observations WHERE LOWER(grid_id) = LOWER($1) LIMIT 1;',
        [cleanId]
      );
      if (obsRes.rows.length === 0) return null;
      const r = obsRes.rows[0];
      return {
        id: r.grid_id,
        grid_id: r.grid_id,
        cell_id: r.grid_id,
        wardName: r.ward_name,
        zone: r.zone,
        coordinates: [r.lat, r.lng],
        priority_score: r.priority_score,
        priorityScore: r.priority_score,
        priority_level: r.priority_level,
        priorityLevel: (r.priority_level || '').toLowerCase(),
        reasons: r.reasons,
        score_breakdown: r.score_breakdown,
        recommendation: 'Unusual spatial change detected. Field verification recommended.'
      };
    }

    const r = res.rows[0];
    return {
      id: r.id,
      rank: r.rank,
      cellId: r.cell_id || r.grid_id,
      grid_id: r.grid_id || r.id,
      wardName: r.ward_name,
      zone: r.zone,
      coordinates: r.coordinates || [r.lat, r.lng],
      category: r.category,
      categoryLabel: r.category_label,
      priorityScore: r.priority_score,
      priority_score: r.priority_score,
      priorityLevel: (r.priority_level || '').toLowerCase(),
      priority_level: r.priority_level,
      anomalyLevel: r.anomaly_level,
      persistence: r.persistence,
      changeSummary: r.change_summary,
      reasons: r.reasons,
      score_breakdown: r.score_breakdown,
      keyMetric: r.key_metric,
      baselineDeviation: r.baseline_deviation,
      neighborhoodPercentile: r.neighborhood_percentile,
      lastObservedDate: r.last_observed_date,
      recommendation: r.recommendation || 'Unusual spatial change detected. Field verification recommended.'
    };
  },

  async getEvidence(hotspotId) {
    if (!hotspotId) return null;
    const cleanId = String(hotspotId).trim();
    const res = await this.query(
      'SELECT * FROM evidence WHERE LOWER(grid_id) = LOWER($1) OR LOWER(hotspot_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    if (res.rows.length === 0) return null;
    const r = res.rows[0];
    return {
      hotspotId: r.hotspot_id || r.grid_id,
      cellId: r.cell_id || r.grid_id,
      grid_id: r.grid_id,
      wardName: r.ward_name,
      coordinates: r.coordinates || [r.lat, r.lng],
      category: r.category,
      categoryLabel: r.category_label,
      summary: r.summary,
      recommendation: r.recommendation || 'Unusual spatial change detected. Field verification recommended.',
      pipeline: r.pipeline
    };
  },

  async getStatistics() {
    const meta = await this.getMeta();
    const res = await this.query(`
      SELECT 
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE priority_level = 'HIGH') AS high,
        COUNT(*) FILTER (WHERE priority_level = 'MEDIUM') AS medium,
        COUNT(*) FILTER (WHERE priority_level = 'LOW') AS low
      FROM urban_observations;
    `);

    const row = res.rows[0] || {};
    const total = parseInt(row.total, 10) || 0;
    const high = parseInt(row.high, 10) || 0;
    const medium = parseInt(row.medium, 10) || 0;
    const low = parseInt(row.low, 10) || 0;
    const anomalous = high + medium;

    return {
      meta,
      analyzed_cells: total,
      anomalous,
      high,
      medium,
      low
    };
  },

  async getAreas() {
    const meta = await this.getMeta();
    const res = await this.query(`
      SELECT grid_id, lat, lng, geometry, priority_level, priority_score 
      FROM urban_observations 
      ORDER BY grid_id ASC;
    `);

    const areas = res.rows.map(r => ({
      grid_id: r.grid_id,
      lat: r.lat,
      lng: r.lng,
      geometry: r.geometry || null,
      priority_level: r.priority_level,
      priority_score: r.priority_score
    }));

    return {
      meta,
      areas
    };
  },

  async getHotspotDetail(gridId) {
    if (!gridId) return null;
    const cleanId = String(gridId).trim();
    const res = await this.query(
      'SELECT * FROM urban_observations WHERE LOWER(grid_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    if (res.rows.length === 0) return null;
    const rec = res.rows[0];
    const meta = await this.getMeta();

    const builtUpDiff = +(rec.built_up_2026 - rec.built_up_2020).toFixed(2);
    const vegetationDiff = +(rec.vegetation_2026 - rec.vegetation_2020).toFixed(2);
    const waterDiff = +(rec.water_2026 - rec.water_2020).toFixed(2);
    const bareLandDiff = rec.bare_land_2026 !== undefined && rec.bare_land_2020 !== undefined
      ? +(rec.bare_land_2026 - rec.bare_land_2020).toFixed(2)
      : undefined;

    return {
      meta,
      ...rec,
      differences: {
        built_up: builtUpDiff,
        vegetation: vegetationDiff,
        water: waterDiff,
        ...(bareLandDiff !== undefined ? { bare_land: bareLandDiff } : {})
      },
      built_up_diff: builtUpDiff,
      vegetation_diff: vegetationDiff,
      water_diff: waterDiff,
      ...(bareLandDiff !== undefined ? { bare_land_diff: bareLandDiff } : {})
    };
  },

  async getChange(gridId) {
    if (!gridId) return null;
    const cleanId = String(gridId).trim();
    const res = await this.query(
      'SELECT * FROM urban_observations WHERE LOWER(grid_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    if (res.rows.length === 0) return null;
    const rec = res.rows[0];
    const meta = await this.getMeta();

    const result = {
      meta,
      grid_id: rec.grid_id,
      built_up: [
        { year: 2020, value: rec.built_up_2020 },
        { year: 2023, value: rec.built_up_2023 },
        { year: 2026, value: rec.built_up_2026 }
      ],
      vegetation: [
        { year: 2020, value: rec.vegetation_2020 },
        { year: 2023, value: rec.vegetation_2023 },
        { year: 2026, value: rec.vegetation_2026 }
      ],
      water: [
        { year: 2020, value: rec.water_2020 },
        { year: 2023, value: rec.water_2023 },
        { year: 2026, value: rec.water_2026 }
      ]
    };

    if (rec.bare_land_2020 !== undefined && rec.bare_land_2020 !== null) {
      result.bare_land = [
        { year: 2020, value: rec.bare_land_2020 },
        { year: 2023, value: rec.bare_land_2023 },
        { year: 2026, value: rec.bare_land_2026 }
      ];
    }

    return result;
  },

  async getEvidenceDetail(gridId) {
    if (!gridId) return null;
    const cleanId = String(gridId).trim();

    // Query evidence table
    const evRes = await this.query(
      'SELECT * FROM evidence WHERE LOWER(grid_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    const meta = await this.getMeta();

    // Scan for existing images
    const cellImagesDir = path.join(IMAGES_DIR, cleanId);
    const existingImages = [];
    if (fs.existsSync(cellImagesDir)) {
      for (const year of [2020, 2023, 2026]) {
        const file = path.join(cellImagesDir, `${year}.svg`);
        if (fs.existsSync(file)) {
          existingImages.push(`/images/${cleanId}/${year}.svg`);
        }
      }
    }

    if (evRes.rows.length > 0) {
      const r = evRes.rows[0];
      const imageList = Array.isArray(r.image_urls) && r.image_urls.length > 0
        ? r.image_urls
        : existingImages;

      return {
        meta,
        grid_id: r.grid_id,
        observed_change: r.observed_change,
        historical_change: r.historical_change,
        local_percentile: r.local_percentile,
        temporal_anomaly: r.temporal_anomaly,
        spatial_anomaly: r.spatial_anomaly,
        persistence: r.persistence,
        priority_score: r.priority_score,
        priority_level: r.priority_level,
        images: imageList,
        image_urls: imageList
      };
    }

    // Fallback query from urban_observations
    const obsRes = await this.query(
      'SELECT * FROM urban_observations WHERE LOWER(grid_id) = LOWER($1) LIMIT 1;',
      [cleanId]
    );

    if (obsRes.rows.length === 0) return null;
    const rec = obsRes.rows[0];

    const observed_change = {
      built_up: +(rec.built_up_2026 - rec.built_up_2020).toFixed(2),
      vegetation: +(rec.vegetation_2026 - rec.vegetation_2020).toFixed(2),
      water: +(rec.water_2026 - rec.water_2020).toFixed(2),
      ...(rec.bare_land_2026 !== undefined ? { bare_land: +(rec.bare_land_2026 - rec.bare_land_2020).toFixed(2) } : {})
    };

    return {
      meta,
      grid_id: rec.grid_id,
      observed_change,
      historical_change: rec.historical_change,
      local_percentile: rec.local_percentile,
      temporal_anomaly: rec.temporal_anomaly,
      spatial_anomaly: rec.spatial_anomaly,
      persistence: rec.persistence,
      priority_score: rec.priority_score,
      priority_level: rec.priority_level,
      images: existingImages,
      image_urls: existingImages
    };
  }
};

export default postgresProvider;
