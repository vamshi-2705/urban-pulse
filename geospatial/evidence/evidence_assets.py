"""
UrbanPulse - Evidence Asset Generation Engine (Step 9).

Extracts georeferenced spatial crops around high-priority candidate hotspots
and renders production-ready visual evidence products for judge / field review:
- Before & After Natural Color (RGB: B04, B03, B02) with calibrated reflectance stretch
- Before & After NDVI canopy vigor maps
- NDVI, NDWI, and NDBI delta change maps
- Multi-spectral combined evidence map with scientifically cautious categorization
- JSON metadata and global evidence manifest for frontend / backend integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.windows import Window, from_bounds

from config.settings import AppConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.evidence.evidence_assets")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_acquisition_dates(
    before_year: int,
    after_year: int,
    processed_dir: Path,
) -> Tuple[str, str]:
    """
    Read verified Sentinel-2 acquisition ISO timestamps from ARD metadata.
    """
    meta_before_file = processed_dir / "sentinel2" / str(before_year) / "metadata.json"
    meta_after_file = processed_dir / "sentinel2" / str(after_year) / "metadata.json"

    before_date = f"{before_year}-01-01T00:00:00Z"
    after_date = f"{after_year}-01-01T00:00:00Z"

    if meta_before_file.exists():
        with open(meta_before_file, encoding="utf-8") as f:
            meta = json.load(f)
            before_date = meta.get("acquisition_date", before_date)

    if meta_after_file.exists():
        with open(meta_after_file, encoding="utf-8") as f:
            meta = json.load(f)
            after_date = meta.get("acquisition_date", after_date)

    return before_date, after_date


def get_hotspot_coordinates(
    grid_id: str,
    period: str,
    outputs_dir: Path,
    processed_dir: Path,
) -> Tuple[float, float, int]:
    """
    Find hotspot centroid (latitude, longitude) and rank from processed or API files.
    """
    # 1. Try API hotspots
    api_file = outputs_dir / "api" / f"hotspots_{period}.json"
    if api_file.exists():
        with open(api_file, encoding="utf-8") as f:
            hotspots = json.load(f)
        for h in hotspots:
            if h.get("grid_id") == grid_id:
                return float(h["latitude"]), float(h["longitude"]), int(h.get("rank", 1))

    # 2. Try priority processed hotspots
    prio_file = processed_dir / "priority" / period / "priority_hotspots.json"
    if prio_file.exists():
        with open(prio_file, encoding="utf-8") as f:
            hotspots = json.load(f)
        for h in hotspots:
            if h.get("grid_id") == grid_id:
                return float(h["latitude"]), float(h["longitude"]), int(h.get("rank", 1))

    raise ValueError(f"Hotspot '{grid_id}' not found for period '{period}'")


def compute_raster_crop_window(
    center_lon: float,
    center_lat: float,
    window_meters: float,
    raster_src: rasterio.io.DatasetReader,
    crs_geo: str = "EPSG:4326",
    crs_proj: str = "EPSG:32644",
) -> Tuple[Window, Any, Tuple[float, float]]:
    """
    Compute integer pixel Window clamped to raster bounds and resulting affine transform.

    Returns:
        Tuple of (clamped_window, crop_transform, (center_x_utm, center_y_utm)).
    """
    transformer = Transformer.from_crs(crs_geo, crs_proj, always_xy=True)
    xc, yc = transformer.transform(center_lon, center_lat)

    half_w = window_meters / 2.0
    win_bounds = (xc - half_w, yc - half_w, xc + half_w, yc + half_w)

    raw_window = from_bounds(*win_bounds, transform=raster_src.transform)

    # Clamp integer offsets safely against raster edges
    col_off = max(0, int(round(raw_window.col_off)))
    row_off = max(0, int(round(raw_window.row_off)))
    width = max(1, min(raster_src.width - col_off, int(round(raw_window.width))))
    height = max(1, min(raster_src.height - row_off, int(round(raw_window.height))))

    int_window = Window(col_off=col_off, row_off=row_off, width=width, height=height)
    crop_transform = raster_src.window_transform(int_window)

    return int_window, crop_transform, (xc, yc)


def stretch_rgb_reflectance(
    red: np.ndarray,
    green: np.ndarray,
    blue: np.ndarray,
    max_reflectance: float = 0.35,
) -> np.ndarray:
    """
    Calibrate surface reflectance to [0.0, 1.0] natural color display stretch.
    """
    rgb = np.stack([red, green, blue], axis=-1).astype(np.float32)
    # Replace non-finite pixels with 0.0
    rgb = np.where(np.isfinite(rgb), rgb, 0.0)
    # Natural stretch clipping bright cloud/roof outliers
    stretched = np.clip(rgb / max_reflectance, 0.0, 1.0)
    return stretched


def render_rgb_preview(
    rgb_stretched: np.ndarray,
    title: str,
    subtitle: str,
    output_path: Path,
) -> None:
    """Render and save RGB natural color preview PNG."""
    fig, ax = plt.subplots(figsize=(6, 6), dpi=120)
    ax.imshow(rgb_stretched, interpolation="bilinear")
    ax.set_title(f"{title}\n{subtitle}", fontsize=9, fontweight="bold", pad=8)
    ax.set_xlabel("UTM Easting Window (10m pixels)", fontsize=8)
    ax.set_ylabel("UTM Northing Window (10m pixels)", fontsize=8)
    ax.grid(color="white", alpha=0.15, linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def render_single_index_preview(
    index_data: np.ndarray,
    title: str,
    subtitle: str,
    cmap: str,
    vmin: float,
    vmax: float,
    colorbar_label: str,
    output_path: Path,
) -> None:
    """Render continuous indicator / delta change map with calibrated colorbar."""
    fig, ax = plt.subplots(figsize=(6.2, 5.5), dpi=120)
    masked_data = np.where(np.isfinite(index_data), index_data, np.nan)
    im = ax.imshow(masked_data, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(colorbar_label, fontsize=8)
    ax.set_title(f"{title}\n{subtitle}", fontsize=9, fontweight="bold", pad=8)
    ax.set_xlabel("UTM Easting Window (10m pixels)", fontsize=8)
    ax.set_ylabel("UTM Northing Window (10m pixels)", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def render_combined_evidence_preview(
    ndvi_delta: np.ndarray,
    ndwi_delta: np.ndarray,
    ndbi_delta: np.ndarray,
    title: str,
    subtitle: str,
    output_path: Path,
) -> Dict[str, Any]:
    """
    Render categorical multi-indicator evidence map with scientifically cautious legend.

    Categories:
    0: Stable baseline / minor variation (Light Gray)
    1: Coherent transition (Vegetation decrease + Built-up-sensitive increase) (Crimson)
    2: Built-up-sensitive spectral increase only (Amber Orange)
    3: Vegetation decrease only (Brown/Muted Green)
    4: Vegetation increase (Emerald Green)
    5: Water-body / moisture spectral change (Azure Blue)
    """
    coherent = (ndvi_delta <= -0.15) & (ndbi_delta >= 0.15)
    built_only = (ndbi_delta >= 0.15) & ~coherent
    veg_loss_only = (ndvi_delta <= -0.15) & ~coherent
    veg_gain = (ndvi_delta >= 0.15)
    water_chg = (np.abs(ndwi_delta) >= 0.15) & ~coherent

    evidence_map = np.zeros(ndvi_delta.shape, dtype=np.uint8)
    evidence_map[water_chg] = 5
    evidence_map[veg_gain] = 4
    evidence_map[veg_loss_only] = 3
    evidence_map[built_only] = 2
    evidence_map[coherent] = 1

    cmap = ListedColormap([
        "#f5f5f5",  # 0: Stable
        "#d32f2f",  # 1: Coherent transition (Veg decrease + Built-up increase)
        "#f57c00",  # 2: Built-up-sensitive increase
        "#8d6e63",  # 3: Vegetation decrease
        "#2e7d32",  # 4: Vegetation increase
        "#0288d1",  # 5: Water / moisture change
    ])

    fig, ax = plt.subplots(figsize=(6.5, 6), dpi=120)
    ax.imshow(evidence_map, cmap=cmap, vmin=0, vmax=5, interpolation="nearest")
    ax.set_title(f"{title}\n{subtitle}", fontsize=9, fontweight="bold", pad=8)
    ax.set_xlabel("UTM Easting Window (10m pixels)", fontsize=8)
    ax.set_ylabel("UTM Northing Window (10m pixels)", fontsize=8)

    patches = [
        mpatches.Patch(color="#d32f2f", label="Coherent (Veg Loss + Built-up Increase)"),
        mpatches.Patch(color="#f57c00", label="Built-up-Sensitive Spectral Increase"),
        mpatches.Patch(color="#8d6e63", label="Vegetation Decrease"),
        mpatches.Patch(color="#2e7d32", label="Vegetation Increase"),
        mpatches.Patch(color="#0288d1", label="Water-Body Spectral Change"),
        mpatches.Patch(color="#f5f5f5", label="Stable / Minor Surface Variation"),
    ]
    ax.legend(
        handles=patches,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=2,
        fontsize=7,
        frameon=True,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    total_px = int(evidence_map.size)
    coherent_px = int(np.count_nonzero(coherent))
    return {
        "total_pixels": total_px,
        "coherent_pixels": coherent_px,
        "coherent_fraction": round(coherent_px / max(1, total_px), 4),
        "built_only_pixels": int(np.count_nonzero(built_only)),
        "veg_loss_pixels": int(np.count_nonzero(veg_loss_only)),
        "veg_gain_pixels": int(np.count_nonzero(veg_gain)),
        "water_change_pixels": int(np.count_nonzero(water_chg)),
    }


def generate_hotspot_evidence(
    grid_id: str,
    period: str,
    window_meters: float = 1000.0,
    output_base_dir: Optional[Path] = None,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Generate production-quality visual evidence assets for a single hotspot.

    Args:
        grid_id: Hotspot ID (e.g. 'HYD_1220').
        period: Observation interval (e.g. '2020_2026').
        window_meters: Physical extent of crop box (default 1000m x 1000m).
        output_base_dir: Base directory for evidence outputs (default data/outputs/evidence).
        config: Optional AppConfig.

    Returns:
        Metadata dictionary with asset paths and scientific metrics.
    """
    if config is None:
        config = get_config()

    parts = period.split("_")
    if len(parts) != 2:
        raise ValueError(f"Invalid period format: '{period}'. Expected 'YYYY_YYYY'.")
    y_before, y_after = int(parts[0]), int(parts[1])

    processed_dir = config.directories.processed_dir
    outputs_dir = config.directories.outputs_dir
    evidence_base = output_base_dir or (outputs_dir / "evidence")

    target_dir = evidence_base / period / grid_id
    target_dir.mkdir(parents=True, exist_ok=True)

    center_lat, center_lon, rank = get_hotspot_coordinates(
        grid_id=grid_id,
        period=period,
        outputs_dir=outputs_dir,
        processed_dir=processed_dir,
    )

    before_date, after_date = get_acquisition_dates(y_before, y_after, processed_dir)
    b_date_str = before_date.split("T")[0]
    a_date_str = after_date.split("T")[0]

    # File paths for underlying rasters
    s2_before_file = processed_dir / "sentinel2" / str(y_before) / "scene_stack.tif"
    s2_after_file = processed_dir / "sentinel2" / str(y_after) / "scene_stack.tif"
    ind_before_file = processed_dir / "indicators" / str(y_before) / "indices.tif"
    ind_after_file = processed_dir / "indicators" / str(y_after) / "indices.tif"
    change_file = processed_dir / "change_detection" / period / "change_stack.tif"

    for req_file in [s2_before_file, s2_after_file, ind_before_file, ind_after_file, change_file]:
        if not req_file.exists():
            raise FileNotFoundError(f"Missing required raster asset: {req_file}")

    # 1. Read S2 Before and compute window
    with rasterio.open(s2_before_file) as src_s2_b:
        win, crop_transform, (xc, yc) = compute_raster_crop_window(
            center_lon=center_lon,
            center_lat=center_lat,
            window_meters=window_meters,
            raster_src=src_s2_b,
        )
        s2_b_data = src_s2_b.read(window=win)

    # 2. Read S2 After
    with rasterio.open(s2_after_file) as src_s2_a:
        s2_a_data = src_s2_a.read(window=win)

    # 3. Read Indicators Before & After
    with rasterio.open(ind_before_file) as src_ind_b:
        ind_b_data = src_ind_b.read(window=win)
    with rasterio.open(ind_after_file) as src_ind_a:
        ind_a_data = src_ind_a.read(window=win)

    # 4. Read Change Stack
    with rasterio.open(change_file) as src_ch:
        ch_data = src_ch.read(window=win)

    # S2 band indexing: 0=Blue, 1=Green, 2=Red
    rgb_before = stretch_rgb_reflectance(red=s2_b_data[2], green=s2_b_data[1], blue=s2_b_data[0])
    rgb_after = stretch_rgb_reflectance(red=s2_a_data[2], green=s2_a_data[1], blue=s2_a_data[0])

    # Indicator indexing: 0=NDVI, 1=NDWI, 2=NDBI
    ndvi_b = ind_b_data[0]
    ndvi_a = ind_a_data[0]

    # Change stack indexing: 0=NDVI delta, 2=NDWI delta, 4=NDBI delta
    ndvi_d = ch_data[0]
    ndwi_d = ch_data[2]
    ndbi_d = ch_data[4]

    subtitle = f"Hotspot {grid_id} (Rank #{rank}) | {int(window_meters)}m Window"

    # Define asset target paths
    path_before_rgb = target_dir / "before_rgb.png"
    path_after_rgb = target_dir / "after_rgb.png"
    path_ndvi_before = target_dir / "ndvi_before.png"
    path_ndvi_after = target_dir / "ndvi_after.png"
    path_ndvi_change = target_dir / "ndvi_change.png"
    path_ndwi_change = target_dir / "ndwi_change.png"
    path_ndbi_change = target_dir / "ndbi_change.png"
    path_comb_change = target_dir / "combined_change.png"
    path_metadata = target_dir / "metadata.json"

    # A & B: Natural Color RGBs
    render_rgb_preview(
        rgb_stretched=rgb_before,
        title=f"Sentinel-2 Natural Color Before ({b_date_str})",
        subtitle=subtitle,
        output_path=path_before_rgb,
    )
    render_rgb_preview(
        rgb_stretched=rgb_after,
        title=f"Sentinel-2 Natural Color After ({a_date_str})",
        subtitle=subtitle,
        output_path=path_after_rgb,
    )

    # C & D: NDVI Before and After
    render_single_index_preview(
        index_data=ndvi_b,
        title=f"NDVI Vegetation Index Before ({b_date_str})",
        subtitle=subtitle,
        cmap="RdYlGn",
        vmin=-0.1,
        vmax=0.8,
        colorbar_label="NDVI (Canopy Vigor)",
        output_path=path_ndvi_before,
    )
    render_single_index_preview(
        index_data=ndvi_a,
        title=f"NDVI Vegetation Index After ({a_date_str})",
        subtitle=subtitle,
        cmap="RdYlGn",
        vmin=-0.1,
        vmax=0.8,
        colorbar_label="NDVI (Canopy Vigor)",
        output_path=path_ndvi_after,
    )

    # E, F, G: Deltas
    render_single_index_preview(
        index_data=ndvi_d,
        title=f"NDVI Delta Change ({y_before} -> {y_after})",
        subtitle=subtitle,
        cmap="RdYlGn",
        vmin=-0.5,
        vmax=0.5,
        colorbar_label="Delta NDVI (Red: Decrease, Green: Increase)",
        output_path=path_ndvi_change,
    )
    render_single_index_preview(
        index_data=ndwi_d,
        title=f"NDWI Moisture Delta Change ({y_before} -> {y_after})",
        subtitle=subtitle,
        cmap="PuOr",
        vmin=-0.5,
        vmax=0.5,
        colorbar_label="Delta NDWI (Purple: Moisture Increase, Orange: Decrease)",
        output_path=path_ndwi_change,
    )
    render_single_index_preview(
        index_data=ndbi_d,
        title=f"NDBI Built-Up-Sensitive Delta ({y_before} -> {y_after})",
        subtitle=subtitle,
        cmap="coolwarm",
        vmin=-0.5,
        vmax=0.5,
        colorbar_label="Delta NDBI (Red: Built-up-Sensitive Increase, Blue: Decrease)",
        output_path=path_ndbi_change,
    )

    # H: Combined Evidence Map
    comb_metrics = render_combined_evidence_preview(
        ndvi_delta=ndvi_d,
        ndwi_delta=ndwi_d,
        ndbi_delta=ndbi_d,
        title=f"Cross-Indicator Change Evidence ({y_before} -> {y_after})",
        subtitle=subtitle,
        output_path=path_comb_change,
    )

    # Calculate relative paths for portable manifest consumption (relative to project root)
    def rel_posix(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
        except ValueError:
            return str(p).replace("\\", "/")

    assets_map = {
        "before_rgb": rel_posix(path_before_rgb),
        "after_rgb": rel_posix(path_after_rgb),
        "ndvi_before": rel_posix(path_ndvi_before),
        "ndvi_after": rel_posix(path_ndvi_after),
        "ndvi_change": rel_posix(path_ndvi_change),
        "ndwi_change": rel_posix(path_ndwi_change),
        "ndbi_change": rel_posix(path_ndbi_change),
        "combined_change": rel_posix(path_comb_change),
    }

    metadata: Dict[str, Any] = {
        "grid_id": grid_id,
        "period": period,
        "rank": rank,
        "center_lat": round(float(center_lat), 6),
        "center_lon": round(float(center_lon), 6),
        "window_meters": float(window_meters),
        "crs": "EPSG:32644",
        "source": "Sentinel-2 L2A",
        "before_date": before_date,
        "after_date": after_date,
        "crop_dimensions": [int(win.height), int(win.width)],
        "assets": assets_map,
        "scientific_metrics": {
            "mean_ndvi_delta": round(float(np.nanmean(ndvi_d)), 4),
            "mean_ndwi_delta": round(float(np.nanmean(ndwi_d)), 4),
            "mean_ndbi_delta": round(float(np.nanmean(ndbi_d)), 4),
            **comb_metrics,
        },
    }

    with open(path_metadata, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Generated visual evidence assets for {grid_id} ({period}) in {target_dir}")
    return metadata


def generate_batch_hotspot_evidence(
    period: str,
    top_k: int = 10,
    window_meters: float = 1000.0,
    config: Optional[AppConfig] = None,
) -> List[Dict[str, Any]]:
    """
    Generate evidence assets for the Top-K candidate hotspots in a period.
    """
    if config is None:
        config = get_config()

    api_file = config.directories.outputs_dir / "api" / f"hotspots_{period}.json"
    if not api_file.exists():
        raise FileNotFoundError(f"API hotspots file not found: {api_file}")

    with open(api_file, encoding="utf-8") as f:
        hotspots = json.load(f)

    selected = hotspots[:top_k]
    logger.info(f"Processing batch evidence assets for Top {len(selected)} hotspots in {period}...")

    results: List[Dict[str, Any]] = []
    for h in selected:
        grid_id = h["grid_id"]
        meta = generate_hotspot_evidence(
            grid_id=grid_id,
            period=period,
            window_meters=window_meters,
            config=config,
        )
        results.append(meta)

    return results


def generate_all_evidence_manifests(
    periods: Optional[List[str]] = None,
    top_k: int = 10,
    window_meters: float = 1000.0,
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Generate Top-K evidence assets for all periods and compile evidence_manifest.json.

    Args:
        periods: List of periods (default: ['2020_2026', '2020_2023', '2023_2026']).
        top_k: Number of top hotspots per period (default 10).
        window_meters: Physical extent of crop box (default 1000m).
        config: Optional AppConfig.

    Returns:
        Structured evidence manifest dictionary.
    """
    if config is None:
        config = get_config()

    if periods is None:
        periods = ["2020_2026", "2020_2023", "2023_2026"]

    evidence_base = config.directories.outputs_dir / "evidence"
    evidence_base.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Dict[str, Any]] = {}

    for period in periods:
        logger.info(f"=== Generating evidence assets for period: {period} (Top {top_k}) ===")
        batch_results = generate_batch_hotspot_evidence(
            period=period,
            top_k=top_k,
            window_meters=window_meters,
            config=config,
        )

        for meta in batch_results:
            gid = meta["grid_id"]
            if gid not in manifest:
                manifest[gid] = {}

            # Structure manifest entry matching Part 6 specification
            manifest_entry = dict(meta["assets"])
            meta_json_path = evidence_base / period / gid / "metadata.json"
            try:
                rel_meta = str(meta_json_path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
            except ValueError:
                rel_meta = str(meta_json_path).replace("\\", "/")
            manifest_entry["metadata"] = rel_meta

            manifest[gid][period] = manifest_entry

    manifest_file = evidence_base / "evidence_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Saved global evidence manifest to {manifest_file} with {len(manifest)} hotspots")
    return manifest
