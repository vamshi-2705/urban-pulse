# UrbanPulse — Evidence Asset Generation (Step 9)

## 1. Purpose & Motivation

In the UrbanPulse investigation workflow, discovering high-priority candidate hotspots is only the first step. When an urban inspector, municipal planner, or judge clicks on a flagged cell, they require immediate, multi-spectral visual corroboration:

```
CLICK HOTSPOT
     ↓
WHY FLAGGED?
     ↓
BEFORE IMAGE (True Color)
     ↓
AFTER IMAGE (True Color)
     ↓
CHANGE EVIDENCE (Categorical Multi-Spectral Map)
     ↓
NUMERIC DELTAS (NDVI, NDWI, NDBI)
     ↓
PRIORITY REASONS & SATELLITE SIGNALS
```

The Evidence Asset Generation layer bridges the gap between raw high-dimensional satellite stacks (100+ MB GeoTIFFs) and lightweight, human-interpretable web graphics (~50–120 KB PNGs) that render instantaneously in the browser or mobile dashboard.

---

## 2. Hotspot Coordinate to Raster Window Mapping

Every 500m grid cell (e.g. `HYD_1220`) has a centroid in geographic coordinates (WGS84: Latitude, Longitude).

### 2.1. Spatial Alignment & Windowing
1. The centroid is projected into the project's metric coordinate system: **WGS 84 / UTM Zone 44N (`EPSG:32644`)**.
2. A configurable spatial window (default: **$1000\text{m} \times 1000\text{m}$**) is centered at the hotspot:
   - Half-window: $500\text{m}$
   - At Sentinel-2's $10\text{m}$ resolution, this corresponds to exactly **$100 \times 100$ pixels** ($10,000$ pixels covering $1\text{ km}^2$).
3. The bounding box in UTM coordinates $[x_c - 500, y_c - 500, x_c + 500, y_c + 500]$ is mapped to raster pixel offsets $[row_{\text{off}}, col_{\text{off}}, height, width]$.
4. **Edge-of-Raster Safety:** If a hotspot borders the study area boundary, pixel window offsets are clamped to $[0, \text{dim}]$ to prevent negative indexing or out-of-bounds exceptions while preserving the exact affine transform.

---

## 3. Visual Evidence Products

For each flagged hotspot, 8 synchronized visual assets are generated:

| Asset Name | Spectral Origin | Visualization & Color Stretch | Observational Role |
| :--- | :--- | :--- | :--- |
| `before_rgb.png` | Sentinel-2 L2A (B04, B03, B02) | Surface Reflectance linear stretch $[0.0, 0.35]$ | Natural color baseline of the site prior to intervention. |
| `after_rgb.png` | Sentinel-2 L2A (B04, B03, B02) | Surface Reflectance linear stretch $[0.0, 0.35]$ | Natural color view of the site at the post-intervention epoch. |
| `ndvi_before.png` | Normalized Difference Veg Index | Colormap: `RdYlGn` ($[-0.1, 0.8]$) | Baseline photosynthetic canopy vigor and green cover. |
| `ndvi_after.png` | Normalized Difference Veg Index | Colormap: `RdYlGn` ($[-0.1, 0.8]$) | Post-intervention canopy density. |
| `ndvi_change.png` | $\Delta \text{NDVI} = \text{NDVI}_{t_2} - \text{NDVI}_{t_1}$ | Diverging `RdYlGn` ($[-0.5, +0.5]$) | Red indicates canopy drop; Green indicates vegetation regrowth. |
| `ndwi_change.png` | $\Delta \text{NDWI} = \text{NDWI}_{t_2} - \text{NDWI}_{t_1}$ | Diverging `PuOr` ($[-0.5, +0.5]$) | Purple indicates moisture increase; Orange indicates moisture loss. |
| `ndbi_change.png` | $\Delta \text{NDBI} = \text{NDBI}_{t_2} - \text{NDBI}_{t_1}$ | Diverging `coolwarm` ($[-0.5, +0.5]$) | Red indicates built-up-sensitive increase; Blue indicates decrease. |
| `combined_change.png` | Cross-indicator multi-spectral rule | Discrete categorical palette with legend | Synthesized multi-indicator evidence classification map. |

---

## 4. Categorical Change Evidence Map

