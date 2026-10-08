"""
UrbanPulse - Satellite Preprocessing Module.

Responsibilities:
- Standardize multi-temporal Sentinel-2 scenes to common analysis CRS (EPSG:32644) and resolution (10m).
- Apply cloud and shadow masks using Sentinel-2 Scene Classification Layer (SCL).
- Normalize surface reflectance across processing baselines (offset correction for PB >= 04.00).
- Produce analysis-ready 6-band stacks [blue, green, red, nir, swir1, swir2] and valid masks.
"""

from geospatial.preprocessing.sentinel2_preprocessor import (
    MASKED_SCL_CLASSES,
    STACK_BAND_ORDER,
    VALID_SCL_CLASSES,
    apply_cloud_shadow_mask,
    create_scene_stack,
    download_scene_assets,
    get_analysis_grid_geometry,
    normalize_reflectance,
    preprocess_all_selected_scenes,
    preprocess_scene,
    reproject_to_analysis_crs,
    validate_preprocessed_scene,
)

__all__ = [
    "MASKED_SCL_CLASSES",
    "STACK_BAND_ORDER",
    "VALID_SCL_CLASSES",
    "apply_cloud_shadow_mask",
    "create_scene_stack",
    "download_scene_assets",
    "get_analysis_grid_geometry",
    "normalize_reflectance",
    "preprocess_all_selected_scenes",
    "preprocess_scene",
    "reproject_to_analysis_crs",
    "validate_preprocessed_scene",
]
