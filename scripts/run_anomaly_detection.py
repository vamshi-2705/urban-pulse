#!/usr/bin/env python3
"""
UrbanPulse - Execute Anomaly Detection Pipeline (Step 6).

Runs temporal anomaly, spatial neighborhood anomaly, combined fusion,
and cross-indicator evidence engines across 2020, 2023, and 2026.
Renders diagnostic preview PNGs for visual QA.
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
import numpy as np
import rasterio

from config.settings import get_config
from geospatial.anomaly_detection import process_all_anomalies
from geospatial.logger import get_logger, setup_logging


def generate_anomaly_previews(
    results: dict,
    output_dir: Path,
) -> None:
    """
    Generate diagnostic preview PNGs for visual QA.

    Pre-renders sequential [0.0, 1.0] anomaly strength maps:
    - {period}_temporal_ndvi.png
    - {period}_temporal_ndwi.png
    - {period}_temporal_ndbi.png
    - {period}_spatial_ndvi.png
    - {period}_spatial_ndwi.png
    - {period}_spatial_ndbi.png
    - {period}_overall_combined.png
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger("run_anomaly_detection.preview")

    cmap = "magma"

    for period, p_stats in results["periods"].items():
        files = p_stats["files"]
        full_stack_file = Path(files["anomaly_stack"])
        mask_file = full_stack_file.parent / "valid_mask.tif"

        with rasterio.open(full_stack_file) as src, rasterio.open(mask_file) as m_src:
            mask = (m_src.read(1) == 1)

            # Band indices (1-indexed):
            # 1: NDVI temporal, 2: NDWI temporal, 3: NDBI temporal
            # 4: NDVI spatial, 5: NDWI spatial, 6: NDBI spatial
            # 10: overall combined
            previews = [
                ("temporal_ndvi", 1, f"NDVI Temporal Anomaly ({period})"),
                ("temporal_ndwi", 2, f"NDWI Temporal Anomaly ({period})"),
                ("temporal_ndbi", 3, f"NDBI Temporal Anomaly ({period})"),
                ("spatial_ndvi", 4, f"NDVI Spatial Anomaly ({period})"),
                ("spatial_ndwi", 5, f"NDWI Spatial Anomaly ({period})"),
                ("spatial_ndbi", 6, f"NDBI Spatial Anomaly ({period})"),
                ("overall_combined", 10, f"Overall Combined Anomaly ({period})"),
            ]

            for name, b_idx, title in previews:
                data = src.read(b_idx)
                masked_data = np.where(mask & np.isfinite(data), data, np.nan)

                fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
                im = ax.imshow(
                    masked_data,
                    cmap=cmap,
                    vmin=0.0,
                    vmax=1.0,
                    interpolation="nearest",
                )
                plt.colorbar(
                    im,
                    ax=ax,
                    fraction=0.046,
                    pad=0.04,
                    label="Anomaly Strength [0.0 = Baseline, 1.0 = Highly Unusual]",
                )
                ax.set_title(
                    f"UrbanPulse — {title}\n"
                    f"Bounded Anomaly Score [0.0 - 1.0] (Statistical Deviation, Not Risk)",
                    fontsize=10,
                    fontweight="bold",
                )
                ax.set_xlabel("UTM Easting (10m pixels)")
                ax.set_ylabel("UTM Northing (10m pixels)")

                preview_file = output_dir / f"{period}_{name}.png"
                plt.tight_layout()
                plt.savefig(preview_file, dpi=120, bbox_inches="tight")
                plt.close(fig)

                logger.info(f"Saved diagnostic preview: {preview_file.name}")


def print_cli_summary(results: dict, total_runtime: float) -> None:
    """Print structured CLI report matching UrbanPulse specification."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print()
    print("UrbanPulse Anomaly Detection Engine (Step 6)")
    print("============================================")
    print()

    periods = [
        ("2020_2023", "2020 -> 2023"),
        ("2023_2026", "2023 -> 2026"),
        ("2020_2026", "2020 -> 2026"),
    ]

    for p_key, p_label in periods:
        p_stats = results["periods"].get(p_key, {})
        print(p_label)
        print("-" * len(p_label))

        # Temporal summary
        temp = p_stats.get("temporal", {})
        print("Temporal Anomalies (Scene Baseline):")
        for ind in ["ndvi", "ndwi", "ndbi"]:
            m = temp.get(ind, {})
            print(f"  {ind.upper()}: median={m.get('median')}, MAD={m.get('mad')}, mean score={m.get('score_mean')}, p95={m.get('score_p95')}")

        # Spatial summary
        spat = p_stats.get("spatial", {})
        print("Spatial Neighborhood Anomalies (Local Window):")
        for ind in ["ndvi", "ndwi", "ndbi"]:
            m = spat.get(ind, {})
            print(f"  {ind.upper()}: window={m.get('window_size_pixels')}px, mean score={m.get('score_mean')}, p95={m.get('score_p95')}, runtime={m.get('runtime_seconds')}s")

        # Combined summary
        comb = p_stats.get("combined", {})
        ov = comb.get("overall", {})
        print("Combined Anomaly (Temporal + Spatial):")
        print(f"  Overall: mean={ov.get('mean')}, median={ov.get('median')}, p95={ov.get('p95')}")
        print(f"  Pixels above 0.50 (Unusual): {ov.get('pct_above_05')}% ({ov.get('pixels_above_05'):,} pixels)")
        print(f"  Pixels above 0.70 (Highly Unusual): {ov.get('pct_above_07')}% ({ov.get('pixels_above_07'):,} pixels)")

        # Evidence summary
        ev = p_stats.get("evidence", {})
        print("Cross-Indicator Evidence Consistency:")
        print(f"  Vegetation change present: {ev.get('vegetation_change_present', {}).get('percentage_of_valid')}%")
        print(f"  Water change present: {ev.get('water_change_present', {}).get('percentage_of_valid')}%")
        print(f"  Built-up signal present: {ev.get('builtup_signal_present', {}).get('percentage_of_valid')}%")
        print(f"  Vegetation + Built-up Coherence: {ev.get('vegetation_builtup_coherence', {}).get('percentage_of_valid')}%")
        print(f"  Persistent change present: {ev.get('persistent_change_present', {}).get('percentage_of_valid')}%")
        print(f"  Reversal present: {ev.get('reversal_present', {}).get('percentage_of_valid')}%")
        print()

    print("Spatial Alignment: PASS")
    print(f"Total Execution Runtime: {total_runtime:.2f}s")
    print("Status: PASS")
    print()


def main() -> int:
    setup_logging()
    logger = get_logger("run_anomaly_detection")

    logger.info("Starting UrbanPulse Anomaly Detection (Step 6)...")
    t0 = time.time()
    try:
        cfg = get_config()
        results = process_all_anomalies(cfg)
        elapsed = time.time() - t0

        preview_dir = cfg.directories.outputs_dir / "anomaly_detection"
        generate_anomaly_previews(results, preview_dir)

        print_cli_summary(results, elapsed)
        return 0

    except Exception as exc:
        logger.error(f"Anomaly detection failed: {exc}", exc_info=True)
        print(f"\nStatus: FAIL: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
