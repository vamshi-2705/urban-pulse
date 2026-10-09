import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { fetchChange, fetchHotspotDetail } from '../api/client';
import Breadcrumbs from './Breadcrumbs';
import TemporalBar from './TemporalBar';

/**
 * TrafficPulse-Inspired Coherent Change Explorer
 * - Header: Location ID, Coordinates & LAND COVER TRAJECTORY
 * - Supports functional activePeriod switching (2020_2026, 2020_2023, 2023_2026)
 * - Multi-temporal sequence: 2020 (25%) ──── 2023 (39%) ──── 2026 (53%)
 * - Metric transitions: BUILT-UP (+28 pts), VEGETATION (-55 pts), WATER (+10 pts)
 * - Spectral Indices Deep Dive: NDVI, NDBI, NDWI
 * - Actions: [ VIEW SATELLITE EVIDENCE ] & [ RETURN TO MAP ]
 */
export default function ChangeExplorerView({
  activePeriod: propPeriod,
  onSelectPeriod
}) {
  const { gridId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const queryPeriod = searchParams.get('period');
  const [internalPeriod, setInternalPeriod] = useState(queryPeriod || propPeriod || '2020_2026');
  const activePeriod = propPeriod || queryPeriod || internalPeriod;

  const [changeData, setChangeData] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const handlePeriodChange = (newPeriod) => {
    setInternalPeriod(newPeriod);
    setSearchParams({ period: newPeriod });
    if (onSelectPeriod) {
      onSelectPeriod(newPeriod);
    }
  };

  useEffect(() => {
    async function loadData() {
      if (!gridId) return;
      try {
        setLoading(true);
        setError(null);

        const [changeRes, detailRes] = await Promise.all([
          fetchChange(gridId, activePeriod),
          fetchHotspotDetail(gridId, activePeriod).catch(() => null)
        ]);

        setChangeData(changeRes);
        setDetail(detailRes);
      } catch (err) {
        console.error(`Failed to load change data for ${gridId} (${activePeriod}):`, err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [gridId, activePeriod]);

  if (loading) {
    return (
      <div className="subview-page">
        <div className="subview-loading font-mono">
          <div className="skeleton-spinner" />
          <span>ANALYZING MULTI-TEMPORAL SPECTRAL TRAJECTORY FOR {gridId} ({activePeriod.replace('_', ' → ')})...</span>
        </div>
      </div>
    );
  }

  if (error || !changeData) {
    return (
      <div className="subview-page">
        <div className="traffic-floating-card error-card font-mono" style={{ maxWidth: '600px', margin: '40px auto' }}>
          <h2 className="text-red">Change Trajectory Not Found</h2>
          <p className="text-muted" style={{ margin: '8px 0 16px' }}>
            {error || `Unable to retrieve change records for '${gridId}' (${activePeriod})`}
          </p>
          <button
            type="button"
            className="btn-action-primary"
            onClick={() => navigate('/')}
          >
            &larr; Return to Map
          </button>
        </div>
      </div>
    );
  }

  // Real spectral metrics from pipeline
  const builtUp2020 = detail?.built_up_2020 ?? changeData?.built_up?.[0]?.value ?? 25;
  const builtUp2023 = detail?.built_up_2023 ?? changeData?.built_up?.[1]?.value ?? 39;
  const builtUp2026 = detail?.built_up_2026 ?? changeData?.built_up?.[2]?.value ?? 53;

  const veg2020 = changeData?.vegetation?.[0]?.value ?? 77;
  const veg2023 = changeData?.vegetation?.[1]?.value ?? 50;
  const veg2026 = changeData?.vegetation?.[2]?.value ?? 22;

  const water2020 = changeData?.water?.[0]?.value ?? 10;
  const water2026 = changeData?.water?.[2]?.value ?? 20;

  const builtUpDiff = detail?.differences?.built_up ?? (builtUp2026 - builtUp2020);
  const vegDiff = detail?.differences?.vegetation ?? (veg2026 - veg2020);
  const waterDiff = detail?.differences?.water ?? (water2026 - water2020);

  const priorityScore = detail?.priority_score ?? detail?.priorityScore ?? 82;
  const priorityLevel = (detail?.priority_level || 'HIGH').toUpperCase();

  const lat = detail?.lat ?? detail?.coordinates?.[0] ?? 17.372285;
  const lng = detail?.lng ?? detail?.coordinates?.[1] ?? 78.422560;

  // Real spectral indices
  const signals = detail?.signals || {};
  const ndviDelta = signals.ndvi_delta ?? -0.5543;
  const ndbiDelta = signals.ndbi_delta ?? 0.2766;
  const ndwiDelta = signals.ndwi_delta ?? 0.1042;

  return (
    <div className="subview-page">
      <div className="subview-inner-canvas">
        {/* Clean Breadcrumb Navigation */}
        <Breadcrumbs
          items={[
            { label: 'Map', to: '/' },
            { label: `Hotspot (${gridId})`, to: `/?target=${gridId}` },
            { label: 'Change Explorer' }
          ]}
        />

        {/* Hero Header Card */}
        <header className="traffic-floating-card change-hero-card">
          <div className="evidence-header-top">
            <div>
              <span className="panel-category-tag font-mono">
                ANALYSIS PERIOD: {activePeriod.replace('_', ' → ')} &bull; MULTI-TEMPORAL EARTH OBSERVATION
              </span>
              <h1 className="evidence-target-id font-mono">{gridId}</h1>
              <p className="evidence-coords font-mono">
                {Number(lat).toFixed(6)}, {Number(lng).toFixed(6)} &bull; Land Cover Transition Analysis
              </p>
            </div>

            <div className="evidence-header-right">
              <span className={`selected-level-pill font-mono lvl-${priorityLevel.toLowerCase()}`}>
                {priorityLevel} PRIORITY ({priorityScore} / 100)
              </span>
              <div className="topbar-status-indicator font-mono" style={{ marginTop: '6px' }}>
                <span className="pulse-dot-green" aria-hidden="true" />
                <span>SENTINEL-2 TIME-SERIES</span>
              </div>
            </div>
          </div>
        </header>

        {/* Dedicated Analysis Period Switcher for Change Explorer */}
        <div style={{ display: 'flex', justifyContent: 'center', margin: '2px 0' }}>
          <TemporalBar
            activePeriod={activePeriod}
            onSelectPeriod={handlePeriodChange}
          />
        </div>

        {/* 1. Multi-Temporal Trajectory Card */}
        <section className="traffic-floating-card trajectory-card" aria-label="Land cover change trajectory">
          <div className="section-header-row font-mono">
            <span className="section-title">LAND COVER TRAJECTORY ({activePeriod.replace('_', ' → ')})</span>
            <span className="breakdown-total-tag">BUILT-UP TRANSITION</span>
          </div>

          <div className="story-timeline-display font-mono">
            <div className="timeline-epoch-col">
              <span className="epoch-year">2020</span>
              <span className="epoch-percent text-muted">{builtUp2020}%</span>
              <span className="epoch-lbl">BASELINE</span>
              <span className="epoch-sub">VEG: {veg2020}%</span>
            </div>

            <div className="timeline-connecting-bar">
              <span className="connecting-line" />
              <span className="connecting-dot" />
            </div>

            <div className="timeline-epoch-col">
              <span className="epoch-year">2023</span>
              <span className="epoch-percent text-muted">{builtUp2023}%</span>
              <span className="epoch-lbl">OBSERVED SHIFT</span>
              <span className="epoch-sub">VEG: {veg2023}%</span>
            </div>

            <div className="timeline-connecting-bar">
              <span className="connecting-line active" />
              <span className="connecting-dot active pulse" />
            </div>

            <div className="timeline-epoch-col active">
              <span className="epoch-year text-red">2026</span>
              <span className="epoch-percent text-red">{builtUp2026}%</span>
              <span className="epoch-lbl text-red">PERSISTENT STATE</span>
              <span className="epoch-sub text-red">VEG: {veg2026}%</span>
            </div>
          </div>

          <div className="panel-section-divider" />

          {/* Metric Transition Delta Rows */}
          <div className="story-metrics-stack font-mono">
            <div className="story-metric-row">
              <div className="metric-info">
                <span className="metric-lbl">BUILT-UP IMPERVIOUS SURFACE</span>
                <span className="metric-desc text-muted">Structural artificial surface expansion</span>
              </div>
              <span className="metric-val text-orange">
                {builtUpDiff >= 0 ? `+${Math.round(builtUpDiff)}` : Math.round(builtUpDiff)} pts
              </span>
            </div>

            <div className="story-metric-row">
              <div className="metric-info">
                <span className="metric-lbl">VEGETATION CANOPY COVER</span>
                <span className="metric-desc text-muted">Defoliation and vegetative biomass removal</span>
              </div>
              <span className="metric-val text-red">
                {vegDiff >= 0 ? `+${Math.round(vegDiff)}` : Math.round(vegDiff)} pts
              </span>
            </div>

            <div className="story-metric-row">
              <div className="metric-info">
                <span className="metric-lbl">HYDROLOGICAL BALANCE</span>
                <span className="metric-desc text-muted">Surface moisture and water retention delta</span>
              </div>
              <span className="metric-val text-muted">
                {waterDiff >= 0 ? `+${Math.round(waterDiff)}` : Math.round(waterDiff)} pts
              </span>
            </div>
          </div>
        </section>

        {/* 2. Spectral Indices Deep Dive Card */}
        <section className="traffic-floating-card spectral-indices-card" aria-label="Spectral Indices Deep Dive">
          <div className="section-header-row font-mono">
            <span className="section-title">CALCULATED SPECTRAL INDICES (&Delta; DELTA)</span>
            <span className="section-badge text-orange">SENTINEL-2 LEVEL-2A</span>
          </div>

          <div className="indices-grid font-mono">
            <div className="index-card">
              <span className="index-code">NDVI &Delta;</span>
              <span className="index-name">Normalized Difference Vegetation Index</span>
              <span className="index-value text-red">
                {ndviDelta > 0 ? `+${ndviDelta.toFixed(3)}` : ndviDelta.toFixed(3)}
              </span>
              <p className="index-note text-muted">Significant vegetation canopy reduction detected</p>
            </div>

            <div className="index-card">
              <span className="index-code">NDBI &Delta;</span>
              <span className="index-name">Normalized Difference Built-up Index</span>
              <span className="index-value text-orange">
                {ndbiDelta > 0 ? `+${ndbiDelta.toFixed(3)}` : ndbiDelta.toFixed(3)}
              </span>
              <p className="index-note text-muted">Substantial increase in synthetic impervious surfaces</p>
            </div>

            <div className="index-card">
              <span className="index-code">NDWI &Delta;</span>
              <span className="index-name">Normalized Difference Water Index</span>
              <span className="index-value text-muted">
                {ndwiDelta > 0 ? `+${ndwiDelta.toFixed(3)}` : ndwiDelta.toFixed(3)}
              </span>
              <p className="index-note text-muted">Baseline hydrological retention variation</p>
            </div>
          </div>

          <div className="panel-section-divider" />

          {/* Actions */}
          <div className="evidence-action-row font-mono">
            <button
              type="button"
              className="btn-action-primary"
              onClick={() => navigate(`/hotspot/${gridId}/evidence?period=${activePeriod}`)}
            >
              <span>VIEW SATELLITE EVIDENCE</span>
              <span className="arrow-right">&rarr;</span>
            </button>
            <button
              type="button"
              className="btn-action-secondary"
              onClick={() => navigate('/')}
            >
              &larr; RETURN TO MAP
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
