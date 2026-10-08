"""
UrbanPulse - Geographic Grid Generation Module.

Responsibilities:
- Generate a fixed, deterministic vector tessellation (e.g. 500m x 500m) over the AOI in projected CRS.
- Transform grid cells into WGS84 coordinates (latitude, longitude centroids and bounding polygons).
- Assign unique, stable identifiers (e.g. HYD_0001, HYD_0421) to each grid cell.
"""

from geospatial.grid.grid_generator import GridCell, generate_study_grid

__all__ = [
    "GridCell",
    "generate_study_grid",
]
