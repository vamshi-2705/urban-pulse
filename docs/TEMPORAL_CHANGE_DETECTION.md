# UrbanPulse — Temporal Change Detection Specification (Step 5)

## 1. Overview & Objective

Temporal change detection in UrbanPulse transforms multi-temporal spectral indicators (NDVI, NDWI, NDBI) into rigorous, quantitative **change evidence**. The system evaluates shifts between sequential observation epochs (2020, 2023, and 2026) across the Hyderabad metropolitan prototype area ($500\text{m} \times 500\text{m}$ grid extent).

Crucially, UrbanPulse adheres to the core intelligence sequence:
$$\text{CHANGE} \longrightarrow \text{BASELINE} \longrightarrow \text{ANOMALY} \longrightarrow \text{EVIDENCE} \longrightarrow \text{PRIORITY}$$

Step 5 strictly generates **spectral change evidence**. It does not perform anomaly scoring, priority ranking, or discrete ground-truth land classification.

---

## 2. Mathematical Definitions

All calculations are computed in **`float32`** on calibrated surface reflectance indices:

### 2.1 Pairwise Shift (Delta)
For any spectral indicator $I \in \{\text{NDVI}, \text{NDWI}, \text{NDBI}\}$ and comparison period $(t_1 \to t_2)$ where $t_2 > t_1$:
$$\Delta I = I_{t_2} - I_{t_1}$$

### 2.2 Change Magnitude
$$\text{Magnitude}(\Delta I) = |\Delta I|$$

### 2.3 Analytical Direction & Epsilon Tolerance ($\epsilon$)
Direct numerical difference ($\Delta I \ne 0$) cannot be treated as real surface alteration due to sensor view geometry variations, atmospheric correction residuals, and minor phenology. UrbanPulse enforces configurable analytical tolerance thresholds $\epsilon$:

$$\text{Direction}(\Delta I) = \begin{cases}
+1 & \text{if } \Delta I > \epsilon \\
0 & \text{if } |\Delta I| \le \epsilon \\
-1 & \text{if } \Delta I < -\epsilon
\end{cases}$$

Default prototype tolerances configured in `config/config.yaml`:
- $\epsilon_{\text{NDVI}} = 0.10$
- $\epsilon_{\text{NDWI}} = 0.10$
- $\epsilon_{\text{NDBI}} = 0.10$

---

## 3. Indicator-Specific Change Signals

To maintain scientific integrity and avoid premature over-interpretation:

### 3.1 Vegetation Change (NDVI)
- **`vegetation_loss`**: $\Delta \text{NDVI} < -\epsilon_{\text{NDVI}}$  
  *Honest Description*: "Vegetation-signal decrease" (NOT "deforestation" or "greenery destruction"). Can indicate harvest, seasonal dieback, site grading, or surface paving.
- **`vegetation_gain`**: $\Delta \text{NDVI} > +\epsilon_{\text{NDVI}}$  
  *Honest Description*: "Vegetation-signal increase" (vegetation regrowth, seasonal greening, or landscaping).

### 3.2 Water Change (NDWI)
- **`water_loss`**: $\Delta \text{NDWI} < -\epsilon_{\text{NDWI}}$  
  *Honest Description*: "Water-sensitive signal decrease" (NOT "lake disappeared"). Reflects reduced surface water reflectance, tank shrinkage, or increased turbidity/vegetation encroachment.
- **`water_gain`**: $\Delta \text{NDWI} > +\epsilon_{\text{NDWI}}$  
  *Honest Description*: "Water-sensitive signal increase" (inundation, reservoir expansion, or wet soil).

### 3.3 Built-Up-Sensitive Change (NDBI)
- **`builtup_increase`**: $\Delta \text{NDBI} > +\epsilon_{\text{NDBI}}$  
  *Honest Description*: "Built-up-sensitive spectral increase" (NOT "new buildings"). Responds to impervious surfaces, concrete, masonry, bare dry soil, excavation sites, and cleared parcels.
- **`builtup_decrease`**: $\Delta \text{NDBI} < -\epsilon_{\text{NDBI}}$  
  *Honest Description*: "Built-up-sensitive spectral decrease" (revegetation, inundation, shadow).

---

## 4. Multi-Temporal Trajectory: Persistence & Reversals

Single-period spectral shifts can easily be caused by transient events (e.g. agricultural harvesting cycles or ephemeral pooling). Persistent multi-epoch trajectories represent much stronger investigative evidence.

Comparing sequential intervals:
- **Period A**: $2020 \to 2023$
- **Period B**: $2023 \to 2026$

### 4.1 Persistence Signals
A signal persists only when the directional change continues across both intervals:
1. **Persistent Vegetation Decrease**: $\text{Loss}_A \land \text{Loss}_B$
2. **Persistent Vegetation Increase**: $\text{Gain}_A \land \text{Gain}_B$
3. **Persistent Water Decrease**: $\text{Loss}_A \land \text{Loss}_B$
4. **Persistent Water Increase**: $\text{Gain}_A \land \text{Gain}_B$
5. **Persistent Built-Up Increase**: $\text{Increase}_A \land \text{Increase}_B$
6. **Persistent Built-Up Decrease**: $\text{Decrease}_A \land \text{Decrease}_B$

