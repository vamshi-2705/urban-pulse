"""
UrbanPulse - Sentinel-2 Level-2A Data Acquisition and Scene Discovery.

Queries Microsoft Planetary Computer's STAC API for cloud-filtered Sentinel-2
surface reflectance items over the configured study area across target temporal epochs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pystac
import pystac_client
import planetary_computer

from config.settings import AppConfig, get_config
from geospatial.logger import get_logger

logger = get_logger("geospatial.acquisition.sentinel2")

# Standard Sentinel-2 L2A spectral assets required for indicator computation
STANDARD_SPECTRAL_BANDS: Dict[str, str] = {
    "blue": "B02",
    "green": "B03",
    "red": "B04",
    "nir": "B08",
    "swir1": "B11",
    "swir2": "B12",
    "scl": "SCL",
    "visual": "visual",
}


def create_catalog_client(api_url: Optional[str] = None) -> pystac_client.Client:
    """
    Establish authenticated connection to Microsoft Planetary Computer STAC catalog.

    Args:
        api_url: Optional override STAC API endpoint URL. Defaults to configured URL.

    Returns:
        pystac_client.Client authenticated with sign_inplace modifier.

    Raises:
        ConnectionError: If connection to STAC endpoint fails.
    """
    cfg: AppConfig = get_config()
    target_url = api_url or cfg.satellite.stac_api_url

    logger.info(f"Connecting to Planetary Computer STAC catalog at: {target_url}")
    try:
        catalog = pystac_client.Client.open(
            target_url,
            modifier=planetary_computer.sign_inplace,
        )
        return catalog
    except Exception as exc:
        err_msg = f"Failed to connect to STAC catalog at {target_url}: {exc}"
        logger.error(err_msg)
        raise ConnectionError(err_msg) from exc


def search_sentinel2_scenes(
    catalog_client: pystac_client.Client,
    aoi_bbox: List[float],
    date_window: str,
    cloud_cover_max: float = 15.0,
    collection: str = "sentinel-2-l2a",
    query_filter: Optional[Dict[str, Any]] = None,
    limit: int = 50,
) -> List[pystac.Item]:
    """
    Query STAC catalog for candidate Sentinel-2 scenes meeting spatial, temporal,
    and cloud cover criteria.

    Args:
        catalog_client: Connected STAC client.
        aoi_bbox: Area of Interest bounding box [min_lon, min_lat, max_lon, max_lat].
        date_window: Temporal filter window (e.g. '2020-01-01/2020-03-31').
        cloud_cover_max: Maximum cloud cover percentage allowed (<= 100.0).
        collection: STAC collection name (default: 'sentinel-2-l2a').
        query_filter: Optional extra STAC query terms.
        limit: Max search limit.

    Returns:
        List of pystac.Item candidate scenes.
    """
    logger.info(
        f"Searching STAC collection '{collection}' | AOI={aoi_bbox} | "
        f"Window={date_window} | Max Cloud={cloud_cover_max}%"
    )

    query: Dict[str, Any] = {"eo:cloud_cover": {"lt": cloud_cover_max}}
    if query_filter:
        query.update(query_filter)

    try:
        search = catalog_client.search(
            collections=[collection],
            bbox=aoi_bbox,
            datetime=date_window,
            query=query,
            limit=limit,
        )
        items: List[pystac.Item] = list(search.item_collection())
        logger.info(
            f"STAC search completed: found {len(items)} candidate scene(s) for window {date_window}"
        )
        return items
    except Exception as exc:
        err_msg = f"STAC search query failed for window {date_window}: {exc}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from exc


def _check_bbox_containment(item_bbox: List[float], aoi_bbox: List[float]) -> bool:
    """Check if item bounding box completely encloses the target AOI bounding box."""
    if not item_bbox or len(item_bbox) < 4 or not aoi_bbox or len(aoi_bbox) < 4:
        return False
    return (
        item_bbox[0] <= aoi_bbox[0]
        and item_bbox[1] <= aoi_bbox[1]
        and item_bbox[2] >= aoi_bbox[2]
        and item_bbox[3] >= aoi_bbox[3]
    )


def rank_scenes(
    items: List[pystac.Item],
    aoi_bbox: List[float],
    target_year: int,
    preferred_months: Optional[List[int]] = None,
) -> List[Tuple[pystac.Item, float, Dict[str, Any]]]:
    """
    Deterministically rank candidate Sentinel-2 scenes by cloud cover, spatial containment,
    and seasonal preference.

    Scoring formula (0 - 100):
    - Cloud cover component (up to 70 pts): (100 - cloud_cover) * 0.70
    - Full spatial containment of AOI (20 pts): 20 if fully contains AOI, else 5
    - Seasonal alignment (10 pts): 10 if acquired in preferred months, else 2

    Args:
        items: Candidate STAC scenes.
        aoi_bbox: Target AOI bounding box [min_lon, min_lat, max_lon, max_lat].
        target_year: Analysis target year.
        preferred_months: List of preferred calendar months (1-12) for seasonal consistency.

    Returns:
        List of tuples: (item, suitability_score, rank_metadata) sorted descending by score.
    """
    if not items:
        return []

    if preferred_months is None:
        preferred_months = [1, 2, 3]

    ranked: List[Tuple[pystac.Item, float, Dict[str, Any]]] = []

    for item in items:
        props = item.properties
        cloud_cover = float(props.get("eo:cloud_cover", 100.0))
        item_dt = item.datetime or datetime.fromisoformat(props.get("datetime", "").replace("Z", "+00:00"))

        # 1. Cloud Cover component (0 - 70 points)
        cloud_score = max(0.0, (100.0 - cloud_cover)) * 0.70

        # 2. AOI Containment component (0 - 20 points)
        fully_contains = _check_bbox_containment(item.bbox, aoi_bbox)
        containment_score = 20.0 if fully_contains else 5.0

        # 3. Seasonal preference component (0 - 10 points)
        in_preferred_month = item_dt.month in preferred_months
        seasonal_score = 10.0 if in_preferred_month else 2.0

        # Total Composite Suitability Score (0 - 100)
        total_score = round(cloud_score + containment_score + seasonal_score, 4)

        metadata = {
            "item_id": item.id,
            "datetime": item_dt.isoformat(),
            "cloud_cover": round(cloud_cover, 4),
            "fully_contains_aoi": fully_contains,
            "in_preferred_season": in_preferred_month,
            "mgrs_tile": props.get("s2:mgrs_tile", "unknown"),
            "platform": props.get("platform", "Sentinel-2"),
            "cloud_score": round(cloud_score, 2),
            "containment_score": containment_score,
            "seasonal_score": seasonal_score,
            "total_score": total_score,
        }
        ranked.append((item, total_score, metadata))

    # Deterministic sorting: highest score first, then lowest cloud cover, then newest item id
    ranked.sort(key=lambda x: (x[1], -x[2]["cloud_cover"], x[0].id), reverse=True)
    return ranked


def select_best_scene(
    items: List[pystac.Item],
    aoi_bbox: List[float],
    target_year: int,
    preferred_months: Optional[List[int]] = None,
) -> Optional[Tuple[pystac.Item, Dict[str, Any]]]:
    """
    Select the single most suitable scene from candidate items for a given year.

    Args:
        items: List of candidate STAC items.
        aoi_bbox: Target AOI bounding box.
        target_year: Analysis target year.
        preferred_months: Optional preferred months.

    Returns:
        Tuple of (selected_item, rank_metadata) or None if no items available.
    """
    if not items:
        logger.warning(f"No candidate scenes available to rank for year {target_year}.")
        return None

    ranked = rank_scenes(
        items=items,
        aoi_bbox=aoi_bbox,
        target_year=target_year,
        preferred_months=preferred_months,
    )

    best_item, best_score, best_meta = ranked[0]
    logger.info(
        f"Selected best scene for {target_year}: ID={best_item.id} | "
        f"Date={best_meta['datetime']} | Cloud={best_meta['cloud_cover']}% | "
        f"Score={best_score:.2f} | Tile={best_meta['mgrs_tile']}"
    )
    return best_item, best_meta


def inspect_scene_assets(
    item: pystac.Item,
    required_bands: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Inspect and catalog spectral band assets present in the selected Sentinel-2 STAC item.

    Does NOT download raster data; only records asset keys, titles, hrefs, and MIME types.

    Args:
        item: STAC Item.
        required_bands: Dictionary mapping band aliases to Sentinel-2 asset keys.

    Returns:
        Dictionary detailing available assets and required band mappings.
    """
    bands_to_check = required_bands or STANDARD_SPECTRAL_BANDS
    inspected_bands: Dict[str, Any] = {}
    missing_bands: List[str] = []

    for alias, asset_key in bands_to_check.items():
        if asset_key in item.assets:
            asset = item.assets[asset_key]
            inspected_bands[alias] = {
                "asset_key": asset_key,
                "title": asset.title or asset_key,
                "href": asset.href,
                "media_type": asset.media_type or "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": asset.roles or ["data"],
            }
        else:
            missing_bands.append(f"{alias} ({asset_key})")

    if missing_bands:
        logger.warning(
            f"Scene {item.id} is missing expected spectral assets: {', '.join(missing_bands)}"
        )

    all_available_keys = list(item.assets.keys())

    return {
        "required_spectral_bands": inspected_bands,
        "all_available_assets": all_available_keys,
        "all_required_present": len(missing_bands) == 0,
        "missing_required_bands": missing_bands,
    }


