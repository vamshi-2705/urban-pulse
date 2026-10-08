"""
UrbanPulse - Spatial / Neighborhood Anomaly Engine.

Detects localized spatial anomalies by answering:
"Is this observed change unusual compared with nearby locations?"

Methodology:
- Constructs a configurable rolling neighborhood (window_size_pixels, e.g. 21x21 = 210m x 210m at 10m resolution).
- Vectorized neighborhood statistics using scipy.ndimage for high performance on multi-million pixel rasters.
- Excludes invalid / masked pixels from contaminating local statistics using exact valid neighbor counting.
- Enforces minimum_valid_neighbors: pixels with insufficient valid neighbors receive NaN scores.
- Computes local robust center (local median) and local robust dispersion (local MAD).
- Handles zero / low local MAD via documented dispersion floor fallback.
- Computes local robust z-score: local_z = 0.6745 * (delta - local_median) / local_MAD.
- Transforms deviation into a bounded [0.0, 1.0] spatial anomaly strength score.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import numpy as np
import scipy.ndimage as ndi

from config.settings import SpatialAnomalyConfig
from geospatial.logger import get_logger

logger = get_logger("geospatial.anomaly_detection.spatial_anomaly")


def count_valid_neighbors(
    valid_mask: np.ndarray,
    window_size: int,
) -> np.ndarray:
    """
    Calculate the exact count of valid pixels within a local window for each pixel.

    Args:
        valid_mask: Boolean valid mask array (H, W).
        window_size: Size of square window in pixels (must be odd, e.g. 21).

    Returns:
        int32 array (H, W) with the number of valid neighbors within the window.
    """
    if window_size % 2 == 0:
        raise ValueError(f"Window size must be an odd integer, got {window_size}")

    valid_float = valid_mask.astype(np.float32)
    # uniform_filter computes local sum / (window_size * window_size)
    local_mean = ndi.uniform_filter(
        valid_float, size=window_size, mode="constant", cval=0.0
    )
    total_window_pixels = float(window_size * window_size)
    counts = np.round(local_mean * total_window_pixels).astype(np.int32)
    return counts


def compute_local_robust_statistics(
    data: np.ndarray,
    valid_mask: np.ndarray,
    window_size: int = 21,
    mad_scale: float = 0.6745,
    mad_floor: float = 0.001,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Compute local median and local robust dispersion across spatial neighborhoods.

    Uses nearest-neighbor valid pixel filling to prevent invalid/NaN values from
    corrupting the median filter, while evaluating output scores strictly on valid pixels.

    Args:
        data: Array of change deltas (float32).
        valid_mask: Boolean valid mask.
        window_size: Window dimension in pixels (odd).
        mad_scale: Consistency factor (default 0.6745).
        mad_floor: Lower floor for MAD to avoid division by zero in uniform regions.

    Returns:
        Tuple of:
            - local_median: (H, W) float32
            - local_mad: (H, W) float32
            - local_dispersion: (H, W) float32 (capped by floor)
            - zero_mad_pixel_count: int
    """
    if window_size % 2 == 0:
        raise ValueError(f"window_size must be an odd integer, got {window_size}")

    # Step 1: Fill invalid pixels with nearest valid pixel so NaN comparisons
    # do not corrupt median filtering
    if not np.all(valid_mask):
        # Distance transform to find coordinates of nearest valid pixel
        nearest_indices = ndi.distance_transform_edt(
            ~valid_mask, return_distances=False, return_indices=True
        )
        filled_data = data[nearest_indices[0], nearest_indices[1]].astype(np.float32)
    else:
        filled_data = data.astype(np.float32).copy()

    # Step 2: Compute local median
    local_median = ndi.median_filter(
        filled_data, size=window_size, mode="reflect"
    ).astype(np.float32)

    # Step 3: Compute local MAD = local_median(|filled_data - local_median|)
    abs_deviation = np.abs(filled_data - local_median).astype(np.float32)
    local_mad = ndi.median_filter(
        abs_deviation, size=window_size, mode="reflect"
    ).astype(np.float32)

    # Step 4: Robust dispersion with floor safeguard
    dispersion_floor = mad_floor / mad_scale
    raw_dispersion = local_mad / mad_scale

    low_mad_mask = valid_mask & (local_mad < mad_floor)
    zero_mad_count = int(np.sum(low_mad_mask))

    local_dispersion = np.maximum(raw_dispersion, dispersion_floor).astype(np.float32)

    return local_median, local_mad, local_dispersion, zero_mad_count


