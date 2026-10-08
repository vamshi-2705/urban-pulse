"""
UrbanPulse - Satellite Data Acquisition Module.

Responsibilities:
- Query Sentinel-2 Level-2A surface reflectance data using Planetary Computer / STAC client.
- Filter candidate scenes by bounding box (AOI), date windows (2020, 2023, 2026), and cloud threshold.
- Sign asset URLs with Planetary Computer token authentication.
- Stream or fetch requested band assets (B02, B03, B04, B08, B11, B12, SCL) without downloading massive scenes.
"""

__all__: list[str] = []
