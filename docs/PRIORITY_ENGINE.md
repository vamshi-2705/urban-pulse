# UrbanPulse — Priority Engine & Investigation Ranking (Step 7)

## 1. Purpose

The UrbanPulse **Priority Engine** synthesizes multi-temporal satellite evidence across change detection, anomaly detection, and cross-indicator coherence into a transparent, explainable decision-support ranking for human field investigators.

> **CRITICAL SCIENTIFIC PRINCIPLE:**
> **Priority score is an explainable ranking signal, not a ground-truth probability of illegal or harmful activity.**
>
> **UrbanPulse detects observable spatial/temporal land-cover patterns; human field verification is required to establish the cause.**
>
> The objective is **NOT** to predict illegality, fraud, flood disasters, or future events.
> The objective is:
> *"Rank locations by how strongly the available multi-spectral evidence suggests that the observed land-cover change deserves human investigation."*

```
CHANGE (Step 5)
   ↓
SCENE-LEVEL ANOMALY (Step 6)
   ↓
CROSS-INDICATOR EVIDENCE (Step 6)
   ↓
PRIORITY ENGINE (Step 7)
   ↓
[Top-K Hotspots & Decision Support]
```

---

## 2. Input Datasets & Lineage

The Priority Engine strictly reuses existing outputs from Step 5 and Step 6 without inventing data or downloading external datasets:

| Signal Category | Source Layer | Bands / Fields Used | Semantic Role |
| :--- | :--- | :--- | :--- |
| **Combined Anomaly** | `anomaly_stack.tif` | Band 10 (`overall_combined_anomaly`) | Statistical severity of change across scene distribution |
| **Spatial Anomaly** | `anomaly_stack.tif` | Bands 4, 5, 6 (`NDVI_spatial`, `NDWI_spatial`, `NDBI_spatial`) | Local neighborhood contrast (rolling window deviation) |
| **Spectral Changes** | `change_stack.tif` | Bands 1–6 ($\Delta \text{NDVI}, \Delta \text{NDWI}, \Delta \text{NDBI}$ & magnitudes) | Direction and absolute physical scale of spectral shifts |
| **Evidence Coherence** | `evidence_flags.tif` | Band 4 (`vegetation_builtup_coherence`) | Co-occurrence of vegetation loss + built-up increase |
| **Multi-Domain Flags** | `evidence_flags.tif` | Bands 1, 2, 3 (Veg change, Water change, Built-up signal) | Cross-domain verification count |
| **Persistence** | `persistence.tif` / `evidence_flags.tif` | Bands 1, 3, 5 / Band 5 (`persistent_change_present`) | Multi-temporal directional stability across snapshots |
| **Reversal** | `evidence_flags.tif` | Band 6 (`reversal_present`) | Directional turnaround (cyclical or seasonal fluctuations) |

---

## 3. Mathematical Formula & Architecture

The priority score $P \in [0.0, 1.0]$ is computed as a transparent linear combination of 5 normalized components:

$$P = w_{\text{anomaly}} \cdot S_{\text{anomaly}} + w_{\text{evidence}} \cdot S_{\text{evidence}} + w_{\text{persistence}} \cdot S_{\text{persistence}} + w_{\text{magnitude}} \cdot S_{\text{magnitude}} + w_{\text{spatial}} \cdot S_{\text{spatial}}$$

### Baseline Weight Scheme

