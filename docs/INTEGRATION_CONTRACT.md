# UrbanPulse — Frontend & Backend Integration Contract (Step 8)

## 1. Overview & Architectural Role

This document defines the official **Integration Contract** between **Member 1 (Geospatial AI & Intelligence Engine)** and **Member 2 (Backend & Frontend Applications)**.

> **SCIENTIFIC DISCLAIMER:**
> **These outputs are decision-support intelligence derived from satellite observations. They do not establish legality, causality, or ground truth.**
>
> UrbanPulse detects observable spatial and temporal multi-spectral land-cover change patterns. Human field verification is required to establish real-world causality or legal status.

All geospatial intelligence artifacts are pre-computed, strictly validated, and exported to `data/outputs/api/` in standardized JSON and GeoJSON formats.

```
+------------------------------------+
|  Member 1 — Geospatial Engine      |
|  (Sentinel-2 -> Change -> Priority) |
+------------------------------------+
                  |
                  | Stable Data Contract
                  v
       data/outputs/api/
       ├── hotspots_{period}.json
       ├── hotspots_{period}.geojson
       ├── city_summary_{period}.json
       └── top_{k}_{period}.json
                  |
                  v
+------------------------------------+
|  Member 2 — Backend / Frontend     |
|  (FastAPI / Express / Leaflet UI)  |
+------------------------------------+
```

---

## 2. API Endpoints Contract (Recommendation for Member 2)

Member 2 owns the web API layer. Member 1 provides the following recommended endpoint specifications to serve the exported intelligence:

### `GET /api/v1/summary`
- **Query Params:** `period` (`2020_2023`, `2023_2026`, default: `2020_2026`).
- **Description:** Returns aggregate city-level change metrics and the top 25 priority investigation hotspots.
- **Source Artifact:** `data/outputs/api/city_summary_{period}.json`.

### `GET /api/v1/hotspots`
- **Query Params:**
  - `period` (`2020_2023`, `2023_2026`, `2020_2026`)
  - `limit` (e.g. `10`, `25`, `50`, or all)
  - `level` (`HIGH`, `MEDIUM`, `LOW`)
- **Description:** Returns ranked investigation candidate list.
- **Source Artifact:** `data/outputs/api/hotspots_{period}.json` or `top_{k}_{period}.json`.

### `GET /api/v1/hotspots/geojson`
- **Query Params:** `period` (default: `2020_2026`).
- **Description:** Returns a GeoJSON `FeatureCollection` formatted for direct rendering on Leaflet or MapLibre.
- **Source Artifact:** `data/outputs/api/hotspots_{period}.geojson`.

### `GET /api/v1/hotspots/{grid_id}`
- **Path Params:** `grid_id` (e.g. `HYD_1220`).
- **Query Params:** `period` (default: `2020_2026`).
- **Description:** Returns full multi-spectral intelligence record and `why_flagged` explanation for a specific 500m cell.

### `GET /api/v1/hotspots/{grid_id}/evidence`
- **Path Params:** `grid_id` (e.g. `HYD_1220`).
- **Description:** Returns detailed cross-indicator consistency and directional change signals.

---

## 3. Data Schema & Field Definitions

### 3.1. Hotspot Record Schema (`hotspots_{period}.json`)

```json
{
  "rank": 1,
  "grid_id": "HYD_1220",
  "period": "2020_2026",
  "latitude": 17.372285,
  "longitude": 78.422560,

  "priority": {
    "score": 0.8200,
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
    "spatial": 1.0000
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
        "code": "PERSISTENT_CHANGE",
        "description": "The directional change persists across available multi-year observations."
      }
    ]
  }
}
```

### 3.2. Field Definitions

| Field | Type | Description | Values / Range |
| :--- | :--- | :--- | :--- |
| `rank` | `int` | Monotonic descending rank by `priority.score` (1-indexed). | $1 \le \text{rank} \le 1462$ |
| `grid_id` | `str` | Unique 500m cell identifier in Hyderabad AOI. | e.g. `HYD_0001` to `HYD_1462` |
| `period` | `str` | Observation interval. | `2020_2023`, `2023_2026`, `2020_2026` |
| `latitude` | `float` | WGS84 latitude centroid of cell. | $17.349 \le \text{lat} \le 17.501$ |
| `longitude` | `float` | WGS84 longitude centroid of cell. | $78.349 \le \text{lon} \le 78.551$ |
| `priority.score` | `float` | Normalized priority score. | $[0.0, 1.0]$ |
| `priority.level` | `str` | Categorical triage tier. | `HIGH` ($\ge 0.70$), `MEDIUM` ($0.45 - 0.70$), `LOW` ($< 0.45$) |
| `priority.recommendation` | `str` | Action guidance. | `FIELD_VERIFICATION_RECOMMENDED`, `MONITOR_AND_REVIEW`, `ROUTINE_OBSERVATION` |
| `anomaly.overall` | `float` | Scene-level combined anomaly strength. | $[0.0, 1.0]$ |
| `anomaly.spatial` | `float` | Neighborhood contrast anomaly. | $[0.0, 1.0]$ |
| `evidence.*` | `bool` | Physical and cross-indicator verification flags. | `true` / `false` |
| `change.*_delta` | `float` | Representative spectral shift ($\Delta = I_{t_2} - I_{t_1}$). | $[-2.0, 2.0]$ |
| `why_flagged.headline` | `str` | Plain-language executive summary. | Concise sentence |
| `why_flagged.factors` | `list` | Factor-by-factor evidence breakdown. | List of `{code, description}` |

