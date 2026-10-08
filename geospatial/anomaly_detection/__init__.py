"""
UrbanPulse - Anomaly Detection Package (Step 6).

Coordinates:
- Temporal Anomaly Engine (Median / MAD / Robust Z / Bounded [0,1] score)
- Spatial Neighborhood Anomaly Engine (Rolling window / Robust local deviation / Valid neighbor checks)
- Anomaly Fusion Engine (Weighted combination / Availability fallback / Overall anomaly)
- Cross-Indicator Evidence Engine (Vegetation-builtup coherence / Persistence & Reversal flags)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

from config.settings import AppConfig, get_config
from geospatial.anomaly_detection.anomaly_fusion import (
    ANOMALY_STACK_BAND_NAMES,
    compute_period_combined_anomalies,
    fuse_anomaly_components,
    validate_anomaly_raster,
    write_anomaly_raster,
)
from geospatial.anomaly_detection.evidence import (
    EVIDENCE_FLAG_BAND_NAMES,
    build_evidence_record,
    evaluate_cross_indicator_evidence,
    write_evidence_raster,
)
from geospatial.anomaly_detection.spatial_anomaly import (
    compute_indicator_spatial_anomaly,
    compute_period_spatial_anomalies,
    count_valid_neighbors,
)
from geospatial.anomaly_detection.temporal_anomaly import (
    calculate_robust_center_dispersion,
    calculate_robust_z,
    compute_indicator_temporal_anomaly,
    compute_period_temporal_anomalies,
    z_to_anomaly_score,
)
from geospatial.logger import get_logger

logger = get_logger("geospatial.anomaly_detection")


def process_period_anomaly(
    period: str,
    earlier_year: int,
    later_year: int,
    change_dir: Path,
    output_base_dir: Path,
    persistence_stack: Optional[np.ndarray] = None,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Execute full anomaly detection pipeline for a single comparison epoch.

    Args:
        period: Period string (e.g. "2020_2023").
        earlier_year: Earlier epoch year.
        later_year: Later epoch year.
        change_dir: Directory containing Step 5 outputs for this period.
        output_base_dir: Base directory for anomaly outputs (data/processed/anomaly_detection).
        persistence_stack: Optional (9, H, W) persistence raster from Step 5.
        config: Optional AppConfig.

    Returns:
        Dict of results and statistics for this period.
    """
    if config is None:
        config = get_config()

    stack_file = change_dir / "change_stack.tif"
    mask_file = change_dir / "valid_mask.tif"

    if not stack_file.exists():
        raise FileNotFoundError(f"Step 5 change stack missing: {stack_file}")
    if not mask_file.exists():
        raise FileNotFoundError(f"Step 5 mask missing: {mask_file}")

    with rasterio.open(stack_file) as src, rasterio.open(mask_file) as m_src:
        profile = src.profile.copy()
        change_stack = src.read().astype(np.float32)
        valid_mask = (m_src.read(1) == 1)

    logger.info(f"Processing anomaly detection for {period} ({change_stack.shape[1]}x{change_stack.shape[2]} pixels)...")

    # 1. Temporal Anomaly
    logger.info(f"Computing temporal anomalies for {period}...")
    t_res = compute_period_temporal_anomalies(
        change_stack, valid_mask, config.anomaly.temporal
    )

    # 2. Spatial Anomaly
    logger.info(f"Computing spatial neighborhood anomalies for {period}...")
    s_res = compute_period_spatial_anomalies(
        change_stack, valid_mask, config.anomaly.spatial
    )

    # 3. Anomaly Fusion
    logger.info(f"Fusing temporal and spatial anomaly components for {period}...")
    f_res = compute_period_combined_anomalies(
        t_res["temporal_stack"], s_res["spatial_stack"], config.anomaly.combined
    )

    # 4. Cross-Indicator Evidence
    logger.info(f"Evaluating cross-indicator evidence consistency for {period}...")
    e_res = evaluate_cross_indicator_evidence(
        change_stack,
        f_res["full_anomaly_stack"],
        f_res["valid_mask"],
        persistence_stack=persistence_stack,
        config=config.anomaly.evidence,
    )

    # 5. Write Rasters
    # A. Temporal Stack (3 bands: NDVI, NDWI, NDBI)
    t_dir = output_base_dir / "temporal" / period
    t_path, t_mask = write_anomaly_raster(
        t_res["temporal_stack"],
        valid_mask,
        profile,
        t_dir / "temporal_anomaly.tif",
        t_dir / "valid_mask.tif",
        ["NDVI_temporal_anomaly", "NDWI_temporal_anomaly", "NDBI_temporal_anomaly"],
    )

    # B. Spatial Stack (3 bands: NDVI, NDWI, NDBI)
    s_dir = output_base_dir / "spatial" / period
    s_path, s_mask = write_anomaly_raster(
        s_res["spatial_stack"],
        s_res["spatial_valid_mask"],
        profile,
        s_dir / "spatial_anomaly.tif",
        s_dir / "valid_mask.tif",
        ["NDVI_spatial_anomaly", "NDWI_spatial_anomaly", "NDBI_spatial_anomaly"],
    )

    # C. Combined Stack (4 bands: NDVI, NDWI, NDBI, overall combined)
    c_dir = output_base_dir / "combined" / period
    c_path, c_mask = write_anomaly_raster(
        f_res["combined_stack"],
        f_res["valid_mask"],
        profile,
        c_dir / "combined_anomaly.tif",
        c_dir / "valid_mask.tif",
        ["NDVI_combined_anomaly", "NDWI_combined_anomaly", "NDBI_combined_anomaly", "overall_combined_anomaly"],
    )

    # D. Comprehensive 10-band anomaly stack
    full_path, full_mask = write_anomaly_raster(
        f_res["full_anomaly_stack"],
        f_res["valid_mask"],
        profile,
        c_dir / "anomaly_stack.tif",
        c_dir / "valid_mask.tif",
        ANOMALY_STACK_BAND_NAMES,
    )
    validate_anomaly_raster(full_path, full_mask, expected_bands=10)

    # E. Evidence Flags (7 bands UInt8)
    e_dir = output_base_dir / "evidence" / period
    e_path, e_mask = write_evidence_raster(
        e_res["evidence_stack"],
        f_res["valid_mask"],
        profile,
        e_dir / "evidence_flags.tif",
        e_dir / "valid_mask.tif",
    )

    # 6. Statistical Summaries
    stats_dir = output_base_dir / "statistics"
    stats_dir.mkdir(parents=True, exist_ok=True)

    def dist_summary(arr: np.ndarray, mask: np.ndarray, name: str) -> Dict[str, Any]:
        v = arr[mask & np.isfinite(arr)]
        if len(v) == 0:
            return {"name": name, "valid_pixels": 0}
        return {
            "name": name,
            "valid_pixels": int(len(v)),
            "min": round(float(np.min(v)), 4),
            "max": round(float(np.max(v)), 4),
            "mean": round(float(np.mean(v)), 4),
            "median": round(float(np.median(v)), 4),
            "std": round(float(np.std(v)), 4),
            "p05": round(float(np.percentile(v, 5)), 4),
            "p50": round(float(np.percentile(v, 50)), 4),
            "p75": round(float(np.percentile(v, 75)), 4),
            "p95": round(float(np.percentile(v, 95)), 4),
            "p99": round(float(np.percentile(v, 99)), 4),
            "pixels_above_05": int(np.sum(v >= 0.5)),
            "pct_above_05": round(100.0 * np.sum(v >= 0.5) / len(v), 2),
            "pixels_above_07": int(np.sum(v >= 0.7)),
            "pct_above_07": round(100.0 * np.sum(v >= 0.7) / len(v), 2),
        }

    c_mask_arr = f_res["valid_mask"]
    stats = {
        "period": period,
        "earlier_year": earlier_year,
        "later_year": later_year,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_pixels": int(change_stack[0].size),
        "valid_pixels": int(np.sum(c_mask_arr)),
        "temporal": {
            "ndvi": t_res["ndvi"]["metadata"],
            "ndwi": t_res["ndwi"]["metadata"],
            "ndbi": t_res["ndbi"]["metadata"],
        },
        "spatial": {
            "ndvi": s_res["ndvi"]["metadata"],
            "ndwi": s_res["ndwi"]["metadata"],
            "ndbi": s_res["ndbi"]["metadata"],
        },
        "combined": {
            "ndvi": dist_summary(f_res["ndvi_combined"], c_mask_arr, "ndvi_combined_anomaly"),
            "ndwi": dist_summary(f_res["ndwi_combined"], c_mask_arr, "ndwi_combined_anomaly"),
            "ndbi": dist_summary(f_res["ndbi_combined"], c_mask_arr, "ndbi_combined_anomaly"),
            "overall": dist_summary(f_res["overall_combined"], c_mask_arr, "overall_combined_anomaly"),
        },
        "evidence": e_res["summary"],
        "files": {
            "temporal_raster": str(t_path.resolve()),
            "spatial_raster": str(s_path.resolve()),
            "combined_raster": str(c_path.resolve()),
            "anomaly_stack": str(full_path.resolve()),
            "evidence_raster": str(e_path.resolve()),
        },
    }

    with open(stats_dir / f"{period}.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Generate sample explainable evidence records for top anomalous locations
    sample_records = []
    overall_arr = f_res["overall_combined"]
    # Identify top 10 anomalous valid pixels
    valid_indices = np.argwhere(c_mask_arr & np.isfinite(overall_arr))
    if len(valid_indices) > 0:
        valid_scores = overall_arr[valid_indices[:, 0], valid_indices[:, 1]]
        top_k_idx = np.argsort(valid_scores)[-10:][::-1]
        for rank, idx in enumerate(top_k_idx, start=1):
            r, c = valid_indices[idx]
            rec = build_evidence_record(
                f"HYD_SAMPLE_{rank:02d}",
                int(r),
                int(c),
                change_stack,
                f_res["full_anomaly_stack"],
                e_res["evidence_stack"],
                c_mask_arr,
            )
            sample_records.append(rec)

    with open(e_dir / "sample_evidence_records.json", "w", encoding="utf-8") as f:
        json.dump(sample_records, f, indent=2)

    logger.info(f"Completed anomaly detection for {period}.")
    return stats


def process_all_anomalies(config: Optional[AppConfig] = None) -> Dict[str, Any]:
    """
    Execute Step 6 anomaly detection pipeline across all multi-temporal comparison periods:
    - 2020 -> 2023
    - 2023 -> 2026
    - 2020 -> 2026

    Args:
        config: Optional AppConfig instance.

    Returns:
        Structured dictionary of results across all periods.
    """
    if config is None:
        config = get_config()

    change_dir = config.directories.processed_dir / "change_detection"
    anomaly_dir = config.directories.processed_dir / "anomaly_detection"
    anomaly_dir.mkdir(parents=True, exist_ok=True)

    # Load persistence stack from Step 5 if present
    persistence_file = change_dir / "multitemporal" / "persistence.tif"
    persistence_stack = None
    if persistence_file.exists():
        with rasterio.open(persistence_file) as p_src:
            persistence_stack = p_src.read()
            logger.info(f"Loaded Step 5 persistence stack: {persistence_stack.shape}")

    results: Dict[str, Any] = {
        "periods": {},
        "pipeline": "UrbanPulse Step 6 Anomaly Detection",
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    periods = [
        ("2020_2023", 2020, 2023),
        ("2023_2026", 2023, 2026),
        ("2020_2026", 2020, 2026),
    ]

    for p_label, yr_start, yr_end in periods:
        p_change_dir = change_dir / p_label
        p_stats = process_period_anomaly(
            p_label,
            yr_start,
            yr_end,
            p_change_dir,
            anomaly_dir,
            persistence_stack=persistence_stack,
            config=config,
        )
        results["periods"][p_label] = p_stats

    # Export overall summary
    stats_dir = anomaly_dir / "statistics"
    with open(stats_dir / "anomaly_summary.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("Successfully executed full UrbanPulse Step 6 Anomaly Detection Engine.")
    return results


__all__ = [
    "ANOMALY_STACK_BAND_NAMES",
    "EVIDENCE_FLAG_BAND_NAMES",
    "build_evidence_record",
    "calculate_robust_center_dispersion",
    "calculate_robust_z",
    "compute_indicator_spatial_anomaly",
    "compute_indicator_temporal_anomaly",
    "compute_period_combined_anomalies",
    "compute_period_spatial_anomalies",
    "compute_period_temporal_anomalies",
    "count_valid_neighbors",
    "evaluate_cross_indicator_evidence",
    "fuse_anomaly_components",
    "process_all_anomalies",
    "process_period_anomaly",
    "validate_anomaly_raster",
    "write_anomaly_raster",
    "write_evidence_raster",
    "z_to_anomaly_score",
]
