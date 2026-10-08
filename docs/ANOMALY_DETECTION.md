# UrbanPulse — Anomaly Detection Specification (Step 6)

## 1. Executive Summary & Core Principle

In the UrbanPulse intelligence hierarchy:
$$\text{CHANGE} \longrightarrow \text{BASELINE} \longrightarrow \text{ANOMALY} \longrightarrow \text{EVIDENCE} \longrightarrow \text{PRIORITY}$$

Step 5 quantified physical multi-temporal spectral shifts ($\Delta \text{NDVI}, \Delta \text{NDWI}, \Delta \text{NDBI}$).  
**Step 6 answers the essential investigative question:**
> *"Is this observed change unusual compared with what normally happens across the scene (historical/temporal baseline) and what is happening immediately around it (spatial/neighborhood baseline)?"*

---

## 2. Why Change $\ne$ Anomaly

A fundamental flaw in naive remote-sensing pipelines is equating raw spectral change with an anomaly:
1. **Expected Broad-Scale Dynamics**: Urban agglomerations and semi-arid landscapes undergo seasonal greening, agricultural harvesting cycles, and regional dry-downs. A drop in NDVI across 5,000 hectares of cropland is **change**, but it is **not** an anomaly because it reflects the regional baseline.
2. **Context Matters**: A $-0.25$ decrease in NDVI within an agricultural belt where the entire zone dropped by $-0.24$ is normal. However, the exact same $-0.25$ drop in a dense, historically stable canopy corridor surrounded by stable canopy is an **extreme local anomaly**.
3. **Decoupling**: By measuring deviations relative to both the scene's distribution and the local spatial neighborhood, UrbanPulse isolates true localized perturbations from widespread macro-scale variations.

---

## 3. Scene-Level Change Anomaly Engine (Temporal Component)

UrbanPulse analyzes three observation epochs: **2020, 2023, and 2026**.  

### 3.1 Scientific Clarification: Scene-Level Distribution vs. Historical Time Series
It is critical to distinguish what this component mathematically represents:
- **What it IS**: A **scene-level change anomaly**. For each comparison period ($2020 \to 2023$, $2023 \to 2026$, $2020 \to 2026$), it calculates whether a pixel's observed shift $\Delta I$ is statistically unusual relative to the empirical distribution of changes occurring across the entire metropolitan scene during that epoch.
- **What it is NOT**: It is **NOT** a dense, per-location historical temporal baseline (e.g. BFAST, LandTrendr, or harmonic regression fitting). Establishing a true per-location historical baseline requires 15–30+ dense, regular observations over multi-year cycles. With only three multi-year snapshots, UrbanPulse does not fabricate non-existent temporal observations.
- **Why this is valid**: In rapid urban monitoring, scene-level contextualization identifies locations undergoing shifts far beyond the regional background rate (e.g. standard phenological drying vs. severe localized land stripping).

### 3.2 Robust Center and Dispersion
Rather than ordinary mean and standard deviation (which are heavily distorted by extreme land clearing and outliers), UrbanPulse employs **robust nonparametric statistics**:
- **Robust Center**: $\text{Median}(\Delta I)$
- **Median Absolute Deviation (MAD)**:
  $$\text{MAD} = \text{Median}(|\Delta I - \text{Median}(\Delta I)|)$$
- **Consistent Robust Dispersion ($\hat{\sigma}_{\text{robust}}$)**:
  Under standard normal assumptions, $\text{MAD} / 0.6745 \approx 1.4826 \cdot \text{MAD}$ estimates standard deviation.
  $$\hat{\sigma}_{\text{robust}} = \frac{\text{MAD}}{0.6745}$$

### 3.3 Robust Z-Score
For each valid pixel $p$ with change $\Delta I(p)$:
$$z_{\text{robust}}(p) = \frac{\Delta I(p) - \text{Median}(\Delta I)}{\hat{\sigma}_{\text{robust}}} = 0.6745 \cdot \frac{\Delta I(p) - \text{Median}(\Delta I)}{\text{MAD}}$$

### 3.4 Zero-MAD / Low-Dispersion Safeguard
In highly uniform sub-regions or synthetic test cases where $\text{MAD} < \text{mad\_floor}$ ($10^{-3}$), division by zero is strictly avoided:
$$\hat{\sigma}_{\text{robust}} = \max\left(\frac{\text{MAD}}{0.6745}, \frac{\text{mad\_floor}}{0.6745}\right)$$
This fallback is recorded explicitly in statistical metadata (`"used_dispersion_fallback": true`).