| Component | Weight | Default Value | Rationale & Interpretation |
| :--- | :---: | :---: | :--- |
| $S_{\text{anomaly}}$ | $w_{\text{anomaly}}$ | **0.35** | Primary driver: statistical rarity of change compared to scene-level baseline. |
| $S_{\text{evidence}}$ | $w_{\text{evidence}}$ | **0.25** | Physical verification: multi-spectral coherence (e.g. green space $\to$ impervious surface). |
| $S_{\text{persistence}}$ | $w_{\text{persistence}}$ | **0.20** | Stability bonus: persistent shifts represent permanent interventions, not seasonal noise. |
| $S_{\text{magnitude}}$ | $w_{\text{magnitude}}$ | **0.10** | Physical shift magnitude: large absolute deltas ($\Delta \ge 0.25$) represent major physical alterations. |
| $S_{\text{spatial}}$ | $w_{\text{spatial}}$ | **0.10** | Local neighborhood contrast: localized cluster of change stands out against surroundings. |
| **Total** | $\sum w$ | **1.00** | Strictly normalized to $[0.0, 1.0]$. |

---

## 4. Component Normalization & Formulations

Every component is explicitly mapped to $[0.0, 1.0]$ prior to weighting:

### 1. Scene-Level Anomaly ($S_{\text{anomaly}}$)
- Sourced directly from Step 6 `overall_combined_anomaly` (Band 10).
- Already bounded in $[0.0, 1.0]$ via the smooth saturation function:
  $$S_{\text{anomaly}} = \min\left(1.0, \max\left(0.0, \frac{|z| - z_{\text{min}}}{z_{\text{max}} - z_{\text{min}}}\right)\right)$$

### 2. Evidence Strength ($S_{\text{evidence}}$)
Evaluates cross-indicator coherence, domain representation, anomaly severity, and cyclical reversal dampening:
$$S_{\text{evidence}} = \text{clip}\left(0.50 \cdot \mathbf{1}_{\text{coherence}} + 0.30 \cdot \frac{\mathbf{1}_{\text{veg}} + \mathbf{1}_{\text{water}} + \mathbf{1}_{\text{built}}}{3.0} + 0.20 \cdot S_{\text{anomaly}} - 0.25 \cdot \mathbf{1}_{\text{reversal}}, \; 0.0, \; 1.0\right)$$
- Coherent green-to-built transitions receive $+0.50$.
- Each physical domain signal contributes up to $+0.10$.
- High anomaly severity adds $+0.20$.
- Cyclical reversals (indicative of seasonal crop rotations or ephemeral ponding) penalize the score by $-0.25$.

### 3. Multi-Temporal Persistence ($S_{\text{persistence}}$)
- Indicator of multi-year directional consistency:
  $$S_{\text{persistence}} = \mathbf{1}_{\text{persistent}} \in \{0.0, 1.0\}$$
- Evaluated across the 2020 $\to$ 2023 $\to$ 2026 tri-epoch sequence.

### 4. Physical Change Magnitude ($S_{\text{magnitude}}$)
- Measures absolute delta across the 3 spectral indices, scaled against an extreme physical change saturation threshold ($0.50$):
  $$\Delta_{\max} = \max(|\Delta \text{NDVI}|, |\Delta \text{NDWI}|, |\Delta \text{NDBI}|)$$
  $$S_{\text{magnitude}} = \text{clip}\left(\frac{\Delta_{\max}}{0.50}, \; 0.0, \; 1.0\right)$$

### 5. Spatial Context ($S_{\text{spatial}}$)
- Sourced from Step 6 spatial neighborhood anomaly (Bands 4, 5, 6):
  $$S_{\text{spatial}} = \max\left(\text{NDVI}_{\text{spatial}}, \text{NDWI}_{\text{spatial}}, \text{NDBI}_{\text{spatial}}\right) \in [0.0, 1.0]$$

---

## 5. Thresholds & Investigation Categories

The continuous priority score is mapped to discrete operational categories:

| Priority Level | Score Range | Operational Recommendation | Action Guidance |
| :---: | :---: | :--- | :--- |
| **HIGH** | $\ge \mathbf{0.70}$ | `FIELD_VERIFICATION_RECOMMENDED` | Urgent dispatch for on-the-ground verification of physical land alteration. |
| **MEDIUM** | $[\mathbf{0.45}, \mathbf{0.70})$ | `MONITOR_AND_REVIEW` | Secondary queue; desktop inspection with high-resolution imagery recommended. |
| **LOW** | $<\mathbf{0.45}$ | `ROUTINE_OBSERVATION` | Background baseline variation; standard automated monitoring cycle. |
| **INVALID** | $\text{NaN}$ | `DATA_UNAVAILABLE` | Cloudy, shadowed, or nodata pixels excluded from evaluation. |

