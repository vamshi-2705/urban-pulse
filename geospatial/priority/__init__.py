"""
UrbanPulse - Priority Engine Package (Step 7).

Coordinates:
- Component score calculation (Anomaly, Evidence, Persistence, Magnitude, Spatial context)
- Transparent weighted priority score fusion ([0.0, 1.0])
- Discrete priority level classification (HIGH, MEDIUM, LOW)
- Machine-readable reason-code generation
- 500m Geographic Grid aggregation (HYD_0001 ... HYD_1462)
- Top-K investigation candidate hotspot extraction (Top 10, Top 25, Top 50)
- Multi-format table export (CSV, JSON, GeoTIFF)
- Scientific baseline diagnostics against background cells
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

from config.settings import AppConfig, get_config
from geospatial.grid import GridCell, generate_study_grid
from geospatial.logger import get_logger
from geospatial.priority.grid_ranking import (
    aggregate_grid_cell_signals,
    export_priority_hotspot_tables,
    rank_and_extract_hotspots,
)
from geospatial.priority.priority_scoring import (
    PRIORITY_LEVEL_NAMES,
    PRIORITY_RECOMMENDATIONS,
    build_why_flagged_record,
    calculate_component_scores,
    calculate_priority_score,
    classify_priority_level,
    generate_reason_codes,
    write_priority_rasters,
)

logger = get_logger("geospatial.priority")


def process_period_priority(
    period: str,
    change_dir: Path,
    anomaly_dir: Path,
    evidence_dir: Path,
    output_dir: Path,
    persistence_stack: Optional[np.ndarray] = None,
    grid_cells: Optional[List[GridCell]] = None,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Execute full priority scoring and hotspot ranking pipeline for a single period.

    Args:
        period: Period string (e.g. "2020_2023", "2023_2026", "2020_2026").
        change_dir: Directory containing Step 5 change_stack.tif and valid_mask.tif.
        anomaly_dir: Directory containing Step 6 anomaly_stack.tif.
        evidence_dir: Directory containing Step 6 evidence_flags.tif.
        output_dir: Output directory for priority rasters and tables.
        persistence_stack: Optional (9, H, W) persistence raster from Step 5.
        grid_cells: Pre-generated 500m GridCell list (or generated on the fly).
        config: Optional AppConfig.

    Returns:
        Dictionary of period results, diagnostics, and file paths.
    """
    if config is None:
        config = get_config()

    priority_cfg = config.priority

    change_file = change_dir / "change_stack.tif"
    anomaly_file = anomaly_dir / "anomaly_stack.tif"
    evidence_file = evidence_dir / "evidence_flags.tif"
    mask_file = change_dir / "valid_mask.tif"

    if not change_file.exists():
        raise FileNotFoundError(f"Missing Step 5 change stack: {change_file}")
    if not anomaly_file.exists():
        raise FileNotFoundError(f"Missing Step 6 anomaly stack: {anomaly_file}")
    if not evidence_file.exists():
        raise FileNotFoundError(f"Missing Step 6 evidence flags: {evidence_file}")
    if not mask_file.exists():
        raise FileNotFoundError(f"Missing valid mask: {mask_file}")

    logger.info(f"Loading raster stacks for priority evaluation ({period})...")
    with rasterio.open(change_file) as c_src, \
         rasterio.open(anomaly_file) as a_src, \
         rasterio.open(evidence_file) as e_src, \
         rasterio.open(mask_file) as m_src:

        profile = c_src.profile.copy()
        transform = c_src.transform
        width = c_src.width
        height = c_src.height

        change_stack = c_src.read().astype(np.float32)
        anomaly_stack = a_src.read().astype(np.float32)
        evidence_stack = e_src.read().astype(np.uint8)
        valid_mask = (m_src.read(1) == 1)

    logger.info(f"Computing 5 normalized priority components for {period}...")
    components = calculate_component_scores(
        change_stack=change_stack,
        anomaly_stack=anomaly_stack,
        evidence_stack=evidence_stack,
        valid_mask=valid_mask,
        persistence_stack=persistence_stack,
    )

    logger.info(f"Evaluating weighted priority score ({period})...")
    priority_score = calculate_priority_score(
        components=components,
        weights=priority_cfg.weights,
        valid_mask=valid_mask,
    )

    logger.info(f"Classifying priority levels ({period})...")
    priority_level = classify_priority_level(
        priority_score=priority_score,
        thresholds=priority_cfg.thresholds,
        valid_mask=valid_mask,
    )

    # Export rasters
    raster_files = write_priority_rasters(
        priority_score=priority_score,
        priority_level=priority_level,
        valid_mask=valid_mask,
        profile=profile,
        output_dir=output_dir,
    )

    # Generate or reuse 500m grid cells
    if grid_cells is None:
        logger.info("Generating 500m tessellation grid cells...")
        grid_cells = generate_study_grid(
            transform=transform,
            width=width,
            height=height,
            cell_size_meters=config.grid.cell_size_meters,
            prefix=config.grid.prefix,
            crs_proj=config.crs.projected,
            crs_geo=config.crs.geographic,
        )

    logger.info(f"Aggregating into {len(grid_cells)} grid cells and ranking hotspots ({period})...")
    ranked_records, diagnostics = rank_and_extract_hotspots(
        grid_cells=grid_cells,
        priority_score=priority_score,
        components=components,
        change_stack=change_stack,
        anomaly_stack=anomaly_stack,
        evidence_stack=evidence_stack,
        valid_mask=valid_mask,
        config=priority_cfg,
    )

    # Export tables and structured JSONs
    table_files = export_priority_hotspot_tables(
        records=ranked_records,
        diagnostics=diagnostics,
        output_dir=output_dir,
    )

    logger.info(
        f"Completed priority processing for {period}: "
        f"{diagnostics['counts']['high']} HIGH, "
        f"{diagnostics['counts']['medium']} MEDIUM, "
        f"{diagnostics['counts']['low']} LOW cells."
    )

    return {
        "period": period,
        "diagnostics": diagnostics,
        "ranked_records": ranked_records,
        "raster_files": {k: str(v) for k, v in raster_files.items()},
        "table_files": {k: str(v) for k, v in table_files.items()},
    }


