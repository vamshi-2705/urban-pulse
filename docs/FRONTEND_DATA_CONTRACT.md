# UrbanPulse — Frontend Data Contract & Integration Reference

> **Document Status:** Authoritative & Locked (Handoff Package for Member 2)  
> **Source Engine:** Member 1 — Geospatial AI & Intelligence Engine  
> **Target Audience:** Member 2 — Frontend & Backend Engineering  
> **Target System:** Web Application / Dashboards (FastAPI / Express / React / Leaflet)  
> **Validation Status:** Verified via `scripts/verify_frontend_contract.py` (Exit Code 0)

---

## 1. Executive Summary & Purpose

This document provides the definitive data contract for Member 2 to consume real geospatial intelligence produced by the UrbanPulse engine. 

All intelligence outputs are generated from real **Sentinel-2 L2A** multispectral imagery over the Hyderabad metropolitan study area. No data or coordinates in this contract are synthetic, mocked, or randomized.

### Critical Guidelines for Member 2
1. **Zero Guesswork:** All file paths, field names, data types, value ranges, and coordinate systems are explicitly defined below.
2. **Pre-computed Intelligence:** All scores, anomalies, why-flagged explanations, GeoJSON features, and evidence assets are pre-computed and stored in `data/outputs/api/` and `data/outputs/evidence/`. Member 2 does not need to run geospatial algorithms.
3. **Evidence Assets are UI Previews:** Evidence PNGs (`100x100` pixels covering a `1000m x 1000m` window around each hotspot) are optimized web previews. Frontend dashboards should consume these PNGs directly rather than attempting to download large multi-band scientific GeoTIFFs.
4. **Coordinate Ordering:** All GeoJSON geometry coordinates strictly follow standard GeoJSON (RFC 7946) order: `[longitude, latitude]`.

---

## 2. Period Contract & Actual Acquisition Dates

UrbanPulse tracks land-cover transitions across three observation snapshots. These represent **actual satellite acquisition dates and timestamps**, not generic yearly averages or synthetic composites.

| Period Identifier | Before Date (UTC) | After Date (UTC) | Satellite Sensor | Primary Role / Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| `2020_2026` | `2020-03-29T05:06:51.024000+00:00` | `2026-03-10T05:12:41.024000+00:00` | Sentinel-2 L2A | **Primary Benchmark:** Long-term 6-year structural land-cover transition. |
| `2020_2023` | `2020-03-29T05:06:51.024000+00:00` | `2023-01-28T05:10:49.024000+00:00` | Sentinel-2 L2A | **First Interval:** Baseline to mid-term transition (3-year interval). |
| `2023_2026` | `2023-01-28T05:10:49.024000+00:00` | `2026-03-10T05:12:41.024000+00:00` | Sentinel-2 L2A | **Second Interval:** Mid-term to recent transition (3-year interval). |

### Supported Evidence Assets for Each Period
For every flagged hotspot cell within any of the three periods, the following visual evidence files are generated on disk under `data/outputs/evidence/{period}/{grid_id}/`:
1. `before_rgb.png`: Natural true-color RGB at `before_date`
2. `after_rgb.png`: Natural true-color RGB at `after_date`
3. `ndvi_before.png`: Photosynthetic vegetation canopy at `before_date`
4. `ndvi_after.png`: Photosynthetic vegetation canopy at `after_date`
5. `ndvi_change.png`: Canopy change map ($\Delta\text{NDVI}$)
6. `ndwi_change.png`: Surface moisture change map ($\Delta\text{NDWI}$)
7. `ndbi_change.png`: Built-up reflectance change map ($\Delta\text{NDBI}$)
8. `combined_change.png`: Categorical multi-spectral evidence synthesis map
9. `metadata.json`: Machine-readable window bounding box, UTM transform, CRS (`EPSG:32644`), and exact pixel metrics

---

## 3. Data Entities & Field Specifications

### 3.1. City Summary Contract
- **File Location:** `data/outputs/api/city_summary_{period}.json`
- **Purpose:** Supplies aggregate high-level metrics for the entire Hyderabad study area (1,462 cells of 500m x 500m grid).

