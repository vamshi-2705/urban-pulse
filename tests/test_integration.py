"""
Unit and integration tests for UrbanPulse API Contract & Export Layer (Step 8).

Validates:
1. HotspotRecord JSON schema and field integrity
2. CitySummary schema and priority count consistency
3. GeoJSON FeatureCollection syntax and Point geometry
4. Monotonic descending rank ordering
5. Coordinate validity within Hyderabad study area bounds
6. Score bounds in [0.0, 1.0] and absence of NaNs
7. Mandatory reason-code presence for HIGH priority hotspots
8. Period parameter handling (2020_2023, 2023_2026, 2020_2026)
9. Deterministic artifact export
10. Strict ValidationError triggering on contract violations
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.settings import get_config
from geospatial.integration import (
    CitySummary,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    HotspotAnomaly,
    HotspotChange,
    HotspotEvidence,
    HotspotPriority,
    HotspotRecord,
    ValidationError,
    WhyFlagged,
    WhyFlaggedFactor,
    build_geojson_collection,
    export_all_api_artifacts,
    export_period_api_artifacts,
    format_hotspot_record,
    generate_why_flagged,
    validate_city_summary,
    validate_geojson_collection,
    validate_hotspot_record,
    validate_hotspots_collection,
)


@pytest.fixture
def sample_raw_hotspot():
    """Returns a realistic raw hotspot record matching Step 7 output."""
    return {
        "grid_id": "HYD_1220",
        "priority_score": 0.82,
        "priority_level": "HIGH",
        "recommendation": "FIELD_VERIFICATION_RECOMMENDED",
        "reasons": [
            "HIGH_SCENE_ANOMALY",
            "SPATIAL_ANOMALY",
            "VEG_BUILTUP_COHERENCE",
            "PERSISTENT_CHANGE",
        ],
        "signals": {
            "overall_anomaly": 0.9639,
            "spatial_anomaly": 1.0,
            "ndvi_anomaly": 0.8929,
            "ndwi_anomaly": 0.9121,
            "ndbi_anomaly": 0.8823,
            "ndvi_delta": -0.5543,
            "ndwi_delta": 0.1043,
            "ndbi_delta": 0.2766,
            "evidence_strength": 0.2083,
            "persistence": 1.0,
            "veg_builtup_coherence": 1.0,
            "reversal": 1.0,
            "vegetation_change_present": True,
            "water_change_present": True,
            "builtup_signal_present": True,
        },
        "latitude": 17.372285,
        "longitude": 78.42256,
        "cell_index": 1220,
        "grid_row": 28,
        "grid_col": 15,
        "rank": 1,
    }


def test_format_hotspot_record(sample_raw_hotspot):
    """Verify raw Step 7 record correctly transforms into HotspotRecord schema."""
    hotspot = format_hotspot_record(sample_raw_hotspot, period="2020_2026")
    d = hotspot.to_dict()

    # Core identification
    assert d["rank"] == 1
    assert d["grid_id"] == "HYD_1220"
    assert d["period"] == "2020_2026"
    assert d["latitude"] == 17.372285
    assert d["longitude"] == 78.42256

    # Priority sub-object
    assert d["priority"]["score"] == 0.82
    assert d["priority"]["level"] == "HIGH"
    assert d["priority"]["recommendation"] == "FIELD_VERIFICATION_RECOMMENDED"

    # Signals
    assert d["anomaly"]["overall"] == 0.9639
    assert d["anomaly"]["spatial"] == 1.0
    assert d["evidence"]["veg_builtup_coherence"] is True
    assert d["evidence"]["persistent_change"] is True
    assert d["change"]["ndvi_delta"] == -0.5543

    # Why flagged
    assert d["why_flagged"]["headline"] == "Strong and persistent land-cover change"
    assert len(d["why_flagged"]["factors"]) == 4


def test_hotspot_schema_validation(sample_raw_hotspot):
    """Verify validator accepts valid records and catches errors."""
    hotspot = format_hotspot_record(sample_raw_hotspot, period="2020_2026").to_dict()
    # Must pass cleanly
    validate_hotspot_record(hotspot)

    # 1. Invalid coordinates
    bad_coords = dict(hotspot, latitude=18.5)
    with pytest.raises(ValidationError, match="Latitude .* outside"):
        validate_hotspot_record(bad_coords)

    # 2. Out of bounds score
    bad_score = dict(hotspot, priority={"score": 1.5, "level": "HIGH", "recommendation": "FIELD_VERIFICATION_RECOMMENDED"})
    with pytest.raises(ValidationError, match="Priority score .* out of bounds"):
        validate_hotspot_record(bad_score)

    # 3. HIGH priority without reasons
    no_reasons = dict(hotspot, reasons=[], why_flagged={"headline": "Test", "factors": []})
    with pytest.raises(ValidationError, match="HIGH priority hotspot .* empty reasons"):
        validate_hotspot_record(no_reasons)


def test_ranking_order_validation(sample_raw_hotspot):
    """Verify list validation requires monotonic descending ranks and scores."""
    h1 = format_hotspot_record(sample_raw_hotspot, period="2020_2026").to_dict()
    h2 = dict(
        h1,
        rank=2,
        grid_id="HYD_1221",
        priority={"score": 0.75, "level": "HIGH", "recommendation": "FIELD_VERIFICATION_RECOMMENDED"},
    )

    validate_hotspots_collection([h1, h2])

    # Rank error: non-descending score
    h2_bad = dict(h2, priority={"score": 0.95, "level": "HIGH", "recommendation": "FIELD_VERIFICATION_RECOMMENDED"})
    with pytest.raises(ValidationError, match="Ranking not descending"):
        validate_hotspots_collection([h1, h2_bad])

    # Rank index mismatch
    h2_bad_idx = dict(h2, rank=5)
    with pytest.raises(ValidationError, match="Rank sequence error"):
        validate_hotspots_collection([h1, h2_bad_idx])

    # Duplicate ID
    h2_dup = dict(h2, grid_id="HYD_1220")
    with pytest.raises(ValidationError, match="Duplicate or missing grid_id"):
        validate_hotspots_collection([h1, h2_dup])


def test_geojson_feature_collection(sample_raw_hotspot):
    """Verify GeoJSON FeatureCollection structure and Point geometry."""
    h = format_hotspot_record(sample_raw_hotspot, period="2020_2026")
    coll = build_geojson_collection([h], period="2020_2026").to_dict()

    validate_geojson_collection(coll)
    assert coll["type"] == "FeatureCollection"
    assert coll["period"] == "2020_2026"
    assert len(coll["features"]) == 1

    feat = coll["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    # Lon, Lat in GeoJSON
    assert feat["geometry"]["coordinates"] == [78.42256, 17.372285]
    assert feat["properties"]["grid_id"] == "HYD_1220"
    assert feat["properties"]["rank"] == 1


def test_city_summary_validation():
    """Verify CitySummary schema and count arithmetic consistency."""
    summary = CitySummary(
        period="2020_2026",
        total_cells=1462,
        high_priority=27,
        medium_priority=453,
        low_priority=982,
        score_median=0.4107,
        score_p95=0.6172,
        top_hotspots=[],
    ).to_dict()

    validate_city_summary(summary)

    # Inconsistent sum
    bad_sum = dict(summary, low_priority=500)
    with pytest.raises(ValidationError, match="does not match total_cells"):
        validate_city_summary(bad_sum)


def test_deterministic_export(sample_raw_hotspot):
    """Verify format transformation is 100% deterministic."""
    h1 = format_hotspot_record(sample_raw_hotspot, period="2020_2026").to_dict()
    h2 = format_hotspot_record(sample_raw_hotspot, period="2020_2026").to_dict()
    assert json.dumps(h1, sort_keys=True) == json.dumps(h2, sort_keys=True)


def test_real_exported_api_files():
    """
    Integration test verifying that the actual exported API files exist in
    data/outputs/api/ and pass all validation checks across all 3 periods.
    """
    cfg = get_config()
    api_dir = cfg.directories.outputs_dir / "api"
    periods = ["2020_2023", "2023_2026", "2020_2026"]

    for period in periods:
        hotspots_path = api_dir / f"hotspots_{period}.json"
        geojson_path = api_dir / f"hotspots_{period}.geojson"
        summary_path = api_dir / f"city_summary_{period}.json"

        assert hotspots_path.exists(), f"Missing {hotspots_path}"
        assert geojson_path.exists(), f"Missing {geojson_path}"
        assert summary_path.exists(), f"Missing {summary_path}"

        with open(hotspots_path, encoding="utf-8") as f:
            hotspots = json.load(f)
        with open(geojson_path, encoding="utf-8") as f:
            geojson = json.load(f)
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)

        validate_hotspots_collection(hotspots)
        validate_geojson_collection(geojson)
        validate_city_summary(summary)

        # Check Top convenience files
        for k in [10, 25, 50]:
            top_path = api_dir / f"top_{k}_{period}.json"
            assert top_path.exists()
            with open(top_path, encoding="utf-8") as f:
                top_data = json.load(f)
                assert len(top_data) == k
                assert top_data[0]["rank"] == 1
