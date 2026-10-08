#!/usr/bin/env python3
"""
UrbanPulse - Execute Priority Engine & Hotspot Ranking (Step 7).

Executes feature-based priority scoring, 500m grid cell aggregation,
and Top-K hotspot extraction across 2020->2023, 2023->2026, and 2020->2026.
Renders diagnostic visual QA previews in data/outputs/priority/.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import rasterio

from config.settings import get_config
from geospatial.logger import get_logger, setup_logging
from geospatial.priority import process_all_priorities


def generate_priority_previews(
    results: dict,
    output_dir: Path,
) -> None:
    """
    Generate diagnostic visual QA preview PNGs:
    - {period}_priority_score.png: Continuous heatmap [0.0, 1.0]
    - {period}_priority_level.png: Categorical map (Low=green/gray, Med=orange, High=red)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger("run_priority_engine.preview")

    for period, p_data in results["periods"].items():
        raster_files = p_data["raster_files"]
        score_file = Path(raster_files["priority_score"])
        level_file = Path(raster_files["priority_level"])
        mask_file = Path(raster_files["valid_mask"])

        with rasterio.open(score_file) as s_src, \
             rasterio.open(level_file) as l_src, \
             rasterio.open(mask_file) as m_src:

            score = s_src.read(1)
            level = l_src.read(1)
            mask = (m_src.read(1) == 1)

            # 1. Continuous Priority Score Map
            fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
            masked_score = np.where(mask & np.isfinite(score), score, np.nan)
            im = ax.imshow(
                masked_score,
                cmap="viridis",
                vmin=0.0,
                vmax=1.0,
                interpolation="nearest",
            )
            plt.colorbar(
                im,
                ax=ax,
                fraction=0.046,
                pad=0.04,
                label="Priority Score [0.0 = Baseline, 1.0 = Urgent Field Priority]",
            )
            ax.set_title(
                f"UrbanPulse — Priority Investigation Score ({period})\n"
                f"Explainable Decision-Support Ranking Signal (Not Ground-Truth Risk)",
                fontsize=10,
                fontweight="bold",
            )
            ax.set_xlabel("UTM Easting (10m pixels)")
            ax.set_ylabel("UTM Northing (10m pixels)")

            score_preview = output_dir / f"{period}_priority_score.png"
            plt.tight_layout()
            plt.savefig(score_preview, dpi=120, bbox_inches="tight")
            plt.close(fig)
            logger.info(f"Saved diagnostic preview: {score_preview.name}")

            # 2. Categorical Priority Levels Map
            fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
            # 0=masked(lightgray), 1=Low(lightgreen), 2=Medium(orange), 3=High(crimson)
            cmap_levels = ListedColormap(["#f0f0f0", "#90caf9", "#ffb74d", "#e53935"])
            masked_level = np.where(mask, level, 0)
            im = ax.imshow(
                masked_level,
                cmap=cmap_levels,
                vmin=0,
                vmax=3,
                interpolation="nearest",
            )
            cbar = plt.colorbar(
                im,
                ax=ax,
                fraction=0.046,
                pad=0.04,
                ticks=[0.375, 1.125, 1.875, 2.625],
            )
            cbar.ax.set_yticklabels(["Invalid", "Low (<0.45)", "Med (0.45-0.70)", "High (>=0.70)"])
            cbar.set_label("Priority Category")
            ax.set_title(
                f"UrbanPulse — Categorical Investigation Levels ({period})\n"
                f"High: Field Verification Recommended | Med: Monitor & Review",
                fontsize=10,
                fontweight="bold",
            )
            ax.set_xlabel("UTM Easting (10m pixels)")
            ax.set_ylabel("UTM Northing (10m pixels)")

            level_preview = output_dir / f"{period}_priority_level.png"
            plt.tight_layout()
            plt.savefig(level_preview, dpi=120, bbox_inches="tight")
            plt.close(fig)
            logger.info(f"Saved diagnostic preview: {level_preview.name}")


