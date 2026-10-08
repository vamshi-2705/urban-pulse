import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { fetchHotspotDetail, fetchChange, fetchEvidence } from '../api/client';

export default function HotspotDetailView() {
  const { gridId } = useParams();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [changeSeries, setChangeSeries] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadDetail() {
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
        console.error(`Failed to load details for ${gridId}:`, err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadDetail();
  }, [gridId]);

  if (loading) {
    return (
      <div className="detail-view-container loading-state">
        <div className="skeleton-spinner" />
        <p>Loading observation dossier for {gridId}...</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="detail-view-container error-state">
        <div className="error-card">
          <h2>Location Not Found</h2>
          <p>{error || `No record found for grid ID '${gridId}'`}</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/')}>
            &larr; Return to Overview
          </button>
        </div>
      </div>
    );
  }

  const level = (detail.priority_level || 'LOW').toUpperCase();
  const score = detail.priority_score ?? 0;
  const breakdown = detail.score_breakdown || {};
  const reasons = detail.reasons || [];
  const differences = detail.differences || {};
  const images = evidenceData?.images || [];

  return (
    <div className="detail-view-container" style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Top Navigation Breadcrumb */}
      <div className="detail-top-nav">
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/')}>
          &larr; Back to Overview
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => navigate('/ranking')}>
          View Hotspot Ranking
        </button>
      </div>

      {/* Hero Header Card */}
      <section className="detail-hero-card">
        <div className="detail-hero-main">
          <div className="detail-hero-titles">
            <div className="detail-grid-title-row">
              <h2 className="detail-grid-id">{detail.grid_id}</h2>
              <span className={`badge ${level === 'HIGH' ? 'badge-high' : level === 'MEDIUM' ? 'badge-medium' : 'badge-normal'}`}>
                {level} PRIORITY
              </span>
            </div>
            <p className="detail-subtext">
              Ward / Zone: {detail.ward_name || detail.wardName || 'Hyderabad Urban'} &bull; Lat: {detail.lat}, Lng: {detail.lng}
            </p>
          </div>

          <div className="detail-score-box">
            <span className="detail-score-label">Priority Score</span>
            <span className="detail-score-value">{score}</span>
            <span className="detail-score-max">/ 100</span>
          </div>
        </div>

        {/* Standard Defensible Mandate Notice */}
        <div className="detail-mandate-banner">
          <span className="mandate-tag">RECOMMENDATION</span>
          <span className="mandate-text">
            &ldquo;Unusual spatial change detected. Field verification recommended.&rdquo;
          </span>
        </div>
      </section>

      <div className="detail-grid-layout">
        {/* Left Column: 2020->2026 Metric Differences & Time Series */}
        <div className="detail-column-left">
          {/* Subtraction Metric Differences */}
          <section className="detail-section-card">
            <h3 className="section-title">2020 &rarr; 2026 Land Cover Net Change</h3>
            <p className="section-subtitle">
              Calculated via simple subtraction across monitoring cycles.
            </p>

            <div className="metrics-diff-grid">
              <div className="metric-diff-card">
                <span className="metric-diff-name">Built-up Surface</span>
                <span className={`metric-diff-val ${differences.built_up > 0 ? 'text-red' : 'text-green'}`}>
                  {differences.built_up > 0 ? `+${differences.built_up}%` : `${differences.built_up}%`}
                </span>
                <span className="metric-diff-sub">
                  {detail.built_up_2020}% &rarr; {detail.built_up_2026}%
                </span>
              </div>

              <div className="metric-diff-card">
                <span className="metric-diff-name">Vegetation Canopy</span>
                <span className={`metric-diff-val ${differences.vegetation < 0 ? 'text-amber' : 'text-green'}`}>
                  {differences.vegetation > 0 ? `+${differences.vegetation}%` : `${differences.vegetation}%`}
                </span>
                <span className="metric-diff-sub">
                  {detail.vegetation_2020}% &rarr; {detail.vegetation_2026}%
                </span>
              </div>

              <div className="metric-diff-card">
                <span className="metric-diff-name">Water Bodies</span>
                <span className="metric-diff-val text-muted">
                  {differences.water > 0 ? `+${differences.water}%` : `${differences.water}%`}
                </span>
                <span className="metric-diff-sub">
                  {detail.water_2020}% &rarr; {detail.water_2026}%
                </span>
              </div>

              {differences.bare_land !== undefined && (
                <div className="metric-diff-card">
                  <span className="metric-diff-name">Bare / Open Land</span>
                  <span className="metric-diff-val text-muted">
                    {differences.bare_land > 0 ? `+${differences.bare_land}%` : `${differences.bare_land}%`}
                  </span>
                  <span className="metric-diff-sub">
                    {detail.bare_land_2020}% &rarr; {detail.bare_land_2026}%
                  </span>
                </div>
              )}
            </div>
          </section>

          {/* Time Series Table */}
          {changeSeries && (
            <section className="detail-section-card">
              <h3 className="section-title">Multi-Year Observation Series</h3>
              <table className="series-table">
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
                      <td style={{ fontWeight: 600 }}>{yr}</td>
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
            </section>
          )}

          {/* Satellite Placeholder Imagery */}
          {images.length > 0 && (
            <section className="detail-section-card">
              <h3 className="section-title">Multi-Temporal Placeholder Imagery</h3>
              <p className="section-subtitle">
                Synthetic development verification tiles (Sentinel-2 baseline).
              </p>
              <div className="imagery-gallery">
                {images.map((imgUrl, idx) => {
                  const years = [2020, 2023, 2026];
                  return (
                    <div key={imgUrl} className="imagery-card">
                      <span className="imagery-year-badge">{years[idx] || 'Epoch'}</span>
                      <img src={imgUrl} alt={`Satellite observation ${years[idx]}`} className="imagery-thumb" />
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </div>

        {/* Right Column: Score Breakdown & Explainable Factors */}
        <div className="detail-column-right">
          {/* Flagging Reasons */}
          <section className="detail-section-card">
            <h3 className="section-title">Flagging Reasons</h3>
            <ul className="reasons-list">
              {reasons.map((r, i) => (
                <li key={i} className="reason-item">
                  <span className="reason-bullet">&bull;</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Additive Score Breakdown */}
          <section className="detail-section-card">
            <h3 className="section-title">Explainable Score Breakdown</h3>
            <p className="section-subtitle">
              Sum of additive factors strictly equals priority score ({score}).
            </p>
            <div className="breakdown-list">
              {Object.entries(breakdown).map(([factor, pts]) => (
                <div key={factor} className="breakdown-row">
                  <span className="factor-name">{factor.replace(/_/g, ' ')}</span>
                  <span className="factor-points">+{pts} pts</span>
                </div>
              ))}
              <div className="breakdown-total-row">
                <strong>Total Priority Score</strong>
                <strong>{score} pts</strong>
              </div>
            </div>
          </section>

          {/* Provenance Audit Information */}
          <section className="detail-section-card">
            <h3 className="section-title">Provenance & Audit Trail</h3>
            <div className="audit-specs">
              <div className="audit-row">
                <span>Persistence score:</span>
                <strong>{detail.persistence ?? 'N/A'}</strong>
              </div>
              <div className="audit-row">
                <span>Temporal anomaly:</span>
                <strong>{detail.temporal_anomaly ?? 'N/A'}</strong>
              </div>
              <div className="audit-row">
                <span>Spatial anomaly:</span>
                <strong>{detail.spatial_anomaly ?? 'N/A'}</strong>
              </div>
              <div className="audit-row">
                <span>Neighborhood percentile:</span>
                <strong>{detail.local_percentile ? `${detail.local_percentile}th` : 'N/A'}</strong>
              </div>
              <div className="audit-row">
                <span>Historical deviation:</span>
                <strong>{detail.historical_change ? `+${detail.historical_change}x` : 'N/A'}</strong>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
