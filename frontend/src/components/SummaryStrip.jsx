import React from 'react';

export default function SummaryStrip({ statistics, loading, error }) {
  if (loading) {
    return (
      <div className="summary-strip-container">
        <div className="summary-strip skeleton">
          <div className="summary-card-skeleton" />
          <div className="summary-card-skeleton" />
          <div className="summary-card-skeleton" />
          <div className="summary-card-skeleton" />
        </div>
      </div>
    );
  }

  if (error || !statistics) {
    return (
      <div className="summary-strip-container">
        <div className="summary-strip error">
          <span>Failed to load regional statistics: {error || 'No data'}</span>
        </div>
      </div>
    );
  }

  const analyzed = statistics.analyzed_cells ?? 0;
  const anomalous = statistics.anomalous ?? 0;
  const high = statistics.high ?? 0;
  const medium = statistics.medium ?? 0;

  return (
    <div className="summary-strip-container" aria-label="Regional intelligence summary">
      {/* Slim Summary Strip */}
      <div className="summary-strip">
        <div className="summary-stat-cell">
          <span className="summary-stat-label">Analyzed locations</span>
          <span className="summary-stat-value">{analyzed}</span>
        </div>

        <div className="summary-stat-divider" aria-hidden="true" />

        <div className="summary-stat-cell highlight-anomalous">
          <span className="summary-stat-label">Anomalous locations</span>
          <span className="summary-stat-value text-amber">{anomalous}</span>
        </div>

        <div className="summary-stat-divider" aria-hidden="true" />

        <div className="summary-stat-cell">
          <span className="summary-stat-label">High priority</span>
          <span className="summary-stat-value text-red">
            <span className="stat-indicator dot-red" aria-hidden="true" />
            {high}
          </span>
        </div>

        <div className="summary-stat-divider" aria-hidden="true" />

        <div className="summary-stat-cell">
          <span className="summary-stat-label">Medium priority</span>
          <span className="summary-stat-value text-amber">
            <span className="stat-indicator dot-amber" aria-hidden="true" />
            {medium}
          </span>
        </div>
      </div>

      {/* Mandatory Single Sentence Under the Strip */}
      <p className="summary-banner-sentence">
        From {analyzed} analyzed locations, Urban IQ flagged {anomalous} for field verification.
      </p>
    </div>
  );
}
