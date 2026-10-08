/**
 * UrbanPulse - Mock Dataset Generator
 *
 * Generates ~150 grid cells for Hyderabad as a regular grid of square cells (~500 m)
 * with GeoJSON "geometry" polygons, score breakdowns, bare land values,
 * and placeholder SVG imagery for top 8 hotspots.
 *
 * Uses a fixed seed PRNG for 100% reproducible output.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '..');
const MOCK_DIR = path.join(ROOT_DIR, 'data', 'mock');
const IMAGES_DIR = path.join(ROOT_DIR, 'data', 'images');

// Seeded PRNG (Mulberry32)
function createRng(seed = 42817) {
  let s = seed >>> 0;
  return function() {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rng = createRng(42817);

function randomInRange(min, max) {
  return min + rng() * (max - min);
}

function randomInt(min, max) {
  return Math.floor(randomInRange(min, max + 1));
}

// 500m in degrees for Hyderabad (~17.4° N)
const CELL_SIZE_M = 500;
const DEG_LAT_M = 111139;
const DEG_LNG_M = 111139 * Math.cos(17.4 * Math.PI / 180); // ~106,053 m
const DELTA_LAT = +(CELL_SIZE_M / DEG_LAT_M).toFixed(6); // ~0.004499°
const DELTA_LNG = +(CELL_SIZE_M / DEG_LNG_M).toFixed(6); // ~0.004715°

function createPolygonGeometry(centerLat, centerLng) {
  const halfLat = DELTA_LAT / 2;
  const halfLng = DELTA_LNG / 2;
  const minLat = +(centerLat - halfLat).toFixed(6);
  const maxLat = +(centerLat + halfLat).toFixed(6);
  const minLng = +(centerLng - halfLng).toFixed(6);
  const maxLng = +(centerLng + halfLng).toFixed(6);

  return {
    type: "Polygon",
    coordinates: [
      [
        [minLng, minLat],
        [maxLng, minLat],
        [maxLng, maxLat],
        [minLng, maxLat],
        [minLng, minLat]
      ]
    ]
  };
}

// Fixed Preserved Records (per specification)
const PRESERVED_RECORDS = [
  {
    grid_id: "HYD_0421",
    lat: 17.385,
    lng: 78.486,
    built_up: [31.2, 38.5, 47.2],
    vegetation: [42.1, 36.8, 31.4],
    water: [8.2, 6.1, 4.8],
    bare_land: [18.5, 18.6, 16.6],
    historical_change: 2.7,
    local_percentile: 95,
    temporal_anomaly: 0.91,
    spatial_anomaly: 0.87,
    persistence: 0.82,
    priority_score: 87,
    priority_level: "HIGH",
    reasons: [
      "Rapid built-up expansion",
      "Significant vegetation loss",
      "Growth exceeds historical baseline"
    ],
    score_breakdown: {
      urban_expansion: 32,
      vegetation_loss: 21,
      water_body_change: 0,
      historical_anomaly: 18,
      spatial_anomaly: 10,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0512",
    lat: 17.442,
    lng: 78.391,
    built_up: [22.4, 29.8, 38.9],
    vegetation: [48.0, 41.5, 35.7],
    water: [5.0, 4.6, 4.1],
    bare_land: [24.6, 24.1, 21.3],
    historical_change: 2.4,
    local_percentile: 94,
    temporal_anomaly: 0.88,
    spatial_anomaly: 0.84,
    persistence: 0.79,
    priority_score: 82,
    priority_level: "HIGH",
    reasons: [
      "Rapid built-up expansion",
      "Vegetation loss",
      "Growth exceeds historical baseline"
    ],
    score_breakdown: {
      urban_expansion: 29,
      vegetation_loss: 19,
      water_body_change: 0,
      historical_anomaly: 17,
      spatial_anomaly: 11,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0387",
    lat: 17.331,
    lng: 78.552,
    built_up: [18.0, 24.1, 31.6],
    vegetation: [55.2, 47.0, 39.9],
    water: [3.1, 3.0, 2.9],
    bare_land: [23.7, 25.9, 25.6],
    historical_change: 2.2,
    local_percentile: 93,
    temporal_anomaly: 0.85,
    spatial_anomaly: 0.82,
    persistence: 0.84,
    priority_score: 79,
    priority_level: "HIGH",
    reasons: [
      "Sustained vegetation loss",
      "Built-up growth above nearby areas"
    ],
    score_breakdown: {
      urban_expansion: 24,
      vegetation_loss: 22,
      water_body_change: 0,
      historical_anomaly: 16,
      spatial_anomaly: 10,
      persistence: 7
    }
  },
  {
    grid_id: "HYD_0621",
    lat: 17.497,
    lng: 78.331,
    built_up: [40.1, 44.8, 49.5],
    vegetation: [30.5, 28.0, 24.2],
    water: [6.0, 5.5, 5.1],
    bare_land: [23.4, 21.7, 21.2],
    historical_change: 1.9,
    local_percentile: 88,
    temporal_anomaly: 0.74,
    spatial_anomaly: 0.79,
    persistence: 0.71,
    priority_score: 73,
    priority_level: "MEDIUM",
    reasons: [
      "Built-up growth exceeds baseline",
      "Local anomaly"
    ],
    score_breakdown: {
      urban_expansion: 22,
      vegetation_loss: 15,
      water_body_change: 0,
      historical_anomaly: 18,
      spatial_anomaly: 12,
      persistence: 6
    }
  }
];

// 2 Additional HIGH cells (Total 5 HIGH cells)
const ADDITIONAL_HIGH_RECORDS = [
  {
    grid_id: "HYD_0499",
    lat: 17.398,
    lng: 78.435,
    built_up: [25.0, 31.0, 39.5],
    vegetation: [45.0, 40.0, 32.5],
    water: [6.0, 5.5, 4.8],
    bare_land: [24.0, 23.5, 23.2],
    historical_change: 2.1,
    local_percentile: 91,
    temporal_anomaly: 0.82,
    spatial_anomaly: 0.80,
    persistence: 0.81,
    priority_score: 76,
    priority_level: "HIGH",
    reasons: [
      "Rapid built-up growth",
      "Vegetation conversion"
    ],
    score_breakdown: {
      urban_expansion: 26,
      vegetation_loss: 18,
      water_body_change: 0,
      historical_anomaly: 16,
      spatial_anomaly: 10,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0555",
    lat: 17.420,
    lng: 78.510,
    built_up: [28.5, 34.2, 42.0],
    vegetation: [41.0, 36.5, 29.5],
    water: [4.5, 4.0, 3.8],
    bare_land: [26.0, 25.3, 24.7],
    historical_change: 2.0,
    local_percentile: 90,
    temporal_anomaly: 0.79,
    spatial_anomaly: 0.78,
    persistence: 0.78,
    priority_score: 74,
    priority_level: "HIGH",
    reasons: [
      "Built-up expansion in transition corridor",
      "Green canopy loss"
    ],
    score_breakdown: {
      urban_expansion: 25,
      vegetation_loss: 18,
      water_body_change: 0,
      historical_anomaly: 15,
      spatial_anomaly: 10,
      persistence: 6
    }
  }
];

// 9 Additional MEDIUM cells (with HYD_0621 brings total to 10 MEDIUM cells)
const ADDITIONAL_MEDIUM_RECORDS = [
  {
    grid_id: "HYD_0298",
    lat: 17.412,
    lng: 78.612,
    built_up: [12.0, 13.5, 15.0],
    vegetation: [35.2, 32.1, 28.5],
    water: [14.5, 11.0, 7.8],
    bare_land: [38.3, 43.4, 48.7],
    historical_change: 2.0,
    local_percentile: 86,
    temporal_anomaly: 0.72,
    spatial_anomaly: 0.70,
    persistence: 0.69,
    priority_score: 68,
    priority_level: "MEDIUM",
    reasons: ["Water-body area shrinking faster than baseline"],
    score_breakdown: {
      urban_expansion: 0,
      vegetation_loss: 14,
      water_body_change: 24,
      historical_anomaly: 14,
      spatial_anomaly: 10,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0733",
    lat: 17.298,
    lng: 78.431,
    built_up: [27.0, 31.5, 36.4],
    vegetation: [43.1, 39.2, 35.8],
    water: [4.2, 4.0, 3.8],
    bare_land: [25.7, 25.3, 24.0],
    historical_change: 1.6,
    local_percentile: 82,
    temporal_anomaly: 0.68,
    spatial_anomaly: 0.71,
    persistence: 0.66,
    priority_score: 61,
    priority_level: "MEDIUM",
    reasons: ["Built-up growth higher than nearby areas"],
    score_breakdown: {
      urban_expansion: 20,
      vegetation_loss: 12,
      water_body_change: 0,
      historical_anomaly: 15,
      spatial_anomaly: 8,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0488",
    lat: 17.458,
    lng: 78.445,
    built_up: [35.0, 38.2, 42.1],
    vegetation: [38.0, 35.1, 31.8],
    water: [3.5, 3.2, 3.0],
    bare_land: [23.5, 23.5, 23.1],
    historical_change: 1.5,
    local_percentile: 80,
    temporal_anomaly: 0.65,
    spatial_anomaly: 0.67,
    persistence: 0.64,
    priority_score: 58,
    priority_level: "MEDIUM",
    reasons: ["Continuous commercial strip expansion"],
    score_breakdown: {
      urban_expansion: 18,
      vegetation_loss: 12,
      water_body_change: 0,
      historical_anomaly: 14,
      spatial_anomaly: 8,
      persistence: 6
    }
  },
  {
    grid_id: "HYD_0542",
    lat: 17.430,
    lng: 78.530,
    built_up: [22.0, 25.4, 29.0],
    vegetation: [46.0, 43.1, 39.8],
    water: [9.0, 8.1, 7.2],
    bare_land: [23.0, 23.4, 24.0],
    historical_change: 1.4,
    local_percentile: 78,
    temporal_anomaly: 0.63,
    spatial_anomaly: 0.62,
    persistence: 0.62,
    priority_score: 55,
    priority_level: "MEDIUM",
    reasons: ["Localized pond periphery alteration"],
    score_breakdown: {
      urban_expansion: 16,
      vegetation_loss: 11,
      water_body_change: 4,
      historical_anomaly: 12,
      spatial_anomaly: 7,
      persistence: 5
    }
  },
  {
    grid_id: "HYD_0365",
    lat: 17.370,
    lng: 78.520,
    built_up: [33.0, 36.2, 39.8],
    vegetation: [36.0, 33.5, 30.2],
    water: [5.2, 5.0, 4.8],
    bare_land: [25.8, 25.3, 25.2],
    historical_change: 1.3,
    local_percentile: 76,
    temporal_anomaly: 0.60,
    spatial_anomaly: 0.60,
    persistence: 0.60,
    priority_score: 52,
    priority_level: "MEDIUM",
    reasons: ["Incremental industrial shed construction"],
    score_breakdown: {
      urban_expansion: 15,
      vegetation_loss: 10,
      water_body_change: 0,
      historical_anomaly: 14,
      spatial_anomaly: 8,
      persistence: 5
    }
  },
  {
    grid_id: "HYD_0615",
    lat: 17.480,
    lng: 78.360,
    built_up: [28.0, 31.0, 34.5],
    vegetation: [42.0, 39.2, 36.1],
    water: [4.0, 3.8, 3.7],
    bare_land: [26.0, 26.0, 25.7],
    historical_change: 1.3,
    local_percentile: 75,
    temporal_anomaly: 0.58,
    spatial_anomaly: 0.59,
    persistence: 0.58,
    priority_score: 50,
    priority_level: "MEDIUM",
    reasons: ["Moderate residential cluster extension"],
    score_breakdown: {
      urban_expansion: 14,
      vegetation_loss: 11,
      water_body_change: 0,
      historical_anomaly: 13,
      spatial_anomaly: 7,
      persistence: 5
    }
  },
  {
    grid_id: "HYD_0410",
    lat: 17.405,
    lng: 78.475,
    built_up: [42.0, 44.5, 47.8],
    vegetation: [29.0, 27.2, 25.1],
    water: [6.5, 6.0, 5.4],
    bare_land: [22.5, 22.3, 21.7],
    historical_change: 1.2,
    local_percentile: 74,
    temporal_anomaly: 0.56,
    spatial_anomaly: 0.57,
    persistence: 0.57,
    priority_score: 48,
    priority_level: "MEDIUM",
    reasons: ["Infill built-up expansion near canal"],
    score_breakdown: {
      urban_expansion: 14,
      vegetation_loss: 9,
      water_body_change: 3,
      historical_anomaly: 11,
      spatial_anomaly: 6,
      persistence: 5
    }
  },
  {
    grid_id: "HYD_0325",
    lat: 17.345,
    lng: 78.490,
    built_up: [24.0, 26.5, 29.5],
    vegetation: [49.0, 46.8, 44.0],
    water: [3.8, 3.6, 3.5],
    bare_land: [23.2, 23.1, 23.0],
    historical_change: 1.2,
    local_percentile: 72,
    temporal_anomaly: 0.54,
    spatial_anomaly: 0.55,
    persistence: 0.55,
    priority_score: 46,
    priority_level: "MEDIUM",
    reasons: ["Vegetation clearing along bypass access"],
    score_breakdown: {
      urban_expansion: 13,
      vegetation_loss: 9,
      water_body_change: 0,
      historical_anomaly: 12,
      spatial_anomaly: 7,
      persistence: 5
    }
  },
  {
    grid_id: "HYD_0580",
    lat: 17.465,
    lng: 78.505,
    built_up: [31.0, 33.4, 36.2],
    vegetation: [39.0, 36.8, 34.2],
    water: [5.0, 4.8, 4.6],
    bare_land: [25.0, 25.0, 25.0],
    historical_change: 1.1,
    local_percentile: 71,
    temporal_anomaly: 0.52,
    spatial_anomaly: 0.54,
    persistence: 0.53,
    priority_score: 45,
    priority_level: "MEDIUM",
    reasons: ["Secondary warehouse extension"],
    score_breakdown: {
      urban_expansion: 12,
      vegetation_loss: 10,
      water_body_change: 0,
      historical_anomaly: 11,
      spatial_anomaly: 7,
      persistence: 5
    }
  }
];

// Helper to partition an integer score into 6 breakdown factors that sum EXACTLY to score
function partitionScore(score, rngFn) {
  // factors: [urban_expansion, vegetation_loss, water_body_change, historical_anomaly, spatial_anomaly, persistence]
  // weights roughly: 30%, 25%, 5%, 20%, 12%, 8%
  let weights = [
    0.28 + rngFn() * 0.08,
    0.22 + rngFn() * 0.08,
    rngFn() > 0.6 ? 0.08 * rngFn() : 0,
    0.18 + rngFn() * 0.06,
    0.12 + rngFn() * 0.05,
    0.08 + rngFn() * 0.04
  ];
  let sumW = weights.reduce((a, b) => a + b, 0);
  let normalized = weights.map(w => w / sumW);

  let parts = normalized.map(w => Math.floor(w * score));
  let remainder = score - parts.reduce((a, b) => a + b, 0);

  // Distribute remainder into highest weight items
  for (let i = 0; i < remainder; i++) {
    parts[i % parts.length]++;
  }

  // Safety assert
  const total = parts.reduce((a, b) => a + b, 0);
  if (total !== score) {
    parts[0] += (score - total);
  }

  return {
    urban_expansion: parts[0],
    vegetation_loss: parts[1],
    water_body_change: parts[2],
    historical_anomaly: parts[3],
    spatial_anomaly: parts[4],
    persistence: parts[5]
  };
}

// Generate the full 150 records dataset
export function generateMockDataset() {
  const records = [];
  const assignedGridIds = new Set();

  // 1. Add 5 HIGH records
  const allHigh = [...PRESERVED_RECORDS.slice(0, 3), ...ADDITIONAL_HIGH_RECORDS];
  for (const item of allHigh) {
    assignedGridIds.add(item.grid_id);
    const rec = {
      grid_id: item.grid_id,
      lat: item.lat,
      lng: item.lng,
      geometry: createPolygonGeometry(item.lat, item.lng),
      built_up_2020: item.built_up[0],
      built_up_2023: item.built_up[1],
      built_up_2026: item.built_up[2],
      vegetation_2020: item.vegetation[0],
      vegetation_2023: item.vegetation[1],
      vegetation_2026: item.vegetation[2],
      water_2020: item.water[0],
      water_2023: item.water[1],
      water_2026: item.water[2],
      bare_land_2020: item.bare_land[0],
      bare_land_2023: item.bare_land[1],
      bare_land_2026: item.bare_land[2],
      historical_change: item.historical_change,
      local_percentile: item.local_percentile,
      temporal_anomaly: item.temporal_anomaly,
      spatial_anomaly: item.spatial_anomaly,
      persistence: item.persistence,
      priority_score: item.priority_score,
      priority_level: item.priority_level,
      reasons: item.reasons,
      score_breakdown: item.score_breakdown
    };
    records.push(rec);
  }

  // 2. Add 10 MEDIUM records (HYD_0621 + 9 additional)
  const allMedium = [PRESERVED_RECORDS[3], ...ADDITIONAL_MEDIUM_RECORDS];
  for (const item of allMedium) {
    assignedGridIds.add(item.grid_id);
    const rec = {
      grid_id: item.grid_id,
      lat: item.lat,
      lng: item.lng,
      geometry: createPolygonGeometry(item.lat, item.lng),
      built_up_2020: item.built_up[0],
      built_up_2023: item.built_up[1],
      built_up_2026: item.built_up[2],
      vegetation_2020: item.vegetation[0],
      vegetation_2023: item.vegetation[1],
      vegetation_2026: item.vegetation[2],
      water_2020: item.water[0],
      water_2023: item.water[1],
      water_2026: item.water[2],
      bare_land_2020: item.bare_land[0],
      bare_land_2023: item.bare_land[1],
      bare_land_2026: item.bare_land[2],
      historical_change: item.historical_change,
      local_percentile: item.local_percentile,
      temporal_anomaly: item.temporal_anomaly,
      spatial_anomaly: item.spatial_anomaly,
      persistence: item.persistence,
      priority_score: item.priority_score,
      priority_level: item.priority_level,
      reasons: item.reasons,
      score_breakdown: item.score_breakdown
    };
    records.push(rec);
  }

  // 3. Generate remaining 135 LOW records across Hyderabad regular grid
  const TOTAL_CELLS = 150;
  const NEED_LOW = TOTAL_CELLS - records.length; // 135

  // Grid bounds centered on Hyderabad:
  // Rows = 11, Cols = 13 roughly
  const baseLat = 17.310;
  const baseLng = 78.340;
  const rows = 11;
  const cols = 13;

  let cellIndex = 1;
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (records.length >= TOTAL_CELLS) break;

      const centerLat = +(baseLat + r * DELTA_LAT).toFixed(6);
      const centerLng = +(baseLng + c * DELTA_LNG).toFixed(6);

      // Unique grid_id format: HYD_XXXX
      let grid_id = `HYD_${String(cellIndex * 7 + 100).padStart(4, '0')}`;
      cellIndex++;
      while (assignedGridIds.has(grid_id)) {
        grid_id = `HYD_${String(cellIndex * 7 + 100).padStart(4, '0')}`;
        cellIndex++;
      }
      assignedGridIds.add(grid_id);

      // Score between 8 and 43 for LOW
      const priority_score = randomInt(8, 43);
      const score_breakdown = partitionScore(priority_score, rng);

      // Realistic land cover values for normal/stable cells
      const baseBuilt = +randomInRange(15, 55).toFixed(1);
      const builtGrowth = +randomInRange(0.2, 2.5).toFixed(1);
      const b20 = baseBuilt;
      const b23 = +(b20 + builtGrowth * 0.4).toFixed(1);
      const b26 = +(b20 + builtGrowth).toFixed(1);

      const baseVeg = +randomInRange(20, 60).toFixed(1);
      const vegDrop = +randomInRange(0.1, 1.8).toFixed(1);
      const v20 = baseVeg;
      const v23 = +(v20 - vegDrop * 0.4).toFixed(1);
      const v26 = +(v20 - vegDrop).toFixed(1);

      const w20 = +randomInRange(1.5, 6.0).toFixed(1);
      const w23 = +(w20 - randomInRange(0.0, 0.3)).toFixed(1);
      const w26 = +(w23 - randomInRange(0.0, 0.3)).toFixed(1);

      const bare20 = +(Math.max(0, 100 - b20 - v20 - w20)).toFixed(1);
      const bare23 = +(Math.max(0, 100 - b23 - v23 - w23)).toFixed(1);
      const bare26 = +(Math.max(0, 100 - b26 - v26 - w26)).toFixed(1);

      const historical_change = +randomInRange(0.4, 1.2).toFixed(1);
      const local_percentile = randomInt(5, 68);
      const temporal_anomaly = +randomInRange(0.10, 0.48).toFixed(2);
      const spatial_anomaly = +randomInRange(0.12, 0.50).toFixed(2);
      const persistence = +randomInRange(0.15, 0.55).toFixed(2);

      const reasons = [
        priority_score > 30 ? "Minor seasonal land fluctuation" : "Stable baseline area",
        "Within expected variance"
      ];

      records.push({
        grid_id,
        lat: centerLat,
        lng: centerLng,
        geometry: createPolygonGeometry(centerLat, centerLng),
        built_up_2020: b20,
        built_up_2023: b23,
        built_up_2026: b26,
        vegetation_2020: v20,
        vegetation_2023: v23,
        vegetation_2026: v26,
        water_2020: w20,
        water_2023: w23,
        water_2026: w26,
        bare_land_2020: bare20,
        bare_land_2023: bare23,
        bare_land_2026: bare26,
        historical_change,
        local_percentile,
        temporal_anomaly,
        spatial_anomaly,
        persistence,
        priority_score,
        priority_level: "LOW",
        reasons,
        score_breakdown
      });
    }
  }

  // Sort records: HIGH first, then MEDIUM, then LOW (ordered by priority_score descending)
  records.sort((a, b) => b.priority_score - a.priority_score);

  const doc = {
    meta: {
      source: "mock",
      is_mock: true,
      warning: "DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo.",
      city: "Hyderabad",
      generated_at: "2026-10-08T00:00:00.000Z",
      imagery_years: [2020, 2023, 2026],
      analyzed_cells: records.length
    },
    records
  };

  return doc;
}

// Generates placeholder SVG diagrams that clearly state "MOCK IMAGERY" and do not look photographic
function generatePlaceholderSvg(gridId, year, score, level) {
  const bgColors = {
    HIGH: "#fef2f2",
    MEDIUM: "#fffbeb",
    LOW: "#f0fdf4"
  };
  const borderColors = {
    HIGH: "#dc2626",
    MEDIUM: "#d97706",
    LOW: "#16a34a"
  };

  const bg = bgColors[level] || "#f8fafc";
  const border = borderColors[level] || "#94a3b8";

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 500" width="100%" height="100%">
  <defs>
    <pattern id="gridPattern" width="25" height="25" patternUnits="userSpaceOnUse">
      <path d="M 25 0 L 0 0 0 25" fill="none" stroke="#cbd5e1" stroke-width="0.8"/>
    </pattern>
    <pattern id="hatchPattern" width="10" height="10" patternUnits="userSpaceOnUse">
      <path d="M-1,1 l2,-2 M0,10 l10,-10 M9,11 l2,-2" stroke="#94a3b8" stroke-width="1.2"/>
    </pattern>
  </defs>

  <!-- Technical Canvas Surface -->
  <rect width="500" height="500" fill="${bg}"/>
  <rect width="500" height="500" fill="url(#gridPattern)"/>
  <rect x="8" y="8" width="484" height="484" fill="none" stroke="${border}" stroke-width="2" stroke-dasharray="6,4"/>

  <!-- Prominent Watermark / Mock Badge -->
  <g transform="translate(250, 250) rotate(-35)">
    <rect x="-210" y="-36" width="420" height="72" fill="#ffffff" fill-opacity="0.92" stroke="${border}" stroke-width="2"/>
    <text x="0" y="8" font-family="Inter, -apple-system, sans-serif" font-size="34" font-weight="900" fill="${border}" text-anchor="middle" letter-spacing="4">
      MOCK IMAGERY
    </text>
    <text x="0" y="26" font-family="Inter, -apple-system, sans-serif" font-size="11" font-weight="700" fill="#64748b" text-anchor="middle" letter-spacing="2">
      SYNTHETIC TEST ASSET &bull; NOT SATELLITE PHOTO
    </text>
  </g>

  <!-- Technical Telemetry Header -->
  <rect x="18" y="18" width="464" height="42" fill="#0f172a" rx="4"/>
  <text x="32" y="44" font-family="monospace" font-size="15" font-weight="700" fill="#38bdf8">
    URBANPULSE SYNTHETIC OBSERVATION
  </text>
  <text x="466" y="44" font-family="monospace" font-size="14" font-weight="700" fill="#f8fafc" text-anchor="end">
    EPOCH: ${year}
  </text>

  <!-- Abstract Vector Schematic Blocks -->
  <rect x="36" y="80" width="140" height="120" fill="#3b82f6" fill-opacity="0.25" stroke="#1d4ed8" stroke-width="1.5"/>
  <text x="44" y="100" font-family="monospace" font-size="11" fill="#1e3a8a">SECTOR A: BUILT-UP</text>

  <rect x="190" y="80" width="274" height="120" fill="#22c55e" fill-opacity="0.25" stroke="#15803d" stroke-width="1.5"/>
  <text x="198" y="100" font-family="monospace" font-size="11" fill="#14532d">SECTOR B: VEGETATION</text>

  <rect x="36" y="310" width="210" height="110" fill="#06b6d4" fill-opacity="0.25" stroke="#0e7490" stroke-width="1.5"/>
  <text x="44" y="330" font-family="monospace" font-size="11" fill="#164e63">SECTOR C: WATER BODY</text>

  <rect x="260" y="310" width="204" height="110" fill="url(#hatchPattern)" stroke="#475569" stroke-width="1.5"/>
  <text x="268" y="330" font-family="monospace" font-size="11" fill="#1e293b">SECTOR D: BARE SOIL</text>

  <!-- Coordinate Crosshair -->
  <circle cx="250" cy="250" r="40" fill="none" stroke="${border}" stroke-width="1" stroke-dasharray="3,3"/>
  <line x1="250" y1="190" x2="250" y2="310" stroke="${border}" stroke-width="1"/>
  <line x1="190" y1="250" x2="310" y2="250" stroke="${border}" stroke-width="1"/>

  <!-- Footer Metadata Bar -->
  <rect x="18" y="440" width="464" height="42" fill="#ffffff" stroke="#cbd5e1" rx="4"/>
  <text x="32" y="466" font-family="monospace" font-size="12" fill="#0f172a" font-weight="600">
    GRID ID: ${gridId} &bull; PRIORITY: ${score} (${level})
  </text>
  <text x="466" y="466" font-family="monospace" font-size="11" fill="#64748b" text-anchor="end">
    500m &times; 500m CELL
  </text>
</svg>`;
}

export function writeMockFiles() {
  const dataset = generateMockDataset();

  // 1. Write investigation_list.json
  const invListPath = path.join(MOCK_DIR, 'investigation_list.json');
  fs.writeFileSync(invListPath, JSON.stringify(dataset, null, 2), 'utf-8');
  console.log(`✓ Wrote ${invListPath} (${dataset.records.length} records)`);

  // 2. Write overview.json
  const highCount = dataset.records.filter(r => r.priority_level === 'HIGH').length;
  const mediumCount = dataset.records.filter(r => r.priority_level === 'MEDIUM').length;
  const lowCount = dataset.records.filter(r => r.priority_level === 'LOW').length;

  const overviewDoc = {
    regionId: "hyd-metro-core",
    regionName: "Hyderabad Metropolitan Growth Corridor",
    city: "Hyderabad",
    state: "Telangana",
    center: [17.385, 78.486],
    defaultZoom: 12,
    bounds: [
      [17.25, 78.30],
      [17.55, 78.65]
    ],
    monitoringCycle: "Multi-temporal Satellite Observation",
    observationDates: ["2020-03-15", "2023-03-15", "2026-03-15"],
    latestObservationDate: "2026-03-15",
    baselinePeriod: "2020–2023",
    currentEvaluationPeriod: "2023–2026",
    monitoredCellsCount: dataset.records.length,
    anomalousCellsCount: highCount + mediumCount,
    priorityCounts: {
      high: highCount,
      medium: mediumCount,
      low: lowCount,
      normal: lowCount
    },
    categoryCounts: {
      built_up_expansion: dataset.records.filter(r => r.score_breakdown.urban_expansion > 15).length,
      vegetation_loss: dataset.records.filter(r => r.score_breakdown.vegetation_loss > 12).length,
      water_body_change: dataset.records.filter(r => r.score_breakdown.water_body_change > 0).length,
      bare_land_change: 4
    },
    isMock: true,
    is_mock: true,
    dataSource: "Preloaded development observations (Hyderabad ~500m grid)",
    legalNotice: "Unusual spatial change detected. Field verification recommended."
  };

  const overviewPath = path.join(MOCK_DIR, 'overview.json');
  fs.writeFileSync(overviewPath, JSON.stringify(overviewDoc, null, 2), 'utf-8');
  console.log(`✓ Wrote ${overviewPath}`);

  // 3. Write hotspots.json (top high + medium records)
  const hotspotsList = dataset.records
    .filter(r => r.priority_level === 'HIGH' || r.priority_level === 'MEDIUM')
    .map((r, idx) => ({
      id: r.grid_id,
      rank: idx + 1,
      cellId: r.grid_id,
      grid_id: r.grid_id,
      wardName: `Zone ${r.grid_id.slice(-2)} - Hyderabad`,
      zone: "Hyderabad Urban",
      coordinates: [r.lat, r.lng],
      category: r.score_breakdown.water_body_change > 0
        ? "water_body_change"
        : r.score_breakdown.vegetation_loss > r.score_breakdown.urban_expansion
        ? "vegetation_loss"
        : "built_up_expansion",
      categoryLabel: r.score_breakdown.water_body_change > 0
        ? "Water-body change"
        : r.score_breakdown.vegetation_loss > r.score_breakdown.urban_expansion
        ? "Vegetation loss"
        : "Built-up expansion",
      priorityScore: r.priority_score,
      priority_score: r.priority_score,
      priorityLevel: r.priority_level.toLowerCase(),
      priority_level: r.priority_level,
      anomalyLevel: r.priority_level.toLowerCase(),
      persistence: r.persistence > 0.7 ? "persistent" : "intermittent",
      changeSummary: r.reasons[0] || "Unusual spatial divergence",
      reasons: r.reasons,
      score_breakdown: r.score_breakdown,
      keyMetric: `+${(r.built_up_2026 - r.built_up_2023).toFixed(1)}% built-up`,
      baselineDeviation: `+${r.historical_change}x historical trend`,
      neighborhoodPercentile: `${r.local_percentile}th percentile`,
      lastObservedDate: "2026-03-15",
      recommendation: "Unusual spatial change detected. Field verification recommended."
    }));

  const hotspotsPath = path.join(MOCK_DIR, 'hotspots.json');
  fs.writeFileSync(hotspotsPath, JSON.stringify(hotspotsList, null, 2), 'utf-8');
  console.log(`✓ Wrote ${hotspotsPath} (${hotspotsList.length} hotspots)`);

  // 4. Write cells.json
  const cellsList = dataset.records.map(r => ({
    cellId: r.grid_id,
    grid_id: r.grid_id,
    hotspotId: (r.priority_level === 'HIGH' || r.priority_level === 'MEDIUM') ? r.grid_id : null,
    wardName: `Zone ${r.grid_id.slice(-2)} - Hyderabad`,
    center: [r.lat, r.lng],
    geometry: r.geometry,
    bounds: [
      [r.geometry.coordinates[0][0][1], r.geometry.coordinates[0][0][0]],
      [r.geometry.coordinates[0][2][1], r.geometry.coordinates[0][2][0]]
    ],
    priorityLevel: r.priority_level.toLowerCase(),
    priority_level: r.priority_level,
    priorityScore: r.priority_score,
    priority_score: r.priority_score,
    score_breakdown: r.score_breakdown,
    anomalyStatus: r.priority_level !== 'LOW' ? "flagged" : "normal",
    category: r.score_breakdown.water_body_change > 0 ? "water_body_change" : "built_up_expansion",
    changeMetric: `+${(r.built_up_2026 - r.built_up_2023).toFixed(1)}% built-up`
  }));

  const cellsPath = path.join(MOCK_DIR, 'cells.json');
  fs.writeFileSync(cellsPath, JSON.stringify(cellsList, null, 2), 'utf-8');
  console.log(`✓ Wrote ${cellsPath} (${cellsList.length} cells)`);

  // 5. Write evidence.json for top hotspots
  const evidenceDoc = {};
  for (const h of hotspotsList) {
    const orig = dataset.records.find(r => r.grid_id === h.grid_id);
    evidenceDoc[h.id] = {
      hotspotId: h.id,
      cellId: h.cellId,
      grid_id: h.grid_id,
      wardName: h.wardName,
      coordinates: h.coordinates,
      category: h.category,
      categoryLabel: h.categoryLabel,
      summary: h.changeSummary,
      recommendation: h.recommendation,
      pipeline: {
        change: {
          title: "Observed change",
          metrics: {
            periods: ["2020-03", "2023-03", "2026-03"],
            builtUpPercent: [orig.built_up_2020, orig.built_up_2023, orig.built_up_2026],
            vegetationPercent: [orig.vegetation_2020, orig.vegetation_2023, orig.vegetation_2026],
            waterPercent: [orig.water_2020, orig.water_2023, orig.water_2026],
            bareLandPercent: [orig.bare_land_2020, orig.bare_land_2023, orig.bare_land_2026]
          },
          observedChangeMetric: h.keyMetric
        },
        historicalBaseline: {
          title: "Historical baseline comparison",
          expectedPeriodGrowth: 1.5,
          observedPeriodGrowth: +(orig.built_up_2026 - orig.built_up_2023).toFixed(1),
          deviationSummary: `+${orig.historical_change}x expected baseline rate`
        },
        localBaseline: {
          title: "Local neighborhood baseline",
          neighborhoodPercentile: orig.local_percentile,
          percentileLabel: `${orig.local_percentile}th percentile against neighbors`
        },
        anomaly: {
          title: "Anomaly classification",
          temporalAnomalyScore: Math.round(orig.temporal_anomaly * 100),
          spatialAnomalyScore: Math.round(orig.spatial_anomaly * 100),
          compositeAnomalyLevel: orig.priority_level.toLowerCase(),
          persistenceConfirmed: orig.persistence > 0.7,
          persistenceDetails: `Persistence score: ${orig.persistence}`
        },
        evidence: {
          title: "Observation evidence dossier",
          sensor: "Sentinel-2 MSI Level-2A (Copernicus)",
          imageUrls: {
            "2020": `/data/images/${orig.grid_id}/2020.svg`,
            "2023": `/data/images/${orig.grid_id}/2023.svg`,
            "2026": `/data/images/${orig.grid_id}/2026.svg`
          }
        },
        priority: {
          title: "Explainable priority score",
          totalScore: orig.priority_score,
          priorityLevel: orig.priority_level.toLowerCase(),
          score_breakdown: orig.score_breakdown,
          factorBreakdown: Object.entries(orig.score_breakdown).map(([factor, points]) => ({
            factor: factor.replace(/_/g, ' '),
            points
          }))
        }
      }
    };
  }

  const evidencePath = path.join(MOCK_DIR, 'evidence.json');
  fs.writeFileSync(evidencePath, JSON.stringify(evidenceDoc, null, 2), 'utf-8');
  console.log(`✓ Wrote ${evidencePath}`);

  // 6. Generate placeholder SVGs for top 8 hotspots
  const top8 = dataset.records.slice(0, 8);
  console.log(`\nGenerating placeholder SVGs for top 8 hotspots:`);
  for (const item of top8) {
    const itemDir = path.join(IMAGES_DIR, item.grid_id);
    if (!fs.existsSync(itemDir)) {
      fs.mkdirSync(itemDir, { recursive: true });
    }

    for (const year of [2020, 2023, 2026]) {
      const svgContent = generatePlaceholderSvg(item.grid_id, year, item.priority_score, item.priority_level);
      const svgPath = path.join(itemDir, `${year}.svg`);
      fs.writeFileSync(svgPath, svgContent, 'utf-8');
    }
    console.log(` - ${item.grid_id}: 2020.svg, 2023.svg, 2026.svg (${item.priority_level}, score: ${item.priority_score})`);
  }

  console.log(`\nMock dataset generation finished successfully!`);
}

// Execute when run as CLI
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  writeMockFiles();
}
