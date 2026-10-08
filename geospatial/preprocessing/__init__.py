"""
UrbanPulse - Satellite Preprocessing Module.

Responsibilities:
- Validate band resolutions and alignment (e.g. 10m vs 20m resampled to common grid).
- Apply cloud and shadow masks using Sentinel-2 Scene Classification Layer (SCL).
- Clip raster arrays to the defined study Area of Interest (AOI).
- Standardize nodata values and scale surface reflectance factors (0-10,000 to 0.0-1.0).
"""

__all__: list[str] = []
