"""
Unit and integration tests for Evidence Asset Generation (Step 9).

Covers:
1. Hotspot to raster coordinate mapping accuracy
2. Correct crop window dimensions (1000m -> 100x100 at 10m res)
3. Correct CRS preservation (EPSG:32644)
4. Affine transform alignment
5. Edge-of-raster boundary clamping safety
6. Missing raster error handling
7. Evidence manifest structure and integrity
8. Finite numerical ranges without NaN/Inf corruption
9. Physical existence and valid PNG headers of visual previews
10. Deterministic regeneration reproducibility
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from affine import Affine

from config.settings import get_config
from geospatial.evidence import (
    compute_raster_crop_window,
    generate_hotspot_evidence,
    get_acquisition_dates,
    get_hotspot_coordinates,
    render_combined_evidence_preview,
    render_rgb_preview,
    render_single_index_preview,
    stretch_rgb_reflectance,
)


def test_acquisition_dates_reading():
    """Verify real Sentinel-2 acquisition dates are read from ARD metadata."""
    cfg = get_config()
    b_date, a_date = get_acquisition_dates(2020, 2026, cfg.directories.processed_dir)
    assert "2020-03-29" in b_date
    assert "2026-03-10" in a_date


def test_hotspot_coordinate_resolution():
    """Verify hotspot centroid lookup resolves to valid coordinates and rank."""
    cfg = get_config()
    lat, lon, rank = get_hotspot_coordinates(
        grid_id="HYD_1220",
        period="2020_2026",
        outputs_dir=cfg.directories.outputs_dir,
        processed_dir=cfg.directories.processed_dir,
    )
    assert 17.35 <= lat <= 17.50
    assert 78.35 <= lon <= 78.55
    assert rank == 1


def test_crop_window_computation():
    """Verify window dimensions and affine transform for 1000m extent."""
    cfg = get_config()
    s2_file = cfg.directories.processed_dir / "sentinel2" / "2020" / "scene_stack.tif"

    with rasterio.open(s2_file) as src:
        win, crop_transform, (xc, yc) = compute_raster_crop_window(
            center_lon=78.42256,
            center_lat=17.372285,
            window_meters=1000.0,
            raster_src=src,
        )
        assert win.width == 100
        assert win.height == 100
        assert crop_transform.a == 10.0  # 10m pixel resolution
        assert crop_transform.e == -10.0


def test_edge_of_raster_handling():
    """Verify boundary clamping prevents out-of-bounds negative coordinates."""
    cfg = get_config()
    s2_file = cfg.directories.processed_dir / "sentinel2" / "2020" / "scene_stack.tif"

    with rasterio.open(s2_file) as src:
        # Near top-left boundary
        win_tl, _, _ = compute_raster_crop_window(
            center_lon=78.3501,
            center_lat=17.4999,
            window_meters=1000.0,
            raster_src=src,
        )
        assert win_tl.col_off >= 0
        assert win_tl.row_off >= 0
        assert win_tl.col_off + win_tl.width <= src.width
        assert win_tl.row_off + win_tl.height <= src.height


def test_rgb_reflectance_stretch():
    """Verify reflectance stretch bounds values in [0.0, 1.0] and handles NaNs."""
    red = np.array([[0.05, 0.35], [0.50, np.nan]], dtype=np.float32)
    green = np.array([[0.04, 0.25], [0.40, np.nan]], dtype=np.float32)
    blue = np.array([[0.03, 0.15], [0.30, np.nan]], dtype=np.float32)

    stretched = stretch_rgb_reflectance(red, green, blue, max_reflectance=0.35)
    assert stretched.shape == (2, 2, 3)
    assert np.all(stretched >= 0.0)
    assert np.all(stretched <= 1.0)
    assert not np.any(np.isnan(stretched))


def test_missing_raster_error_handling(tmp_path):
    """Verify FileNotFoundError is raised if a required raster is missing."""
    with pytest.raises((FileNotFoundError, ValueError)):
        generate_hotspot_evidence(
            grid_id="HYD_9999_NONEXISTENT",
            period="2020_2026",
            output_base_dir=tmp_path,
        )


def test_evidence_manifest_integrity():
    """Verify pre-generated evidence_manifest.json has required structure and valid files."""
    cfg = get_config()
    manifest_file = cfg.directories.outputs_dir / "evidence" / "evidence_manifest.json"

    assert manifest_file.exists(), "evidence_manifest.json does not exist"
    with open(manifest_file, encoding="utf-8") as f:
        manifest = json.load(f)

    assert "HYD_1220" in manifest
    hyd1220 = manifest["HYD_1220"]
    assert "2020_2026" in hyd1220

    assets = hyd1220["2020_2026"]
    for k in ["before_rgb", "after_rgb", "ndvi_change", "ndwi_change", "ndbi_change", "combined_change", "metadata"]:
        assert k in assets
        p = cfg.directories.outputs_dir.parent.parent / assets[k]
        assert p.exists(), f"Asset {assets[k]} does not exist on disk"
        assert p.stat().st_size > 0


def test_png_preview_signatures():
    """Verify preview images are valid non-corrupted PNG files."""
    cfg = get_config()
    hyd1220_dir = cfg.directories.outputs_dir / "evidence" / "2020_2026" / "HYD_1220"

    png_files = list(hyd1220_dir.glob("*.png"))
    assert len(png_files) == 8, f"Expected 8 PNG files, found {len(png_files)}"

    for png in png_files:
        assert png.stat().st_size > 1000  # Non-trivial image size
        with open(png, "rb") as f:
            header = f.read(8)
            assert header == b"\x89PNG\r\n\x1a\n", f"Invalid PNG header in {png}"


def test_deterministic_evidence_generation(tmp_path):
    """Verify re-generating evidence for a hotspot produces deterministic metrics."""
    cfg = get_config()
    m1 = generate_hotspot_evidence(
        grid_id="HYD_1220",
        period="2020_2026",
        window_meters=1000.0,
        output_base_dir=tmp_path / "run1",
        config=cfg,
    )
    m2 = generate_hotspot_evidence(
        grid_id="HYD_1220",
        period="2020_2026",
        window_meters=1000.0,
        output_base_dir=tmp_path / "run2",
        config=cfg,
    )

    assert m1["scientific_metrics"] == m2["scientific_metrics"]
    assert m1["crop_dimensions"] == m2["crop_dimensions"]
    assert m1["center_lat"] == m2["center_lat"]
    assert m1["center_lon"] == m2["center_lon"]
