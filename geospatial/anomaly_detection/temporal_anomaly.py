"""
UrbanPulse - Scene-Level Change Anomaly Engine (Temporal Component).

SCIENTIFIC REFRAME & CLARIFICATION:
With only three observation epochs (2020, 2023, 2026), this component computes a
**scene-level change anomaly** across each multi-temporal comparison period.
It measures how statistically unusual a given pixel's observed shift (delta) is
relative to the empirical distribution of changes occurring across the entire scene
during that observation epoch.

IMPORTANT NOTE:
This is NOT a dense, per-location historical time series baseline (which would require
15-30+ dense temporal observations over multiple annual cycles). We do NOT fabricate
additional temporal observations. Instead, we use the available scene-wide change
distribution to establish the robust statistical baseline for each comparison interval.

Methodology:
- Robust central tendency (Median of scene change distribution)
- Robust dispersion (Median Absolute Deviation, MAD)
- Standardized Robust Z-score: robust_z = 0.6745 * (delta - median) / MAD
- Division-by-zero protection via documented dispersion floor fallback
- Deterministic bounded transformation to [0.0, 1.0] anomaly strength score.

NOTE: Terminology reflects anomaly strength, NOT priority or risk.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

from config.settings import TemporalAnomalyConfig
from geospatial.logger import get_logger

logger = get_logger("geospatial.anomaly_detection.temporal_anomaly")


def calculate_robust_center_dispersion(
    data: np.ndarray,
    valid_mask: np.ndarray,
    mad_scale: float = 0.6745,
    mad_floor: float = 0.001,
    min_samples: int = 100,
) -> Tuple[float, float, float, bool]:
    """
    Calculate robust center (median) and robust dispersion (MAD / 0.6745).

    Under standard normal distribution assumptions:
        sigma_robust = MAD / 0.6745 = 1.4826 * MAD
    where MAD = median(|x - median(x)|).

    If MAD < mad_floor:
        dispersion falls back to mad_floor / mad_scale to prevent division by zero.

    Args:
        data: Array of delta values (float32).
        valid_mask: Boolean array indicating valid pixels.
        mad_scale: Consistency factor (default 0.6745 for Gaussian equivalent).
        mad_floor: Lower bound for MAD to prevent division by zero or infinite z.
        min_samples: Minimum valid samples required to compute statistics.

    Returns:
        Tuple of (median, raw_mad, robust_dispersion, used_fallback).
    """
    valid_data = data[valid_mask & np.isfinite(data)]
    n_samples = len(valid_data)

    if n_samples < min_samples:
        logger.warning(
            f"Insufficient valid samples for temporal distribution: {n_samples} < {min_samples}"
        )
        return 0.0, 0.0, mad_floor / mad_scale, True

    med = float(np.median(valid_data))
    abs_deviations = np.abs(valid_data - med)
    mad = float(np.median(abs_deviations))

    used_fallback = False
    if mad < mad_floor:
        logger.info(
            f"MAD ({mad:.6f}) is below floor threshold ({mad_floor}); using dispersion floor fallback."
        )
        robust_dispersion = float(mad_floor / mad_scale)
        used_fallback = True
    else:
        # dispersion = MAD / 0.6745 so that (x - med) / dispersion = 0.6745 * (x - med) / MAD
        robust_dispersion = float(mad / mad_scale)

    return med, mad, robust_dispersion, used_fallback


def calculate_robust_z(
    data: np.ndarray,
    median: float,
    dispersion: float,
    valid_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Compute standardized robust z-score: (data - median) / dispersion.

    Args:
        data: Array of delta values (float32).
        median: Robust center.
        dispersion: Robust dispersion (MAD / mad_scale).
        valid_mask: Optional boolean valid mask.

    Returns:
        float32 array of robust z-scores. Outside valid mask, values are np.nan.
    """
    robust_z = np.full(data.shape, np.nan, dtype=np.float32)

    if valid_mask is not None:
        mask = valid_mask.astype(bool) & np.isfinite(data)
    else:
        mask = np.isfinite(data)

    if dispersion <= 0.0:
        raise ValueError(f"Dispersion must be strictly positive, got {dispersion}")

    robust_z[mask] = ((data[mask] - median) / dispersion).astype(np.float32)
    return robust_z


