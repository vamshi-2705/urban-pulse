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
│   └── mock/                           # Preloaded mock datasets
│       ├── overview.json               # Monitored region summary & baseline dates
│       ├── pipeline.json               # 7-stage evidence pipeline definition
│       ├── hotspots.json               # Ranked field investigation queue
│       ├── evidence.json               # Full multi-epoch evidence dossiers
│       └── cells.json                  # Monitored grid cells with bounds
├── backend/
│   ├── package.json
│   └── src/
│       ├── server.js                   # Express REST API (Port 5001)
│       └── providers/
│           └── mockProvider.js         # In-memory mock data loader & provider
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

## 4. How to Run Locally

### Prerequisites
- Node.js (v18+)
- npm (v9+)

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
# Running at http://localhost:5001
```

**Frontend Application (Vite + React)**:
```bash
cd frontend
npm run dev
# Running at http://localhost:3000
```

---

## 5. API Reference

All endpoints return JSON and are served by `backend/src/providers/mockProvider.js`:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System health check, provider mode (`development-mock`), and uptime |
| `GET` | `/api/overview` | Monitored region summary, cell counts, baseline periods |
| `GET` | `/api/pipeline` | The 7 pipeline stages (`Change` → `Investigation list`) |
| `GET` | `/api/grid-cells` | Monitored spatial grid cells with bounds and anomaly flags |
| `GET` | `/api/hotspots` | Ranked investigation list with scores, categories, and metrics |
| `GET` | `/api/hotspots/:id` | Single hotspot detail by ID |
| `GET` | `/api/hotspots/:id/evidence` | Full multi-epoch evidence dossier for a specific hotspot |

---

## 6. Verification and Smoke Testing

1. **Verify Backend Health**:
   ```bash
   curl -s http://localhost:5001/api/health
   ```
   *Expected response:* `{"status":"ok","service":"urban-pulse-backend","isMock":true}`

2. **Verify Overview Data**:
   ```bash
   curl -s http://localhost:5001/api/overview
   ```
   *Expected response:* JSON containing `regionName: "Bengaluru East Growth Corridor..."`, `isMock: true`.

3. **Verify Hotspots Queue**:
   ```bash
   curl -s http://localhost:5001/api/hotspots
   ```
   *Expected response:* Ranked array of 12 hotspots with `priorityScore` and recommendation.

4. **Verify Frontend UI in Browser**:
   Open `http://localhost:3000` to confirm:
   - "Development data" banner is active at the top.
   - Municipal masthead shows online status and active region.
   - Pipeline breadcrumb visually represents `Change → Historical baseline → Local baseline → Anomaly → Evidence → Priority → Investigation list`.
   - Ranked investigation table is interactive and clicking "Inspect evidence" renders the full dossier.