### 3.5 Bounded Anomaly Transformation
Standardized deviations are converted into a stable, deterministic $[0.0, 1.0]$ anomaly strength score:
$$S_{\text{temporal}}(p) = \min\left(1.0, \frac{|z_{\text{robust}}(p)|}{z_{\text{clip}}}\right)$$
where $z_{\text{clip}} = 3.5$.
- $S = 0.0$: Change aligns exactly with the scene median.
- $S \ge 1.0$: Change deviates by $\ge 3.5$ robust standard deviations.
- Invalid pixels: Strictly `np.nan`.

---

## 4. Spatial / Neighborhood Anomaly Engine

To determine if a pixel's change is anomalous relative to its surrounding urban fabric:

### 4.1 Configurable Rolling Window
At 10m Sentinel-2 resolution, a window of $21 \times 21$ pixels represents **$210\text{m} \times 210\text{m}$** ($\approx 4.41\text{ hectares}$), matching the physical footprint of typical urban block typologies.

### 4.2 Exact Valid Neighbor Accounting & Edge Behavior
- Valid neighbor counts within each window are computed via uniform convolution:
  $$N_{\text{valid}}(p) = \sum_{q \in W(p)} \mathbf{1}_{\text{valid}}(q)$$
- **Strict rule**: If $N_{\text{valid}}(p) < \text{minimum\_valid\_neighbors}$ (configured as 20), the spatial anomaly is marked **invalid** and assigned `np.nan`. Invalid pixels never contribute false zeroes.

### 4.3 Local Robust Deviation
Within each window:
$$\text{med}_{\text{local}}(p) = \text{Median}_{q \in W(p)}(\Delta I(q))$$
$$\text{MAD}_{\text{local}}(p) = \text{Median}_{q \in W(p)}(|\Delta I(q) - \text{med}_{\text{local}}(p)|)$$
$$\hat{\sigma}_{\text{local}}(p) = \max\left(\frac{\text{MAD}_{\text{local}}(p)}{0.6745}, \frac{\text{mad\_floor}}{0.6745}\right)$$
$$z_{\text{spatial}}(p) = \frac{\Delta I(p) - \text{med}_{\text{local}}(p)}{\hat{\sigma}_{\text{local}}(p)}$$
$$S_{\text{spatial}}(p) = \min\left(1.0, \frac{|z_{\text{spatial}}(p)|}{z_{\text{clip}}}\right)$$

---

## 5. Anomaly Fusion & Scientific Review of Aggregation

Temporal and spatial components are synthesized via explainable weighted combination:
$$S_{\text{combined}}(p) = w_{\text{temporal}} \cdot S_{\text{temporal}}(p) + w_{\text{spatial}} \cdot S_{\text{spatial}}(p)$$
Default weights (`config/config.yaml`): $w_{\text{temporal}} = 0.6, w_{\text{spatial}} = 0.4$.

### 5.1 Component Availability Logic:
- **Both Valid**: Full weighted sum.
- **Single Component Valid** (e.g. boundary pixels with valid temporal data but $< 20$ spatial neighbors): If `fallback_to_available_component: true`, the available score is utilized and flagged in metadata; otherwise `np.nan`.

### 5.2 Overall Multi-Indicator Anomaly Aggregation: Empirical Review

We systematically evaluated three candidate aggregations across the 3.61 million real pixels of the Hyderabad study area:
1. **Candidate A: Maximum Aggregation (`max`)**:
   $$S_{\text{overall}} = \max\left(S_{\text{ndvi\_comb}}, S_{\text{ndwi\_comb}}, S_{\text{ndbi\_comb}}\right)$$
2. **Candidate B: Mean Aggregation (`mean`)**:
   $$S_{\text{overall}} = \frac{1}{3} \left(S_{\text{ndvi\_comb}} + S_{\text{ndwi\_comb}} + S_{\text{ndbi\_comb}}\right)$$
3. **Candidate C: Corroborated / Top-Two Aggregation (`corroborated`)**:
   $$S_{\text{overall}} = 0.70 \cdot S_{(1)} + 0.30 \cdot S_{(2)} \quad (\text{where } S_{(1)} \ge S_{(2)} \ge S_{(3)})$$

#### Empirical Comparison on Real 2020 → 2023 Sentinel-2 Data ($N = 3,613,656$ valid pixels):

