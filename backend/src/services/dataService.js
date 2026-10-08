/**
 * UrbanPulse - Data Service
 *
 * Implements business data access for mock data layer per contract:
 * - Preloaded synchronously into memory at module load.
 * - Adheres strictly to Hard Rules: never recalculates or adjusts priority or anomaly scores.
 * - Simple subtraction for metric differences (2020 -> 2026).
 * - Checks for existence of placeholder SVGs in data/images/<gridId>/.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '../../..');
const MOCK_FILE = path.join(ROOT_DIR, 'data', 'mock', 'investigation_list.json');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

function loadData() {
  try {
    const raw = fs.readFileSync(MOCK_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch (err) {
    console.error(`[DataService] Failed to load ${MOCK_FILE}:`, err.message);
    throw err;
  }
}

// In-memory dataset
const rawData = loadData();

export const dataService = {
  getMeta() {
    return {
      source: rawData.meta?.source || "mock",
      is_mock: rawData.meta?.is_mock !== undefined ? rawData.meta.is_mock : true,
      warning: rawData.meta?.warning || "DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo.",
      city: rawData.meta?.city || "Hyderabad",
      generated_at: rawData.meta?.generated_at || "2026-10-08T00:00:00.000Z",
      imagery_years: rawData.meta?.imagery_years || [2020, 2023, 2026],
      analyzed_cells: rawData.records.length
    };
  },

  getAllRecords() {
    return rawData.records;
  },

  getRecordById(gridId) {
    if (!gridId) return null;
    const cleanId = String(gridId).trim();
    return rawData.records.find(
      r => r.grid_id.toLowerCase() === cleanId.toLowerCase()
    ) || null;
  },

  getStatistics() {
    const meta = this.getMeta();
    const records = rawData.records;

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
    const areas = rawData.records.map(r => ({
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

  getHotspotDetail(gridId) {
    const rec = this.getRecordById(gridId);
    if (!rec) return null;

    const meta = this.getMeta();

    // Per-metric differences (2020 -> 2026) by simple subtraction
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
    const rec = this.getRecordById(gridId);
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

  getEvidence(gridId) {
    const rec = this.getRecordById(gridId);
    if (!rec) return null;

    const meta = this.getMeta();

    // Check placeholder images in data/images/<grid_id>/
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

export default dataService;
