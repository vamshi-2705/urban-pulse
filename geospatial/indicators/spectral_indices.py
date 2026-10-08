"""
UrbanPulse - Spectral Indicators & Indices Engine.

Calculates standardized, continuous environmental and urban spectral indices:
- NDVI (Vegetation-sensitive index): (NIR - Red) / (NIR + Red)
- NDWI (Water-sensitive index): (Green - NIR) / (Green + NIR)
- NDBI (Built-up-sensitive index): (SWIR1 - NIR) / (SWIR1 + NIR)

Outputs 3-band analysis-ready float32 GeoTIFF stacks with propagated validity masks
and robust statistical distributions.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio
from affine import Affine

from config.settings import AppConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.indicators.spectral_indices")

# Canonical band order in the 3-band indicator stack
INDICATOR_BAND_NAMES: List[str] = ["NDVI", "NDWI", "NDBI"]

# Input ARD stack band indices (1-indexed)
ARD_BAND_INDICES = {
    "blue": 1,
    "green": 2,
    "red": 3,
    "nir": 4,
    "swir1": 5,
    "swir2": 6,
}


def _safe_normalized_difference(
    band_a: np.ndarray,
    band_b: np.ndarray,
    base_mask: Optional[np.ndarray] = None,
    name: str = "index",
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Safely compute normalized difference: (band_a - band_b) / (band_a + band_b).

    Guarantees:
    - Zero / near-zero denominators are marked invalid.
    - Non-finite (NaN, Inf) inputs are marked invalid.
    - Pixels outside base_mask are marked invalid.
    - Valid pixels are within theoretical range [-1.0, 1.0] (allowing tiny eps tolerance).
    - Invalid pixels are set strictly to np.nan.

    Args:
        band_a: First spectral band array (float32).
        band_b: Second spectral band array (float32).
        base_mask: Optional initial boolean valid mask.
        name: Indicator name for logging.

    Returns:
        Tuple of (index_array_float32, valid_mask_boolean).
    """
    if band_a.shape != band_b.shape:
        raise ValueError(f"Shape mismatch: band_a {band_a.shape} vs band_b {band_b.shape}")

    # Initialize validity mask
    if base_mask is not None:
        valid_mask = base_mask.astype(bool).copy()
    else:
        valid_mask = np.ones(band_a.shape, dtype=bool)

    # Input finite check
    finite_inputs = np.isfinite(band_a) & np.isfinite(band_b)
    valid_mask &= finite_inputs

    numerator = band_a - band_b
    denominator = band_a + band_b

    # Safe denominator check (avoid division by zero or negative denominators from unphysical noise)
    nonzero_denom = np.abs(denominator) > 1e-7
    valid_mask &= nonzero_denom

    # Allocate result initialized to NaN
    index_arr = np.full(band_a.shape, np.nan, dtype=np.float32)

    # Compute only on valid pixels
    with np.errstate(divide="ignore", invalid="ignore"):
        index_arr[valid_mask] = numerator[valid_mask] / denominator[valid_mask]

    # Sanity check: valid pixels must not have produced NaN/Inf
    computed_finite = np.isfinite(index_arr) & valid_mask
    valid_mask = computed_finite

    # Theoretical bounds check with 1e-4 tolerance for floating point rounding
    out_of_bounds = (index_arr < -1.0001) | (index_arr > 1.0001)
    if np.any(out_of_bounds & valid_mask):
        num_oob = int(np.sum(out_of_bounds & valid_mask))
        logger.warning(
            f"Indicator {name}: {num_oob} valid pixel(s) exceeded [-1.0, 1.0] range; clamping."
        )
        # Clamp tiny numerical excursions to [-1.0, 1.0]
        index_arr[valid_mask] = np.clip(index_arr[valid_mask], -1.0, 1.0)

    # Ensure all invalid pixels remain NaN
    index_arr[~valid_mask] = np.nan

    return index_arr.astype(np.float32), valid_mask


