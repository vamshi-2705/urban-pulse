#!/usr/bin/env python3
"""
UrbanPulse - Execute Evidence Asset Generation (Step 9).

Generates georeferenced crop previews, delta indicator maps, combined evidence maps,
metadata JSONs, and compiles data/outputs/evidence/evidence_manifest.json
for the Top-10 hotspots across 2020->2026, 2020->2023, and 2023->2026.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config
from geospatial.evidence import generate_all_evidence_manifests
from geospatial.logger import get_logger, setup_logging


def main() -> int:
    setup_logging()
    logger = get_logger("run_evidence_generation")

    logger.info("Starting UrbanPulse Evidence Asset Generation (Step 9)...")
    t0 = time.time()
    try:
        cfg = get_config()
        # Process Top 10 hotspots for each of the 3 comparison periods
        manifest = generate_all_evidence_manifests(
            periods=["2020_2026", "2020_2023", "2023_2026"],
            top_k=10,
            window_meters=1000.0,
            config=cfg,
        )
        elapsed = time.time() - t0

        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

        print()
        print("UrbanPulse Evidence Asset Generation (Step 9)")
        print("==============================================")
        print()
        print(f"Total Unique Hotspots Processed: {len(manifest)}")
        print(f"Manifest Location: data/outputs/evidence/evidence_manifest.json")
        print()
        for gid, periods in list(manifest.items())[:5]:
            print(f"Hotspot: {gid}")
            for p, assets in periods.items():
                print(f"  Period: {p}")
                print(f"    Before RGB:      {assets.get('before_rgb')}")
                print(f"    After RGB:       {assets.get('after_rgb')}")
                print(f"    Combined Change: {assets.get('combined_change')}")
            print()

        print(f"Total Generation Runtime: {elapsed:.2f}s")
        print("Status: PASS")
        print()
        return 0

    except Exception as exc:
        logger.error(f"Evidence generation failed: {exc}", exc_info=True)
        print(f"\nStatus: FAIL: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
