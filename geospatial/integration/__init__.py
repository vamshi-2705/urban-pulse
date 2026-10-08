"""
UrbanPulse - Integration & API Contract Package (Step 8).

Prepares geospatial intelligence outputs for consumption by Member 2 frontend/backend:
- Stable HotspotRecord, WhyFlagged, CitySummary, and GeoJSON schemas.
- High-performance conversion and export pipeline.
- Strict contract validation ensuring zero fabricated data or invalid metrics.
"""

from __future__ import annotations

from geospatial.integration.exporter import (
    build_geojson_collection,
    export_all_api_artifacts,
    export_period_api_artifacts,
    format_hotspot_record,
    generate_why_flagged,
)
from geospatial.integration.schema import (
    REASON_CODE_DESCRIPTIONS,
    CitySummary,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    HotspotAnomaly,
    HotspotChange,
    HotspotEvidence,
    HotspotPriority,
    HotspotRecord,
    WhyFlagged,
    WhyFlaggedFactor,
)
from geospatial.integration.validator import (
    ValidationError,
    validate_city_summary,
    validate_geojson_collection,
    validate_hotspot_record,
    validate_hotspots_collection,
)

__all__ = [
    "REASON_CODE_DESCRIPTIONS",
    "CitySummary",
    "GeoJSONFeature",
    "GeoJSONFeatureCollection",
    "HotspotAnomaly",
    "HotspotChange",
    "HotspotEvidence",
    "HotspotPriority",
    "HotspotRecord",
    "ValidationError",
    "WhyFlagged",
    "WhyFlaggedFactor",
    "build_geojson_collection",
    "export_all_api_artifacts",
    "export_period_api_artifacts",
    "format_hotspot_record",
    "generate_why_flagged",
    "validate_city_summary",
    "validate_geojson_collection",
    "validate_hotspot_record",
    "validate_hotspots_collection",
]
