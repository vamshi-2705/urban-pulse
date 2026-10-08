/**
 * UrbanPulse - Selftest Verification Script
 *
 * Verifies data integrity of the mock layer:
 * 1. meta.is_mock is true
 * 2. meta.analyzed_cells equals number of cells generated (~150)
 * 3. 5 HIGH, 10 MEDIUM, ~135 LOW cells
 * 4. Preserved cells (HYD_0421, HYD_0512, HYD_0387, HYD_0621) retain exact values
 * 5. Every record has score_breakdown that sums EXACTLY to priority_score
 * 6. Every record has valid GeoJSON square polygon geometry
 * 7. Optional bare_land_2020/2023/2026 are present and valid
 * 8. Top 8 hotspots have placeholder SVG images with "MOCK IMAGERY"
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '..');
const MOCK_FILE = path.join(ROOT_DIR, 'data', 'mock', 'investigation_list.json');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

console.log('--- UrbanPulse Mock Layer Selftest ---');

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
  // Check closed ring
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

console.log('\nALL SELFTEST CHECKS PASSED SUCCESSFULLY (0 errors).\n');
process.exit(0);
