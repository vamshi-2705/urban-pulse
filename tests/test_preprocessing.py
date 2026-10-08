"""
Unit and integration tests for Sentinel-2 preprocessing and ARD stacking.
Offline unit tests use synthetic in-memory arrays and small temp rasters.
Live network access is isolated to @pytest.mark.integration.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Dict

import numpy as np
import pytest
import rasterio
from affine import Affine

from config.settings import get_config
from geospatial.preprocessing.sentinel2_preprocessor import (
    STACK_BAND_ORDER,
    VALID_SCL_CLASSES,
    apply_cloud_shadow_mask,
    create_scene_stack,
    get_analysis_grid_geometry,
    normalize_reflectance,
    validate_preprocessed_scene,
)


def test_scene_catalog_loading():
    """Verify that the generated scene_catalog.json exists and contains 2020, 2023, 2026."""
    cfg = get_config()
    cat_path = cfg.directories.processed_dir / "scene_catalog.json"
    assert cat_path.exists(), "scene_catalog.json should exist from Step 2"

    with open(cat_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "periods" in data
    for yr in ["2020", "2023", "2026"]:
        assert yr in data["periods"]
        assert data["periods"][yr]["status"] == "SUCCESS"
        assert data["periods"][yr]["selected_scene"] is not None


def test_analysis_grid_geometry_calculation():
    """Verify snapped bounds, 10m resolution, and positive dimensions."""
    aoi = [78.35, 17.35, 78.55, 17.50]
    transform, width, height, bounds = get_analysis_grid_geometry(
        aoi_bbox=aoi,
        crs="EPSG:32644",
        resolution=10.0,
    )

    assert width > 0
    assert height > 0
    assert abs(transform[0] - 10.0) < 1e-4
    assert abs(transform[4] - (-10.0)) < 1e-4
    assert bounds[0] < bounds[2]
    assert bounds[1] < bounds[3]
    # Check bounds snapped to 10m
    assert bounds[0] % 10.0 == 0.0
    assert bounds[1] % 10.0 == 0.0


def test_reflectance_normalization_pre_pb0400():
    """Verify pre-PB 04.00 (2020) reflectance scaling (DN / 10000)."""
    raw_dn = np.array([0, 1000, 2000, 5000, 10000], dtype=np.uint16)
    refl = normalize_reflectance(raw_dn, acquisition_date="2020-03-29T05:06:51")

    assert np.isnan(refl[0])  # DN=0 is nodata
    assert np.isclose(refl[1], 0.10)
    assert np.isclose(refl[2], 0.20)
    assert np.isclose(refl[3], 0.50)
    assert np.isclose(refl[4], 1.00)


def test_reflectance_normalization_post_pb0400():
    """Verify PB 04.00+ (2023 & 2026) offset correction ((DN - 1000) / 10000)."""
    raw_dn = np.array([0, 500, 1000, 2000, 11000], dtype=np.uint16)
    refl = normalize_reflectance(raw_dn, acquisition_date="2023-01-28T05:10:49")

    assert np.isnan(refl[0])  # DN=0 is nodata
    assert np.isclose(refl[1], 0.0)  # (500 - 1000) clipped to 0.0
    assert np.isclose(refl[2], 0.0)  # (1000 - 1000)/10000 = 0.0
    assert np.isclose(refl[3], 0.10)  # (2000 - 1000)/10000 = 0.10
    assert np.isclose(refl[4], 1.00)  # (11000 - 1000)/10000 = 1.00


def test_scl_cloud_and_shadow_masking():
    """Verify SCL masking classifies valid vs masked categories correctly."""
    # SCL values: 0 (NoData), 2 (Dark), 3 (Shadow), 4 (Veg), 7 (Urban), 8 (Cloud), 9 (Cloud High)
    scl_sample = np.array([0, 2, 3, 4, 7, 8, 9], dtype=np.uint8)
    mask = apply_cloud_shadow_mask(scl_sample)

    expected = np.array([False, True, False, True, True, False, False], dtype=bool)
    np.testing.assert_array_equal(mask, expected)


def test_synthetic_scene_stack_creation_and_validation(tmp_path: Path):
    """Create a small synthetic 6-band scene stack and verify quality validation passes."""
    h, w = 40, 50
    transform = Affine(10.0, 0.0, 218000.0, 0.0, -10.0, 1930000.0)
    crs = "EPSG:32644"

    # Create synthetic float32 bands
    bands: Dict[str, np.ndarray] = {}
    for alias in STACK_BAND_ORDER:
        bands[alias] = np.full((h, w), 0.25, dtype=np.float32)

    # Valid mask with mostly valid pixels
    mask = np.ones((h, w), dtype=bool)
    mask[0, 0] = False  # 1 invalid pixel

    stack_path, mask_path = create_scene_stack(
        year=2023,
        normalized_bands=bands,
        valid_mask=mask,
        target_transform=transform,
        target_crs=crs,
        output_dir=tmp_path,
    )

    assert stack_path.exists()
    assert mask_path.exists()

    val_result = validate_preprocessed_scene(
        stack_path=stack_path,
        mask_path=mask_path,
        expected_crs=crs,
        expected_res=10.0,
    )

    assert val_result["passed"] is True
    assert val_result["width"] == w
    assert val_result["height"] == h
    assert val_result["valid_pixels"] == (h * w) - 1
    assert "band_stats" in val_result


def test_validation_fails_on_corrupted_band(tmp_path: Path):
    """Verify validation detects NaN values inside valid pixels."""
    h, w = 20, 20
    transform = Affine(10.0, 0.0, 218000.0, 0.0, -10.0, 1930000.0)
    crs = "EPSG:32644"

    bands: Dict[str, np.ndarray] = {alias: np.full((h, w), 0.2, dtype=np.float32) for alias in STACK_BAND_ORDER}
    # Corrupt one band with NaN inside valid area
    bands["red"][5, 5] = np.nan
    mask = np.ones((h, w), dtype=bool)

    stack_path, mask_path = create_scene_stack(
        year=2020,
        normalized_bands=bands,
        valid_mask=mask,
        target_transform=transform,
        target_crs=crs,
        output_dir=tmp_path,
    )

    val_result = validate_preprocessed_scene(
        stack_path=stack_path,
        mask_path=mask_path,
        expected_crs=crs,
        expected_res=10.0,
    )

    assert val_result["passed"] is False
    assert any("NaN" in err for err in val_result["errors"])


# ==============================================================================
# LIVE INTEGRATION TEST (Requires live Planetary Computer access)
# ==============================================================================


@pytest.mark.integration
def test_live_sentinel2_asset_access():
    """Live integration test: Verify signed asset URL can be opened with rasterio."""
    import planetary_computer

    cfg = get_config()
    cat_path = cfg.directories.processed_dir / "scene_catalog.json"
    with open(cat_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    p2023 = catalog["periods"]["2023"]["selected_scene"]
    b02_url = p2023["assets"]["blue"]["href"].split("?")[0]
    signed_url = planetary_computer.sign_url(b02_url)

    with rasterio.open(signed_url) as src:
        assert src.crs is not None
        assert src.width > 0
        assert src.height > 0
