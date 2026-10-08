#!/usr/bin/env python3
"""
UrbanPulse - Export Integration API Contracts (Step 8).

Transforms processed priority records across 2020->2023, 2023->2026, and 2020->2026
into API-ready JSON, GeoJSON, and City Summary artifacts in data/outputs/api/.
Validates all outputs against strict API data contract rules.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config
from geospatial.integration import (
    export_all_api_artifacts,
    validate_city_summary,
    validate_geojson_collection,
    validate_hotspots_collection,
)
from geospatial.logger import get_logger, setup_logging


def validate_exported_api_directory(api_dir: Path) -> None:
    """Validate all generated JSON and GeoJSON files in the API output directory."""
    logger = get_logger("export_api_contracts.validate")
    periods = ["2020_2023", "2023_2026", "2020_2026"]

    for period in periods:
        hotspots_file = api_dir / f"hotspots_{period}.json"
        geojson_file = api_dir / f"hotspots_{period}.geojson"
        summary_file = api_dir / f"city_summary_{period}.json"

        logger.info(f"Validating API contracts for {period}...")

        # 1. Hotspots JSON
        with open(hotspots_file, encoding="utf-8") as f:
            hotspots = json.load(f)
        validate_hotspots_collection(hotspots)
        logger.info(f"  PASS: {hotspots_file.name} ({len(hotspots)} records, monotonic rank, bounded scores)")

        # 2. GeoJSON
        with open(geojson_file, encoding="utf-8") as f:
            geojson = json.load(f)
        validate_geojson_collection(geojson)
        logger.info(f"  PASS: {geojson_file.name} ({len(geojson['features'])} features, valid Point geometry)")

        # 3. City Summary
        with open(summary_file, encoding="utf-8") as f:
            summary = json.load(f)
        validate_city_summary(summary)
        logger.info(
            f"  PASS: {summary_file.name} (Total: {summary['total_cells']}, "
            f"High: {summary['high_priority']}, Med: {summary['medium_priority']}, Low: {summary['low_priority']})"
        )


def main() -> int:
    setup_logging()
    logger = get_logger("export_api_contracts")

    logger.info("Starting UrbanPulse API Contract Export (Step 8)...")
    t0 = time.time()
    try:
        cfg = get_config()
        results = export_all_api_artifacts(cfg)
        elapsed = time.time() - t0

        api_dir = cfg.directories.outputs_dir / "api"
        logger.info("Running strict schema validation on generated API contracts...")
        validate_exported_api_directory(api_dir)

        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        print()
        print("UrbanPulse Integration & API Contracts (Step 8)")
        print("================================================")
        print()
        for p, artifacts in results.items():
            print(f"Period: {p}")
            print(f"  Hotspots JSON: {Path(artifacts['hotspots']).name}")
            print(f"  GeoJSON:       {Path(artifacts['geojson']).name}")
            print(f"  City Summary:  {Path(artifacts['summary']).name}")
            print(f"  Subsets:       top_10, top_25, top_50")
            print()

        print("Validation: ALL CONTRACTS VALIDATED (No NaN, valid coordinates, monotonic rank)")
        print(f"Total Execution Runtime: {elapsed:.2f}s")
        print("Status: PASS")
        print()
        return 0

    except Exception as exc:
        logger.error(f"API export failed: {exc}", exc_info=True)
        print(f"\nStatus: FAIL: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
