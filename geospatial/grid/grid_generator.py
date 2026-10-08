"""
UrbanPulse - Geographic Grid Generation Engine.

Generates a fixed, deterministic vector tessellation (e.g. 500m x 500m)
over the study area in the projected coordinate reference system (UTM Zone 44N),
calculating WGS84 centroids and raster pixel window indices for fast aggregation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import rasterio
from affine import Affine
from pyproj import Transformer

from config.settings import GridConfig, StudyAreaConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.grid.grid_generator")


@dataclass(frozen=True)
class GridCell:
    """Represents a single deterministic grid cell in the AOI tessellation."""

    grid_id: str
    cell_index: int
    grid_row: int
    grid_col: int
    pixel_row_min: int
    pixel_row_max: int
    pixel_col_min: int
    pixel_col_max: int
    minx: float
    miny: float
    maxx: float
    maxy: float
    centroid_x: float
    centroid_y: float
    latitude: float
    longitude: float

    def to_dict(self) -> Dict[str, float | str | int]:
        return {
            "grid_id": self.grid_id,
            "cell_index": self.cell_index,
            "grid_row": self.grid_row,
            "grid_col": self.grid_col,
            "latitude": round(self.latitude, 6),
            "longitude": round(self.longitude, 6),
            "pixel_row_min": self.pixel_row_min,
            "pixel_row_max": self.pixel_row_max,
            "pixel_col_min": self.pixel_col_min,
            "pixel_col_max": self.pixel_col_max,
        }


def generate_study_grid(
    transform: Affine,
    width: int,
    height: int,
    cell_size_meters: float = 500.0,
    prefix: str = "HYD",
    crs_proj: str = "EPSG:32644",
    crs_geo: str = "EPSG:4326",
) -> List[GridCell]:
    """
    Generate a deterministic grid of regular cells covering the raster extent.

    Args:
        transform: Affine transform mapping pixel coordinates to projected CRS.
        width: Raster width in pixels.
        height: Raster height in pixels.
        cell_size_meters: Metric cell side length (default 500m).
        prefix: Grid cell prefix (e.g. 'HYD').
        crs_proj: Projected coordinate reference system.
        crs_geo: Geographic coordinate reference system.

    Returns:
        List of GridCell objects covering the raster bounding box.
    """
    # Calculate raster bounds in projected CRS
    minx = transform.c
    maxy = transform.f
    pixel_size_x = transform.a  # +10.0m
    pixel_size_y = -transform.e  # +10.0m (since transform.e is -10.0)

    maxx = minx + width * pixel_size_x
    miny = maxy - height * pixel_size_y

    pixels_per_cell_x = int(round(cell_size_meters / pixel_size_x))
    pixels_per_cell_y = int(round(cell_size_meters / pixel_size_y))

    n_cols = int(math.ceil(width / pixels_per_cell_x))
    n_rows = int(math.ceil(height / pixels_per_cell_y))

    transformer = Transformer.from_crs(crs_proj, crs_geo, always_xy=True)

    cells: List[GridCell] = []
    cell_idx = 1

    for r in range(n_rows):
        r_min = r * pixels_per_cell_y
        r_max = min(height, (r + 1) * pixels_per_cell_y)

        cell_top = maxy - r_min * pixel_size_y
        cell_bottom = maxy - r_max * pixel_size_y

        for c in range(n_cols):
            c_min = c * pixels_per_cell_x
            c_max = min(width, (c + 1) * pixels_per_cell_x)

            cell_left = minx + c_min * pixel_size_x
            cell_right = minx + c_max * pixel_size_x

            centroid_x = (cell_left + cell_right) / 2.0
            centroid_y = (cell_top + cell_bottom) / 2.0

            # Transform centroid to WGS84 (lon, lat)
            lon, lat = transformer.transform(centroid_x, centroid_y)

            grid_id = f"{prefix}_{cell_idx:04d}"

            cell = GridCell(
                grid_id=grid_id,
                cell_index=cell_idx,
                grid_row=r,
                grid_col=c,
                pixel_row_min=r_min,
                pixel_row_max=r_max,
                pixel_col_min=c_min,
                pixel_col_max=c_max,
                minx=cell_left,
                miny=cell_bottom,
                maxx=cell_right,
                maxy=cell_top,
                centroid_x=centroid_x,
                centroid_y=centroid_y,
                latitude=float(lat),
                longitude=float(lon),
            )
            cells.append(cell)
            cell_idx += 1

    logger.info(
        f"Generated {len(cells)} grid cells ({n_rows} rows x {n_cols} cols) "
        f"with resolution {cell_size_meters}m and prefix '{prefix}'"
    )
    return cells