def compute_indicator_spatial_anomaly(
    delta: np.ndarray,
    valid_mask: np.ndarray,
    config: Optional[SpatialAnomalyConfig] = None,
    indicator_name: str = "delta",
) -> Dict[str, Any]:
    """
    Compute spatial neighborhood anomaly pipeline for a single indicator change delta.

    Workflow:
    1. Calculate valid neighbor counts per window.
    2. Flag pixels with count < minimum_valid_neighbors as spatially invalid.
    3. Compute local robust median and local MAD via 2D spatial filtering.
    4. Compute standardized local robust z-score:
           local_z = (delta - local_median) / local_dispersion
    5. Transform local_z magnitude into bounded [0.0, 1.0] spatial anomaly score:
           score = min(1.0, |local_z| / z_clip)

    Args:
        delta: Signed change delta array (float32).
        valid_mask: Boolean valid mask array.
        config: Optional SpatialAnomalyConfig.
        indicator_name: Name for reporting.

    Returns:
        Dict containing:
            - "anomaly_score": (H, W) float32 in [0.0, 1.0] (NaN outside valid)
            - "local_z": (H, W) float32 local robust z-scores (NaN outside valid)
            - "spatial_valid_mask": (H, W) bool
            - "metadata": Spatial summary dict
    """
    if config is None:
        config = SpatialAnomalyConfig()

    t_start = time.time()
    w_size = config.window_size_pixels
    min_neighbors = config.minimum_valid_neighbors
    z_clip = config.z_clip
    mad_floor = config.mad_floor

    # Step 1: Neighbor counts
    neighbor_counts = count_valid_neighbors(valid_mask, window_size=w_size)

    # Spatial validity requires original pixel valid AND sufficient neighbors
    spatial_valid = (
        valid_mask.astype(bool)
        & (neighbor_counts >= min_neighbors)
        & np.isfinite(delta)
    )

    # Step 2: Local robust statistics
    local_median, local_mad, local_dispersion, low_mad_count = (
        compute_local_robust_statistics(
            delta,
            valid_mask,
            window_size=w_size,
            mad_scale=0.6745,
            mad_floor=mad_floor,
        )
    )

    # Step 3: Compute standardized local deviation
    local_z = np.full(delta.shape, np.nan, dtype=np.float32)
    local_z[spatial_valid] = (
        (delta[spatial_valid] - local_median[spatial_valid])
        / local_dispersion[spatial_valid]
    )

    # Step 4: Bounded anomaly score [0.0, 1.0]
    score = np.full(delta.shape, np.nan, dtype=np.float32)
    abs_z = np.abs(local_z[spatial_valid])
    score[spatial_valid] = np.clip(abs_z / z_clip, 0.0, 1.0).astype(np.float32)

    elapsed = time.time() - t_start
    n_valid = int(np.sum(spatial_valid))
    n_total = int(delta.size)
    valid_scores = score[spatial_valid]

    logger.debug(
        f"Spatial anomaly for {indicator_name}: window={w_size}x{w_size}, "
        f"valid_pixels={n_valid:,} ({100.0 * n_valid / n_total:.2f}%), "
        f"low_mad_pixels={low_mad_count:,}, runtime={elapsed:.2f}s"
    )

    meta = {
        "indicator": indicator_name,
        "window_size_pixels": w_size,
        "minimum_valid_neighbors": min_neighbors,
        "z_clip": z_clip,
        "mad_floor": mad_floor,
        "valid_pixels": n_valid,
        "insufficient_neighbor_pixels": int(np.sum(valid_mask & ~spatial_valid)),
        "low_mad_fallback_pixels": low_mad_count,
        "runtime_seconds": round(elapsed, 2),
        "score_mean": round(float(np.mean(valid_scores)), 4) if n_valid > 0 else 0.0,
        "score_median": round(float(np.median(valid_scores)), 4) if n_valid > 0 else 0.0,
        "score_p95": round(float(np.percentile(valid_scores, 95)), 4) if n_valid > 0 else 0.0,
    }

    return {
        "anomaly_score": score,
        "local_z": local_z,
        "spatial_valid_mask": spatial_valid,
        "metadata": meta,
    }


def compute_period_spatial_anomalies(
    change_stack: np.ndarray,
    valid_mask: np.ndarray,
    config: Optional[SpatialAnomalyConfig] = None,
) -> Dict[str, Any]:
    """
    Compute spatial neighborhood anomalies for all 3 indicators (NDVI, NDWI, NDBI).

    Args:
        change_stack: (12, H, W) float32 pairwise change stack.
        valid_mask: (H, W) boolean valid mask.
        config: Optional SpatialAnomalyConfig.

    Returns:
        Dict containing:
            - "spatial_stack": (3, H, W) float32 stack [0: NDVI, 1: NDWI, 2: NDBI]
            - "ndvi": single-indicator result dict
            - "ndwi": single-indicator result dict
            - "ndbi": single-indicator result dict
            - "spatial_valid_mask": combined boolean validity mask
    """
    if config is None:
        config = SpatialAnomalyConfig()

    ndvi_res = compute_indicator_spatial_anomaly(
        change_stack[0], valid_mask, config, indicator_name="NDVI_spatial_anomaly"
    )
    ndwi_res = compute_indicator_spatial_anomaly(
        change_stack[2], valid_mask, config, indicator_name="NDWI_spatial_anomaly"
    )
    ndbi_res = compute_indicator_spatial_anomaly(
        change_stack[4], valid_mask, config, indicator_name="NDBI_spatial_anomaly"
    )

    spatial_stack = np.stack(
        [
            ndvi_res["anomaly_score"],
            ndwi_res["anomaly_score"],
            ndbi_res["anomaly_score"],
        ],
        axis=0,
    ).astype(np.float32)

    combined_spatial_mask = (
        ndvi_res["spatial_valid_mask"]
        & ndwi_res["spatial_valid_mask"]
        & ndbi_res["spatial_valid_mask"]
    )

    return {
        "spatial_stack": spatial_stack,
        "ndvi": ndvi_res,
        "ndwi": ndwi_res,
        "ndbi": ndbi_res,
        "spatial_valid_mask": combined_spatial_mask,
    }
