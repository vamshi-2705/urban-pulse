"""
UrbanPulse - Satellite Data Acquisition Module.

Responsibilities:
- Query Sentinel-2 Level-2A surface reflectance data using Planetary Computer / STAC client.
- Filter candidate scenes by bounding box (AOI), date windows (2020, 2023, 2026), and cloud threshold.
- Sign asset URLs with Planetary Computer token authentication.
- Rank candidate scenes deterministically and inspect spectral band assets (B02, B03, B04, B08, B11, B12, SCL).
"""

from geospatial.acquisition.sentinel2 import (
    STANDARD_SPECTRAL_BANDS,
    create_catalog_client,
    discover_scenes,
    inspect_scene_assets,
    rank_scenes,
    search_sentinel2_scenes,
    select_best_scene,
)

__all__ = [
    "STANDARD_SPECTRAL_BANDS",
    "create_catalog_client",
    "discover_scenes",
    "inspect_scene_assets",
    "rank_scenes",
    "search_sentinel2_scenes",
    "select_best_scene",
]