| Field Name | Type | Meaning / Description | Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `period` | `string` | Analysis interval (`2020_2026`, `2020_2023`, `2023_2026`) | `"2020_2026"` | **Required** |
| `total_cells` | `integer` | Total number of 500m grid cells in the AOI | `1462` | **Required** |
| `high_priority` | `integer` | Count of cells flagged as `HIGH` priority (score $\ge 0.70$) | `27` | **Required** |
| `medium_priority` | `integer` | Count of cells flagged as `MEDIUM` priority ($0.45 \le \text{score} < 0.70$) | `453` | **Required** |
| `low_priority` | `integer` | Count of cells flagged as `LOW` priority (score $< 0.45$) | `982` | **Required** |
| `score_median` | `float` | 50th percentile of priority scores across all cells | `0.4107` | **Required** |
| `score_p95` | `float` | 95th percentile priority score across all cells | `0.6172` | **Required** |
| `top_hotspots` | `array[object]` | Pre-compiled list of top 25 priority hotspots (each follows Hotspot Record schema) | `[...]` | **Required** |

---

### 3.2. Hotspot List & Individual Hotspot Record Contract
- **Full Catalog:** `data/outputs/api/hotspots_{period}.json` (1,462 records)
- **Top Subsets:** `data/outputs/api/top_10_{period}.json`, `top_25_{period}.json`, `top_50_{period}.json`

| Field Name | Type | Meaning / Description | Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `rank` | `integer` | Priority rank within the selected period (1 = highest priority) | `1` | **Required** |
| `grid_id` | `string` | Stable unique 500m grid cell identifier (`HYD_xxxx`) | `"HYD_1220"` | **Required** |
| `period` | `string` | Observation period identifier | `"2020_2026"` | **Required** |
| `latitude` | `float` | Centroid latitude in WGS 84 degrees | `17.372285` | **Required** |
| `longitude` | `float` | Centroid longitude in WGS 84 degrees | `78.422560` | **Required** |
| `priority` | `object` | Structured priority score, level, and human recommendation | *See 3.3* | **Required** |
| `reasons` | `array[string]` | Machine-readable rule codes triggered by this hotspot | `["HIGH_SCENE_ANOMALY", ...]` | **Required** |
| `anomaly` | `object` | Anomaly magnitude signals | *See 3.4* | **Required** |
| `evidence` | `object` | Boolean evidence flags | *See 3.5* | **Required** |
| `change` | `object` | Physical spectral index deltas ($\Delta\text{NDVI}, \Delta\text{NDWI}, \Delta\text{NDBI}$) | *See 3.6* | **Required** |
| `why_flagged` | `object` | Scientifically cautious human headline and factor breakdown | *See 3.7* | **Required** |
| `assets` | `object` | Relative paths to visual evidence PNG files and metadata | *See 3.8* | **Optional** (Present for top candidate hotspots) |

---

### 3.3. Priority Object (`priority`)
| Field Name | Type | Meaning / Description | Allowed Values / Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `score` | `float` | Explainable priority score $[0.0, 1.0]$ | `0.8200` | **Required** |
| `level` | `string` | Priority classification tier | `"HIGH"`, `"MEDIUM"`, `"LOW"` | **Required** |
| `recommendation` | `string` | Operational municipal action recommendation | `"FIELD_VERIFICATION_RECOMMENDED"`, `"MONITOR_AND_REVIEW"`, `"ROUTINE_OBSERVATION"` | **Required** |

---

### 3.4. Anomaly Object (`anomaly`)
| Field Name | Type | Meaning / Description | Range / Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `overall` | `float` | Fused scene-level change anomaly across spectral indicators | $[0.0, 1.0]$, e.g. `0.9639` | **Required** |
| `ndvi` | `float` | Scene-level vegetation change anomaly magnitude | $[0.0, 1.0]$, e.g. `0.8929` | **Required** |
| `ndwi` | `float` | Scene-level water/moisture change anomaly magnitude | $[0.0, 1.0]$, e.g. `0.9121` | **Required** |
| `ndbi` | `float` | Scene-level built-up change anomaly magnitude | $[0.0, 1.0]$, e.g. `0.8823` | **Required** |
| `spatial` | `float` | Local spatial context anomaly ($15\times15$ kernel deviation) | $[0.0, 1.0]$, e.g. `1.0000` | **Optional** |

