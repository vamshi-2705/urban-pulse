"""
UrbanPulse - Validation & Data Quality Module.

Responsibilities:
- Validate schema compliance and value ranges (e.g. fractions sum to ~100%, coords within bbox).
- Detect and handle missing data, excessive cloud gaps, and sensor artifacts.
- Provide data confidence indicators without fabricating satellite values.
- Validate reproducibility across pipeline stages.
"""

__all__: list[str] = []
