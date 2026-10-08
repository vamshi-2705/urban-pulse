/**
 * UrbanPulse - Real Provider & Canonical Hotspot Verification Test
 *
 * Verifies that:
 * 1. DATA_PROVIDER=real is active and loads real Sentinel-2 outputs.
 * 2. Canonical demo hotspot HYD_1220 is retrieved with:
 *    - priority_score ≈ 0.82 (or 82/100)
 *    - priority_level = HIGH
 *    - latitude ≈ 17.372285
 *    - longitude ≈ 78.422560
 * 3. Verification of other verified hotspots (HYD_1223, HYD_0863, HYD_1200).
 * 4. Multi-temporal change deltas and real evidence assets resolve properly.
 */

import { realProvider } from '../backend/src/providers/realProvider.js';
import { getProvider, getProviderType } from '../backend/src/providers/index.js';
import { dataService } from '../backend/src/services/dataService.js';

console.log('--- UrbanPulse Real Provider Integration Test ---');

// Set provider env
process.env.DATA_PROVIDER = 'real';

const provider = getProvider();
const providerType = getProviderType();

if (providerType !== 'real') {
  console.error(`FAIL: Expected providerType 'real', got '${providerType}'`);
  process.exit(1);
}
console.log('✓ Provider selection: [REAL]');

if (provider.isMockActive() !== false) {
  console.error('FAIL: isMockActive() must be false for realProvider');
  process.exit(1);
}
console.log('✓ isMockActive() is false');

// 1. Verify Overview and Statistics
const stats = provider.getStatistics('2020_2026');
if (!stats || stats.analyzed_cells !== 1462) {
  console.error(`FAIL: Expected 1462 analyzed cells, got ${stats?.analyzed_cells}`);
  process.exit(1);
}
if (stats.high !== 27) {
  console.error(`FAIL: Expected 27 high priority cells, got ${stats?.high}`);
  process.exit(1);
}
console.log(`✓ City statistics verified: 1462 cells, ${stats.high} HIGH priority cells`);

// 2. Verify Canonical Hotspot HYD_1220
const hyd1220 = provider.getHotspotById('HYD_1220', '2020_2026');
if (!hyd1220) {
  console.error("FAIL: Canonical hotspot HYD_1220 not found in real provider");
  process.exit(1);
}
console.log('✓ Canonical hotspot HYD_1220 retrieved successfully');

// Priority score check (score is 82 or ~0.82)
const score = hyd1220.priorityScore ?? hyd1220.priority_score;
if (Math.abs(score - 82) > 1 && Math.abs(score - 0.82) > 0.05) {
  console.error(`FAIL: HYD_1220 priority score expected ~82 (or 0.82), got ${score}`);
  process.exit(1);
}
console.log(`✓ HYD_1220 priority score: ${score}`);

// Priority level check
const level = (hyd1220.priorityLevel || hyd1220.priority_level || '').toUpperCase();
if (level !== 'HIGH') {
  console.error(`FAIL: HYD_1220 priority level expected 'HIGH', got '${level}'`);
  process.exit(1);
}
console.log(`✓ HYD_1220 priority level: ${level}`);

// Coordinates check
const lat = hyd1220.lat ?? hyd1220.latitude;
const lng = hyd1220.lng ?? hyd1220.longitude;
if (Math.abs(lat - 17.372285) > 0.001) {
  console.error(`FAIL: HYD_1220 latitude expected ~17.372285, got ${lat}`);
  process.exit(1);
}
if (Math.abs(lng - 78.422560) > 0.001) {
  console.error(`FAIL: HYD_1220 longitude expected ~78.422560, got ${lng}`);
  process.exit(1);
}
console.log(`✓ HYD_1220 coordinates verified: (${lat.toFixed(6)}, ${lng.toFixed(6)})`);

// 3. Verify Backup Demo Hotspots
for (const backupId of ['HYD_1223', 'HYD_0863', 'HYD_1200']) {
  const backup = provider.getHotspotById(backupId, '2020_2026');
  if (!backup) {
    console.error(`FAIL: Backup hotspot ${backupId} not found`);
    process.exit(1);
  }
  const bLevel = (backup.priorityLevel || backup.priority_level || '').toUpperCase();
  if (bLevel !== 'HIGH') {
    console.error(`FAIL: Backup hotspot ${backupId} expected HIGH, got ${bLevel}`);
    process.exit(1);
  }
  console.log(`✓ Backup demo hotspot ${backupId}: Rank ${backup.rank}, Score ${backup.priorityScore}, Level ${bLevel}`);
}

// 4. Verify Change Time Series
const change = provider.getChange('HYD_1220', '2020_2026');
if (!change || !Array.isArray(change.built_up) || change.built_up.length !== 3) {
  console.error('FAIL: Invalid change series for HYD_1220');
  process.exit(1);
}
console.log('✓ Change trajectory series verified (2020, 2023, 2026)');

// 5. Verify Evidence Dossier & Assets
const evidence = provider.getEvidence('HYD_1220', '2020_2026');
if (!evidence || !evidence.assets) {
  console.error('FAIL: Missing evidence assets for HYD_1220');
  process.exit(1);
}
if (!evidence.assets.before_rgb || !evidence.assets.after_rgb) {
  console.error('FAIL: Missing RGB preview assets for HYD_1220');
  process.exit(1);
}
console.log(`✓ Real evidence assets verified: before_rgb (${evidence.assets.before_rgb}), after_rgb (${evidence.assets.after_rgb})`);

// 6. Verify dataService delegation
const dsHotspot = dataService.getHotspotDetail('HYD_1220', '2020_2026');
if (!dsHotspot || dsHotspot.grid_id !== 'HYD_1220') {
  console.error('FAIL: dataService failed to return HYD_1220 under DATA_PROVIDER=real');
  process.exit(1);
}
console.log('✓ dataService delegation verified');

console.log('\n========================================');
console.log('ALL REAL PROVIDER TESTS PASSED (EXIT 0)');
console.log('========================================');
process.exit(0);