def z_to_anomaly_score(
    robust_z: np.ndarray,
    z_clip: float = 3.5,
    valid_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Convert absolute robust z-score magnitude into bounded [0.0, 1.0] anomaly score.

    Transformation:
        score = min(1.0, |robust_z| / z_clip)

    Properties:
        score = 0.0: Zero deviation from robust center.
        score = 1.0: Deviation reaches or exceeds z_clip standard robust deviations.
        Invalid pixels: np.nan.

    Args:
        robust_z: Standardized robust z-score array.
        z_clip: Upper saturation bound for z-score (e.g. 3.5).
        valid_mask: Optional boolean valid mask.

    Returns:
        float32 array of anomaly scores strictly in [0.0, 1.0], or np.nan outside valid.
    """
    if z_clip <= 0.0:
        raise ValueError(f"z_clip parameter must be strictly positive, got {z_clip}")

    score = np.full(robust_z.shape, np.nan, dtype=np.float32)

    if valid_mask is not None:
        mask = valid_mask.astype(bool) & np.isfinite(robust_z)
    else:
        mask = np.isfinite(robust_z)

    abs_z = np.abs(robust_z[mask])
    normalized = np.clip(abs_z / z_clip, 0.0, 1.0)
    score[mask] = normalized.astype(np.float32)

    return score


def compute_indicator_temporal_anomaly(
    delta: np.ndarray,
    valid_mask: np.ndarray,
    config: Optional[TemporalAnomalyConfig] = None,
    indicator_name: str = "delta",
) -> Dict[str, Any]:
    """
    Compute full temporal anomaly pipeline for a single spectral indicator delta.

    Args:
        delta: Signed change delta array (float32).
        valid_mask: Boolean valid mask.
        config: Optional TemporalAnomalyConfig.
        indicator_name: Name for logging and reporting.

    Returns:
        Dict containing:
            - "anomaly_score": (H, W) float32 in [0.0, 1.0] (NaN outside valid)
            - "robust_z": (H, W) float32 signed robust z-scores (NaN outside valid)
            - "sign": (H, W) int8 signed direction {-1, 0, +1}
            - "metadata": Distribution summary (median, mad, dispersion, fallback, etc.)
    """
    if config is None:
        config = TemporalAnomalyConfig()

    med, mad, dispersion, used_fallback = calculate_robust_center_dispersion(
        delta,
        valid_mask,
        mad_scale=config.mad_scale,
        mad_floor=config.mad_floor,
        min_samples=config.minimum_valid_samples,
    )

    robust_z = calculate_robust_z(delta, med, dispersion, valid_mask=valid_mask)
    score = z_to_anomaly_score(robust_z, z_clip=config.z_clip, valid_mask=valid_mask)

    # Signed direction: +1, -1, 0 (0 for invalid or stable)
    sign = np.zeros(delta.shape, dtype=np.int8)
    finite_mask = valid_mask & np.isfinite(delta)
    sign[finite_mask & (delta > 0)] = 1
    sign[finite_mask & (delta < 0)] = -1

    valid_scores = score[valid_mask & np.isfinite(score)]
    n_valid = int(len(valid_scores))

    meta = {
        "indicator": indicator_name,
        "component_type": "scene_level_change_anomaly",
        "baseline_type": "scene_level_change_distribution",
        "median": round(med, 4),
        "mad": round(mad, 4),
        "dispersion": round(dispersion, 4),
        "used_dispersion_fallback": used_fallback,
        "mad_scale": config.mad_scale,
        "z_clip": config.z_clip,
        "valid_pixels": n_valid,
        "score_mean": round(float(np.mean(valid_scores)), 4) if n_valid > 0 else 0.0,
        "score_median": round(float(np.median(valid_scores)), 4) if n_valid > 0 else 0.0,
        "score_p95": round(float(np.percentile(valid_scores, 95)), 4) if n_valid > 0 else 0.0,
    }

    return {
        "anomaly_score": score,
        "robust_z": robust_z,
        "sign": sign,
        "metadata": meta,
    }


def compute_period_temporal_anomalies(
    change_stack: np.ndarray,
    valid_mask: np.ndarray,
    config: Optional[TemporalAnomalyConfig] = None,
) -> Dict[str, Any]:
    """
    Compute temporal / scene-level change anomalies for all 3 indicators (NDVI, NDWI, NDBI).

    Change stack band mapping (1-indexed from Step 5):
        Band 1 (idx 0): NDVI_delta
        Band 3 (idx 2): NDWI_delta
        Band 5 (idx 4): NDBI_delta

    Args:
        change_stack: (12, H, W) float32 pairwise change stack.
        valid_mask: (H, W) boolean valid mask.
        config: Optional TemporalAnomalyConfig.

    Returns:
        Dict containing:
            - "temporal_stack": (3, H, W) float32 stack [0: NDVI, 1: NDWI, 2: NDBI]
            - "ndvi": single-indicator result dict
            - "ndwi": single-indicator result dict
            - "ndbi": single-indicator result dict
    """
    if config is None:
        config = TemporalAnomalyConfig()

    ndvi_res = compute_indicator_temporal_anomaly(
        change_stack[0], valid_mask, config, indicator_name="NDVI_temporal_anomaly"
    )
    ndwi_res = compute_indicator_temporal_anomaly(
        change_stack[2], valid_mask, config, indicator_name="NDWI_temporal_anomaly"
    )
    ndbi_res = compute_indicator_temporal_anomaly(
        change_stack[4], valid_mask, config, indicator_name="NDBI_temporal_anomaly"
    )

    temporal_stack = np.stack(
        [
            ndvi_res["anomaly_score"],
            ndwi_res["anomaly_score"],
            ndbi_res["anomaly_score"],
        ],
        axis=0,
    ).astype(np.float32)

    return {
        "temporal_stack": temporal_stack,
        "ndvi": ndvi_res,
        "ndwi": ndwi_res,
        "ndbi": ndbi_res,
    }


# Scientifically accurate aliases
compute_scene_change_anomaly = compute_indicator_temporal_anomaly
compute_period_scene_change_anomalies = compute_period_temporal_anomalies
