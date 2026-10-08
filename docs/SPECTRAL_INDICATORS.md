# UrbanPulse — Spectral Indicators & Continuous Index Engine

## 1. Executive Overview

UrbanPulse transforms 6-band Sentinel-2 Level-2A Analysis-Ready Data (ARD) stacks into continuous spectral indicator layers:
- **NDVI**: Vegetation-sensitive index
- **NDWI**: Water-sensitive index
- **NDBI**: Built-up-sensitive index

These layers are maintained as continuous floating-point variables ($[-1.0, 1.0]$) rather than being prematurely quantized into discrete land-cover categories.

---

## 2. Core Indicator Formulations

All three indices utilize normalized difference ratios of the general form $\frac{A - B}{A + B}$, which mitigates solar illumination variations, terrain shading, and sensor viewing geometry across epochs:

| Indicator | Concept | Mathematical Formula | Sentinel-2 Bands | Physical Mechanism |
| :---: | :--- | :---: | :---: | :--- |
| **NDVI** | Vegetation-sensitive index | $\frac{\text{NIR} - \text{RED}}{\text{NIR} + \text{RED}}$ | $\text{B08} (842\text{nm}) - \text{B04} (665\text{nm})$ | High chlorophyll absorption in Red contrasted with high cellular mesophyll scattering in NIR. |
| **NDWI** | Water-sensitive index (McFeeters) | $\frac{\text{GREEN} - \text{NIR}}{\text{GREEN} + \text{NIR}}$ | $\text{B03} (560\text{nm}) - \text{B08} (842\text{nm})$ | High water reflectance in Green contrasted with near-total water absorption in NIR. |
| **NDBI** | Built-up-sensitive index | $\frac{\text{SWIR1} - \text{NIR}}{\text{SWIR1} + \text{NIR}}$ | $\text{B11} (1610\text{nm}) - \text{B08} (842\text{nm})$ | Higher reflectance of impervious artificial surfaces in shortwave infrared compared to near infrared. |

---

## 3. Why Continuous Indicators Are Preferred Over Hard Classifications

> [!IMPORTANT]
> **Core Methodological Principle**:  
> In complex metropolitan environments like Hyderabad, individual 10-meter pixels represent composite mixtures of rooftops, asphalt, road medians, shade trees, bare construction soil, and parking lots.  
> 
> Forcing pixels prematurely into discrete bins (e.g. `is_building = True`) introduces catastrophic quantization errors and destroys subtle multi-temporal trajectories. UrbanPulse maintains continuous indicator fields so the downstream engine can evaluate **magnitude, direction, and spatial context of change**.

### Spectral Ambiguities in Urban Landscapes:
- **NDBI $\ne$ Buildings**: Impervious urban rooftops, asphalt highways, dry bare soil, and rocky quarry terrain all exhibit elevated SWIR reflectance relative to NIR. NDBI responds to both built structures and dry bare ground.
- **NDWI $\ne$ Pure Water**: Deep shadow cast by high-rise buildings and topographic depressions can produce low NIR reflectance and mimic water signatures.
- **NDVI $\ne$ Permanent Forest**: Lawns, roadside shrubs, agricultural plots on the urban fringe, and seasonal greening post-rains exhibit dynamic NDVI swings without representing permanent forest cover.

---

## 4. Valid Mask Propagation & Numerical Safety

To ensure zero corrupted pixels enter downstream statistical modules:
1. **Denominator Safety**: Denominators satisfying $|A + B| \le 10^{-7}$ are flagged as division-by-zero risks and set to invalid.
2. **Finite Input Gate**: Any pixel containing $\text{NaN}$ or $\text{Inf}$ in input bands is marked invalid.
3. **Propagated SCL Clearance**: Mask from Step 3 (clearing cloud shadows, cirrus, and sensor defects) is strictly intersected.
4. **NaN Isolation**:
   - **Valid Pixels**: Guaranteed to contain finite values strictly within $[-1.0, 1.0]$.
   - **Invalid Pixels**: Set to $\text{NaN}$ in `indices.tif` and `0` in `valid_mask.tif`.
   - **No Zero Substitution**: Zero ($0.0$) is a meaningful physical indicator value and is never used as a proxy for missing data.

---

## 5. Output Data Model (`indices.tif`)

For each epoch (`2020`, `2023`, `2026`), outputs are saved under `data/processed/indicators/{year}/`:
- **`indices.tif`**: 3-band Float32 Cloud-Optimized GeoTIFF:
  - Band 1: `NDVI`
  - Band 2: `NDWI`
  - Band 3: `NDBI`
- **`valid_mask.tif`**: 1-band UInt8 GeoTIFF ($1 = \text{valid}$, $0 = \text{invalid}$).
- **`indicator_metadata.json`**: Complete statistical distribution metrics and epoch provenance.

### Geometry Invariants:
- **CRS**: `EPSG:32644` (WGS 84 / UTM Zone 44N)
- **Dimensions**: $1690 \text{ rows} \times 2149 \text{ columns}$ ($3,631,810$ pixels)
- **Resolution**: Exactly $10.0\text{m} \times 10.0\text{m}$
- **Transform**: `Affine(10.0, 0.0, 218370.0, 0.0, -10.0, 1936830.0)`

---

## 6. Heuristic Exploratory Thresholds (Non-Binding)

In `config/config.yaml`, prototype exploratory thresholds are provided for initial visual screening only:
```yaml
indicators:
  heuristic_thresholds:
    vegetation_candidate: 0.35  # Exploratory: NDVI > 0.35
    water_candidate: 0.05        # Exploratory: NDWI > 0.05
    builtup_candidate: 0.05      # Exploratory: NDBI > 0.05
```

These are **heuristic exploration thresholds** only and are **never treated as ground truth**.

---

## 7. Feed-Forward Contract to Step 5 (Change Detection)

The 3-band indicator stacks directly power Step 5:
$$\Delta \text{NDVI} = \text{NDVI}_{t_2} - \text{NDVI}_{t_1}$$
$$\Delta \text{NDBI} = \text{NDBI}_{t_2} - \text{NDBI}_{t_1}$$
$$\Delta \text{NDWI} = \text{NDWI}_{t_2} - \text{NDWI}_{t_1}$$

By keeping spatial grids strictly congruent across 2020, 2023, and 2026, multi-temporal delta tensors can be computed via vectorized array arithmetic without spatial interpolation artifacts.
