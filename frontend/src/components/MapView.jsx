import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, Popup, useMap } from 'react-leaflet';

/**
 * Controller to smoothly adjust map viewport when selection changes
 */
function MapController({ selectedCell, center, zoom }) {
  const map = useMap();

  useEffect(() => {
    if (selectedCell && selectedCell.center) {
      map.flyTo(selectedCell.center, Math.max(map.getZoom(), 14), {
        duration: 0.6
      });
    }
  }, [selectedCell, map]);

  return null;
}

export default function MapView({
  cells = [],
  selectedCellId,
  onSelectCell,
  overview
}) {
  const [filterLevel, setFilterLevel] = useState('ALL'); // 'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'

  const center = overview?.center || [17.385, 78.486];
  const defaultZoom = overview?.defaultZoom || 12;

  // Filter cells based on user selection
  const filteredCells = cells.filter((c) => {
    if (filterLevel === 'ALL') return true;
    const level = (c.priority_level || c.priorityLevel || '').toUpperCase();
    return level === filterLevel;
  });

  // Cell counts
  const highCount = cells.filter(c => (c.priority_level || c.priorityLevel || '').toUpperCase() === 'HIGH').length;
  const mediumCount = cells.filter(c => (c.priority_level || c.priorityLevel || '').toUpperCase() === 'MEDIUM').length;
  const lowCount = cells.filter(c => (c.priority_level || c.priorityLevel || '').toUpperCase() === 'LOW').length;

  const selectedCell = cells.find(c => (c.grid_id || c.cellId) === selectedCellId);

  // Style helper based on priority level
  const getPolygonStyle = (cell) => {
    const isSelected = (cell.grid_id || cell.cellId) === selectedCellId;
    const level = (cell.priority_level || cell.priorityLevel || '').toUpperCase();

    if (isSelected) {
      return {
        color: '#1e3a8a',
        weight: 3.5,
        fillColor: level === 'HIGH' ? '#dc2626' : level === 'MEDIUM' ? '#d97706' : '#16a34a',
        fillOpacity: 0.85
      };
    }

    switch (level) {
      case 'HIGH':
        return {
          color: '#dc2626',
          weight: 2,
          fillColor: '#dc2626',
          fillOpacity: 0.65
        };
      case 'MEDIUM':
        return {
          color: '#d97706',
          weight: 1.5,
          fillColor: '#d97706',
          fillOpacity: 0.45
        };
      case 'LOW':
      default:
        return {
          color: '#16a34a',
          weight: 1,
          fillColor: '#16a34a',
          fillOpacity: 0.15
        };
    }
  };

  // Convert GeoJSON Polygon [lng, lat] to Leaflet Polygon [lat, lng]
  const getPositions = (cell) => {
    if (cell.geometry?.coordinates?.[0]) {
      return cell.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
    }
    if (cell.bounds) {
      const [[minLat, minLng], [maxLat, maxLng]] = cell.bounds;
      return [
        [minLat, minLng],
        [maxLat, minLng],
        [maxLat, maxLng],
        [minLat, maxLng]
      ];
    }
    return [];
  };

  return (
    <section className="map-card" aria-label="Interactive geospatial observation map">
      {/* Map Control & Filter Toolbar */}
      <div className="map-header">
        <div className="map-header-left">
          <span className="map-title">Monitored Region Grid</span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Showing {filteredCells.length} of {cells.length} square cells (~500 m)
          </span>
        </div>

        <div className="map-filters">
          <button
            type="button"
            className={`filter-btn ${filterLevel === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterLevel('ALL')}
          >
            All <span className="badge-count">{cells.length}</span>
          </button>
          <button
            type="button"
            className={`filter-btn ${filterLevel === 'HIGH' ? 'active' : ''}`}
            onClick={() => setFilterLevel('HIGH')}
          >
            High <span className="badge-count">{highCount}</span>
          </button>
          <button
            type="button"
            className={`filter-btn ${filterLevel === 'MEDIUM' ? 'active' : ''}`}
            onClick={() => setFilterLevel('MEDIUM')}
          >
            Medium <span className="badge-count">{mediumCount}</span>
          </button>
          <button
            type="button"
            className={`filter-btn ${filterLevel === 'LOW' ? 'active' : ''}`}
            onClick={() => setFilterLevel('LOW')}
          >
            Low <span className="badge-count">{lowCount}</span>
          </button>

          {/* Quick Focus Hotspots Selector */}
          <select
            style={{
              padding: '3px 8px',
              fontSize: '11px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-default)',
              backgroundColor: 'var(--bg-surface)'
            }}
            value={selectedCellId || ''}
            onChange={(e) => onSelectCell(e.target.value)}
            aria-label="Focus top hotspot"
          >
            <option value="">Focus top hotspot...</option>
            {cells
              .filter(c => (c.priority_level || c.priorityLevel || '').toUpperCase() === 'HIGH')
              .map(c => (
                <option key={c.grid_id || c.cellId} value={c.grid_id || c.cellId}>
                  {c.grid_id || c.cellId} — Score: {c.priority_score || c.priorityScore} (High)
                </option>
              ))}
          </select>
        </div>
      </div>

      {/* Map Container Viewport */}
      <div className="map-wrapper">
        <MapContainer
          center={center}
          zoom={defaultZoom}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapController
            selectedCell={selectedCell}
            center={center}
            zoom={defaultZoom}
          />

          {filteredCells.map((cell) => {
            const id = cell.grid_id || cell.cellId;
            const positions = getPositions(cell);
            if (positions.length === 0) return null;

            const score = cell.priority_score || cell.priorityScore || 0;
            const level = (cell.priority_level || cell.priorityLevel || 'LOW').toUpperCase();
            const metric = cell.changeMetric || (cell.score_breakdown ? `Urban: +${cell.score_breakdown.urban_expansion}` : 'Observed shift');

            return (
              <Polygon
                key={id}
                positions={positions}
                pathOptions={getPolygonStyle(cell)}
                eventHandlers={{
                  click: () => onSelectCell(id)
                }}
              >
                <Popup>
                  <div className="popup-card">
                    <div className="popup-header">
                      <span className="popup-title">{id}</span>
                      <span className={`badge ${level === 'HIGH' ? 'badge-high' : level === 'MEDIUM' ? 'badge-medium' : 'badge-normal'}`}>
                        {level} ({score})
                      </span>
                    </div>
                    <div className="popup-body">
                      <div className="popup-metric">{metric}</div>
                      <div style={{ color: 'var(--text-muted)' }}>
                        Ward/Zone: {cell.wardName || 'Hyderabad Urban'}
                      </div>
                      {cell.reasons && cell.reasons.length > 0 && (
                        <div className="popup-reasons">
                          &ldquo;{cell.reasons[0]}&rdquo;
                        </div>
                      )}
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Field verification recommended.
                      </div>
                    </div>
                    <div className="popup-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        style={{ fontSize: '11px', padding: '3px 8px' }}
                        onClick={() => onSelectCell(id)}
                      >
                        Inspect Evidence &rarr;
                      </button>
                    </div>
                  </div>
                </Popup>
              </Polygon>
            );
          })}
        </MapContainer>

        {/* Map Legend */}
        <div className="map-legend" aria-label="Map color legend">
          <div className="map-legend-title">Priority Legend</div>
          <div className="legend-item">
            <span className="legend-color-box" style={{ backgroundColor: '#dc2626' }} />
            <span>High priority (Urgent verification)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color-box" style={{ backgroundColor: '#d97706' }} />
            <span>Medium priority (Secondary inspection)</span>
          </div>
          <div className="legend-item">
            <span className="legend-color-box" style={{ backgroundColor: '#16a34a' }} />
            <span>Low priority (Baseline monitoring)</span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-light)', paddingTop: '4px' }}>
            Fixed ~500m&sup2; multi-temporal cell grid
          </div>
        </div>
      </div>
    </section>
  );
}
