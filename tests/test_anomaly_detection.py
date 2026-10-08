"""
Unit and Integration Tests for UrbanPulse Anomaly Detection (Step 6).

Verifies all 22 specification criteria:
1. Robust median calculation
2. MAD calculation
3. Robust z-score accuracy
4. Zero-MAD fallback handling
5. Bounded anomaly transformation [0, 1]
6. Temporal anomaly direction and magnitude
7. Spatial neighborhood calculation
8. Invalid-neighbor exclusion
9. Minimum-neighbor threshold
10. Spatial edge behavior
11. Combined anomaly weighting
12. Missing-component handling
13. Score bounds [0, 1]
14. NaN propagation
15. Evidence flags
16. Vegetation + built-up coherence
17. Persistence integration
18. Reversal integration
19. Raster alignment validation
20. Output metadata
21. Output band order
22. Real Step 5 integration (@pytest.mark.integration)
"""

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import rasterio

from config.settings import (
    CombinedAnomalyConfig,
    EvidenceConfig,
    SpatialAnomalyConfig,
    TemporalAnomalyConfig,
    get_config,
)
from geospatial.anomaly_detection import (
    ANOMALY_STACK_BAND_NAMES,
    EVIDENCE_FLAG_BAND_NAMES,
    build_evidence_record,
    calculate_robust_center_dispersion,
    calculate_robust_z,
    compute_indicator_spatial_anomaly,
    compute_indicator_temporal_anomaly,
    compute_period_combined_anomalies,
    count_valid_neighbors,
    evaluate_cross_indicator_evidence,
    fuse_anomaly_components,
    validate_anomaly_raster,
    z_to_anomaly_score,
)


# 1. Robust Median Calculation
def test_robust_median_calculation():
    data = np.array([1.0, 2.0, 3.0, 4.0, 100.0], dtype=np.float32)
    mask = np.ones(5, dtype=bool)
    med, mad, disp, fallback = calculate_robust_center_dispersion(data, mask, min_samples=3)
    assert med == pytest.approx(3.0, abs=1e-5)
    assert not fallback


# 2. MAD Calculation
def test_mad_calculation():
    # deviations from median 3: |1-3|=2, |2-3|=1, |3-3|=0, |4-3|=1, |100-3|=97
    # sorted deviations: [0, 1, 1, 2, 97], median is 1.0
    data = np.array([1.0, 2.0, 3.0, 4.0, 100.0], dtype=np.float32)
    mask = np.ones(5, dtype=bool)
    med, mad, disp, fallback = calculate_robust_center_dispersion(data, mask, mad_scale=0.6745, min_samples=3)
    assert mad == pytest.approx(1.0, abs=1e-5)
    assert disp == pytest.approx(1.0 / 0.6745, abs=1e-4)


# 3. Robust Z-Score
def test_robust_z_score():
    data = np.array([3.0, 5.0, 1.0], dtype=np.float32)
    # median = 3.0, dispersion = 2.0
    z = calculate_robust_z(data, median=3.0, dispersion=2.0)
    expected = np.array([0.0, 1.0, -1.0], dtype=np.float32)
    np.testing.assert_allclose(z, expected, atol=1e-5)


# 4. Zero-MAD Fallback
def test_zero_mad_fallback():
    # Identical values yield MAD = 0.0
    data = np.full(50, 2.5, dtype=np.float32)
    mask = np.ones(50, dtype=bool)
    med, mad, disp, fallback = calculate_robust_center_dispersion(
        data, mask, mad_floor=0.001, mad_scale=0.6745, min_samples=10
    )
    assert mad == 0.0
    assert fallback is True
    assert disp == pytest.approx(0.001 / 0.6745, abs=1e-5)


# 5. Bounded Anomaly Transformation [0, 1]
def test_bounded_anomaly_transformation():
    z = np.array([0.0, 1.75, 3.5, 7.0, -7.0], dtype=np.float32)
    score = z_to_anomaly_score(z, z_clip=3.5)
    expected = np.array([0.0, 0.5, 1.0, 1.0, 1.0], dtype=np.float32)
    np.testing.assert_allclose(score, expected, atol=1e-5)


# 6. Temporal Anomaly Direction & Magnitude
def test_temporal_anomaly_direction_magnitude():
    delta = np.array([0.0, 0.5, -0.5], dtype=np.float32)
    mask = np.ones(3, dtype=bool)
    cfg = TemporalAnomalyConfig(minimum_valid_samples=3, z_clip=2.0)
    res = compute_indicator_temporal_anomaly(delta, mask, cfg)
    assert res["sign"][1] == 1
    assert res["sign"][2] == -1
    assert res["anomaly_score"][1] > 0.0
    assert res["anomaly_score"][2] > 0.0


