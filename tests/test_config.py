"""Tests for the central configuration system."""

from pathlib import Path
import pytest

from config.settings import AppConfig, get_config, load_config


def test_load_config_default():
    """Verify that default config loads correctly and returns AppConfig."""
    cfg = get_config(reload=True)
    assert isinstance(cfg, AppConfig)
    assert cfg.study_area.name is not None
    assert len(cfg.study_area.name) > 0


def test_study_area_bbox_validity():
    """Verify bounding box coordinates are well-formed."""
    cfg = get_config()
    bbox = cfg.study_area.bbox
    assert len(bbox) == 4
    min_lon, min_lat, max_lon, max_lat = bbox

    # Check coordinate order
    assert min_lon < max_lon, "min_lon must be less than max_lon"
    assert min_lat < max_lat, "min_lat must be less than max_lat"

    # Check bounds are within valid WGS84 range
    assert -180.0 <= min_lon <= 180.0
    assert -180.0 <= max_lon <= 180.0
    assert -90.0 <= min_lat <= 90.0
    assert -90.0 <= max_lat <= 90.0

    # Check properties
    assert cfg.study_area.min_lon == min_lon
    assert cfg.study_area.min_lat == min_lat
    assert cfg.study_area.max_lon == max_lon
    assert cfg.study_area.max_lat == max_lat


def test_crs_configuration():
    """Verify coordinate reference system configuration."""
    cfg = get_config()
    assert "EPSG:" in cfg.crs.geographic
    assert "EPSG:" in cfg.crs.projected
    assert cfg.crs.geographic == "EPSG:4326"


def test_time_periods():
    """Verify analysis time periods include 2020, 2023, 2026."""
    cfg = get_config()
    expected_years = [2020, 2023, 2026]
    assert all(year in cfg.time_periods.years for year in expected_years)


def test_satellite_and_grid_parameters():
    """Verify satellite and grid configurations."""
    cfg = get_config()
    assert 0.0 < cfg.satellite.cloud_cover_max_percent <= 100.0
    assert cfg.grid.cell_size_meters > 0.0
    assert cfg.grid.prefix == "HYD"


def test_directories_creation():
    """Verify directory paths are resolved and exist."""
    cfg = get_config()
    assert cfg.directories.raw_dir.is_dir()
    assert cfg.directories.processed_dir.is_dir()
    assert cfg.directories.outputs_dir.is_dir()
    assert cfg.directories.logs_dir.is_dir()


def test_target_schema_fields():
    """Verify the target data schema defines required indicator attributes."""
    cfg = get_config()
    raw = cfg.raw_dict
    assert "schema" in raw
    fields = raw["schema"]["fields"]
    required_fields = ["grid_id", "lat", "lng", "date", "built_up", "vegetation", "water", "bare"]
    for field_name in required_fields:
        assert field_name in fields, f"Missing required schema field: {field_name}"


def test_change_detection_config():
    """Verify change detection tolerance configuration values."""
    cfg = get_config(reload=True)
    assert hasattr(cfg, "change_detection")
    assert cfg.change_detection.ndvi_epsilon > 0.0
    assert cfg.change_detection.ndwi_epsilon > 0.0
    assert cfg.change_detection.ndbi_epsilon > 0.0


def test_anomaly_config():
    """Verify anomaly detection configuration parameters."""
    cfg = get_config(reload=True)
    assert hasattr(cfg, "anomaly")
    assert cfg.anomaly.temporal.mad_scale > 0.0
    assert cfg.anomaly.temporal.z_clip > 0.0
    assert cfg.anomaly.spatial.window_size_pixels % 2 == 1  # Must be odd window
    assert cfg.anomaly.spatial.minimum_valid_neighbors > 0
    assert 0.0 <= cfg.anomaly.combined.temporal_weight <= 1.0
    assert 0.0 <= cfg.anomaly.combined.spatial_weight <= 1.0
    assert abs((cfg.anomaly.combined.temporal_weight + cfg.anomaly.combined.spatial_weight) - 1.0) < 1e-5
    assert 0.0 < cfg.anomaly.evidence.anomaly_threshold < 1.0
