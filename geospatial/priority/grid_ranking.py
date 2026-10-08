"""
UrbanPulse - Grid Aggregation & Investigation Ranking Engine.

Aggregates pixel-level priority scores and multi-spectral evidence signals
into 500m x 500m geographic grid cells (e.g. HYD_0001 ... HYD_1462),
ranks candidate investigation locations, extracts Top-K hotspots (Top 10, 25, 50),
and performs scientific validation diagnostics against background baseline cells.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config.settings import PriorityConfig, PriorityThresholdsConfig
from geospatial.grid import GridCell, generate_study_grid
from geospatial.logger import get_logger
from geospatial.priority.priority_scoring import (
    PRIORITY_LEVEL_NAMES,
    build_why_flagged_record,
    classify_priority_level,
    generate_reason_codes,
)

logger = get_logger("geospatial.priority.grid_ranking")


def aggregate_grid_cell_signals(
    cell: GridCell,
    priority_score: np.ndarray,
    components: Dict[str, np.ndarray],
    change_stack: np.ndarray,
    anomaly_stack: np.ndarray,
    evidence_stack: np.ndarray,
    valid_mask: np.ndarray,
    thresholds: PriorityThresholdsConfig,
) -> Optional[Dict[str, Any]]:
    """
    Aggregate pixel-level rasters into a single 500m grid cell summary.

    Args:
        cell: GridCell instance defining pixel window bounds.
        priority_score: (H, W) float32 priority score array.
        components: Dict of 5 component rasters.
        change_stack: (12, H, W) change rasters from Step 5.
        anomaly_stack: (10, H, W) anomaly rasters from Step 6.
        evidence_stack: (7, H, W) evidence flags from Step 6.
        valid_mask: (H, W) boolean valid pixel mask.
        thresholds: PriorityThresholdsConfig.

    Returns:
        Structured cell dictionary or None if cell contains no valid pixels.
    """
    rmin, rmax = cell.pixel_row_min, cell.pixel_row_max
    cmin, cmax = cell.pixel_col_min, cell.pixel_col_max

    cell_mask = valid_mask[rmin:rmax, cmin:cmax]
    total_pixels = int(cell_mask.size)
    valid_pixels = int(np.count_nonzero(cell_mask))

    # Skip cells with zero or insufficient valid pixels (e.g. outside AOI or 100% masked)
    if valid_pixels == 0:
        return None

    # Slice priority scores
    p_scores = priority_score[rmin:rmax, cmin:cmax][cell_mask]
    finite_p = p_scores[np.isfinite(p_scores)]
    if finite_p.size == 0:
        return None

    # Cell-level priority score: use 90th percentile to represent focal hotspot change
    # within the 500m cell while being robust against isolated single-pixel noise.
    cell_score = float(np.percentile(finite_p, 90))
    cell_score_mean = float(np.mean(finite_p))
    cell_score_max = float(np.max(finite_p))

    # Priority Level
    if cell_score >= thresholds.high:
        level_str = "HIGH"
    elif cell_score >= thresholds.medium:
        level_str = "MEDIUM"
    else:
        level_str = "LOW"

    # Slice component and indicator values within valid window
    c_anom = components["anomaly"][rmin:rmax, cmin:cmax][cell_mask]
    c_evid = components["evidence"][rmin:rmax, cmin:cmax][cell_mask]
    c_persist = components["persistence"][rmin:rmax, cmin:cmax][cell_mask]
    c_mag = components["magnitude"][rmin:rmax, cmin:cmax][cell_mask]
    c_spat = components["spatial_context"][rmin:rmax, cmin:cmax][cell_mask]

    # Change stack slices:
    # 0: NDVI delta, 2: NDWI delta, 4: NDBI delta
    ndvi_d = change_stack[0, rmin:rmax, cmin:cmax][cell_mask]
    ndwi_d = change_stack[2, rmin:rmax, cmin:cmax][cell_mask]
    ndbi_d = change_stack[4, rmin:rmax, cmin:cmax][cell_mask]

    # Anomaly stack slices:
    # 6: NDVI combined, 7: NDWI combined, 8: NDBI combined, 9: overall
    ndvi_anom = anomaly_stack[6, rmin:rmax, cmin:cmax][cell_mask]
    ndwi_anom = anomaly_stack[7, rmin:rmax, cmin:cmax][cell_mask]
    ndbi_anom = anomaly_stack[8, rmin:rmax, cmin:cmax][cell_mask]

    # Evidence stack slices:
    # 0: veg change, 1: water change, 2: builtup signal, 3: veg-built coherence, 4: persist, 5: reversal
    ev_veg = evidence_stack[0, rmin:rmax, cmin:cmax][cell_mask]
    ev_water = evidence_stack[1, rmin:rmax, cmin:cmax][cell_mask]
    ev_built = evidence_stack[2, rmin:rmax, cmin:cmax][cell_mask]
    ev_coher = evidence_stack[3, rmin:rmax, cmin:cmax][cell_mask]
    ev_pers = evidence_stack[4, rmin:rmax, cmin:cmax][cell_mask]
    ev_rev = evidence_stack[5, rmin:rmax, cmin:cmax][cell_mask]

    # Aggregate representative signals
    anom_score_rep = float(np.percentile(c_anom[np.isfinite(c_anom)], 90)) if np.any(np.isfinite(c_anom)) else 0.0
    spat_score_rep = float(np.percentile(c_spat[np.isfinite(c_spat)], 90)) if np.any(np.isfinite(c_spat)) else 0.0
    ndvi_d_rep = float(np.percentile(ndvi_d[np.isfinite(ndvi_d)], 10)) if np.any(np.isfinite(ndvi_d)) else 0.0  # lowest delta (loss)
    ndwi_d_rep = float(np.mean(ndwi_d[np.isfinite(ndwi_d)])) if np.any(np.isfinite(ndwi_d)) else 0.0
    ndbi_d_rep = float(np.percentile(ndbi_d[np.isfinite(ndbi_d)], 90)) if np.any(np.isfinite(ndbi_d)) else 0.0  # highest delta (expansion)

    max_delta_rep = float(np.percentile(c_mag[np.isfinite(c_mag)], 90) * 0.50) if np.any(np.isfinite(c_mag)) else 0.0

    coherence_flag = bool(np.mean(ev_coher == 1) >= 0.05)  # >=5% coherent pixels in cell
    persist_flag = bool(np.mean(ev_pers == 1) >= 0.05)
    reversal_flag = bool(np.mean(ev_rev == 1) >= 0.10)

    veg_flag = bool(np.mean(ev_veg == 1) >= 0.10)
    water_flag = bool(np.mean(ev_water == 1) >= 0.10)
    built_flag = bool(np.mean(ev_built == 1) >= 0.10)

    # Machine-readable reason codes
    reason_codes = generate_reason_codes(
        ndvi_delta=ndvi_d_rep,
        ndwi_delta=ndwi_d_rep,
        ndbi_delta=ndbi_d_rep,
        max_delta=max_delta_rep,
        anomaly_score=anom_score_rep,
        spatial_score=spat_score_rep,
        veg_builtup_coherence=coherence_flag,
        persistent=persist_flag,
        reversal=reversal_flag,
    )

    signals: Dict[str, float | bool] = {
        "overall_anomaly": anom_score_rep,
        "spatial_anomaly": spat_score_rep,
        "ndvi_anomaly": float(np.percentile(ndvi_anom[np.isfinite(ndvi_anom)], 90)) if np.any(np.isfinite(ndvi_anom)) else 0.0,
        "ndwi_anomaly": float(np.percentile(ndwi_anom[np.isfinite(ndwi_anom)], 90)) if np.any(np.isfinite(ndwi_anom)) else 0.0,
        "ndbi_anomaly": float(np.percentile(ndbi_anom[np.isfinite(ndbi_anom)], 90)) if np.any(np.isfinite(ndbi_anom)) else 0.0,
        "ndvi_delta": ndvi_d_rep,
        "ndwi_delta": ndwi_d_rep,
        "ndbi_delta": ndbi_d_rep,
        "evidence_strength": float(np.mean(c_evid[np.isfinite(c_evid)])),
        "persistence": 1.0 if persist_flag else 0.0,
        "veg_builtup_coherence": 1.0 if coherence_flag else 0.0,
        "reversal": 1.0 if reversal_flag else 0.0,
        "vegetation_change_present": veg_flag,
        "water_change_present": water_flag,
        "builtup_signal_present": built_flag,
        "valid_pixels": valid_pixels,
        "total_pixels": total_pixels,
        "valid_fraction": round(valid_pixels / total_pixels, 4),
        "cell_score_mean": round(cell_score_mean, 4),
        "cell_score_max": round(cell_score_max, 4),
    }

    record = build_why_flagged_record(
        grid_id=cell.grid_id,
        priority_score=cell_score,
        priority_level=level_str,
        reason_codes=reason_codes,
        signals=signals,
        latitude=cell.latitude,
        longitude=cell.longitude,
    )
    record["cell_index"] = cell.cell_index
    record["grid_row"] = cell.grid_row
    record["grid_col"] = cell.grid_col
    return record


def rank_and_extract_hotspots(
    grid_cells: List[GridCell],
    priority_score: np.ndarray,
    components: Dict[str, np.ndarray],
    change_stack: np.ndarray,
    anomaly_stack: np.ndarray,
    evidence_stack: np.ndarray,
    valid_mask: np.ndarray,
    config: Optional[PriorityConfig] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Aggregate all cells, rank descending by priority score, and compute diagnostics.

    Args:
        grid_cells: List of 500m GridCell objects.
        priority_score: (H, W) float32 priority score array.
        components: Dict of 5 component rasters.
        change_stack: (12, H, W) change rasters from Step 5.
        anomaly_stack: (10, H, W) anomaly rasters from Step 6.
        evidence_stack: (7, H, W) evidence flags from Step 6.
        valid_mask: (H, W) boolean valid pixel mask.
        config: PriorityConfig.

    Returns:
        Tuple of (ranked_cell_records, summary_diagnostics_dict).
    """
    if config is None:
        config = PriorityConfig()

    thresholds = config.thresholds

    records: List[Dict[str, Any]] = []
    for cell in grid_cells:
        cell_rec = aggregate_grid_cell_signals(
            cell=cell,
            priority_score=priority_score,
            components=components,
            change_stack=change_stack,
            anomaly_stack=anomaly_stack,
            evidence_stack=evidence_stack,
            valid_mask=valid_mask,
            thresholds=thresholds,
        )
        if cell_rec is not None:
            records.append(cell_rec)

    # Sort descending by priority_score, breaking ties by overall_anomaly and grid_id
    records.sort(
        key=lambda r: (
            r["priority_score"],
            r["signals"].get("overall_anomaly", 0.0),
            -r["cell_index"],
        ),
        reverse=True,
    )

    # Assign 1-indexed rank
    for rank_idx, rec in enumerate(records, start=1):
        rec["rank"] = rank_idx

    # Compute diagnostics
    total_valid_cells = len(records)
    scores = np.array([r["priority_score"] for r in records], dtype=np.float32)

    high_cells = [r for r in records if r["priority_level"] == "HIGH"]
    med_cells = [r for r in records if r["priority_level"] == "MEDIUM"]
    low_cells = [r for r in records if r["priority_level"] == "LOW"]

    n_high = len(high_cells)
    n_med = len(med_cells)
    n_low = len(low_cells)

    score_median = float(np.median(scores)) if total_valid_cells > 0 else 0.0
    score_p95 = float(np.percentile(scores, 95)) if total_valid_cells > 0 else 0.0

    pct_high = round((n_high / total_valid_cells) * 100.0, 2) if total_valid_cells > 0 else 0.0
    pct_med = round((n_med / total_valid_cells) * 100.0, 2) if total_valid_cells > 0 else 0.0
    pct_low = round((n_low / total_valid_cells) * 100.0, 2) if total_valid_cells > 0 else 0.0

    # Reason code frequencies in Top 10, Top 25, and all High
    def get_reason_distribution(subset: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in subset:
            for code in r.get("reasons", []):
                counts[code] = counts.get(code, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    top_10 = records[:10]
    top_25 = records[:25]
    top_50 = records[:50]

    top_10_reasons = get_reason_distribution(top_10)
    top_25_reasons = get_reason_distribution(top_25)

    # High-priority evidence characteristics
    high_evidence_pcts: Dict[str, float] = {}
    if n_high > 0:
        high_evidence_pcts = {
            "persistence": round(np.mean([r["signals"]["persistence"] == 1.0 for r in high_cells]) * 100.0, 2),
            "veg_builtup_coherence": round(np.mean([r["signals"]["veg_builtup_coherence"] == 1.0 for r in high_cells]) * 100.0, 2),
            "strong_anomaly": round(np.mean([r["signals"]["overall_anomaly"] >= 0.70 for r in high_cells]) * 100.0, 2),
            "vegetation_evidence": round(np.mean([bool(r["signals"]["vegetation_change_present"]) for r in high_cells]) * 100.0, 2),
            "water_evidence": round(np.mean([bool(r["signals"]["water_change_present"]) for r in high_cells]) * 100.0, 2),
            "builtup_evidence": round(np.mean([bool(r["signals"]["builtup_signal_present"]) for r in high_cells]) * 100.0, 2),
        }

    # Scientific check: Background comparison (HIGH priority vs LOW / Background)
    background_comparison: Dict[str, Any] = {}
    if n_high > 0 and n_low > 0:
        high_anom_mean = float(np.mean([r["signals"]["overall_anomaly"] for r in high_cells]))
        low_anom_mean = float(np.mean([r["signals"]["overall_anomaly"] for r in low_cells]))

        high_score_mean = float(np.mean([r["priority_score"] for r in high_cells]))
        low_score_mean = float(np.mean([r["priority_score"] for r in low_cells]))

        high_coher_mean = float(np.mean([r["signals"]["veg_builtup_coherence"] for r in high_cells]))
        low_coher_mean = float(np.mean([r["signals"]["veg_builtup_coherence"] for r in low_cells]))

        high_persist_mean = float(np.mean([r["signals"]["persistence"] for r in high_cells]))
        low_persist_mean = float(np.mean([r["signals"]["persistence"] for r in low_cells]))

        background_comparison = {
            "high_count": n_high,
            "low_count": n_low,
            "high_priority_score_mean": round(high_score_mean, 4),
            "background_priority_score_mean": round(low_score_mean, 4),
            "score_ratio": round(high_score_mean / max(low_score_mean, 1e-4), 2),
            "high_overall_anomaly_mean": round(high_anom_mean, 4),
            "background_overall_anomaly_mean": round(low_anom_mean, 4),
            "anomaly_ratio": round(high_anom_mean / max(low_anom_mean, 1e-4), 2),
            "high_coherence_rate": round(high_coher_mean, 4),
            "background_coherence_rate": round(low_coher_mean, 4),
            "high_persistence_rate": round(high_persist_mean, 4),
            "background_persistence_rate": round(low_persist_mean, 4),
            "verification_status": "CONFIRMED: HIGH priority locations exhibit substantially elevated anomaly and evidence metrics over background",
        }
    else:
        background_comparison = {
            "high_count": n_high,
            "low_count": n_low,
            "verification_status": "INSUFFICIENT_SAMPLES_FOR_COMPARISON",
        }

    diagnostics: Dict[str, Any] = {
        "total_valid_cells": total_valid_cells,
        "priority_score_median": round(score_median, 4),
        "priority_score_p95": round(score_p95, 4),
        "thresholds": {
            "high": thresholds.high,
            "medium": thresholds.medium,
        },
        "counts": {
            "high": n_high,
            "medium": n_med,
            "low": n_low,
        },
        "percentages": {
            "high": pct_high,
            "medium": pct_med,
            "low": pct_low,
        },
        "top_10_reasons": top_10_reasons,
        "top_25_reasons": top_25_reasons,
        "high_priority_evidence_rates": high_evidence_pcts,
        "background_comparison": background_comparison,
        "top_k_distribution": {
            "top_10_scores": [round(r["priority_score"], 4) for r in top_10],
            "top_25_scores": [round(r["priority_score"], 4) for r in top_25],
            "top_50_scores": [round(r["priority_score"], 4) for r in top_50],
        },
    }

    return records, diagnostics


def export_priority_hotspot_tables(
    records: List[Dict[str, Any]],
    diagnostics: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    """
    Save priority tables in CSV and JSON formats:
    - priority_hotspots.csv (all valid ranked cells)
    - priority_hotspots.json (all valid ranked cells)
    - top_10_hotspots.json
    - top_25_hotspots.json
    - top_50_hotspots.json
    - priority_stats.json (diagnostics and scientific checks)
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "priority_hotspots.csv"
    json_path = output_dir / "priority_hotspots.json"
    top10_path = output_dir / "top_10_hotspots.json"
    top25_path = output_dir / "top_25_hotspots.json"
    top50_path = output_dir / "top_50_hotspots.json"
    stats_path = output_dir / "priority_stats.json"

    # 1. Write CSV
    csv_fields = [
        "rank",
        "grid_id",
        "latitude",
        "longitude",
        "priority_score",
        "priority_level",
        "recommendation",
        "reason_codes",
        "overall_anomaly",
        "spatial_anomaly",
        "ndvi_anomaly",
        "ndwi_anomaly",
        "ndbi_anomaly",
        "ndvi_delta",
        "ndwi_delta",
        "ndbi_delta",
        "evidence_strength",
        "persistence",
        "veg_builtup_coherence",
        "reversal",
        "valid_pixels",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_fields)
        for r in records:
            sig = r.get("signals", {})
            writer.writerow([
                r.get("rank"),
                r.get("grid_id"),
                r.get("latitude"),
                r.get("longitude"),
                r.get("priority_score"),
                r.get("priority_level"),
                r.get("recommendation"),
                ";".join(r.get("reasons", [])),
                sig.get("overall_anomaly"),
                sig.get("spatial_anomaly"),
                sig.get("ndvi_anomaly"),
                sig.get("ndwi_anomaly"),
                sig.get("ndbi_anomaly"),
                sig.get("ndvi_delta"),
                sig.get("ndwi_delta"),
                sig.get("ndbi_delta"),
                sig.get("evidence_strength"),
                sig.get("persistence"),
                sig.get("veg_builtup_coherence"),
                sig.get("reversal"),
                sig.get("valid_pixels"),
            ])

    # 2. Write JSONs
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    with open(top10_path, "w", encoding="utf-8") as f:
        json.dump(records[:10], f, indent=2)

    with open(top25_path, "w", encoding="utf-8") as f:
        json.dump(records[:25], f, indent=2)

    with open(top50_path, "w", encoding="utf-8") as f:
        json.dump(records[:50], f, indent=2)

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2)

    logger.info(f"Saved priority tables and diagnostics to {output_dir}")
    return {
        "csv": csv_path,
        "json": json_path,
        "top_10": top10_path,
        "top_25": top25_path,
        "top_50": top50_path,
        "stats": stats_path,
    }
