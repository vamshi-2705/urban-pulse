# UrbanPulse

> **Evidence-Based Urban Change & Field Investigation Intelligence**  
> Decision-support software for municipal corporations and urban planning authorities.

---

## 1. Product Overview

UrbanPulse is a decision-support platform designed to help municipal authorities answer a critical operational question:

> **Where should a city deploy limited field-inspection resources first?**

Rather than asking municipal planners to manually scan expansive satellite maps or sift through thousands of routine land-cover shifts, UrbanPulse prioritizes locations showing **unusual, persistent, and localized spatial change**.

### The Core Evidence Pipeline
UrbanPulse presents an explicit, transparent 7-stage chain:
```
CHANGE → HISTORICAL BASELINE → LOCAL BASELINE → ANOMALY → EVIDENCE → PRIORITY → INVESTIGATION LIST
```
1. **Change**: Multi-temporal land-cover indicators observed across monitoring cycles (built-up expansion, vegetation loss, water-body contraction, bare land change).
2. **Historical Baseline**: Compares current change rates against the cell's multi-year historical trajectory (2020–2023).
3. **Local Baseline**: Compares change against immediate neighborhood cells (500m radius) to isolate local divergence from regional trends.
4. **Anomaly**: Flags statistically significant divergence and confirms multi-temporal persistence across observation epochs.
5. **Evidence**: Retains verifiable observation records (dates, cloud scores, deltas, percentiles) in an inspectable dossier.
6. **Priority**: Transparent additive factor weights generate an explainable ranking score without black-box adjustments.
7. **Investigation List**: Delivers a high-confidence, ranked queue for field inspector deployment.

---

## 2. Hard Governance Rules & Boundaries

UrbanPulse adheres strictly to established ethical and system boundaries:

1. **No Client or Backend Recalculation**: Anomaly scores, priority scores, and priority levels are **never calculated or adjusted** in the backend or frontend. The system displays what the precomputed data contains.
2. **No Satellite Processing Algorithms**: Zero satellite image processing, NDVI/NDWI/NDBI calculations, or anomaly algorithms are executed in this full-stack interface layer.
3. **Isolated Mock Provider**: Mock data lives exclusively in `data/mock/` and is served solely by `backend/src/providers/mockProvider.js`. While mock data is active, the UI renders the persistent **"Development data"** banner.
4. **Standard Defensible Language**: The system never claims "illegal construction detection", "building-level detection", "flood prediction", "real-time monitoring", or "enforcement decisions". The standardized directive is:
   > *"Unusual spatial change detected. Field verification recommended."*
5. **Approved Technology Stack**: React + Vite (JavaScript), React Leaflet, Express, plain CSS tokens. No arbitrary frameworks, microservices, Tailwind, or component libraries.
6. **Geospatial Decision-Support Aesthetic**: Professional light neutral theme, strong hierarchy, sentence-case labels, restrained motion.
   - **Green** = Normal (`#15803d`)
   - **Amber** = Medium priority (`#b45309`)
   - **Red** = High priority (`#b91c1c`)
   - Tokenized in `frontend/src/styles.css`.
7. **Reliability Over Cleverness**: All data is preloaded synchronously into memory at server startup for deterministic, sub-millisecond responses.

---

## 3. Architecture & Repository Structure

```
urban-pulse/
├── data/
│   ├── images/                         # Watermarked placeholder SVGs (top 8 hotspots)
│   └── mock/                           # Preloaded mock datasets
│       ├── overview.json               # Monitored region summary & baseline dates
│       ├── pipeline.json               # 7-stage evidence pipeline definition
│       ├── hotspots.json               # Ranked field investigation queue
│       ├── evidence.json               # Full multi-epoch evidence dossiers
│       ├── cells.json                  # Monitored grid cells with bounds
│       └── investigation_list.json     # Standard 150-cell intelligence dataset
├── backend/
│   ├── package.json
│   ├── db/
│   │   └── schema.sql                  # PostgreSQL DDL (urban_observations, evidence, hotspots)
│   ├── scripts/
│   │   └── import.js                   # Idempotent intelligence JSON importer
│   └── src/
│       ├── server.js                   # Express REST API (Port 5001)
│       ├── routes/
│       │   └── api.js                  # Modular REST routes
│       ├── services/
│       │   └── dataService.js          # Business logic and metric difference layer
│       └── providers/
│           ├── index.js                # Provider factory & environment selector
│           ├── mockProvider.js         # In-memory mock data loader
│           ├── fileProvider.js         # Direct filesystem JSON provider
│           └── postgresProvider.js     # PostgreSQL persistent provider (pg pool)
├── frontend/
│   ├── package.json
│   ├── vite.config.js                  # Vite dev server with /api proxy (Port 3000)
│   ├── index.html                      # HTML template with Inter typography
│   └── src/
│       ├── main.jsx                    # Application entry
│       ├── App.jsx                     # Root application coordinator
│       ├── styles.css                  # Design tokens & semantic classes
│       ├── api/
│       │   └── client.js               # Centralized fetch API client
│       └── components/
│           ├── DevelopmentDataBanner.jsx # Persistent mock data banner
│           ├── Header.jsx              # Municipal brand masthead
│           ├── PipelineBreadcrumb.jsx  # Obvious 7-stage chain visualization
│           ├── CityOverviewBar.jsx     # High-level regional KPI metrics
│           └── Phase1Dashboard.jsx     # Investigation list & evidence inspector
├── package.json                        # Root workspace scripts & concurrency
└── README.md
```

---

## 4. Persistence & Data Providers

UrbanPulse supports three decoupled data providers via the `DATA_PROVIDER` environment variable:

