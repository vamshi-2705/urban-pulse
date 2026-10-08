"""
UrbanPulse - Integration Data Contracts & Schema Definitions (Step 8).

Defines stable, explainable API data contracts for frontend/backend integration:
- HotspotRecord: Unified investigation candidate entity
- WhyFlagged: Scientifically cautious, factor-by-factor explanation
- CitySummary: Study-area scale aggregate intelligence metrics
- GeoJSONFeatureCollection: Direct Leaflet/MapLibre mapping contract
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# Reason code scientifically cautious descriptions
REASON_CODE_DESCRIPTIONS: Dict[str, str] = {
    "HIGH_SCENE_ANOMALY": "Observed spectral change is unusually strong relative to the scene distribution.",
    "SPATIAL_ANOMALY": "Spectral change sharply deviates from the surrounding 15x15 pixel local context.",
    "VEG_BUILTUP_COHERENCE": "Vegetation decrease coincides with built-up-sensitive spectral increase.",
    "VEGETATION_LOSS": "Substantial reduction in photosynthetic canopy (NDVI delta <= -0.15).",
    "BUILTUP_SENSITIVE_CHANGE": "Substantial increase in shortwave-infrared impervious surface reflectance (NDBI delta >= 0.15).",
    "WATER_CHANGE": "Significant shift in surface moisture or surface water extent (|NDWI delta| >= 0.15).",
    "PERSISTENT_CHANGE": "The directional change persists across available multi-year observations.",
    "STRONG_CHANGE_MAGNITUDE": "Extreme physical spectral displacement across one or more indicator bands.",
    "CYCLICAL_REVERSAL_DAMPENED": "Directional turnaround detected across observation intervals; priority dampened for potential cyclical variation.",
}


@dataclass(frozen=True)
class HotspotPriority:
    score: float
    level: str  # HIGH, MEDIUM, LOW
    recommendation: str  # FIELD_VERIFICATION_RECOMMENDED, MONITOR_AND_REVIEW, ROUTINE_OBSERVATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(float(self.score), 4),
            "level": self.level,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class HotspotAnomaly:
    overall: float
    ndvi: float
    ndwi: float
    ndbi: float
    spatial: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "overall": round(float(self.overall), 4),
            "ndvi": round(float(self.ndvi), 4),
            "ndwi": round(float(self.ndwi), 4),
            "ndbi": round(float(self.ndbi), 4),
        }
        if self.spatial is not None:
            d["spatial"] = round(float(self.spatial), 4)
        return d


@dataclass(frozen=True)
class HotspotEvidence:
    vegetation_loss: bool
    water_change: bool
    builtup_change: bool
    veg_builtup_coherence: bool
    persistent_change: bool
    cyclical_reversal: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "vegetation_loss": bool(self.vegetation_loss),
            "water_change": bool(self.water_change),
            "builtup_change": bool(self.builtup_change),
            "veg_builtup_coherence": bool(self.veg_builtup_coherence),
            "persistent_change": bool(self.persistent_change),
            "cyclical_reversal": bool(self.cyclical_reversal),
        }


@dataclass(frozen=True)
class HotspotChange:
    ndvi_delta: float
    ndwi_delta: float
    ndbi_delta: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "ndvi_delta": round(float(self.ndvi_delta), 4),
            "ndwi_delta": round(float(self.ndwi_delta), 4),
            "ndbi_delta": round(float(self.ndbi_delta), 4),
        }


@dataclass(frozen=True)
class WhyFlaggedFactor:
    code: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "description": self.description,
        }


@dataclass(frozen=True)
class WhyFlagged:
    headline: str
    factors: List[WhyFlaggedFactor]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headline": self.headline,
            "factors": [f.to_dict() for f in self.factors],
        }


@dataclass
class HotspotRecord:
    rank: int
    grid_id: str
    period: str
    latitude: float
    longitude: float
    priority: HotspotPriority
    reasons: List[str]
    anomaly: HotspotAnomaly
    evidence: HotspotEvidence
    change: HotspotChange
    why_flagged: WhyFlagged
    assets: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "rank": int(self.rank),
            "grid_id": self.grid_id,
            "period": self.period,
            "latitude": round(float(self.latitude), 6),
            "longitude": round(float(self.longitude), 6),
            "priority": self.priority.to_dict(),
            "reasons": list(self.reasons),
            "anomaly": self.anomaly.to_dict(),
            "evidence": self.evidence.to_dict(),
            "change": self.change.to_dict(),
            "why_flagged": self.why_flagged.to_dict(),
        }
        if self.assets is not None:
            d["assets"] = self.assets
        return d


@dataclass
class CitySummary:
    period: str
    total_cells: int
    high_priority: int
    medium_priority: int
    low_priority: int
    score_median: float
    score_p95: float
    top_hotspots: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "total_cells": int(self.total_cells),
            "high_priority": int(self.high_priority),
            "medium_priority": int(self.medium_priority),
            "low_priority": int(self.low_priority),
            "score_median": round(float(self.score_median), 4),
            "score_p95": round(float(self.score_p95), 4),
            "top_hotspots": self.top_hotspots,
        }


@dataclass
class GeoJSONFeature:
    grid_id: str
    latitude: float
    longitude: float
    properties: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(float(self.longitude), 6), round(float(self.latitude), 6)],
            },
            "properties": self.properties,
        }


@dataclass
class GeoJSONFeatureCollection:
    period: str
    features: List[GeoJSONFeature]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FeatureCollection",
            "period": self.period,
            "features": [f.to_dict() for f in self.features],
        }