---

## 6. Machine-Readable Reason Codes

Every candidate location includes unambiguous, satellite-derived reason codes explaining why it received its score:

| Reason Code | Trigger Condition | Observational Interpretation |
| :--- | :--- | :--- |
| `HIGH_SCENE_ANOMALY` | $S_{\text{anomaly}} \ge 0.70$ | Observed change is statistically rare across the study area scene distribution. |
| `SPATIAL_ANOMALY` | $S_{\text{spatial}} \ge 0.60$ | Pixel change strongly deviates from its immediate spatial neighborhood ($15 \times 15$ window). |
| `VEG_BUILTUP_COHERENCE` | Coherence flag active | Simultaneous vegetation decrease ($\Delta \text{NDVI} \le -\epsilon$) and built-up increase ($\Delta \text{NDBI} \ge +\epsilon$). |
| `VEGETATION_LOSS` | $\Delta \text{NDVI} \le -0.15$ | Substantial drop in photosynthetic canopy or green cover. |
| `BUILTUP_SENSITIVE_CHANGE` | $\Delta \text{NDBI} \ge +0.15$ | Substantial increase in shortwave-infrared impervious surface reflectance. |
| `WATER_CHANGE` | $|\Delta \text{NDWI}| \ge 0.15$ | Significant alteration in surface moisture or open water extent. |
| `PERSISTENT_CHANGE` | Persistence flag active | Change direction maintained across consecutive multi-year observation epochs. |
| `STRONG_CHANGE_MAGNITUDE` | $\Delta_{\max} \ge 0.25$ | Severe spectral displacement across one or more index domains. |
| `CYCLICAL_REVERSAL_DAMPENED` | Reversal flag active | Trajectory reversed across epochs (e.g. crop cycle or temporary ponding); priority dampened. |

---

## 7. 500m Geographic Grid Tessellation & Aggregation

To provide decision support suitable for municipal dispatch:
1. The study area is partitioned into a regular **500m $\times$ 500m grid** in UTM Zone 44N (EPSG:32644), yielding **1,462 cells** (`HYD_0001` through `HYD_1462`).
2. Each 500m cell encompasses up to $50 \times 50 = 2,500$ Sentinel-2 10m pixels.
3. The representative cell **priority score** is calculated as the **90th percentile** of valid pixel priority scores within the cell:
   - Captures focal land-cover interventions within the cell.
   - Remains robust against isolated single-pixel sensor noise or georeferencing artifacts.
4. Hotspots are ranked descending by priority score and exported as **Top 10**, **Top 25**, and **Top 50** candidate investigation lists.

### Sample "Why Flagged" Output Record
```json
{
  "grid_id": "HYD_0863",
  "priority_score": 0.7787,
  "priority_level": "HIGH",
  "reasons": [
    "HIGH_SCENE_ANOMALY",
    "SPATIAL_ANOMALY",
    "VEG_BUILTUP_COHERENCE",
    "VEGETATION_LOSS",
    "BUILTUP_SENSITIVE_CHANGE",
    "WATER_CHANGE",
    "PERSISTENT_CHANGE",
    "STRONG_CHANGE_MAGNITUDE",
    "CYCLICAL_REVERSAL_DAMPENED"
  ],
  "signals": {
    "overall_anomaly": 0.8728,
    "spatial_anomaly": 0.7311,
    "ndvi_anomaly": 0.843,
    "ndwi_anomaly": 0.7913,
    "ndbi_anomaly": 0.7997,
    "ndvi_delta": -0.6065,
    "ndwi_delta": 0.1877,
    "ndbi_delta": 0.3809,
    "evidence_strength": 0.3649,
    "persistence": 1.0,
    "veg_builtup_coherence": 1.0,
    "reversal": 1.0,
    "valid_pixels": 2500,
    "cell_score_max": 1.0
  },
  "recommendation": "FIELD_VERIFICATION_RECOMMENDED",
  "latitude": 17.407605,
  "longitude": 78.360919,
  "rank": 1
}
```

