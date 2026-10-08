"""
UrbanPulse - Integration Data Validator (Step 8).

Validates API JSON, GeoJSON, and City Summary artifacts against strict contracts:
- Valid bounding coordinates in study area [78.35, 78.55] E, [17.35, 17.50] N
- No NaN / null in numeric fields
- Bounded scores in [0.0, 1.0]
- Consistent priority levels and thresholds
- Monotonic descending rank ordering
- Non-empty reason codes for HIGH priority
- Valid GeoJSON geometries
- Unique grid_id per period
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

VALID_PERIODS = {"2020_2023", "2023_2026", "2020_2026"}
VALID_PRIORITY_LEVELS = {"HIGH", "MEDIUM", "LOW"}
VALID_RECOMMENDATIONS = {
    "FIELD_VERIFICATION_RECOMMENDED",
    "MONITOR_AND_REVIEW",
    "ROUTINE_OBSERVATION",
}

# Hyderabad Study Area Bounding Box [min_lon, min_lat, max_lon, max_lat]
BBOX_LON_MIN = 78.349
BBOX_LON_MAX = 78.551
BBOX_LAT_MIN = 17.349
BBOX_LAT_MAX = 17.501


class ValidationError(Exception):
    """Raised when an API integration artifact violates contract rules."""
    pass


def validate_hotspot_record(record: Dict[str, Any], high_threshold: float = 0.70, medium_threshold: float = 0.45) -> None:
    """
    Validate a single HotspotRecord dictionary against contract specifications.
    """
    # 1. Top-level required keys
    required_keys = {
        "rank",
        "grid_id",
        "period",
        "latitude",
        "longitude",
        "priority",
        "reasons",
        "anomaly",
        "evidence",
        "change",
        "why_flagged",
    }
    missing = required_keys - set(record.keys())
    if missing:
        raise ValidationError(f"Hotspot record missing required keys: {missing}")

    # 2. Period
    period = record["period"]
    if period not in VALID_PERIODS:
        raise ValidationError(f"Invalid period '{period}' in record {record.get('grid_id')}")

    # 3. Coordinates
    lat = float(record["latitude"])
    lon = float(record["longitude"])
    if not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX):
        raise ValidationError(f"Latitude {lat} outside study area bounds [{BBOX_LAT_MIN}, {BBOX_LAT_MAX}]")
    if not (BBOX_LON_MIN <= lon <= BBOX_LON_MAX):
        raise ValidationError(f"Longitude {lon} outside study area bounds [{BBOX_LON_MIN}, {BBOX_LON_MAX}]")

    # 4. Priority
    prio = record["priority"]
    score = float(prio.get("score", -1.0))
    level = prio.get("level", "")
    rec = prio.get("recommendation", "")

    if math.isnan(score) or not (0.0 <= score <= 1.0):
        raise ValidationError(f"Priority score {score} out of bounds [0.0, 1.0]")
    if level not in VALID_PRIORITY_LEVELS:
        raise ValidationError(f"Invalid priority level '{level}'")
    if rec not in VALID_RECOMMENDATIONS:
        raise ValidationError(f"Invalid recommendation '{rec}'")

    # Threshold consistency (with 1e-4 boundary tolerance for 4-decimal rounded values)
    eps = 1e-4
    if score >= high_threshold + eps and level != "HIGH":
        raise ValidationError(f"Score {score} >= {high_threshold} but level is {level}")
    elif (medium_threshold + eps <= score < high_threshold - eps) and level != "MEDIUM":
        raise ValidationError(f"Score {score} in [{medium_threshold}, {high_threshold}) but level is {level}")
    elif (score < medium_threshold - eps) and level != "LOW":
        raise ValidationError(f"Score {score} < {medium_threshold} but level is {level}")

    # 5. Reason codes
    reasons = record.get("reasons", [])
    if not isinstance(reasons, list):
        raise ValidationError(f"Reasons must be a list, got {type(reasons)}")
    if level == "HIGH" and len(reasons) == 0:
        raise ValidationError(f"HIGH priority hotspot {record.get('grid_id')} has empty reasons list")

    # 6. Anomaly block
    anom = record["anomaly"]
    for k in ["overall", "ndvi", "ndwi", "ndbi"]:
        val = anom.get(k)
        if val is None or math.isnan(val) or not (0.0 <= val <= 1.0):
            raise ValidationError(f"Anomaly signal {k}={val} is missing, NaN, or out of [0, 1]")

    # 7. Evidence block
    ev = record["evidence"]
    for k in ["vegetation_loss", "water_change", "builtup_change", "veg_builtup_coherence", "persistent_change"]:
        if not isinstance(ev.get(k), bool):
            raise ValidationError(f"Evidence flag {k} must be boolean, got {ev.get(k)}")

    # 8. Change block
    ch = record["change"]
    for k in ["ndvi_delta", "ndwi_delta", "ndbi_delta"]:
        val = ch.get(k)
        if val is None or math.isnan(val):
            raise ValidationError(f"Change signal {k} is NaN or missing")

    # 9. Why flagged block
    wf = record["why_flagged"]
    if not wf.get("headline"):
        raise ValidationError("Why flagged headline is missing or empty")
    factors = wf.get("factors", [])
    if len(factors) != len(reasons):
        raise ValidationError(f"Why flagged factors count ({len(factors)}) mismatch with reasons count ({len(reasons)})")


def validate_hotspots_collection(
    records: List[Dict[str, Any]],
    high_threshold: float = 0.70,
    medium_threshold: float = 0.45,
) -> None:
    """
    Validate a list of HotspotRecord dictionaries including rank monotonicity and ID uniqueness.
    """
    if not records:
        raise ValidationError("Hotspots collection is empty")

    seen_ids = set()
    prev_score = float("inf")
    prev_rank = 0

    for idx, r in enumerate(records):
        grid_id = r.get("grid_id")
        if not grid_id or grid_id in seen_ids:
            raise ValidationError(f"Duplicate or missing grid_id '{grid_id}' at index {idx}")
        seen_ids.add(grid_id)

        validate_hotspot_record(r, high_threshold, medium_threshold)

        rank = r.get("rank")
        if rank != prev_rank + 1:
            raise ValidationError(f"Rank sequence error: expected {prev_rank + 1}, got {rank}")
        prev_rank = rank

        score = float(r["priority"]["score"])
        # Monotonic descending (or equal in rare tie)
        if score > prev_score + 1e-6:
            raise ValidationError(f"Ranking not descending: rank {rank} score {score} > rank {rank-1} score {prev_score}")
        prev_score = score


def validate_geojson_collection(geojson: Dict[str, Any]) -> None:
    """
    Validate a GeoJSON FeatureCollection dictionary.
    """
    if geojson.get("type") != "FeatureCollection":
        raise ValidationError(f"Expected GeoJSON type 'FeatureCollection', got {geojson.get('type')}")
    if geojson.get("period") not in VALID_PERIODS:
        raise ValidationError(f"Invalid GeoJSON period '{geojson.get('period')}'")

    features = geojson.get("features", [])
    if not features:
        raise ValidationError("GeoJSON has zero features")

    for idx, f in enumerate(features):
        if f.get("type") != "Feature":
            raise ValidationError(f"Feature at index {idx} has invalid type: {f.get('type')}")
        geom = f.get("geometry", {})
        if geom.get("type") != "Point":
            raise ValidationError(f"Geometry at index {idx} must be 'Point', got {geom.get('type')}")
        coords = geom.get("coordinates", [])
        if len(coords) != 2:
            raise ValidationError(f"Point coordinates must be [lon, lat], got {coords}")
        lon, lat = coords
        if not (BBOX_LON_MIN <= lon <= BBOX_LON_MAX) or not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX):
            raise ValidationError(f"Feature coordinates [{lon}, {lat}] outside AOI")

        props = f.get("properties", {})
        for req in ["grid_id", "rank", "priority_score", "priority_level", "period"]:
            if req not in props:
                raise ValidationError(f"Feature properties missing required key '{req}'")


def validate_city_summary(summary: Dict[str, Any]) -> None:
    """
    Validate a CitySummary dictionary.
    """
    for req in ["period", "total_cells", "high_priority", "medium_priority", "low_priority", "score_median", "score_p95", "top_hotspots"]:
        if req not in summary:
            raise ValidationError(f"CitySummary missing key '{req}'")

    if summary["period"] not in VALID_PERIODS:
        raise ValidationError(f"Invalid period '{summary['period']}' in summary")

    total = summary["total_cells"]
    high = summary["high_priority"]
    med = summary["medium_priority"]
    low = summary["low_priority"]

    if total <= 0:
        raise ValidationError(f"Invalid total_cells {total}")
    if high + med + low != total:
        raise ValidationError(f"Priority count sum ({high} + {med} + {low} = {high+med+low}) does not match total_cells ({total})")
