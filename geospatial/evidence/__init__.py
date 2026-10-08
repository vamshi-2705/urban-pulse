"""
UrbanPulse - Evidence Asset Generation Package (Step 9).

Exports:
- generate_hotspot_evidence: Extracts crops and renders visual evidence for a single hotspot.
- generate_batch_hotspot_evidence: Generates crops for the Top-K hotspots in a period.
- generate_all_evidence_manifests: Compiles global evidence_manifest.json across epochs.
"""

from __future__ import annotations

from geospatial.evidence.evidence_assets import (
    compute_raster_crop_window,
    generate_all_evidence_manifests,
    generate_batch_hotspot_evidence,
    generate_hotspot_evidence,
    get_acquisition_dates,
    get_hotspot_coordinates,
    render_combined_evidence_preview,
    render_rgb_preview,
    render_single_index_preview,
    stretch_rgb_reflectance,
)

__all__ = [
    "compute_raster_crop_window",
    "generate_all_evidence_manifests",
    "generate_batch_hotspot_evidence",
    "generate_hotspot_evidence",
    "get_acquisition_dates",
    "get_hotspot_coordinates",
    "render_combined_evidence_preview",
    "render_rgb_preview",
    "render_single_index_preview",
    "stretch_rgb_reflectance",
]
