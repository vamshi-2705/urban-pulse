import React from 'react';

export default function Header({ overview, isConnected }) {
  return (
    <header className="app-header" id="main-header">
      <div className="header-brand">
        <div className="brand-symbol" aria-hidden="true">UP</div>
        <div className="brand-text">
          <h1>UrbanPulse</h1>
          <p>Municipal Change & Field Investigation Intelligence</p>
        </div>
      </div>

      <div className="header-metadata">
        {overview && (
          <>
            <div className="meta-group">
              <span className="meta-label">Monitored region</span>
              <span className="meta-value">{overview.regionName || 'Loading...'}</span>
            </div>
            <div className="meta-group">
              <span className="meta-label">Observation cycle</span>
              <span className="meta-value">{overview.currentEvaluationPeriod || '2023–2026'}</span>
            </div>
          </>
        )}
        <div className="meta-group">
          <span className="meta-label">System status</span>
          <span className="status-pill">
            <span
              className={`status-dot ${isConnected ? 'status-dot-green' : 'status-dot-red'}`}
              aria-hidden="true"
            />
            <span className="meta-value">{isConnected ? 'Online (Mock Provider)' : 'Connecting...'}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
