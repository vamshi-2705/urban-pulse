"""
Tests for UrbanPulse Temporal Change Detection Module (Step 5).

Covers:
1. Pairwise subtraction accuracy
2. Absolute change magnitude
3. Epsilon thresholding tolerance
4. Positive directional classification
5. Negative directional classification
6. Stable tolerance zone classification
7. Persistence trajectory detection
8. Reversal trajectory detection
9. Valid mask propagation across epochs (invalid if invalid in either)
10. Spatial alignment validation (CRS, dimensions, transform, resolution)
11. Metadata generation and schema
12. Output band ordering
13. Real indicator integration test (@pytest.mark.integration)
"""

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import rasterio
from affine import Affine

from config.settings import AppConfig, get_config
from geospatial.change_detection.temporal_change import (
    PAIRWISE_CHANGE_BAND_NAMES,
    PERSISTENCE_BAND_NAMES,
    calculate_change_magnitude,
    calculate_pairwise_change,
    calculate_persistence,
    classify_change_direction,
    generate_change_metadata,
    summarize_delta,
    validate_change_outputs,
    validate_temporal_alignment,
)


def _create_synthetic_profiles(
    crs: str = "EPSG:32644",
    width: int = 10,
    height: int = 10,
    transform: Affine = Affine(10.0, 0.0, 200000.0, 0.0, -10.0, 1900000.0),
) -> Dict[str, Any]:
    """Helper to create minimal rasterio profile dictionary."""
    return {
        "crs": crs,
        "width": width,
        "height": height,
        "transform": transform,
        "count": 3,
        "dtype": "float32",
    }


def test_pairwise_subtraction():
    """Verify that delta is computed strictly as (later_value - earlier_value)."""
    earlier = np.array([[[0.2, 0.5], [0.8, 0.1]]], dtype=np.float32)
    later = np.array([[[0.5, 0.3], [0.8, -0.2]]], dtype=np.float32)
    # Stack 3 identical bands for shape (3, 2, 2)
    earlier_stack = np.repeat(earlier, 3, axis=0)
    later_stack = np.repeat(later, 3, axis=0)
    mask = np.ones((2, 2), dtype=bool)

    result = calculate_pairwise_change(
        earlier_stack, later_stack, mask, mask, epsilons={"ndvi": 0.1, "ndwi": 0.1, "ndbi": 0.1}
    )

    expected_delta = np.array([[0.3, -0.2], [0.0, -0.3]], dtype=np.float32)
    np.testing.assert_allclose(result["ndvi_delta"], expected_delta, atol=1e-6)
    np.testing.assert_allclose(result["ndwi_delta"], expected_delta, atol=1e-6)
    np.testing.assert_allclose(result["ndbi_delta"], expected_delta, atol=1e-6)


def test_absolute_change_magnitude():
    """Verify abs_change = abs(delta) with NaNs preserved."""
    delta = np.array([[0.25, -0.35], [0.0, np.nan]], dtype=np.float32)
    mag = calculate_change_magnitude(delta)

    assert mag[0, 0] == pytest.approx(0.25, abs=1e-6)
    assert mag[0, 1] == pytest.approx(0.35, abs=1e-6)
    assert mag[1, 0] == pytest.approx(0.0, abs=1e-6)
    assert np.isnan(mag[1, 1])


def test_epsilon_thresholding_and_direction():
    """Verify analytical tolerance epsilon classifies delta into +1, -1, 0."""
    delta = np.array([-0.25, -0.10, -0.05, 0.0, 0.05, 0.10, 0.25], dtype=np.float32)
    eps = 0.10
    direction = classify_change_direction(delta, epsilon=eps)

    expected = np.array([-1, 0, 0, 0, 0, 0, 1], dtype=np.int8)
    np.testing.assert_array_equal(direction, expected)


def test_positive_and_negative_direction_invalid_mask():
    """Verify that pixels outside valid_mask are classified as 0 (inactive)."""
    delta = np.array([0.5, -0.5, 0.5], dtype=np.float32)
    valid_mask = np.array([True, True, False], dtype=bool)
    direction = classify_change_direction(delta, epsilon=0.1, valid_mask=valid_mask)

    assert direction[0] == 1
    assert direction[1] == -1
    assert direction[2] == 0  # Invalid pixel


def test_stable_tolerance_zone():
    """Verify that small sensor / atmospheric noise below epsilon is mapped to stable (0)."""
    delta = np.array([0.02, -0.03, 0.001], dtype=np.float32)
    direction = classify_change_direction(delta, epsilon=0.08)
    np.testing.assert_array_equal(direction, np.zeros(3, dtype=np.int8))


