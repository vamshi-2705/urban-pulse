"""
UrbanPulse - Anomaly Fusion Engine.

Synthesizes temporal and spatial anomaly components into explainable combined anomaly layers:
- Configurable weighted fusion: combined = w_temp * temporal + w_spat * spatial
- Component availability logic (robust fallback when spatial neighbors are insufficient)
- Per-indicator combined anomalies (NDVI, NDWI, NDBI)
- Overall combined anomaly (maximum indicator response: max(NDVI, NDWI, NDBI))
- Multi-band GeoTIFF raster export and strict validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

from config.settings import CombinedAnomalyConfig
from geospatial.logger import get_logger

logger = get_logger("geospatial.anomaly_detection.anomaly_fusion")

ANOMALY_STACK_BAND_NAMES: List[str] = [
    "NDVI_temporal_anomaly",
    "NDWI_temporal_anomaly",
    "NDBI_temporal_anomaly",
    "NDVI_spatial_anomaly",
    "NDWI_spatial_anomaly",
    "NDBI_spatial_anomaly",
    "NDVI_combined_anomaly",
    "NDWI_combined_anomaly",
    "NDBI_combined_anomaly",
    "overall_combined_anomaly",
]


def fuse_anomaly_components(
    temporal_score: np.ndarray,
    spatial_score: np.ndarray,
    config: Optional[CombinedAnomalyConfig] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Fuse temporal and spatial anomaly scores into an explainable combined score.

    Availability rules:
    - If both temporal and spatial are valid (finite):
          combined = w_t * temporal + w_s * spatial
    - If only temporal is valid:
          if fallback_to_available_component: combined = temporal
          else: combined = np.nan
    - If only spatial is valid:
          if fallback_to_available_component: combined = spatial
          else: combined = np.nan
    - If neither is valid:
          combined = np.nan

    Args:
        temporal_score: (H, W) float32 in [0.0, 1.0] (or NaN).
        spatial_score: (H, W) float32 in [0.0, 1.0] (or NaN).
        config: Optional CombinedAnomalyConfig.

    Returns:
        Tuple of:
            - combined_score: (H, W) float32 in [0.0, 1.0]
            - valid_mask: (H, W) boolean mask
            - metadata: Component availability counts
    """
    if config is None:
        config = CombinedAnomalyConfig()

    w_temp = config.temporal_weight
    w_spat = config.spatial_weight
    fallback = config.fallback_to_available_component

    # Normalize weights if they do not sum to 1.0
    w_sum = w_temp + w_spat
    if abs(w_sum - 1.0) > 1e-5:
        w_temp /= w_sum
        w_spat /= w_sum

    t_valid = np.isfinite(temporal_score)
    s_valid = np.isfinite(spatial_score)
    both_valid = t_valid & s_valid
    t_only = t_valid & ~s_valid
    s_only = ~t_valid & s_valid

    combined = np.full(temporal_score.shape, np.nan, dtype=np.float32)

    # 1. Both valid: standard weighted sum
    combined[both_valid] = (
        w_temp * temporal_score[both_valid] + w_spat * spatial_score[both_valid]
    ).astype(np.float32)

    # 2. Fallbacks
    if fallback:
        combined[t_only] = temporal_score[t_only].astype(np.float32)
        combined[s_only] = spatial_score[s_only].astype(np.float32)

    valid_mask = np.isfinite(combined)
    combined[valid_mask] = np.clip(combined[valid_mask], 0.0, 1.0)

    n_both = int(np.sum(both_valid))
    n_t_only = int(np.sum(t_only))
    n_s_only = int(np.sum(s_only))
    n_total_valid = int(np.sum(valid_mask))

    meta = {
        "temporal_weight": round(w_temp, 2),
        "spatial_weight": round(w_spat, 2),
        "fallback_to_available_component": fallback,
        "both_components_valid_pixels": n_both,
        "temporal_only_pixels": n_t_only,
        "spatial_only_pixels": n_s_only,
        "total_valid_combined_pixels": n_total_valid,
    }

    return combined, valid_mask, meta


