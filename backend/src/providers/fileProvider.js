/**
 * UrbanPulse - File Data Provider
 *
 * Serves observations directly from JSON files in data/mock.
 * Used when DATA_PROVIDER=file is set.
 *
 * Rules:
 * - Reads from data/mock dynamically from filesystem.
 * - Never calculates or adjusts priority or anomaly scores.
 * - Purely returns what the file records contain.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '../../..');
const DATA_DIR = path.join(ROOT_DIR, 'data', 'mock');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

function readJson(fileName) {
  const filePath = path.join(DATA_DIR, fileName);
  try {
    const raw = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    console.error(`[FileProvider] Failed to read ${filePath}:`, err.message);
    throw err;
  }
}

export const fileProvider = {
  getMode() {
    return 'file';
  },

  isMockActive() {
    try {
      const overview = readJson('overview.json');
      return overview.isMock !== undefined ? overview.isMock : true;
    } catch {
      return true;
    }
  },

  getOverview() {
    const overview = readJson('overview.json');
    return {
      ...overview,
      timestamp: new Date().toISOString()
    };
  },

  getPipeline() {
    return readJson('pipeline.json');
  },

  getInvestigationList() {
    return readJson('investigation_list.json');
  },

  getHotspots(filters = {}) {
    const hotspots = readJson('hotspots.json');
    let result = [...hotspots];

    if (filters.priorityLevel) {
      result = result.filter(h => (h.priorityLevel || h.priority_level || '').toLowerCase() === filters.priorityLevel.toLowerCase());
    }
    if (filters.category) {
      result = result.filter(h => h.category === filters.category);
    }
    if (filters.zone) {
      result = result.filter(h => (h.zone || '').toLowerCase() === filters.zone.toLowerCase());
    }

    return result.sort((a, b) => (a.rank || 0) - (b.rank || 0));
  },

  getHotspotById(id) {
    const hotspots = readJson('hotspots.json');
    const cleanId = String(id).trim().toLowerCase();
    return hotspots.find(h => 
      (h.id && h.id.toLowerCase() === cleanId) || 
      (h.grid_id && h.grid_id.toLowerCase() === cleanId) ||
      (h.cellId && h.cellId.toLowerCase() === cleanId)
    ) || null;
  },

  getEvidence(hotspotId) {
    const evidenceData = readJson('evidence.json');
    const cleanId = String(hotspotId).trim();

    if (evidenceData[cleanId]) {
      return evidenceData[cleanId];
    }

    // Check by matching lowercase keys or cellId
    for (const [key, val] of Object.entries(evidenceData)) {
      if (key.toLowerCase() === cleanId.toLowerCase() ||
          (val.cellId && val.cellId.toLowerCase() === cleanId.toLowerCase()) ||
          (val.grid_id && val.grid_id.toLowerCase() === cleanId.toLowerCase())) {
        return val;
      }
    }
    return null;
  },

  getGridCells(filters = {}) {
    const cells = readJson('cells.json');
    let result = [...cells];

    if (filters.priorityLevel) {
      result = result.filter(c => (c.priorityLevel || c.priority_level || '').toLowerCase() === filters.priorityLevel.toLowerCase());
    }
    if (filters.anomalyStatus) {
      result = result.filter(c => (c.anomalyStatus || '').toLowerCase() === filters.anomalyStatus.toLowerCase());
    }

    return result;
  },

  getMeta() {
    try {
      const inv = readJson('investigation_list.json');
      return {
        source: inv.meta?.source || 'file',
        is_mock: inv.meta?.is_mock !== undefined ? inv.meta.is_mock : true,
        warning: inv.meta?.warning || 'DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo.',
        city: inv.meta?.city || 'Hyderabad',
        generated_at: inv.meta?.generated_at || '2026-10-08T00:00:00.000Z',
        imagery_years: inv.meta?.imagery_years || [2020, 2023, 2026],
        analyzed_cells: inv.records ? inv.records.length : 0
      };
    } catch {
      return {
        source: 'file',
        is_mock: true,
        warning: 'DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo.'
      };
    }
  },

  getStatistics() {
    const meta = this.getMeta();
    const inv = readJson('investigation_list.json');
    const records = inv.records || [];

    const high = records.filter(r => r.priority_level === 'HIGH').length;
    const medium = records.filter(r => r.priority_level === 'MEDIUM').length;
    const low = records.filter(r => r.priority_level === 'LOW').length;
    const anomalous = high + medium;

    return {
      meta,
      analyzed_cells: records.length,
      anomalous,
      high,
      medium,
      low
    };
  },

  getAreas() {
    const meta = this.getMeta();
    const inv = readJson('investigation_list.json');
    const records = inv.records || [];

    const areas = records.map(r => ({
      grid_id: r.grid_id,
      lat: r.lat,
      lng: r.lng,
      geometry: r.geometry || null,
      priority_level: r.priority_level,
      priority_score: r.priority_score,
      reasons: r.reasons || []
    }));

    return {
      meta,
      areas
    };
  },

  getHotspotDetail(gridId) {
    const inv = readJson('investigation_list.json');
    const cleanId = String(gridId).trim().toLowerCase();
    const rec = (inv.records || []).find(r => r.grid_id.toLowerCase() === cleanId);
    if (!rec) return null;

    const meta = this.getMeta();
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

  getChange(gridId) {
    const inv = readJson('investigation_list.json');
    const cleanId = String(gridId).trim().toLowerCase();
    const rec = (inv.records || []).find(r => r.grid_id.toLowerCase() === cleanId);
    if (!rec) return null;

    const meta = this.getMeta();
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

    if (rec.bare_land_2020 !== undefined) {
      result.bare_land = [
        { year: 2020, value: rec.bare_land_2020 },
        { year: 2023, value: rec.bare_land_2023 },
        { year: 2026, value: rec.bare_land_2026 }
      ];
    }

    return result;
  },

  getEvidenceDetail(gridId) {
    const inv = readJson('investigation_list.json');
    const cleanId = String(gridId).trim().toLowerCase();
    const rec = (inv.records || []).find(r => r.grid_id.toLowerCase() === cleanId);
    if (!rec) return null;

    const meta = this.getMeta();
    const cellImagesDir = path.join(IMAGES_DIR, rec.grid_id);
    const existingImages = [];

    if (fs.existsSync(cellImagesDir)) {
      for (const year of [2020, 2023, 2026]) {
        const file = path.join(cellImagesDir, `${year}.svg`);
        if (fs.existsSync(file)) {
          existingImages.push(`/images/${rec.grid_id}/${year}.svg`);
        }
      }
    }

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

export default fileProvider;