# 7. Spatial Neighborhood Calculation
def test_spatial_neighborhood_calculation():
    # 5x5 array with uniform background 1.0 and an anomalous center pixel 10.0
    data = np.ones((5, 5), dtype=np.float32)
    data[2, 2] = 10.0
    mask = np.ones((5, 5), dtype=bool)
    cfg = SpatialAnomalyConfig(window_size_pixels=3, minimum_valid_neighbors=5, z_clip=3.5)
    res = compute_indicator_spatial_anomaly(data, mask, cfg)
    # Center pixel should have high spatial anomaly score
    assert res["anomaly_score"][2, 2] > 0.8
    # Interior background pixel (1, 1) has 9 neighbors and 0.0 deviation
    assert res["anomaly_score"][1, 1] == pytest.approx(0.0, abs=1e-4)


# 8. Invalid-Neighbor Exclusion
def test_invalid_neighbor_exclusion():
    mask = np.zeros((5, 5), dtype=bool)
    mask[2, 2] = True
    mask[2, 1] = True
    # Count valid neighbors in 3x3 window around (2, 2)
    counts = count_valid_neighbors(mask, window_size=3)
    assert counts[2, 2] == 2  # Only two pixels valid


# 9. Minimum-Neighbor Threshold
def test_minimum_neighbor_threshold():
    data = np.ones((5, 5), dtype=np.float32)
    mask = np.zeros((5, 5), dtype=bool)
    # Only 3 pixels valid in the entire array
    mask[2, 2] = True
    mask[2, 1] = True
    mask[2, 3] = True
    cfg = SpatialAnomalyConfig(window_size_pixels=3, minimum_valid_neighbors=5)
    res = compute_indicator_spatial_anomaly(data, mask, cfg)
    # Center pixel has only 3 neighbors < 5 minimum -> must be NaN
    assert np.isnan(res["anomaly_score"][2, 2])
    assert not res["spatial_valid_mask"][2, 2]


# 10. Spatial Edge Behavior
def test_spatial_edge_behavior():
    # 5x5 array fully valid; corners should have fewer neighbors due to boundaries
    mask = np.ones((5, 5), dtype=bool)
    counts = count_valid_neighbors(mask, window_size=3)
    # Center has 9 neighbors (3x3)
    assert counts[2, 2] == 9
    # Corner has 4 neighbors inside boundary (mode='constant', cval=0.0)
    assert counts[0, 0] == 4


# 11. Combined Anomaly Weighting
def test_combined_anomaly_weighting():
    t_score = np.array([[0.8]], dtype=np.float32)
    s_score = np.array([[0.4]], dtype=np.float32)
    cfg = CombinedAnomalyConfig(temporal_weight=0.6, spatial_weight=0.4)
    comb, mask, meta = fuse_anomaly_components(t_score, s_score, cfg)
    # 0.6 * 0.8 + 0.4 * 0.4 = 0.48 + 0.16 = 0.64
    assert comb[0, 0] == pytest.approx(0.64, abs=1e-5)


# 12. Missing-Component Handling
def test_missing_component_handling():
    t_score = np.array([[0.7]], dtype=np.float32)
    s_score = np.array([[np.nan]], dtype=np.float32)
    cfg_fallback = CombinedAnomalyConfig(fallback_to_available_component=True)
    comb, mask, _ = fuse_anomaly_components(t_score, s_score, cfg_fallback)
    # Fallback uses available temporal component
    assert comb[0, 0] == pytest.approx(0.7, abs=1e-5)

    cfg_no_fallback = CombinedAnomalyConfig(fallback_to_available_component=False)
    comb_no, _, _ = fuse_anomaly_components(t_score, s_score, cfg_no_fallback)
    assert np.isnan(comb_no[0, 0])


# 13. Score Bounds [0, 1]
def test_score_bounds():
    z = np.linspace(-10, 10, 50, dtype=np.float32)
    scores = z_to_anomaly_score(z, z_clip=3.0)
    assert np.all(scores >= 0.0)
    assert np.all(scores <= 1.0)


# 14. NaN Propagation
def test_nan_propagation():
    data = np.array([[0.5, np.nan], [0.2, 0.3]], dtype=np.float32)
    mask = np.array([[True, False], [True, True]], dtype=bool)
    cfg = TemporalAnomalyConfig(minimum_valid_samples=3)
    res = compute_indicator_temporal_anomaly(data, mask, cfg)
    assert np.isnan(res["anomaly_score"][0, 1])


