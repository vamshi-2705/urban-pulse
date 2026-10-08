"""
Unit and integration tests for spectral indicators (NDVI, NDWI, NDBI).
Offline unit tests use synthetic arrays and small temporary GeoTIFFs.
Real ARD stack integration is marked with @pytest.mark.integration.
"""

from pathlib import Path
from typing import Dict

import numpy as np
import pytest
import rasterio
from affine import Affine

from geospatial.indicators.spectral_indices import (
    INDICATOR_BAND_NAMES,
    calculate_indices,
    calculate_ndbi,
    calculate_ndvi,
    calculate_ndwi,
    process_year_indicators,
    summarize_indicator,
    validate_indicator_raster,
)


def test_ndvi_formula_accuracy():
    """Verify NDVI = (NIR - Red) / (NIR + Red) calculation on known values."""
    nir = np.array([0.60, 0.40, 0.10], dtype=np.float32)
    red = np.array([0.20, 0.40, 0.50], dtype=np.float32)

    ndvi, mask = calculate_ndvi(nir, red)

    assert mask.all()
    # (0.60 - 0.20) / (0.60 + 0.20) = 0.40 / 0.80 = 0.50
    assert np.isclose(ndvi[0], 0.50)
    # (0.40 - 0.40) / (0.40 + 0.40) = 0.0
    assert np.isclose(ndvi[1], 0.00)
    # (0.10 - 0.50) / (0.10 + 0.50) = -0.40 / 0.60 = -0.6667
    assert np.isclose(ndvi[2], -0.6666667)


def test_ndwi_formula_accuracy():
    """Verify NDWI = (Green - NIR) / (Green + NIR) calculation on known values."""
    green = np.array([0.30, 0.10], dtype=np.float32)
    nir = np.array([0.10, 0.30], dtype=np.float32)

    ndwi, mask = calculate_ndwi(green, nir)

    assert mask.all()
    # (0.30 - 0.10) / (0.30 + 0.10) = 0.50
    assert np.isclose(ndwi[0], 0.50)
    # (0.10 - 0.30) / (0.10 + 0.30) = -0.50
    assert np.isclose(ndwi[1], -0.50)


def test_ndbi_formula_accuracy():
    """Verify NDBI = (SWIR1 - NIR) / (SWIR1 + NIR) calculation on known values."""
    swir1 = np.array([0.40, 0.20], dtype=np.float32)
    nir = np.array([0.20, 0.40], dtype=np.float32)

    ndbi, mask = calculate_ndbi(swir1, nir)

    assert mask.all()
    # (0.40 - 0.20) / (0.40 + 0.20) = 0.3333333
    assert np.isclose(ndbi[0], 1.0 / 3.0)
    # (0.20 - 0.40) / (0.20 + 0.40) = -0.3333333
    assert np.isclose(ndbi[1], -1.0 / 3.0)


def test_zero_denominator_handling():
    """Verify zero denominators produce NaN in indicator and False in valid mask."""
    nir = np.array([0.0, 0.3], dtype=np.float32)
    red = np.array([0.0, 0.1], dtype=np.float32)

    ndvi, mask = calculate_ndvi(nir, red)

    assert mask[0] is np.False_ or mask[0] == False
    assert np.isnan(ndvi[0])
    assert mask[1] is np.True_ or mask[1] == True
    assert np.isclose(ndvi[1], 0.5)


def test_valid_mask_propagation():
    """Verify external valid mask is respected and propagated."""
    nir = np.array([0.5, 0.5, 0.5], dtype=np.float32)
    red = np.array([0.1, 0.1, 0.1], dtype=np.float32)
    base_mask = np.array([True, False, True], dtype=bool)

    ndvi, mask = calculate_ndvi(nir, red, base_mask=base_mask)

    assert mask[0] is np.True_ or mask[0] == True
    assert mask[1] is np.False_ or mask[1] == False
    assert np.isnan(ndvi[1])
    assert mask[2] is np.True_ or mask[2] == True


def test_nan_and_inf_handling():
    """Verify NaN and Inf inputs are isolated and set to NaN without exceptions."""
    nir = np.array([np.nan, np.inf, 0.40], dtype=np.float32)
    red = np.array([0.20, 0.20, 0.20], dtype=np.float32)

    ndvi, mask = calculate_ndvi(nir, red)

    assert not mask[0]
    assert np.isnan(ndvi[0])
    assert not mask[1]
    assert np.isnan(ndvi[1])
    assert mask[2]
    assert np.isfinite(ndvi[2])


def test_theoretical_ranges():
    """Verify all valid calculated indices lie strictly within [-1.0, 1.0]."""
    rng = np.random.default_rng(42)
    band_a = rng.uniform(0.01, 0.90, size=(50, 50)).astype(np.float32)
    band_b = rng.uniform(0.01, 0.90, size=(50, 50)).astype(np.float32)

    ndvi, mask = calculate_ndvi(band_a, band_b)

    assert mask.all()
    assert np.all(ndvi >= -1.0)
    assert np.all(ndvi <= 1.0)


