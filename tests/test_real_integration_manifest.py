"""Integration test verifying Member 1 real API outputs and canonical hotspot HYD_1220."""

import json
from pathlib import Path
import pytest

from config.settings import get_config


def test_canonical_hotspot_hyd_1220():
    cfg = get_config()
    api_dir = cfg.directories.outputs_dir / "api"
    hotspots_file = api_dir / "top_10_2020_2026.json"

    assert hotspots_file.exists(), f"Missing real API file: {hotspots_file}"
    with open(hotspots_file, "r", encoding="utf-8") as f:
        hotspots = json.load(f)

    # Find canonical demo hotspot
    hyd_1220 = next((h for h in hotspots if h.get("grid_id") == "HYD_1220"), None)
    assert hyd_1220 is not None, "Canonical hotspot HYD_1220 not found in top 10"

    # Verify priority score approx 0.8200
    score = hyd_1220["priority"]["score"]
    assert pytest.approx(score, abs=0.01) == 0.82

    # Verify priority level HIGH
    assert hyd_1220["priority"]["level"] == "HIGH"
    assert hyd_1220["priority"]["recommendation"] == "FIELD_VERIFICATION_RECOMMENDED"

    # Verify coordinates
    lat = hyd_1220["latitude"]
    lon = hyd_1220["longitude"]
    assert pytest.approx(lat, abs=0.001) == 17.372285
    assert pytest.approx(lon, abs=0.001) == 78.422560

    # Verify assets exist
    assets = hyd_1220.get("assets", {})
    assert "before_rgb" in assets
    assert "after_rgb" in assets
    assert "combined_change" in assets

    root_dir = Path(__file__).resolve().parent.parent
    before_path = root_dir / assets["before_rgb"]
    after_path = root_dir / assets["after_rgb"]
    assert before_path.exists(), f"Evidence asset missing: {before_path}"
    assert after_path.exists(), f"Evidence asset missing: {after_path}"
