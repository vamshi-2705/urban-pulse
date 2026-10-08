"""
UrbanPulse - Multi-Temporal Change Detection Module.

Responsibilities:
- Perform pairwise and sequence multi-temporal change calculations across epochs (2020 -> 2023 -> 2026).
- Quantify absolute and relative shifts in indicator fractions (delta_built_up, delta_vegetation, delta_water).
- Filter out transient seasonal variations by contrasting comparable post-monsoon / dry-season baselines.
- Maintain consistent observation records mapped to fixed grid IDs.
"""

__all__: list[str] = []
