import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Polygon, CircleMarker, Popup, useMap } from 'react-leaflet';
import { useNavigate } from 'react-router-dom';

function SideMapFocusController({ targetCoord }) {
  const map = useMap();

  useEffect(() => {
    if (targetCoord && targetCoord.length === 2) {
      map.panTo(targetCoord, { animate: true, duration: 0.4 });
    }
  }, [targetCoord, map]);

  return null;
}

function SideMapBoundsFitter({ bounds }) {
  const map = useMap();

  useEffect(() => {
    if (bounds && bounds.length === 2) {
      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 13 });
    }
  }, [bounds, map]);

  return null;
}

export default function HotspotSideMap({
  hotspots = [],
  hoveredId = null
}) {
  const navigate = useNavigate();

  // Find hovered hotspot coordinates
  const hoveredHotspot = useMemo(() => {
    if (!hoveredId) return null;
    return hotspots.find(
      (h) => (h.grid_id || h.id || h.cellId) === hoveredId
    ) || null;
  }, [hotspots, hoveredId]);

  const targetCoord = useMemo(() => {
    if (!hoveredHotspot) return null;
    if (hoveredHotspot.lat && hoveredHotspot.lng) {
      return [hoveredHotspot.lat, hoveredHotspot.lng];
    }
    if (hoveredHotspot.coordinates && hoveredHotspot.coordinates.length === 2) {
      return hoveredHotspot.coordinates;
    }
    return null;
  }, [hoveredHotspot]);

  // Compute bounding box of all hotspots
  const bounds = useMemo(() => {
    if (!hotspots.length) return null;
    let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;

    hotspots.forEach((h) => {
      const lat = h.lat ?? (h.coordinates ? h.coordinates[0] : null);
      const lng = h.lng ?? (h.coordinates ? h.coordinates[1] : null);
      if (lat && lng) {
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
      }
    });

    if (minLat === Infinity || minLng === Infinity) return null;
    return [[minLat, minLng], [maxLat, maxLng]];
  }, [hotspots]);

  const defaultCenter = useMemo(() => {
    if (bounds) {
      return [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2];
    }
    return [17.385, 78.486];
  }, [bounds]);

  const getStyle = (item) => {
    const id = item.grid_id || item.id || item.cellId;
    const isHovered = id === hoveredId;
    const level = (item.priority_level || item.priorityLevel || 'LOW').toUpperCase();

    if (isHovered) {
      return {
        color: '#1e3a8a',
        weight: 3.5,
        fillColor: level === 'HIGH' ? '#ef4444' : '#f59e0b',
        fillOpacity: 0.9
      };
    }

    if (level === 'HIGH') {
      return {
        color: '#b91c1c',
        weight: 1.8,
        fillColor: '#dc2626',
        fillOpacity: 0.65
      };
    }

    return {
      color: '#b45309',
      weight: 1.5,
      fillColor: '#d97706',
      fillOpacity: 0.50
    };
  };

  const getPositions = (item) => {
    if (item.geometry?.coordinates?.[0]) {
      return item.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
    }
    return null;
  };

  return (
    <aside className="side-map-panel" aria-label="Geospatial location preview map">
      <div className="side-map-header">
        <span className="side-map-title">Location Preview</span>
        {hoveredHotspot ? (
          <span className="side-map-hover-tag">
            Active: <strong>{hoveredHotspot.grid_id || hoveredHotspot.id}</strong> (Score {hoveredHotspot.priority_score ?? hoveredHotspot.priorityScore})
          </span>
        ) : (
          <span className="side-map-hint">Hover a row to highlight</span>
        )}
      </div>

      <div className="side-map-viewport">
        <MapContainer
          center={defaultCenter}
          zoom={12}
          scrollWheelZoom={false}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {bounds && <SideMapBoundsFitter bounds={bounds} />}
          {targetCoord && <SideMapFocusController targetCoord={targetCoord} />}

          {hotspots.map((item) => {
            const id = item.grid_id || item.id || item.cellId;
            const positions = getPositions(item);
            const lat = item.lat ?? (item.coordinates ? item.coordinates[0] : null);
            const lng = item.lng ?? (item.coordinates ? item.coordinates[1] : null);
            const isHovered = id === hoveredId;

            const popupContent = (
              <Popup>
                <div style={{ fontSize: '11px', padding: '4px' }}>
                  <strong>{id}</strong> (Rank #{item.rank})
                  <div style={{ color: 'var(--text-muted)' }}>Score: {item.priority_score ?? item.priorityScore}</div>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ fontSize: '10px', padding: '2px 6px', marginTop: '4px' }}
                    onClick={() => navigate(`/hotspot/${id}`)}
                  >
                    Open details &rarr;
                  </button>
                </div>
              </Popup>
            );

            if (positions && positions.length > 0) {
              return (
                <Polygon
                  key={id}
                  positions={positions}
                  pathOptions={getStyle(item)}
                >
                  {popupContent}
                </Polygon>
              );
            }

            if (lat && lng) {
              return (
                <CircleMarker
                  key={id}
                  center={[lat, lng]}
                  radius={isHovered ? 12 : 8}
                  pathOptions={getStyle(item)}
                >
                  {popupContent}
                </CircleMarker>
              );
            }

            return null;
          })}
        </MapContainer>
      </div>
    </aside>
  );
}
