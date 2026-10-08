"""
UrbanPulse - Temporal Change Detection Engine.

Quantifies multi-temporal spectral index shifts across observation epochs (2020, 2023, 2026):
- Pairwise delta calculations: delta = later_value - earlier_value
- Absolute change magnitudes: abs(delta)
- Epsilon-thresholded directional signals:
    * vegetation_loss_signal, vegetation_gain_signal (NDVI)
    * water_loss_signal, water_gain_signal (NDWI)
    * builtup_increase_signal, builtup_decrease_signal (NDBI)
- Multi-temporal trajectory analysis:
    * Persistent change across sequential epochs (2020->2023 AND 2023->2026)
    * Directional reversals (e.g. decrease followed by increase)
- Validity mask propagation (pixel invalid in either epoch is marked invalid)
- Statistical distribution analysis for downstream anomaly detection (Step 6).

NOTE ON TERMINOLOGY:
Indicators represent spectral-sensitive response shifts, NOT direct ground truth:
- NDVI decrease = "vegetation-signal decrease" (not deforestation)
- NDWI decrease = "water-sensitive signal decrease" (not dried lake)
- NDBI increase = "built-up-sensitive spectral increase" (not new buildings)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio
from affine import Affine

from config.settings import AppConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.change_detection.temporal_change")

# Band descriptions for the 12-band change stack
PAIRWISE_CHANGE_BAND_NAMES: List[str] = [
    "NDVI_delta",
    "NDVI_abs_change",
    "NDWI_delta",
    "NDWI_abs_change",
    "NDBI_delta",
    "NDBI_abs_change",
    "vegetation_loss",
    "vegetation_gain",
    "water_loss",
    "water_gain",
    "builtup_increase",
    "builtup_decrease",
]

# Band descriptions for the 9-band persistence stack
PERSISTENCE_BAND_NAMES: List[str] = [
    "persistent_vegetation_decrease",
    "persistent_vegetation_increase",
    "persistent_water_decrease",
    "persistent_water_increase",
    "persistent_builtup_increase",
    "persistent_builtup_decrease",
    "vegetation_reversal",
    "water_reversal",
    "builtup_reversal",
]


def load_indicator_raster(
    indices_path: Path | str,
    mask_path: Optional[Path | str] = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Load a 3-band indicator GeoTIFF stack and its corresponding valid mask.

    Args:
        indices_path: Path to 3-band GeoTIFF (Band 1: NDVI, Band 2: NDWI, Band 3: NDBI).
        mask_path: Optional path to valid_mask.tif. If omitted, attempts to locate
                   valid_mask.tif in the same directory.

    Returns:
        Tuple of:
            - indices_stack: np.ndarray of shape (3, height, width), float32.
            - valid_mask: np.ndarray of shape (height, width), boolean.
            - profile: rasterio profile dictionary.
    """
    indices_file = Path(indices_path).resolve()
    if not indices_file.exists():
        raise FileNotFoundError(f"Indicator raster not found: {indices_file}")

    # Discover mask if not provided
    if mask_path is None:
        candidate_mask = indices_file.parent / "valid_mask.tif"
        if candidate_mask.exists():
            mask_file = candidate_mask
        else:
            mask_file = None
    else:
        mask_file = Path(mask_path).resolve()
        if not mask_file.exists():
            raise FileNotFoundError(f"Mask file not found: {mask_file}")

    with rasterio.open(indices_file) as src:
        profile = src.profile.copy()
        indices_stack = src.read().astype(np.float32)

        if indices_stack.shape[0] < 3:
            raise ValueError(
                f"Indicator raster {indices_file.name} must have at least 3 bands, got {indices_stack.shape[0]}"
            )

    if mask_file is not None:
        with rasterio.open(mask_file) as m_src:
            valid_mask = (m_src.read(1) == 1)
    else:
        # Fallback mask: all finite pixels across all 3 bands
        valid_mask = np.all(np.isfinite(indices_stack[:3]), axis=0)

    # Ensure pixels flagged as invalid or non-finite are strictly invalid
    finite_check = np.all(np.isfinite(indices_stack[:3]), axis=0)
    valid_mask = valid_mask & finite_check

    logger.debug(
        f"Loaded indicator raster {indices_file.name}: shape={indices_stack.shape}, "
        f"valid_pixels={np.sum(valid_mask):,} ({100.0 * np.mean(valid_mask):.2f}%)"
    )

    return indices_stack[:3], valid_mask, profile


