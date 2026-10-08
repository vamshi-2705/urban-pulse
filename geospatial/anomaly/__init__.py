"""
UrbanPulse - Anomaly Detection Module.

Responsibilities:
- Establish historical baselines per grid cell across available temporal observations.
- Establish neighborhood/local spatial baselines (e.g., k-nearest cells or radial spatial lag).
- Identify temporal anomalies: abrupt shifts deviating significantly from historical trends.
- Identify spatial anomalies: isolated alterations contrasting sharply with neighboring urban fabric.
- Output normalized z-scores / anomaly metrics for change classification.
"""

from geospatial.anomaly_detection import (
    ANOMALY_STACK_BAND_NAMES,
    EVIDENCE_FLAG_BAND_NAMES,
    build_evidence_record,
    calculate_robust_center_dispersion,
    calculate_robust_z,
    compute_indicator_spatial_anomaly,
    compute_indicator_temporal_anomaly,
    compute_period_combined_anomalies,
    compute_period_spatial_anomalies,
    compute_period_temporal_anomalies,
    count_valid_neighbors,
    evaluate_cross_indicator_evidence,
    fuse_anomaly_components,
    process_all_anomalies,
    process_period_anomaly,
    validate_anomaly_raster,
    write_anomaly_raster,
    write_evidence_raster,
    z_to_anomaly_score,
)

__all__ = [
    "ANOMALY_STACK_BAND_NAMES",
    "EVIDENCE_FLAG_BAND_NAMES",
    "build_evidence_record",
    "calculate_robust_center_dispersion",
    "calculate_robust_z",
    "compute_indicator_spatial_anomaly",
    "compute_indicator_temporal_anomaly",
    "compute_period_combined_anomalies",
    "compute_period_spatial_anomalies",
    "compute_period_temporal_anomalies",
    "count_valid_neighbors",
    "evaluate_cross_indicator_evidence",
    "fuse_anomaly_components",
    "process_all_anomalies",
    "process_period_anomaly",
    "validate_anomaly_raster",
    "write_anomaly_raster",
    "write_evidence_raster",
    "z_to_anomaly_score",
]