def discover_scenes(
    config_path: Optional[Path | str] = None,
    output_path: Optional[Path | str] = None,
    client: Optional[pystac_client.Client] = None,
) -> Dict[str, Any]:
    """
    Execute full Step 2 Scene Discovery across all configured temporal epochs.

    1. Loads central configuration (AOI, CRS, target years, cloud threshold).
    2. Connects to Microsoft Planetary Computer STAC API.
    3. Searches candidate Sentinel-2 L2A scenes for each year.
    4. Ranks candidates deterministically and selects best scene per epoch.
    5. Inspects required spectral assets.
    6. Saves structured scene catalog to data/processed/scene_catalog.json.

    Args:
        config_path: Optional override config path.
        output_path: Optional override output file destination.
        client: Optional pre-configured STAC client (used for tests/mocking).

    Returns:
        Structured scene catalog dictionary.
    """
    cfg: AppConfig = get_config() if config_path is None else get_config(reload=True)

    catalog_client = client or create_catalog_client(cfg.satellite.stac_api_url)

    aoi_bbox = cfg.study_area.bbox
    cloud_threshold = cfg.satellite.cloud_cover_max_percent
    preferred_months = cfg.time_periods.preferred_months
    collection = cfg.satellite.collection

    catalog_output: Dict[str, Any] = {
        "study_area": cfg.study_area.name,
        "region": cfg.study_area.region,
        "bbox": aoi_bbox,
        "collection": collection,
        "cloud_threshold": cloud_threshold,
        "preferred_months": preferred_months,
        "crs": {
            "geographic": cfg.crs.geographic,
            "projected": cfg.crs.projected,
        },
        "discovery_timestamp": datetime.utcnow().isoformat() + "Z",
        "periods": {},
    }

    for year in cfg.time_periods.years:
        logger.info(f"--- Discovering Sentinel-2 scenes for target year: {year} ---")

        # Preferred seasonal window (Jan 01 - Mar 31)
        start_month = min(preferred_months)
        end_month = max(preferred_months)
        primary_window = f"{year}-{start_month:02d}-01/{year}-{end_month:02d}-31"

        candidate_items = search_sentinel2_scenes(
            catalog_client=catalog_client,
            aoi_bbox=aoi_bbox,
            date_window=primary_window,
            cloud_cover_max=cloud_threshold,
            collection=collection,
        )

        window_used = primary_window
        # Fallback to full year if no scenes found in preferred season
        if not candidate_items:
            logger.warning(
                f"No scenes under {cloud_threshold}% cloud cover in seasonal window {primary_window}. "
                f"Expanding search window to full year {year}."
            )
            fallback_window = f"{year}-01-01/{year}-12-31"
            candidate_items = search_sentinel2_scenes(
                catalog_client=catalog_client,
                aoi_bbox=aoi_bbox,
                date_window=fallback_window,
                cloud_cover_max=cloud_threshold,
                collection=collection,
            )
            window_used = fallback_window

        if not candidate_items:
            logger.error(
                f"No suitable Sentinel-2 scene found for year {year} below cloud threshold {cloud_threshold}%."
            )
            catalog_output["periods"][str(year)] = {
                "selected_scene": None,
                "candidates_considered": 0,
                "status": "NO_SCENES_FOUND",
                "search_window": window_used,
            }
            continue

        selection = select_best_scene(
            items=candidate_items,
            aoi_bbox=aoi_bbox,
            target_year=year,
            preferred_months=preferred_months,
        )

        if selection is None:
            catalog_output["periods"][str(year)] = {
                "selected_scene": None,
                "candidates_considered": len(candidate_items),
                "status": "SELECTION_FAILED",
                "search_window": window_used,
            }
            continue

        selected_item, rank_meta = selection
        asset_info = inspect_scene_assets(selected_item)

        catalog_output["periods"][str(year)] = {
            "selected_scene": {
                "item_id": selected_item.id,
                "datetime": rank_meta["datetime"],
                "cloud_cover": rank_meta["cloud_cover"],
                "bbox": selected_item.bbox,
                "collection": collection,
                "platform": rank_meta["platform"],
                "mgrs_tile": rank_meta["mgrs_tile"],
                "suitability_score": rank_meta["total_score"],
                "fully_contains_aoi": rank_meta["fully_contains_aoi"],
                "assets": asset_info["required_spectral_bands"],
                "available_asset_count": len(asset_info["all_available_assets"]),
                "all_spectral_bands_present": asset_info["all_required_present"],
            },
            "candidates_considered": len(candidate_items),
            "search_window": window_used,
            "status": "SUCCESS",
        }

    # Write output catalog to JSON
    dest_path = (
        Path(output_path).resolve()
        if output_path
        else (cfg.directories.processed_dir / "scene_catalog.json").resolve()
    )
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(catalog_output, f, indent=2)

    logger.info(f"Scene catalog written to: {dest_path}")
    return catalog_output
