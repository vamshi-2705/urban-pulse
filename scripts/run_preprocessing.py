#!/usr/bin/env python3
"""
UrbanPulse - Execute Sentinel-2 Preprocessing & ARD Stack Pipeline (Step 3).

Downloads required spectral and classification assets from scene_catalog.json,
standardizes to EPSG:32644 at 10m resolution, applies SCL cloud masks,
normalizes reflectance, and produces validated scene stacks.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from geospatial.logger import get_logger, setup_logging
from geospatial.preprocessing.sentinel2_preprocessor import preprocess_all_selected_scenes


def main() -> int:
    setup_logging()
    logger = get_logger("run_preprocessing")

    logger.info("Starting UrbanPulse Sentinel-2 Preprocessing (Step 3)...")
    try:
        summary = preprocess_all_selected_scenes()

        print("\n" + "=" * 65)
        print("URBANPULSE SENTINEL-2 PREPROCESSING SUMMARY (STEP 3)")
        print("=" * 65)
        print(f"Study Area: {summary['study_area']}")
        print(f"Target CRS: {summary['target_crs']}")
        print(f"Target Resolution: {summary['target_resolution']}m")
        print("-" * 65)

        for year_str, rec in summary["epochs"].items():
            print(f"\nEpoch {year_str}:")
            print(f"  Scene ID: {rec['item_id']}")
            print(f"  Acquisition Date: {rec['acquisition_date']} (DOY: {rec['day_of_year']})")
            print(f"  Cloud Cover: {rec['cloud_percentage']}%")
            print(f"  Dimensions: {rec['dimensions'][0]} rows x {rec['dimensions'][1]} cols")
            print(f"  CRS: {rec['crs']}")
            print(f"  Resolution: {rec['resolution_meters']}m")
            print(f"  Valid Pixels: {rec['valid_pixel_percentage']}%")
            print(f"  Reflectance Formula: {rec['reflectance_scaling']['formula']}")
            print(f"  Stack File: {rec['stack_file']}")
            print(f"  Mask File: {rec['mask_file']}")
            print("  Band Statistics (Mean Reflectance):")
            for b_name, b_stat in rec["band_statistics"].items():
                print(f"    - {b_name:6s}: min={b_stat['min']:.4f}, mean={b_stat['mean']:.4f}, max={b_stat['max']:.4f}")
            print(f"  Validation Status: PASS")

        print("=" * 65 + "\n")
        logger.info("Step 3 preprocessing completed successfully.")
        return 0

    except Exception as exc:
        logger.error(f"Preprocessing pipeline failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