To provide rapid visual clarity for field inspectors, the `combined_change.png` map synthesizes multi-spectral deltas into distinct observable categories:

- **Coherent Transition (Crimson `#d32f2f`):** Co-occurring vegetation decrease ($\Delta \text{NDVI} \le -0.15$) and built-up-sensitive spectral increase ($\Delta \text{NDBI} \ge +0.15$). This is the characteristic signature of ground clearing and impervious construction.
- **Built-Up-Sensitive Increase Only (Amber `#f57c00`):** Impervious/bare-soil reflectance increase ($\Delta \text{NDBI} \ge +0.15$).
- **Vegetation Decrease Only (Brown `#8d6e63`):** Canopy loss ($\Delta \text{NDVI} \le -0.15$) without accompanying built-up response.
- **Vegetation Increase (Emerald `#2e7d32`):** Canopy growth ($\Delta \text{NDVI} \ge +0.15$).
- **Water-Body / Moisture Change (Blue `#0288d1`):** Significant shift in surface moisture ($|\Delta \text{NDWI}| \ge 0.15$).
- **Stable / Baseline Variation (Light Gray `#f5f5f5`):** Variations below the detection tolerance threshold ($|\Delta| < 0.15$).

---

## 5. Scientific Rasters vs. UI Preview Images

| Attribute | Scientific Rasters (`.tif`) | UI Preview Images (`.png`) |
| :--- | :--- | :--- |
| **Primary Consumer** | GIS tools, spatial analysts, automated engines | Web frontend, mobile UI, PDF investigation dossiers |
| **Data Format** | Multi-band 32-bit Float GeoTIFF with CRS | Lightweight 8-bit RGB PNG ($120\text{ dpi}$) |
| **Typical File Size** | $50\text{ MB} - 150\text{ MB}$ per scene | $\sim 50\text{ KB} - 120\text{ KB}$ per asset |
| **Values Stored** | Unaltered physical reflectance & indices | Human-calibrated visual stretch and colormaps |
| **Georeferencing** | Embedded GeoTIFF tags (transform, CRS) | Associated with `metadata.json` bounding coordinates |

---

## 6. Frontend Manifest Consumption

Frontend and backend services consume `data/outputs/evidence/evidence_manifest.json`:

```json
{
  "HYD_1220": {
    "2020_2026": {
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
}
```

### Hotspot Detail Metadata (`metadata.json`)
```json
{
  "grid_id": "HYD_1220",
  "period": "2020_2026",
  "rank": 1,
  "center_lat": 17.372285,
  "center_lon": 78.42256,
  "window_meters": 1000.0,
  "crs": "EPSG:32644",
  "source": "Sentinel-2 L2A",
  "before_date": "2020-03-29T05:06:51.024000+00:00",
  "after_date": "2026-03-10T05:12:41.024000+00:00",
  "crop_dimensions": [100, 100],
  "assets": { ... },
  "scientific_metrics": {
    "mean_ndvi_delta": -0.5543,
    "mean_ndwi_delta": 0.1043,
    "mean_ndbi_delta": 0.2766,
    "total_pixels": 10000,
    "coherent_pixels": 838,
    "coherent_fraction": 0.0838,
    "built_only_pixels": 37,
    "veg_loss_pixels": 624,
    "veg_gain_pixels": 0,
    "water_change_pixels": 574
  }
}
```

---

## 7. Resolution Limitations & Scientific Safety

### 7.1. Spatial Resolution Limitations
- Sentinel-2 Level-2A imagery operates at **$10\text{m}$** (RGB, NIR) and **$20\text{m}$** (SWIR) native spatial resolution.
- Individual vehicles, fences, small shacks, or micro-scale structures cannot be resolved.
- A single $10\text{m}$ pixel represents $100\text{ m}^2$ of mixed surface reflectance.

### 7.2. Scientific Caution & Decision-Support Framing
- Spectral shifts represent **observable physical surface alterations**, not legal verdicts.
- Terms such as *"built-up-sensitive spectral increase"* are used instead of *"unauthorized construction confirmed"*.
- Terms such as *"vegetation decrease"* are used instead of *"illegal tree felling"*.
- Human field verification is indispensable to confirm on-the-ground causes and administrative authorization.
