"""
UrbanPulse - Priority Scoring Engine (Step 7).

Implements a transparent, explainable feature-based priority ranking model:
- Combines 5 normalized evidence components:
    1. Scene-level anomaly severity (S_anomaly)
    2. Cross-indicator evidence strength (S_evidence)
    3. Multi-temporal persistence (S_persistence)
    4. Physical change magnitude (S_magnitude)
    5. Spatial neighborhood context (S_spatial_context)
- Strictly bounded within [0.0, 1.0].
- Preserves NaN / invalid masks without imputation.
- Assigns interpretable priority levels (HIGH, MEDIUM, LOW) and recommendations.
- Produces machine-readable reason codes describing satellite-derived evidence.

SCIENTIFIC PRINCIPLE:
The priority score is an explainable decision-support ranking signal, NOT a
predictive probability of illegality, fraud, flood risk, or urban hazards.
Human field verification is required to establish real-world cause.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

from config.settings import PriorityConfig, PriorityThresholdsConfig, PriorityWeightsConfig
from geospatial.logger import get_logger

logger = get_logger("geospatial.priority.priority_scoring")

PRIORITY_LEVEL_NAMES: Dict[int, str] = {
    0: "INVALID",
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
}

PRIORITY_RECOMMENDATIONS: Dict[str, str] = {
    "HIGH": "FIELD_VERIFICATION_RECOMMENDED",
    "MEDIUM": "MONITOR_AND_REVIEW",
    "LOW": "ROUTINE_OBSERVATION",
    "INVALID": "DATA_UNAVAILABLE",
}


def calculate_component_scores(
    change_stack: np.ndarray,
    anomaly_stack: np.ndarray,
    evidence_stack: np.ndarray,
    valid_mask: np.ndarray,
    persistence_stack: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """
    Compute the 5 normalized [0.0, 1.0] components of priority ranking.

    Args:
        change_stack: (12, H, W) change rasters from Step 5.
            Band 1 (idx 0): NDVI delta
            Band 2 (idx 1): NDVI abs change
            Band 3 (idx 2): NDWI delta
            Band 4 (idx 3): NDWI abs change
            Band 5 (idx 4): NDBI delta
            Band 6 (idx 5): NDBI abs change
        anomaly_stack: (10, H, W) anomaly rasters from Step 6.
            Band 4 (idx 3): NDVI spatial anomaly
            Band 5 (idx 4): NDWI spatial anomaly
            Band 6 (idx 5): NDBI spatial anomaly
            Band 10 (idx 9): overall combined anomaly
        evidence_stack: (7, H, W) evidence flags from Step 6.
            Band 1 (idx 0): vegetation change present
            Band 2 (idx 1): water change present
            Band 3 (idx 2): builtup signal present
            Band 4 (idx 3): vegetation + builtup coherence
            Band 5 (idx 4): persistent change present
            Band 6 (idx 5): reversal present
        valid_mask: (H, W) boolean mask of valid pixels.
        persistence_stack: Optional (9, H, W) multi-temporal persistence stack.

    Returns:
        Dict mapping component name to (H, W) float32 array in [0.0, 1.0] (or NaN).
    """
    H, W = valid_mask.shape

    # 1. Anomaly severity component: Band 10 of anomaly stack
    s_anomaly = np.full((H, W), np.nan, dtype=np.float32)
    raw_anom = anomaly_stack[9]
    valid_anom = valid_mask & np.isfinite(raw_anom)
    s_anomaly[valid_anom] = np.clip(raw_anom[valid_anom], 0.0, 1.0)

    # 2. Evidence strength component:
    # Coherence (0.50) + Domain Flags (0.30) + Anomaly reinforcement (0.20) - Reversal dampening (0.25)
    s_evidence = np.full((H, W), np.nan, dtype=np.float32)
    coherence = (evidence_stack[3] == 1).astype(np.float32)
    domain_flags = (
        (evidence_stack[0] == 1).astype(np.float32)
        + (evidence_stack[1] == 1).astype(np.float32)
        + (evidence_stack[2] == 1).astype(np.float32)
    ) / 3.0
    anom_reinforce = np.where(valid_anom, s_anomaly, 0.0)
    reversal = (evidence_stack[5] == 1).astype(np.float32)

    raw_evidence = (
        0.50 * coherence
        + 0.30 * domain_flags
        + 0.20 * anom_reinforce
        - 0.25 * reversal
    )
    s_evidence[valid_mask] = np.clip(raw_evidence[valid_mask], 0.0, 1.0)

    # 3. Persistence component:
    s_persistence = np.full((H, W), np.nan, dtype=np.float32)
    if persistence_stack is not None:
        # Multi-temporal persistence: vegetation decrease, water decrease, or builtup increase
        p_flag = (
            (persistence_stack[0] == 1)
            | (persistence_stack[2] == 1)
            | (persistence_stack[4] == 1)
        ).astype(np.float32)
    else:
        p_flag = (evidence_stack[4] == 1).astype(np.float32)
    s_persistence[valid_mask] = p_flag[valid_mask]

    # 4. Magnitude component:
    # Max absolute delta across NDVI, NDWI, NDBI scaled by 0.50 saturation limit
    s_magnitude = np.full((H, W), np.nan, dtype=np.float32)
    abs_ndvi = change_stack[1]
    abs_ndwi = change_stack[3]
    abs_ndbi = change_stack[5]

    max_delta = np.maximum(
        np.where(np.isfinite(abs_ndvi), abs_ndvi, 0.0),
        np.maximum(
            np.where(np.isfinite(abs_ndwi), abs_ndwi, 0.0),
            np.where(np.isfinite(abs_ndbi), abs_ndbi, 0.0),
        ),
    )
    norm_mag = np.clip(max_delta / 0.50, 0.0, 1.0)
    s_magnitude[valid_mask] = norm_mag[valid_mask]

    # 5. Spatial context component:
    # Maximum spatial anomaly across NDVI, NDWI, NDBI (Bands 4, 5, 6)
    s_spatial = np.full((H, W), np.nan, dtype=np.float32)
    spat_ndvi = np.where(np.isfinite(anomaly_stack[3]), anomaly_stack[3], 0.0)
    spat_ndwi = np.where(np.isfinite(anomaly_stack[4]), anomaly_stack[4], 0.0)
    spat_ndbi = np.where(np.isfinite(anomaly_stack[5]), anomaly_stack[5], 0.0)

    max_spatial = np.maximum(spat_ndvi, np.maximum(spat_ndwi, spat_ndbi))
    s_spatial[valid_mask] = np.clip(max_spatial[valid_mask], 0.0, 1.0)

    return {
        "anomaly": s_anomaly,
        "evidence": s_evidence,
        "persistence": s_persistence,
        "magnitude": s_magnitude,
        "spatial_context": s_spatial,
    }


def calculate_priority_score(
    components: Dict[str, np.ndarray],
    weights: Optional[PriorityWeightsConfig] = None,
    valid_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Calculate weighted priority score bounded in [0.0, 1.0].

    Formula:
        priority_score = w_anom * S_anom + w_evid * S_evid + w_persist * S_persist
                         + w_mag * S_mag + w_spat * S_spat

    Args:
        components: Dict of 5 component arrays.
        weights: PriorityWeightsConfig with component weights summing to 1.0.
        valid_mask: Boolean mask of valid pixels.

    Returns:
        (H, W) float32 array with scores in [0.0, 1.0] and np.nan for invalid pixels.
    """
    if weights is None:
        weights = PriorityWeightsConfig()

    w_anom = float(weights.anomaly)
    w_evid = float(weights.evidence)
    w_persist = float(weights.persistence)
    w_mag = float(weights.magnitude)
    w_spat = float(weights.spatial_context)

    # Normalize weights if not exactly summing to 1.0
    w_total = w_anom + w_evid + w_persist + w_mag + w_spat
    if not np.isclose(w_total, 1.0, atol=1e-5):
        logger.warning(f"Priority weights sum to {w_total:.4f}, normalizing to 1.0")
        w_anom /= w_total
        w_evid /= w_total
        w_persist /= w_total
        w_mag /= w_total
        w_spat /= w_total

    s_anom = components["anomaly"]
    s_evid = components["evidence"]
    s_persist = components["persistence"]
    s_mag = components["magnitude"]
    s_spat = components["spatial_context"]

    # Initialize output array with NaNs
    H, W = s_anom.shape
    priority_score = np.full((H, W), np.nan, dtype=np.float32)

    # Determine valid evaluation mask
    eval_mask = (
        np.isfinite(s_anom)
        & np.isfinite(s_evid)
        & np.isfinite(s_persist)
        & np.isfinite(s_mag)
        & np.isfinite(s_spat)
    )
    if valid_mask is not None:
        eval_mask = eval_mask & valid_mask

    weighted_sum = (
        w_anom * s_anom[eval_mask]
        + w_evid * s_evid[eval_mask]
        + w_persist * s_persist[eval_mask]
        + w_mag * s_mag[eval_mask]
        + w_spat * s_spat[eval_mask]
    )

    priority_score[eval_mask] = np.clip(weighted_sum, 0.0, 1.0)
    return priority_score