def calculate_ndvi(
    nir: np.ndarray,
    red: np.ndarray,
    base_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Normalized Difference Vegetation Index (NDVI).

    Formula: (NIR - RED) / (NIR + RED)
    Sensors: Sentinel-2 B08 (NIR, 842nm) and B04 (Red, 665nm).
    Interpretation: Vegetation-sensitive indicator.

    Returns:
        Tuple of (ndvi_float32, valid_mask_bool).
    """
    return _safe_normalized_difference(nir, red, base_mask, name="NDVI")


def calculate_ndwi(
    green: np.ndarray,
    nir: np.ndarray,
    base_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate McFeeters Normalized Difference Water Index (NDWI).

    Formula: (GREEN - NIR) / (GREEN + NIR)
    Sensors: Sentinel-2 B03 (Green, 560nm) and B08 (NIR, 842nm).
    Interpretation: Water-sensitive indicator (positive values typically indicate water).

    Returns:
        Tuple of (ndwi_float32, valid_mask_bool).
    """
    return _safe_normalized_difference(green, nir, base_mask, name="NDWI")


def calculate_ndbi(
    swir1: np.ndarray,
    nir: np.ndarray,
    base_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate Normalized Difference Built-Up Index (NDBI).

    Formula: (SWIR1 - NIR) / (SWIR1 + NIR)
    Sensors: Sentinel-2 B11 (SWIR1, 1610nm) and B08 (NIR, 842nm).
    Interpretation: Built-up-sensitive indicator (higher in impervious/urban fabrics).

    Returns:
        Tuple of (ndbi_float32, valid_mask_bool).
    """
    return _safe_normalized_difference(swir1, nir, base_mask, name="NDBI")


def calculate_indices(
    stack_path: Path,
    mask_path: Path,
) -> Tuple[Dict[str, np.ndarray], np.ndarray, Dict[str, Any]]:
    """
    Load an ARD scene stack and compute all 3 spectral indicators with propagated validity.

    Args:
        stack_path: Path to scene_stack.tif (6-band float32).
        mask_path: Path to valid_mask.tif (uint8, 1=valid).

    Returns:
        Tuple of:
        - Dict of { "NDVI": array, "NDWI": array, "NDBI": array }
        - Combined boolean valid mask
        - Raster profile metadata dictionary
    """
    with rasterio.open(mask_path) as m_src:
        base_mask = (m_src.read(1) == 1)

    with rasterio.open(stack_path) as s_src:
        green = s_src.read(ARD_BAND_INDICES["green"])
        red = s_src.read(ARD_BAND_INDICES["red"])
        nir = s_src.read(ARD_BAND_INDICES["nir"])
        swir1 = s_src.read(ARD_BAND_INDICES["swir1"])

        meta = s_src.meta.copy()

    # Calculate each indicator independently
    ndvi, ndvi_mask = calculate_ndvi(nir, red, base_mask)
    ndwi, ndwi_mask = calculate_ndwi(green, nir, base_mask)
    ndbi, ndbi_mask = calculate_ndbi(swir1, nir, base_mask)

    # Combined validity: a pixel must be valid across all 3 indicators
    combined_mask = ndvi_mask & ndwi_mask & ndbi_mask

    # Re-apply combined mask to ensure complete parity across layers
    ndvi[~combined_mask] = np.nan
    ndwi[~combined_mask] = np.nan
    ndbi[~combined_mask] = np.nan

    indices_dict = {
        "NDVI": ndvi,
        "NDWI": ndwi,
        "NDBI": ndbi,
    }

    return indices_dict, combined_mask, meta


def summarize_indicator(
    data: np.ndarray,
    valid_mask: np.ndarray,
    indicator_name: str,
) -> Dict[str, Any]:
    """
    Compute rigorous statistical distribution metrics strictly on valid pixels.

    Args:
        data: Float32 indicator raster.
        valid_mask: Boolean valid pixel mask.
        indicator_name: Name of indicator (e.g. 'NDVI').

    Returns:
        Dictionary of distribution metrics.
    """
    valid_values = data[valid_mask]
    total_pixels = data.size
    valid_count = int(valid_values.size)
    invalid_count = total_pixels - valid_count
    valid_percentage = round((valid_count / total_pixels) * 100.0, 2)

    if valid_count == 0:
        logger.warning(f"Indicator {indicator_name} has 0 valid pixels!")
        return {
            "name": indicator_name,
            "valid_pixels": 0,
            "invalid_pixels": invalid_count,
            "valid_percentage": 0.0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
            "p05": None,
            "p25": None,
            "p75": None,
            "p95": None,
        }

    return {
        "name": indicator_name,
        "valid_pixels": valid_count,
        "invalid_pixels": invalid_count,
        "valid_percentage": valid_percentage,
        "min": round(float(np.min(valid_values)), 4),
        "max": round(float(np.max(valid_values)), 4),
        "mean": round(float(np.mean(valid_values)), 4),
        "median": round(float(np.median(valid_values)), 4),
        "std": round(float(np.std(valid_values)), 4),
        "p05": round(float(np.percentile(valid_values, 5)), 4),
        "p25": round(float(np.percentile(valid_values, 25)), 4),
        "p75": round(float(np.percentile(valid_values, 75)), 4),
        "p95": round(float(np.percentile(valid_values, 95)), 4),
    }


def validate_indicator_raster(
    indices_path: Path,
    mask_path: Path,
    expected_crs: str = "EPSG:32644",
    expected_dims: Optional[Tuple[int, int]] = None,
) -> Dict[str, Any]:
    """
    Verify indicator stack integrity, data types, physical ranges, and NaN constraints.

    Args:
        indices_path: Path to indices.tif.
        mask_path: Path to valid_mask.tif.
        expected_crs: Target CRS string.
        expected_dims: Optional (height, width) tuple.

    Returns:
        Validation results dictionary.
    """
    errors: List[str] = []

    if not indices_path.exists():
        return {"passed": False, "errors": [f"Indices file missing: {indices_path}"]}
    if not mask_path.exists():
        return {"passed": False, "errors": [f"Mask file missing: {mask_path}"]}

    with rasterio.open(indices_path) as ind_src, rasterio.open(mask_path) as m_src:
        if ind_src.count != 3:
            errors.append(f"Expected 3 bands in indices.tif, found {ind_src.count}")

        if ind_src.crs.to_string() != expected_crs:
            errors.append(f"CRS mismatch: {ind_src.crs} != {expected_crs}")

        if expected_dims and (ind_src.height, ind_src.width) != expected_dims:
            errors.append(f"Dimensions mismatch: {ind_src.height}x{ind_src.width} != {expected_dims}")

        if ind_src.transform != m_src.transform:
            errors.append("Affine transforms between indices and mask do not match")

        mask = (m_src.read(1) == 1)

        # Check each indicator band
        for b_idx, b_name in enumerate(INDICATOR_BAND_NAMES, start=1):
            data = ind_src.read(b_idx)
            if data.dtype != np.float32:
                errors.append(f"Band {b_name} dtype is {data.dtype}, expected float32")

            valid_data = data[mask]
            # Must not contain NaN inside valid mask
            if np.isnan(valid_data).any():
                errors.append(f"Band {b_name} contains NaN inside valid mask")
            # Must not contain Inf inside valid mask
            if np.isinf(valid_data).any():
                errors.append(f"Band {b_name} contains Inf inside valid mask")

            # Check bounds [-1.0, 1.0] with tolerance
            if valid_data.size > 0:
                v_min = float(np.min(valid_data))
                v_max = float(np.max(valid_data))
                if v_min < -1.0001 or v_max > 1.0001:
                    errors.append(
                        f"Band {b_name} values [{v_min:.4f}, {v_max:.4f}] exceed [-1.0, 1.0]"
                    )

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "indices_file": str(indices_path),
    }


def process_year_indicators(
    year: int,
    ard_dir: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Generate and save 3-band indicator stack and metadata for a single year.

    Args:
        year: Target year (2020, 2023, 2026).
        ard_dir: Path to directory containing scene_stack.tif, valid_mask.tif, metadata.json.
        output_dir: Destination directory for indicator outputs.

    Returns:
        Structured metadata record for downstream change detection.
    """
    stack_file = ard_dir / "scene_stack.tif"
    mask_file = ard_dir / "valid_mask.tif"
    meta_file = ard_dir / "metadata.json"

    if not stack_file.exists() or not mask_file.exists():
        raise FileNotFoundError(f"Missing ARD files in {ard_dir}")

    ard_meta: Dict[str, Any] = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            ard_meta = json.load(f)

    logger.info(f"[{year}] Calculating NDVI, NDWI, NDBI from ARD stack...")
    indices_dict, combined_mask, profile = calculate_indices(stack_file, mask_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_indices_path = output_dir / "indices.tif"
    out_mask_path = output_dir / "valid_mask.tif"

    height, width = combined_mask.shape

    # 1. Write 3-band float32 indices GeoTIFF
    indices_profile = profile.copy()
    indices_profile.update({
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": width,
        "height": height,
        "count": len(INDICATOR_BAND_NAMES),
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    })

    with rasterio.open(out_indices_path, "w", **indices_profile) as dst:
        for idx, name in enumerate(INDICATOR_BAND_NAMES, start=1):
            dst.write(indices_dict[name], idx)
            dst.set_band_description(idx, name)

    # 2. Write updated combined indicator valid mask
    mask_profile = profile.copy()
    mask_profile.update({
        "driver": "GTiff",
        "dtype": "uint8",
        "nodata": 0,
        "width": width,
        "height": height,
        "count": 1,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    })

    with rasterio.open(out_mask_path, "w", **mask_profile) as dst:
        dst.write(combined_mask.astype(np.uint8), 1)
        dst.set_band_description(1, "indicator_valid_mask")

    # 3. Compute distribution statistics
    stats_dict: Dict[str, Any] = {}
    for name in INDICATOR_BAND_NAMES:
        stats_dict[name.lower()] = summarize_indicator(
            data=indices_dict[name],
            valid_mask=combined_mask,
            indicator_name=name,
        )

    # 4. Perform quality validation
    validation = validate_indicator_raster(
        indices_path=out_indices_path,
        mask_path=out_mask_path,
        expected_crs=profile["crs"].to_string(),
        expected_dims=(height, width),
    )

    if not validation["passed"]:
        raise RuntimeError(f"Indicator validation failed for {year}: {validation['errors']}")

    # 5. Build metadata record for downstream Step 5
    metadata_record = {
        "year": year,
        "scene_id": ard_meta.get("item_id", "unknown"),
        "acquisition_date": ard_meta.get("acquisition_date", "unknown"),
        "day_of_year": ard_meta.get("day_of_year", None),
        "cloud_percentage": ard_meta.get("cloud_percentage", None),
        "crs": profile["crs"].to_string(),
        "dimensions": [height, width],
        "resolution_meters": abs(profile["transform"][0]),
        "bounds_projected": ard_meta.get("bounds_projected"),
        "band_order": INDICATOR_BAND_NAMES,
        "indices_file": str(out_indices_path),
        "mask_file": str(out_mask_path),
        "valid_pixel_percentage": stats_dict["ndvi"]["valid_percentage"],
        "statistics": stats_dict,
        "formulas": {
            "ndvi": "(NIR - RED) / (NIR + RED)",
            "ndwi": "(GREEN - NIR) / (GREEN + NIR)",
            "ndbi": "(SWIR1 - NIR) / (SWIR1 + NIR)",
        },
        "created_timestamp": datetime.utcnow().isoformat() + "Z",
    }

    meta_out_path = output_dir / "indicator_metadata.json"
    with open(meta_out_path, "w", encoding="utf-8") as f:
        json.dump(metadata_record, f, indent=2)

    logger.info(
        f"[{year}] Indicators generated: {out_indices_path.name} "
        f"({out_indices_path.stat().st_size / (1024*1024):.2f} MB) | "
        f"Valid Pixels={metadata_record['valid_pixel_percentage']}%"
    )
    return metadata_record


def check_spatial_consistency_across_epochs(
    epoch_records: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify that all generated indicator stacks share identical spatial metadata.

    Args:
        epoch_records: Dictionary mapping year string to indicator metadata dict.

    Returns:
        Consistency report dictionary.
    """
    years = sorted(list(epoch_records.keys()))
    if len(years) < 2:
        return {"passed": True, "details": "Only 1 epoch present"}

    ref_year = years[0]
    ref_file = Path(epoch_records[ref_year]["indices_file"])

    with rasterio.open(ref_file) as ref_src:
        ref_crs = ref_src.crs.to_string()
        ref_transform = ref_src.transform
        ref_dims = (ref_src.height, ref_src.width)
        ref_bounds = ref_src.bounds

    mismatches: List[str] = []
    comparisons: Dict[str, str] = {}

    for comp_year in years[1:]:
        comp_file = Path(epoch_records[comp_year]["indices_file"])
        pair_key = f"{ref_year} <-> {comp_year}"
        with rasterio.open(comp_file) as comp_src:
            if comp_src.crs.to_string() != ref_crs:
                mismatches.append(f"{pair_key}: CRS mismatch ({comp_src.crs} vs {ref_crs})")
            if comp_src.transform != ref_transform:
                mismatches.append(f"{pair_key}: Transform mismatch")
            if (comp_src.height, comp_src.width) != ref_dims:
                mismatches.append(
                    f"{pair_key}: Dimensions mismatch ({comp_src.height}x{comp_src.width} vs {ref_dims})"
                )
            if comp_src.bounds != ref_bounds:
                mismatches.append(f"{pair_key}: Bounds mismatch")

        comparisons[pair_key] = "PASS" if not any(pair_key in m for m in mismatches) else "FAIL"

    return {
        "passed": len(mismatches) == 0,
        "mismatches": mismatches,
        "comparisons": comparisons,
    }


def process_all_indicators(
    ard_base_dir: Optional[Path | str] = None,
    output_base_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Execute Step 4 across all epochs (2020, 2023, 2026).

    Args:
        ard_base_dir: Optional override for data/processed/sentinel2.
        output_base_dir: Optional override for data/processed/indicators.

    Returns:
        Summary dictionary containing metadata and spatial consistency checks.
    """
    cfg: AppConfig = get_config()
    in_dir = (
        Path(ard_base_dir).resolve()
        if ard_base_dir
        else cfg.directories.processed_dir / "sentinel2"
    )
    out_dir = (
        Path(output_base_dir).resolve()
        if output_base_dir
        else cfg.directories.processed_dir / "indicators"
    )

    epochs_summary: Dict[str, Any] = {}

    for year in cfg.time_periods.years:
        epoch_ard_dir = in_dir / str(year)
        if not epoch_ard_dir.exists():
            logger.warning(f"No ARD directory found for year {year} at {epoch_ard_dir}. Skipping.")
            continue

        epoch_out_dir = out_dir / str(year)
        record = process_year_indicators(
            year=year,
            ard_dir=epoch_ard_dir,
            output_dir=epoch_out_dir,
        )
        epochs_summary[str(year)] = record

    consistency = check_spatial_consistency_across_epochs(epochs_summary)
    if not consistency["passed"]:
        logger.error(f"Spatial consistency check failed across epochs: {consistency['mismatches']}")
        raise RuntimeError(f"Multi-temporal spatial mismatch: {consistency['mismatches']}")

    return {
        "epochs": epochs_summary,
        "spatial_consistency": consistency,
    }
