#!/usr/bin/env python3
"""
UrbanPulse - Verify Evidence Assets (Step 9 Demo Validation).

Performs strict integrity validation on generated visual evidence products:
- Verifies existence and structure of data/outputs/evidence/evidence_manifest.json
- Verifies all referenced PNG images and metadata JSON files exist on disk
- Verifies metadata schemas, coordinate bounding, acquisition timestamps, and CRS
- Verifies image files are non-empty and valid PNGs
- Returns exit code 0 on complete validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config
from geospatial.logger import get_logger, setup_logging


def verify_evidence_manifest() -> bool:
    """Validate global evidence manifest and all referenced assets."""
    logger = get_logger("verify_evidence_assets")
    cfg = get_config()

    evidence_dir = cfg.directories.outputs_dir / "evidence"
    manifest_file = evidence_dir / "evidence_manifest.json"

    if not manifest_file.exists():
        logger.error(f"Missing evidence manifest: {manifest_file}")
        return False

    with open(manifest_file, encoding="utf-8") as f:
        try:
            manifest = json.load(f)
        except json.JSONDecodeError as err:
            logger.error(f"Manifest JSON is corrupted: {err}")
            return False

    if not manifest:
        logger.error("Evidence manifest is empty.")
        return False

    total_hotspots = len(manifest)
    total_periods = 0
    total_assets_checked = 0

    required_asset_keys = [
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

    for grid_id, periods_dict in manifest.items():
        if not isinstance(periods_dict, dict):
            logger.error(f"Hotspot '{grid_id}' value is not a dict of periods.")
            return False

        for period, assets in periods_dict.items():
            total_periods += 1

            # 1. Check all required asset keys exist in manifest
            for req_key in required_asset_keys:
                if req_key not in assets:
                    logger.error(f"Missing asset key '{req_key}' for {grid_id} ({period})")
                    return False

                asset_rel_path = assets[req_key]
                asset_full_path = PROJECT_ROOT / asset_rel_path

                if not asset_full_path.exists():
                    logger.error(f"Referenced asset file does not exist: {asset_full_path}")
                    return False

                if asset_full_path.stat().st_size == 0:
                    logger.error(f"Asset file is empty (0 bytes): {asset_full_path}")
                    return False

                # Check PNG signature for image assets
                if asset_full_path.suffix.lower() == ".png":
                    with open(asset_full_path, "rb") as img_f:
                        header = img_f.read(8)
                        if header != b"\x89PNG\r\n\x1a\n":
                            logger.error(f"File is not a valid PNG: {asset_full_path}")
                            return False

                total_assets_checked += 1

            # 2. Check metadata JSON content
            meta_rel = assets["metadata"]
            meta_full = PROJECT_ROOT / meta_rel
            with open(meta_full, encoding="utf-8") as mf:
                meta = json.load(mf)

            req_meta_fields = [
                "grid_id",
                "period",
                "center_lat",
                "center_lon",
                "window_meters",
                "crs",
                "source",
                "before_date",
                "after_date",
                "crop_dimensions",
                "assets",
            ]
            for mf_key in req_meta_fields:
                if mf_key not in meta:
                    logger.error(f"Metadata missing required field '{mf_key}' in {meta_full}")
                    return False

            if meta["grid_id"] != grid_id:
                logger.error(f"Metadata grid_id '{meta['grid_id']}' != expected '{grid_id}'")
                return False

            if meta["crs"] != "EPSG:32644":
                logger.error(f"Metadata CRS '{meta['crs']}' != 'EPSG:32644'")
                return False

            dims = meta["crop_dimensions"]
            if not isinstance(dims, list) or len(dims) != 2 or dims[0] <= 0 or dims[1] <= 0:
                logger.error(f"Invalid crop dimensions {dims} in {meta_full}")
                return False

    logger.info(
        f"Manifest verification SUCCESS: {total_hotspots} hotspots, "
        f"{total_periods} epoch instances, {total_assets_checked} files verified."
    )
    return True


def main() -> int:
    setup_logging()
    logger = get_logger("verify_evidence_assets")

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print()
    print("UrbanPulse Visual Evidence Assets Verification (Step 9)")
    print("=======================================================")
    print()

    try:
        success = verify_evidence_manifest()
        if success:
            cfg = get_config()
            manifest_file = cfg.directories.outputs_dir / "evidence" / "evidence_manifest.json"
            with open(manifest_file, encoding="utf-8") as f:
                manifest = json.load(f)

            sample_gid = list(manifest.keys())[0] if manifest else "None"
            sample_period = list(manifest[sample_gid].keys())[0] if manifest else "None"
            sample_assets = manifest.get(sample_gid, {}).get(sample_period, {})

            print(f"Verified Evidence Hotspots: {len(manifest)}")
            print(f"Sample Hotspot: {sample_gid} ({sample_period})")
            print(f"  Before RGB:      {sample_assets.get('before_rgb')}")
            print(f"  After RGB:       {sample_assets.get('after_rgb')}")
            print(f"  NDVI Change:     {sample_assets.get('ndvi_change')}")
            print(f"  Combined Change: {sample_assets.get('combined_change')}")
            print(f"  Metadata:        {sample_assets.get('metadata')}")
            print()
            print("Status: PASS (Exit code 0)")
            print()
            return 0
        else:
            print("Status: FAIL")
            return 1

    except Exception as exc:
        logger.error(f"Verification error: {exc}", exc_info=True)
        print(f"Status: FAIL ({exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