def test_persistence_detection():
    """Verify persistence across two sequential observation intervals."""
    # Synthetic period A: NDBI increases by +0.3
    # Synthetic period B: NDBI increases by +0.2
    h, w = 2, 2
    period_a = {
        "valid_mask": np.ones((h, w), dtype=bool),
        "vegetation_loss": np.zeros((h, w), dtype=np.float32),
        "vegetation_gain": np.zeros((h, w), dtype=np.float32),
        "water_loss": np.zeros((h, w), dtype=np.float32),
        "water_gain": np.zeros((h, w), dtype=np.float32),
        "builtup_increase": np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32),
        "builtup_decrease": np.zeros((h, w), dtype=np.float32),
    }

    period_b = {
        "valid_mask": np.ones((h, w), dtype=bool),
        "vegetation_loss": np.zeros((h, w), dtype=np.float32),
        "vegetation_gain": np.zeros((h, w), dtype=np.float32),
        "water_loss": np.zeros((h, w), dtype=np.float32),
        "water_gain": np.zeros((h, w), dtype=np.float32),
        "builtup_increase": np.array([[1.0, 1.0], [0.0, 0.0]], dtype=np.float32),
        "builtup_decrease": np.zeros((h, w), dtype=np.float32),
    }

    persist = calculate_persistence(period_a, period_b)
    # (0, 0) was built-up increase in both periods -> persistent_builtup_increase = 1
    assert persist["persistent_builtup_increase"][0, 0] == 1
    # (0, 1) was built-up increase only in period B -> not persistent
    assert persist["persistent_builtup_increase"][0, 1] == 0
    # No reversals
    assert persist["builtup_reversal"][0, 0] == 0


def test_reversal_detection():
    """Verify that opposite directional movements between periods are tagged as reversals."""
    h, w = 2, 2
    # Period A: vegetation loss (NDVI decrease)
    period_a = {
        "valid_mask": np.ones((h, w), dtype=bool),
        "vegetation_loss": np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32),
        "vegetation_gain": np.zeros((h, w), dtype=np.float32),
        "water_loss": np.zeros((h, w), dtype=np.float32),
        "water_gain": np.zeros((h, w), dtype=np.float32),
        "builtup_increase": np.zeros((h, w), dtype=np.float32),
        "builtup_decrease": np.zeros((h, w), dtype=np.float32),
    }

    # Period B: vegetation gain (NDVI rebound)
    period_b = {
        "valid_mask": np.ones((h, w), dtype=bool),
        "vegetation_loss": np.zeros((h, w), dtype=np.float32),
        "vegetation_gain": np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.float32),
        "water_loss": np.zeros((h, w), dtype=np.float32),
        "water_gain": np.zeros((h, w), dtype=np.float32),
        "builtup_increase": np.zeros((h, w), dtype=np.float32),
        "builtup_decrease": np.zeros((h, w), dtype=np.float32),
    }

    persist = calculate_persistence(period_a, period_b)
    # Pixel (0, 0) decreased in A and increased in B -> Reversal!
    assert persist["vegetation_reversal"][0, 0] == 1
    # Persistent decrease must NOT be flagged
    assert persist["persistent_vegetation_decrease"][0, 0] == 0


def test_valid_mask_propagation():
    """
    Verify invalid pixel propagation:
    If pixel is invalid in EITHER earlier or later epoch, comparison must be invalid,
    and delta must be NaN, NEVER zero.
    """
    earlier = np.ones((3, 2, 2), dtype=np.float32) * 0.5
    later = np.ones((3, 2, 2), dtype=np.float32) * 0.7

    earlier_mask = np.array([[True, False], [True, True]], dtype=bool)
    later_mask = np.array([[True, True], [False, True]], dtype=bool)

    result = calculate_pairwise_change(earlier, later, earlier_mask, later_mask)

    # Pixel (0, 0): both valid -> delta = 0.2
    assert result["valid_mask"][0, 0] is True or result["valid_mask"][0, 0] == 1
    assert result["ndvi_delta"][0, 0] == pytest.approx(0.2, abs=1e-6)

    # Pixel (0, 1): invalid in earlier -> invalid, delta must be NaN
    assert not result["valid_mask"][0, 1]
    assert np.isnan(result["ndvi_delta"][0, 1])

    # Pixel (1, 0): invalid in later -> invalid, delta must be NaN
    assert not result["valid_mask"][1, 0]
    assert np.isnan(result["ndvi_delta"][1, 0])

    # Pixel (1, 1): both valid -> delta = 0.2
    assert result["valid_mask"][1, 1] is True or result["valid_mask"][1, 1] == 1
    assert result["ndvi_delta"][1, 1] == pytest.approx(0.2, abs=1e-6)