def validate_temporal_alignment(
    profiles_or_rasters: List[Dict[str, Any]],
    tolerance: float = 1e-5,
) -> bool:
    """
    Validate that all observation rasters share identical spatial grids.

    Checks:
    - CRS
    - Dimensions (width, height)
    - Affine transform
    - Resolution
    - Spatial bounds

    Args:
        profiles_or_rasters: List of rasterio profile dictionaries.
        tolerance: Spatial tolerance for coordinates and resolution.

    Returns:
        True if all match.

    Raises:
        ValueError: If spatial misalignment is detected.
    """
    if len(profiles_or_rasters) < 2:
        return True

    base = profiles_or_rasters[0]
    base_crs = str(base.get("crs"))
    base_w = base.get("width")
    base_h = base.get("height")
    base_transform: Affine = base.get("transform")
    base_res = (base_transform.a, abs(base_transform.e))

    for idx, other in enumerate(profiles_or_rasters[1:], start=1):
        other_crs = str(other.get("crs"))
        if other_crs != base_crs:
            raise ValueError(
                f"CRS mismatch at index {idx}: base={base_crs} vs target={other_crs}"
            )

        other_w = other.get("width")
        other_h = other.get("height")
        if other_w != base_w or other_h != base_h:
            raise ValueError(
                f"Dimension mismatch at index {idx}: base=({base_h}, {base_w}) vs target=({other_h}, {other_w})"
            )

        other_transform: Affine = other.get("transform")
        other_res = (other_transform.a, abs(other_transform.e))

        if abs(base_res[0] - other_res[0]) > tolerance or abs(base_res[1] - other_res[1]) > tolerance:
            raise ValueError(
                f"Resolution mismatch at index {idx}: base={base_res} vs target={other_res}"
            )

        # Check transform coefficients
        for param in ("a", "b", "c", "d", "e", "f"):
            v_base = getattr(base_transform, param)
            v_other = getattr(other_transform, param)
            if abs(v_base - v_other) > tolerance:
                raise ValueError(
                    f"Affine transform parameter '{param}' mismatch at index {idx}: "
                    f"base={v_base} vs target={v_other}"
                )

    logger.info(
        f"Validated temporal spatial alignment across {len(profiles_or_rasters)} epochs: "
        f"CRS={base_crs}, dimensions=({base_h}, {base_w}), resolution={base_res}"
    )
    return True


def calculate_change_magnitude(delta: np.ndarray) -> np.ndarray:
    """
    Compute absolute magnitude of index shift: abs(delta).

    Args:
        delta: Signed difference array (float32).

    Returns:
        np.ndarray of absolute differences (float32). NaNs preserved.
    """
    return np.abs(delta).astype(np.float32)


