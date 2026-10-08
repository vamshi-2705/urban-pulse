"""
UrbanPulse - Integration Data Exporter (Step 8).

Transforms raw geospatial priority records from Step 7 into standardized,
API-ready JSON, GeoJSON, and City Summary artifacts for Member 2 frontend/backend.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import AppConfig, get_config
from geospatial.integration.schema import (
    REASON_CODE_DESCRIPTIONS,
    CitySummary,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    HotspotAnomaly,
    HotspotChange,
    HotspotEvidence,
    HotspotPriority,
    HotspotRecord,
    WhyFlagged,
    WhyFlaggedFactor,
)
from geospatial.logger import get_logger

logger = get_logger("geospatial.integration.exporter")


def generate_why_flagged(
    reasons: List[str],
    priority_level: str,
    signals: Dict[str, Any],
) -> WhyFlagged:
    """
    Generate a scientifically cautious, factor-by-factor explanation.

    Args:
        reasons: List of machine-readable reason code strings.
        priority_level: Priority category ('HIGH', 'MEDIUM', 'LOW').
        signals: Dictionary of underlying signal values.

    Returns:
        Structured WhyFlagged instance.
    """
    # 1. Headline generation
    has_coherence = "VEG_BUILTUP_COHERENCE" in reasons or signals.get("veg_builtup_coherence") == 1.0
    has_persistence = "PERSISTENT_CHANGE" in reasons or signals.get("persistence") == 1.0
    has_high_anom = "HIGH_SCENE_ANOMALY" in reasons or signals.get("overall_anomaly", 0.0) >= 0.70
    has_spatial = "SPATIAL_ANOMALY" in reasons

    if has_coherence and has_persistence:
        headline = "Strong and persistent land-cover change"
    elif has_coherence and has_high_anom:
        headline = "Coherent multi-spectral land-cover alteration"
    elif has_high_anom and has_spatial:
        headline = "Pronounced localized spectral change anomaly"
    elif has_high_anom:
        headline = "Pronounced scene-level change anomaly"
    elif priority_level == "MEDIUM":
        headline = "Moderate land-cover change requiring monitoring"
    else:
        headline = "Minor baseline surface variation"

    # 2. Factor descriptions
    factors: List[WhyFlaggedFactor] = []
    for code in reasons:
        desc = REASON_CODE_DESCRIPTIONS.get(
            code, "Observable satellite-derived spectral anomaly flag."
        )
        factors.append(WhyFlaggedFactor(code=code, description=desc))

    return WhyFlagged(headline=headline, factors=factors)


def format_hotspot_record(
    raw_record: Dict[str, Any],
    period: str,
    assets: Optional[Dict[str, str]] = None,
) -> HotspotRecord:
    """
    Transform a raw Step 7 cell record into the stable HotspotRecord contract.

    Args:
        raw_record: Dictionary from priority_hotspots.json.
        period: Period string (e.g. '2020_2026').
        assets: Optional dictionary of visual evidence asset paths.

    Returns:
        Validated HotspotRecord instance.
    """
    signals = raw_record.get("signals", {})
    reasons = raw_record.get("reasons", [])
    priority_level = raw_record.get("priority_level", "LOW")

    priority = HotspotPriority(
        score=float(raw_record.get("priority_score", 0.0)),
        level=priority_level,
        recommendation=raw_record.get("recommendation", "ROUTINE_OBSERVATION"),
    )

    anomaly = HotspotAnomaly(
        overall=float(signals.get("overall_anomaly", 0.0)),
        ndvi=float(signals.get("ndvi_anomaly", 0.0)),
        ndwi=float(signals.get("ndwi_anomaly", 0.0)),
        ndbi=float(signals.get("ndbi_anomaly", 0.0)),
        spatial=float(signals.get("spatial_anomaly", 0.0)),
    )

    ndvi_d = float(signals.get("ndvi_delta", 0.0))
    ndwi_d = float(signals.get("ndwi_delta", 0.0))
    ndbi_d = float(signals.get("ndbi_delta", 0.0))

    evidence = HotspotEvidence(
        vegetation_loss=bool(
            signals.get("vegetation_change_present", False)
            or ndvi_d <= -0.15
            or "VEGETATION_LOSS" in reasons
        ),
        water_change=bool(
            signals.get("water_change_present", False)
            or abs(ndwi_d) >= 0.15
            or "WATER_CHANGE" in reasons
        ),
        builtup_change=bool(
            signals.get("builtup_signal_present", False)
            or ndbi_d >= 0.15
            or "BUILTUP_SENSITIVE_CHANGE" in reasons
        ),
        veg_builtup_coherence=bool(
            signals.get("veg_builtup_coherence") == 1.0
            or "VEG_BUILTUP_COHERENCE" in reasons
        ),
        persistent_change=bool(
            signals.get("persistence") == 1.0
            or "PERSISTENT_CHANGE" in reasons
        ),
        cyclical_reversal=bool(
            signals.get("reversal") == 1.0
            or "CYCLICAL_REVERSAL_DAMPENED" in reasons
        ),
    )

    change = HotspotChange(
        ndvi_delta=ndvi_d,
        ndwi_delta=ndwi_d,
        ndbi_delta=ndbi_d,
    )

    why_flagged = generate_why_flagged(
        reasons=reasons,
        priority_level=priority_level,
        signals=signals,
    )

    return HotspotRecord(
        rank=int(raw_record.get("rank", 0)),
        grid_id=str(raw_record.get("grid_id", "")),
        period=period,
        latitude=float(raw_record.get("latitude", 0.0)),
        longitude=float(raw_record.get("longitude", 0.0)),
        priority=priority,
        reasons=reasons,
        anomaly=anomaly,
        evidence=evidence,
        change=change,
        why_flagged=why_flagged,
        assets=assets,
    )


def build_geojson_collection(
    hotspots: List[HotspotRecord],
    period: str,
) -> GeoJSONFeatureCollection:
    """
    Convert a list of HotspotRecords into a Leaflet-ready GeoJSON FeatureCollection.

    Args:
        hotspots: List of HotspotRecords.
        period: Period string (e.g. '2020_2026').

    Returns:
        GeoJSONFeatureCollection instance.
    """
    features: List[GeoJSONFeature] = []
    for h in hotspots:
        props = {
            "grid_id": h.grid_id,
            "rank": h.rank,
            "priority_score": h.priority.score,
            "priority_level": h.priority.level,
            "recommendation": h.priority.recommendation,
            "period": h.period,
            "reasons": h.reasons,
            "overall_anomaly": h.anomaly.overall,
            "headline": h.why_flagged.headline,
        }
        features.append(
            GeoJSONFeature(
                grid_id=h.grid_id,
                latitude=h.latitude,
                longitude=h.longitude,
                properties=props,
            )
        )
    return GeoJSONFeatureCollection(period=period, features=features)


def export_period_api_artifacts(
    period: str,
    priority_dir: Path,
    output_dir: Path,
) -> Dict[str, Path]:
    """
    Export all API-ready JSON and GeoJSON outputs for a given period.

    Args:
        period: Comparison period (e.g. '2020_2026').
        priority_dir: Directory containing Step 7 priority outputs.
        output_dir: Target API directory (e.g. 'data/outputs/api/').

    Returns:
        Dict mapping artifact name to its Path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    hotspots_file = priority_dir / "priority_hotspots.json"
    stats_file = priority_dir / "priority_stats.json"

    if not hotspots_file.exists():
        raise FileNotFoundError(f"Missing priority hotspots file: {hotspots_file}")
    if not stats_file.exists():
        raise FileNotFoundError(f"Missing priority stats file: {stats_file}")

    with open(hotspots_file, encoding="utf-8") as f:
        raw_hotspots = json.load(f)
    with open(stats_file, encoding="utf-8") as f:
        stats = json.load(f)

    manifest_file = output_dir.parent / "evidence" / "evidence_manifest.json"
    evidence_manifest: Dict[str, Any] = {}
    if manifest_file.exists():
        try:
            with open(manifest_file, encoding="utf-8") as mf:
                evidence_manifest = json.load(mf)
        except Exception:
            pass

    logger.info(f"Formatting {len(raw_hotspots)} hotspot records for period {period}...")
    hotspot_records = [
        format_hotspot_record(
            raw_record=r,
            period=period,
            assets=evidence_manifest.get(r.get("grid_id"), {}).get(period),
        )
        for r in raw_hotspots
    ]
    hotspot_dicts = [h.to_dict() for h in hotspot_records]

    # 1. Full hotspots list JSON
    api_hotspots_path = output_dir / f"hotspots_{period}.json"
    with open(api_hotspots_path, "w", encoding="utf-8") as f:
        json.dump(hotspot_dicts, f, indent=2)

    # 2. GeoJSON FeatureCollection
    geojson_coll = build_geojson_collection(hotspot_records, period)
    api_geojson_path = output_dir / f"hotspots_{period}.geojson"
    with open(api_geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_coll.to_dict(), f, indent=2)

    # 3. City Summary JSON
    counts = stats.get("counts", {})
    summary = CitySummary(
        period=period,
        total_cells=stats.get("total_valid_cells", len(hotspot_records)),
        high_priority=counts.get("high", 0),
        medium_priority=counts.get("medium", 0),
        low_priority=counts.get("low", 0),
        score_median=stats.get("priority_score_median", 0.0),
        score_p95=stats.get("priority_score_p95", 0.0),
        top_hotspots=hotspot_dicts[:25],  # Embed Top 25 in city summary
    )
    api_summary_path = output_dir / f"city_summary_{period}.json"
    with open(api_summary_path, "w", encoding="utf-8") as f:
        json.dump(summary.to_dict(), f, indent=2)

    # 4. Convenience subsets (Top 10, Top 25, Top 50)
    top10_path = output_dir / f"top_10_{period}.json"
    with open(top10_path, "w", encoding="utf-8") as f:
        json.dump(hotspot_dicts[:10], f, indent=2)

    top25_path = output_dir / f"top_25_{period}.json"
    with open(top25_path, "w", encoding="utf-8") as f:
        json.dump(hotspot_dicts[:25], f, indent=2)

    top50_path = output_dir / f"top_50_{period}.json"
    with open(top50_path, "w", encoding="utf-8") as f:
        json.dump(hotspot_dicts[:50], f, indent=2)

    logger.info(f"Exported API artifacts for {period} to {output_dir}")
    return {
        "hotspots": api_hotspots_path,
        "geojson": api_geojson_path,
        "summary": api_summary_path,
        "top_10": top10_path,
        "top_25": top25_path,
        "top_50": top50_path,
    }


def export_all_api_artifacts(
    config: Optional[AppConfig] = None,
) -> Dict[str, Any]:
    """
    Generate complete API export artifacts for all periods:
    - 2020_2023
    - 2023_2026
    - 2020_2026
    """
    if config is None:
        config = get_config()

    priority_base = config.directories.processed_dir / "priority"
    api_base = config.directories.outputs_dir / "api"
    api_base.mkdir(parents=True, exist_ok=True)

    periods = ["2020_2023", "2023_2026", "2020_2026"]
    results: Dict[str, Any] = {}

    for period in periods:
        p_dir = priority_base / period
        if not p_dir.exists():
            logger.warning(f"Priority directory for {period} missing: {p_dir}")
            continue

        p_artifacts = export_period_api_artifacts(
            period=period,
            priority_dir=p_dir,
            output_dir=api_base,
        )
        results[period] = {k: str(v) for k, v in p_artifacts.items()}

    logger.info(f"Completed API artifact export for {len(results)} periods")
    return results
