"""
Unit and integration tests for UrbanPulse Priority Engine (Step 7).

Covers:
1. Score normalization in [0.0, 1.0]
2. Weighted priority calculation accuracy
3. Evidence strength component and reversal dampening
4. Persistence contribution
5. Machine-readable reason-code generation
6. Priority threshold classification (HIGH, MEDIUM, LOW)
7. Deterministic ranking order descending by score
8. NaN and invalid mask propagation
9. All-zero / neutral input handling
10. Deterministic output reproducibility
11. Configuration validation and weight handling
12. End-to-end integration test with real Step 6 outputs
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from config.settings import (
    AppConfig,
    PriorityConfig,
    PriorityThresholdsConfig,
    PriorityWeightsConfig,
    get_config,
)
from geospatial.grid import GridCell, generate_study_grid
from geospatial.priority import (
    aggregate_grid_cell_signals,
    build_why_flagged_record,
    calculate_component_scores,
    calculate_priority_score,
    classify_priority_level,
    generate_reason_codes,
    process_period_priority,
    rank_and_extract_hotspots,
)


def _create_synthetic_inputs(H: int = 10, W: int = 10):
    """Helper creating aligned synthetic arrays matching Step 5/6 shapes."""
    change_stack = np.zeros((12, H, W), dtype=np.float32)
    # 0: NDVI delta, 1: abs NDVI, 2: NDWI delta, 3: abs NDWI, 4: NDBI delta, 5: abs NDBI
    change_stack[0] = -0.30  # Veg loss
    change_stack[1] = 0.30
    change_stack[2] = 0.05
    change_stack[3] = 0.05
    change_stack[4] = 0.25   # Built-up increase
    change_stack[5] = 0.25

    anomaly_stack = np.zeros((10, H, W), dtype=np.float32)
    # 3: NDVI spatial, 4: NDWI spatial, 5: NDBI spatial, 9: overall combined
    anomaly_stack[3] = 0.65
    anomaly_stack[4] = 0.10
    anomaly_stack[5] = 0.70
    anomaly_stack[9] = 0.85  # High overall anomaly

    evidence_stack = np.zeros((7, H, W), dtype=np.uint8)
    # 0: veg change, 1: water change, 2: builtup signal, 3: veg-built coherence, 4: persist, 5: reversal
    evidence_stack[0] = 1
    evidence_stack[1] = 0
    evidence_stack[2] = 1
    evidence_stack[3] = 1  # Coherence present
    evidence_stack[4] = 1  # Persistent change
    evidence_stack[5] = 0  # No reversal

    valid_mask = np.ones((H, W), dtype=bool)

    return change_stack, anomaly_stack, evidence_stack, valid_mask


def test_score_normalization():
    """Verify all 5 components and the final priority score are strictly in [0.0, 1.0]."""
    change, anomaly, evidence, mask = _create_synthetic_inputs(20, 20)
    # Inject extreme out-of-range values in raw inputs
    anomaly[9] = 2.5
    change[1] = 1.8
    change[5] = 2.0

    comps = calculate_component_scores(change, anomaly, evidence, mask)
    for name, arr in comps.items():
        finite_vals = arr[mask & np.isfinite(arr)]
        assert np.all(finite_vals >= 0.0), f"Component {name} has negative values"
        assert np.all(finite_vals <= 1.0), f"Component {name} exceeds 1.0"

    score = calculate_priority_score(comps, valid_mask=mask)
    score_vals = score[mask & np.isfinite(score)]
    assert np.all(score_vals >= 0.0)
    assert np.all(score_vals <= 1.0)


def test_weighted_priority_calculation():
    """Verify mathematically exact weighted combination."""
    H, W = 5, 5
    mask = np.ones((H, W), dtype=bool)
    comps = {
        "anomaly": np.full((H, W), 0.80, dtype=np.float32),
        "evidence": np.full((H, W), 0.60, dtype=np.float32),
        "persistence": np.full((H, W), 1.00, dtype=np.float32),
        "magnitude": np.full((H, W), 0.50, dtype=np.float32),
        "spatial_context": np.full((H, W), 0.70, dtype=np.float32),
    }
    weights = PriorityWeightsConfig(
        anomaly=0.35,
        evidence=0.25,
        persistence=0.20,
        magnitude=0.10,
        spatial_context=0.10,
    )
    score = calculate_priority_score(comps, weights=weights, valid_mask=mask)
    expected = 0.35 * 0.80 + 0.25 * 0.60 + 0.20 * 1.00 + 0.10 * 0.50 + 0.10 * 0.70
    assert np.allclose(score[mask], expected, atol=1e-5)


def test_evidence_contribution_and_reversal_dampening():
    """Verify coherence boosts evidence and reversal dampens evidence score."""
    change, anomaly, evidence, mask = _create_synthetic_inputs(5, 5)

    # Base case: coherence = 1, reversal = 0
    comps_coherent = calculate_component_scores(change, anomaly, evidence, mask)

    # Non-coherent case: coherence = 0
    evidence_incoherent = evidence.copy()
    evidence_incoherent[3] = 0
    comps_incoherent = calculate_component_scores(change, anomaly, evidence_incoherent, mask)

    # Reversal case: coherence = 1, reversal = 1
    evidence_reversed = evidence.copy()
    evidence_reversed[5] = 1
    comps_reversed = calculate_component_scores(change, anomaly, evidence_reversed, mask)

    # Coherent evidence must be higher than incoherent
    assert np.mean(comps_coherent["evidence"]) > np.mean(comps_incoherent["evidence"])

    # Reversal evidence must be dampened compared to non-reversed
    assert np.mean(comps_coherent["evidence"]) > np.mean(comps_reversed["evidence"])


def test_persistence_contribution():
    """Verify persistence flag adds directly to priority score according to weight."""
    change, anomaly, evidence, mask = _create_synthetic_inputs(5, 5)
    weights = PriorityWeightsConfig(persistence=0.20)

    # Case 1: with persistence
    comps_p = calculate_component_scores(change, anomaly, evidence, mask)
    score_p = calculate_priority_score(comps_p, weights=weights, valid_mask=mask)

    # Case 2: without persistence
    evidence_no_p = evidence.copy()
    evidence_no_p[4] = 0
    comps_no_p = calculate_component_scores(change, anomaly, evidence_no_p, mask)
    score_no_p = calculate_priority_score(comps_no_p, weights=weights, valid_mask=mask)

    diff = np.mean(score_p) - np.mean(score_no_p)
    assert np.isclose(diff, 0.20, atol=1e-4)


def test_reason_code_generation():
    """Verify machine-readable reason codes accurately reflect observed signals."""
    codes = generate_reason_codes(
        ndvi_delta=-0.35,
        ndwi_delta=0.02,
        ndbi_delta=0.28,
        max_delta=0.35,
        anomaly_score=0.82,
        spatial_score=0.68,
        veg_builtup_coherence=True,
        persistent=True,
        reversal=False,
    )

    expected = [
        "HIGH_SCENE_ANOMALY",
        "SPATIAL_ANOMALY",
        "VEG_BUILTUP_COHERENCE",
        "VEGETATION_LOSS",
        "BUILTUP_SENSITIVE_CHANGE",
        "PERSISTENT_CHANGE",
        "STRONG_CHANGE_MAGNITUDE",
    ]
    for exp in expected:
        assert exp in codes

    # Test reversal code
    codes_rev = generate_reason_codes(
        ndvi_delta=0.0,
        ndwi_delta=0.0,
        ndbi_delta=0.0,
        max_delta=0.0,
        anomaly_score=0.1,
        spatial_score=0.1,
        veg_builtup_coherence=False,
        persistent=False,
        reversal=True,
    )
    assert "CYCLICAL_REVERSAL_DAMPENED" in codes_rev


def test_priority_thresholds():
    """Verify classification into HIGH, MEDIUM, LOW, and INVALID."""
    scores = np.array([[np.nan, 0.20], [0.55, 0.85]], dtype=np.float32)
    mask = np.array([[True, True], [True, True]], dtype=bool)
    thresholds = PriorityThresholdsConfig(high=0.70, medium=0.45)

    levels = classify_priority_level(scores, thresholds=thresholds, valid_mask=mask)

    assert levels[0, 0] == 0  # INVALID (NaN)
    assert levels[0, 1] == 1  # LOW (< 0.45)
    assert levels[1, 0] == 2  # MEDIUM (0.45 - 0.70)
    assert levels[1, 1] == 3  # HIGH (>= 0.70)


def test_ranking_order():
    """Verify grid cells are ranked descending by priority score."""
    H, W = 10, 10
    mask = np.ones((H, W), dtype=bool)
    # Cell 1 has score 0.3, Cell 2 has score 0.8
    p_score = np.full((H, W), 0.30, dtype=np.float32)
    p_score[:, 5:] = 0.80

    comps = {
        k: np.full((H, W), 0.5, dtype=np.float32)
        for k in ["anomaly", "evidence", "persistence", "magnitude", "spatial_context"]
    }
    change = np.zeros((12, H, W), dtype=np.float32)
    anomaly = np.zeros((10, H, W), dtype=np.float32)
    evidence = np.zeros((7, H, W), dtype=np.uint8)

    cell1 = GridCell(
        grid_id="HYD_0001",
        cell_index=1,
        grid_row=0,
        grid_col=0,
        pixel_row_min=0,
        pixel_row_max=10,
        pixel_col_min=0,
        pixel_col_max=5,
        minx=0.0,
        miny=0.0,
        maxx=500.0,
        maxy=1000.0,
        centroid_x=250.0,
        centroid_y=500.0,
        latitude=17.40,
        longitude=78.40,
    )
    cell2 = GridCell(
        grid_id="HYD_0002",
        cell_index=2,
        grid_row=0,
        grid_col=1,
        pixel_row_min=0,
        pixel_row_max=10,
        pixel_col_min=5,
        pixel_col_max=10,
        minx=500.0,
        miny=0.0,
        maxx=1000.0,
        maxy=1000.0,
        centroid_x=750.0,
        centroid_y=500.0,
        latitude=17.40,
        longitude=78.45,
    )

    ranked, diags = rank_and_extract_hotspots(
        grid_cells=[cell1, cell2],
        priority_score=p_score,
        components=comps,
        change_stack=change,
        anomaly_stack=anomaly,
        evidence_stack=evidence,
        valid_mask=mask,
    )

    assert len(ranked) == 2
    assert ranked[0]["grid_id"] == "HYD_0002"
    assert ranked[0]["rank"] == 1
    assert ranked[0]["priority_level"] == "HIGH"
    assert ranked[1]["grid_id"] == "HYD_0001"
    assert ranked[1]["rank"] == 2
    assert ranked[1]["priority_level"] == "LOW"


def test_nan_handling():
    """Verify NaN inputs strictly produce NaN priority score and 0 priority level."""
    change, anomaly, evidence, mask = _create_synthetic_inputs(5, 5)
    # Mask out top row
    mask[0, :] = False
    anomaly[9, 1, 1] = np.nan

    comps = calculate_component_scores(change, anomaly, evidence, mask)
    score = calculate_priority_score(comps, valid_mask=mask)
    levels = classify_priority_level(score, valid_mask=mask)

    assert np.all(np.isnan(score[0, :]))
    assert np.all(levels[0, :] == 0)
    assert np.isnan(score[1, 1])
    assert levels[1, 1] == 0


def test_all_zero_neutral_input():
    """Verify all-zero neutral input produces score 0.0 and LOW priority without false alarms."""
    H, W = 5, 5
    change = np.zeros((12, H, W), dtype=np.float32)
    anomaly = np.zeros((10, H, W), dtype=np.float32)
    evidence = np.zeros((7, H, W), dtype=np.uint8)
    mask = np.ones((H, W), dtype=bool)

    comps = calculate_component_scores(change, anomaly, evidence, mask)
    score = calculate_priority_score(comps, valid_mask=mask)
    levels = classify_priority_level(score, valid_mask=mask)

    assert np.allclose(score[mask], 0.0)
    assert np.all(levels[mask] == 1)  # LOW priority


def test_deterministic_output():
    """Verify repeated execution on identical inputs yields bitwise identical outputs."""
    change, anomaly, evidence, mask = _create_synthetic_inputs(10, 10)
    c1 = calculate_component_scores(change, anomaly, evidence, mask)
    s1 = calculate_priority_score(c1, valid_mask=mask)
    l1 = classify_priority_level(s1, valid_mask=mask)

    c2 = calculate_component_scores(change, anomaly, evidence, mask)
    s2 = calculate_priority_score(c2, valid_mask=mask)
    l2 = classify_priority_level(s2, valid_mask=mask)

    assert np.array_equal(s1, s2, equal_nan=True)
    assert np.array_equal(l1, l2)


def test_configuration_validation():
    """Verify configuration loading and weight normalization."""
    cfg = get_config()
    assert cfg.priority.enabled is True
    assert 0.0 < cfg.priority.weights.anomaly <= 1.0
    assert 0.0 < cfg.priority.weights.evidence <= 1.0
    assert 0.0 < cfg.priority.weights.persistence <= 1.0
    assert 0.0 < cfg.priority.weights.magnitude <= 1.0
    assert 0.0 < cfg.priority.weights.spatial_context <= 1.0

    w_sum = (
        cfg.priority.weights.anomaly
        + cfg.priority.weights.evidence
        + cfg.priority.weights.persistence
        + cfg.priority.weights.magnitude
        + cfg.priority.weights.spatial_context
    )
    assert np.isclose(w_sum, 1.0, atol=1e-5)
    assert cfg.priority.thresholds.high > cfg.priority.thresholds.medium


def test_real_step6_priority_integration(tmp_path):
    """
    Integration test running priority scoring on real Step 5/6 outputs
    for the 2020_2023 period and validating outputs.
    """
    cfg = get_config()
    processed_dir = cfg.directories.processed_dir

    change_dir = processed_dir / "change_detection" / "2020_2023"
    anomaly_dir = processed_dir / "anomaly_detection" / "combined" / "2020_2023"
    evidence_dir = processed_dir / "anomaly_detection" / "evidence" / "2020_2023"

    if not change_dir.exists() or not anomaly_dir.exists() or not evidence_dir.exists():
        pytest.skip("Step 5/6 real processed rasters not available")

    out_dir = tmp_path / "priority_test_output"

    res = process_period_priority(
        period="2020_2023",
        change_dir=change_dir,
        anomaly_dir=anomaly_dir,
        evidence_dir=evidence_dir,
        output_dir=out_dir,
        config=cfg,
    )

    # 1. Check return structure
    assert "diagnostics" in res
    assert "ranked_records" in res
    assert "raster_files" in res
    assert "table_files" in res

    # 2. Check rasters exist and match dimensions
    score_tif = Path(res["raster_files"]["priority_score"])
    level_tif = Path(res["raster_files"]["priority_level"])
    assert score_tif.exists()
    assert level_tif.exists()

    with rasterio.open(score_tif) as src:
        assert src.count == 1
        assert src.dtypes[0] == "float32"
        s_data = src.read(1)
        valid_s = s_data[np.isfinite(s_data)]
        assert len(valid_s) > 0
        assert np.all(valid_s >= 0.0)
        assert np.all(valid_s <= 1.0)

    # 3. Check CSV and JSON tables exist
    csv_file = Path(res["table_files"]["csv"])
    json_file = Path(res["table_files"]["json"])
    top10_file = Path(res["table_files"]["top_10"])
    stats_file = Path(res["table_files"]["stats"])

    assert csv_file.exists()
    assert json_file.exists()
    assert top10_file.exists()
    assert stats_file.exists()

    with open(top10_file, encoding="utf-8") as f:
        top10 = json.load(f)
        assert len(top10) <= 10
        if len(top10) > 1:
            # Check descending sort
            assert top10[0]["priority_score"] >= top10[1]["priority_score"]
            assert top10[0]["recommendation"] in [
                "FIELD_VERIFICATION_RECOMMENDED",
                "MONITOR_AND_REVIEW",
                "ROUTINE_OBSERVATION",
            ]