def test_summarize_indicator_metrics():
    """Verify statistics computation on valid values."""
    data = np.array([0.1, 0.2, 0.3, 0.4, np.nan], dtype=np.float32)
    mask = np.array([True, True, True, True, False], dtype=bool)

    stats = summarize_indicator(data, mask, "TEST_INDEX")

    assert stats["valid_pixels"] == 4
    assert stats["invalid_pixels"] == 1
    assert stats["valid_percentage"] == 80.0
    assert np.isclose(stats["min"], 0.1)
    assert np.isclose(stats["max"], 0.4)
    assert np.isclose(stats["mean"], 0.25)
    assert np.isclose(stats["median"], 0.25)


def test_synthetic_indicator_stack_creation_and_band_order(tmp_path: Path):
    """Create a temporary 6-band ARD stack, process indicators, and verify outputs."""
    h, w = 30, 40
    transform = Affine(10.0, 0.0, 218000.0, 0.0, -10.0, 1930000.0)
    crs = "EPSG:32644"

    ard_dir = tmp_path / "ard"
    out_dir = tmp_path / "indicators"
    ard_dir.mkdir(parents=True)

    # 1. Write synthetic 6-band ARD stack:
    # 1: blue=0.1, 2: green=0.15, 3: red=0.10, 4: nir=0.40, 5: swir1=0.25, 6: swir2=0.20
    stack_file = ard_dir / "scene_stack.tif"
    mask_file = ard_dir / "valid_mask.tif"

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "nodata": np.nan,
        "width": w,
        "height": h,
        "count": 6,
        "crs": crs,
        "transform": transform,
    }

    band_values = [0.10, 0.15, 0.10, 0.40, 0.25, 0.20]
    with rasterio.open(stack_file, "w", **profile) as dst:
        for b_i, val in enumerate(band_values, start=1):
            dst.write(np.full((h, w), val, dtype=np.float32), b_i)

    # Write mask (all valid except top-left corner)
    mask_arr = np.ones((h, w), dtype=np.uint8)
    mask_arr[0, 0] = 0

    mask_profile = profile.copy()
    mask_profile.update({"dtype": "uint8", "nodata": 0, "count": 1})
    with rasterio.open(mask_file, "w", **mask_profile) as dst:
        dst.write(mask_arr, 1)

    # 2. Process indicators
    record = process_year_indicators(year=2023, ard_dir=ard_dir, output_dir=out_dir)

    # Verify generated files
    ind_file = out_dir / "indices.tif"
    ind_mask_file = out_dir / "valid_mask.tif"
    assert ind_file.exists()
    assert ind_mask_file.exists()

    with rasterio.open(ind_file) as src:
        assert src.count == 3
        assert src.crs.to_string() == crs
        assert src.width == w
        assert src.height == h
        assert src.descriptions == tuple(INDICATOR_BAND_NAMES)

        # Band 1: NDVI = (0.40 - 0.10) / (0.40 + 0.10) = 0.30 / 0.50 = 0.60
        ndvi_band = src.read(1)
        assert np.isnan(ndvi_band[0, 0])
        assert np.isclose(ndvi_band[1, 1], 0.60)

        # Band 2: NDWI = (0.15 - 0.40) / (0.15 + 0.40) = -0.25 / 0.55 = -0.454545
        ndwi_band = src.read(2)
        assert np.isclose(ndwi_band[1, 1], -0.25 / 0.55)

        # Band 3: NDBI = (0.25 - 0.40) / (0.25 + 0.40) = -0.15 / 0.65 = -0.230769
        ndbi_band = src.read(3)
        assert np.isclose(ndbi_band[1, 1], -0.15 / 0.65)


# ==============================================================================
# INTEGRATION TEST (Uses real Step 3 ARD outputs)
# ==============================================================================


@pytest.mark.integration
def test_real_ard_indicators_integration():
    """Verify indicators calculation on actual processed 2023 ARD scene stack."""
    from config.settings import get_config

    cfg = get_config()
    ard_2023 = cfg.directories.processed_dir / "sentinel2" / "2023"
    stack_file = ard_2023 / "scene_stack.tif"
    mask_file = ard_2023 / "valid_mask.tif"

    assert stack_file.exists(), "Step 3 ARD stack for 2023 must exist"
    assert mask_file.exists(), "Step 3 valid mask for 2023 must exist"

    indices_dict, combined_mask, profile = calculate_indices(stack_file, mask_file)

    assert "NDVI" in indices_dict
    assert "NDWI" in indices_dict
    assert "NDBI" in indices_dict
    assert combined_mask.shape == (profile["height"], profile["width"])

    valid_ndvi = indices_dict["NDVI"][combined_mask]
    assert valid_ndvi.size > 0
    assert np.all(valid_ndvi >= -1.0)
    assert np.all(valid_ndvi <= 1.0)
    assert not np.isnan(valid_ndvi).any()