def test_alignment_validation():
    """Verify temporal alignment enforces strict CRS, dimensions, resolution, and affine transform."""
    prof1 = _create_synthetic_profiles()
    prof2 = _create_synthetic_profiles()
    # Matching passes
    assert validate_temporal_alignment([prof1, prof2]) is True

    # CRS mismatch
    prof_crs_bad = _create_synthetic_profiles(crs="EPSG:4326")
    with pytest.raises(ValueError, match="CRS mismatch"):
        validate_temporal_alignment([prof1, prof_crs_bad])

    # Dimension mismatch
    prof_dim_bad = _create_synthetic_profiles(width=12)
    with pytest.raises(ValueError, match="Dimension mismatch"):
        validate_temporal_alignment([prof1, prof_dim_bad])

    # Resolution mismatch
    t_bad = Affine(20.0, 0.0, 200000.0, 0.0, -20.0, 1900000.0)
    prof_res_bad = _create_synthetic_profiles(transform=t_bad)
    with pytest.raises(ValueError, match="Resolution mismatch"):
        validate_temporal_alignment([prof1, prof_res_bad])


def test_metadata_structure():
    """Verify metadata summarizer computes distribution percentiles and counts."""
    delta = np.array([[0.2, -0.3], [0.05, 0.0]], dtype=np.float32)
    mask = np.ones((2, 2), dtype=bool)

    stats = summarize_delta(delta, mask, "test_delta", epsilon=0.10)
    assert stats["name"] == "test_delta"
    assert stats["valid_pixels"] == 4
    assert stats["invalid_pixels"] == 0
    assert stats["positive_pixels"] == 1  # 0.2
    assert stats["negative_pixels"] == 1  # -0.3
    assert stats["changed_pixels"] == 2
    assert "mean" in stats
    assert "median" in stats
    assert "p05" in stats
    assert "p95" in stats


def test_output_band_ordering():
    """Verify deterministic band names and ordering for change and persistence stacks."""
    expected_change_bands = [
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
    assert PAIRWISE_CHANGE_BAND_NAMES == expected_change_bands
    assert len(PAIRWISE_CHANGE_BAND_NAMES) == 12

    expected_persistence_bands = [
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
    assert PERSISTENCE_BAND_NAMES == expected_persistence_bands
    assert len(PERSISTENCE_BAND_NAMES) == 9


@pytest.mark.integration
def test_real_indicators_change_integration():
    """
    Integration test: Run pairwise change detection on real Step 4 indicator rasters.
    Verifies real raster reading, alignment, delta computation, and mask propagation.
    """
    cfg = get_config()
    proc_dir = cfg.directories.processed_dir / "indicators"
    path_2020 = proc_dir / "2020" / "indices.tif"
    path_2023 = proc_dir / "2023" / "indices.tif"

    if not path_2020.exists() or not path_2023.exists():
        pytest.skip("Step 4 indicator rasters not found on disk; skipping integration test.")

    with rasterio.open(path_2020) as s20, rasterio.open(path_2023) as s23:
        p20 = s20.profile
        p23 = s23.profile

    # Verify alignment
    assert validate_temporal_alignment([p20, p23]) is True

    # Read window of 100x100 pixels for fast integration check
    win = rasterio.windows.Window(100, 100, 100, 100)
    with rasterio.open(path_2020) as s20, rasterio.open(path_2023) as s23:
        arr_2020 = s20.read(window=win)
        arr_2023 = s23.read(window=win)

    mask_2020_path = proc_dir / "2020" / "valid_mask.tif"
    mask_2023_path = proc_dir / "2023" / "valid_mask.tif"

    with rasterio.open(mask_2020_path) as m20, rasterio.open(mask_2023_path) as m23:
        m_2020 = m20.read(1, window=win) == 1
        m_2023 = m23.read(1, window=win) == 1

    res = calculate_pairwise_change(arr_2020, arr_2023, m_2020, m_2023)

    assert "change_stack" in res
    assert res["change_stack"].shape == (12, 100, 100)
    assert res["change_stack"].dtype == np.float32

    # Check finite deltas inside valid mask
    v_mask = res["valid_mask"]
    assert np.all(np.isfinite(res["ndvi_delta"][v_mask]))
    assert np.all(np.isfinite(res["ndwi_delta"][v_mask]))
    assert np.all(np.isfinite(res["ndbi_delta"][v_mask]))