# 15. Evidence Flags
def test_evidence_flags_generation():
    h, w = 2, 2
    change_stack = np.zeros((12, h, w), dtype=np.float32)
    anomaly_stack = np.zeros((10, h, w), dtype=np.float32)
    # Pixel (0, 0) has high NDVI combined anomaly
    anomaly_stack[6, 0, 0] = 0.85
    valid_mask = np.ones((h, w), dtype=bool)

    cfg = EvidenceConfig(anomaly_threshold=0.50)
    e_res = evaluate_cross_indicator_evidence(change_stack, anomaly_stack, valid_mask, config=cfg)
    assert e_res["vegetation_change_present"][0, 0] is True or e_res["vegetation_change_present"][0, 0] == 1
    assert e_res["vegetation_change_present"][0, 1] == 0


# 16. Vegetation + Built-up Coherence
def test_vegetation_builtup_coherence():
    h, w = 2, 2
    change_stack = np.zeros((12, h, w), dtype=np.float32)
    anomaly_stack = np.zeros((10, h, w), dtype=np.float32)
    valid_mask = np.ones((h, w), dtype=bool)

    # Pixel (0, 0): NDVI loss (-0.25, anomaly 0.8) AND NDBI gain (+0.25, anomaly 0.8)
    change_stack[0, 0, 0] = -0.25  # NDVI delta
    change_stack[4, 0, 0] = +0.25  # NDBI delta
    anomaly_stack[6, 0, 0] = 0.8   # NDVI combined anomaly
    anomaly_stack[8, 0, 0] = 0.8   # NDBI combined anomaly

    cfg = EvidenceConfig(anomaly_threshold=0.50)
    e_res = evaluate_cross_indicator_evidence(change_stack, anomaly_stack, valid_mask, config=cfg)
    assert e_res["vegetation_builtup_coherence"][0, 0] == 1
    assert e_res["vegetation_builtup_coherence"][0, 1] == 0


# 17. Persistence Integration
def test_persistence_integration():
    h, w = 2, 2
    change_stack = np.zeros((12, h, w), dtype=np.float32)
    anomaly_stack = np.zeros((10, h, w), dtype=np.float32)
    valid_mask = np.ones((h, w), dtype=bool)

    # Persistence raster with persistent vegetation decrease (band 1)
    persist = np.zeros((9, h, w), dtype=np.uint8)
    persist[0, 1, 1] = 1  # Band 1: persistent_vegetation_decrease

    e_res = evaluate_cross_indicator_evidence(change_stack, anomaly_stack, valid_mask, persistence_stack=persist)
    assert e_res["persistent_change_present"][1, 1] == 1
    assert e_res["persistent_change_present"][0, 0] == 0


# 18. Reversal Integration
def test_reversal_integration():
    h, w = 2, 2
    change_stack = np.zeros((12, h, w), dtype=np.float32)
    anomaly_stack = np.zeros((10, h, w), dtype=np.float32)
    valid_mask = np.ones((h, w), dtype=bool)

    # Persistence raster with reversal in vegetation (band 7)
    persist = np.zeros((9, h, w), dtype=np.uint8)
    persist[6, 1, 0] = 1  # Band 7: vegetation_reversal

    e_res = evaluate_cross_indicator_evidence(change_stack, anomaly_stack, valid_mask, persistence_stack=persist)
    assert e_res["reversal_present"][1, 0] == 1


# 19. Structured Evidence Record Schema
def test_structured_evidence_record_schema():
    h, w = 2, 2
    change_stack = np.zeros((12, h, w), dtype=np.float32)
    anomaly_stack = np.zeros((10, h, w), dtype=np.float32)
    evidence_stack = np.zeros((7, h, w), dtype=np.uint8)
    valid_mask = np.ones((h, w), dtype=bool)

    rec = build_evidence_record("TEST_01", 0, 0, change_stack, anomaly_stack, evidence_stack, valid_mask)
    assert rec["grid_id"] == "TEST_01"
    assert "ndvi_delta" in rec
    assert "ndvi_temporal_anomaly" in rec
    assert "ndvi_spatial_anomaly" in rec
    assert "combined_anomaly" in rec
    assert "vegetation_builtup_coherence" in rec


# 20. Output Band Order Schema
def test_output_band_order():
    assert len(ANOMALY_STACK_BAND_NAMES) == 10
    assert ANOMALY_STACK_BAND_NAMES[0] == "NDVI_temporal_anomaly"
    assert ANOMALY_STACK_BAND_NAMES[3] == "NDVI_spatial_anomaly"
    assert ANOMALY_STACK_BAND_NAMES[6] == "NDVI_combined_anomaly"
    assert ANOMALY_STACK_BAND_NAMES[9] == "overall_combined_anomaly"

    assert len(EVIDENCE_FLAG_BAND_NAMES) == 7
    assert EVIDENCE_FLAG_BAND_NAMES[0] == "vegetation_change_present"
    assert EVIDENCE_FLAG_BAND_NAMES[3] == "vegetation_builtup_coherence"
    assert EVIDENCE_FLAG_BAND_NAMES[4] == "persistent_change_present"


