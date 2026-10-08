"""
UrbanPulse - Cross-Indicator Evidence & Consistency Engine.

Evaluates multi-spectral evidence coherence and persistence:
- Distinguishes multi-spectral signatures (e.g. vegetation loss + built-up increase)
  from isolated single-band noise or seasonal variations.
- Evaluates persistence and reversal flags from Step 5 multi-temporal observations.
- Generates 7-band UInt8 evidence rasters with documented flag semantics.
- Generates structured, explainable anomaly records ("Why Flagged?") for downstream priority ranking.

SCIENTIFIC TERMINOLOGY:
- NDVI decrease + NDBI increase = "urban-expansion-consistent spectral pattern"
  (NOT "confirmed new buildings" or "deforestation").
- Evidence indicates statistical and spectral coherence, NOT legal or causal ground truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import rasterio

from config.settings import EvidenceConfig
from geospatial.logger import get_logger

logger = get_logger("geospatial.anomaly_detection.evidence")

EVIDENCE_FLAG_BAND_NAMES: List[str] = [
    "vegetation_change_present",
    "water_change_present",
    "builtup_signal_present",
    "vegetation_builtup_coherence",
    "persistent_change_present",
    "reversal_present",
    "valid_anomaly_components_count",
]


def evaluate_cross_indicator_evidence(
    change_stack: np.ndarray,
    anomaly_stack: np.ndarray,
    valid_mask: np.ndarray,
    persistence_stack: Optional[np.ndarray] = None,
    config: Optional[EvidenceConfig] = None,
) -> Dict[str, Any]:
    """
    Evaluate cross-indicator coherence, persistence, and reversal evidence.

    Inputs from change stack:
        Band 1 (idx 0): NDVI delta
        Band 5 (idx 4): NDBI delta
    Inputs from anomaly stack (10 bands):
        Band 7 (idx 6): NDVI combined anomaly
        Band 8 (idx 7): NDWI combined anomaly
        Band 9 (idx 8): NDBI combined anomaly
        Band 1 (idx 0): NDVI temporal anomaly
        Band 4 (idx 3): NDVI spatial anomaly

    Inputs from persistence stack (9 bands from Step 5):
        Band 1: persistent_vegetation_decrease
        Band 5: persistent_builtup_increase
        Band 3: persistent_water_decrease
        Band 7: vegetation_reversal
        Band 9: builtup_reversal
        Band 8: water_reversal

    Evidence Flags (UInt8: 1 = active, 0 = inactive):
    1. vegetation_change_present: NDVI combined anomaly >= threshold
    2. water_change_present: NDWI combined anomaly >= threshold
    3. builtup_signal_present: NDBI combined anomaly >= threshold
    4. vegetation_builtup_coherence:
           (NDVI delta < 0) AND (NDBI delta > 0) AND (NDVI anomalous) AND (NDBI anomalous)
    5. persistent_change_present:
           persistent veg decrease OR persistent builtup increase OR persistent water decrease
    6. reversal_present:
           vegetation reversal OR builtup reversal OR water reversal
    7. valid_anomaly_components_count:
           Number of valid components (0, 1, or 2 [temporal + spatial])

    Args:
        change_stack: (12, H, W) pairwise change stack.
        anomaly_stack: (10, H, W) comprehensive anomaly stack.
        valid_mask: (H, W) boolean valid mask.
        persistence_stack: Optional (9, H, W) persistence raster from Step 5.
        config: Optional EvidenceConfig.

    Returns:
        Dict containing:
            - "evidence_stack": (7, H, W) uint8 raster stack
            - individual boolean / uint8 flag arrays
            - "summary_stats": count and percentage of each flag
    """
    if config is None:
        config = EvidenceConfig()

    threshold = config.anomaly_threshold
    height, width = valid_mask.shape

    # Anomaly scores
    ndvi_anom = anomaly_stack[6]  # NDVI combined
    ndwi_anom = anomaly_stack[7]  # NDWI combined
    ndbi_anom = anomaly_stack[8]  # NDBI combined

    # Signed deltas
    ndvi_delta = change_stack[0]
    ndbi_delta = change_stack[4]

    # Temporal & Spatial validity for component counting
    temp_valid = np.isfinite(anomaly_stack[0])  # NDVI temporal
    spat_valid = np.isfinite(anomaly_stack[3])  # NDVI spatial
    component_count = (temp_valid.astype(np.uint8) + spat_valid.astype(np.uint8))
    component_count[~valid_mask] = 0

    # Flag 1: Vegetation change present
    f_veg = valid_mask & np.isfinite(ndvi_anom) & (ndvi_anom >= threshold)

    # Flag 2: Water change present
    f_water = valid_mask & np.isfinite(ndwi_anom) & (ndwi_anom >= threshold)

    # Flag 3: Built-up signal present
    f_built = valid_mask & np.isfinite(ndbi_anom) & (ndbi_anom >= threshold)

    # Flag 4: Cross-indicator coherence (urban expansion pattern: veg loss + built-up gain)
    f_coherence = (
        valid_mask
        & (ndvi_delta < 0.0)
        & (ndbi_delta > 0.0)
        & f_veg
        & f_built
    )

    # Flag 5 & 6: Persistence & Reversal from Step 5
    if persistence_stack is not None and persistence_stack.shape[0] >= 9:
        p_veg_dec = persistence_stack[0] == 1
        p_built_inc = persistence_stack[4] == 1
        p_water_dec = persistence_stack[2] == 1
        f_persistent = valid_mask & (p_veg_dec | p_built_inc | p_water_dec)

        r_veg = persistence_stack[6] == 1
        r_water = persistence_stack[7] == 1
        r_built = persistence_stack[8] == 1
        f_reversal = valid_mask & (r_veg | r_water | r_built)
    else:
        f_persistent = np.zeros((height, width), dtype=bool)
        f_reversal = np.zeros((height, width), dtype=bool)

    # Assemble 7-band UInt8 stack
    evidence_stack = np.stack(
        [
            f_veg.astype(np.uint8),
            f_water.astype(np.uint8),
            f_built.astype(np.uint8),
            f_coherence.astype(np.uint8),
            f_persistent.astype(np.uint8),
            f_reversal.astype(np.uint8),
            component_count,
        ],
        axis=0,
    ).astype(np.uint8)

    n_valid = int(np.sum(valid_mask))

    def stat(arr: np.ndarray) -> Dict[str, Any]:
        count = int(np.sum(arr))
        pct = round(100.0 * count / max(1, n_valid), 2)
        return {"active_pixels": count, "percentage_of_valid": pct}

    summary = {
        "anomaly_threshold": threshold,
        "valid_pixels": n_valid,
        "vegetation_change_present": stat(f_veg),
        "water_change_present": stat(f_water),
        "builtup_signal_present": stat(f_built),
        "vegetation_builtup_coherence": stat(f_coherence),
        "persistent_change_present": stat(f_persistent),
        "reversal_present": stat(f_reversal),
    }

    return {
        "evidence_stack": evidence_stack,
        "vegetation_change_present": f_veg,
        "water_change_present": f_water,
        "builtup_signal_present": f_built,
        "vegetation_builtup_coherence": f_coherence,
        "persistent_change_present": f_persistent,
        "reversal_present": f_reversal,
        "valid_anomaly_components_count": component_count,
        "summary": summary,
    }


def write_evidence_raster(
    evidence_stack: np.ndarray,
    valid_mask: np.ndarray,
    profile: Dict[str, Any],
    output_path: Path,
    mask_path: Path,
) -> Tuple[Path, Path]:
    """
    Write 7-band UInt8 evidence flag raster to disk.

    Args:
        evidence_stack: (7, H, W) uint8 array.
        valid_mask: (H, W) boolean mask array.
        profile: Base rasterio profile.
        output_path: Target GeoTIFF path.
        mask_path: Target valid mask path.

    Returns:
        Tuple of (output_path, mask_path).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)

    bands, height, width = evidence_stack.shape

    out_profile = profile.copy()
    out_profile.update(
        count=bands,
        dtype="uint8",
        compress="lzw",
        nodata=None,
    )

    with rasterio.open(output_path, "w", **out_profile) as dst:
        dst.write(evidence_stack)
        for idx, name in enumerate(EVIDENCE_FLAG_BAND_NAMES, start=1):
            dst.set_band_description(idx, name)

    mask_profile = profile.copy()
    mask_profile.update(
        count=1,
        dtype="uint8",
        compress="lzw",
        nodata=None,
    )

    with rasterio.open(mask_path, "w", **mask_profile) as dst:
        dst.write(valid_mask.astype(np.uint8), 1)
        dst.set_band_description(1, "valid_evidence_mask")

    logger.info(f"Saved evidence flag raster: {output_path.name} (7 bands)")
    return output_path, mask_path