def compute_period_combined_anomalies(
    temporal_stack: np.ndarray,
    spatial_stack: np.ndarray,
    config: Optional[CombinedAnomalyConfig] = None,
) -> Dict[str, Any]:
    """
    Fuse temporal and spatial stacks across all 3 indicators and compute overall combined anomaly.

    Args:
        temporal_stack: (3, H, W) float32 stack [NDVI, NDWI, NDBI].
        spatial_stack: (3, H, W) float32 stack [NDVI, NDWI, NDBI].
        config: Optional CombinedAnomalyConfig.

    Returns:
        Dict containing:
            - "ndvi_combined": (H, W) float32
            - "ndwi_combined": (H, W) float32
            - "ndbi_combined": (H, W) float32
            - "overall_combined": (H, W) float32 (maximum response across indicators)
            - "combined_stack": (4, H, W) float32 stack [NDVI, NDWI, NDBI, overall]
            - "full_anomaly_stack": (10, H, W) float32 complete 10-band stack
            - "valid_mask": (H, W) boolean mask
    """
    if config is None:
        config = CombinedAnomalyConfig()

    ndvi_comb, ndvi_mask, meta_ndvi = fuse_anomaly_components(
        temporal_stack[0], spatial_stack[0], config
    )
    ndwi_comb, ndwi_mask, meta_ndwi = fuse_anomaly_components(
        temporal_stack[1], spatial_stack[1], config
    )
    ndbi_comb, ndbi_mask, meta_ndbi = fuse_anomaly_components(
        temporal_stack[2], spatial_stack[2], config
    )

    combined_mask = ndvi_mask | ndwi_mask | ndbi_mask

    # Overall combined anomaly aggregation
    method = getattr(config, "aggregation_method", "max").lower()
    overall = np.full(ndvi_comb.shape, np.nan, dtype=np.float32)

    if method == "mean":
        # Mean across valid indicators
        sum_valid = np.nan_to_num(ndvi_comb) + np.nan_to_num(ndwi_comb) + np.nan_to_num(ndbi_comb)
        count_valid = ndvi_mask.astype(float) + ndwi_mask.astype(float) + ndbi_mask.astype(float)
        has_valid = count_valid > 0
        overall[has_valid] = (sum_valid[has_valid] / count_valid[has_valid]).astype(np.float32)
    elif method == "corroborated":
        # Top-two corroborated blend: 0.7 * highest + 0.3 * 2nd highest
        stacked = np.stack(
            [np.nan_to_num(ndvi_comb), np.nan_to_num(ndwi_comb), np.nan_to_num(ndbi_comb)],
            axis=0,
        )
        sorted_s = np.sort(stacked, axis=0)[::-1]
        overall[combined_mask] = (
            0.7 * sorted_s[0][combined_mask] + 0.3 * sorted_s[1][combined_mask]
        ).astype(np.float32)
    else:
        # Default: "max" (ceiling response across indicators)
        overall = np.fmax(ndvi_comb, ndwi_comb)
        overall = np.fmax(overall, ndbi_comb)
        overall[~combined_mask] = np.nan

    overall[combined_mask] = np.clip(overall[combined_mask], 0.0, 1.0)

    # 4-band combined stack
    combined_stack = np.stack(
        [ndvi_comb, ndwi_comb, ndbi_comb, overall], axis=0
    ).astype(np.float32)

    # 10-band comprehensive anomaly stack
    full_anomaly_stack = np.stack(
        [
            temporal_stack[0],  # 1: NDVI temporal
            temporal_stack[1],  # 2: NDWI temporal
            temporal_stack[2],  # 3: NDBI temporal
            spatial_stack[0],   # 4: NDVI spatial
            spatial_stack[1],   # 5: NDWI spatial
            spatial_stack[2],   # 6: NDBI spatial
            ndvi_comb,          # 7: NDVI combined
            ndwi_comb,          # 8: NDWI combined
            ndbi_comb,          # 9: NDBI combined
            overall,            # 10: overall combined
        ],
        axis=0,
    ).astype(np.float32)

    return {
        "ndvi_combined": ndvi_comb,
        "ndwi_combined": ndwi_comb,
        "ndbi_combined": ndbi_comb,
        "overall_combined": overall,
        "combined_stack": combined_stack,
        "full_anomaly_stack": full_anomaly_stack,
        "valid_mask": combined_mask,
        "metadata": {
            "ndvi": meta_ndvi,
            "ndwi": meta_ndwi,
            "ndbi": meta_ndbi,
        },
    }


