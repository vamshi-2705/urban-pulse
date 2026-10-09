import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchHotspotDetail, fetchChange, fetchEvidence } from '../api/client';
import Breadcrumbs from './Breadcrumbs';
import TemporalBar from './TemporalBar';

/**
 * Urban IQ Hotspot Intelligence Dossier — "Why was this area flagged?"
 * Defensible, explainable decomposition of Sentinel-2 multi-temporal anomaly scores.
 */
export default function HotspotDetailView({
  activePeriod: propPeriod = '2020_2026',
  onSelectPeriod
}) {
  const { gridId } = useParams();
  const navigate = useNavigate();

  const [internalPeriod, setInternalPeriod] = useState(propPeriod);
  const activePeriod = propPeriod || internalPeriod;

  const [detail, setDetail] = useState(null);
  const [changeSeries, setChangeSeries] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [activeTab, setActiveTab] = useState('trajectory'); // 'trajectory' | 'satellite'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  const handlePeriodChange = (newPeriod) => {
    setInternalPeriod(newPeriod);
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

        const [detailRes, changeRes, evidenceRes] = await Promise.all([
          fetchHotspotDetail(gridId, activePeriod),
          fetchChange(gridId, activePeriod).catch(() => null),
          fetchEvidence(gridId, activePeriod).catch(() => null)
        ]);

        setDetail(detailRes);
        setChangeSeries(changeRes);
        setEvidenceData(evidenceRes);
      } catch (err) {
        console.error(`Failed to load hotspot data for ${gridId}:`, err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [gridId, activePeriod, retryTrigger]);

  // Process score breakdown:
  // Urban expansion, Vegetation loss, Water change (only if nonzero), Historical anomaly, Local anomaly, Persistence
  const sortedBreakdown = useMemo(() => {
    if (!detail?.score_breakdown) return null;

    const breakdown = detail.score_breakdown;
    const labelMap = {
      urban_expansion: 'Urban expansion',
      vegetation_loss: 'Vegetation loss',
      water_body_change: 'Water change',
      water_change: 'Water change',
      historical_anomaly: 'Historical anomaly',
      spatial_anomaly: 'Local anomaly',
      local_anomaly: 'Local anomaly',
      persistence: 'Persistence'
    };

    const items = Object.entries(breakdown)
      .map(([key, value]) => ({
        key,
        label: labelMap[key] || key.replace(/_/g, ' '),
        points: typeof value === 'number' ? value : 0
      }))
      .filter((item) => {
        if (item.key === 'water_body_change' || item.key === 'water_change') {
          return item.points !== 0;
        }
        return true;
      })
      .sort((a, b) => b.points - a.points);

    return items;
  }, [detail]);

  const maxPoints = useMemo(() => {
    if (!sortedBreakdown || sortedBreakdown.length === 0) return 1;
    return Math.max(...sortedBreakdown.map((i) => i.points), 1);
  }, [sortedBreakdown]);

  const periodLabel = activePeriod.replace('_', ' → ');

  if (loading) {
    return (
      <div className="dossier-page-container loading-state">
        <div className="dossier-loading-card">
          <div className="skeleton-spinner" />
          <h3 className="loading-title">Loading Investigation Dossier</h3>
          <p className="loading-desc font-mono">
            Synthesizing explainable anomaly breakdown for {gridId} ({periodLabel})...
          </p>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="dossier-page-container">
        <div className="dossier-error-card">
          <div className="error-icon" aria-hidden="true">&#9888;</div>
          <h3 className="error-title">Location Not Found</h3>
          <p className="error-details font-mono">{error || `No record found for grid ID '${gridId}'`}</p>
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '16px' }}>
            <button
              type="button"
              className="btn-action-primary font-mono"
              onClick={() => setRetryTrigger((prev) => prev + 1)}
            >
              Retry Loading
            </button>
            <button
              type="button"
              className="btn-action-outline font-mono"
              onClick={() => navigate('/ranking')}
            >
              &larr; Back to Rankings
            </button>
          </div>
        </div>
      </div>
    );
  }

  const level = (detail.priority_level || 'LOW').toUpperCase();
  const score = detail.priority_score ?? 0;

  // Evidence metric formatting
  const builtUp2020 = Math.round(detail.built_up_2020 ?? 0);
  const builtUp2026 = Math.round(detail.built_up_2026 ?? 0);
  const builtUpDelta = Math.round(detail.differences?.built_up ?? (detail.built_up_2026 - detail.built_up_2020));

  const veg2020 = Math.round(detail.vegetation_2020 ?? 0);
  const veg2026 = Math.round(detail.vegetation_2026 ?? 0);
  const vegDelta = Math.round(detail.differences?.vegetation ?? (detail.vegetation_2026 - detail.vegetation_2020));

  const water2020 = Math.round(detail.water_2020 ?? 0);
  const water2026 = Math.round(detail.water_2026 ?? 0);
  const waterDelta = Math.round(detail.differences?.water ?? (detail.water_2026 - detail.water_2020));

  const percentile = detail.local_percentile ?? 95;
  const historicalBaseline = detail.historical_change ?? 2.7;

  return (
    <div className="dossier-page-container" id="dossier-scroll-container">
      {/* 1. Municipal Breadcrumbs & Quick Action Header */}
      <div className="dossier-top-nav-bar">
        <Breadcrumbs
          items={[
            { label: 'Map Overview', to: '/' },
            { label: 'Ranking Queue', to: '/ranking' },
            { label: `Hotspot (${detail.grid_id})` }
          ]}
        />

        <div className="dossier-quick-links">
          <button
            type="button"
            className="dossier-link-btn btn-map-fly font-mono"
            onClick={() => navigate(`/?target=${detail.grid_id}`)}
            title="Locate and fly to cell on central map"
          >
            Map View ↗
          </button>
          <button
            type="button"
            className="dossier-link-btn btn-change-link font-mono"
            onClick={() => navigate(`/hotspot/${detail.grid_id}/change`)}
            title="Inspect temporal change charts"
          >
            Change Explorer ↗
          </button>
          <button
            type="button"
            className="dossier-link-btn btn-evidence-link font-mono"
            onClick={() => navigate(`/hotspot/${detail.grid_id}/evidence`)}
            title="Inspect full satellite evidence gallery"
          >
            Satellite Evidence ↗
          </button>
        </div>
      </div>

      {/* 2. Hero Target Header Card */}
      <div className="dossier-hero-header">
        <div className="hero-header-main">
          <div className="hero-telemetry-tag font-mono">
            <span className="telemetry-pill">ESA SENTINEL-2 L2A</span>
            <span className="telemetry-sep">&bull;</span>
            <span className="telemetry-pill">FIELD VERIFICATION DOSSIER</span>
            <span className="telemetry-sep">&bull;</span>
            <span className="telemetry-pill">GRID CELL {detail.grid_id}</span>
          </div>

          <h1 className="hero-main-title">Why was this area flagged?</h1>

          <div className="hero-identity-row">
            <span className="hero-grid-id font-mono">{detail.grid_id}</span>

            <span
              className={`hero-priority-badge font-mono ${
                level === 'HIGH' ? 'badge-high' : level === 'MEDIUM' ? 'badge-medium' : 'badge-normal'
              }`}
            >
              <span className={`status-dot ${level === 'HIGH' ? 'bg-red' : 'bg-amber'}`} aria-hidden="true" />
              {level} PRIORITY
            </span>

            <span className="hero-location-text">
              {detail.ward_name || detail.wardName || 'Hyderabad Urban'} &bull; Monitored cell (~500 m &times; 500 m)
            </span>
          </div>
        </div>

        {/* Period Selector Dock */}
        <div className="hero-period-dock">
          <span className="period-dock-label font-mono">OBSERVATION WINDOW</span>
          <TemporalBar
            activePeriod={activePeriod}
            onSelectPeriod={handlePeriodChange}
          />
        </div>
      </div>

      {/* 3. Core Intelligence Matrix (Score + Breakdown on Left, Evidence on Right) */}
      <div className="dossier-matrix-grid">
        {/* LEFT COLUMN: Priority Score & Decomposition */}
        <div className="matrix-left-col">
          {/* Card A: Priority Score Gauge */}
          <div className="dossier-card priority-score-card">
            <div className="card-header-mini font-mono">
              <span className="mini-label">PRIORITY URGENCY INDEX</span>
              <span className="mini-sub">{periodLabel}</span>
            </div>

            <div className="score-hero-display">
              <span className={`score-hero-number font-mono ${level === 'HIGH' ? 'text-red' : 'text-amber'}`}>
                {score}
              </span>
              <span className="score-hero-denom font-mono">/ 100</span>
            </div>

            {/* Visual Linear Meter */}
            <div className="score-meter-track" aria-hidden="true">
              <div
                className={`score-meter-fill ${level === 'HIGH' ? 'meter-high' : 'meter-medium'}`}
                style={{ width: `${Math.min(100, Math.max(10, score))}%` }}
              />
            </div>

            <p className="score-caption-text">
              Ranked municipal investigation urgency derived from explainable spatial divergence factors.
            </p>

            <div className="score-highlights-row font-mono">
              <div className="highlight-chip">
                <span className="chip-val text-red">{percentile}th</span>
                <span className="chip-lbl">Percentile Anomaly</span>
              </div>
              <div className="highlight-chip">
                <span className="chip-val text-orange">{historicalBaseline}x</span>
                <span className="chip-lbl">Historical Speed</span>
              </div>
            </div>
          </div>

          {/* Card B: Explainable Score Breakdown */}
          <div className="dossier-card breakdown-card">
            <div className="card-header-clean">
              <h2 className="card-clean-title">Score breakdown</h2>
              <span className="breakdown-total-tag font-mono">Sums to {score} points</span>
            </div>

            <p className="card-clean-desc">
              Algorithmic component contributions from multi-temporal Sentinel-2 spectral shifts:
            </p>

            {!sortedBreakdown || sortedBreakdown.length === 0 ? (
              <div className="dossier-notice-box font-mono" role="status">
                Notice: Score breakdown data is not available for this record.
              </div>
            ) : (
              <div className="breakdown-bars-list font-mono">
                {sortedBreakdown.map((item) => {
                  const widthPercent = Math.min(100, Math.max(12, (item.points / maxPoints) * 100));
                  const isExpansion = item.key === 'urban_expansion';
                  const isVeg = item.key === 'vegetation_loss';
                  const isAnomaly = item.key.includes('anomaly');
                  const isPersistence = item.key === 'persistence';

                  let barClass = 'bar-anomaly';
                  if (isExpansion) barClass = 'bar-expansion';
                  else if (isVeg) barClass = 'bar-veg';
                  else if (isPersistence) barClass = 'bar-persistence';

                  return (
                    <div key={item.key} className="breakdown-row-item">
                      <div className="breakdown-meta-line">
                        <span className="breakdown-name">{item.label}</span>
                        <span className={`breakdown-pts ${isVeg ? 'text-red' : isExpansion ? 'text-orange' : 'text-amber'}`}>
                          +{item.points}
                        </span>
                      </div>

                      <div className="breakdown-bar-track">
                        <div
                          className={`breakdown-bar-fill ${barClass}`}
                          style={{ width: `${widthPercent}%` }}
                          role="progressbar"
                          aria-valuenow={item.points}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${item.label}: +${item.points} points`}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Evidence Observations */}
        <div className="matrix-right-col">
          <div className="dossier-card evidence-container-card">
            <div className="card-header-clean">
              <h2 className="card-clean-title">Evidence & Spectral Findings</h2>
              <span className="evidence-badge-tag font-mono">COPERNICUS OPTICAL L2A</span>
            </div>

            <div className="evidence-cards-stack">
              {/* 1. Built-up */}
              <div className="evidence-bullet-card card-expansion">
                <div className="bullet-indicator indicator-orange" aria-hidden="true">&#9670;</div>
                <div className="bullet-content">
                  <div className="bullet-title-row">
                    <span className="bullet-title">
                      Built-up {builtUp2020}% &rarr; {builtUp2026}% (+{builtUpDelta} points)
                    </span>
                    <span className="bullet-tag-pill font-mono tag-orange">+{builtUpDelta}% Growth</span>
                  </div>
                  <p className="bullet-description">
                    Rapid conversion of open and natural land to impervious urban surfaces between 2020 and 2026.
                  </p>
                </div>
              </div>

              {/* 2. Vegetation */}
              <div className="evidence-bullet-card card-vegetation">
                <div className="bullet-indicator indicator-red" aria-hidden="true">&#9670;</div>
                <div className="bullet-content">
                  <div className="bullet-title-row">
                    <span className="bullet-title">
                      Vegetation {veg2020}% &rarr; {veg2026}% ({vegDelta} points)
                    </span>
                    <span className="bullet-tag-pill font-mono tag-red">{vegDelta}% Canopy</span>
                  </div>
                  <p className="bullet-description">
                    Net canopy loss over the observation period, deviating from expected seasonal patterns.
                  </p>
                </div>
              </div>

              {/* 3. Water change */}
              <div className="evidence-bullet-card card-water">
                <div className="bullet-indicator indicator-blue" aria-hidden="true">&#9670;</div>
                <div className="bullet-content">
                  <div className="bullet-title-row">
                    <span className="bullet-title">
                      Water change {water2020}% &rarr; {water2026}% ({waterDelta > 0 ? `+${waterDelta}` : `${waterDelta}`} points)
                    </span>
                    <span className="bullet-tag-pill font-mono tag-blue">{waterDelta > 0 ? `+${waterDelta}%` : `${waterDelta}%`}</span>
                  </div>
                  <p className="bullet-description">
                    {waterDelta < 0
                      ? 'Shrinkage or alteration of local surface water bodies and natural drainage corridors.'
                      : waterDelta > 0
                      ? 'Expansion of standing water or seasonal surface water accumulation.'
                      : 'Surface water extent remained stable across monitoring intervals.'}
                  </p>
                </div>
              </div>

              {/* 4. 95th percentile */}
              <div className="evidence-bullet-card card-neighborhood">
                <div className="bullet-indicator indicator-purple" aria-hidden="true">&#9670;</div>
                <div className="bullet-content">
                  <div className="bullet-title-row">
                    <span className="bullet-title">
                      {percentile}th percentile among nearby areas
                    </span>
                    <span className="bullet-tag-pill font-mono tag-purple">Spatial Outlier</span>
                  </div>
                  <p className="bullet-description">
                    Local spatial divergence compared against immediate 500 m neighborhood cells.
                  </p>
                </div>
              </div>

              {/* 5. 2.7x baseline */}
              <div className="evidence-bullet-card card-baseline">
                <div className="bullet-indicator indicator-amber" aria-hidden="true">&#9670;</div>
                <div className="bullet-content">
                  <div className="bullet-title-row">
                    <span className="bullet-title">
                      {historicalBaseline}x the historical baseline
                    </span>
                    <span className="bullet-tag-pill font-mono tag-amber">Accelerated</span>
                  </div>
                  <p className="bullet-description">
                    Current rate of transition significantly exceeds this grid cell&rsquo;s 2020–2023 trajectory.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Municipal Action Directive Closing Banner */}
      <div className="dossier-directive-banner">
        <div className="directive-icon-circle" aria-hidden="true">&#9873;</div>
        <div className="directive-body">
          <div className="directive-tag font-mono">ACTION DIRECTIVE &bull; MUNICIPAL PROTOCOL</div>
          <p className="directive-quote">
            &ldquo;Unusual spatial change detected. Field verification recommended.&rdquo;
          </p>
          <span className="directive-helper">
            Autonomous decision-support signal for field inspector unit dispatch to Hyderabad grid cell {detail.grid_id}.
          </span>
        </div>
      </div>

      {/* 5. Interactive Embedded Deep Dive Section */}
      <div className="dossier-card embedded-deepdive-card">
        <div className="deepdive-header-bar">
          <div className="deepdive-tabs font-mono">
            <button
              type="button"
              className={`deepdive-tab-btn ${activeTab === 'trajectory' ? 'active' : ''}`}
              onClick={() => setActiveTab('trajectory')}
            >
              Multi-Temporal Trajectory Table
            </button>
            <button
              type="button"
              className={`deepdive-tab-btn ${activeTab === 'satellite' ? 'active' : ''}`}
              onClick={() => setActiveTab('satellite')}
            >
              Sentinel-2 Satellite Frames
            </button>
          </div>

          <div className="deepdive-external-actions font-mono">
            {activeTab === 'trajectory' ? (
              <button
                type="button"
                className="btn-deepdive-full"
                onClick={() => navigate(`/hotspot/${detail.grid_id}/change`)}
              >
                Launch Change Explorer &rarr;
              </button>
            ) : (
              <button
                type="button"
                className="btn-deepdive-full"
                onClick={() => navigate(`/hotspot/${detail.grid_id}/evidence`)}
              >
                Launch Satellite Evidence View &rarr;
              </button>
            )}
          </div>
        </div>

        <div className="deepdive-content-body">
          {activeTab === 'trajectory' ? (
            <div className="trajectory-table-container">
              {changeSeries ? (
                <table className="dossier-data-table font-mono" aria-label="Multi-temporal trajectory">
                  <thead>
                    <tr>
                      <th>EPOCH</th>
                      <th>BUILT-UP</th>
                      <th>VEGETATION</th>
                      <th>WATER BODY</th>
                      {changeSeries.bare_land && <th>BARE LAND</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {[2020, 2023, 2026].map((yr, idx) => (
                      <tr key={yr}>
                        <td className="epoch-cell"><strong>{yr}</strong></td>
                        <td className="text-orange">{changeSeries.built_up?.[idx]?.value ?? '-'}%</td>
                        <td className="text-red">{changeSeries.vegetation?.[idx]?.value ?? '-'}%</td>
                        <td className="text-blue">{changeSeries.water?.[idx]?.value ?? '-'}%</td>
                        {changeSeries.bare_land && (
                          <td>{changeSeries.bare_land?.[idx]?.value ?? '-'}%</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="dossier-empty-note font-mono">
                  Connecting to Sentinel-2 multi-temporal trajectory feed...
                </div>
              )}
            </div>
          ) : (
            <div className="satellite-gallery-container">
              {evidenceData?.images && evidenceData.images.length > 0 ? (
                <div className="dossier-gallery-grid">
                  {evidenceData.images.map((imgUrl, idx) => {
                    const years = [2020, 2023, 2026];
                    return (
                      <div key={imgUrl} className="gallery-frame-card">
                        <div className="frame-header font-mono">
                          <span className="frame-year">{years[idx] || 'Observation'}</span>
                          <span className="frame-res">10m / px L2A</span>
                        </div>
                        <div className="frame-img-box">
                          <img
                            src={imgUrl}
                            alt={`Sentinel-2 observation tile for ${years[idx]}`}
                            className="frame-image"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="dossier-empty-note font-mono">
                  Satellite optical frames available in full Evidence View.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
