"""Tests verifying all geospatial module imports and package integrity."""

import importlib
import pytest


@pytest.mark.parametrize(
    "module_path",
    [
        "geospatial",
        "geospatial.logger",
        "geospatial.acquisition",
        "geospatial.preprocessing",
        "geospatial.grid",
        "geospatial.indicators",
        "geospatial.change_detection",
        "geospatial.anomaly",
        "geospatial.priority",
        "geospatial.evidence",
        "geospatial.validation",
        "config",
        "config.settings",
    ],
)
def test_module_import(module_path: str):
    """Ensure every foundation module can be imported without syntax or dependency errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None


def test_geospatial_version_and_exports():
    """Verify geospatial package exports version and logging functions."""
    import geospatial

    assert hasattr(geospatial, "__version__")
    assert hasattr(geospatial, "get_logger")
    assert hasattr(geospatial, "setup_logging")
