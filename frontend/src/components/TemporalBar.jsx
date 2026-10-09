import React from 'react';

/**
 * Functional Analysis Period Controls
 * Supported periods: 2020_2026, 2020_2023, 2023_2026
 * Distinct visual state for active period.
 */
export default function TemporalBar({
  activePeriod = '2020_2026',
  onSelectPeriod
}) {
  const periods = [
    { id: '2020_2026', label: '2020 → 2026' },
    { id: '2020_2023', label: '2020 → 2023' },
    { id: '2023_2026', label: '2023 → 2026' }
  ];

  return (
    <div className="tiny-bottom-timeline font-mono" role="region" aria-label="Analysis period selector">
      <span className="analysis-period-tag">ANALYSIS PERIOD</span>
      <div className="timeline-pill-sep" />
      <div className="timeline-pills-row" role="group" aria-label="Epoch period selector">
        {periods.map((p) => {
          const isActive = activePeriod === p.id;
          return (
            <button
              key={p.id}
              type="button"
              className={`timeline-pill-btn ${isActive ? 'active' : ''}`}
              onClick={() => onSelectPeriod && onSelectPeriod(p.id)}
              title={`Switch analysis period to ${p.label}`}
              aria-pressed={isActive}
            >
              [ {p.label} ]
            </button>
          );
        })}
      </div>
    </div>
  );
}
