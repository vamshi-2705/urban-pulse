# UrbanPulse

## Evidence-Based Urban Change Investigation & Priority Engine

UrbanPulse is a geospatial intelligence platform that converts multi-temporal satellite observations into an evidence-backed list of locations that deserve human attention.

Instead of simply showing **"change detected"**, UrbanPulse follows:

> **CHANGE → ANOMALY → EVIDENCE → PRIORITY**

The system analyzes real Sentinel-2 satellite imagery, measures changes in vegetation, water and built-up-sensitive areas, identifies unusual spatial change, generates supporting evidence, and ranks locations for field verification.

---

## 🎯 Problem

Urban areas change continuously, but city authorities cannot manually inspect thousands of locations across a city using satellite imagery.

Existing mapping and change-detection systems can show where change occurred, but an important question remains:

> **Which changes actually deserve attention first?**

UrbanPulse addresses this gap by converting large-scale satellite observations into a prioritized investigation list.

---

## 💡 Solution

UrbanPulse processes multi-temporal Sentinel-2 imagery and:

1. Preprocesses satellite imagery into a common analysis grid.
2. Calculates spectral indicators:
   - **NDVI** — vegetation condition
   - **NDWI** — water-related change
   - **NDBI** — built-up-sensitive change
3. Compares observations across multiple periods.
4. Detects significant spectral and spatial changes.
5. Identifies scene-level change anomalies.
6. Combines anomaly signals with physical evidence such as:
   - vegetation loss
   - water change
   - built-up-sensitive change
   - persistence
   - spatial deviation
   - vegetation/built-up coherence
7. Generates an explainable priority score.
8. Produces before/after evidence for important hotspots.
9. Provides a ranked list of locations recommended for field verification.

---

## 🛰️ Real Satellite Data

UrbanPulse uses real Sentinel-2 Level-2A imagery obtained through the Microsoft Planetary Computer STAC API.

### Prototype Region

Hyderabad, India

### Analysis Periods

- 2020
- 2023
- 2026

### Spatial Resolution

10 m common analysis grid.

### Satellite Indicators

| Indicator | Formula | Purpose |
|---|---|---|
| NDVI | `(B08 - B04) / (B08 + B04)` | Vegetation |
| NDWI | `(B03 - B08) / (B03 + B08)` | Water-related signal |
| NDBI | `(B11 - B08) / (B11 + B08)` | Built-up-sensitive signal |

---

# 🧠 Intelligence Pipeline

```text
Sentinel-2 Satellite Data
          ↓
Scene Discovery
          ↓
Cloud / Quality Filtering
          ↓
Preprocessing & Common Grid
          ↓
Spectral Indicators
   ┌──────┼──────┐
   ↓      ↓      ↓
 NDVI   NDWI   NDBI
   └──────┼──────┘
          ↓
Temporal Change Detection
          ↓
Anomaly Detection
          ↓
Evidence Generation
          ↓
Priority Scoring
          ↓
Hotspot Ranking
          ↓
GeoJSON / JSON / Evidence Assets
          ↓
Backend API
          ↓
React + Leaflet Dashboard