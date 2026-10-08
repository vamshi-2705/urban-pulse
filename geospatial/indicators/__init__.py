"""
UrbanPulse - Spectral & Land-Cover Indicators Module.

Responsibilities:
- Compute core continuous spectral indices:
    * NDVI (Vegetation-sensitive index): (NIR - Red) / (NIR + Red)
    * NDWI (Water-sensitive index): (Green - NIR) / (Green + NIR)
    * NDBI (Built-up-sensitive index): (SWIR1 - NIR) / (SWIR1 + NIR)
- Propagate validity masks to exclude cloud shadows, sensor saturation, and zero denominators.
- Generate statistical distributions across temporal epochs (2020, 2023, 2026).
- Validate strict multi-temporal spatial consistency and pixel alignment.
"""

from geospatial.indicators.spectral_indices import (
    INDICATOR_BAND_NAMES,
    calculate_indices,
    calculate_ndbi,
    calculate_ndvi,
    calculate_ndwi,
    check_spatial_consistency_across_epochs,
    process_all_indicators,
    process_year_indicators,
    summarize_indicator,
    validate_indicator_raster,
)

__all__ = [
    "INDICATOR_BAND_NAMES",
    "calculate_indices",
    "calculate_ndbi",
    "calculate_ndvi",
    "calculate_ndwi",
    "check_spatial_consistency_across_epochs",
    "process_all_indicators",
    "process_year_indicators",
    "summarize_indicator",
    "validate_indicator_raster",
]
