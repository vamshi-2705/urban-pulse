import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, CircleMarker, Tooltip, useMap } from 'react-leaflet';

/**
 * Controller to smoothly center and fly map to target hotspot coordinates
 * plus exposes controls for zoom and recenter
 */
function MapControlsManager({ cameraTarget, targetCoord, defaultCoord = [17.372285, 78.422560] }) {
  const map = useMap();

  useEffect(() => {
    if (cameraTarget && cameraTarget.center && cameraTarget.center.length === 2) {
      map.flyTo(cameraTarget.center, cameraTarget.zoom || 13, {
        duration: cameraTarget.duration || 1.2,
        easeLinearity: 0.25
      });
    } else if (targetCoord && targetCoord.length === 2) {
      map.flyTo(targetCoord, 14, {
        duration: 0.8,
        easeLinearity: 0.25
      });
    }
  }, [cameraTarget, targetCoord, map]);

  return (
    <div className="map-floating-action-cluster font-mono">
      <button
        type="button"
        className="map-action-btn"
        onClick={() => map.zoomIn()}
        title="Zoom in"
        aria-label="Zoom in"
      >
        +
      </button>
      <button
        type="button"
        className="map-action-btn"
        onClick={() => map.zoomOut()}
        title="Zoom out"
        aria-label="Zoom out"
      >
        &minus;
      </button>
      <button
        type="button"
        className="map-action-btn recenter-btn"
        onClick={() => map.flyTo(defaultCoord, 12.5, { duration: 0.8 })}
        title="Recenter map on Hyderabad"
        aria-label="Recenter map"
      >
        &#8635;
      </button>
    </div>
  );
}