def classify_priority_level(
    priority_score: np.ndarray,
    thresholds: Optional[PriorityThresholdsConfig] = None,
    valid_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Classify priority scores into discrete levels:
        0: INVALID
        1: LOW (< medium threshold)
        2: MEDIUM (>= medium threshold and < high threshold)
        3: HIGH (>= high threshold)

    Args:
        priority_score: (H, W) float32 array in [0.0, 1.0] or NaN.
        thresholds: PriorityThresholdsConfig (default high=0.70, medium=0.45).
        valid_mask: Boolean mask of valid pixels.

    Returns:
        (H, W) uint8 array of level codes (0, 1, 2, 3).
    """
    if thresholds is None:
        thresholds = PriorityThresholdsConfig()

    high_thresh = float(thresholds.high)
    med_thresh = float(thresholds.medium)

    H, W = priority_score.shape
    priority_level = np.zeros((H, W), dtype=np.uint8)

    valid = np.isfinite(priority_score)
    if valid_mask is not None:
        valid = valid & valid_mask

    scores = priority_score[valid]

    # LOW (code 1)
    low_idx = scores < med_thresh
    # MEDIUM (code 2)
    med_idx = (scores >= med_thresh) & (scores < high_thresh)
    # HIGH (code 3)
    high_idx = scores >= high_thresh

    temp = np.zeros(scores.shape, dtype=np.uint8)
    temp[low_idx] = 1
    temp[med_idx] = 2
    temp[high_idx] = 3

    priority_level[valid] = temp
    return priority_level


def generate_reason_codes(
    ndvi_delta: float,
    ndwi_delta: float,
    ndbi_delta: float,
    max_delta: float,
    anomaly_score: float,
    spatial_score: float,
    veg_builtup_coherence: bool,
    persistent: bool,
    reversal: bool,
) -> List[str]:
    """
    Generate machine-readable satellite evidence reason codes for a location.

    Reason codes strictly describe satellite-derived observations:
    - HIGH_SCENE_ANOMALY: Combined anomaly >= 0.70
    - SPATIAL_ANOMALY: Spatial neighborhood anomaly >= 0.60
    - VEG_BUILTUP_COHERENCE: Coherent vegetation loss + built-up response
    - VEGETATION_LOSS: NDVI decrease <= -0.15
    - BUILTUP_SENSITIVE_CHANGE: NDBI increase >= 0.15
    - WATER_CHANGE: NDWI absolute change >= 0.15
    - PERSISTENT_CHANGE: Multi-temporal persistent change verified
    - STRONG_CHANGE_MAGNITUDE: Max absolute change >= 0.25
    - CYCLICAL_REVERSAL_DAMPENED: Directional reversal observed across epochs

    Returns:
        List of uppercase reason code strings.
    """
    codes: List[str] = []

    if anomaly_score >= 0.70:
        codes.append("HIGH_SCENE_ANOMALY")
    if spatial_score >= 0.60:
        codes.append("SPATIAL_ANOMALY")
    if veg_builtup_coherence:
        codes.append("VEG_BUILTUP_COHERENCE")
    if ndvi_delta <= -0.15:
        codes.append("VEGETATION_LOSS")
    if ndbi_delta >= 0.15:
        codes.append("BUILTUP_SENSITIVE_CHANGE")
    if abs(ndwi_delta) >= 0.15:
        codes.append("WATER_CHANGE")
    if persistent:
        codes.append("PERSISTENT_CHANGE")
    if max_delta >= 0.25:
        codes.append("STRONG_CHANGE_MAGNITUDE")
    if reversal:
        codes.append("CYCLICAL_REVERSAL_DAMPENED")

    return codes


def build_why_flagged_record(
    grid_id: str,
    priority_score: float,
    priority_level: str,
    reason_codes: List[str],
    signals: Dict[str, float | bool],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Construct a structured 'Why Flagged' decision-support record for a hotspot.

    Args:
        grid_id: Identifier (e.g. 'HYD_0421').
        priority_score: Normalized priority score [0.0, 1.0].
        priority_level: Priority level string ('HIGH', 'MEDIUM', 'LOW').
        reason_codes: List of machine-readable reason codes.
        signals: Dictionary of underlying signal values.
        latitude: WGS84 centroid latitude.
        longitude: WGS84 centroid longitude.

    Returns:
        Structured dictionary matching UrbanPulse API & investigation schema.
    """
    recommendation = PRIORITY_RECOMMENDATIONS.get(
        priority_level, "DATA_UNAVAILABLE"
    )

    record: Dict[str, Any] = {
        "grid_id": grid_id,
        "priority_score": round(float(priority_score), 4),
        "priority_level": priority_level,
        "reasons": reason_codes,
        "signals": {
            k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v)
            for k, v in signals.items()
        },
        "recommendation": recommendation,
    }

    if latitude is not None and longitude is not None:
        record["latitude"] = round(float(latitude), 6)
        record["longitude"] = round(float(longitude), 6)

    return record