### 4.2 Reversal Trajectory Detection
Reversals indicate opposite movement between consecutive periods:
- **Vegetation Reversal**: $(\text{Loss}_A \land \text{Gain}_B) \lor (\text{Gain}_A \land \text{Loss}_B)$
- **Water Reversal**: $(\text{Loss}_A \land \text{Gain}_B) \lor (\text{Gain}_A \land \text{Loss}_B)$
- **Built-Up Reversal**: $(\text{Increase}_A \land \text{Decrease}_B) \lor (\text{Decrease}_A \land \text{Increase}_B)$

Reversals are essential false-alarm suppressors for Step 6, distinguishing rotational crop patterns or seasonal ponding from permanent urban expansion.

---

## 5. Validity Propagation & Edge Cases

If a pixel is invalid in *either* observation epoch of a comparison:
$$\text{Valid}_{t_1 \to t_2} = \text{Valid}_{t_1} \land \text{Valid}_{t_2} \land \text{isfinite}(I_{t_1}) \land \text{isfinite}(I_{t_2})$$

- **Invalid pixels**: Assigned `np.nan` for continuous delta and magnitude layers, and `0` in binary signal layers and validity masks.
- **Critical rule**: Zero ($0.0$) is a valid delta value (indicating spectral stability) and is **never** used to encode missing or invalid data.

---

## 6. Output Raster Specifications

### 6.1 Pairwise Change Stack (`change_stack.tif`)
Stored in `data/processed/change_detection/{period}/`:
- **Format**: 12-band GeoTIFF, `Float32`, LZW compressed
- **Spatial Grid**: Preserves ARD grid ($1690 \times 2149$, EPSG:32644, 10m resolution)
- **Band Structure**:
  1. `NDVI_delta`
  2. `NDVI_abs_change`
  3. `NDWI_delta`
  4. `NDWI_abs_change`
  5. `NDBI_delta`
  6. `NDBI_abs_change`
  7. `vegetation_loss` (1.0 or 0.0)
  8. `vegetation_gain` (1.0 or 0.0)
  9. `water_loss` (1.0 or 0.0)
  10. `water_gain` (1.0 or 0.0)
  11. `builtup_increase` (1.0 or 0.0)
  12. `builtup_decrease` (1.0 or 0.0)
- Accompanying: `valid_mask.tif` (1-band `uint8`)

### 6.2 Multi-Temporal Persistence Stack (`persistence.tif`)
Stored in `data/processed/change_detection/multitemporal/`:
- **Format**: 9-band GeoTIFF, `UInt8`, LZW compressed
- **Band Structure**:
  1. `persistent_vegetation_decrease`
  2. `persistent_vegetation_increase`
  3. `persistent_water_decrease`
  4. `persistent_water_increase`
  5. `persistent_builtup_increase`
  6. `persistent_builtup_decrease`
  7. `vegetation_reversal`
  8. `water_reversal`
  9. `builtup_reversal`
- Accompanying: `valid_mask.tif` (1-band `uint8`)

---

## 7. Temporal Acquisition Limitations

The observation dates for the three epochs are:
- **2020**: `2020-03-29` (DOY 89)
- **2023**: `2023-01-28` (DOY 28)
- **2026**: `2026-03-10` (DOY 69)

While all three acquisitions fall within the configured regional dry/post-monsoon window (January–March), they are not on the identical day of the year:
- **Late January vs. Late March**: Natural vegetation in semi-arid Hyderabad exhibits lower moisture and accelerated senescence in late March relative to late January.
- **Phenological Bias**: Some fraction of detected $\Delta \text{NDVI}$ between January 2023 and March 2026 reflects seasonal vegetation dry-down rather than anthropogenic land clearing.
- **Handling in UrbanPulse**: Downstream Step 6 handles this by computing local/neighborhood spatial context baselines rather than relying solely on global delta thresholds.

---

## 8. Why Change $\ne$ Anomaly $\ne$ Priority

A core architectural principle of UrbanPulse is decoupling change from priority:

1. **Change is Expected in Dynamic Metropolises**:
   - Seasonal water fluctuations, crop rotation, and planned development corridors undergo natural change.
   - Widespread regional shifts (e.g. city-wide vegetation decrease due to dry spell) are **not** localized anomalies.

2. **Anomaly Requires Local & Historical Baseline Divergence**:
   - A cell is anomalous only if its change trajectory significantly deviates from its spatial neighborhood (e.g. a sudden 500m cleared patch surrounded by stable canopy) or historical baseline.

3. **Priority Requires Multi-Factor Evidence & Context**:
   - Priority ranking integrates anomaly magnitude, persistence, proximity to sensitive buffers (lakes, reserves), and multi-spectral coherence before generating field investigation alerts.