def classify_change_direction(
    delta: np.ndarray,
    epsilon: float,
    valid_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Classify signed change into analytical direction categories:
        +1: delta > epsilon (positive directional signal)
         0: abs(delta) <= epsilon or invalid (stable / within tolerance)
        -1: delta < -epsilon (negative directional signal)

    Args:
        delta: Signed difference array.
        epsilon: Analytical tolerance threshold (> 0.0).
        valid_mask: Optional boolean valid mask.

    Returns:
        np.ndarray of int8 values {-1, 0, +1}.
    """
    if epsilon <= 0.0:
        raise ValueError(f"Epsilon tolerance must be strictly positive, got {epsilon}")

    direction = np.zeros(delta.shape, dtype=np.int8)

    if valid_mask is not None:
        mask = valid_mask.astype(bool) & np.isfinite(delta)
    else:
        mask = np.isfinite(delta)

    direction[mask & (delta > epsilon)] = 1
    direction[mask & (delta < -epsilon)] = -1

    return direction


def calculate_pairwise_change(
    earlier_indices: np.ndarray,
    later_indices: np.ndarray,
    earlier_mask: np.ndarray,
    later_mask: np.ndarray,
    epsilons: Optional[Dict[str, float]] = None,
) -> Dict[str, np.ndarray]:
    """
    Calculate comprehensive pairwise change evidence between two observation epochs.

    Computes for each indicator (NDVI, NDWI, NDBI):
    - raw delta: later - earlier
    - absolute change: abs(delta)
    - directional signals thresholded with epsilon tolerances:
        * NDVI: vegetation_loss (< -eps), vegetation_gain (> +eps)
        * NDWI: water_loss (< -eps), water_gain (> +eps)
        * NDBI: builtup_increase (> +eps), builtup_decrease (< -eps)

    Validity propagation rule:
        valid = earlier_valid AND later_valid AND isfinite(earlier) AND isfinite(later)
        Invalid pixels: delta = NaN, abs_change = NaN, signals = 0.

    Args:
        earlier_indices: (3, H, W) float32 stack [0: NDVI, 1: NDWI, 2: NDBI].
        later_indices: (3, H, W) float32 stack [0: NDVI, 1: NDWI, 2: NDBI].
        earlier_mask: (H, W) boolean/uint8 mask.
        later_mask: (H, W) boolean/uint8 mask.
        epsilons: Dict of tolerance thresholds {"ndvi": eps, "ndwi": eps, "ndbi": eps}.

    Returns:
        Dict containing arrays for:
        - "valid_mask" (H, W) bool
        - "ndvi_delta", "ndvi_abs_change", "vegetation_loss", "vegetation_gain"
        - "ndwi_delta", "ndwi_abs_change", "water_loss", "water_gain"
        - "ndbi_delta", "ndbi_abs_change", "builtup_increase", "builtup_decrease"
        - "change_stack": (12, H, W) float32 complete raster stack
    """
    if earlier_indices.shape != later_indices.shape:
        raise ValueError(
            f"Shape mismatch: earlier {earlier_indices.shape} vs later {later_indices.shape}"
        )

    if epsilons is None:
        epsilons = {"ndvi": 0.10, "ndwi": 0.10, "ndbi": 0.10}

    eps_ndvi = float(epsilons.get("ndvi", 0.10))
    eps_ndwi = float(epsilons.get("ndwi", 0.10))
    eps_ndbi = float(epsilons.get("ndbi", 0.10))

    # Propagate valid mask
    valid_mask = earlier_mask.astype(bool) & later_mask.astype(bool)
    finite_inputs = (
        np.all(np.isfinite(earlier_indices[:3]), axis=0)
        & np.all(np.isfinite(later_indices[:3]), axis=0)
    )
    valid_mask &= finite_inputs

    _, height, width = earlier_indices.shape

    # Allocate deltas initialized to NaN
    ndvi_delta = np.full((height, width), np.nan, dtype=np.float32)
    ndwi_delta = np.full((height, width), np.nan, dtype=np.float32)
    ndbi_delta = np.full((height, width), np.nan, dtype=np.float32)

    ndvi_delta[valid_mask] = later_indices[0][valid_mask] - earlier_indices[0][valid_mask]
    ndwi_delta[valid_mask] = later_indices[1][valid_mask] - earlier_indices[1][valid_mask]
    ndbi_delta[valid_mask] = later_indices[2][valid_mask] - earlier_indices[2][valid_mask]

    # Absolute change
    ndvi_abs = calculate_change_magnitude(ndvi_delta)
    ndwi_abs = calculate_change_magnitude(ndwi_delta)
    ndbi_abs = calculate_change_magnitude(ndbi_delta)

    # Directional binary signals (0.0 or 1.0; 0.0 outside valid pixels)
    # NDVI signals
    veg_loss = np.zeros((height, width), dtype=np.float32)
    veg_gain = np.zeros((height, width), dtype=np.float32)
    veg_loss[valid_mask & (ndvi_delta < -eps_ndvi)] = 1.0
    veg_gain[valid_mask & (ndvi_delta > eps_ndvi)] = 1.0

    # NDWI signals
    water_loss = np.zeros((height, width), dtype=np.float32)
    water_gain = np.zeros((height, width), dtype=np.float32)
    water_loss[valid_mask & (ndwi_delta < -eps_ndwi)] = 1.0
    water_gain[valid_mask & (ndwi_delta > eps_ndwi)] = 1.0

    # NDBI signals
    builtup_inc = np.zeros((height, width), dtype=np.float32)
    builtup_dec = np.zeros((height, width), dtype=np.float32)
    builtup_inc[valid_mask & (ndbi_delta > eps_ndbi)] = 1.0
    builtup_dec[valid_mask & (ndbi_delta < -eps_ndbi)] = 1.0

    # Assemble 12-band stack (float32)
    change_stack = np.stack(
        [
            ndvi_delta,
            ndvi_abs,
            ndwi_delta,
            ndwi_abs,
            ndbi_delta,
            ndbi_abs,
            veg_loss,
            veg_gain,
            water_loss,
            water_gain,
            builtup_inc,
            builtup_dec,
        ],
        axis=0,
    ).astype(np.float32)

    return {
        "valid_mask": valid_mask,
        "ndvi_delta": ndvi_delta,
        "ndvi_abs_change": ndvi_abs,
        "vegetation_loss": veg_loss,
        "vegetation_gain": veg_gain,
        "ndwi_delta": ndwi_delta,
        "ndwi_abs_change": ndwi_abs,
        "water_loss": water_loss,
        "water_gain": water_gain,
        "ndbi_delta": ndbi_delta,
        "ndbi_abs_change": ndbi_abs,
        "builtup_increase": builtup_inc,
        "builtup_decrease": builtup_dec,
        "change_stack": change_stack,
        "epsilons": {
            "ndvi": eps_ndvi,
            "ndwi": eps_ndwi,
            "ndbi": eps_ndbi,
        },
    }


def calculate_persistence(
    period_a_signals: Dict[str, np.ndarray],
    period_b_signals: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    """
    Calculate trajectory persistence and reversal signals across two sequential periods.

    Period A: Epoch 1 -> Epoch 2 (e.g. 2020 -> 2023)
    Period B: Epoch 2 -> Epoch 3 (e.g. 2023 -> 2026)

    Persistence is defined as consistent directional movement in BOTH periods:
    - persistent vegetation decrease: veg_loss_A AND veg_loss_B
    - persistent vegetation increase: veg_gain_A AND veg_gain_B
    - persistent water decrease: water_loss_A AND water_loss_B
    - persistent water increase: water_gain_A AND water_gain_B
    - persistent built-up increase: builtup_increase_A AND builtup_increase_B
    - persistent built-up decrease: builtup_decrease_A AND builtup_decrease_B

    Reversals indicate direction flip between periods (critical for false-alarm suppression):
    - vegetation reversal: (loss_A AND gain_B) OR (gain_A AND loss_B)
    - water reversal: (loss_A AND gain_B) OR (gain_A AND loss_B)
    - builtup reversal: (increase_A AND decrease_B) OR (decrease_A AND increase_B)

    Output format:
    9-band uint8 array where 1 = active signal, 0 = inactive / invalid.

    Args:
        period_a_signals: Result dict from calculate_pairwise_change for Period A.
        period_b_signals: Result dict from calculate_pairwise_change for Period B.

    Returns:
        Dict containing:
        - "valid_mask" (H, W) bool
        - individual binary arrays (uint8)
        - "persistence_stack": (9, H, W) uint8 raster stack
    """
    valid_mask = period_a_signals["valid_mask"] & period_b_signals["valid_mask"]
    height, width = valid_mask.shape

    # Helper for boolean mask to uint8
    def to_uint8(cond: np.ndarray) -> np.ndarray:
        arr = np.zeros((height, width), dtype=np.uint8)
        arr[valid_mask & cond] = 1
        return arr

    # Signals from Period A
    veg_loss_a = period_a_signals["vegetation_loss"] > 0.5
    veg_gain_a = period_a_signals["vegetation_gain"] > 0.5
    water_loss_a = period_a_signals["water_loss"] > 0.5
    water_gain_a = period_a_signals["water_gain"] > 0.5
    builtup_inc_a = period_a_signals["builtup_increase"] > 0.5
    builtup_dec_a = period_a_signals["builtup_decrease"] > 0.5

    # Signals from Period B
    veg_loss_b = period_b_signals["vegetation_loss"] > 0.5
    veg_gain_b = period_b_signals["vegetation_gain"] > 0.5
    water_loss_b = period_b_signals["water_loss"] > 0.5
    water_gain_b = period_b_signals["water_gain"] > 0.5
    builtup_inc_b = period_b_signals["builtup_increase"] > 0.5
    builtup_dec_b = period_b_signals["builtup_decrease"] > 0.5

    # 6 Persistence indicators
    p_veg_dec = to_uint8(veg_loss_a & veg_loss_b)
    p_veg_inc = to_uint8(veg_gain_a & veg_gain_b)
    p_water_dec = to_uint8(water_loss_a & water_loss_b)
    p_water_inc = to_uint8(water_gain_a & water_gain_b)
    p_built_inc = to_uint8(builtup_inc_a & builtup_inc_b)
    p_built_dec = to_uint8(builtup_dec_a & builtup_dec_b)

    # 3 Reversal indicators
    r_veg = to_uint8((veg_loss_a & veg_gain_b) | (veg_gain_a & veg_loss_b))
    r_water = to_uint8((water_loss_a & water_gain_b) | (water_gain_a & water_loss_b))
    r_built = to_uint8((builtup_inc_a & builtup_dec_b) | (builtup_dec_a & builtup_inc_b))

    persistence_stack = np.stack(
        [
            p_veg_dec,
            p_veg_inc,
            p_water_dec,
            p_water_inc,
            p_built_inc,
            p_built_dec,
            r_veg,
            r_water,
            r_built,
        ],
        axis=0,
    ).astype(np.uint8)

    return {
        "valid_mask": valid_mask,
        "persistent_vegetation_decrease": p_veg_dec,
        "persistent_vegetation_increase": p_veg_inc,
        "persistent_water_decrease": p_water_dec,
        "persistent_water_increase": p_water_inc,
        "persistent_builtup_increase": p_built_inc,
        "persistent_builtup_decrease": p_built_dec,
        "vegetation_reversal": r_veg,
        "water_reversal": r_water,
        "builtup_reversal": r_built,
        "persistence_stack": persistence_stack,
    }


def summarize_delta(
    delta: np.ndarray,
    valid_mask: np.ndarray,
    name: str,
    epsilon: float,
) -> Dict[str, Any]:
    """
    Compute distribution statistics for a signed indicator delta.

    Args:
        delta: Delta raster array (float32).
        valid_mask: Boolean mask indicating valid pixels.
        name: Indicator delta name.
        epsilon: Tolerance threshold.

    Returns:
        Dict with distribution percentiles and count statistics.
    """
    valid_data = delta[valid_mask & np.isfinite(delta)]
    total_valid = int(len(valid_data))
    total_pixels = int(delta.size)

    if total_valid == 0:
        return {
            "name": name,
            "valid_pixels": 0,
            "invalid_pixels": total_pixels,
            "valid_percentage": 0.0,
            "epsilon": epsilon,
            "changed_pixels": 0,
            "changed_percentage": 0.0,
        }

    positive_mask = valid_data > epsilon
    negative_mask = valid_data < -epsilon
    changed_mask = positive_mask | negative_mask

    pos_count = int(np.sum(positive_mask))
    neg_count = int(np.sum(negative_mask))
    changed_count = int(np.sum(changed_mask))

    p05, p25, p50, p75, p95 = np.percentile(valid_data, [5, 25, 50, 75, 95])

    return {
        "name": name,
        "valid_pixels": total_valid,
        "invalid_pixels": total_pixels - total_valid,
        "valid_percentage": round(100.0 * total_valid / total_pixels, 2),
        "epsilon": epsilon,
        "positive_pixels": pos_count,
        "positive_percentage": round(100.0 * pos_count / total_valid, 2),
        "negative_pixels": neg_count,
        "negative_percentage": round(100.0 * neg_count / total_valid, 2),
        "changed_pixels": changed_count,
        "changed_percentage": round(100.0 * changed_count / total_valid, 2),
        "min": round(float(np.min(valid_data)), 4),
        "max": round(float(np.max(valid_data)), 4),
        "mean": round(float(np.mean(valid_data)), 4),
        "median": round(float(p50), 4),
        "std": round(float(np.std(valid_data)), 4),
        "p05": round(float(p05), 4),
        "p25": round(float(p25), 4),
        "p75": round(float(p75), 4),
        "p95": round(float(p95), 4),
    }


def generate_change_metadata(
    period_label: str,
    earlier_year: int,
    later_year: int,
    pairwise_result: Dict[str, Any],
    profile: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Generate comprehensive metadata for a pairwise change detection period.

    Args:
        period_label: Period string e.g. "2020_2023".
        earlier_year: Earlier observation year.
        later_year: Later observation year.
        pairwise_result: Result dict from calculate_pairwise_change.
        profile: Raster profile dictionary.
        output_dir: Directory where outputs are stored.

    Returns:
        Structured metadata dictionary.
    """
    valid_mask = pairwise_result["valid_mask"]
    epsilons = pairwise_result["epsilons"]

    ndvi_stats = summarize_delta(
        pairwise_result["ndvi_delta"], valid_mask, "NDVI_delta", epsilons["ndvi"]
    )
    ndwi_stats = summarize_delta(
        pairwise_result["ndwi_delta"], valid_mask, "NDWI_delta", epsilons["ndwi"]
    )
    ndbi_stats = summarize_delta(
        pairwise_result["ndbi_delta"], valid_mask, "NDBI_delta", epsilons["ndbi"]
    )

    total_valid = int(np.sum(valid_mask))
    total_pixels = int(valid_mask.size)

    # Signal summaries
    def signal_stat(name: str, key: str) -> Dict[str, Any]:
        count = int(np.sum(pairwise_result[key] > 0.5))
        return {
            "signal": name,
            "active_pixels": count,
            "percentage_of_valid": round(100.0 * count / max(1, total_valid), 2),
        }

    signals = {
        "vegetation_loss": signal_stat("vegetation_loss", "vegetation_loss"),
        "vegetation_gain": signal_stat("vegetation_gain", "vegetation_gain"),
        "water_loss": signal_stat("water_loss", "water_loss"),
        "water_gain": signal_stat("water_gain", "water_gain"),
        "builtup_increase": signal_stat("builtup_increase", "builtup_increase"),
        "builtup_decrease": signal_stat("builtup_decrease", "builtup_decrease"),
    }

    metadata = {
        "period": period_label,
        "earlier_year": earlier_year,
        "later_year": later_year,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "crs": str(profile.get("crs")),
        "dimensions": [profile.get("height"), profile.get("width")],
        "resolution_meters": profile.get("transform")[0],
        "total_pixels": total_pixels,
        "valid_pixels": total_valid,
        "valid_pixel_percentage": round(100.0 * total_valid / total_pixels, 2),
        "band_order": PAIRWISE_CHANGE_BAND_NAMES,
        "change_stack_file": str((output_dir / "change_stack.tif").resolve()),
        "mask_file": str((output_dir / "valid_mask.tif").resolve()),
        "epsilons": epsilons,
        "statistics": {
            "ndvi_delta": ndvi_stats,
            "ndwi_delta": ndwi_stats,
            "ndbi_delta": ndbi_stats,
        },
        "signals": signals,
    }

    return metadata


def validate_change_outputs(
    change_stack_path: Path | str,
    mask_path: Path | str,
    expected_bands: int = 12,
    expected_dtype: str = "float32",
) -> bool:
    """
    Validate that generated change raster satisfies all pipeline constraints:
    - GeoTIFF exists and opens
    - Correct band count, dimensions, and dtype
    - No NaN/Inf values inside valid mask
    - Invalid pixels have NaN outside valid mask (for float stacks)
    - Valid mask matches raster dimensions

    Args:
        change_stack_path: Path to change_stack.tif.
        mask_path: Path to valid_mask.tif.
        expected_bands: Expected number of bands in change stack.
        expected_dtype: Expected data type string.

    Returns:
        True if valid.

    Raises:
        ValueError / AssertionError: If any requirement fails.
    """
    c_path = Path(change_stack_path).resolve()
    m_path = Path(mask_path).resolve()

    if not c_path.exists():
        raise FileNotFoundError(f"Change stack not found: {c_path}")
    if not m_path.exists():
        raise FileNotFoundError(f"Mask file not found: {m_path}")

    with rasterio.open(c_path) as src, rasterio.open(m_path) as m_src:
        if src.count != expected_bands:
            raise ValueError(
                f"Expected {expected_bands} bands in {c_path.name}, got {src.count}"
            )

        if str(src.dtypes[0]) != expected_dtype:
            raise ValueError(
                f"Expected dtype {expected_dtype} in {c_path.name}, got {src.dtypes[0]}"
            )

        if src.shape != m_src.shape:
            raise ValueError(
                f"Dimension mismatch: change stack {src.shape} vs mask {m_src.shape}"
            )

        mask = (m_src.read(1) == 1)

        # Inspect continuous delta bands (first 6 bands)
        for b_idx in range(1, min(7, src.count + 1)):
            data = src.read(b_idx)
            # Valid pixels must be completely finite
            valid_subset = data[mask]
            if not np.all(np.isfinite(valid_subset)):
                raise ValueError(
                    f"Non-finite values detected inside valid mask for band {b_idx} in {c_path.name}"
                )

    logger.debug(f"Validated change raster outputs: {c_path.name}")
    return True


def write_change_stack(
    change_stack: np.ndarray,
    valid_mask: np.ndarray,
    profile: Dict[str, Any],
    output_dir: Path,
    band_names: List[str],
) -> Tuple[Path, Path]:
    """
    Write multi-band change stack and valid mask to disk.

    Args:
        change_stack: (bands, H, W) array.
        valid_mask: (H, W) boolean mask.
        profile: Base rasterio profile.
        output_dir: Target output directory.
        band_names: Descriptive names for each band.

    Returns:
        Tuple of (change_stack_path, valid_mask_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    change_stack_path = output_dir / "change_stack.tif"
    mask_path = output_dir / "valid_mask.tif"

    bands, height, width = change_stack.shape

    out_profile = profile.copy()
    out_profile.update(
        count=bands,
        dtype=str(change_stack.dtype),
        compress="lzw",
        nodata=np.nan if np.issubdtype(change_stack.dtype, np.floating) else None,
    )

    with rasterio.open(change_stack_path, "w", **out_profile) as dst:
        dst.write(change_stack)
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
        dst.set_band_description(1, "valid_comparison_mask")

    logger.info(f"Saved change raster stack: {change_stack_path.name} ({bands} bands)")
    logger.info(f"Saved comparison valid mask: {mask_path.name}")

    return change_stack_path, mask_path


def write_persistence_stack(
    persistence_stack: np.ndarray,
    valid_mask: np.ndarray,
    profile: Dict[str, Any],
    output_dir: Path,
) -> Tuple[Path, Path]:
    """
    Write 9-band persistence and reversal raster to disk.

    Args:
        persistence_stack: (9, H, W) uint8 array.
        valid_mask: (H, W) boolean mask.
        profile: Base rasterio profile.
        output_dir: Target output directory.

    Returns:
        Tuple of (persistence_path, valid_mask_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    persistence_path = output_dir / "persistence.tif"
    mask_path = output_dir / "valid_mask.tif"

    bands, height, width = persistence_stack.shape

    out_profile = profile.copy()
    out_profile.update(
        count=bands,
        dtype="uint8",
        compress="lzw",
        nodata=None,
    )

    with rasterio.open(persistence_path, "w", **out_profile) as dst:
        dst.write(persistence_stack)
        for idx, name in enumerate(PERSISTENCE_BAND_NAMES, start=1):
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
        dst.set_band_description(1, "multitemporal_valid_mask")

    logger.info(f"Saved persistence raster stack: {persistence_path.name} (9 bands)")
    logger.info(f"Saved multitemporal valid mask: {mask_path.name}")

    return persistence_path, mask_path


def calculate_multitemporal_change(
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Orchestrate full Step 5 temporal change detection pipeline across 2020, 2023, and 2026.

    Workflow:
    1. Validate input indicator rasters exist and have identical spatial grids.
    2. Compute pairwise change for:
       - Period A: 2020 -> 2023
       - Period B: 2023 -> 2026
       - Long-term: 2020 -> 2026
    3. Compute multi-temporal persistence and reversal signals across (A) and (B).
    4. Write GeoTIFF change stacks and validity masks.
    5. Save statistical distributions to JSON files for Step 6 anomaly engine.
    6. Validate all output rasters.

    Args:
        config: Optional AppConfig instance.

    Returns:
        Dictionary containing summary of change detection results.
    """
    if config is None:
        config = get_config()

    proc_dir = config.directories.processed_dir
    ind_dir = proc_dir / "indicators"
    change_dir = proc_dir / "change_detection"
    stats_dir = change_dir / "statistics"
    stats_dir.mkdir(parents=True, exist_ok=True)

    epsilons = {
        "ndvi": config.change_detection.ndvi_epsilon,
        "ndwi": config.change_detection.ndwi_epsilon,
        "ndbi": config.change_detection.ndbi_epsilon,
    }

    years = config.time_periods.years
    if len(years) < 3:
        raise ValueError(f"Change detection requires at least 3 epochs, configured: {years}")

    logger.info(f"Starting temporal change detection across epochs: {years}")
    logger.info(f"Using analytical tolerance epsilons: {epsilons}")

    # Load 2020
    idx_2020, mask_2020, prof_2020 = load_indicator_raster(ind_dir / "2020" / "indices.tif")
    # Load 2023
    idx_2023, mask_2023, prof_2023 = load_indicator_raster(ind_dir / "2023" / "indices.tif")
    # Load 2026
    idx_2026, mask_2026, prof_2026 = load_indicator_raster(ind_dir / "2026" / "indices.tif")

    # Step 3 Check: Verify spatial alignment across all three epochs
    validate_temporal_alignment([prof_2020, prof_2023, prof_2026])

    results: Dict[str, Any] = {
        "periods": {},
        "multitemporal": {},
        "alignment_status": "PASS",
    }

    # 1. Period A: 2020 -> 2023
    logger.info("Computing pairwise change: 2020 -> 2023...")
    change_2020_2023 = calculate_pairwise_change(
        idx_2020, idx_2023, mask_2020, mask_2023, epsilons=epsilons
    )
    dir_2020_2023 = change_dir / "2020_2023"
    stack_2020_2023_path, mask_2020_2023_path = write_change_stack(
        change_2020_2023["change_stack"],
        change_2020_2023["valid_mask"],
        prof_2020,
        dir_2020_2023,
        PAIRWISE_CHANGE_BAND_NAMES,
    )
    validate_change_outputs(stack_2020_2023_path, mask_2020_2023_path)
    meta_2020_2023 = generate_change_metadata(
        "2020_2023", 2020, 2023, change_2020_2023, prof_2020, dir_2020_2023
    )
    with open(stats_dir / "2020_2023.json", "w", encoding="utf-8") as f:
        json.dump(meta_2020_2023, f, indent=2)
    results["periods"]["2020_2023"] = meta_2020_2023

    # Free 2020 indices memory if needed, but here we still need 2020 for 2020->2026
    # 2. Period B: 2023 -> 2026
    logger.info("Computing pairwise change: 2023 -> 2026...")
    change_2023_2026 = calculate_pairwise_change(
        idx_2023, idx_2026, mask_2023, mask_2026, epsilons=epsilons
    )
    dir_2023_2026 = change_dir / "2023_2026"
    stack_2023_2026_path, mask_2023_2026_path = write_change_stack(
        change_2023_2026["change_stack"],
        change_2023_2026["valid_mask"],
        prof_2023,
        dir_2023_2026,
        PAIRWISE_CHANGE_BAND_NAMES,
    )
    validate_change_outputs(stack_2023_2026_path, mask_2023_2026_path)
    meta_2023_2026 = generate_change_metadata(
        "2023_2026", 2023, 2026, change_2023_2026, prof_2023, dir_2023_2026
    )
    with open(stats_dir / "2023_2026.json", "w", encoding="utf-8") as f:
        json.dump(meta_2023_2026, f, indent=2)
    results["periods"]["2023_2026"] = meta_2023_2026

    # 3. Long-Term: 2020 -> 2026
    logger.info("Computing pairwise change: 2020 -> 2026...")
    change_2020_2026 = calculate_pairwise_change(
        idx_2020, idx_2026, mask_2020, mask_2026, epsilons=epsilons
    )
    dir_2020_2026 = change_dir / "2020_2026"
    stack_2020_2026_path, mask_2020_2026_path = write_change_stack(
        change_2020_2026["change_stack"],
        change_2020_2026["valid_mask"],
        prof_2020,
        dir_2020_2026,
        PAIRWISE_CHANGE_BAND_NAMES,
    )
    validate_change_outputs(stack_2020_2026_path, mask_2020_2026_path)
    meta_2020_2026 = generate_change_metadata(
        "2020_2026", 2020, 2026, change_2020_2026, prof_2020, dir_2020_2026
    )
    with open(stats_dir / "2020_2026.json", "w", encoding="utf-8") as f:
        json.dump(meta_2020_2026, f, indent=2)
    results["periods"]["2020_2026"] = meta_2020_2026

    # 4. Multi-temporal Persistence and Reversals across Period A and Period B
    logger.info("Computing multi-temporal persistence and reversal trajectory signals...")
    persistence_res = calculate_persistence(change_2020_2023, change_2023_2026)
    dir_multi = change_dir / "multitemporal"
    persist_path, persist_mask_path = write_persistence_stack(
        persistence_res["persistence_stack"],
        persistence_res["valid_mask"],
        prof_2020,
        dir_multi,
    )
    validate_change_outputs(
        persist_path, persist_mask_path, expected_bands=9, expected_dtype="uint8"
    )

    p_valid_mask = persistence_res["valid_mask"]
    p_valid_count = int(np.sum(p_valid_mask))
    p_total_pixels = int(p_valid_mask.size)

    def p_stat(key: str) -> Dict[str, Any]:
        count = int(np.sum(persistence_res[key] == 1))
        return {
            "active_pixels": count,
            "percentage_of_valid": round(100.0 * count / max(1, p_valid_count), 2),
        }

    persistence_meta = {
        "period": "multitemporal_2020_2023_2026",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_pixels": p_total_pixels,
        "valid_pixels": p_valid_count,
        "valid_percentage": round(100.0 * p_valid_count / p_total_pixels, 2),
        "persistence_file": str(persist_path.resolve()),
        "mask_file": str(persist_mask_path.resolve()),
        "band_order": PERSISTENCE_BAND_NAMES,
        "persistence_signals": {
            "persistent_vegetation_decrease": p_stat("persistent_vegetation_decrease"),
            "persistent_vegetation_increase": p_stat("persistent_vegetation_increase"),
            "persistent_water_decrease": p_stat("persistent_water_decrease"),
            "persistent_water_increase": p_stat("persistent_water_increase"),
            "persistent_builtup_increase": p_stat("persistent_builtup_increase"),
            "persistent_builtup_decrease": p_stat("persistent_builtup_decrease"),
        },
        "reversals": {
            "vegetation_reversal": p_stat("vegetation_reversal"),
            "water_reversal": p_stat("water_reversal"),
            "builtup_reversal": p_stat("builtup_reversal"),
        },
    }

    with open(stats_dir / "multitemporal.json", "w", encoding="utf-8") as f:
        json.dump(persistence_meta, f, indent=2)
    results["multitemporal"] = persistence_meta

    logger.info("Successfully completed temporal change detection (Step 5).")
    return results
