# UrbanPulse — Sentinel-2 Data Preprocessing & ARD Pipeline

## 1. Sentinel-2 Data Source
- **Provider**: European Space Agency (ESA) via Microsoft Planetary Computer STAC API.
- **Collection**: `sentinel-2-l2a` (Level-2A Bottom-Of-Atmosphere / Surface Reflectance).
- **Format**: Cloud-Optimized GeoTIFFs (COG) with Deflate compression.

---

## 2. Selected Scenes for Prototype Epochs
All scenes were selected by Step 2 based on cloud cover minimization, spatial containment over Hyderabad AOI (`[78.35, 17.35, 78.55, 17.50]`), and dry-season alignment:

| Epoch | Scene Identifier | Date | DOY | Cloud Cover | MGRS Tile |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **2020** | `S2A_MSIL2A_20200329T050651_R019_T43QHV_20201020T215529` | 2020-03-29 | 89 | 0.0567% | `43QHV` |
| **2023** | `S2B_MSIL2A_20230128T051049_R019_T44QKE_20230130T005242` | 2023-01-28 | 28 | 0.0012% | `44QKE` |
| **2026** | `S2A_MSIL2A_20260310T051241_R019_T43QHV_20260310T105217` | 2026-03-10 | 69 | 0.0010% | `43QHV` |

---

## 3. Band Mapping & Canonical Stack Order
UrbanPulse standardizes each scene into a 6-band float32 GeoTIFF stack (`scene_stack.tif`) plus an accompanying binary mask (`valid_mask.tif`):

| Stack Band | Alias | Sentinel-2 Key | Native Res | Target Res | Role in UrbanPulse |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **Band 1** | `blue` | **B02** | 10m | 10m | Atmospheric check & true color |
| **Band 2** | `green` | **B03** | 10m | 10m | Water detection (NDWI) |
| **Band 3** | `red` | **B04** | 10m | 10m | Chlorophyll absorption (NDVI) |
| **Band 4** | `nir` | **B08** | 10m | 10m | Vegetation & biomass (NDVI / NDWI / NDBI) |
| **Band 5** | `swir1` | **B11** | 20m | 10m | Built-up indicator (NDBI) & soil moisture |
| **Band 6** | `swir2` | **B12** | 20m | 10m | Built-up vs bare differentiation |
| **Auxiliary**| `mask` | **SCL** | 20m | 10m | Scene Classification valid-pixel mask |

---

## 4. Reflectance Handling & Baseline Offset Decision

### The Challenge: ESA Processing Baseline 04.00 Shift
On **January 25, 2022**, ESA deployed Sentinel-2 Processing Baseline `04.00`.
- **Pre-PB 04.00 (e.g. 2020, PB 02.12)**:
  Digital Numbers (DN) relate to surface reflectance via quantification value 10,000:
  $$\text{Reflectance} = \frac{\text{DN}}{10000.0}$$
- **PB 04.00+ (e.g. 2023 PB 04.00, 2026 PB 05.12)**:
  ESA introduced a radiometric offset `BOA_ADD_OFFSET = -1000` to represent negative reflectance values without zero-clipping:
  $$\text{Reflectance} = \frac{\text{DN} - 1000.0}{10000.0}$$

### Empirical Verification
Inspection of raw DN distributions over Hyderabad confirmed this shift:
- 2020 Blue (B02) median DN: `965.0` $\rightarrow 965 / 10000 = \mathbf{0.0965}$
- 2023 Blue (B02) median DN: `1850.0` $\rightarrow (1850 - 1000) / 10000 = \mathbf{0.0850}$

Blindly dividing all scenes by 10,000 would cause an artificial $+0.10$ reflectance spike in 2023 and 2026, generating catastrophic false change detections. UrbanPulse explicitly detects the acquisition date / baseline and corrects for `BOA_ADD_OFFSET = -1000` on PB 04.00+ scenes.

