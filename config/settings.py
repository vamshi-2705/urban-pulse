"""Configuration loader and schema definition for UrbanPulse Geospatial Engine."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

# Identify the root directory of the repository (parent of config directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class StudyAreaConfig:
    name: str
    region: str
    bbox: List[float]  # [min_lon, min_lat, max_lon, max_lat]
    center: Dict[str, float]

    @property
    def min_lon(self) -> float:
        return self.bbox[0]

    @property
    def min_lat(self) -> float:
        return self.bbox[1]

    @property
    def max_lon(self) -> float:
        return self.bbox[2]

    @property
    def max_lat(self) -> float:
        return self.bbox[3]


@dataclass(frozen=True)
class CRSConfig:
    geographic: str
    projected: str


@dataclass(frozen=True)
class TimePeriodsConfig:
    years: List[int]
    preferred_months: List[int]


@dataclass(frozen=True)
class SatelliteConfig:
    collection: str
    stac_api_url: str
    cloud_cover_max_percent: float
    bands: Dict[str, str]


@dataclass(frozen=True)
class GridConfig:
    prefix: str
    cell_size_meters: float


@dataclass(frozen=True)
class DirectoriesConfig:
    raw_dir: Path
    processed_dir: Path
    outputs_dir: Path
    logs_dir: Path

    def ensure_directories(self) -> None:
        """Create configured directories if they do not exist."""
        for path in (self.raw_dir, self.processed_dir, self.outputs_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    format: str
    date_format: str
    log_file: Path


@dataclass(frozen=True)
class IndicatorThresholdsConfig:
    vegetation_candidate: float = 0.35
    water_candidate: float = 0.05
    builtup_candidate: float = 0.05


@dataclass(frozen=True)
class ChangeDetectionConfig:
    ndvi_epsilon: float = 0.10
    ndwi_epsilon: float = 0.10
    ndbi_epsilon: float = 0.10


@dataclass(frozen=True)
class TemporalAnomalyConfig:
    mad_scale: float = 0.6745
    z_clip: float = 3.5
    mad_floor: float = 0.001
    minimum_valid_samples: int = 100


@dataclass(frozen=True)
class SpatialAnomalyConfig:
    window_size_pixels: int = 21
    minimum_valid_neighbors: int = 20
    mad_floor: float = 0.001
    z_clip: float = 3.5


@dataclass(frozen=True)
class CombinedAnomalyConfig:
    temporal_weight: float = 0.6
    spatial_weight: float = 0.4
    fallback_to_available_component: bool = True
    aggregation_method: str = "max"  # Options: "max", "mean", "corroborated"


@dataclass(frozen=True)
class EvidenceConfig:
    anomaly_threshold: float = 0.50


@dataclass(frozen=True)
class AnomalyConfig:
    temporal: TemporalAnomalyConfig = field(default_factory=TemporalAnomalyConfig)
    spatial: SpatialAnomalyConfig = field(default_factory=SpatialAnomalyConfig)
    combined: CombinedAnomalyConfig = field(default_factory=CombinedAnomalyConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)


@dataclass(frozen=True)
class PriorityWeightsConfig:
    anomaly: float = 0.35
    evidence: float = 0.25
    persistence: float = 0.20
    magnitude: float = 0.10
    spatial_context: float = 0.10


@dataclass(frozen=True)
class PriorityThresholdsConfig:
    high: float = 0.70
    medium: float = 0.45


@dataclass(frozen=True)
class PriorityConfig:
    enabled: bool = True
    weights: PriorityWeightsConfig = field(default_factory=PriorityWeightsConfig)
    thresholds: PriorityThresholdsConfig = field(default_factory=PriorityThresholdsConfig)
    top_k: List[int] = field(default_factory=lambda: [10, 25, 50])


@dataclass(frozen=True)
class AppConfig:
    study_area: StudyAreaConfig
    crs: CRSConfig
    time_periods: TimePeriodsConfig
    satellite: SatelliteConfig
    grid: GridConfig
    directories: DirectoriesConfig
    logging: LoggingConfig
    indicators: IndicatorThresholdsConfig = field(default_factory=IndicatorThresholdsConfig)
    change_detection: ChangeDetectionConfig = field(default_factory=ChangeDetectionConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    priority: PriorityConfig = field(default_factory=PriorityConfig)
    raw_dict: Dict[str, Any] = field(default_factory=dict)


_CACHED_CONFIG: Optional[AppConfig] = None


def load_config(config_path: Optional[Path | str] = None) -> AppConfig:
    """
    Load configuration from YAML file, resolving paths relative to project root.

    Args:
        config_path: Path to config.yaml. Defaults to config/config.yaml in project root.

    Returns:
        AppConfig typed configuration object.
    """
    if config_path is None:
        target_path = PROJECT_ROOT / "config" / "config.yaml"
    else:
        target_path = Path(config_path).resolve()

    if not target_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = yaml.safe_load(f)

    # Resolve directories relative to project root
    dirs_data = data.get("directories", {})
    directories = DirectoriesConfig(
        raw_dir=(PROJECT_ROOT / dirs_data.get("raw_dir", "data/raw")).resolve(),
        processed_dir=(PROJECT_ROOT / dirs_data.get("processed_dir", "data/processed")).resolve(),
        outputs_dir=(PROJECT_ROOT / dirs_data.get("outputs_dir", "data/outputs")).resolve(),
        logs_dir=(PROJECT_ROOT / dirs_data.get("logs_dir", "logs")).resolve(),
    )

    log_data = data.get("logging", {})
    log_file_rel = log_data.get("log_file", "logs/geospatial_engine.log")
    logging_cfg = LoggingConfig(
        level=log_data.get("level", "INFO"),
        format=log_data.get("format", "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"),
        date_format=log_data.get("date_format", "%Y-%m-%d %H:%M:%S"),
        log_file=(PROJECT_ROOT / log_file_rel).resolve(),
    )

    ind_data = data.get("indicators", {}).get("heuristic_thresholds", {})
    indicators_cfg = IndicatorThresholdsConfig(
        vegetation_candidate=float(ind_data.get("vegetation_candidate", 0.35)),
        water_candidate=float(ind_data.get("water_candidate", 0.05)),
        builtup_candidate=float(ind_data.get("builtup_candidate", 0.05)),
    )

    cd_data = data.get("change_detection", {})
    change_detection_cfg = ChangeDetectionConfig(
        ndvi_epsilon=float(cd_data.get("ndvi", {}).get("epsilon", 0.10)),
        ndwi_epsilon=float(cd_data.get("ndwi", {}).get("epsilon", 0.10)),
        ndbi_epsilon=float(cd_data.get("ndbi", {}).get("epsilon", 0.10)),
    )

    anom_data = data.get("anomaly", {})
    t_data = anom_data.get("temporal", {})
    s_data = anom_data.get("spatial", {})
    c_data = anom_data.get("combined", {})
    e_data = anom_data.get("evidence", {})

    anomaly_cfg = AnomalyConfig(
        temporal=TemporalAnomalyConfig(
            mad_scale=float(t_data.get("mad_scale", 0.6745)),
            z_clip=float(t_data.get("z_clip", 3.5)),
            mad_floor=float(t_data.get("mad_floor", 0.001)),
            minimum_valid_samples=int(t_data.get("minimum_valid_samples", 100)),
        ),
        spatial=SpatialAnomalyConfig(
            window_size_pixels=int(s_data.get("window_size_pixels", 21)),
            minimum_valid_neighbors=int(s_data.get("minimum_valid_neighbors", 20)),
            mad_floor=float(s_data.get("mad_floor", 0.001)),
            z_clip=float(s_data.get("z_clip", 3.5)),
        ),
        combined=CombinedAnomalyConfig(
            temporal_weight=float(c_data.get("temporal_weight", 0.6)),
            spatial_weight=float(c_data.get("spatial_weight", 0.4)),
            fallback_to_available_component=bool(
                c_data.get("fallback_to_available_component", True)
            ),
            aggregation_method=str(c_data.get("aggregation_method", "max")),
        ),
        evidence=EvidenceConfig(
            anomaly_threshold=float(e_data.get("anomaly_threshold", 0.50)),
        ),
    )

    p_data = data.get("priority", {})
    p_weights = p_data.get("weights", {})
    p_thresholds = p_data.get("thresholds", {})
    priority_cfg = PriorityConfig(
        enabled=bool(p_data.get("enabled", True)),
        weights=PriorityWeightsConfig(
            anomaly=float(p_weights.get("anomaly", 0.35)),
            evidence=float(p_weights.get("evidence", 0.25)),
            persistence=float(p_weights.get("persistence", 0.20)),
            magnitude=float(p_weights.get("magnitude", 0.10)),
            spatial_context=float(p_weights.get("spatial_context", 0.10)),
        ),
        thresholds=PriorityThresholdsConfig(
            high=float(p_thresholds.get("high", 0.70)),
            medium=float(p_thresholds.get("medium", 0.45)),
        ),
        top_k=list(p_data.get("top_k", [10, 25, 50])),
    )

    app_config = AppConfig(
        study_area=StudyAreaConfig(**data["study_area"]),
        crs=CRSConfig(**data["crs"]),
        time_periods=TimePeriodsConfig(**data["time_periods"]),
        satellite=SatelliteConfig(**data["satellite"]),
        grid=GridConfig(**data["grid"]),
        directories=directories,
        logging=logging_cfg,
        indicators=indicators_cfg,
        change_detection=change_detection_cfg,
        anomaly=anomaly_cfg,
        priority=priority_cfg,
        raw_dict=data,
    )

    # Ensure project directories exist
    app_config.directories.ensure_directories()

    return app_config


def get_config(reload: bool = False) -> AppConfig:
    """
    Get cached singleton AppConfig instance.

    Args:
        reload: If True, reload configuration from disk.

    Returns:
        AppConfig typed instance.
    """
    global _CACHED_CONFIG
    if _CACHED_CONFIG is None or reload:
        _CACHED_CONFIG = load_config()
    return _CACHED_CONFIG
