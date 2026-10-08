import React from 'react';

export default function CityOverviewBar({ overview }) {
  if (!overview) return null;

  return (
    <section className="summary-bar" aria-label="Monitored region metrics summary">
      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Monitored cells</span>
          <span className="badge badge-normal">Active grid</span>
        </div>
        <div className="stat-value">{overview.monitoredCellsCount?.toLocaleString() || '—'}</div>
        <div className="stat-subtext">Fixed 100m² multi-temporal cells</div>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Anomalous cells detected</span>
          <span className="badge badge-high">Statistical outliers</span>
        </div>
        <div className="stat-value">{overview.anomalousCellsCount || '—'}</div>
        <div className="stat-subtext">Deviating from historical/local baselines</div>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">High priority sites</span>
          <span className="badge badge-high">Immediate inspection</span>
        </div>
        <div className="stat-value">{overview.priorityCounts?.high || 0}</div>
        <div className="stat-subtext">Highest composite change urgency</div>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Medium priority sites</span>
          <span className="badge badge-medium">Secondary inspection</span>
        </div>
        <div className="stat-value">{overview.priorityCounts?.medium || 0}</div>
        <div className="stat-subtext">Noticeable localized divergence</div>
      </div>

      <div className="stat-card">
        <div className="stat-header">
          <span className="stat-label">Observation dates</span>
          <span className="badge badge-normal">Sentinel-2 MSI</span>
        </div>
        <div className="stat-value" style={{ fontSize: '15px', fontWeight: 600, marginTop: '4px' }}>
          {overview.baselinePeriod} → {overview.latestObservationDate}
        </div>
        <div className="stat-subtext">Multi-temporal cloud-screened epochs</div>
      </div>
    </section>
  );
}
