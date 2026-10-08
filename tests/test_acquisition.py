"""
Unit and integration tests for Sentinel-2 data acquisition and scene discovery.
Unit tests are fully offline (using mock STAC items).
Integration tests are marked with @pytest.mark.integration.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import pystac

from config.settings import get_config
from geospatial.acquisition.sentinel2 import (
    STANDARD_SPECTRAL_BANDS,
    _check_bbox_containment,
    discover_scenes,
    inspect_scene_assets,
    rank_scenes,
    search_sentinel2_scenes,
    select_best_scene,
)


def _create_mock_item(
    item_id: str,
    dt: datetime,
    cloud_cover: float,
    bbox: List[float],
    mgrs_tile: str = "44QKE",
    include_all_bands: bool = True,
) -> pystac.Item:
    """Helper to synthesize a valid pystac.Item in memory without network calls."""
    geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
            ]
        ],
    }
    properties: Dict[str, Any] = {
        "datetime": dt.isoformat(),
        "eo:cloud_cover": cloud_cover,
        "s2:mgrs_tile": mgrs_tile,
        "platform": "Sentinel-2A",
    }
    item = pystac.Item(
        id=item_id,
        geometry=geom,
        bbox=bbox,
        datetime=dt,
        properties=properties,
    )

    if include_all_bands:
        for alias, band_key in STANDARD_SPECTRAL_BANDS.items():
            item.add_asset(
                band_key,
                pystac.Asset(
                    href=f"https://planetarycomputer.microsoft.com/mock/{item_id}/{band_key}.tif",
                    title=f"Band {band_key}",
                    media_type="image/tiff; application=geotiff; profile=cloud-optimized",
                    roles=["data"],
                ),
            )
    return item


# ==============================================================================
# PURE / UNIT TESTS (OFFLINE)
# ==============================================================================


def test_configuration_read_for_acquisition():
    """Verify that acquisition uses the central config without hardcoding."""
    cfg = get_config()
    assert cfg.study_area.name == "Hyderabad_Prototype"
    assert cfg.study_area.bbox == [78.35, 17.35, 78.55, 17.50]
    assert cfg.satellite.collection == "sentinel-2-l2a"
    assert cfg.satellite.cloud_cover_max_percent == 15.0
    assert 2020 in cfg.time_periods.years
    assert 2023 in cfg.time_periods.years
    assert 2026 in cfg.time_periods.years


def test_search_parameters_use_configured_aoi_and_cloud_threshold():
    """Verify that search_sentinel2_scenes forwards correct AOI, query, and collection."""
    mock_client = MagicMock()
    mock_search = MagicMock()
    mock_client.search.return_value = mock_search

    dt_dummy = datetime(2023, 2, 1, 10, 0, tzinfo=timezone.utc)
    mock_item = _create_mock_item("S2_TEST_1", dt_dummy, 2.5, [78.0, 17.0, 79.0, 18.0])
    mock_search.item_collection.return_value = [mock_item]

    aoi = [78.35, 17.35, 78.55, 17.50]
    results = search_sentinel2_scenes(
        catalog_client=mock_client,
        aoi_bbox=aoi,
        date_window="2023-01-01/2023-03-31",
        cloud_cover_max=12.0,
        collection="sentinel-2-l2a",
    )

    mock_client.search.assert_called_once()
    call_kwargs = mock_client.search.call_args[1]

    assert call_kwargs["collections"] == ["sentinel-2-l2a"]
    assert call_kwargs["bbox"] == aoi
    assert call_kwargs["datetime"] == "2023-01-01/2023-03-31"
    assert call_kwargs["query"] == {"eo:cloud_cover": {"lt": 12.0}}
    assert len(results) == 1
    assert results[0].id == "S2_TEST_1"


def test_bbox_containment_logic():
    """Verify spatial containment checking between item bbox and target AOI."""
    aoi = [78.35, 17.35, 78.55, 17.50]

    # Tile fully covering AOI
    tile_enclosing = [78.0, 17.0, 79.0, 18.0]
    assert _check_bbox_containment(tile_enclosing, aoi) is True

    # Tile shifted and partially cutting AOI
    tile_partial = [78.40, 17.0, 79.0, 18.0]
    assert _check_bbox_containment(tile_partial, aoi) is False


def test_scene_ranking_is_deterministic():
    """
    Verify that ranking consistently favors:
    1. Lower cloud cover
    2. Full spatial containment of the AOI
    3. Seasonal match (preferred months)
    """
    aoi = [78.35, 17.35, 78.55, 17.50]
    tile_full = [78.0, 17.0, 79.0, 18.0]
    tile_partial = [78.40, 17.0, 79.0, 18.0]

    # Best candidate: Jan, low cloud (0.5%), full containment
    item_ideal = _create_mock_item(
        "ITEM_IDEAL",
        datetime(2023, 1, 15, tzinfo=timezone.utc),
        cloud_cover=0.5,
        bbox=tile_full,
    )
    # Higher cloud (10.0%), Jan, full containment
    item_cloudy = _create_mock_item(
        "ITEM_CLOUDY",
        datetime(2023, 1, 20, tzinfo=timezone.utc),
        cloud_cover=10.0,
        bbox=tile_full,
    )
    # Low cloud (0.5%), but partial containment
    item_partial = _create_mock_item(
        "ITEM_PARTIAL",
        datetime(2023, 1, 15, tzinfo=timezone.utc),
        cloud_cover=0.5,
        bbox=tile_partial,
    )
    # Low cloud (0.5%), full containment, but off-season (July)
    item_off_season = _create_mock_item(
        "ITEM_OFF_SEASON",
        datetime(2023, 7, 15, tzinfo=timezone.utc),
        cloud_cover=0.5,
        bbox=tile_full,
    )

    items = [item_cloudy, item_off_season, item_partial, item_ideal]

    # Run ranking multiple times to assert determinism
    ranked_1 = rank_scenes(items, aoi_bbox=aoi, target_year=2023, preferred_months=[1, 2, 3])
    ranked_2 = rank_scenes(items, aoi_bbox=aoi, target_year=2023, preferred_months=[1, 2, 3])

    assert [r[0].id for r in ranked_1] == [r[0].id for r in ranked_2]
    # The top ranked item must be ITEM_IDEAL
    assert ranked_1[0][0].id == "ITEM_IDEAL"
    # Its score must be the highest
    assert ranked_1[0][1] > ranked_1[1][1]


def test_scene_selection_handles_no_results():
    """Verify that select_best_scene gracefully handles empty candidate lists."""
    aoi = [78.35, 17.35, 78.55, 17.50]
    result = select_best_scene([], aoi_bbox=aoi, target_year=2020)
    assert result is None


def test_asset_inspection_detects_spectral_bands():
    """Verify that inspect_scene_assets inspects B02, B03, B04, B08, B11, B12, SCL, visual."""
    dt = datetime(2023, 2, 1, tzinfo=timezone.utc)
    item_complete = _create_mock_item("S2_COMPLETE", dt, 1.0, [78.0, 17.0, 79.0, 18.0], include_all_bands=True)

    info = inspect_scene_assets(item_complete)
    assert info["all_required_present"] is True
    assert len(info["missing_required_bands"]) == 0

    spectral = info["required_spectral_bands"]
    for expected in ["blue", "green", "red", "nir", "swir1", "swir2", "scl", "visual"]:
        assert expected in spectral
        assert spectral[expected]["asset_key"] == STANDARD_SPECTRAL_BANDS[expected]
        assert "href" in spectral[expected]


def test_asset_inspection_reports_missing_bands():
    """Verify that missing expected bands are flagged."""
    dt = datetime(2023, 2, 1, tzinfo=timezone.utc)
    item_incomplete = _create_mock_item(
        "S2_INCOMPLETE", dt, 1.0, [78.0, 17.0, 79.0, 18.0], include_all_bands=False
    )
    # Add only blue
    item_incomplete.add_asset("B02", pystac.Asset(href="http://mock/B02.tif"))

    info = inspect_scene_assets(item_incomplete)
    assert info["all_required_present"] is False
    assert len(info["missing_required_bands"]) > 0


def test_discover_scenes_output_schema_validity(tmp_path: Path):
    """Verify that discover_scenes generates the expected schema and JSON file."""
    mock_client = MagicMock()
    mock_search = MagicMock()
    mock_client.search.return_value = mock_search

    # Provide candidate items for 2020, 2023, 2026
    items_by_year = {
        2020: [_create_mock_item("S2_2020", datetime(2020, 2, 1, tzinfo=timezone.utc), 1.2, [78.0, 17.0, 79.0, 18.0])],
        2023: [_create_mock_item("S2_2023", datetime(2023, 2, 1, tzinfo=timezone.utc), 0.5, [78.0, 17.0, 79.0, 18.0])],
        2026: [_create_mock_item("S2_2026", datetime(2026, 2, 1, tzinfo=timezone.utc), 0.8, [78.0, 17.0, 79.0, 18.0])],
    }

    def side_effect_search(*args, **kwargs):
        dt_window = kwargs.get("datetime", "")
        mock_res = MagicMock()
        for y, itms in items_by_year.items():
            if str(y) in dt_window:
                mock_res.item_collection.return_value = itms
                return mock_res
        mock_res.item_collection.return_value = []
        return mock_res

    mock_client.search.side_effect = side_effect_search

    out_file = tmp_path / "scene_catalog_test.json"
    catalog = discover_scenes(output_path=out_file, client=mock_client)

    # Validate output schema structure
    assert catalog["study_area"] == "Hyderabad_Prototype"
    assert catalog["collection"] == "sentinel-2-l2a"
    assert catalog["cloud_threshold"] == 15.0
    assert "periods" in catalog

    for year in ["2020", "2023", "2026"]:
        assert year in catalog["periods"]
        period = catalog["periods"][year]
        assert period["status"] == "SUCCESS"
        assert period["candidates_considered"] >= 1
        scene = period["selected_scene"]
        assert scene is not None
        assert "item_id" in scene
        assert "datetime" in scene
        assert "cloud_cover" in scene
        assert "bbox" in scene
        assert "assets" in scene
        assert scene["all_spectral_bands_present"] is True

    # Validate JSON file written to disk
    assert out_file.exists()


# ==============================================================================
# LIVE INTEGRATION TEST (Requires live Planetary Computer access)
# ==============================================================================


@pytest.mark.integration
def test_live_planetary_computer_stac_connection():
    """Live integration test: Connect to Planetary Computer and query Hyderabad AOI."""
    from geospatial.acquisition.sentinel2 import create_catalog_client, search_sentinel2_scenes

    client = create_catalog_client()
    assert client is not None

    aoi = [78.35, 17.35, 78.55, 17.50]
    # Test a known clear window for 2023
    items = search_sentinel2_scenes(
        catalog_client=client,
        aoi_bbox=aoi,
        date_window="2023-01-01/2023-03-31",
        cloud_cover_max=5.0,
        limit=5,
    )

    assert len(items) > 0, "Expected at least 1 Sentinel-2 scene from live STAC query"
    first = items[0]
    assert first.collection_id == "sentinel-2-l2a"
    assert "B02" in first.assets
    assert "B04" in first.assets
    assert "B08" in first.assets