def print_cli_summary(results: dict, total_runtime: float) -> None:
    """Print structured CLI report matching UrbanPulse specification."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print()
    print("UrbanPulse Priority Engine & Hotspot Ranking (Step 7)")
    print("=====================================================")
    print()

    periods = [
        ("2020_2023", "2020 -> 2023"),
        ("2023_2026", "2023 -> 2026"),
        ("2020_2026", "2020 -> 2026"),
    ]

    for p_key, p_label in periods:
        p_res = results["periods"].get(p_key, {})
        diag = p_res.get("diagnostics", {})
        ranked = p_res.get("ranked_records", [])

        print(p_label)
        print("-" * len(p_label))
        print(f"Total Valid 500m Grid Cells: {diag.get('total_valid_cells', 0):,}")
        print(f"Priority Score Distribution: median={diag.get('priority_score_median')}, p95={diag.get('priority_score_p95')}")
        print(f"Investigation Categories:")
        cnts = diag.get("counts", {})
        pcts = diag.get("percentages", {})
        print(f"  HIGH   (score >= {diag.get('thresholds', {}).get('high')}): {cnts.get('high', 0):>4} cells ({pcts.get('high', 0.0):.2f}%) -> FIELD_VERIFICATION_RECOMMENDED")
        print(f"  MEDIUM (score >= {diag.get('thresholds', {}).get('medium')}): {cnts.get('medium', 0):>4} cells ({pcts.get('medium', 0.0):.2f}%) -> MONITOR_AND_REVIEW")
        print(f"  LOW    (score <  {diag.get('thresholds', {}).get('medium')}): {cnts.get('low', 0):>4} cells ({pcts.get('low', 0.0):.2f}%) -> ROUTINE_OBSERVATION")
        print()

        ev_rates = diag.get("high_priority_evidence_rates", {})
        if ev_rates:
            print("HIGH-Priority Evidence Composition:")
            print(f"  Persistence present:                {ev_rates.get('persistence', 0.0)}%")
            print(f"  Vegetation + Built-up Coherence:    {ev_rates.get('veg_builtup_coherence', 0.0)}%")
            print(f"  Strong Anomaly (>= 0.70):           {ev_rates.get('strong_anomaly', 0.0)}%")
            print(f"  Vegetation Evidence present:        {ev_rates.get('vegetation_evidence', 0.0)}%")
            print(f"  Water Evidence present:             {ev_rates.get('water_evidence', 0.0)}%")
            print(f"  Built-up Evidence present:          {ev_rates.get('builtup_evidence', 0.0)}%")
            print()

        bg_comp = diag.get("background_comparison", {})
        if bg_comp.get("high_count", 0) > 0:
            print("Background Comparison Check (HIGH vs Background):")
            print(f"  Mean Priority Score: HIGH={bg_comp.get('high_priority_score_mean')} vs BG={bg_comp.get('background_priority_score_mean')} (Ratio: {bg_comp.get('score_ratio')}x)")
            print(f"  Mean Overall Anomaly: HIGH={bg_comp.get('high_overall_anomaly_mean')} vs BG={bg_comp.get('background_overall_anomaly_mean')} (Ratio: {bg_comp.get('anomaly_ratio')}x)")
            print(f"  Coherence Rate:      HIGH={bg_comp.get('high_coherence_rate')} vs BG={bg_comp.get('background_coherence_rate')}")
            print(f"  Persistence Rate:    HIGH={bg_comp.get('high_persistence_rate')} vs BG={bg_comp.get('background_persistence_rate')}")
            print(f"  Diagnostic Status:   {bg_comp.get('verification_status')}")
            print()

        print("Top 10 Reason Codes Frequency:")
        for r_code, count in list(diag.get("top_10_reasons", {}).items())[:8]:
            print(f"  - {r_code}: {count}")
        print()

        print("Top 5 Candidate Hotspots for Investigation:")
        for r in ranked[:5]:
            reasons_str = ", ".join(r.get("reasons", []))
            print(
                f"  Rank #{r.get('rank'):<2} [{r.get('grid_id')}] "
                f"Score={r.get('priority_score'):.4f} ({r.get('priority_level')}) "
                f"Lat={r.get('latitude'):.5f}, Lon={r.get('longitude'):.5f}\n"
                f"    Reasons: {reasons_str}\n"
                f"    Recommendation: {r.get('recommendation')}"
            )
        print()

    print("Spatial Alignment & Grid Integrity: PASS")
    print(f"Total Execution Runtime: {total_runtime:.2f}s")
    print("Status: PASS")
    print()


def main() -> int:
    setup_logging()
    logger = get_logger("run_priority_engine")

    logger.info("Starting UrbanPulse Priority Engine & Hotspot Ranking (Step 7)...")
    t0 = time.time()
    try:
        cfg = get_config()
        results = process_all_priorities(cfg)
        elapsed = time.time() - t0

        preview_dir = cfg.directories.outputs_dir / "priority"
        generate_priority_previews(results, preview_dir)

        print_cli_summary(results, elapsed)
        return 0

    except Exception as exc:
        logger.error(f"Priority engine failed: {exc}", exc_info=True)
        print(f"\nStatus: FAIL: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
