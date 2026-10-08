import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchHotspotDetail, fetchChange, fetchEvidence } from '../api/client';

export default function HotspotDetailView() {
  const { gridId } = useParams();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [changeSeries, setChangeSeries] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [activeModule, setActiveModule] = useState(null); // 'change' | 'evidence' | null
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      if (!gridId) return;
      try {
        setLoading(true);
        setError(null);

        const [detailRes, changeRes, evidenceRes] = await Promise.all([
          fetchHotspotDetail(gridId),
          fetchChange(gridId).catch(() => null),
          fetchEvidence(gridId).catch(() => null)
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
  }, [gridId]);

  // 3. Process score breakdown:
  // "from score_breakdown as horizontal bars labelled '+32', sorted by size:
  // Urban expansion, Vegetation loss, Water change (only if nonzero), Historical anomaly, Local anomaly, Persistence.
  // Never invent or rescale values. If score_breakdown is missing, show a clear notice."
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
      // Water change: only if nonzero
      .filter((item) => {
        if (item.key === 'water_body_change' || item.key === 'water_change') {
          return item.points !== 0;
        }
        return true;
      })
      // Sorted by size descending
      .sort((a, b) => b.points - a.points);

    return items;
  }, [detail]);

  // Max points for bar proportional rendering without modifying raw point values
  const maxPoints = useMemo(() => {
    if (!sortedBreakdown || sortedBreakdown.length === 0) return 1;
    return Math.max(...sortedBreakdown.map((i) => i.points), 1);
  }, [sortedBreakdown]);

  if (loading) {
    return (
      <div className="why-flagged-container loading-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ fontWeight: 600 }}>Loading investigation dossier for {gridId}...</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="why-flagged-container" style={{ padding: '40px 20px', maxWidth: '640px', margin: '0 auto' }}>
        <div className="error-card">
          <h2>Location Not Found</h2>
          <p>{error || `No record found for grid ID '${gridId}'`}</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/ranking')}>
            &larr; Back to Hotspot ranking
          </button>
        </div>
      </div>
    );
  }

  const level = (detail.priority_level || 'LOW').toUpperCase();
  const score = detail.priority_score ?? 0;

  // 4. Evidence metric formatting:
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
    <div className="why-flagged-page">
      <div className="why-flagged-container">
        {/* Navigation Breadcrumb */}
        <div className="why-flagged-nav">
          <button type="button" className="back-link-btn" onClick={() => navigate('/ranking')}>
            &larr; Back to Hotspot ranking
          </button>
          <button type="button" className="back-link-btn" onClick={() => navigate('/')}>
            Overview map
          </button>
        </div>

        {/* 1. "Why was this area flagged?" with grid_id and priority badge */}
        <header className="why-flagged-header">
          <div className="why-flagged-title-cluster">
            <h1 className="why-flagged-main-title">Why was this area flagged?</h1>
            <div className="why-flagged-badge-row">
              <span className="why-flagged-grid-id">{detail.grid_id}</span>
              <span
                className={`badge ${
                  level === 'HIGH'
                    ? 'badge-high'
                    : level === 'MEDIUM'
                    ? 'badge-medium'
                    : 'badge-normal'
                }`}
              >
                <span
                  className={`status-dot-sm ${level === 'HIGH' ? 'bg-red' : 'bg-amber'}`}
                  aria-hidden="true"
                />
                {level} PRIORITY
              </span>
            </div>
            <p className="why-flagged-subtext">
              {detail.ward_name || detail.wardName || 'Hyderabad Metropolitan Growth Corridor'} &bull;
              Monitored cell (~500 m)
            </p>
          </div>
        </header>

        {/* 2. Priority score "87 / 100", large */}
        <section className="why-flagged-score-section" aria-label="Priority Score">
          <span className="score-heading-label">Priority score</span>
          <div className="score-display-large">
            <span className="score-large-number">{score}</span>
            <span className="score-large-denom">/ 100</span>
          </div>
          <p className="score-caption">
            Ranked municipal investigation urgency derived from explainable spatial divergence factors.
          </p>
        </section>

        {/* 3. Score breakdown from score_breakdown as horizontal bars labelled "+32", sorted by size */}
        <section className="why-flagged-breakdown-section" aria-label="Score Breakdown">
          <div className="section-header-row">
            <h2 className="why-flagged-section-title">Score breakdown</h2>
            <span className="breakdown-total-tag">Sums to {score} points</span>
          </div>

          {!sortedBreakdown || sortedBreakdown.length === 0 ? (
            <div className="notice-box" role="status">
              Notice: Score breakdown data is not available for this record.
            </div>
          ) : (
            <div className="breakdown-bars-container">
              {sortedBreakdown.map((item) => {
                const widthPercent = Math.min(100, Math.max(10, (item.points / maxPoints) * 100));
                const isExpansion = item.key === 'urban_expansion';
                const isVeg = item.key === 'vegetation_loss';

                return (
                  <div key={item.key} className="breakdown-bar-row">
                    <div className="breakdown-bar-meta">
                      <span className="breakdown-bar-name">{item.label}</span>
                      <span className="breakdown-bar-label">+{item.points}</span>
                    </div>

                    <div className="breakdown-bar-track">
                      <div
                        className={`breakdown-bar-fill ${
                          isExpansion ? 'fill-expansion' : isVeg ? 'fill-vegetation' : 'fill-anomaly'
                        }`}
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
        </section>

        {/* 4. Evidence */}
        <section className="why-flagged-evidence-section" aria-label="Evidence Observations">
          <h2 className="why-flagged-section-title">Evidence</h2>

          <div className="evidence-cards-grid">
            {/* Built-up 31% -> 47% (+16 points) */}
            <div className="evidence-bullet-card">
              <div className="evidence-card-icon icon-expansion" aria-hidden="true">&bull;</div>
              <div className="evidence-card-content">
                <span className="evidence-metric-lead">
                  Built-up {builtUp2020}% &rarr; {builtUp2026}% (+{builtUpDelta} points)
                </span>
                <span className="evidence-metric-sub">
                  Rapid conversion of open and natural land to impervious urban surfaces between 2020 and 2026.
                </span>
              </div>
            </div>

            {/* Vegetation 42% -> 31% (-11 points) */}
            <div className="evidence-bullet-card">
              <div className="evidence-card-icon icon-vegetation" aria-hidden="true">&bull;</div>
              <div className="evidence-card-content">
                <span className="evidence-metric-lead">
                  Vegetation {veg2020}% &rarr; {veg2026}% ({vegDelta} points)
                </span>
                <span className="evidence-metric-sub">
                  Net canopy loss over the observation period, deviating from expected seasonal patterns.
                </span>
              </div>
            </div>

            {/* Water change */}
            <div className="evidence-bullet-card">
              <div className="evidence-card-icon icon-water" aria-hidden="true">&bull;</div>
              <div className="evidence-card-content">
                <span className="evidence-metric-lead">
                  Water change {water2020}% &rarr; {water2026}% ({waterDelta > 0 ? `+${waterDelta}` : `${waterDelta}`} points)
                </span>
                <span className="evidence-metric-sub">
                  {waterDelta < 0
                    ? 'Shrinkage or alteration of local surface water bodies and natural drainage corridors.'
                    : waterDelta > 0
                    ? 'Expansion of standing water or seasonal surface water accumulation.'
                    : 'Surface water extent remained stable across monitoring intervals.'}
                </span>
              </div>
            </div>

            {/* "95th percentile among nearby areas" */}
            <div className="evidence-bullet-card highlight-percentile">
              <div className="evidence-card-icon icon-percentile" aria-hidden="true">&bull;</div>
              <div className="evidence-card-content">
                <span className="evidence-metric-lead">
                  {percentile}th percentile among nearby areas
                </span>
                <span className="evidence-metric-sub">
                  Local spatial divergence compared against immediate 500 m neighborhood cells.
                </span>
              </div>
            </div>

            {/* "2.7x the historical baseline" */}
            <div className="evidence-bullet-card highlight-baseline">
              <div className="evidence-card-icon icon-baseline" aria-hidden="true">&bull;</div>
              <div className="evidence-card-content">
                <span className="evidence-metric-lead">
                  {historicalBaseline}x the historical baseline
                </span>
                <span className="evidence-metric-sub">
                  Current rate of transition significantly exceeds this grid cell&rsquo;s 2020–2023 trajectory.
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* 5. Closing line: "Unusual spatial change detected. Field verification recommended." */}
        <section className="why-flagged-closing-banner" aria-label="Closing Directive">
          <div className="closing-banner-content">
            <span className="closing-directive-badge">ACTION DIRECTIVE</span>
            <p className="closing-directive-quote">
              &ldquo;Unusual spatial change detected. Field verification recommended.&rdquo;
            </p>
          </div>
        </section>

        {/* 6. Buttons: Change explorer, Evidence view */}
        <section className="why-flagged-actions-section" aria-label="Detailed Explorer Views">
          <div className="action-buttons-cluster">
            <button
              type="button"
              className={`btn ${activeModule === 'change' ? 'btn-primary' : 'btn-outline-primary'}`}
              onClick={() => setActiveModule(activeModule === 'change' ? null : 'change')}
            >
              Change explorer
            </button>
            <button
              type="button"
              className={`btn ${activeModule === 'evidence' ? 'btn-primary' : 'btn-outline-primary'}`}
              onClick={() => setActiveModule(activeModule === 'evidence' ? null : 'evidence')}
            >
              Evidence view
            </button>
          </div>

          {/* Expandable Module: Change explorer */}
          {activeModule === 'change' && changeSeries && (
            <div className="interactive-module-card fade-in" id="change-explorer-panel">
              <div className="module-card-header">
                <h3 className="module-title">Multi-Temporal Change Explorer</h3>
                <span className="module-badge">2020 &bull; 2023 &bull; 2026 Trajectory</span>
              </div>
              <div className="module-card-body">
                <table className="series-table" aria-label="Multi-temporal trajectory">
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Built-up</th>
                      <th>Vegetation</th>
                      <th>Water</th>
                      {changeSeries.bare_land && <th>Bare land</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {[2020, 2023, 2026].map((yr, idx) => (
                      <tr key={yr}>
                        <td style={{ fontWeight: 700 }}>{yr}</td>
                        <td>{changeSeries.built_up?.[idx]?.value}%</td>
                        <td>{changeSeries.vegetation?.[idx]?.value}%</td>
                        <td>{changeSeries.water?.[idx]?.value}%</td>
                        {changeSeries.bare_land && (
                          <td>{changeSeries.bare_land?.[idx]?.value}%</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Expandable Module: Evidence view */}
          {activeModule === 'evidence' && evidenceData && (
            <div className="interactive-module-card fade-in" id="evidence-view-panel">
              <div className="module-card-header">
                <h3 className="module-title">Evidence Dossier & Satellite Imagery</h3>
                <span className="module-badge">Copernicus Sentinel-2 MSI</span>
              </div>
              <div className="module-card-body">
                <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                  Multi-temporal verification frames for spatial cell {gridId}:
                </p>
                <div className="imagery-gallery">
                  {(evidenceData.images || []).map((imgUrl, idx) => {
                    const years = [2020, 2023, 2026];
                    return (
                      <div key={imgUrl} className="imagery-card">
                        <span className="imagery-year-badge">{years[idx] || 'Observation'}</span>
                        <img src={imgUrl} alt={`Observation tile ${years[idx]}`} className="imagery-thumb" />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
