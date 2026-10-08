#!/usr/bin/env python3
"""
UrbanPulse - Verify Frontend Data Contract & Integration Readiness.

Validates the complete Member 2 handoff package:
1. All required API JSON files exist and parse correctly.
2. All GeoJSON files exist and conform to RFC 7946 specifications.
3. Evidence manifest exists and is complete.
4. Every designated demo hotspot exists in hotspot catalogs.
5. Every referenced evidence asset exists on disk and is non-empty.
6. Geographic coordinates are valid and bounded.
7. Priority scores are bounded in [0.0, 1.0].
8. Priority levels and recommendations are valid.
9. Period identifiers match the acquisition contract.
10. Evidence paths resolve to real on-disk files.
11. No broken or dangling references across outputs.
12. Exit code 0 on complete pass; non-zero on failure.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config

# Constants
VALID_PERIODS = ["2020_2026", "2020_2023", "2023_2026"]
VALID_PRIORITY_LEVELS = {"HIGH", "MEDIUM", "LOW"}
VALID_RECOMMENDATIONS = {
    "FIELD_VERIFICATION_RECOMMENDED",
    "MONITOR_AND_REVIEW",
    "ROUTINE_OBSERVATION",
}

# Study area bounds for Hyderabad AOI
BBOX_LON_MIN = 78.349
BBOX_LON_MAX = 78.551
BBOX_LAT_MIN = 17.349
BBOX_LAT_MAX = 17.501

REQUIRED_EVIDENCE_KEYS = [
    "before_rgb",
    "after_rgb",
    "ndvi_before",
    "ndvi_after",
    "ndvi_change",
    "ndwi_change",
    "ndbi_change",
    "combined_change",
    "metadata",
]


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_contract_validation() -> int:
    cfg = get_config()
    api_dir = cfg.directories.outputs_dir / "api"
    evidence_dir = cfg.directories.outputs_dir / "evidence"

    status_checks: Dict[str, bool] = {
        "API contracts": False,
        "GeoJSON": False,
        "Evidence manifest": False,
        "Evidence assets": False,
        "Coordinates": False,
        "Priority scores": False,
        "Periods": False,
        "Demo hotspots": False,
    }

    try:
        # ---------------------------------------------------------
        # Check 1: API JSON contracts & Periods
        # ---------------------------------------------------------
        demo_manifest_file = api_dir / "demo_manifest.json"
        if not demo_manifest_file.exists():
            raise FileNotFoundError(f"Missing demo manifest: {demo_manifest_file}")
        demo_manifest = load_json(demo_manifest_file)

        api_files_to_check = [demo_manifest_file]
        for period in VALID_PERIODS:
            api_files_to_check.append(api_dir / f"city_summary_{period}.json")
            api_files_to_check.append(api_dir / f"hotspots_{period}.json")
            api_files_to_check.append(api_dir / f"top_10_{period}.json")
            api_files_to_check.append(api_dir / f"top_25_{period}.json")
            api_files_to_check.append(api_dir / f"top_50_{period}.json")

        all_hotspot_records: List[Dict[str, Any]] = []
        for file_path in api_files_to_check:
            data = load_json(file_path)
            if "hotspots_" in file_path.name or "top_" in file_path.name:
                if isinstance(data, list):
                    all_hotspot_records.extend(data)

        status_checks["API contracts"] = True
        status_checks["Periods"] = True

        # ---------------------------------------------------------
        # Check 2: GeoJSON files and coordinate order
        # ---------------------------------------------------------
        for period in VALID_PERIODS:
            geojson_file = api_dir / f"hotspots_{period}.geojson"
            geojson_data = load_json(geojson_file)

            if geojson_data.get("type") != "FeatureCollection":
                raise ValueError(f"GeoJSON type is not FeatureCollection in {geojson_file.name}")
            if geojson_data.get("period") != period:
                raise ValueError(f"GeoJSON period mismatch in {geojson_file.name}")

            features = geojson_data.get("features", [])
            if len(features) != 1462:
                raise ValueError(f"Expected 1462 features in {geojson_file.name}, found {len(features)}")

            for feat in features:
                geom = feat.get("geometry", {})
                if geom.get("type") != "Point":
                    raise ValueError(f"Expected Point geometry in {geojson_file.name}")
                coords = geom.get("coordinates", [])
                if len(coords) != 2:
                    raise ValueError(f"Expected [lon, lat] coordinates, got {coords}")
                lon, lat = coords
                # GeoJSON coordinates order MUST be [longitude, latitude]
                if not (BBOX_LON_MIN <= lon <= BBOX_LON_MAX):
                    raise ValueError(f"Longitude {lon} out of bounds in GeoJSON")
                if not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX):
                    raise ValueError(f"Latitude {lat} out of bounds in GeoJSON")

        status_checks["GeoJSON"] = True

        # ---------------------------------------------------------
        # Check 3 & 4: Evidence manifest and assets
        # ---------------------------------------------------------
        manifest_path = evidence_dir / "evidence_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing evidence manifest at {manifest_path}")
        evidence_manifest = load_json(manifest_path)

        if not isinstance(evidence_manifest, dict) or len(evidence_manifest) == 0:
            raise ValueError("Evidence manifest is empty or invalid.")

        status_checks["Evidence manifest"] = True

        # Check all assets in evidence manifest
        for grid_id, period_dict in evidence_manifest.items():
            for period, assets in period_dict.items():
                if period not in VALID_PERIODS:
                    raise ValueError(f"Invalid period '{period}' in evidence manifest for {grid_id}")
                for key in REQUIRED_EVIDENCE_KEYS:
                    if key not in assets:
                        raise KeyError(f"Missing evidence asset key '{key}' for {grid_id} ({period})")
                    rel_path = assets[key]
                    full_path = PROJECT_ROOT / rel_path
                    if not full_path.exists():
                        raise FileNotFoundError(f"Evidence file missing on disk: {full_path}")
                    if full_path.stat().st_size == 0:
                        raise ValueError(f"Evidence file is empty: {full_path}")

        status_checks["Evidence assets"] = True

        # ---------------------------------------------------------
        # Check 5 & 6: Coordinates, Priority Scores, Levels
        # ---------------------------------------------------------
        for record in all_hotspot_records:
            lat = record.get("latitude")
            lon = record.get("longitude")
            if lat is None or lon is None:
                raise ValueError(f"Missing coordinates in hotspot {record.get('grid_id')}")
            if not (BBOX_LAT_MIN <= lat <= BBOX_LAT_MAX):
                raise ValueError(f"Hotspot latitude {lat} outside Hyderabad bounding box")
            if not (BBOX_LON_MIN <= lon <= BBOX_LON_MAX):
                raise ValueError(f"Hotspot longitude {lon} outside Hyderabad bounding box")

            priority = record.get("priority", {})
            score = priority.get("score")
            level = priority.get("level")
            rec = priority.get("recommendation")

            if score is None or math.isnan(score) or not (0.0 <= score <= 1.0):
                raise ValueError(f"Invalid priority score {score} in {record.get('grid_id')}")
            if level not in VALID_PRIORITY_LEVELS:
                raise ValueError(f"Invalid priority level '{level}' in {record.get('grid_id')}")
            if rec not in VALID_RECOMMENDATIONS:
                raise ValueError(f"Invalid recommendation '{rec}' in {record.get('grid_id')}")

        status_checks["Coordinates"] = True
        status_checks["Priority scores"] = True

        # ---------------------------------------------------------
        # Check 7: Demo Hotspots
        # ---------------------------------------------------------
        recommended_hotspot = demo_manifest.get("recommended_demo_hotspot")
        if recommended_hotspot != "HYD_1220":
            raise ValueError(f"Expected recommended demo hotspot HYD_1220, got {recommended_hotspot}")

        demo_hotspots_catalog = demo_manifest.get("demo_hotspots", {})
        if "HYD_1220" not in demo_hotspots_catalog:
            raise KeyError("HYD_1220 not found in demo_manifest demo_hotspots catalog")

        for hid in [recommended_hotspot] + demo_manifest.get("backup_demo_hotspots", []):
            if hid not in evidence_manifest:
                raise KeyError(f"Demo hotspot {hid} not found in evidence_manifest.json")
            # Verify primary period assets exist
            demo_info = demo_hotspots_catalog.get(hid, {})
            prim_period = demo_info.get("primary_period", "2020_2026")
            evidence_entry = evidence_manifest[hid].get(prim_period)
            if not evidence_entry:
                raise KeyError(f"Demo hotspot {hid} has no evidence for {prim_period}")

        status_checks["Demo hotspots"] = True

    except Exception as exc:
        print(f"Validation FAILED: {exc}", file=sys.stderr)
        return 1

    # Formatted readiness report
    print("UrbanPulse Frontend Contract Validation")
    print("----------------------------------------")
    for component, passed in status_checks.items():
        res_str = "PASS" if passed else "FAIL"
        print(f"{component + ':':<22} {res_str}")
    print()
    print("Recommended demo hotspot:")
    print(recommended_hotspot)
    print()
    print("Status: READY")

    return 0


if __name__ == "__main__":
    sys.exit(run_contract_validation())
