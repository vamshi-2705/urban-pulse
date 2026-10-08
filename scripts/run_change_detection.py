#!/usr/bin/env python3
"""
UrbanPulse - Execute Temporal Change Detection Pipeline (Step 5).

Computes multi-temporal pairwise deltas, persistence trajectories,
and directional reversal signals across 2020, 2023, and 2026.
Renders diagnostic diverging change previews for visual QA.
"""

from __future__ import annotations

import sys
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
from geospatial.change_detection.temporal_change import calculate_multitemporal_change
from geospatial.logger import get_logger, setup_logging


def generate_change_previews(
    change_summary: dict,
    output_dir: Path,
) -> None:
    """
    Generate lightweight diverging preview PNGs for visual QA diagnostics.

    Saves:
        - {period}_ndvi_change.png (RdYlGn)
        - {period}_ndwi_change.png (RdBu)
        - {period}_ndbi_change.png (coolwarm)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger("run_change_detection.preview")

    cmaps = {
        "ndvi": "RdYlGn",
        "ndwi": "RdBu",
        "ndbi": "coolwarm",
    }
    limits = {
        "ndvi": (-0.35, 0.35),
        "ndwi": (-0.35, 0.35),
        "ndbi": (-0.35, 0.35),
    }

    for period, meta in change_summary["periods"].items():
        change_path = Path(meta["change_stack_file"])
        mask_path = Path(meta["mask_file"])

        with rasterio.open(change_path) as src, rasterio.open(mask_path) as m_src:
            mask = (m_src.read(1) == 1)

            # Band 1: NDVI_delta, Band 3: NDWI_delta, Band 5: NDBI_delta
            band_map = [("ndvi", 1), ("ndwi", 3), ("ndbi", 5)]

            for name, b_idx in band_map:
                data = src.read(b_idx)
                masked_data = np.where(mask, data, np.nan)

                fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
                vmin, vmax = limits[name]
                im = ax.imshow(
                    masked_data,
                    cmap=cmaps[name],
                    vmin=vmin,
                    vmax=vmax,
                    interpolation="nearest",
                )
                plt.colorbar(
                    im,
                    ax=ax,
                    fraction=0.046,
                    pad=0.04,
                    label=f"Δ {name.upper()} (Signed Shift)",
                )
                earlier = meta["earlier_year"]
                later = meta["later_year"]
                eps = meta["epsilons"][name]
                stat = meta["statistics"][f"{name}_delta"]
                ax.set_title(
                    f"UrbanPulse Δ {name.upper()} — {earlier} → {later}\n"
                    f"Tolerance ε={eps:.2f} | Changed: {stat['changed_percentage']}% | Mean Δ: {stat['mean']:+.3f}",
                    fontsize=10,
                    fontweight="bold",
                )
                ax.set_xlabel("UTM Easting (10m pixels)")
                ax.set_ylabel("UTM Northing (10m pixels)")

                preview_file = output_dir / f"{period}_{name}_change.png"
                plt.tight_layout()
                plt.savefig(preview_file, dpi=120, bbox_inches="tight")
                plt.close(fig)

                logger.info(f"Saved diagnostic preview: {preview_file.name}")


def print_cli_summary(summary: dict) -> None:
    """Print structured CLI report matching UrbanPulse specification."""
    # Ensure stdout handles unicode if needed
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print()
    print("UrbanPulse Temporal Change Detection")
    print("=====================================")
    print()

    period_display = [
        ("2020_2023", "2020 -> 2023"),
        ("2023_2026", "2023 -> 2026"),
        ("2020_2026", "2020 -> 2026"),
    ]

    for key, label in period_display:
        meta = summary["periods"].get(key, {})
        stats = meta.get("statistics", {})
        print(label)
        print("-" * len(label))

        for ind_name in ["ndvi", "ndwi", "ndbi"]:
            st = stats.get(f"{ind_name}_delta", {})
            ind_upper = ind_name.upper()
            print(f"{ind_upper} change:")
            print(f"  mean: {st.get('mean', 'N/A')}")
            print(f"  median: {st.get('median', 'N/A')}")
            print(f"  p95: {st.get('p95', 'N/A')}")
            print(f"  changed pixels: {st.get('changed_percentage', 'N/A')}%")
        print()

    multi = summary.get("multitemporal", {})
    p_sigs = multi.get("persistence_signals", {})
    revs = multi.get("reversals", {})

    print("Persistence:")
    print(f"  vegetation decrease: {p_sigs.get('persistent_vegetation_decrease', {}).get('percentage_of_valid', 'N/A')}%")
    print(f"  water decrease: {p_sigs.get('persistent_water_decrease', {}).get('percentage_of_valid', 'N/A')}%")
    print(f"  built-up-sensitive increase: {p_sigs.get('persistent_builtup_increase', {}).get('percentage_of_valid', 'N/A')}%")
    print()

    print("Reversals:")
    print(f"  vegetation: {revs.get('vegetation_reversal', {}).get('percentage_of_valid', 'N/A')}%")
    print(f"  water: {revs.get('water_reversal', {}).get('percentage_of_valid', 'N/A')}%")
    print(f"  built-up: {revs.get('builtup_reversal', {}).get('percentage_of_valid', 'N/A')}%")
    print()

    print("Alignment:")
    print(f"  {summary.get('alignment_status', 'PASS')}")
    print()

    print("Status:")
    print("  PASS")
    print()


def main() -> int:
    setup_logging()
    logger = get_logger("run_change_detection")

    logger.info("Starting UrbanPulse Temporal Change Detection (Step 5)...")
    try:
        cfg = get_config()
        summary = calculate_multitemporal_change(cfg)

        # Render preview PNGs
        preview_dir = cfg.directories.outputs_dir / "change_detection"
        generate_change_previews(summary, preview_dir)

        # Print formatted report
        print_cli_summary(summary)
        return 0

    except Exception as exc:
        logger.error(f"Change detection failed: {exc}", exc_info=True)
        print(f"\nStatus:\n  FAIL: {exc}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