---

### 3.5. Evidence Object (`evidence`)
| Field Name | Type | Meaning / Description | Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `vegetation_loss` | `boolean` | `true` if $\Delta\text{NDVI} \le -0.15$ | `true` | **Required** |
| `water_change` | `boolean` | `true` if $\|\Delta\text{NDWI}\| \ge 0.15$ | `true` | **Required** |
| `builtup_change` | `boolean` | `true` if $\Delta\text{NDBI} \ge +0.15$ | `true` | **Required** |
| `veg_builtup_coherence` | `boolean` | `true` if vegetation drop coincides with built-up increase | `true` | **Required** |
| `persistent_change` | `boolean` | `true` if directional change continues across multiple epochs | `true` | **Required** |
| `cyclical_reversal` | `boolean` | `true` if change reversed direction (dampens priority) | `true` | **Required** |

---

### 3.6. Change Object (`change`)
| Field Name | Type | Meaning / Description | Range / Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `ndvi_delta` | `float` | Mean difference in NDVI ($\text{NDVI}_{\text{after}} - \text{NDVI}_{\text{before}}$) | $[-2.0, +2.0]$, e.g. `-0.5543` | **Required** |
| `ndwi_delta` | `float` | Mean difference in NDWI ($\text{NDWI}_{\text{after}} - \text{NDWI}_{\text{before}}$) | $[-2.0, +2.0]$, e.g. `+0.1043` | **Required** |
| `ndbi_delta` | `float` | Mean difference in NDBI ($\text{NDBI}_{\text{after}} - \text{NDBI}_{\text{before}}$) | $[-2.0, +2.0]$, e.g. `+0.2766` | **Required** |

---

### 3.7. Why Flagged Object (`why_flagged`)
| Field Name | Type | Meaning / Description | Example | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `headline` | `string` | Scientifically cautious human headline | `"Strong and persistent land-cover change"` | **Required** |
| `factors` | `array[object]` | Factor list containing `code` and human-readable `description` | *See below* | **Required** |

Each item in `factors` has:
- `code` (`string`, required): Standard reason code (e.g. `"HIGH_SCENE_ANOMALY"`).
- `description` (`string`, required): Scientifically cautious description (e.g. `"Observed spectral change is unusually strong relative to the scene distribution."`).

---

### 3.8. Evidence Assets Object (`assets`)
| Field Name | Type | Meaning / Description | Example Relative Path | Required? |
| :--- | :--- | :--- | :--- | :--- |
| `before_rgb` | `string` | Natural true color preview prior to intervention | `"data/outputs/evidence/2020_2026/HYD_1220/before_rgb.png"` | **Required in assets** |
| `after_rgb` | `string` | Natural true color preview post intervention | `"data/outputs/evidence/2020_2026/HYD_1220/after_rgb.png"` | **Required in assets** |
| `ndvi_before` | `string` | Photosynthetic canopy preview at before date | `"data/outputs/evidence/2020_2026/HYD_1220/ndvi_before.png"` | **Required in assets** |
| `ndvi_after` | `string` | Photosynthetic canopy preview at after date | `"data/outputs/evidence/2020_2026/HYD_1220/ndvi_after.png"` | **Required in assets** |
| `ndvi_change` | `string` | Diverging canopy difference map ($\Delta\text{NDVI}$) | `"data/outputs/evidence/2020_2026/HYD_1220/ndvi_change.png"` | **Required in assets** |
| `ndwi_change` | `string` | Diverging surface moisture difference map ($\Delta\text{NDWI}$) | `"data/outputs/evidence/2020_2026/HYD_1220/ndwi_change.png"` | **Required in assets** |
| `ndbi_change` | `string` | Diverging built-up difference map ($\Delta\text{NDBI}$) | `"data/outputs/evidence/2020_2026/HYD_1220/ndbi_change.png"` | **Required in assets** |
| `combined_change` | `string` | Categorical multi-indicator synthesis preview | `"data/outputs/evidence/2020_2026/HYD_1220/combined_change.png"` | **Required in assets** |
| `metadata` | `string` | JSON file with bounding box, UTM transform, & pixel counts | `"data/outputs/evidence/2020_2026/HYD_1220/metadata.json"` | **Required in assets** |

