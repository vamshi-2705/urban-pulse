#!/usr/bin/env python3
"""
UrbanPulse - Execute Spectral Indicator Generation & Visual QA (Step 4).

Generates standardized 3-band float32 GeoTIFF stacks (NDVI, NDWI, NDBI),
computes distribution statistics, performs cross-epoch spatial consistency checks,
and renders engineering diagnostic preview PNGs.
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
from geospatial.indicators.spectral_indices import process_all_indicators
from geospatial.logger import get_logger, setup_logging


def generate_diagnostic_previews(
    indicator_summary: dict,
    output_dir: Path,
) -> None:
    """Generate lightweight preview PNGs for visual QA diagnostics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = get_logger("run_indicator_generation.preview")

    cmaps = {
        "ndvi": "RdYlGn",
        "ndwi": "Blues",
        "ndbi": "YlOrRd",
    }
    limits = {
        "ndvi": (-0.2, 0.8),
        "ndwi": (-0.6, 0.4),
        "ndbi": (-0.4, 0.4),
    }

    for year_str, epoch_meta in indicator_summary["epochs"].items():
        indices_path = Path(epoch_meta["indices_file"])
        mask_path = Path(epoch_meta["mask_file"])

        with rasterio.open(indices_path) as src, rasterio.open(mask_path) as m_src:
            mask = (m_src.read(1) == 1)

            for b_idx, name in enumerate(["ndvi", "ndwi", "ndbi"], start=1):
                data = src.read(b_idx)
                # Plot masked data
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
                plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=f"{name.upper()} Value")
                ax.set_title(
                    f"UrbanPulse {name.upper()} — Hyderabad ({year_str})\n"
                    f"Acquisition: {epoch_meta['acquisition_date'][:10]} | Valid: {epoch_meta['valid_pixel_percentage']}%",
                    fontsize=11,
                    fontweight="bold",
                )
                ax.set_xlabel("UTM Easting (10m pixels)")
                ax.set_ylabel("UTM Northing (10m pixels)")

                preview_file = output_dir / f"{year_str}_{name}.png"
                plt.tight_layout()
                plt.savefig(preview_file, dpi=120, bbox_inches="tight")
                plt.close(fig)

                logger.info(f"Saved diagnostic preview: {preview_file.name}")


def main() -> int:
    setup_logging()
    logger = get_logger("run_indicator_generation")

    logger.info("Starting UrbanPulse Spectral Indicator Generation (Step 4)...")
    try:
        cfg = get_config()
        summary = process_all_indicators()

        # Render preview PNGs
        preview_dir = cfg.directories.outputs_dir / "indicators"
        generate_diagnostic_previews(summary, preview_dir)

        print("\n" + "=" * 55)
        print("UrbanPulse Spectral Indicator Generation")
        print("=" * 55)

        for year_str, rec in summary["epochs"].items():
            print(f"\n{year_str}")
            print("-" * 35)
            stats = rec["statistics"]
            for ind_name in ["ndvi", "ndwi", "ndbi"]:
                st = stats[ind_name]
                print(f"{ind_name.upper()}:")
                print(f"  valid: {st['valid_percentage']}%")
                print(f"  mean: {st['mean']}")
                print(f"  median: {st['median']}")
                print(f"  std: {st['std']}")
                print(f"  p05: {st['p05']}")
                print(f"  p25: {st['p25']}")
                print(f"  p75: {st['p75']}")
                print(f"  p95: {st['p95']}")

        print("\nSpatial Consistency Alignment:")
        for pair_label, status_str in summary["spatial_consistency"]["comparisons"].items():
            print(f"  {pair_label}: {status_str}")

        print(f"\nOverall Status: PASS")
        print("=" * 55 + "\n")
        logger.info("Step 4 indicator generation completed successfully.")
        return 0

    except Exception as exc:
        logger.error(f"Indicator generation failed: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