---

## 8. Real-Data Validation Diagnostics & Background Comparison

The engine was executed across all three observation epochs (2020 $\to$ 2023, 2023 $\to$ 2026, and 2020 $\to$ 2026).

### Period Summary Statistics

| Comparison Period | Valid 500m Cells | Median Score | P95 Score | HIGH Priority Cells | MEDIUM Priority Cells | LOW Priority Cells |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **2020 $\to$ 2023** | 1,462 | 0.3913 | 0.5595 | **11** (0.75%) | **300** (20.52%) | **1,151** (78.73%) |
| **2023 $\to$ 2026** | 1,462 | 0.3836 | 0.5373 | **0** (0.00%) | **275** (18.81%) | **1,187** (81.19%) |
| **2020 $\to$ 2026** | 1,462 | 0.4107 | 0.6172 | **27** (1.85%) | **453** (30.98%) | **982** (67.17%) |

### High-Priority Evidence Composition (2020 $\to$ 2026)
- **Vegetation + Built-up Coherence:** 100.0% of HIGH cells exhibit coherent green-loss + built-up increase.
- **Strong Anomaly ($S_{\text{anom}} \ge 0.70$):** 100.0% of HIGH cells exhibit extreme scene anomalies.
- **Multi-Temporal Persistence:** 92.59% of HIGH cells are confirmed persistent across multi-year intervals.

### Background Comparison Check (High Priority vs Background Cells)

| Metric | HIGH Priority Locations | Background (LOW) Locations | Ratio / Contrast | Diagnostic Verification |
| :--- | :---: | :---: | :---: | :--- |
| **Mean Priority Score** | **0.7603** | **0.3849** | **1.98x** | Substantially elevated decision urgency |
| **Mean Overall Anomaly** | **0.8570** | **0.6426** | **1.33x** | Strong statistical anomaly signal |
| **Coherence Rate** | **1.0000** | **0.0570** | **17.5x** | Coherent multi-spectral signature dominates |
| **Persistence Rate** | **0.9259** | **0.0000** | **$\infty$** | Background cells show zero persistent intervention |

**Diagnostic Conclusion:**
The priority ranking is genuinely driven by physical and statistical evidence, not random background noise or artificial threshold inflation.

---

## 9. Limitations & Caveats

1. **Snapshot Sparsity:**
   With three observation dates (March 2020, January 2023, March 2026), the engine detects multi-year net changes, not daily or monthly event sequences.
2. **Phenological Seasonality:**
   Agricultural cycles and dry-season vegetation dormancy can cause seasonal spectral drops. The `CYCLICAL_REVERSAL_DAMPENED` flag and persistence checks help mitigate this, but human verification remains necessary.
3. **Absence of Ground Truth:**
   Priority rankings do not measure classification accuracy or legal violation rates.

---

## 10. Future Calibration with Ground-Truth Labels

If and when municipal field verification outcomes become available (e.g. *Confirmed Unauthorized Excavation*, *Permitted Construction*, *Agricultural Fallow*):
- The model weights $(w_{\text{anom}}, w_{\text{evid}}, w_{\text{persist}}, w_{\text{mag}}, w_{\text{spat}})$ can be calibrated via logistic regression or rank optimization (e.g. maximizing Precision@K or NDCG).
- Feature importance and threshold cutoffs can be tuned to optimize field inspector caseload capacity.
- The transparent, modular design ensures full backward compatibility with future calibration datasets.