---

## 4. Canonical Hotspot Example: `HYD_1220` (Actual Generated Values)

This is the exact JSON record for the primary recommended demo hotspot `HYD_1220` in `data/outputs/api/top_10_2020_2026.json`:

```json
{
  "rank": 1,
  "grid_id": "HYD_1220",
  "period": "2020_2026",
  "latitude": 17.372285,
  "longitude": 78.42256,
  "priority": {
    "score": 0.82,
    "level": "HIGH",
    "recommendation": "FIELD_VERIFICATION_RECOMMENDED"
  },
  "reasons": [
    "HIGH_SCENE_ANOMALY",
    "SPATIAL_ANOMALY",
    "VEG_BUILTUP_COHERENCE",
    "VEGETATION_LOSS",
    "BUILTUP_SENSITIVE_CHANGE",
    "PERSISTENT_CHANGE",
    "STRONG_CHANGE_MAGNITUDE",
    "CYCLICAL_REVERSAL_DAMPENED"
  ],
  "anomaly": {
    "overall": 0.9639,
    "ndvi": 0.8929,
    "ndwi": 0.9121,
    "ndbi": 0.8823,
    "spatial": 1.0
  },
  "evidence": {
    "vegetation_loss": true,
    "water_change": true,
    "builtup_change": true,
    "veg_builtup_coherence": true,
    "persistent_change": true,
    "cyclical_reversal": true
  },
  "change": {
    "ndvi_delta": -0.5543,
    "ndwi_delta": 0.1043,
    "ndbi_delta": 0.2766
  },
  "why_flagged": {
    "headline": "Strong and persistent land-cover change",
    "factors": [
      {
        "code": "HIGH_SCENE_ANOMALY",
        "description": "Observed spectral change is unusually strong relative to the scene distribution."
      },
      {
        "code": "SPATIAL_ANOMALY",
        "description": "Spectral change sharply deviates from the surrounding 15x15 pixel local context."
      },
      {
        "code": "VEG_BUILTUP_COHERENCE",
        "description": "Vegetation decrease coincides with built-up-sensitive spectral increase."
      },
      {
        "code": "VEGETATION_LOSS",
        "description": "Substantial reduction in photosynthetic canopy (NDVI delta <= -0.15)."
      },
      {
        "code": "BUILTUP_SENSITIVE_CHANGE",
        "description": "Substantial increase in shortwave-infrared impervious surface reflectance (NDBI delta >= 0.15)."
      },
      {
        "code": "PERSISTENT_CHANGE",
        "description": "The directional change persists across available multi-year observations."
      },
      {
        "code": "STRONG_CHANGE_MAGNITUDE",
        "description": "Extreme physical spectral displacement across one or more indicator bands."
      },
      {
        "code": "CYCLICAL_REVERSAL_DAMPENED",
        "description": "Directional turnaround detected across observation intervals; priority dampened for potential cyclical variation."
      }
    ]
  },
  "assets": {
    "before_rgb": "data/outputs/evidence/2020_2026/HYD_1220/before_rgb.png",
    "after_rgb": "data/outputs/evidence/2020_2026/HYD_1220/after_rgb.png",
    "ndvi_before": "data/outputs/evidence/2020_2026/HYD_1220/ndvi_before.png",
    "ndvi_after": "data/outputs/evidence/2020_2026/HYD_1220/ndvi_after.png",
    "ndvi_change": "data/outputs/evidence/2020_2026/HYD_1220/ndvi_change.png",
    "ndwi_change": "data/outputs/evidence/2020_2026/HYD_1220/ndwi_change.png",
    "ndbi_change": "data/outputs/evidence/2020_2026/HYD_1220/ndbi_change.png",
    "combined_change": "data/outputs/evidence/2020_2026/HYD_1220/combined_change.png",
    "metadata": "data/outputs/evidence/2020_2026/HYD_1220/metadata.json"
  }
}
```

---

## 5. Evidence Path Contract & Separation of Concerns