def build_evidence_record(
    grid_id: str,
    row: int,
    col: int,
    change_stack: np.ndarray,
    anomaly_stack: np.ndarray,
    evidence_stack: np.ndarray,
    valid_mask: np.ndarray,
) -> Dict[str, Any]:
    """
    Construct a structured, explainable evidence record for an individual pixel/cell.

    Format matches UrbanPulse Section 9 schema.

    Args:
        grid_id: Grid cell or pixel identifier.
        row: Row coordinate.
        col: Column coordinate.
        change_stack: (12, H, W) pairwise change stack.
        anomaly_stack: (10, H, W) anomaly stack.
        evidence_stack: (7, H, W) evidence flag stack.
        valid_mask: (H, W) boolean mask.

    Returns:
        Dict record suitable for JSON export or database insertion.
    """
    is_valid = bool(valid_mask[row, col])

    def val(arr: np.ndarray, b_idx: int) -> Optional[float]:
        if not is_valid:
            return None
        v = float(arr[b_idx, row, col])
        return round(v, 4) if np.isfinite(v) else None

    def flag(b_idx: int) -> bool:
        if not is_valid:
            return False
        return bool(evidence_stack[b_idx, row, col] == 1)

    record = {
        "grid_id": grid_id,
        "pixel_row": row,
        "pixel_col": col,
        "is_valid": is_valid,
        # Step 5 Deltas
        "ndvi_delta": val(change_stack, 0),
        "ndwi_delta": val(change_stack, 2),
        "ndbi_delta": val(change_stack, 4),
        # Temporal Anomalies
        "ndvi_temporal_anomaly": val(anomaly_stack, 0),
        "ndwi_temporal_anomaly": val(anomaly_stack, 1),
        "ndbi_temporal_anomaly": val(anomaly_stack, 2),
        # Spatial Anomalies
        "ndvi_spatial_anomaly": val(anomaly_stack, 3),
        "ndwi_spatial_anomaly": val(anomaly_stack, 4),
        "ndbi_spatial_anomaly": val(anomaly_stack, 5),
        # Combined Anomalies
        "ndvi_combined_anomaly": val(anomaly_stack, 6),
        "ndwi_combined_anomaly": val(anomaly_stack, 7),
        "ndbi_combined_anomaly": val(anomaly_stack, 8),
        "combined_anomaly": val(anomaly_stack, 9),
        # Evidence Flags
        "vegetation_change_present": flag(0),
        "water_change_present": flag(1),
        "builtup_signal_present": flag(2),
        "vegetation_builtup_coherence": flag(3),
        "persistent_change_present": flag(4),
        "reversal_present": flag(5),
        "valid_anomaly_components": int(evidence_stack[6, row, col]) if is_valid else 0,
    }

    return record