export default function CityOverviewMap({
  areas = [],
  hotspots = [],
  selectedGridId = 'HYD_1220',
  onSelectCell,
  cameraTarget = null,
  guidedScene = null
}) {
  // Find selected cell
  const selectedCell = useMemo(() => {
    return (
      areas.find((c) => c.grid_id === selectedGridId) ||
      hotspots.find((h) => (h.grid_id || h.id) === selectedGridId)
    );
  }, [areas, hotspots, selectedGridId]);

  // Compute centroid
  const selectedCentroid = useMemo(() => {
    if (!selectedCell) return [17.372285, 78.422560];
    if (selectedCell.lat && selectedCell.lng) {
      return [selectedCell.lat, selectedCell.lng];
    }
    if (selectedCell.coordinates && selectedCell.coordinates.length === 2) {
      return selectedCell.coordinates;
    }
    if (selectedCell.geometry?.coordinates?.[0]) {
      const coords = selectedCell.geometry.coordinates[0];
      let sumLat = 0;
      let sumLng = 0;
      coords.forEach(([lng, lat]) => {
        sumLat += lat;
        sumLng += lng;
      });
      return [sumLat / coords.length, sumLng / coords.length];
    }
    return [17.372285, 78.422560];
  }, [selectedCell]);

  // Convert polygon coordinates
  const getPolygonPositions = (cell) => {
    if (cell.geometry?.coordinates?.[0]) {
      return cell.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
    }
    return null;
  };

  /**
   * Calm polygon styling — adaptive to guided walkthrough scenes
   */
  const getCellStyle = (cell) => {
    const isSelected = cell.grid_id === selectedGridId;
    const level = (cell.priority_level || '').toUpperCase();

    // Scene 1: OBSERVE — clearly highlight the 1,462 500m cells grid mesh
    if (guidedScene === 1) {
      return {
        color: 'rgba(255, 107, 53, 0.40)',
        weight: 0.8,
        fillColor: 'rgba(255, 107, 53, 0.05)',
        fillOpacity: 0.15
      };
    }

    // Scene 2: CHANGE — illuminate cells with confirmed spectral displacement
    if (guidedScene === 2) {
      if (level === 'HIGH' || level === 'MEDIUM') {
        return {
          color: '#FF6B35',
          weight: 1.2,
          fillColor: level === 'HIGH' ? '#EF4444' : '#FF6B35',
          fillOpacity: 0.45
        };
      }
      return {
        color: 'rgba(255, 255, 255, 0.03)',
        weight: 0.2,
        fillColor: 'transparent',
        fillOpacity: 0
      };
    }

    // Scene 3: ANOMALY — illuminate fused high and medium priority anomaly polygons
    if (guidedScene === 3) {
      if (level === 'HIGH') {
        return {
          color: '#EF4444',
          weight: 1.8,
          fillColor: '#EF4444',
          fillOpacity: 0.65
        };
      }
      if (level === 'MEDIUM') {
        return {
          color: '#F59E0B',
          weight: 0.9,
          fillColor: '#F59E0B',
          fillOpacity: 0.25
        };
      }
      return {
        color: 'rgba(255, 255, 255, 0.02)',
        weight: 0.2,
        fillColor: 'transparent',
        fillOpacity: 0
      };
    }

    // Standard / Scenes 4-7 styling
    if (isSelected) {
      return {
        color: '#FF6B35',
        weight: 2.2,
        fillColor: level === 'HIGH' ? '#EF4444' : '#F59E0B',
        fillOpacity: 0.70
      };
    }

    if (level === 'HIGH') {
      return {
        color: '#EF4444',
        weight: 1.2,
        fillColor: '#EF4444',
        fillOpacity: 0.55
      };
    }

    if (level === 'MEDIUM') {
      return {
        color: 'rgba(245, 158, 11, 0.35)',
        weight: 0.5,
        fillColor: '#F59E0B',
        fillOpacity: 0.10
      };
    }

    // NORMAL: very calm & subtle
    return {
      color: 'rgba(255, 255, 255, 0.03)',
      weight: 0.3,
      fillColor: 'transparent',
      fillOpacity: 0.0
    };
  };

  const rawScore = selectedCell?.priority_score ?? selectedCell?.priorityScore ?? 82;
  const displayScore =
    typeof rawScore === 'number' && rawScore < 1
      ? Math.round(rawScore * 100)
      : Math.round(rawScore);

  return (
    <div className="product-map-frame" aria-label="Geospatial map frame">
      <MapContainer
        center={selectedCentroid}
        zoom={13}
        scrollWheelZoom={true}
        zoomControl={false}
        style={{ height: '100%', width: '100%', background: '#080D14' }}
      >
        {/* Zero-Key Free Esri World Dark Gray Basemap (No API key, no watermark) */}
        <TileLayer
          attribution='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          maxZoom={19}
          maxNativeZoom={16}
        />
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
          maxZoom={19}
          maxNativeZoom={16}
        />

        {/* Floating Top-Right Map Controls & Flight Handler */}
        <MapControlsManager
          cameraTarget={cameraTarget}
          targetCoord={selectedCentroid}
        />

        {/* All Monitored Cells */}
        {areas.map((cell) => {
          const positions = getPolygonPositions(cell);
          const level = (cell.priority_level || 'LOW').toUpperCase();
          const score = cell.priority_score ?? 0;
          const formattedScore =
            typeof score === 'number' && score < 1
              ? (score * 100).toFixed(0)
              : Number(score).toFixed(0);

          const cellTooltip = (
            <Tooltip direction="top" offset={[0, -6]} className="clean-cell-tooltip">
              <div className="tooltip-inner font-mono">
                <span className="tooltip-id">{cell.grid_id}</span>
                <span className={`tooltip-lvl lvl-${level.toLowerCase()}`}>{level}</span>
                <span className="tooltip-score">{formattedScore}</span>
              </div>
            </Tooltip>
          );

          if (positions && positions.length > 0) {
            return (
              <Polygon
                key={cell.grid_id}
                positions={positions}
                pathOptions={getCellStyle(cell)}
                eventHandlers={{
                  click: () => onSelectCell && onSelectCell(cell.grid_id)
                }}
              >
                {cellTooltip}
              </Polygon>
            );
          }

          return (
            <CircleMarker
              key={cell.grid_id}
              center={[cell.lat, cell.lng]}
              radius={7}
              pathOptions={getCellStyle(cell)}
              eventHandlers={{
                click: () => onSelectCell && onSelectCell(cell.grid_id)
              }}
            >
              {cellTooltip}
            </CircleMarker>
          );
        })}

        {/* Selected Location Target Radar Marker */}
        {selectedCentroid && (
          <>
            <CircleMarker
              center={selectedCentroid}
              radius={24}
              pathOptions={{
                color: '#FF6B35',
                weight: 1.5,
                fillColor: '#FF6B35',
                fillOpacity: 0.14,
                className: 'target-radar-pulse'
              }}
            />
            <CircleMarker
              center={selectedCentroid}
              radius={12}
              pathOptions={{
                color: '#FF6B35',
                weight: 1.5,
                fillColor: 'transparent',
                fillOpacity: 0
              }}
            />
            <CircleMarker
              center={selectedCentroid}
              radius={4}
              pathOptions={{
                color: '#FFFFFF',
                weight: 1.5,
                fillColor: '#FF6B35',
                fillOpacity: 1
              }}
            >
              <Tooltip
                permanent
                direction="top"
                offset={[0, -14]}
                className="target-tag-tooltip"
              >
                <div className="target-tag font-mono">
                  <span>{selectedGridId}</span>
                  <span className="text-orange">{displayScore}</span>
                </div>
              </Tooltip>
            </CircleMarker>
          </>
        )}
      </MapContainer>

      {/* Floating Top-Left Status Pill Over Map */}
      <div className="map-floating-header-pill font-mono">
        <span className="pill-dot-live" aria-hidden="true" />
        <span className="pill-region">HYDERABAD METROPOLITAN AREA</span>
        <span className="pill-sep">&bull;</span>
        <span className="pill-meta text-muted">SENTINEL-2 EARTH OBSERVATION</span>
      </div>

      {/* Floating Bottom-Left Tiny Legend */}
      <div className="map-floating-legend font-mono" aria-label="Map legend">
        <div className="legend-chip">
          <span className="legend-dot dot-normal" />
          <span>Normal</span>
        </div>
        <div className="legend-chip">
          <span className="legend-dot dot-medium" />
          <span>Medium</span>
        </div>
        <div className="legend-chip">
          <span className="legend-dot dot-high" />
          <span>High</span>
        </div>
        <div className="legend-chip">
          <span className="legend-dot dot-selected" />
          <span>Selected</span>
        </div>
      </div>
    </div>
  );
}
