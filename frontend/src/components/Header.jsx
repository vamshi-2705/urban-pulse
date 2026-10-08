import React from 'react';
import { NavLink } from 'react-router-dom';

export default function Header({ overview, isConnected }) {
  return (
    <header className="app-header" id="main-header">
      <div className="header-left-cluster">
        <div className="header-brand">
          <div className="brand-symbol" aria-hidden="true">UP</div>
          <div className="brand-text">
            <h1>UrbanPulse</h1>
            <p>Municipal Change & Field Investigation Intelligence</p>
          </div>
        </div>

        <nav className="header-nav" aria-label="Main Navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-tab ${isActive ? 'active' : ''}`}
          >
            Overview
          </NavLink>
          <NavLink
            to="/ranking"
            className={({ isActive }) => `nav-tab ${isActive ? 'active' : ''}`}
          >
            Hotspot ranking
          </NavLink>
        </nav>
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
            <span className="meta-value">{isConnected ? 'Online' : 'Connecting...'}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
