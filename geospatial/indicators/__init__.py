"""
UrbanPulse - Spectral & Land-Cover Indicators Module.

Responsibilities:
- Compute core spectral indices from calibrated surface reflectance bands:
    * NDVI: (NIR - Red) / (NIR + Red)
    * NDWI: (Green - NIR) / (Green + NIR)
    * NDBI: (SWIR - NIR) / (SWIR + NIR)
- Aggregate indicator statistics per geographic grid cell (mean, median, standard deviation).
- Derive physical land-cover component fractions per cell:
    * built_up (%)
    * vegetation (%)
    * water (%)
    * bare (%)
"""

__all__: list[str] = []
