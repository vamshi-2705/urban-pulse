"""
UrbanPulse - Multi-Temporal Change Detection Module.

Responsibilities:
- Perform pairwise and sequence multi-temporal change calculations across epochs (2020 -> 2023 -> 2026).
- Quantify absolute and relative shifts in indicator fractions (delta_built_up, delta_vegetation, delta_water).
- Filter out transient seasonal variations by contrasting comparable post-monsoon / dry-season baselines.
- Maintain consistent observation records mapped to fixed grid IDs.
"""

from geospatial.change_detection.temporal_change import (
    PAIRWISE_CHANGE_BAND_NAMES,
    PERSISTENCE_BAND_NAMES,
    calculate_change_magnitude,
    calculate_multitemporal_change,
    calculate_pairwise_change,
    calculate_persistence,
    classify_change_direction,
    generate_change_metadata,
    load_indicator_raster,
    summarize_delta,
    validate_change_outputs,
    validate_temporal_alignment,
)

__all__ = [
    "PAIRWISE_CHANGE_BAND_NAMES",
    "PERSISTENCE_BAND_NAMES",
    "calculate_change_magnitude",
    "calculate_multitemporal_change",
    "calculate_pairwise_change",
    "calculate_persistence",
    "classify_change_direction",
    "generate_change_metadata",
    "load_indicator_raster",
    "summarize_delta",
    "validate_change_outputs",
    "validate_temporal_alignment",
]
