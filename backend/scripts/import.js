/**
 * UrbanPulse - Intelligence JSON Importer
 *
 * Loads intelligence data into PostgreSQL idempotently.
 * Storing values exactly as given without any recalculations.
 *
 * Usage:
 *   DATABASE_URL="postgresql://user:pass@localhost:5432/urbanpulse" node backend/scripts/import.js [file_path]
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import pg from 'pg';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '../..');

// Load .env from backend or root
dotenv.config({ path: path.join(ROOT_DIR, 'backend', '.env') });
dotenv.config({ path: path.join(ROOT_DIR, '.env') });

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

async function runImport() {
  const dbUrl = process.env.DATABASE_URL;
  if (!dbUrl) {
    console.error('\n[UrbanPulse Importer] ERROR: DATABASE_URL environment variable is not defined.');
    console.error('Please specify DATABASE_URL to connect to PostgreSQL.');
    console.error('Example: DATABASE_URL="postgresql://postgres:postgres@localhost:5432/urbanpulse" node backend/scripts/import.js\n');
    process.exit(1);
  }

  // Determine input file
  const defaultPath = path.join(ROOT_DIR, 'data', 'mock', 'investigation_list.json');
  const inputArg = process.argv[2] || process.env.IMPORT_FILE || defaultPath;
  const resolvedInputPath = path.isAbsolute(inputArg) ? inputArg : path.resolve(process.cwd(), inputArg);

  if (!fs.existsSync(resolvedInputPath)) {
    console.error(`\n[UrbanPulse Importer] ERROR: Input file not found: ${resolvedInputPath}\n`);
    process.exit(1);
  }

  console.log(`[UrbanPulse Importer] Connecting to PostgreSQL at ${maskDatabaseUrl(dbUrl)}...`);

  const client = new pg.Client({
    connectionString: dbUrl,
    connectionTimeoutMillis: 5000
  });

  try {
    await client.connect();
  } catch (err) {
    const errorDetails = err.message || err.code || String(err);
    console.error(`\n[UrbanPulse Importer] ERROR: Could not connect to PostgreSQL database.`);
    console.error(`Target: ${maskDatabaseUrl(dbUrl)}`);
    console.error(`Details: ${errorDetails}`);
    console.error(`Please verify that PostgreSQL is running and DATABASE_URL is accessible.\n`);
    process.exit(1);
  }

  try {
    console.log('[UrbanPulse Importer] Initializing database schema from backend/db/schema.sql...');
    const schemaSqlPath = path.join(__dirname, '../db/schema.sql');
    if (fs.existsSync(schemaSqlPath)) {
      const schemaSql = fs.readFileSync(schemaSqlPath, 'utf-8');
      await client.query(schemaSql);
      console.log('[UrbanPulse Importer] Schema verified/updated successfully.');
    }

    // Check for PostGIS column in urban_observations
    const postgisCheck = await client.query(`
      SELECT 1 FROM information_schema.columns 
      WHERE table_name = 'urban_observations' AND column_name = 'geom'
    `);
    const hasPostgis = postgisCheck.rowCount > 0;
    if (hasPostgis) {
      console.log('[UrbanPulse Importer] PostGIS geometry column detected. Spatial indexing active.');
    } else {
      console.log('[UrbanPulse Importer] PostGIS not detected; using standard GeoJSON JSONB persistence.');
    }

    // Read and parse input data
    console.log(`[UrbanPulse Importer] Reading input JSON from: ${resolvedInputPath}`);
    const rawContent = fs.readFileSync(resolvedInputPath, 'utf-8');
    const inputData = JSON.parse(rawContent);

    let meta = inputData.meta || null;
    let records = Array.isArray(inputData) ? inputData : (inputData.records || []);

    if (!records.length) {
      console.warn('[UrbanPulse Importer] Warning: No records found in input file.');
    }

    await client.query('BEGIN');

    // 1. Store metadata
    if (meta) {
      await client.query(`
        INSERT INTO metadata (key, value, updated_at)
        VALUES ('meta', $1, NOW())
        ON CONFLICT (key) DO UPDATE SET
          value = EXCLUDED.value,
          updated_at = NOW();
      `, [JSON.stringify(meta)]);
    }

    // 2. Load urban_observations idempotently
    console.log(`[UrbanPulse Importer] Inserting/updating ${records.length} records into urban_observations...`);
    let obsCount = 0;
    for (const rec of records) {
      const gridId = rec.grid_id || rec.cellId || rec.id;
      if (!gridId) continue;

      const lat = rec.lat !== undefined ? rec.lat : (rec.center ? rec.center[0] : (rec.coordinates ? rec.coordinates[0] : 0));
      const lng = rec.lng !== undefined ? rec.lng : (rec.center ? rec.center[1] : (rec.coordinates ? rec.coordinates[1] : 0));

      await client.query(`
        INSERT INTO urban_observations (
          grid_id, lat, lng, geometry,
          built_up_2020, built_up_2023, built_up_2026,
          vegetation_2020, vegetation_2023, vegetation_2026,
          water_2020, water_2023, water_2026,
          bare_land_2020, bare_land_2023, bare_land_2026,
          historical_change, local_percentile, temporal_anomaly, spatial_anomaly, persistence,
          priority_score, priority_level, reasons, score_breakdown,
          ward_name, zone, category, raw_data, updated_at
        ) VALUES (
          $1, $2, $3, $4,
          $5, $6, $7,
          $8, $9, $10,
          $11, $12, $13,
          $14, $15, $16,
          $17, $18, $19, $20, $21,
          $22, $23, $24, $25,
          $26, $27, $28, $29, NOW()
        )
        ON CONFLICT (grid_id) DO UPDATE SET
          lat = EXCLUDED.lat,
          lng = EXCLUDED.lng,
          geometry = EXCLUDED.geometry,
          built_up_2020 = EXCLUDED.built_up_2020,
          built_up_2023 = EXCLUDED.built_up_2023,
          built_up_2026 = EXCLUDED.built_up_2026,
          vegetation_2020 = EXCLUDED.vegetation_2020,
          vegetation_2023 = EXCLUDED.vegetation_2023,
          vegetation_2026 = EXCLUDED.vegetation_2026,
          water_2020 = EXCLUDED.water_2020,
          water_2023 = EXCLUDED.water_2023,
          water_2026 = EXCLUDED.water_2026,
          bare_land_2020 = EXCLUDED.bare_land_2020,
          bare_land_2023 = EXCLUDED.bare_land_2023,
          bare_land_2026 = EXCLUDED.bare_land_2026,
          historical_change = EXCLUDED.historical_change,
          local_percentile = EXCLUDED.local_percentile,
          temporal_anomaly = EXCLUDED.temporal_anomaly,
          spatial_anomaly = EXCLUDED.spatial_anomaly,
          persistence = EXCLUDED.persistence,
          priority_score = EXCLUDED.priority_score,
          priority_level = EXCLUDED.priority_level,
          reasons = EXCLUDED.reasons,
          score_breakdown = EXCLUDED.score_breakdown,
          ward_name = EXCLUDED.ward_name,
          zone = EXCLUDED.zone,
          category = EXCLUDED.category,
          raw_data = EXCLUDED.raw_data,
          updated_at = NOW();
      `, [
        gridId,
        lat,
        lng,
        rec.geometry ? JSON.stringify(rec.geometry) : null,
        rec.built_up_2020 ?? null,
        rec.built_up_2023 ?? null,
        rec.built_up_2026 ?? null,
        rec.vegetation_2020 ?? null,
        rec.vegetation_2023 ?? null,
        rec.vegetation_2026 ?? null,
        rec.water_2020 ?? null,
        rec.water_2023 ?? null,
        rec.water_2026 ?? null,
        rec.bare_land_2020 ?? null,
        rec.bare_land_2023 ?? null,
        rec.bare_land_2026 ?? null,
        rec.historical_change ?? null,
        rec.local_percentile ?? null,
        rec.temporal_anomaly ?? null,
        rec.spatial_anomaly ?? null,
        rec.persistence ?? null,
        rec.priority_score ?? rec.priorityScore ?? null,
        rec.priority_level ?? (rec.priorityLevel ? rec.priorityLevel.toUpperCase() : null),
        rec.reasons ? JSON.stringify(rec.reasons) : JSON.stringify([]),
        rec.score_breakdown ? JSON.stringify(rec.score_breakdown) : null,
        rec.ward_name || rec.wardName || null,
        rec.zone || null,
        rec.category || null,
        JSON.stringify(rec)
      ]);

      if (hasPostgis && rec.geometry) {
        await client.query(`
          UPDATE urban_observations 
          SET geom = ST_SetSRID(ST_GeomFromGeoJSON($1), 4326) 
          WHERE grid_id = $2;
        `, [JSON.stringify(rec.geometry), gridId]);
      }

      obsCount++;
    }

    // 3. Load hotspots table
    console.log('[UrbanPulse Importer] Loading hotspots table...');
    const inputDir = path.dirname(resolvedInputPath);
    const companionHotspotsPath = path.join(inputDir, 'hotspots.json');
    let hotspotsList = [];

    if (fs.existsSync(companionHotspotsPath)) {
      try {
        hotspotsList = JSON.parse(fs.readFileSync(companionHotspotsPath, 'utf-8'));
      } catch (e) {
        console.warn(`[UrbanPulse Importer] Could not parse companion hotspots.json: ${e.message}`);
      }
    }

    // If no companion hotspots file, derive from high/medium records
    if (!hotspotsList.length) {
      hotspotsList = records
        .filter(r => (r.priority_level === 'HIGH' || r.priority_level === 'MEDIUM' || (r.priority_score || 0) >= 40))
        .sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0))
        .map((r, idx) => ({
          id: r.grid_id,
          grid_id: r.grid_id,
          cell_id: r.grid_id,
          rank: idx + 1,
          ward_name: r.ward_name || r.wardName || `Zone ${r.grid_id}`,
          zone: r.zone || 'Hyderabad Urban',
          lat: r.lat,
          lng: r.lng,
          coordinates: [r.lat, r.lng],
          category: r.category || 'built_up_expansion',
          category_label: r.categoryLabel || 'Built-up expansion',
          priority_score: r.priority_score,
          priority_level: r.priority_level,
          anomaly_level: r.priority_level.toLowerCase(),
          persistence: r.persistence ? 'persistent' : 'intermittent',
          change_summary: (r.reasons && r.reasons[0]) || 'Unusual land cover change detected',
          reasons: r.reasons || [],
          score_breakdown: r.score_breakdown || {},
          key_metric: `+${(r.built_up_2026 - r.built_up_2020).toFixed(1)}% built-up`,
          baseline_deviation: `+${r.historical_change || 2}x historical trend`,
          neighborhood_percentile: `${r.local_percentile || 90}th percentile`,
          last_observed_date: '2026-03-15',
          recommendation: 'Unusual spatial change detected. Field verification recommended.',
          geometry: r.geometry || null,
          raw_data: r
        }));
    }

    let hotspotCount = 0;
    for (const h of hotspotsList) {
      const id = h.id || h.grid_id || h.cellId;
      if (!id) continue;

      const lat = h.lat !== undefined ? h.lat : (h.coordinates ? h.coordinates[0] : (h.center ? h.center[0] : null));
      const lng = h.lng !== undefined ? h.lng : (h.coordinates ? h.coordinates[1] : (h.center ? h.center[1] : null));

      await client.query(`
        INSERT INTO hotspots (
          id, grid_id, cell_id, rank, ward_name, zone,
          lat, lng, coordinates, category, category_label,
          priority_score, priority_level, anomaly_level, persistence,
          change_summary, reasons, score_breakdown,
          key_metric, baseline_deviation, neighborhood_percentile,
          last_observed_date, recommendation, geometry, raw_data, updated_at
        ) VALUES (
          $1, $2, $3, $4, $5, $6,
          $7, $8, $9, $10, $11,
          $12, $13, $14, $15,
          $16, $17, $18,
          $19, $20, $21,
          $22, $23, $24, $25, NOW()
        )
        ON CONFLICT (id) DO UPDATE SET
          grid_id = EXCLUDED.grid_id,
          cell_id = EXCLUDED.cell_id,
          rank = EXCLUDED.rank,
          ward_name = EXCLUDED.ward_name,
          zone = EXCLUDED.zone,
          lat = EXCLUDED.lat,
          lng = EXCLUDED.lng,
          coordinates = EXCLUDED.coordinates,
          category = EXCLUDED.category,
          category_label = EXCLUDED.category_label,
          priority_score = EXCLUDED.priority_score,
          priority_level = EXCLUDED.priority_level,
          anomaly_level = EXCLUDED.anomaly_level,
          persistence = EXCLUDED.persistence,
          change_summary = EXCLUDED.change_summary,
          reasons = EXCLUDED.reasons,
          score_breakdown = EXCLUDED.score_breakdown,
          key_metric = EXCLUDED.key_metric,
          baseline_deviation = EXCLUDED.baseline_deviation,
          neighborhood_percentile = EXCLUDED.neighborhood_percentile,
          last_observed_date = EXCLUDED.last_observed_date,
          recommendation = EXCLUDED.recommendation,
          geometry = EXCLUDED.geometry,
          raw_data = EXCLUDED.raw_data,
          updated_at = NOW();
      `, [
        id,
        h.grid_id || id,
        h.cell_id || h.cellId || id,
        h.rank || null,
        h.ward_name || h.wardName || null,
        h.zone || null,
        lat,
        lng,
        h.coordinates ? JSON.stringify(h.coordinates) : (lat !== null ? JSON.stringify([lat, lng]) : null),
        h.category || null,
        h.category_label || h.categoryLabel || null,
        h.priority_score ?? h.priorityScore ?? null,
        h.priority_level ?? (h.priorityLevel ? h.priorityLevel.toUpperCase() : null),
        h.anomaly_level ?? h.anomalyLevel ?? null,
        h.persistence ? String(h.persistence) : null,
        h.change_summary || h.changeSummary || null,
        h.reasons ? JSON.stringify(h.reasons) : JSON.stringify([]),
        h.score_breakdown ? JSON.stringify(h.score_breakdown) : null,
        h.key_metric || h.keyMetric || null,
        h.baseline_deviation || h.baselineDeviation || null,
        h.neighborhood_percentile || h.neighborhoodPercentile || null,
        h.last_observed_date || h.lastObservedDate || null,
        h.recommendation || 'Unusual spatial change detected. Field verification recommended.',
        h.geometry ? JSON.stringify(h.geometry) : null,
        JSON.stringify(h)
      ]);

      if (hasPostgis && h.geometry) {
        await client.query(`
          UPDATE hotspots 
          SET geom = ST_SetSRID(ST_GeomFromGeoJSON($1), 4326) 
          WHERE id = $2;
        `, [JSON.stringify(h.geometry), id]);
      }

      hotspotCount++;
    }

    // 4. Load evidence table
    console.log('[UrbanPulse Importer] Loading evidence table...');
    const companionEvidencePath = path.join(inputDir, 'evidence.json');
    let evidenceMap = {};

    if (fs.existsSync(companionEvidencePath)) {
      try {
        evidenceMap = JSON.parse(fs.readFileSync(companionEvidencePath, 'utf-8'));
      } catch (e) {
        console.warn(`[UrbanPulse Importer] Could not parse companion evidence.json: ${e.message}`);
      }
    }

    let evidenceCount = 0;
    for (const rec of records) {
      const gridId = rec.grid_id || rec.cellId || rec.id;
      if (!gridId) continue;

      const explicitEvidence = evidenceMap[gridId] || null;

      // Scan existing images
      const cellImagesDir = path.join(ROOT_DIR, 'data', 'images', gridId);
      const existingImages = [];
      if (fs.existsSync(cellImagesDir)) {
        for (const yr of [2020, 2023, 2026]) {
          if (fs.existsSync(path.join(cellImagesDir, `${yr}.svg`))) {
            existingImages.push(`/images/${gridId}/${yr}.svg`);
          }
        }
      }

      const observed_change = {
        built_up: rec.built_up_2026 !== undefined && rec.built_up_2020 !== undefined ? +(rec.built_up_2026 - rec.built_up_2020).toFixed(2) : null,
        vegetation: rec.vegetation_2026 !== undefined && rec.vegetation_2020 !== undefined ? +(rec.vegetation_2026 - rec.vegetation_2020).toFixed(2) : null,
        water: rec.water_2026 !== undefined && rec.water_2020 !== undefined ? +(rec.water_2026 - rec.water_2020).toFixed(2) : null,
        ...(rec.bare_land_2026 !== undefined && rec.bare_land_2020 !== undefined ? { bare_land: +(rec.bare_land_2026 - rec.bare_land_2020).toFixed(2) } : {})
      };

      const lat = rec.lat !== undefined ? rec.lat : (rec.coordinates ? rec.coordinates[0] : null);
      const lng = rec.lng !== undefined ? rec.lng : (rec.coordinates ? rec.coordinates[1] : null);

      await client.query(`
        INSERT INTO evidence (
          grid_id, hotspot_id, cell_id, ward_name,
          lat, lng, coordinates, category, category_label,
          summary, recommendation, pipeline, observed_change,
          historical_change, local_percentile, temporal_anomaly, spatial_anomaly, persistence,
          priority_score, priority_level, image_urls, raw_data, updated_at
        ) VALUES (
          $1, $2, $3, $4,
          $5, $6, $7, $8, $9,
          $10, $11, $12, $13,
          $14, $15, $16, $17, $18,
          $19, $20, $21, $22, NOW()
        )
        ON CONFLICT (grid_id) DO UPDATE SET
          hotspot_id = EXCLUDED.hotspot_id,
          cell_id = EXCLUDED.cell_id,
          ward_name = EXCLUDED.ward_name,
          lat = EXCLUDED.lat,
          lng = EXCLUDED.lng,
          coordinates = EXCLUDED.coordinates,
          category = EXCLUDED.category,
          category_label = EXCLUDED.category_label,
          summary = EXCLUDED.summary,
          recommendation = EXCLUDED.recommendation,
          pipeline = EXCLUDED.pipeline,
          observed_change = EXCLUDED.observed_change,
          historical_change = EXCLUDED.historical_change,
          local_percentile = EXCLUDED.local_percentile,
          temporal_anomaly = EXCLUDED.temporal_anomaly,
          spatial_anomaly = EXCLUDED.spatial_anomaly,
          persistence = EXCLUDED.persistence,
          priority_score = EXCLUDED.priority_score,
          priority_level = EXCLUDED.priority_level,
          image_urls = EXCLUDED.image_urls,
          raw_data = EXCLUDED.raw_data,
          updated_at = NOW();
      `, [
        gridId,
        gridId,
        gridId,
        explicitEvidence?.wardName || rec.ward_name || rec.wardName || null,
        lat,
        lng,
        JSON.stringify([lat, lng]),
        explicitEvidence?.category || rec.category || 'built_up_expansion',
        explicitEvidence?.categoryLabel || rec.categoryLabel || 'Built-up expansion',
        explicitEvidence?.summary || (rec.reasons && rec.reasons[0]) || 'Unusual spatial change detected',
        explicitEvidence?.recommendation || 'Unusual spatial change detected. Field verification recommended.',
        explicitEvidence?.pipeline ? JSON.stringify(explicitEvidence.pipeline) : null,
        JSON.stringify(observed_change),
        rec.historical_change ?? null,
        rec.local_percentile ?? null,
        rec.temporal_anomaly ?? null,
        rec.spatial_anomaly ?? null,
        rec.persistence ?? null,
        rec.priority_score ?? rec.priorityScore ?? null,
        rec.priority_level ?? (rec.priorityLevel ? rec.priorityLevel.toUpperCase() : null),
        JSON.stringify(existingImages),
        explicitEvidence ? JSON.stringify(explicitEvidence) : JSON.stringify(rec)
      ]);

      evidenceCount++;
    }

    await client.query('COMMIT');

    console.log('\n=======================================================');
    console.log('✓ UrbanPulse PostgreSQL Import Succeeded (Idempotent)!');
    console.log(`  - Urban observations: ${obsCount} rows`);
    console.log(`  - Hotspots:           ${hotspotCount} rows`);
    console.log(`  - Evidence dossiers:  ${evidenceCount} rows`);
    console.log('=======================================================\n');

  } catch (err) {
    await client.query('ROLLBACK');
    console.error(`\n[UrbanPulse Importer] Transaction failed and rolled back.`);
    console.error(`Error: ${err.message}\n`);
    process.exit(1);
  } finally {
    await client.end();
  }
}

// Execute when invoked as CLI script
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  runImport().catch(err => {
    console.error(`[UrbanPulse Importer] Unhandled rejection: ${err.message}`);
    process.exit(1);
  });
}

export { runImport };
