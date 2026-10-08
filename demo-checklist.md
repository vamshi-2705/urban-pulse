# UrbanPulse — Hackathon Demonstration Checklist & Guide

This document outlines the exact demo flow, URLs, click order, talking points, network resilience measures, and local-run fallback instructions for presenting UrbanPulse to judges and municipal stakeholders.

---

## 1. Quick Verification & Demonstration URLs

| Screen | Target URL | Primary Verification Objective |
| :--- | :--- | :--- |
| **1. City Overview** | `http://localhost:5001/` | 150 monitored cells on OpenStreetMap, summary strip, 7-stage evidence pipeline. |
| **2. Hotspot Ranking** | `http://localhost:5001/ranking` | Prioritized queue of 15 anomalous cells with side-map sync and keyboard focus. |
| **3. Why Flagged (#1 Hotspot)** | `http://localhost:5001/hotspot/HYD_0421` | Prominent `87 / 100` score, additive breakdown bars, 5-second plain-language evidence. |
| **4. Change Explorer** | `http://localhost:5001/hotspot/HYD_0421/change` | `31% -> 38% -> 47%` sequence panels, plain SVG charts, mini map, side-by-side imagery. |
| **5. Evidence View** | `http://localhost:5001/hotspot/HYD_0421/evidence` | 2020 &rarr; 2023 &rarr; 2026 imagery row, 5-step vertical traceable reasoning chain. |

*Alternative Vite development port:* `http://localhost:3000` (proxies to backend port `5001`).

---

## 2. Step-by-Step Demonstration Script & Click Order

### Step 1: City Overview (`/`)
1. **Navigate to:** `http://localhost:5001/`
2. **What to point out:**
   - **Provenance banner:** Persistent development data notice (*"DEVELOPMENT DATA ONLY"*).
   - **Municipal summary strip:** *"From 150 analyzed locations, UrbanPulse flagged 15 for field verification."*
   - **7-Stage pipeline chain:** `Change → Baseline → Anomaly → Evidence → Priority → Investigation Queue`.
   - **Map interaction:** Toggle between *"All cells"* (150) and *"Anomalous only"* (15).
   - **Cell interaction:** Click on cell `HYD_0421` in central Hyderabad. The popup displays priority score `87 / 100` and the button *"Open details"*.
3. **Transition action:** Click **"Hotspot ranking"** in the top navigation bar (or popup *"Open details"*).

---

### Step 2: Hotspot Ranking (`/ranking`)
1. **Navigate to:** `http://localhost:5001/ranking`
2. **What to point out:**
   - **Queue structure:** Sorted municipal queue with columns: `Rank`, `Location`, `Priority score`, `Main reason`, `Status`.
   - **Filter tabs:** Click *"High"* (5 cells), *"Medium"* (10 cells), and *"All"* (15 cells).
   - **Keyboard accessibility:** Press `Tab` to navigate through rows; press `Enter` on any row to open details.
   - **Side-map synchronization:** Hovering or focusing row `#1 (HYD_0421)` highlights the cell on the synchronized right-hand map.
3. **Transition action:** Click on row `#1 (HYD_0421)`.

---

### Step 3: Why Flagged Screen (`/hotspot/HYD_0421`)
1. **Navigate to:** `http://localhost:5001/hotspot/HYD_0421`
2. **What to point out (5-second judge readability):**
   - **Header:** *"Why was this area flagged?"* with `HYD_0421` and `HIGH PRIORITY` badge.
   - **Urgency score:** Large, high-contrast score: **`87 / 100`**.
   - **Score breakdown:** Horizontal bars sorted strictly by weight without inventing or rescaling values:
     - `Urban expansion: +32`
     - `Vegetation loss: +21`
     - `Historical anomaly: +18`
     - `Local anomaly: +10`
     - `Persistence: +6`
     - *(Water change is 0, so filtered from breakdown as required).*
   - **Observable evidence:**
     - Built-up: `31% -> 47% (+16 points)`
     - Vegetation: `42% -> 31% (-11 points)`
     - Water change: `8% -> 5% (-3 points)`
     - Local baseline: `"95th percentile among nearby areas"`
     - Historical baseline: `"2.7x the historical baseline"`
   - **Closing directive:** *"Unusual spatial change detected. Field verification recommended."*
3. **Transition action:** Click **"Change explorer"** button.

---

### Step 4: Change Explorer (`/hotspot/HYD_0421/change`)
1. **Navigate to:** `http://localhost:5001/hotspot/HYD_0421/change`
2. **What to point out:**
   - **Standardized breadcrumb:** `Overview › Ranking › Hotspot (HYD_0421) › Change Explorer`.
   - **Transition panels:**
     - Built-up: Value sequence **`31% -> 38% -> 47%`** with clean SVG sparkline bar chart.
     - Vegetation: Value sequence **`42% -> 37% -> 31%`** with clean SVG sparkline bar chart.
     - Water: Value sequence **`8% -> 6% -> 5%`** with clean SVG sparkline bar chart.
   - **Mini map:** Dedicated Leaflet mini map centered on `HYD_0421` (~500 m cell footprint).
   - **Before / After imagery:**
     - Left frame: `Before (2020)` with visible `"Mock imagery"` badge.
     - Right frame: `After (2026)` with visible `"Mock imagery"` badge.
     - Click `2023` in either year selector to demonstrate interactive epoch switching.
3. **Transition action:** Click **"Evidence view"** in breadcrumbs or navigation.

---

### Step 5: Evidence View (`/hotspot/HYD_0421/evidence`)
1. **Navigate to:** `http://localhost:5001/hotspot/HYD_0421/evidence`
2. **What to point out:**
   - **Multi-epoch imagery row:** `2020 → 2023 → 2026` side-by-side progression with visible `"Mock imagery"` badges.
   - **5-Step vertical traceable reasoning chain:**
     1. **Step 1: Observed change** &rarr; *"Built-up area grew 16 points while vegetation contracted by 11 points between 2020 and 2026."*
     2. **Step 2: Historical baseline** &rarr; *"Observed rate of transition is 2.7x the historical baseline recorded for this grid cell."*
     3. **Step 3: Local baseline** &rarr; *"Local change ranks in the 95th percentile compared to surrounding 500 m neighborhood cells."*
     4. **Step 4: Anomaly** &rarr; *"Temporal divergence (0.91) and spatial divergence (0.87) detected with 0.82 multi-epoch persistence."*
     5. **Step 5: Priority** &rarr; *"Composite anomaly and divergence metrics establish a priority score of 87 / 100 with HIGH inspection urgency."*
   - **Closing directive:** Action banner concludes with *"Field verification recommended."*

---

## 3. Network Resilience & Offline Fallback Architecture

To ensure the demo succeeds under poor Wi-Fi, conference throttling, or network drops:

1. **In-Memory Request Caching (`apiCache`):**
   - Implemented in `frontend/src/api/client.js`.
   - Caches all resolved responses. Duplicate calls for the same endpoint return cached promises immediately (0 ms response).
2. **Startup Background Preloading (`preloadAllData()`):**
   - On application load, `App.jsx` triggers background preloading for:
     - `/api/health`, `/api/overview`, `/api/pipeline`, `/api/statistics`, `/api/areas`, `/api/hotspots`
     - `/api/hotspots/HYD_0421`, `/api/change/HYD_0421`, `/api/evidence/HYD_0421`
   - All 5 demo screens are cached in memory during initial load.
3. **Graceful Loading, Empty, and Error States:**
   - Every screen features skeleton loading indicators, empty dataset fallbacks, and a dedicated **"Retry"** button to recover from transient failures without requiring a full browser refresh.

---

## 4. Local-Run Fallback Instructions

If hosted cloud deployment (Render/Railway) experiences DNS or connectivity issues during presentation:

### Option A: Unified Production Server (Single Port 5001)
```bash
# 1. From repository root:
npm run build

# 2. Start unified server:
npm start

# 3. Open in browser:
# http://localhost:5001
```

### Option B: Local Development Server (Vite + Express)
```bash
# 1. Start both servers concurrently:
npm run dev

# 2. Open in browser:
# http://localhost:3000
```

---

## 5. Summary of Changes Made in this Pass

1. **API Client Caching & Preloading ([client.js](file:///Users/pardhu/urban-pulse/frontend/src/api/client.js)):**
   - Added `cachedFetch()` with request deduplication and error eviction.
   - Added `preloadAllData()` pre-caching all primary demo routes at startup.
2. **App Coordinator Enhancements ([App.jsx](file:///Users/pardhu/urban-pulse/frontend/src/App.jsx)):**
   - Integrated `preloadAllData()` on launch.
   - Added interactive *"Retry connection"* button to backend error screen.
3. **Empty & Error State Hardening:**
   - **[CityOverviewMap.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/CityOverviewMap.jsx):** Added empty state when 0 areas return, plus error state with retry button.
   - **[CityOverviewPage.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/CityOverviewPage.jsx):** Added retry trigger and `onRetry` handler.
   - **[HotspotRankingPage.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/HotspotRankingPage.jsx):** Added retry state and button to error card.
   - **[HotspotDetailView.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/HotspotDetailView.jsx):** Added retry trigger and dual buttons (*"Retry"* and *"Back to Ranking"*).
   - **[ChangeExplorerView.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/ChangeExplorerView.jsx):** Added retry trigger and dual buttons.
   - **[EvidenceView.jsx](file:///Users/pardhu/urban-pulse/frontend/src/components/EvidenceView.jsx):** Added retry trigger and dual buttons.
4. **Wording Audit & Compliance:**
   - Audited codebase and replaced prohibited phrasing in `ChangeExplorerView.jsx` with compliant municipal language: *"Unusual spatial change detected. Field verification recommended."*
5. **Documentation:**
   - Created this `demo-checklist.md` guide.
