# UrbanPulse - Geospatial AI + Intelligence Engine Architecture

## 1. Overview & Team Scope

**UrbanPulse** analyzes multi-temporal satellite observations and transforms them into an evidence-backed list of locations deserving field investigation.

### Ownership Boundary
- **Member 1 (This Repository / Engine):** Geospatial AI + Intelligence Engine.
  - Satellite data acquisition & preprocessing (Sentinel-2 L2A via STAC / Planetary Computer).
  - Fixed geographic grid tessellation & coordinate handling.
  - Spectral indicators (NDVI, NDWI, NDBI) and physical land-cover fractions (built-up, vegetation, water, bare).
  - Multi-temporal comparison across epochs (2020, 2023, 2026).
  - Baseline construction (historical per cell + spatial neighborhood).
  - Anomaly detection (temporal deviations + spatial outliers).
  - Persistence analysis & Priority scoring (0-100).
  - Evidence dossier generation & validation.
- **Member 2 (Downstream Consumer):**
  - Backend API server.
  - Database persistence.
  - User authentication and role-based access.
  - Web dashboards and UI mapping components.

---

## 2. Core Processing Pipeline

```
Sentinel-2 L2A (STAC / Planetary Computer)
    │
    ▼
Preprocessing (SCL cloud masking, radiometric scaling, AOI clip)
    │
    ▼
Fixed Geographic Grid (e.g., HYD_0001, 500m cells)
    │
    ▼
Spectral & Land-Cover Indicators (NDVI, NDWI, NDBI, Land-cover %)
    │
    ▼
Multi-Temporal Change Detection (2020 ➔ 2023 ➔ 2026)
    │
    ├── Historical Baseline (Time-series per cell)
    └── Local / Neighborhood Baseline (Spatial context lag)
    │
    ▼
Anomaly Detection (Temporal shifts & spatial anomalies)
    │
    ▼
Evidence Generation (Auditable metrics, trajectory profiles)
    │
    ▼
Priority Scoring (Persistence check, urgency rank 0-100)
    │
    ▼
Export to Member 2 (JSON / GeoJSON Schema)
```

The guiding paradigm:
$$\text{CHANGE} \longrightarrow \text{BASELINE} \longrightarrow \text{ANOMALY} \longrightarrow \text{EVIDENCE} \longrightarrow \text{PRIORITY}$$

---

## 3. Data Model & Downstream Contract

Each processed grid observation follows the strict target schema consumed by Member 2:

```json
{
  "grid_id": "HYD_0421",
  "lat": 17.385,
  "lng": 78.486,
  "date": "2026-09-15",
  "built_up": 47.2,
  "vegetation": 31.4,
  "water": 4.8,
  "bare": 16.6
}
```

### Invariants:
1. **Never fabricate data**: Missing or obscured observations are flagged with cloud/quality metadata; values are never synthetically guessed or fabricated.
2. **Deterministic Identifiers**: `grid_id` remains constant across all temporal epochs.
3. **Reproducibility**: Standardized CRS transformations (WGS84 `EPSG:4326` for lat/lng; UTM Zone 44N `EPSG:32644` for metric distance & area).

---

## 4. Directory & Module Responsibilities

```
geospatial/
├── acquisition/       # STAC queries, scene discovery, asset signing
├── preprocessing/     # Cloud masking (SCL), radiometric calibration, clipping
├── grid/              # Tessellation generation, spatial indexing, centroid math
├── indicators/        # Index calculation (NDVI, NDWI, NDBI) and land-cover fractioning
├── change_detection/  # Multi-temporal delta computation across 2020, 2023, 2026
├── anomaly/           # Deviation metrics from historical & neighborhood baselines
├── priority/          # Persistence filtering, multi-factor weighting, priority ranking
├── evidence/          # Dossier assembly and payload formatting for Member 2
├── validation/        # Coordinate boundary checks, sum checks, schema validation
└── logger.py          # Centralized structured logging

config/
├── config.yaml        # Single source of truth for AOI, dates, thresholds, paths
└── settings.py        # Typed Python dataclass configuration loader
```
