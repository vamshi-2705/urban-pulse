#!/usr/bin/env python3
"""
UrbanPulse - Execute Sentinel-2 Scene Discovery Script.

Discovers, ranks, and records optimal Sentinel-2 Level-2A scenes for Hyderabad AOI
across target years 2020, 2023, and 2026.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from geospatial.acquisition.sentinel2 import discover_scenes
from geospatial.logger import get_logger, setup_logging


def main() -> int:
    setup_logging()
    logger = get_logger("run_scene_discovery")

    logger.info("Starting UrbanPulse Sentinel-2 Scene Discovery (Step 2)...")
    try:
        catalog = discover_scenes()
        output_file = PROJECT_ROOT / "data" / "processed" / "scene_catalog.json"

        print("\n" + "=" * 60)
        print("URBANPULSE SENTINEL-2 SCENE DISCOVERY SUMMARY")
        print("=" * 60)
        print(f"Study Area: {catalog['study_area']} ({catalog['region']})")
        print(f"Collection: {catalog['collection']}")
        print(f"Cloud Threshold: <={catalog['cloud_threshold']}%")
        print(f"Catalog saved to: {output_file}")
        print("-" * 60)

        for year, pdata in catalog["periods"].items():
            print(f"\nTarget Year: {year}")
            print(f"  Status: {pdata.get('status')}")
            print(f"  Candidates Considered: {pdata.get('candidates_considered')}")
            scene = pdata.get("selected_scene")
            if scene:
                print(f"  Selected Scene ID: {scene['item_id']}")
                print(f"  Acquisition Date: {scene['datetime']}")
                print(f"  Cloud Cover: {scene['cloud_cover']}%")
                print(f"  MGRS Tile: {scene.get('mgrs_tile')}")
                print(f"  Suitability Score: {scene.get('suitability_score')}/100")
                print(f"  All Spectral Bands Present: {scene.get('all_spectral_bands_present')}")
                print("  Inspected Assets:")
                for b_name, b_info in scene["assets"].items():
                    print(f"    - {b_name} ({b_info['asset_key']}): {b_info['title']}")
            else:
                print("  Selected Scene: None")

        print("=" * 60 + "\n")
        return 0

    except Exception as exc:
        logger.error(f"Scene discovery failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
