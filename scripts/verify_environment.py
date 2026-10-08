#!/usr/bin/env python3
"""
UrbanPulse - Environment & Foundation Verification Script.

Verifies:
1. Python runtime and core libraries
2. Central configuration loading
3. File directory integrity
4. Logging setup
5. Key module imports
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_config
from geospatial.logger import get_logger, setup_logging


def main() -> int:
    setup_logging()
    logger = get_logger("verify_environment")
    logger.info("==================================================")
    logger.info("UrbanPulse Geospatial Engine - Environment Verification")
    logger.info("==================================================")

    # 1. Verify Configuration
    try:
        cfg = get_config(reload=True)
        logger.info(f"[OK] Configuration successfully loaded from config/config.yaml")
        logger.info(f"     - Study Area: {cfg.study_area.name} ({cfg.study_area.region})")
        logger.info(f"     - Bounding Box: {cfg.study_area.bbox}")
        logger.info(f"     - Coordinate Systems: Geographic={cfg.crs.geographic}, Projected={cfg.crs.projected}")
        logger.info(f"     - Analysis Epochs: {cfg.time_periods.years}")
        logger.info(f"     - Max Cloud Threshold: {cfg.satellite.cloud_cover_max_percent}%")
        logger.info(f"     - Grid Resolution: {cfg.grid.cell_size_meters}m (Prefix: {cfg.grid.prefix})")
    except Exception as exc:
        logger.error(f"[FAIL] Failed to load configuration: {exc}")
        return 1

    # 2. Verify Directory Structure
    dirs_to_check = [
        ("Raw Data", cfg.directories.raw_dir),
        ("Processed Data", cfg.directories.processed_dir),
        ("Outputs", cfg.directories.outputs_dir),
        ("Logs", cfg.directories.logs_dir),
    ]

    all_dirs_ok = True
    for label, dir_path in dirs_to_check:
        if dir_path.exists() and dir_path.is_dir():
            logger.info(f"[OK] Directory verified: {label} -> {dir_path}")
        else:
            logger.warning(f"[MISSING] Directory created: {label} -> {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)
            if not dir_path.exists():
                all_dirs_ok = False

    if not all_dirs_ok:
        logger.error("[FAIL] Directory verification failed.")
        return 1

    # 3. Verify Geospatial Subpackages
    submodules = [
        "geospatial.acquisition",
        "geospatial.preprocessing",
        "geospatial.grid",
        "geospatial.indicators",
        "geospatial.change_detection",
        "geospatial.anomaly",
        "geospatial.priority",
        "geospatial.evidence",
        "geospatial.validation",
    ]

    for mod_name in submodules:
        try:
            importlib.import_module(mod_name)
            logger.info(f"[OK] Submodule imported: {mod_name}")
        except Exception as exc:
            logger.error(f"[FAIL] Submodule import failed: {mod_name} ({exc})")
            return 1

    # 4. Check Optional / Ecosystem Dependencies
    dependencies = [
        ("yaml", "PyYAML (Config Parser)"),
        ("pytest", "Pytest (Test Runner)"),
        ("numpy", "NumPy (Scientific Arrays)"),
        ("pandas", "Pandas (Tabular Data)"),
        ("shapely", "Shapely (Geometry Engine)"),
        ("pyproj", "PyProj (Coordinate Transformations)"),
        ("pystac_client", "PySTAC Client (STAC API Querying)"),
        ("planetary_computer", "Planetary Computer (Asset Authentication)"),
        ("rasterio", "Rasterio (Geotiff I/O)"),
        ("geopandas", "GeoPandas (Vector Data)"),
        ("sklearn", "Scikit-Learn (Anomaly Detection & Modeling)"),
        ("matplotlib", "Matplotlib (Visualization Diagnostics)"),
    ]

    logger.info("--------------------------------------------------")
    logger.info("Checking Ecosystem Dependencies:")
    for pkg_name, description in dependencies:
        try:
            mod = importlib.import_module(pkg_name)
            version = getattr(mod, "__version__", "installed")
            logger.info(f"  [INSTALLED] {description}: v{version}")
        except ImportError:
            logger.warning(f"  [NOT INSTALLED] {description} ({pkg_name}) - Run pip install -r requirements.txt")

    logger.info("==================================================")
    logger.info("Verification Complete: Foundation is valid and operational.")
    logger.info("==================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
