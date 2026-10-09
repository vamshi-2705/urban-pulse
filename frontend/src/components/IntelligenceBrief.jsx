import React from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * TrafficPulse-Inspired Right Floating Intelligence Panel
 * - Header: SELECTED LOCATION
 * - HYD_1220 + coordinates
 * - Circular Score Ring (82 / 100)
 * - FIELD VERIFICATION RECOMMENDED
 * - WHY FLAGGED compact rows (Vegetation, Built-up, Spatial anomaly, Persistence)
 * - Primary Actions: [ VIEW EVIDENCE ] & [ CHANGE EXPLORER ]
 */
export default function IntelligenceBrief({
  hotspot,
  selectedGridId = 'HYD_1220',
  activePeriod = '2020_2026',
  loading = false
}) {
  const navigate = useNavigate();

  const periodLabel =
    activePeriod === '2020_2023'
      ? '2020 → 2023'
      : activePeriod === '2023_2026'
      ? '2023 → 2026'
      : '2020 → 2026';

  const id = hotspot?.grid_id || hotspot?.id || selectedGridId || 'HYD_1220';
  const level = (hotspot?.priority_level || hotspot?.priorityLevel || 'HIGH').toUpperCase();
  const rawScore = hotspot?.priority_score ?? hotspot?.priorityScore ?? 82;
  const score =
    typeof rawScore === 'number' && rawScore < 1
      ? Math.round(rawScore * 100)
      : Math.round(rawScore);

  const lat = hotspot?.lat ?? hotspot?.coordinates?.[0] ?? 17.372285;
  const lng = hotspot?.lng ?? hotspot?.coordinates?.[1] ?? 78.422560;

  // Real spectral signals from API
  const signals = hotspot?.signals || {};
  const change = hotspot?.change || {};
  const anomaly = hotspot?.anomaly || {};
  const evidence = hotspot?.evidence || {};

  const ndviDelta = signals.ndvi_delta ?? change.ndvi_delta ?? -0.5543;
  const ndbiDelta = signals.ndbi_delta ?? change.ndbi_delta ?? 0.2766;
  const spatialAnomaly = signals.spatial_anomaly ?? anomaly.spatial ?? 1.0;
  const spatialLevel = spatialAnomaly >= 0.7 ? 'HIGH' : 'ELEVATED';
  const persistenceStatus =
    evidence.persistent_change !== false && hotspot?.persistence !== 'cyclical'
      ? 'DETECTED'
      : 'NOMINAL';

  // Circular gauge calculation (radius 36, circumference ~226)
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div
      className="traffic-floating-card right-panel"
      aria-label="Selected location intelligence dossier"
    >
      {/* Panel Category & Title */}
      <div className="panel-header-row">
        <div className="panel-title-stack">
          <span className="panel-category-tag font-mono">ANALYSIS: {periodLabel}</span>
          <h2 className="panel-title font-mono">SELECTED LOCATION</h2>
        </div>
      </div>

      {/* Target ID & Coordinates */}
      <div className="selected-target-hero">
        <div className="target-id-badge-row">
          <h3 className="selected-id font-mono">{id}</h3>
          <span className={`selected-level-pill font-mono lvl-${level.toLowerCase()}`}>
            {level} PRIORITY
          </span>
        </div>
        <p className="selected-coords font-mono">
          {Number(lat).toFixed(6)}, {Number(lng).toFixed(6)}
        </p>
      </div>

      {/* Circular Score Gauge & Recommendation */}
      <div className="score-gauge-cluster">
        <div className="gauge-svg-wrapper">
          <svg className="score-gauge-svg" width="96" height="96" viewBox="0 0 96 96">
            <circle
              className="gauge-bg"
              cx="48"
              cy="48"
              r={radius}
              strokeWidth="7"
            />
            <circle
              className="gauge-progress"
              cx="48"
              cy="48"
              r={radius}
              strokeWidth="7"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
            />
          </svg>
          <div className="gauge-center-text font-mono">
            <span className="gauge-score-value">{score}</span>
            <span className="gauge-score-denom">/100</span>
          </div>
        </div>

        <div className="directive-tag-box font-mono">
          <span className="directive-icon">&#9678;</span>
          <span className="directive-text">FIELD VERIFICATION RECOMMENDED</span>
        </div>
      </div>

      <div className="panel-section-divider" />

      {/* Compact WHY FLAGGED Section */}
      <div className="why-flagged-card">
        <div className="section-label-row font-mono">
          <span className="section-title">WHY FLAGGED</span>
          <span className="section-badge text-orange">SIGNALS</span>
        </div>

        <div className="why-signals-grid font-mono">
          <div className="signal-cell">
            <span className="signal-label">Vegetation</span>
            <span className="signal-val text-red">
              {ndviDelta > 0 ? `+${ndviDelta.toFixed(3)}` : ndviDelta.toFixed(3)}
            </span>
          </div>

          <div className="signal-cell">
            <span className="signal-label">Built-up</span>
            <span className="signal-val text-orange">
              {ndbiDelta > 0 ? `+${ndbiDelta.toFixed(3)}` : ndbiDelta.toFixed(3)}
            </span>
          </div>

          <div className="signal-cell">
            <span className="signal-label">Spatial anomaly</span>
            <span className="signal-val text-amber">{spatialLevel}</span>
          </div>

          <div className="signal-cell">
            <span className="signal-label">Persistence</span>
            <span className="signal-val text-green">{persistenceStatus}</span>
          </div>
        </div>
      </div>

      <div className="panel-section-divider" />

      {/* Action Buttons */}
      <div className="intelligence-action-buttons font-mono">
        <button
          type="button"
          className="btn-action-primary"
          onClick={() => navigate(`/hotspot/${id}/evidence?period=${activePeriod}`)}
        >
          <span>VIEW EVIDENCE</span>
          <span className="arrow-right">&rarr;</span>
        </button>

        <button
          type="button"
          className="btn-action-secondary"
          onClick={() => navigate(`/hotspot/${id}/change?period=${activePeriod}`)}
        >
          <span>CHANGE EXPLORER</span>
          <span className="arrow-right">&rarr;</span>
        </button>
      </div>
    </div>
  );
}
