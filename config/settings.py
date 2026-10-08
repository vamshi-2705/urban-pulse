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
class AppConfig:
    study_area: StudyAreaConfig
    crs: CRSConfig
    time_periods: TimePeriodsConfig
    satellite: SatelliteConfig
    grid: GridConfig
    directories: DirectoriesConfig
    logging: LoggingConfig
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

    app_config = AppConfig(
        study_area=StudyAreaConfig(**data["study_area"]),
        crs=CRSConfig(**data["crs"]),
        time_periods=TimePeriodsConfig(**data["time_periods"]),
        satellite=SatelliteConfig(**data["satellite"]),
        grid=GridConfig(**data["grid"]),
        directories=directories,
        logging=logging_cfg,
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