| Aggregation Method | Median | p95 | Pixels $\ge 0.50$ | Pixels $\ge 0.70$ | Veg-Only Subset ($N=452,752$) Median / $\ge 0.50$ | Coherent Subset ($N=99,832$) Median / $\ge 0.50$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. `max` (Default Ceiling)** | **0.324** | **0.836** | **24.41%** | **10.25%** | 0.689 / **100.0%** | **0.846 / 100.0%** |
| **B. `mean` (Uniform Dilution)** | 0.208 | 0.626 | 10.11% | 3.05% | 0.508 / 52.2% | 0.721 / 94.8% |
| **C. `corroborated` (Top-2 Blend)** | 0.287 | 0.774 | 19.30% | 7.59% | 0.647 / 88.2% | 0.810 / 100.0% |

#### Scientific Justification for UrbanPulse Architecture:
1. **Why `mean` is NOT Defensible**: A pure lake contraction or reservoir drying event causes an extreme NDWI anomaly ($S_{\text{ndwi}} \approx 0.95$), while surrounding vegetation and built-up indices may be quiescent ($S \approx 0.10$). Under `mean` aggregation, this genuine, severe environmental anomaly is diluted down to $(0.95 + 0.10 + 0.10)/3 = 0.38$, falling below the $0.50$ threshold.
2. **Why `max` is the Most Defensible Anomaly Ceiling**:
   - The purpose of the **Anomaly Layer** is to measure *maximum unusual physical deviation* across any observable environmental dimension without premature suppression.
   - The question of whether an anomaly is an uncorroborated single-band shift (e.g. crop cycle) versus a multi-spectral urban expansion pattern (vegetation loss + built-up increase) is **explicitly resolved by the Evidence Layer** (`vegetation_builtup_coherence`, `persistent_change_present`, `reversal_present`).
   - In Step 7, the **Priority Engine** integrates the continuous Anomaly Ceiling with the Evidence Flags. Discarding or diluting single-band anomalies in Step 6 would deprive Step 7 of crucial investigative signal.
   - For analytical flexibility, `aggregation_method: "max"` is fully configurable in `config/config.yaml` (`"max"`, `"mean"`, or `"corroborated"`).

---

## 6. Cross-Indicator Evidence & Consistency

To prevent isolated spectral noise from triggering false alarms, Step 6 cross-correlates multi-spectral signatures:

1. **`vegetation_change_present`**: $S_{\text{ndvi\_combined}} \ge 0.50$
2. **`water_change_present`**: $S_{\text{ndwi\_combined}} \ge 0.50$
3. **`builtup_signal_present`**: $S_{\text{ndbi\_combined}} \ge 0.50$
4. **`vegetation_builtup_coherence`**:
   $$\Delta \text{NDVI} < 0 \land \Delta \text{NDBI} > 0 \land S_{\text{ndvi\_combined}} \ge 0.50 \land S_{\text{ndbi\_combined}} \ge 0.50$$
   *Physical Meaning*: Simultaneous vegetation loss and built-up response increase—an urban-expansion-consistent spectral pattern.
5. **`persistent_change_present`**: Verified multi-period directional continuity from Step 5 persistence raster.
6. **`reversal_present`**: Non-monotonic directional flip from Step 5 reversal raster (suppresses cyclical false alarms).

---

## 7. Output Specifications

Outputs are structured in `data/processed/anomaly_detection/`:
- **`temporal/{period}/temporal_anomaly.tif`**: 3 bands (NDVI, NDWI, NDBI float32)
- **`spatial/{period}/spatial_anomaly.tif`**: 3 bands (NDVI, NDWI, NDBI float32)
- **`combined/{period}/combined_anomaly.tif`**: 4 bands (NDVI, NDWI, NDBI, overall combined float32)
- **`combined/{period}/anomaly_stack.tif`**: Unified 10-band float32 GeoTIFF
- **`evidence/{period}/evidence_flags.tif`**: 7-band UInt8 GeoTIFF
- **`statistics/{period}.json`**: Full empirical distribution summaries

---

## 8. Important Scientific Caveats & Limitations

1. **Acquisition Date Variations**:
   - 2020: `2020-03-29`
   - 2023: `2023-01-28`
   - 2026: `2026-03-10`
   All fall within the dry-season window, but differences in day-of-year introduce uncorrected phenological moisture variations. Local spatial windowing helps isolate point anomalies from this macro effect.
2. **Anomaly $\ne$ Ground Truth / Causality**:
   The engine flags statistical deviations in spectral response. It does not establish legal land zoning, construction permits, or deforestation causality.
3. **Anomaly $\ne$ Priority**:
   An anomaly in an uninhabited barren quarry may be statistically extreme but low priority, whereas an anomaly on a lake boundary or reserve forest buffer is high priority. That contextual synthesis belongs to Step 7.