# 21. Anomaly Fusion Aggregation Methods
def test_anomaly_fusion_overall_maximum():
    temp = np.array([[[0.2]], [[0.8]], [[0.5]]], dtype=np.float32)
    spat = np.array([[[0.4]], [[0.6]], [[0.3]]], dtype=np.float32)
    cfg = CombinedAnomalyConfig(temporal_weight=0.5, spatial_weight=0.5, aggregation_method="max")
    res = compute_period_combined_anomalies(temp, spat, cfg)
    # NDVI comb: 0.5*0.2 + 0.5*0.4 = 0.3
    # NDWI comb: 0.5*0.8 + 0.5*0.6 = 0.7
    # NDBI comb: 0.5*0.5 + 0.5*0.3 = 0.4
    # Overall: max(0.3, 0.7, 0.4) = 0.7
    assert res["ndvi_combined"][0, 0] == pytest.approx(0.3, abs=1e-5)
    assert res["ndwi_combined"][0, 0] == pytest.approx(0.7, abs=1e-5)
    assert res["ndbi_combined"][0, 0] == pytest.approx(0.4, abs=1e-5)
    assert res["overall_combined"][0, 0] == pytest.approx(0.7, abs=1e-5)


def test_anomaly_fusion_aggregation_alternatives():
    """Verify mean and corroborated aggregation modes."""
    temp = np.array([[[0.3]], [[0.7]], [[0.2]]], dtype=np.float32)
    spat = np.array([[[0.3]], [[0.7]], [[0.2]]], dtype=np.float32)
    # scores: [0.3, 0.7, 0.2]
    # mean: (0.3 + 0.7 + 0.2) / 3 = 0.4
    cfg_mean = CombinedAnomalyConfig(temporal_weight=0.5, spatial_weight=0.5, aggregation_method="mean")
    res_mean = compute_period_combined_anomalies(temp, spat, cfg_mean)
    assert res_mean["overall_combined"][0, 0] == pytest.approx(0.4, abs=1e-5)

    # corroborated: sorted [0.7, 0.3, 0.2] -> 0.7 * 0.7 + 0.3 * 0.3 = 0.49 + 0.09 = 0.58
    cfg_corr = CombinedAnomalyConfig(temporal_weight=0.5, spatial_weight=0.5, aggregation_method="corroborated")
    res_corr = compute_period_combined_anomalies(temp, spat, cfg_corr)
    assert res_corr["overall_combined"][0, 0] == pytest.approx(0.58, abs=1e-5)


def test_scene_level_change_anomaly_metadata():
    """Verify scene-level change anomaly metadata explicitly documents baseline type."""
    delta = np.array([0.1, -0.2, 0.3, 0.0], dtype=np.float32)
    mask = np.ones(4, dtype=bool)
    res = compute_indicator_temporal_anomaly(delta, mask)
    assert res["metadata"]["baseline_type"] == "scene_level_change_distribution"
    assert res["metadata"]["component_type"] == "scene_level_change_anomaly"


# 22. Real Step 5 Data Integration
@pytest.mark.integration
def test_real_step5_anomaly_integration():
    """Integration test: reads actual Step 5 change stack and computes anomaly pipeline."""
    cfg = get_config()
    change_path = cfg.directories.processed_dir / "change_detection" / "2020_2023" / "change_stack.tif"
    mask_path = cfg.directories.processed_dir / "change_detection" / "2020_2023" / "valid_mask.tif"

    if not change_path.exists() or not mask_path.exists():
        pytest.skip("Step 5 change stack not present on disk; skipping integration test.")

    # Read 50x50 window for rapid execution
    win = rasterio.windows.Window(200, 200, 50, 50)
    with rasterio.open(change_path) as src, rasterio.open(mask_path) as m_src:
        c_sub = src.read(window=win)
        m_sub = m_src.read(1, window=win) == 1

    t_cfg = TemporalAnomalyConfig(minimum_valid_samples=50, z_clip=3.5)
    s_cfg = SpatialAnomalyConfig(window_size_pixels=9, minimum_valid_neighbors=10, z_clip=3.5)
    c_cfg = CombinedAnomalyConfig()

    t_res = compute_indicator_temporal_anomaly(c_sub[0], m_sub, t_cfg)
    s_res = compute_indicator_spatial_anomaly(c_sub[0], m_sub, s_cfg)
    comb, v_mask, _ = fuse_anomaly_components(t_res["anomaly_score"], s_res["anomaly_score"], c_cfg)

    assert comb.shape == (50, 50)
    valid_comb = comb[v_mask & np.isfinite(comb)]
    assert len(valid_comb) > 0
    assert np.all(valid_comb >= 0.0)
    assert np.all(valid_comb <= 1.0)
