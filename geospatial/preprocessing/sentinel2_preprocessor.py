"""
UrbanPulse - Sentinel-2 Level-2A Preprocessing & Analysis-Ready Data (ARD) Pipeline.

Transforms remotely acquired Sentinel-2 Level-2A surface reflectance scenes into
standardized, cloud-masked, 10-meter analysis raster stacks in EPSG:32644.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import planetary_computer
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from rasterio.windows import from_bounds

from config.settings import AppConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.preprocessing.sentinel2_preprocessor")

# Canonical order of spectral bands for UrbanPulse ARD stacks
STACK_BAND_ORDER: List[str] = ["blue", "green", "red", "nir", "swir1", "swir2"]
STACK_BAND_ASSET_KEYS: Dict[str, str] = {
    "blue": "B02",
    "green": "B03",
    "red": "B04",
    "nir": "B08",
    "swir1": "B11",
    "swir2": "B12",
}

# ESA Sentinel-2 Scene Classification Layer (SCL) mapping
VALID_SCL_CLASSES: Set[int] = {2, 4, 5, 6, 7}
MASKED_SCL_CLASSES: Set[int] = {0, 1, 3, 8, 9, 10, 11}

# Baseline 04.00 deployment date: 2022-01-25 UTC
BASELINE_0400_DATE = datetime(2022, 1, 25, tzinfo=timezone.utc)
QUANTIFICATION_VALUE = 10000.0
BOA_ADD_OFFSET = -1000.0


def get_analysis_grid_geometry(
    aoi_bbox: List[float],
    crs: str = "EPSG:32644",
    resolution: float = 10.0,
) -> Tuple[Affine, int, int, Tuple[float, float, float, float]]:
    """
    Compute a deterministic, snapped pixel grid in the target CRS for the AOI.

    Args:
        aoi_bbox: Bounding box [min_lon, min_lat, max_lon, max_lat] in WGS84.
        crs: Target analysis CRS (e.g. 'EPSG:32644').
        resolution: Target pixel resolution in meters (default 10.0m).

    Returns:
        Tuple of (transform, width, height, (minx, miny, maxx, maxy)).
    """
    bounds_target = transform_bounds("EPSG:4326", crs, *aoi_bbox)

    # Snap bounds to integer multiples of resolution
    minx = float(int(bounds_target[0] // resolution) * resolution)
    miny = float(int(bounds_target[1] // resolution) * resolution)
    maxx = float(int(bounds_target[2] // resolution + 1) * resolution)
    maxy = float(int(bounds_target[3] // resolution + 1) * resolution)

    width = int(round((maxx - minx) / resolution))
    height = int(round((maxy - miny) / resolution))

    transform = Affine(resolution, 0.0, minx, 0.0, -resolution, maxy)
    return transform, width, height, (minx, miny, maxx, maxy)


def download_scene_assets(
    year: int,
    scene_meta: Dict[str, Any],
    raw_dir: Path,
    aoi_bbox: Optional[List[float]] = None,
) -> Dict[str, Path]:
    """
    Download only required spectral bands and SCL layer for the given scene,
    windowed to the configured AOI for efficiency.

    Args:
        year: Analysis epoch year.
        scene_meta: Scene dictionary from scene_catalog.json.
        raw_dir: Base directory for raw files (e.g. data/raw/sentinel2/{year}).
        aoi_bbox: AOI bounding box in WGS84. Defaults to config study_area.bbox.

    Returns:
        Dictionary mapping asset names (e.g. 'B02', 'SCL') to local GeoTIFF paths.
    """
    cfg: AppConfig = get_config()
    target_aoi = aoi_bbox or cfg.study_area.bbox

    scene_raw_dir = raw_dir / str(year)
    scene_raw_dir.mkdir(parents=True, exist_ok=True)

    assets_dict = scene_meta.get("assets", {})
    # Map both band aliases and direct asset keys
    keys_to_fetch = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]

    # Invert mapping from alias to key if needed
    alias_map = {b_info["asset_key"]: b_info for b_info in assets_dict.values()}

    local_paths: Dict[str, Path] = {}

    for key in keys_to_fetch:
        dest_file = scene_raw_dir / f"{key}.tif"
        if dest_file.exists() and dest_file.stat().st_size > 0:
            logger.info(f"[{year}] Asset {key} already downloaded at {dest_file.name}")
            local_paths[key] = dest_file
            continue

        if key not in alias_map:
            raise KeyError(f"Asset key '{key}' not found in scene catalog for year {year}")

        remote_url = alias_map[key]["href"]
        signed_url = planetary_computer.sign_url(remote_url)

        logger.info(f"[{year}] Streaming windowed asset {key} -> {dest_file.name}")
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                with rasterio.open(signed_url) as src:
                    # Transform AOI to source raster native CRS
                    aoi_native = transform_bounds("EPSG:4326", src.crs, *target_aoi)
                    # Add a 200m buffer in native CRS to prevent edge clipping during reprojection
                    buf = 200.0
                    buffered_bounds = (
                        aoi_native[0] - buf,
                        aoi_native[1] - buf,
                        aoi_native[2] + buf,
                        aoi_native[3] + buf,
                    )

                    window = from_bounds(*buffered_bounds, transform=src.transform)
                    # Round window offsets and dimensions to valid pixel coordinates
                    col_off = max(0, int(window.col_off))
                    row_off = max(0, int(window.row_off))
                    w_width = min(src.width - col_off, int(window.width) + 2)
                    w_height = min(src.height - row_off, int(window.height) + 2)

                    from rasterio.windows import Window
                    clamped_window = Window(col_off, row_off, w_width, w_height)

                    data = src.read(1, window=clamped_window)
                    win_transform = src.window_transform(clamped_window)

                    profile = src.profile.copy()
                    profile.update({
                        "driver": "GTiff",
                        "height": data.shape[0],
                        "width": data.shape[1],
                        "transform": win_transform,
                        "compress": "deflate",
                        "tiled": True,
                    })

                    with rasterio.open(dest_file, "w", **profile) as dst:
                        dst.write(data, 1)

                logger.info(
                    f"[{year}] Saved {key}.tif ({dest_file.stat().st_size / 1024:.1f} KB, shape={data.shape})"
                )
                local_paths[key] = dest_file
                break
            except Exception as exc:
                if attempt == max_retries:
                    logger.error(f"[{year}] Failed to download asset {key} after {max_retries} attempts: {exc}")
                    raise
                import time
                logger.warning(f"[{year}] Download attempt {attempt} for {key} failed ({exc}). Retrying in 2s...")
                time.sleep(2)
                # Refresh SAS signed URL
                signed_url = planetary_computer.sign_url(remote_url)

    return local_paths


def normalize_reflectance(
    data: np.ndarray,
    acquisition_date: str | datetime,
    baseline: Optional[str] = None,
) -> np.ndarray:
    """
    Convert raw Sentinel-2 Digital Numbers (DN) to physically calibrated surface reflectance.

    Applies radiometric baseline offset correction:
    - Pre-PB 04.00 (< 2022-01-25): Reflectance = DN / 10000.0
    - PB 04.00+ (>= 2022-01-25): Reflectance = (DN - 1000.0) / 10000.0

    Clips valid pixels to [0.0, 1.0], preserving zeros/NaNs for invalid data.

    Args:
        data: Raw digital number array (integer or float).
        acquisition_date: ISO date string or datetime object.
        baseline: Optional ESA processing baseline string (e.g. '04.00').

    Returns:
        Floating-point reflectance array in range [0.0, 1.0] with NaNs for nodata.
    """
    if isinstance(acquisition_date, str):
        # Handle ISO strings with possible UTC offset
        clean_date_str = acquisition_date.split("T")[0]
        acq_dt = datetime.strptime(clean_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    elif acquisition_date.tzinfo is None:
        acq_dt = acquisition_date.replace(tzinfo=timezone.utc)
    else:
        acq_dt = acquisition_date

    has_offset = False
    if baseline:
        try:
            has_offset = float(baseline.replace("0", "", 1) if baseline.startswith("0") else baseline) >= 4.0
        except ValueError:
            has_offset = acq_dt >= BASELINE_0400_DATE
    else:
        has_offset = acq_dt >= BASELINE_0400_DATE

    refl = data.astype(np.float32)

    # Mask nodata (DN == 0)
    nodata_mask = (data == 0)

    if has_offset:
        # Subtract ESA PB 04.00 offset (1000 DN)
        refl = (refl - 1000.0) / QUANTIFICATION_VALUE
    else:
        refl = refl / QUANTIFICATION_VALUE

    # Clip valid reflectance to physical range [0.0, 1.0]
    refl = np.clip(refl, 0.0, 1.0)
    refl[nodata_mask] = np.nan

    return refl


def apply_cloud_shadow_mask(scl_array: np.ndarray) -> np.ndarray:
    """
    Generate boolean valid-pixel mask using Sentinel-2 Scene Classification Layer (SCL).

    Valid classes: 2 (Dark), 4 (Vegetation), 5 (Bare/Soil), 6 (Water), 7 (Unclassified/Urban).
    Masked classes: 0 (No Data), 1 (Defective), 3 (Shadows), 8 (Med Cloud),
                    9 (High Cloud), 10 (Cirrus), 11 (Snow/Ice).

    Args:
        scl_array: Resampled SCL integer array.

    Returns:
        Boolean numpy array where True = valid, False = cloud/shadow/invalid.
    """
    valid_mask = np.isin(scl_array, list(VALID_SCL_CLASSES))
    return valid_mask.astype(bool)


def reproject_to_analysis_crs(
    src_path: Path,
    target_crs: str,
    target_transform: Affine,
    target_width: int,
    target_height: int,
    is_categorical: bool = False,
) -> np.ndarray:
    """
    Reproject and resample a source raster into the standardized target analysis grid.

    Uses Bilinear resampling for continuous reflectance, Nearest-Neighbor for categorical SCL.

    Args:
        src_path: Path to source GeoTIFF.
        target_crs: Target CRS string (e.g. 'EPSG:32644').
        target_transform: Snapped affine transform.
        target_width: Number of columns.
        target_height: Number of rows.
        is_categorical: True if categorical raster (SCL), False if continuous spectral band.

    Returns:
        Numpy array of shape (target_height, target_width).
    """
    resampling_method = Resampling.nearest if is_categorical else Resampling.bilinear

    with rasterio.open(src_path) as src:
        dest_dtype = src.dtypes[0]
        destination = np.zeros((target_height, target_width), dtype=dest_dtype)

        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=target_transform,
            dst_crs=target_crs,
            resampling=resampling_method,
        )

    return destination


def create_scene_stack(
    year: int,
    normalized_bands: Dict[str, np.ndarray],
    valid_mask: np.ndarray,
    target_transform: Affine,
    target_crs: str,
    output_dir: Path,
) -> Tuple[Path, Path]:
    """
    Write standardized 6-band reflectance stack and valid mask GeoTIFFs.

    Band order:
    1: Blue (B02)
    2: Green (B03)
    3: Red (B04)
    4: NIR (B08)
    5: SWIR1 (B11)
    6: SWIR2 (B12)

    Args:
        year: Analysis epoch year.
        normalized_bands: Dictionary of float32 band arrays.
        valid_mask: Boolean valid-pixel mask.
        target_transform: Grid transform.
        target_crs: Analysis CRS.
        output_dir: Output directory (e.g. data/processed/sentinel2/{year}).

    Returns:
        Tuple of (scene_stack_path, valid_mask_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stack_file = output_dir / "scene_stack.tif"
    mask_file = output_dir / "valid_mask.tif"

    height, width = valid_mask.shape

    # 1. Write 6-band float32 scene stack
    stack_profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": width,
        "height": height,
        "count": len(STACK_BAND_ORDER),
        "crs": target_crs,
        "transform": target_transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(stack_file, "w", **stack_profile) as dst:
        for idx, band_name in enumerate(STACK_BAND_ORDER, start=1):
            band_data = normalized_bands[band_name].astype(np.float32)
            dst.write(band_data, idx)
            dst.set_band_description(idx, band_name)

    # 2. Write 1-band uint8 valid mask (1 = valid, 0 = invalid)
    mask_profile = {
        "driver": "GTiff",
        "dtype": "uint8",
        "nodata": 0,
        "width": width,
        "height": height,
        "count": 1,
        "crs": target_crs,
        "transform": target_transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }

    with rasterio.open(mask_file, "w", **mask_profile) as dst:
        dst.write(valid_mask.astype(np.uint8), 1)
        dst.set_band_description(1, "valid_mask")

    logger.info(
        f"[{year}] Created standardized ARD stack: {stack_file.name} "
        f"({stack_file.stat().st_size / (1024*1024):.2f} MB) and {mask_file.name}"
    )
    return stack_file, mask_file


def validate_preprocessed_scene(
    stack_path: Path,
    mask_path: Path,
    expected_crs: str = "EPSG:32644",
    expected_res: float = 10.0,
) -> Dict[str, Any]:
    """
    Perform rigorous data quality and sanity checks on processed scene outputs.

    Checks:
    - Files exist and non-empty
    - Count == 6 spectral bands
    - CRS matches expected analysis CRS
    - Resolution == 10m
    - Stack and mask dimensions match
    - No NaN/Inf values inside valid pixels
    - Valid reflectance values within [0.0, 1.0] range
    - Valid pixel percentage reported

    Args:
        stack_path: Path to scene_stack.tif.
        mask_path: Path to valid_mask.tif.
        expected_crs: Target CRS string.
        expected_res: Expected resolution in meters.

    Returns:
        Dictionary of quality validation results.
    """
    errors: List[str] = []

    if not stack_path.exists():
        errors.append(f"Stack raster missing: {stack_path}")
    if not mask_path.exists():
        errors.append(f"Valid mask missing: {mask_path}")

    if errors:
        return {"passed": False, "errors": errors}

    with rasterio.open(stack_path) as src_stack, rasterio.open(mask_path) as src_mask:
        # Band count
        if src_stack.count != 6:
            errors.append(f"Expected 6 bands in stack, found {src_stack.count}")

        # CRS
        if src_stack.crs.to_string() != expected_crs:
            errors.append(f"Stack CRS {src_stack.crs} != expected {expected_crs}")
        if src_mask.crs.to_string() != expected_crs:
            errors.append(f"Mask CRS {src_mask.crs} != expected {expected_crs}")

        # Resolution
        res_x = abs(src_stack.transform[0])
        res_y = abs(src_stack.transform[4])
        if abs(res_x - expected_res) > 0.01 or abs(res_y - expected_res) > 0.01:
            errors.append(f"Resolution ({res_x}, {res_y}) != expected {expected_res}m")

        # Dimensions & transform match
        if (src_stack.width, src_stack.height) != (src_mask.width, src_mask.height):
            errors.append("Stack and mask dimensions do not match")
        if src_stack.transform != src_mask.transform:
            errors.append("Stack and mask affine transforms do not match")

        # Pixel statistics
        mask_data = src_mask.read(1)
        valid_indices = (mask_data == 1)
        total_pixels = mask_data.size
        valid_pixels = int(np.sum(valid_indices))
        valid_percentage = round((valid_pixels / total_pixels) * 100.0, 2)

        band_stats = {}
        for b_idx in range(1, 7):
            b_data = src_stack.read(b_idx)
            b_valid = b_data[valid_indices]

            # Check for NaNs/Infs in valid pixels
            if np.isnan(b_valid).any() or np.isinf(b_valid).any():
                errors.append(f"Band {b_idx} contains NaN/Inf values inside valid mask")

            # Check physical reflectance bounds
            if b_valid.size > 0:
                b_min = float(np.min(b_valid))
                b_max = float(np.max(b_valid))
                b_mean = float(np.mean(b_valid))
                band_stats[STACK_BAND_ORDER[b_idx - 1]] = {
                    "min": round(b_min, 4),
                    "max": round(b_max, 4),
                    "mean": round(b_mean, 4),
                }
                if b_min < -0.05 or b_max > 1.20:
                    errors.append(
                        f"Band {b_idx} reflectance range [{b_min:.2f}, {b_max:.2f}] outside reasonable bounds"
                    )

    passed = len(errors) == 0
    return {
        "passed": passed,
        "errors": errors,
        "width": src_stack.width,
        "height": src_stack.height,
        "crs": src_stack.crs.to_string(),
        "resolution": expected_res,
        "valid_pixels": valid_pixels,
        "total_pixels": total_pixels,
        "valid_percentage": valid_percentage,
        "band_stats": band_stats,
    }


def preprocess_scene(
    year: int,
    scene_meta: Dict[str, Any],
    raw_band_paths: Dict[str, Path],
    output_dir: Path,
    target_crs: str = "EPSG:32644",
    resolution: float = 10.0,
    aoi_bbox: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Execute end-to-end preprocessing pipeline for a single Sentinel-2 scene.

    Args:
        year: Analysis epoch year.
        scene_meta: Scene catalog metadata dict.
        raw_band_paths: Dictionary mapping keys ('B02', 'SCL', etc.) to downloaded files.
        output_dir: Output directory for ARD stack.
        target_crs: Target CRS string.
        resolution: Target resolution in meters.
        aoi_bbox: Target AOI in WGS84.

    Returns:
        Metadata record including paths and validation results.
    """
    cfg: AppConfig = get_config()
    target_aoi = aoi_bbox or cfg.study_area.bbox

    # 1. Establish common snapped analysis grid
    target_transform, width, height, bounds = get_analysis_grid_geometry(
        aoi_bbox=target_aoi,
        crs=target_crs,
        resolution=resolution,
    )

    logger.info(
        f"[{year}] Target Grid: CRS={target_crs} | Res={resolution}m | "
        f"Dims=({height}x{width}) | Bounds={bounds}"
    )

    # 2. Reproject and resample SCL (Categorical -> Nearest Neighbor)
    scl_reprojected = reproject_to_analysis_crs(
        src_path=raw_band_paths["SCL"],
        target_crs=target_crs,
        target_transform=target_transform,
        target_width=width,
        target_height=height,
        is_categorical=True,
    )

    # 3. Create cloud and shadow valid mask
    valid_mask = apply_cloud_shadow_mask(scl_reprojected)

    # 4. Reproject, resample, and normalize spectral bands
    acq_date = scene_meta["datetime"]
    baseline = scene_meta.get("platform_baseline")

    normalized_bands: Dict[str, np.ndarray] = {}
    for alias in STACK_BAND_ORDER:
        asset_key = STACK_BAND_ASSET_KEYS[alias]
        raw_path = raw_band_paths[asset_key]

        band_reprojected = reproject_to_analysis_crs(
            src_path=raw_path,
            target_crs=target_crs,
            target_transform=target_transform,
            target_width=width,
            target_height=height,
            is_categorical=False,
        )

        norm_band = normalize_reflectance(
            data=band_reprojected,
            acquisition_date=acq_date,
            baseline=baseline,
        )
        normalized_bands[alias] = norm_band

    # Ensure valid mask reflects SCL clearance AND presence of valid spectral data across all bands
    for alias in STACK_BAND_ORDER:
        valid_mask = valid_mask & (~np.isnan(normalized_bands[alias]))

    # 5. Write standardized scene stack and mask
    stack_path, mask_path = create_scene_stack(
        year=year,
        normalized_bands=normalized_bands,
        valid_mask=valid_mask,
        target_transform=target_transform,
        target_crs=target_crs,
        output_dir=output_dir,
    )

    # 6. Quality validation checks
    validation = validate_preprocessed_scene(
        stack_path=stack_path,
        mask_path=mask_path,
        expected_crs=target_crs,
        expected_res=resolution,
    )

    if not validation["passed"]:
        logger.error(f"[{year}] Preprocessing validation FAILED: {validation['errors']}")
        raise RuntimeError(f"Quality validation failed for {year}: {validation['errors']}")

    # 7. Write temporal metadata record
    dt_obj = datetime.fromisoformat(acq_date.replace("Z", "+00:00"))
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    metadata_record = {
        "year": year,
        "item_id": scene_meta["item_id"],
        "acquisition_date": acq_date,
        "day_of_year": dt_obj.timetuple().tm_yday,
        "cloud_percentage": scene_meta["cloud_cover"],
        "mgrs_tile": scene_meta.get("mgrs_tile", "unknown"),
        "crs": target_crs,
        "resolution_meters": resolution,
        "dimensions": [height, width],
        "bounds_projected": bounds,
        "band_order": STACK_BAND_ORDER,
        "stack_file": str(stack_path),
        "mask_file": str(mask_path),
        "valid_pixel_percentage": validation["valid_percentage"],
        "band_statistics": validation["band_stats"],
        "reflectance_scaling": {
            "quantification_value": QUANTIFICATION_VALUE,
            "boa_add_offset_applied": dt_obj >= BASELINE_0400_DATE,
            "formula": (
                "(DN - 1000) / 10000" if dt_obj >= BASELINE_0400_DATE else "DN / 10000"
            ),
        },
        "scl_masking": {
            "valid_classes": sorted(list(VALID_SCL_CLASSES)),
            "masked_classes": sorted(list(MASKED_SCL_CLASSES)),
        },
        "preprocessing_timestamp": datetime.utcnow().isoformat() + "Z",
    }

    meta_file = output_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata_record, f, indent=2)

    return metadata_record


def preprocess_all_selected_scenes(
    catalog_path: Optional[Path | str] = None,
    output_base_dir: Optional[Path | str] = None,
    raw_base_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Execute full Step 3 pipeline across all scenes in scene_catalog.json.

    1. Loads scene_catalog.json.
    2. Downloads required assets for 2020, 2023, 2026.
    3. Standardizes bands into EPSG:32644 at 10m resolution.
    4. Computes SCL valid-pixel mask.
    5. Normalizes reflectance with baseline offset handling.
    6. Creates standardized scene stacks and validates outputs.

    Args:
        catalog_path: Optional path to scene_catalog.json.
        output_base_dir: Optional base directory for processed sentinel2 stacks.
        raw_base_dir: Optional base directory for raw downloaded bands.

    Returns:
        Summary dictionary containing metadata for each epoch.
    """
    cfg: AppConfig = get_config()
    cat_file = (
        Path(catalog_path).resolve()
        if catalog_path
        else cfg.directories.processed_dir / "scene_catalog.json"
    )

    if not cat_file.exists():
        raise FileNotFoundError(f"Scene catalog not found at {cat_file}. Run Step 2 first.")

    with open(cat_file, "r", encoding="utf-8") as f:
        catalog_data = json.load(f)

    raw_dir = (
        Path(raw_base_dir).resolve()
        if raw_base_dir
        else cfg.directories.raw_dir / "sentinel2"
    )
    processed_dir = (
        Path(output_base_dir).resolve()
        if output_base_dir
        else cfg.directories.processed_dir / "sentinel2"
    )

    summary: Dict[str, Any] = {
        "study_area": catalog_data.get("study_area"),
        "target_crs": cfg.crs.projected,
        "target_resolution": 10.0,
        "epochs": {},
    }

    for year_str, period_data in catalog_data.get("periods", {}).items():
        year = int(year_str)
        scene = period_data.get("selected_scene")
        if not scene:
            logger.warning(f"No selected scene found in catalog for year {year}. Skipping.")
            continue

        logger.info(f"========== Preprocessing Epoch {year}: {scene['item_id']} ==========")

        # 1. Download required raw assets (windowed to AOI)
        raw_paths = download_scene_assets(
            year=year,
            scene_meta=scene,
            raw_dir=raw_dir,
            aoi_bbox=cfg.study_area.bbox,
        )

        # 2. Preprocess into ARD stack
        epoch_out_dir = processed_dir / str(year)
        record = preprocess_scene(
            year=year,
            scene_meta=scene,
            raw_band_paths=raw_paths,
            output_dir=epoch_out_dir,
            target_crs=cfg.crs.projected,
            resolution=10.0,
            aoi_bbox=cfg.study_area.bbox,
        )
        summary["epochs"][str(year)] = record

    logger.info("All selected Sentinel-2 scenes preprocessed and verified successfully.")
    return summary
