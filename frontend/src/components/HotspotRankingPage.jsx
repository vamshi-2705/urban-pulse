import React, { useState, useEffect } from 'react';
import { fetchHotspots, fetchAreas } from '../api/client';
import HotspotTable from './HotspotTable';
import HotspotSideMap from './HotspotSideMap';

export default function HotspotRankingPage() {
  const [hotspots, setHotspots] = useState([]);
  const [hoveredId, setHoveredId] = useState(null);
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const [hotspotsRes, areasRes] = await Promise.all([
          fetchHotspots(),
          fetchAreas().catch(() => ({ areas: [] }))
        ]);

        // Merge geometry from areas if available
        const areasMap = new Map();
        (areasRes?.areas || []).forEach((a) => {
          areasMap.set(a.grid_id.toLowerCase(), a);
        });

        const mergedHotspots = (hotspotsRes || []).map((h) => {
          const area = areasMap.get((h.grid_id || h.id || '').toLowerCase());
          return {
            ...h,
            geometry: h.geometry || area?.geometry || null,
            lat: h.lat ?? (h.coordinates ? h.coordinates[0] : area?.lat),
            lng: h.lng ?? (h.coordinates ? h.coordinates[1] : area?.lng)
          };
        });

        setHotspots(mergedHotspots);
      } catch (err) {
        console.error('Failed to load hotspots:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="ranking-page-container loading-state" style={{ padding: '40px 20px', textAlign: 'center' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 12px' }} />
        <p style={{ fontWeight: 600 }}>Loading prioritized hotspot rankings...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ranking-page-container" style={{ padding: '24px' }}>
        <div className="error-card">
          <p style={{ color: 'var(--status-high)', fontWeight: 600 }}>Failed to load hotspot ranking</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ranking-page-container" style={{ padding: '0 20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Defensible Operational Guidance Notice */}
      <div className="legal-notice-box" id="ranking-legal-notice">
        <strong>Municipal Decision-Support Notice:</strong>{' '}
        Ranked queue for field inspector deployment based on anomalous multi-temporal divergence.
        &ldquo;Unusual spatial change detected. Field verification recommended.&rdquo;
      </div>

      {/* Main Responsive Layout: Table + Side Map if it fits */}
      <div className="ranking-layout-grid">
        <div className="ranking-table-column">
          <HotspotTable
            hotspots={hotspots}
            hoveredId={hoveredId}
            onHoverHotspot={setHoveredId}
            filterLevel={filterLevel}
            onFilterChange={setFilterLevel}
          />
        </div>

        {/* Small Side Map (conditionally styled to display when layout width allows) */}
        <div className="ranking-sidemap-column">
          <HotspotSideMap
            hotspots={hotspots}
            hoveredId={hoveredId}
          />
        </div>
      </div>
    </div>
  );
}