def write_priority_rasters(
    priority_score: np.ndarray,
    priority_level: np.ndarray,
    valid_mask: np.ndarray,
    profile: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    """
    Export single-band priority score and discrete priority level GeoTIFFs.

    Args:
        priority_score: (H, W) float32 score array.
        priority_level: (H, W) uint8 level array (0=Invalid, 1=Low, 2=Med, 3=High).
        valid_mask: (H, W) boolean mask array.
        profile: Rasterio profile dictionary.
        output_dir: Output directory path.

    Returns:
        Dict mapping raster names to their written Path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    score_path = output_dir / "priority_score.tif"
    level_path = output_dir / "priority_level.tif"
    mask_path = output_dir / "valid_mask.tif"

    # 1. Priority Score (Float32, NaN nodata)
    score_profile = profile.copy()
    score_profile.update(
        count=1,
        dtype=rasterio.float32,
        nodata=np.nan,
        compress="lzw",
    )
    with rasterio.open(score_path, "w", **score_profile) as dst:
        dst.write(priority_score.astype(np.float32), 1)
        dst.set_band_description(1, "priority_score_normalized_0_1")

    # 2. Priority Level (UInt8, 0 nodata)
    level_profile = profile.copy()
    level_profile.update(
        count=1,
        dtype=rasterio.uint8,
        nodata=0,
        compress="lzw",
    )
    with rasterio.open(level_path, "w", **level_profile) as dst:
        dst.write(priority_level.astype(np.uint8), 1)
        dst.set_band_description(1, "priority_level_0_invalid_1_low_2_med_3_high")

    # 3. Valid Mask (UInt8)
    mask_profile = profile.copy()
    mask_profile.update(
        count=1,
        dtype=rasterio.uint8,
        nodata=0,
        compress="lzw",
    )
    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(valid_mask.astype(np.uint8), 1)
        dst.set_band_description(1, "valid_pixel_mask")

    logger.info(f"Saved priority rasters to {output_dir}")
    return {
        "priority_score": score_path,
        "priority_level": level_path,
        "valid_mask": mask_path,
    }