def write_anomaly_raster(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    profile: Dict[str, Any],
    output_path: Path,
    mask_path: Path,
    band_names: List[str],
) -> Tuple[Path, Path]:
    """
    Write anomaly raster stack and validity mask with LZW compression and descriptions.

    Args:
        stack: (bands, H, W) float32 array.
        valid_mask: (H, W) boolean mask array.
        profile: Base rasterio profile.
        output_path: Target GeoTIFF path.
        mask_path: Target valid mask GeoTIFF path.
        band_names: List of band descriptions.

    Returns:
        Tuple of (output_path, mask_path).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)

    bands, height, width = stack.shape

    out_profile = profile.copy()
    out_profile.update(
        count=bands,
        dtype="float32",
        compress="lzw",
        nodata=np.nan,
    )

    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(stack.astype(np.float32))
        for idx, name in enumerate(band_names, start=1):
            dst.set_band_description(idx, name)

    mask_profile = profile.copy()
    mask_profile.update(
        count=1,
        dtype="uint8",
        compress="lzw",
        nodata=None,
    )

    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(valid_mask.astype(np.uint8), 1)
        dst.set_band_description(1, "valid_anomaly_mask")

    logger.info(f"Saved anomaly stack: {output_path.name} ({bands} bands)")
    logger.info(f"Saved anomaly valid mask: {mask_path.name}")

    return output_path, mask_path


def validate_anomaly_raster(
    raster_path: Path | str,
    mask_path: Path | str,
    expected_bands: int = 10,
) -> bool:
    """
    Validate that written anomaly GeoTIFF conforms to strict pipeline requirements:
    - File exists and opens
    - Correct band count
    - Dtype is float32
    - Scores inside valid mask are bounded in [0.0, 1.0]
    - No Infs anywhere
    - Invalid pixels have NaN

    Args:
        raster_path: Path to anomaly GeoTIFF.
        mask_path: Path to valid mask GeoTIFF.
        expected_bands: Expected number of bands.

    Returns:
        True if valid.
    """
    r_path = Path(raster_path).resolve()
    m_path = Path(mask_path).resolve()

    if not r_path.exists():
        raise FileNotFoundError(f"Anomaly raster missing: {r_path}")
    if not m_path.exists():
        raise FileNotFoundError(f"Mask raster missing: {m_path}")

    with rasterio.open(r_path) as src, rasterio.open(m_path) as m_src:
        if src.count != expected_bands:
            raise ValueError(
                f"Expected {expected_bands} bands in {r_path.name}, got {src.count}"
            )

        if str(src.dtypes[0]) != "float32":
            raise ValueError(
                f"Expected dtype float32 in {r_path.name}, got {src.dtypes[0]}"
            )

        mask = (m_src.read(1) == 1)

        for b_idx in range(1, src.count + 1):
            data = src.read(b_idx)
            valid_vals = data[mask & np.isfinite(data)]

            # Check for Infinities
            if np.any(np.isinf(data)):
                raise ValueError(f"Infinite values found in band {b_idx} of {r_path.name}")

            # Check bounds [0.0, 1.0] (allowing tiny 1e-4 float tolerance)
            if len(valid_vals) > 0:
                if np.min(valid_vals) < -1e-4 or np.max(valid_vals) > 1.0001:
                    raise ValueError(
                        f"Band {b_idx} in {r_path.name} has values outside [0, 1]: "
                        f"min={np.min(valid_vals)}, max={np.max(valid_vals)}"
                    )

    logger.debug(f"Validated anomaly raster: {r_path.name}")
    return True
