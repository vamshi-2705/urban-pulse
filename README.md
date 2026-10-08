# UrbanPulse — Geospatial AI + Intelligence Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-foundation--ready-green.svg)]()

> **Member 1 Responsibility**: Geospatial AI + Intelligence Engine.  
> Converts multi-temporal Sentinel-2 satellite observations into an evidence-backed list of locations deserving field investigation.

---

## Scope & Architectural Boundary

| Member | Domain | Scope |
| :--- | :--- | :--- |
| **Member 1 (This Repository)** | **Geospatial AI Engine** | Satellite acquisition, preprocessing, spatial grid generation, spectral/land-cover indicators, multi-temporal change detection, historical & neighborhood baselines, anomaly detection, persistence analysis, priority scoring, evidence generation, validation. |
| **Member 2** | **Fullstack Application** | Backend REST/GraphQL API, database persistence, authentication, user management, and frontend web dashboards. |

### Core Pipeline
$$\text{Sentinel-2} \longrightarrow \text{Preprocessing} \longrightarrow \text{Fixed Grid} \longrightarrow \text{Indicators} \longrightarrow \text{Change Detection} \longrightarrow \text{Baselines} \longrightarrow \text{Anomaly} \longrightarrow \text{Evidence} \longrightarrow \text{Priority}$$

$$\mathbf{CHANGE \longrightarrow BASELINE \longrightarrow ANOMALY \longrightarrow EVIDENCE \longrightarrow PRIORITY}$$

---

## Target Study Area & Epochs

- **Prototype Area**: Hyderabad, Telangana, India (Focused prototype bounding box: `[78.35, 17.35, 78.55, 17.50]`).
- **CRS**: Geographic `EPSG:4326`, Projected Metric `EPSG:32644` (WGS 84 / UTM Zone 44N).
- **Analysis Epochs**: `2020`, `2023`, `2026` (Dry/clear season observations with cloud threshold $\le 15\%$).
- **Data Source**: Sentinel-2 Level-2A surface reflectance via Microsoft Planetary Computer STAC API.

---

## Project Structure

```
urban-pulse/
├── geospatial/               # Core Geospatial AI Engine
│   ├── __init__.py           # Package exports & version
│   ├── logger.py             # Structured logging utility
│   ├── acquisition/          # STAC querying & asset authentication
│   ├── preprocessing/        # SCL cloud masking & radiometric calibration
│   ├── grid/                 # Deterministic geographic grid tessellation
│   ├── indicators/           # Spectral indices (NDVI/NDWI/NDBI) & land-cover %
│   ├── change_detection/     # Multi-temporal delta calculations (2020-2023-2026)
│   ├── anomaly/              # Temporal & spatial neighborhood baseline anomalies
│   ├── priority/             # Persistence analysis & priority scoring (0-100)
│   ├── evidence/             # Evidence dossier generation for Member 2
│   └── validation/           # Data integrity, boundary, and schema checks
│
├── config/                   # Central Configuration System
│   ├── __init__.py
│   ├── config.yaml           # Central parameter file (AOI, CRS, epochs, thresholds)
│   └── settings.py           # Typed dataclass config loader
│
├── data/                     # Data Lake (gitignored except .gitkeep)
│   ├── raw/                  # Cached satellite observations & scenes
│   ├── processed/            # Masked arrays, index layers, and cell aggregations
│   └── outputs/              # Exported priority ranking & evidence JSON/GeoJSON
│
├── scripts/                  # Operational & Verification Scripts
│   ├── __init__.py
│   └── verify_environment.py # End-to-end environment & config checker
│
├── tests/                    # Automated Test Suite
│   ├── __init__.py
│   ├── test_config.py        # Central config tests
│   ├── test_imports.py       # Module imports and integrity tests
│   └── test_logger.py        # Logging utility tests
│
├── docs/                     # Architectural & Technical Specifications
│   └── ARCHITECTURE.md
│
├── .gitignore                # Geospatial and Python ignore patterns
├── requirements.txt          # Minimal Python dependencies
└── README.md
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- Git

### 2. Virtual Environment Setup

#### Windows (PowerShell):
```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

#### macOS / Linux (Bash):
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Verification & Testing

### Run Foundation Verification Script
Verifies configuration loading, directory availability, submodule imports, and library health:
```bash
python scripts/verify_environment.py
```

### Run Test Suite
Executes unit tests verifying configuration schemas, subpackage imports, and logging:
```bash
pytest -v
```

---

## Configuration System

All parameters are centrally governed by [`config/config.yaml`](config/config.yaml) and loaded into typed Python structures through [`config/settings.py`](config/settings.py). 

Never hardcode coordinates, thresholds, or directories into processing scripts.

```python
from config.settings import get_config

cfg = get_config()
print(cfg.study_area.name)            # "Hyderabad_Prototype"
print(cfg.study_area.bbox)            # [78.35, 17.35, 78.55, 17.50]
print(cfg.time_periods.years)         # [2020, 2023, 2026]
print(cfg.satellite.cloud_cover_max_percent) # 15.0
```

---

## Data Contract (Output Schema for Member 2)

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

---

## Engineering Rules
1. **Independent Modules**: Subpackages communicate strictly via well-defined inputs and outputs.
2. **Deterministic & Reproducible**: Fixed grid cell identifiers across all temporal points.
3. **No Fabricated Data**: If clouds or missing observations occur, flag them gracefully. Real data only.
4. **Structured Logging**: Consistent timestamps, levels, and output destinations.
