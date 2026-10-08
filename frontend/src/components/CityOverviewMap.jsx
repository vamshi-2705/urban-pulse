import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, CircleMarker, Popup, useMap } from 'react-leaflet';
import { useNavigate } from 'react-router-dom';

/**
 * Controller to fit the map viewport exactly to the bounding box of all monitored cells
 */
function BoundsFitter({ bounds }) {
  const map = useMap();

  useEffect(() => {
    if (bounds && bounds.length === 2) {
      map.fitBounds(bounds, {
        padding: [30, 30],
        maxZoom: 14,
        animate: true,
        duration: 0.8
      });
    }
  }, [bounds, map]);

  return null;
}

/**
 * Focus controller when a specific cell is selected
 */
function CellFocusController({ targetCoord }) {
  const map = useMap();

  useEffect(() => {
    if (targetCoord && targetCoord.length === 2) {
      map.flyTo(targetCoord, Math.max(map.getZoom(), 14), {
        duration: 0.5
      });
    }
  }, [targetCoord, map]);

  return null;
}

export default function CityOverviewMap({
  areas = [],
  selectedGridId,
  onSelectCell,
  loading = false,
  error = null,
  onRetry
}) {
  const navigate = useNavigate();
  const [filterMode, setFilterMode] = useState('all'); // 'all' | 'anomalous'
  const [focusTarget, setFocusTarget] = useState(null);

  // Compute bounding box across all areas
  const bounds = useMemo(() => {
    if (!areas || areas.length === 0) return null;

    let minLat = Infinity;
    let maxLat = -Infinity;
    let minLng = Infinity;
    let maxLng = -Infinity;

    areas.forEach((cell) => {
      if (cell.geometry?.coordinates?.[0]) {
        cell.geometry.coordinates[0].forEach(([lng, lat]) => {
          if (lat < minLat) minLat = lat;
          if (lat > maxLat) maxLat = lat;
          if (lng < minLng) minLng = lng;
          if (lng > maxLng) maxLng = lng;
        });
      } else if (cell.lat && cell.lng) {
        if (cell.lat < minLat) minLat = cell.lat;
        if (cell.lat > maxLat) maxLat = cell.lat;
        if (cell.lng < minLng) minLng = cell.lng;
        if (cell.lng > maxLng) maxLng = cell.lng;
      }
    });

    if (minLat === Infinity || minLng === Infinity) return null;
    return [
      [minLat, minLng],
      [maxLat, maxLng]
    ];
  }, [areas]);

  // Default center
  const defaultCenter = useMemo(() => {
    if (bounds) {
      return [
        (bounds[0][0] + bounds[1][0]) / 2,
        (bounds[0][1] + bounds[1][1]) / 2
      ];
    }
    return [17.385, 78.486]; // Hyderabad default
  }, [bounds]);

  // Counts
  const anomalousCount = useMemo(() => {
    return areas.filter(
      (c) => c.priority_level === 'HIGH' || c.priority_level === 'MEDIUM'
    ).length;
  }, [areas]);

  // Filtered cells based on toggle
  const visibleCells = useMemo(() => {
    if (filterMode === 'anomalous') {
      return areas.filter(
        (c) => c.priority_level === 'HIGH' || c.priority_level === 'MEDIUM'
      );
    }
    return areas;
  }, [areas, filterMode]);

  // Convert GeoJSON coordinates [lng, lat] to Leaflet [lat, lng]
  const getPolygonPositions = (cell) => {
    if (cell.geometry?.coordinates?.[0]) {
      return cell.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
    }
    return null;
  };

  // Styling helper:
  // "Keep LOW cells very light and low-opacity so red and amber stand out."
  const getCellStyle = (cell) => {
    const isSelected = cell.grid_id === selectedGridId;
    const level = (cell.priority_level || '').toUpperCase();

    if (isSelected) {
      return {
        color: '#1e3a8a',
        weight: 3.5,
        fillColor: level === 'HIGH' ? '#dc2626' : level === 'MEDIUM' ? '#d97706' : '#16a34a',
        fillOpacity: 0.85
      };
    }

    if (level === 'HIGH') {
      return {
        color: '#b91c1c',
        weight: 2,
        fillColor: '#dc2626',
        fillOpacity: 0.72
      };
    }

    if (level === 'MEDIUM') {
      return {
        color: '#b45309',
        weight: 1.5,
        fillColor: '#d97706',
        fillOpacity: 0.52
      };
    }

    // LOW priority (Normal): Keep very light and low-opacity
    return {
      color: '#16a34a',
      weight: 0.6,
      fillColor: '#22c55e',
      fillOpacity: 0.08
    };
  };

  const handleCellClick = (cell) => {
    if (onSelectCell) {
      onSelectCell(cell.grid_id);
    }
    if (cell.lat && cell.lng) {
      setFocusTarget([cell.lat, cell.lng]);
    }
  };

  const handleOpenDetails = (gridId) => {
    navigate(`/hotspot/${gridId}`);
  };

  if (loading) {
    return (
      <div className="map-card loading-state">
        <div className="map-skeleton">
          <div className="skeleton-spinner" />
          <p>Loading geospatial areas & observations...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="map-card error-state">
        <div style={{ padding: '32px 24px', textAlign: 'center' }}>
          <p style={{ color: 'var(--status-high)', fontWeight: 700, fontSize: '15px' }}>Error loading map areas</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{error}</p>
          {onRetry && (
            <button type="button" className="btn btn-primary" style={{ marginTop: '16px' }} onClick={onRetry}>
              Retry loading map
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!loading && !error && areas.length === 0) {
    return (
      <div className="map-card empty-state">
        <div style={{ padding: '40px 24px', textAlign: 'center' }}>
          <p style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>No Monitored Cells Available</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
            No geospatial intelligence records were returned for this region. Verify data provider connection.
          </p>
          {onRetry && (
            <button type="button" className="btn btn-outline-primary" style={{ marginTop: '16px' }} onClick={onRetry}>
              Refresh data
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <section className="map-card" aria-label="City overview geospatial map">
      {/* Map Control Toolbar with Toggle */}
      <div className="map-header">
        <div className="map-header-left">
          <span className="map-title">City Spatial Overview</span>
          <span className="map-cell-count">
            Showing {visibleCells.length} of {areas.length} grid cells (~500 m)
          </span>
        </div>

        {/* Toggle: All cells / Anomalous only */}
        <div className="map-toggle-group" role="group" aria-label="Cell visibility filter">
          <button
            type="button"
            className={`toggle-btn ${filterMode === 'all' ? 'active' : ''}`}
            onClick={() => setFilterMode('all')}
          >
            All cells <span className="toggle-badge">{areas.length}</span>
          </button>
          <button
            type="button"
            className={`toggle-btn ${filterMode === 'anomalous' ? 'active' : ''}`}
            onClick={() => setFilterMode('anomalous')}
          >
            Anomalous only <span className="toggle-badge text-amber">{anomalousCount}</span>
          </button>
        </div>
      </div>

      {/* Map Viewport */}
      <div className="map-wrapper" style={{ height: '540px', position: 'relative' }}>
        <MapContainer
          center={defaultCenter}
          zoom={12}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* Automatic bounds fitting to /api/areas */}
          {bounds && <BoundsFitter bounds={bounds} />}

          {/* Focus controller on user click */}
          {focusTarget && <CellFocusController targetCoord={focusTarget} />}

          {visibleCells.map((cell) => {
            const positions = getPolygonPositions(cell);
            const level = (cell.priority_level || 'LOW').toUpperCase();
            const score = cell.priority_score ?? 0;
            const mainReason = (cell.reasons && cell.reasons.length > 0)
              ? cell.reasons[0]
              : (level === 'HIGH' ? 'Rapid built-up expansion & significant vegetation loss'
                 : level === 'MEDIUM' ? 'Localized land cover divergence from baseline'
                 : 'Stable nominal baseline observation');

            const popupContent = (
              <Popup>
                <div className="popup-card">
                  <div className="popup-header">
                    <span className="popup-title">{cell.grid_id}</span>
                    <span className={`badge ${level === 'HIGH' ? 'badge-high' : level === 'MEDIUM' ? 'badge-medium' : 'badge-normal'}`}>
                      {level}
                    </span>
                  </div>

                  <div className="popup-body">
                    <div className="popup-score-row">
                      <span className="popup-score-label">Priority score:</span>
                      <strong className="popup-score-val">{score} / 100</strong>
                    </div>

                    <div className="popup-reason-box">
                      <span className="popup-reason-heading">Main reason:</span>
                      <p className="popup-reason-text">&ldquo;{mainReason}&rdquo;</p>
                    </div>

                    <div className="popup-status-note">
                      Field verification recommended.
                    </div>
                  </div>

                  <div className="popup-actions">
                    <button
                      type="button"
                      className="btn btn-primary btn-open-details"
                      onClick={() => handleOpenDetails(cell.grid_id)}
                    >
                      Open details &rarr;
                    </button>
                  </div>
                </div>
              </Popup>
            );

            // Draw as polygon if geometry present, fall back to circle if no geometry
            if (positions && positions.length > 0) {
              return (
                <Polygon
                  key={cell.grid_id}
                  positions={positions}
                  pathOptions={getCellStyle(cell)}
                  eventHandlers={{
                    click: () => handleCellClick(cell)
                  }}
                >
                  {popupContent}
                </Polygon>
              );
            }

            return (
              <CircleMarker
                key={cell.grid_id}
                center={[cell.lat, cell.lng]}
                radius={10}
                pathOptions={getCellStyle(cell)}
                eventHandlers={{
                  click: () => handleCellClick(cell)
                }}
              >
                {popupContent}
              </CircleMarker>
            );
          })}
        </MapContainer>

        {/* Legend bottom-left (Normal, Moderate, High priority) */}
        <div className="map-legend bottom-left" aria-label="Priority color legend">
          <div className="map-legend-title">Priority Level</div>
          <div className="legend-item">
            <span
              className="legend-color-box"
              style={{
                backgroundColor: 'rgba(34, 197, 94, 0.25)',
                border: '1px solid #16a34a'
              }}
            />
            <span>Normal</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-box"
              style={{
                backgroundColor: '#d97706',
                border: '1px solid #b45309'
              }}
            />
            <span>Moderate</span>
          </div>
          <div className="legend-item">
            <span
              className="legend-color-box"
              style={{
                backgroundColor: '#dc2626',
                border: '1px solid #b91c1c'
              }}
            />
            <span>High priority</span>
          </div>
        </div>
      </div>
    </section>
  );
}