### 5.1. UI Previews vs. Scientific Rasters
- **UI Preview PNG Assets (`data/outputs/evidence/{period}/{grid_id}/`)**:
  - Format: Standard 8-bit RGB/RGBA PNG images (~50–120 KB each).
  - Spatial Coverage: $1000\text{m} \times 1000\text{m}$ bounding window around the hotspot centroid ($100 \times 100$ pixels at Sentinel-2's $10\text{m}$ resolution).
  - Designed for instantaneous loading in web browsers, dashboard cards, modal carousels, and image comparisons.
- **Scientific Rasters (`data/outputs/rasters/`)**:
  - Format: Multi-megabyte 16-bit unsigned integer and 32-bit floating-point GeoTIFFs containing raw reflectance and full scene index arrays.
  - **Important for Member 2:** The frontend UI should **NEVER** attempt to load or parse these heavy scientific GeoTIFFs directly. All visual verification is completely served by the PNG evidence previews.

### 5.2. Relative Path Resolution
All path strings stored in `record.assets` or `demo_manifest.json` are formatted relative to the repository workspace root:
```javascript
// Example frontend/backend path resolver:
const assetUrl = `/static/${record.assets.before_rgb}`;
// or serving static files from the repository root:
// http://localhost:8000/data/outputs/evidence/2020_2026/HYD_1220/before_rgb.png
```

---

## 6. GeoJSON Contract & Coordinate Ordering (Leaflet / MapLibre)

### 6.1. Standard RFC 7946 GeoJSON Structure
- **File Location:** `data/outputs/api/hotspots_{period}.geojson`
- Every file contains a root `FeatureCollection` with exactly 1,462 `Feature` records representing the 500m study grid.

```json
{
  "type": "FeatureCollection",
  "period": "2020_2026",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [
          78.42256,
          17.372285
        ]
      },
      "properties": {
        "grid_id": "HYD_1220",
        "rank": 1,
        "priority_score": 0.82,
        "priority_level": "HIGH",
        "recommendation": "FIELD_VERIFICATION_RECOMMENDED",
        "period": "2020_2026",
        "reasons": [
          "HIGH_SCENE_ANOMALY",
          "SPATIAL_ANOMALY",
          "VEG_BUILTUP_COHERENCE",
          "VEGETATION_LOSS",
          "BUILTUP_SENSITIVE_CHANGE",
          "PERSISTENT_CHANGE",
          "STRONG_CHANGE_MAGNITUDE",
          "CYCLICAL_REVERSAL_DAMPENED"
        ],
        "overall_anomaly": 0.9639,
        "headline": "Strong and persistent land-cover change"
      }
    }
  ]
}
```

### 6.2. Explicit Coordinate Ordering: `[longitude, latitude]`
- In compliance with RFC 7946, the `geometry.coordinates` array **MUST ALWAYS BE**:
  $$\text{coordinates} = [\text{longitude}, \text{latitude}]$$
- In Leaflet, passing GeoJSON directly via `L.geoJSON(geojsonLayer)` handles `[lon, lat]` automatically. If creating individual markers manually via `L.marker([lat, lon])`, note that Leaflet expects `[latitude, longitude]`.
- **All coordinates are strictly verified within:**
  - Longitude: $[78.349, 78.551]$ (within global $[-180, 180]$)
  - Latitude: $[17.349, 17.501]$ (within global $[-90, 90]$)

---

## 7. Frontend UI Demo Flow & Field Mapping

This section outlines how Member 2's frontend screens should map directly to contract fields:

```
[CITY OVERVIEW]
      ↓
[HOTSPOT MAP]
      ↓ (User clicks a hotspot marker)
[HOTSPOT DETAIL]
      ↓
[WHY FLAGGED?]
      ↓
[EVIDENCE VIEW (Side-by-Side Before/After & Change Map)]
      ↓
[OPERATIONAL PRIORITY & RECOMMENDATION]
```

### Screen 1: City Overview
- **Data Source:** `data/outputs/api/city_summary_{period}.json`
- **Fields Used:**
  - `total_cells`: Total inspected area ($1,462 \times 0.25\text{ km}^2 \approx 365.5\text{ km}^2$).
  - `high_priority`, `medium_priority`, `low_priority`: Stat cards and priority breakdown donut/bar chart.
  - `score_median`, `score_p95`: Statistical benchmark cards for baseline vs. anomaly distribution.
  - `top_hotspots`: Quick-access ranked leaderboard list.

### Screen 2: Hotspot Map (Interactive Leaflet/MapLibre View)
- **Data Source:** `data/outputs/api/hotspots_{period}.geojson`
- **Fields Used:**
  - `geometry.coordinates`: Marker placements `[lon, lat]`.
  - `properties.priority_level`: Marker pin color:
    - `HIGH`: Crimson Red (`#E53E3E`)
    - `MEDIUM`: Amber Orange (`#DD6B20`)
    - `LOW`: Slate Gray / Blue (`#718096`)
  - `properties.priority_score`: Marker size or tooltip ranking.
  - `properties.headline`: Tooltip on hover.
  - `properties.grid_id`: Selected state key on click.

### Screen 3: Hotspot Detail & Why Flagged
- **Data Source:** Selected item from `top_{k}_{period}.json` or `hotspots_{period}.json`
- **Fields Used:**
  - `grid_id`, `rank`, `latitude`, `longitude`: Header bar.
  - `why_flagged.headline`: Primary banner title.
  - `why_flagged.factors`: Factor card list showing each factor `code` badge and human-readable `description`.
  - `change.ndvi_delta`, `change.ndbi_delta`, `change.ndwi_delta`: Spectral indicator change gauges.

### Screen 4: Visual Evidence View (Before / After & Change Map)
- **Data Source:** `record.assets`
- **Fields Used:**
  - `assets.before_rgb` vs. `assets.after_rgb`: Interactive slider or side-by-side true-color image comparison.
  - `assets.combined_change`: Categorical change classification map (vegetation loss, built-up increase, coherent conversion).
  - `assets.ndvi_change`, `assets.ndbi_change`: Spectral indicator difference maps for in-depth inspection.

### Screen 5: Priority & Operational Recommendation
- **Data Source:** `record.priority`
- **Fields Used:**
  - `priority.score`: Radial progress bar or score gauge (e.g. `82%`).
  - `priority.level`: Prominent badge (`HIGH`).
  - `priority.recommendation`: Action box (`FIELD_VERIFICATION_RECOMMENDED`).

---

## 8. Demo Hotspot Roster

For presentation or demonstration walkthroughs, Member 2 should highlight the following pre-validated candidate cells from `data/outputs/api/demo_manifest.json`:

| Hotspot ID | Status | Rank | Score | Level | Latitude | Longitude | Key Transition Narrative |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`HYD_1220`** | **Primary Recommended** | 1 | `0.8200` | `HIGH` | `17.372285` | `78.422560` | **Canonical site:** Severe canopy drop ($\Delta\text{NDVI} = -0.5543$) with impervious increase ($\Delta\text{NDBI} = +0.2766$), multi-year persistence, and maximum spatial contrast. |
| **`HYD_1223`** | **Backup 1** | 2 | `0.8042` | `HIGH` | `17.372466` | `78.436666` | Adjacent expansion corridor cell exhibiting coherent conversion and multi-year persistence. |
| **`HYD_0863`** | **Backup 2** | 3 | `0.8036` | `HIGH` | `17.407605` | `78.360919` | North-western peri-urban zone hotspot exhibiting pronounced spectral deviation and vegetation clearing. |
| **`HYD_1200`** | **Backup 3** | 4 | `0.8010` | `HIGH` | `17.378174` | `78.530650` | Eastern development corridor hotspot demonstrating significant land-cover displacement and surface moisture alteration. |

---

## 9. Verification & Quality Assurance

Member 2 can verify the integrity of the data package at any time by executing:
```bash
python scripts/verify_frontend_contract.py
```
A successful validation output will confirm:
```text
UrbanPulse Frontend Contract Validation
----------------------------------------
API contracts:         PASS
GeoJSON:               PASS
Evidence manifest:     PASS
Evidence assets:       PASS
Coordinates:           PASS
Priority scores:       PASS
Periods:               PASS
Demo hotspots:         PASS

Recommended demo hotspot:
HYD_1220

Status: READY
```
