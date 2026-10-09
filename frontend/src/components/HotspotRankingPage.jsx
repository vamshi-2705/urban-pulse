import React, { useState, useEffect, useMemo } from 'react';
import { fetchHotspots, fetchAreas } from '../api/client';
import Breadcrumbs from './Breadcrumbs';
import HotspotTable from './HotspotTable';
import HotspotSideMap from './HotspotSideMap';
import TemporalBar from './TemporalBar';

/**
 * Urban IQ Prioritized Anomaly Ranking Board
 * Provides an evidence-ranked queue for field inspector dispatch
 * based on multi-temporal Sentinel-2 spectral divergence.
 */
export default function HotspotRankingPage({
  activePeriod = '2020_2026',
  onSelectPeriod
}) {
  const [hotspots, setHotspots] = useState([]);
  const [hoveredId, setHoveredId] = useState(null);
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const [hotspotsRes, areasRes] = await Promise.all([
          fetchHotspots({ period: activePeriod }),
          fetchAreas(activePeriod).catch(() => ({ areas: [] }))
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
  }, [activePeriod, retryTrigger]);

  const highCount = useMemo(() => {
    return hotspots.filter(
      (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'HIGH'
    ).length;
  }, [hotspots]);

  const mediumCount = useMemo(() => {
    return hotspots.filter(
      (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'MEDIUM'
    ).length;
  }, [hotspots]);

  const periodLabel = activePeriod.replace('_', ' → ');

  if (loading) {
    return (
      <div className="ranking-page-container loading-state">
        <div className="ranking-loading-card">
          <div className="skeleton-spinner" />
          <h3 className="loading-title">Loading Prioritized Hotspot Rankings</h3>
          <p className="loading-desc font-mono">
            Synthesizing Sentinel-2 anomaly scores for analysis window {periodLabel}...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ranking-page-container">
        <div className="ranking-error-card">
          <div className="error-icon" aria-hidden="true">&#9888;</div>
          <h3 className="error-title">Failed to load hotspot rankings</h3>
          <p className="error-details font-mono">{error}</p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setRetryTrigger((prev) => prev + 1)}
          >
            Retry Loading Rankings
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ranking-page-container" id="ranking-scroll-container">
      {/* 1. Municipal Breadcrumb Navigation */}
      <div className="ranking-breadcrumbs-bar">
        <Breadcrumbs
          items={[
            { label: 'Map Overview', to: '/' },
            { label: `Prioritized Queue (${periodLabel})` }
          ]}
        />
      </div>

      {/* 2. Top Command Deck with Title & Period Selector */}
      <div className="ranking-header-deck">
        <div className="header-deck-info">
          <div className="deck-tag-row font-mono">
            <span className="deck-tag-telemetry">ESA SENTINEL-2 L2A</span>
            <span className="deck-tag-dot">&bull;</span>
            <span className="deck-tag-telemetry">10M RESOLUTION</span>
            <span className="deck-tag-dot">&bull;</span>
            <span className="deck-tag-telemetry">HYDERABAD MUNICIPALITY</span>
          </div>
          <h1 className="deck-title">Prioritized Investigation Queue</h1>
          <p className="deck-subtitle">
            Ranked queue for municipal field verification based on multi-temporal spectral anomaly detection
          </p>
        </div>

        {/* Period Switcher in Command Deck */}
        <div className="header-deck-period">
          <span className="period-dock-label font-mono">ANALYSIS PERIOD</span>
          <TemporalBar
            activePeriod={activePeriod}
            onSelectPeriod={onSelectPeriod}
          />
        </div>
      </div>

      {/* 3. Telemetry KPI Stat Strip */}
      <div className="ranking-kpi-grid">
        <div className="ranking-kpi-card">
          <span className="kpi-label font-mono">MONITORED CELLS</span>
          <div className="kpi-value font-mono">
            {hotspots.length > 0 ? hotspots.length.toLocaleString() : '1,462'}
          </div>
          <span className="kpi-subtext">Uniform 500m &times; 500m grid</span>
        </div>

        <div className="ranking-kpi-card kpi-high">
          <div className="kpi-label-row font-mono">
            <span className="kpi-label text-red">HIGH PRIORITY FLAGS</span>
            <span className="kpi-dot dot-red" aria-hidden="true" />
          </div>
          <div className="kpi-value text-red font-mono">{highCount}</div>
          <span className="kpi-subtext">Immediate ground deployment</span>
        </div>

        <div className="ranking-kpi-card kpi-medium">
          <div className="kpi-label-row font-mono">
            <span className="kpi-label text-amber">MEDIUM DIVERGENCE</span>
            <span className="kpi-dot dot-amber" aria-hidden="true" />
          </div>
          <div className="kpi-value text-amber font-mono">{mediumCount}</div>
          <span className="kpi-subtext">Secondary municipal monitor</span>
        </div>

        <div className="ranking-kpi-card">
          <span className="kpi-label font-mono">OBSERVATION WINDOW</span>
          <div className="kpi-value font-mono text-orange">{periodLabel}</div>
          <span className="kpi-subtext">Sentinel-2 BOA Multispectral</span>
        </div>
      </div>

      {/* 4. Municipal Decision-Support Directive Notice */}
      <div className="ranking-legal-banner" id="ranking-legal-notice">
        <div className="banner-icon-badge" aria-hidden="true">&#9432;</div>
        <div className="banner-content">
          <div className="banner-title font-mono">MUNICIPAL DECISION-SUPPORT DIRECTIVE</div>
          <div className="banner-text">
            Ranked queue for field inspector deployment for analysis window <strong>{periodLabel}</strong> based on anomalous multi-temporal divergence.
            &ldquo;Unusual spatial change detected. Field verification recommended.&rdquo;
          </div>
        </div>
      </div>

      {/* 5. Main Layout: Datatable + Side Map Preview */}
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

        {/* Small Side Map */}
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