---

## 4. Frontend Map Contract (GeoJSON Schema)

The file `data/outputs/api/hotspots_{period}.geojson` is compliant with RFC 7946 GeoJSON:

```json
{
  "type": "FeatureCollection",
  "period": "2020_2026",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [78.422560, 17.372285]
      },
      "properties": {
        "grid_id": "HYD_1220",
        "rank": 1,
        "priority_score": 0.8200,
        "priority_level": "HIGH",
        "recommendation": "FIELD_VERIFICATION_RECOMMENDED",
        "period": "2020_2026",
        "reasons": [
          "HIGH_SCENE_ANOMALY",
          "SPATIAL_ANOMALY",
          "VEG_BUILTUP_COHERENCE",
          "PERSISTENT_CHANGE"
        ],
        "overall_anomaly": 0.9639,
        "headline": "Strong and persistent land-cover change"
      }
    }
  ]
}
```

### Direct Leaflet / MapLibre Integration Snippet
```javascript
// Example Leaflet styling
L.geoJSON(hotspotsGeoJSON, {
  pointToLayer: function (feature, latlng) {
    const level = feature.properties.priority_level;
    const color = level === 'HIGH' ? '#e53935' : (level === 'MEDIUM' ? '#ffb74d' : '#90caf9');
    return L.circleMarker(latlng, {
      radius: level === 'HIGH' ? 8 : 4,
      fillColor: color,
      color: '#ffffff',
      weight: 1,
      fillOpacity: 0.85
    });
  },
  onEachFeature: function (feature, layer) {
    layer.bindPopup(`
      <b>${feature.properties.grid_id} (Rank #${feature.properties.rank})</b><br/>
      <b>Priority:</b> ${feature.properties.priority_score} (${feature.properties.priority_level})<br/>
      <b>Status:</b> ${feature.properties.recommendation}<br/>
      <i>${feature.properties.headline}</i>
    `);
  }
}).addTo(map);
```

---

## 5. City Summary Contract (`city_summary_{period}.json`)

Provides high-level city statistics and embeds the top 25 candidate hotspots:

```json
{
  "period": "2020_2026",
  "total_cells": 1462,
  "high_priority": 27,
  "medium_priority": 453,
  "low_priority": 982,
  "score_median": 0.4107,
  "score_p95": 0.6172,
  "top_hotspots": [ ... ]
}
```

---

## 6. Reason Codes & Scientifically Cautious Descriptions

| Reason Code | Scientific Meaning |
| :--- | :--- |
| `HIGH_SCENE_ANOMALY` | Observed spectral change is unusually strong relative to the scene distribution. |
| `SPATIAL_ANOMALY` | Spectral change sharply deviates from the surrounding 15x15 pixel local context. |
| `VEG_BUILTUP_COHERENCE` | Vegetation decrease coincides with built-up-sensitive spectral increase. |
| `VEGETATION_LOSS` | Substantial reduction in photosynthetic canopy (NDVI delta <= -0.15). |
| `BUILTUP_SENSITIVE_CHANGE` | Substantial increase in shortwave-infrared impervious surface reflectance (NDBI delta >= 0.15). |
| `WATER_CHANGE` | Significant shift in surface moisture or surface water extent (\|NDWI delta\| >= 0.15). |
| `PERSISTENT_CHANGE` | The directional change persists across available multi-year observations. |
| `STRONG_CHANGE_MAGNITUDE` | Extreme physical spectral displacement across one or more indicator bands. |
| `CYCLICAL_REVERSAL_DAMPENED` | Directional turnaround detected across observation intervals; priority dampened for potential cyclical variation. |

---

## 7. Data Quality & Contract Guarantees

Every file exported to `data/outputs/api/` is programmatically guaranteed to satisfy:
1. **Coordinate Bounding:** $17.349 \le \text{lat} \le 17.501$, $78.349 \le \text{lon} \le 78.551$.
2. **Zero Missing / NaN Values:** Numeric fields contain finite floats in $[0.0, 1.0]$ or valid delta ranges.
3. **Monotonic Rank Sorting:** Ranked strictly descending by `priority.score`.
4. **Unique Identifiers:** Grid IDs (`HYD_xxxx`) are unique within each period.
5. **Arithmetic Integrity:** High + Medium + Low counts exactly sum to `total_cells` (1,462).
