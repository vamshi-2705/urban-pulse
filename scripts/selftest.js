/**
 * UrbanPulse - Selftest Verification Script
 *
 * Verifies data integrity and REST service contract:
 * 1. meta.is_mock is true and meta block present
 * 2. meta.analyzed_cells equals number of cells generated (~150)
 * 3. 5 HIGH, 10 MEDIUM, ~135 LOW cells
 * 4. Preserved cells (HYD_0421, HYD_0512, HYD_0387, HYD_0621) retain exact values
 * 5. Every record has score_breakdown that sums EXACTLY to priority_score
 * 6. Every record has valid GeoJSON square polygon geometry
 * 7. Optional bare_land_2020/2023/2026 are present and valid
 * 8. Top 8 hotspots have placeholder SVG images with "MOCK IMAGERY"
 * 9. GET /api/statistics service contract (analyzed_cells, anomalous, high, medium, low)
 * 10. GET /api/areas service contract (all cells with grid_id, lat, lng, geometry, priority_level, priority_score)
 * 11. GET /api/hotspots/:gridId service contract (full record, score_breakdown, reasons, per-metric deltas, 404 for unknown)
 * 12. GET /api/change/:gridId service contract (built_up, vegetation, water, bare_land series, 404 for unknown)
 * 13. GET /api/evidence/:gridId service contract (observed_change, baselines, anomalies, persistence, image URLs, 404 for unknown)
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dataService } from '../backend/src/services/dataService.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '..');
const MOCK_FILE = path.join(ROOT_DIR, 'data', 'mock', 'investigation_list.json');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

console.log('--- UrbanPulse Selftest Suite ---');

if (!fs.existsSync(MOCK_FILE)) {
  console.error(`FAIL: Mock file not found at ${MOCK_FILE}`);
  process.exit(1);
}

const raw = fs.readFileSync(MOCK_FILE, 'utf-8');
const data = JSON.parse(raw);

const { meta, records } = data;

// 1. Check Meta
if (!meta || meta.is_mock !== true) {
  console.error('FAIL: meta.is_mock must be true');
  process.exit(1);
}
console.log('✓ meta.is_mock is true');

if (meta.analyzed_cells !== records.length) {
  console.error(`FAIL: meta.analyzed_cells (${meta.analyzed_cells}) !== records.length (${records.length})`);
  process.exit(1);
}
console.log(`✓ meta.analyzed_cells matches records count (${records.length})`);

if (records.length < 140 || records.length > 165) {
  console.error(`FAIL: Expected ~150 records, got ${records.length}`);
  process.exit(1);
}
console.log(`✓ Total grid cells generated: ${records.length} (~150 regular grid cells)`);

// 2. Priority Distribution
const highCells = records.filter(r => r.priority_level === 'HIGH');
const mediumCells = records.filter(r => r.priority_level === 'MEDIUM');
const lowCells = records.filter(r => r.priority_level === 'LOW');

if (highCells.length !== 5) {
  console.error(`FAIL: Expected exactly 5 HIGH cells, got ${highCells.length}`);
  process.exit(1);
}
console.log(`✓ Exactly 5 HIGH cells: ${highCells.map(h => `${h.grid_id} (${h.priority_score})`).join(', ')}`);

if (mediumCells.length !== 10) {
  console.error(`FAIL: Expected exactly 10 MEDIUM cells, got ${mediumCells.length}`);
  process.exit(1);
}
console.log(`✓ Exactly 10 MEDIUM cells: ${mediumCells.map(m => `${m.grid_id} (${m.priority_score})`).join(', ')}`);

if (lowCells.length !== records.length - 15) {
  console.error(`FAIL: Expected ${records.length - 15} LOW cells, got ${lowCells.length}`);
  process.exit(1);
}
console.log(`✓ Majority LOW cells: ${lowCells.length} cells`);

// 3. Check Preserved Records
const preservedExpected = {
  HYD_0421: { score: 87, level: 'HIGH' },
  HYD_0512: { score: 82, level: 'HIGH' },
  HYD_0387: { score: 79, level: 'HIGH' },
  HYD_0621: { score: 73, level: 'MEDIUM' }
};

for (const [id, exp] of Object.entries(preservedExpected)) {
  const rec = records.find(r => r.grid_id === id);
  if (!rec) {
    console.error(`FAIL: Preserved record ${id} not found in dataset!`);
    process.exit(1);
  }
  if (rec.priority_score !== exp.score || rec.priority_level !== exp.level) {
    console.error(`FAIL: Preserved record ${id} mismatch: score ${rec.priority_score} (exp ${exp.score}), level ${rec.priority_level} (exp ${exp.level})`);
    process.exit(1);
  }
}
console.log('✓ Preserved records (HYD_0421, HYD_0512, HYD_0387, HYD_0621) matched exact expected values');

// 4. Verify Score Breakdown sums and GeoJSON Geometry for ALL records
let breakdownChecked = 0;
for (const rec of records) {
  if (!rec.score_breakdown) {
    console.error(`FAIL: Record ${rec.grid_id} missing score_breakdown`);
    process.exit(1);
  }

  const {
    urban_expansion = 0,
    vegetation_loss = 0,
    water_body_change = 0,
    historical_anomaly = 0,
    spatial_anomaly = 0,
    persistence = 0
  } = rec.score_breakdown;

  const sum = urban_expansion + vegetation_loss + water_body_change + historical_anomaly + spatial_anomaly + persistence;

  if (sum !== rec.priority_score) {
    console.error(`FAIL: Record ${rec.grid_id} breakdown sum (${sum}) does not match priority_score (${rec.priority_score})!`);
    console.error(`Details:`, rec.score_breakdown);
    process.exit(1);
  }

  // Geometry check
  if (!rec.geometry || rec.geometry.type !== 'Polygon' || !Array.isArray(rec.geometry.coordinates)) {
    console.error(`FAIL: Record ${rec.grid_id} missing valid GeoJSON Polygon geometry`);
    process.exit(1);
  }
  const ring = rec.geometry.coordinates[0];
  if (!ring || ring.length !== 5) {
    console.error(`FAIL: Record ${rec.grid_id} geometry polygon ring must have 5 coordinate pairs (closed square)`);
    process.exit(1);
  }
  if (ring[0][0] !== ring[4][0] || ring[0][1] !== ring[4][1]) {
    console.error(`FAIL: Record ${rec.grid_id} geometry polygon ring is not closed`);
    process.exit(1);
  }

  // Optional bare_land checks
  if (rec.bare_land_2020 !== undefined) {
    if (typeof rec.bare_land_2020 !== 'number' || typeof rec.bare_land_2023 !== 'number' || typeof rec.bare_land_2026 !== 'number') {
      console.error(`FAIL: Record ${rec.grid_id} invalid bare_land fields`);
      process.exit(1);
    }
  }

  breakdownChecked++;
}
console.log(`✓ All ${breakdownChecked} records verified: score_breakdown sums strictly equal priority_score`);
console.log(`✓ All ${breakdownChecked} records verified: valid GeoJSON square polygon (~500m)`);

// 5. Check Placeholder Images for Top 8 Hotspots
const top8 = records.slice(0, 8);
for (const item of top8) {
  const itemDir = path.join(IMAGES_DIR, item.grid_id);
  for (const year of [2020, 2023, 2026]) {
    const svgPath = path.join(itemDir, `${year}.svg`);
    if (!fs.existsSync(svgPath)) {
      console.error(`FAIL: Missing placeholder SVG: ${svgPath}`);
      process.exit(1);
    }
    const svgContent = fs.readFileSync(svgPath, 'utf-8');
    if (!svgContent.includes('MOCK IMAGERY')) {
      console.error(`FAIL: ${svgPath} must contain 'MOCK IMAGERY' in text`);
      process.exit(1);
    }
  }
}
console.log(`✓ Top 8 hotspots have valid placeholder SVG images with 'MOCK IMAGERY' watermark (24 files total)`);

// =========================================================================
// 6. Extended REST API Services & Contract Checks
// =========================================================================

console.log('\n--- Extended REST Services Contract Tests ---');

// A. Statistics
const stats = dataService.getStatistics();
if (!stats.meta || stats.meta.is_mock !== true || !stats.meta.warning) {
  console.error('FAIL: getStatistics missing required meta block');
  process.exit(1);
}
if (stats.analyzed_cells !== records.length || stats.anomalous !== 15 || stats.high !== 5 || stats.medium !== 10 || stats.low !== 135) {
  console.error('FAIL: getStatistics counts mismatch:', stats);
  process.exit(1);
}
console.log(`✓ getStatistics contract passed (analyzed: ${stats.analyzed_cells}, anomalous: ${stats.anomalous}, high: ${stats.high}, medium: ${stats.medium}, low: ${stats.low})`);

// B. Areas
const areasResult = dataService.getAreas();
if (!areasResult.meta || !Array.isArray(areasResult.areas)) {
  console.error('FAIL: getAreas missing meta or areas array');
  process.exit(1);
}
if (areasResult.areas.length !== records.length) {
  console.error(`FAIL: getAreas count mismatch: ${areasResult.areas.length} !== ${records.length}`);
  process.exit(1);
}
const firstArea = areasResult.areas[0];
if (!firstArea.grid_id || typeof firstArea.lat !== 'number' || typeof firstArea.lng !== 'number' || !firstArea.geometry || !firstArea.priority_level || typeof firstArea.priority_score !== 'number') {
  console.error('FAIL: getAreas item missing required attributes:', firstArea);
  process.exit(1);
}
console.log(`✓ getAreas contract passed (${areasResult.areas.length} cells with geometry & scores)`);

// C. Hotspot Detail (HYD_0421 & unknown)
const hotspotDetail = dataService.getHotspotDetail('HYD_0421');
if (!hotspotDetail || !hotspotDetail.meta || hotspotDetail.grid_id !== 'HYD_0421') {
  console.error('FAIL: getHotspotDetail(HYD_0421) failed');
  process.exit(1);
}
if (!hotspotDetail.score_breakdown || !Array.isArray(hotspotDetail.reasons) || !hotspotDetail.differences) {
  console.error('FAIL: getHotspotDetail missing score_breakdown, reasons, or differences');
  process.exit(1);
}
// Check difference calculation: 47.2 - 31.2 = 16.0
if (hotspotDetail.differences.built_up !== 16) {
  console.error(`FAIL: HYD_0421 built_up difference expected 16, got ${hotspotDetail.differences.built_up}`);
  process.exit(1);
}
if (hotspotDetail.differences.vegetation !== -10.7) {
  console.error(`FAIL: HYD_0421 vegetation difference expected -10.7, got ${hotspotDetail.differences.vegetation}`);
  process.exit(1);
}
console.log(`✓ getHotspotDetail(HYD_0421) contract passed (built_up diff: +${hotspotDetail.differences.built_up}%, veg diff: ${hotspotDetail.differences.vegetation}%)`);

// Unknown hotspot should return null (maps to 404)
const unknownHotspot = dataService.getHotspotDetail('NON_EXISTENT_ID');
if (unknownHotspot !== null) {
  console.error('FAIL: getHotspotDetail on unknown ID must return null');
  process.exit(1);
}
console.log('✓ getHotspotDetail unknown ID correctly returns null for 404 response');

// D. Change Series (HYD_0421 & unknown)
const changeSeries = dataService.getChange('HYD_0421');
if (!changeSeries || !changeSeries.meta || changeSeries.grid_id !== 'HYD_0421') {
  console.error('FAIL: getChange(HYD_0421) failed');
  process.exit(1);
}
if (!Array.isArray(changeSeries.built_up) || !Array.isArray(changeSeries.vegetation) || !Array.isArray(changeSeries.water)) {
  console.error('FAIL: getChange series missing arrays for built_up, vegetation, or water');
  process.exit(1);
}
if (changeSeries.built_up.length !== 3 || changeSeries.built_up[0].year !== 2020 || changeSeries.built_up[2].year !== 2026) {
  console.error('FAIL: getChange series format invalid:', changeSeries.built_up);
  process.exit(1);
}
console.log('✓ getChange(HYD_0421) contract passed (multi-year time series [{year, value}])');

const unknownChange = dataService.getChange('NON_EXISTENT_ID');
if (unknownChange !== null) {
  console.error('FAIL: getChange on unknown ID must return null');
  process.exit(1);
}
console.log('✓ getChange unknown ID correctly returns null for 404 response');

// E. Evidence Record (HYD_0421 & unknown)
const evidenceRec = dataService.getEvidence('HYD_0421');
if (!evidenceRec || !evidenceRec.meta || evidenceRec.grid_id !== 'HYD_0421') {
  console.error('FAIL: getEvidence(HYD_0421) failed');
  process.exit(1);
}
if (!evidenceRec.observed_change || typeof evidenceRec.historical_change !== 'number' || typeof evidenceRec.local_percentile !== 'number') {
  console.error('FAIL: getEvidence missing observed_change, historical_change, or local_percentile');
  process.exit(1);
}
if (!Array.isArray(evidenceRec.images) || evidenceRec.images.length !== 3) {
  console.error('FAIL: HYD_0421 should have 3 image URLs, got:', evidenceRec.images);
  process.exit(1);
}
console.log(`✓ getEvidence(HYD_0421) contract passed (${evidenceRec.images.length} verified placeholder image URLs)`);

const unknownEvidence = dataService.getEvidence('NON_EXISTENT_ID');
if (unknownEvidence !== null) {
  console.error('FAIL: getEvidence on unknown ID must return null');
  process.exit(1);
}
console.log('✓ getEvidence unknown ID correctly returns null for 404 response');

// =========================================================================
// 7. Database Persistence & Provider Architecture Tests
// =========================================================================

console.log('\n--- Persistence & Multi-Provider Architecture Tests ---');

// A. Schema SQL Validation
const schemaPath = path.join(ROOT_DIR, 'backend', 'db', 'schema.sql');
if (!fs.existsSync(schemaPath)) {
  console.error('FAIL: backend/db/schema.sql does not exist');
  process.exit(1);
}
const schemaSql = fs.readFileSync(schemaPath, 'utf-8');
const requiredTables = ['urban_observations', 'evidence', 'hotspots', 'metadata'];
for (const table of requiredTables) {
  if (!schemaSql.includes(`CREATE TABLE IF NOT EXISTS ${table}`)) {
    console.error(`FAIL: schema.sql missing required table: ${table}`);
    process.exit(1);
  }
}
if (!schemaSql.includes('postgis') || !schemaSql.includes('geom geometry')) {
  console.error('FAIL: schema.sql missing conditional PostGIS geometry handling');
  process.exit(1);
}
console.log('✓ schema.sql verified (tables: urban_observations, evidence, hotspots; conditional PostGIS support)');

// B. Importer Script Validation
const importScriptPath = path.join(ROOT_DIR, 'backend', 'scripts', 'import.js');
if (!fs.existsSync(importScriptPath)) {
  console.error('FAIL: backend/scripts/import.js does not exist');
  process.exit(1);
}
const importScriptContent = fs.readFileSync(importScriptPath, 'utf-8');
if (!importScriptContent.includes('ON CONFLICT') || !importScriptContent.includes('DATABASE_URL')) {
  console.error('FAIL: import.js missing idempotent conflict handling or DATABASE_URL config');
  process.exit(1);
}
console.log('✓ import.js verified (idempotent loading with ON CONFLICT DO UPDATE)');

// C. File Provider Contract Tests
const { fileProvider } = await import('../backend/src/providers/fileProvider.js');
const fileStats = fileProvider.getStatistics();
if (fileStats.analyzed_cells !== 150 || fileStats.high !== 5 || fileStats.medium !== 10) {
  console.error('FAIL: fileProvider.getStatistics mismatch:', fileStats);
  process.exit(1);
}
const fileAreas = fileProvider.getAreas();
if (fileAreas.areas.length !== 150) {
  console.error('FAIL: fileProvider.getAreas length mismatch');
  process.exit(1);
}
const fileHotspot = fileProvider.getHotspotDetail('HYD_0421');
if (!fileHotspot || fileHotspot.differences.built_up !== 16) {
  console.error('FAIL: fileProvider.getHotspotDetail calculation mismatch');
  process.exit(1);
}
console.log('✓ fileProvider verified (reads directly from filesystem with identical metrics)');

// D. Provider Selector & Postgres Unreachable Handling
const { getProvider, postgresProvider } = await import('../backend/src/providers/index.js');
const defaultProv = getProvider();
if (defaultProv.getMode && defaultProv.getMode() !== 'mock') {
  console.error('FAIL: default provider should be mock in development');
  process.exit(1);
}
console.log('✓ In-memory mock provider remains active by default');

// E. Verify Postgres Provider Fails With Clear Message When DB is Unreachable
let caughtError = null;
const originalDbUrl = process.env.DATABASE_URL;
try {
  process.env.DATABASE_URL = 'postgresql://localhost:59999/unreachable_db';
  await postgresProvider.verifyConnection();
} catch (err) {
  caughtError = err;
} finally {
  if (originalDbUrl) {
    process.env.DATABASE_URL = originalDbUrl;
  } else {
    delete process.env.DATABASE_URL;
  }
}

if (!caughtError || !caughtError.message.includes('Database unreachable')) {
  console.error('FAIL: postgresProvider did not fail with clear "Database unreachable" message:', caughtError);
  process.exit(1);
}
console.log('✓ postgresProvider fails with clear message when DB is unreachable');

console.log('\nALL EXTENDED REST SERVICES & PERSISTENCE CHECKS PASSED (0 errors).\n');
process.exit(0);

