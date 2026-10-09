import React, { useMemo } from 'react';

/**
 * TrafficPulse-Inspired Left Floating Investigation Panel
 * - Header: INVESTIGATION
 * - Stat Cards: 27 HIGH PRIORITY | 453 MEDIUM | 982 LOW
 * - Top Investigations: 4–6 compact items (e.g. HYD_1220, HYD_1223, HYD_0863, HYD_1200)
 * - Action: VIEW ALL → to open full triage queue
 */
export default function InvestigationPanel({
  statistics,
  hotspots = [],
  selectedGridId = 'HYD_1220',
  onSelectHotspot,
  onOpenFullQueue,
  onStartGuidedTour,
  loading = false,
  error = null
}) {
  const highCount = statistics?.high ?? 27;
  const mediumCount = statistics?.medium ?? 453;
  const lowCount = statistics?.low ?? 982;

  // Filter top 4 to 6 investigations
  const topList = useMemo(() => {
    if (!Array.isArray(hotspots) || hotspots.length === 0) return [];
    return hotspots.slice(0, 5);
  }, [hotspots]);

  return (
    <div className="traffic-floating-card left-panel" aria-label="Investigation triage panel">
      {/* Panel Header */}
      <div className="panel-header-row">
        <div className="panel-title-stack">
          <span className="panel-category-tag font-mono">OPERATIONAL TRIAGE</span>
          <h2 className="panel-title font-mono">INVESTIGATION</h2>
        </div>
      </div>

      {/* Guided Investigation Hero Trigger */}
      {onStartGuidedTour && (
        <button
          type="button"
          className="guided-tour-hero-trigger font-mono"
          onClick={onStartGuidedTour}
          title="Launch automated 7-scene Guided Investigation demonstration"
        >
          <div className="guided-trigger-left">
            <span className="guided-pulse-dot" />
            <span className="guided-trigger-title">GUIDED INVESTIGATION</span>
          </div>
          <span className="guided-trigger-badge">7 SCENES &rarr;</span>
        </button>
      )}

      {/* 3 Compact Stat Cards */}
      <div className="panel-stats-grid">
        <div className="stat-card stat-card-high">
          <div className="stat-card-top">
            <span className="stat-number font-mono">{highCount}</span>
            <span className="stat-pill-indicator bg-red font-mono">HIGH</span>
          </div>
          <span className="stat-label">HIGH PRIORITY</span>
        </div>

        <div className="stat-card stat-card-med">
          <div className="stat-card-top">
            <span className="stat-number font-mono">{mediumCount}</span>
            <span className="stat-pill-indicator bg-amber font-mono">MED</span>
          </div>
          <span className="stat-label">MEDIUM</span>
        </div>

        <div className="stat-card stat-card-low">
          <div className="stat-card-top">
            <span className="stat-number font-mono">{lowCount}</span>
            <span className="stat-pill-indicator bg-muted font-mono">LOW</span>
          </div>
          <span className="stat-label">MONITORED</span>
        </div>
      </div>

      <div className="panel-section-divider" />

      {/* Top Investigations Section */}
      <div className="top-investigations-container">
        <div className="section-label-row font-mono">
          <span className="section-title">TOP INVESTIGATIONS</span>
          <span className="section-badge">{topList.length} TARGETS</span>
        </div>

        {loading && (
          <div className="panel-empty-state font-mono">
            <span>SYNCING OBSERVATION QUEUE...</span>
          </div>
        )}

        {error && (
          <div className="panel-empty-state error font-mono">
            <span>TELEMETRY TIMEOUT</span>
          </div>
        )}

        {!loading && !error && (
          <div className="top-targets-list" role="list">
            {topList.map((item, idx) => {
              const id = item.grid_id || item.id;
              const isSelected = id === selectedGridId;
              const rankStr = String(idx + 1).padStart(2, '0');
              const rawScore = item.priorityScore ?? item.priority_score ?? 80;
              const score =
                typeof rawScore === 'number' && rawScore < 1
                  ? Math.round(rawScore * 100)
                  : Math.round(rawScore);
              const level = (item.priorityLevel || item.priority_level || 'HIGH').toUpperCase();
              const isHigh = level === 'HIGH';

              return (
                <div
                  key={id}
                  role="listitem"
                  tabIndex={0}
                  className={`target-compact-row ${isSelected ? 'active-target' : ''}`}
                  onClick={() => onSelectHotspot && onSelectHotspot(id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (onSelectHotspot) onSelectHotspot(id);
                    }
                  }}
                >
                  <div className="target-row-left">
                    <span className="target-rank font-mono">{rankStr}</span>
                    <div className="target-id-group">
                      <span className="target-id font-mono">{id}</span>
                      <span className={`target-lvl font-mono ${isHigh ? 'text-red' : 'text-amber'}`}>
                        {level}
                      </span>
                    </div>
                  </div>

                  <div className="target-row-right">
                    <span className={`target-score-badge font-mono ${isHigh ? 'score-high' : 'score-med'}`}>
                      {score}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* View All Queue Trigger */}
        <button
          type="button"
          className="btn-view-all-queue font-mono"
          onClick={onOpenFullQueue}
        >
          <span>VIEW ALL QUEUE ({hotspots.length || 27})</span>
          <span className="arrow-right">&rarr;</span>
        </button>
      </div>
    </div>
  );
}