| Provider | `DATA_PROVIDER` | Description |
| :--- | :--- | :--- |
| **Mock** *(Default)* | `mock` (or unset) | Synchronously preloaded in-memory dataset from `data/mock/`. Fast and zero external dependencies. |
| **File** | `file` | Reads datasets dynamically from filesystem JSON files in `data/mock/`. |
| **PostgreSQL** | `postgres` | Persists observations, evidence dossiers, and hotspots into PostgreSQL via `pg`. Requires `DATABASE_URL`. |

> **Fail-Safe Contract**: If `DATA_PROVIDER=postgres` is selected and the database is unreachable or misconfigured, the server aborts startup immediately with a clear diagnostic message. Mock and File providers require zero database setup and will never fail due to external database unavailability.

### PostgreSQL Setup & Schema Migration

The database schema is defined in `backend/db/schema.sql`:
- **`urban_observations`**: Grid cells with coordinates, 2020/2023/2026 land cover metrics, percentiles, anomalies, and breakdowns.
- **`evidence`**: Full evidence dossiers, pipeline audit trails, and image references.
- **`hotspots`**: Ranked investigation targets with priority scores and recommendations.
- **`metadata`**: Provenance, imagery timestamps, and dataset metadata.
- **PostGIS Support**: Automatically adds `geom geometry(Polygon, 4326)` and GIST spatial indices if the `postgis` extension is available on the PostgreSQL host.

#### 1. Run Schema Migration
```bash
psql "$DATABASE_URL" -f backend/db/schema.sql
```

#### 2. Import Intelligence JSON Idempotently
The importer script safely loads or updates records (`ON CONFLICT DO UPDATE`), storing values exactly as provided without altering scores:
```bash
# Import default intelligence JSON (data/mock/investigation_list.json)
DATABASE_URL="postgresql://user:password@localhost:5432/urbanpulse" node backend/scripts/import.js

# Or import a custom intelligence JSON file:
DATABASE_URL="postgresql://user:password@localhost:5432/urbanpulse" node backend/scripts/import.js /path/to/intelligence.json
```

#### 3. Run Backend with PostgreSQL
```bash
DATA_PROVIDER=postgres DATABASE_URL="postgresql://user:password@localhost:5432/urbanpulse" npm --prefix backend run dev
```

---

## 5. How to Run Locally

### Prerequisites
- Node.js (v18+)
- npm (v9+)
- *(Optional)* PostgreSQL 14+ (only if running with `DATA_PROVIDER=postgres`)

### Single-Command Start (Root)
From the repository root (`/Users/pardhu/urban-pulse`):

```bash
# 1. Install dependencies across root, backend, and frontend
npm run install:all

# 2. Run both Backend (Port 5001) and Frontend (Port 3000) concurrently
npm run dev
```

### Or Run Services Separately

**Backend Server (Express)**:
```bash
cd backend
npm run dev
# Running at http://localhost:5001 (defaults to in-memory mock provider)

# Or test filesystem provider:
DATA_PROVIDER=file npm run dev

# Or run with PostgreSQL:
DATA_PROVIDER=postgres DATABASE_URL="postgresql://user:pass@localhost:5432/urbanpulse" npm run dev
```

**Frontend Application (Vite + React)**:
```bash
cd frontend
npm run dev
# Running at http://localhost:3000
```

---

## 6. API Reference

All endpoints return JSON and include the provenance `meta` block (`source`, `is_mock`, `warning`):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System health check, active provider mode (`development-mock`, `file`, `postgres`) |
| `GET` | `/api/overview` | Monitored region summary, cell counts, baseline periods |
| `GET` | `/api/statistics` | Aggregated counts: `analyzed_cells`, `anomalous` (Medium+High), `high`, `medium`, `low` |
| `GET` | `/api/areas` | All grid cells with `grid_id`, coordinates, GeoJSON `geometry`, and priority levels |
| `GET` | `/api/hotspots` | Ranked investigation queue with scores, categories, and recommendations |
| `GET` | `/api/hotspots/:gridId` | Hotspot detail, score breakdown, reasons, and 2020->2026 metric differences |
| `GET` | `/api/change/:gridId` | Time-series data points `[{year, value}]` for built-up, vegetation, water, bare land |
| `GET` | `/api/evidence/:gridId` | Full evidence metrics, anomalies, persistence, and placeholder image URLs |
| `GET` | `/api/pipeline` | The 7 pipeline stages (`Change` → `Investigation list`) |
| `GET` | `/images/:gridId/:year.svg` | Static placeholder SVG imagery with "MOCK IMAGERY" watermark |

---

## 7. Verification and Smoke Testing

Run the automated test suite verifying data integrity, metric calculations, and multi-provider handling:

```bash
npm test
```

*Expected output:*
```text
✓ All 150 records verified: score_breakdown sums strictly equal priority_score
✓ All 150 records verified: valid GeoJSON square polygon (~500m)
✓ Top 8 hotspots have valid placeholder SVG images with 'MOCK IMAGERY' watermark
✓ getStatistics, getAreas, getHotspotDetail, getChange, getEvidence contracts passed
✓ schema.sql verified (tables: urban_observations, evidence, hotspots; conditional PostGIS support)
✓ import.js verified (idempotent loading with ON CONFLICT DO UPDATE)
✓ fileProvider verified (reads directly from filesystem with identical metrics)
✓ In-memory mock provider remains active by default
✓ postgresProvider fails with clear message when DB is unreachable
ALL EXTENDED REST SERVICES & PERSISTENCE CHECKS PASSED (0 errors).
```

