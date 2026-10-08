"""
UrbanPulse - Anomaly Detection Module.

Responsibilities:
- Establish historical baselines per grid cell across available temporal observations.
- Establish neighborhood/local spatial baselines (e.g., k-nearest cells or radial spatial lag).
- Identify temporal anomalies: abrupt shifts deviating significantly from historical trends.
- Identify spatial anomalies: isolated alterations contrasting sharply with neighboring urban fabric.
- Output normalized z-scores / anomaly metrics for change classification.
"""

__all__: list[str] = []