def process_all_priorities(
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Execute priority pipeline across all defined comparison periods:
    - 2020 -> 2023
    - 2023 -> 2026
    - 2020 -> 2026
    """
    if config is None:
        config = get_config()

    processed_dir = config.directories.processed_dir
    change_base = processed_dir / "change_detection"
    anomaly_base = processed_dir / "anomaly_detection" / "combined"
    evidence_base = processed_dir / "anomaly_detection" / "evidence"
    priority_base = processed_dir / "priority"

    priority_base.mkdir(parents=True, exist_ok=True)

    # Load persistence stack if present
    persistence_file = change_base / "multitemporal" / "persistence.tif"
    persistence_stack: Optional[np.ndarray] = None
    if persistence_file.exists():
        logger.info(f"Loading multi-temporal persistence stack from {persistence_file}...")
        with rasterio.open(persistence_file) as p_src:
            persistence_stack = p_src.read().astype(np.uint8)

    periods = [
        ("2020_2023", 2020, 2023),
        ("2023_2026", 2023, 2026),
        ("2020_2026", 2020, 2026),
    ]

    all_results: Dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "study_area_bbox": config.study_area.bbox,
            "grid_cell_size_meters": config.grid.cell_size_meters,
            "weights": {
                "anomaly": config.priority.weights.anomaly,
                "evidence": config.priority.weights.evidence,
                "persistence": config.priority.weights.persistence,
                "magnitude": config.priority.weights.magnitude,
                "spatial_context": config.priority.weights.spatial_context,
            },
            "thresholds": {
                "high": config.priority.thresholds.high,
                "medium": config.priority.thresholds.medium,
            },
        },
        "periods": {},
    }

    grid_cells_cache: Optional[List[GridCell]] = None

    for p_key, y1, y2 in periods:
        logger.info(f"=== Processing Step 7 Priority Engine for Period: {p_key} ({y1} -> {y2}) ===")
        c_dir = change_base / p_key
        a_dir = anomaly_base / p_key
        e_dir = evidence_base / p_key
        out_dir = priority_base / p_key

        period_res = process_period_priority(
            period=p_key,
            change_dir=c_dir,
            anomaly_dir=a_dir,
            evidence_dir=e_dir,
            output_dir=out_dir,
            persistence_stack=persistence_stack,
            grid_cells=grid_cells_cache,
            config=config,
        )

        all_results["periods"][p_key] = period_res

    # Save global priority manifest
    manifest_path = priority_base / "priority_manifest.json"
    serializable = {
        "metadata": all_results["metadata"],
        "periods": {
            p: {
                "diagnostics": res["diagnostics"],
                "raster_files": res["raster_files"],
                "table_files": res["table_files"],
            }
            for p, res in all_results["periods"].items()
        },
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    logger.info(f"Saved global priority manifest to {manifest_path}")
    return all_results


__all__ = [
    "PRIORITY_LEVEL_NAMES",
    "PRIORITY_RECOMMENDATIONS",
    "aggregate_grid_cell_signals",
    "build_why_flagged_record",
    "calculate_component_scores",
    "calculate_priority_score",
    "classify_priority_level",
    "export_priority_hotspot_tables",
    "generate_reason_codes",
    "process_all_priorities",
    "process_period_priority",
    "rank_and_extract_hotspots",
    "write_priority_rasters",
]