Values are clipped to the valid physical reflectance domain $[0.0, 1.0]$. Pixels with raw $\text{DN} = 0$ are assigned $\text{NaN}$ and marked invalid.

---

## 5. Cloud & Shadow Masking (SCL)
Scene Classification Layer (SCL) values are categorized:

- **Valid Surface Classes (1 in mask)**:
  - `2`: Dark feature pixels
  - `4`: Vegetation
  - `5`: Not-vegetated (soils, bare, rock)
  - `6`: Water
  - `7`: Unclassified (predominantly urban built-up surfaces in Hyderabad)
- **Masked Obscuration Classes (0 in mask)**:
  - `0`: No data
  - `1`: Saturated or defective pixels
  - `3`: Cloud shadows
  - `8`: Cloud medium probability
  - `9`: Cloud high probability
  - `10`: Thin cirrus
  - `11`: Snow or ice

---

## 6. Coordinate Reference System (CRS) & Analysis Grid
- **Analysis CRS**: `EPSG:32644` (WGS 84 / UTM Zone 44N, metric coordinates).
- **Target Spatial Resolution**: Exactly `10.0` meters.
- **Snapped Pixel Alignment**: Bounds are snapped to integer multiples of 10 meters:
  - $\text{minx} = 218370.0$, $\text{maxx} = 239860.0$ (Span: 21,490m)
  - $\text{miny} = 1919930.0$, $\text{maxy} = 1936830.0$ (Span: 16,900m)
  - **Dimensions**: $1690 \text{ rows} \times 2149 \text{ columns}$.
  - **Transform**: `Affine(10.0, 0.0, 218370.0, 0.0, -10.0, 1936830.0)`

All three epochs are projected and snapped to this identical geometry, guaranteeing pixel-to-pixel correspondence.

---

## 7. Resampling Strategy
- **Continuous Spectral Bands (B02, B03, B04, B08, B11, B12)**:
  Resampled using **Bilinear Interpolation** (`Resampling.bilinear`) to maintain continuous radiometric gradients, especially when upsampling 20m SWIR bands to 10m.
- **Categorical Layer (SCL)**:
  Resampled strictly using **Nearest-Neighbor** (`Resampling.nearest`) to preserve integer discrete class codes without blending class boundaries.

---

## 8. AOI Clipping & Windowed Streaming
To avoid downloading gigabytes of irrelevant satellite data, the pipeline performs windowed reads directly from Planetary Computer COG endpoints:
1. Transforms AOI bounds to the native raster CRS with a 200m buffer.
2. Clamps the read window to valid source coordinates.
3. Streams and writes local GeoTIFFs to `data/raw/sentinel2/{year}/{band}.tif`.
4. Reprojects only the AOI into the final analysis grid, producing compact ~85 MB stacks.

---

## 9. Quality Validation Checks
Before any scene stack is marked valid, `validate_preprocessed_scene` verifies:
- Exactly 6 spectral bands exist.
- CRS matches `EPSG:32644`.
- Pixel resolution is exactly $10.0\text{m} \times 10.0\text{m}$.
- Mask and stack dimensions and affine transforms match identically.
- Zero $\text{NaN}$ or $\text{Inf}$ values inside valid-pixel areas.
- Physical reflectance values lie within reasonable bounds $[-0.05, 1.20]$.
- Valid pixel percentage is recorded in `metadata.json`.

---

## 10. Temporal Comparability & Known Limitations

> [!WARNING]
> **Technical Honesty & Limitation**:
> Sentinel-2 observations are temporally comparable within the selected dry-season window, but acquisition dates differ (March 29 in 2020, January 28 in 2023, March 10 in 2026) and therefore seasonal/phenological effects cannot be assumed to be completely eliminated.

Differences in sun elevation, soil moisture following late-winter rains, and crop rotation schedules between late January and late March remain potential confounding variables. Downstream anomaly and change detection modules must use local neighborhood baselines and persistence filters to differentiate transient phenological fluctuations from structural urban development.
