import React, { useMemo } from 'react';

/**
 * Slide-in Investigation Drawer (Overlays map without reducing map width)
 * Opens when floating INVESTIGATIONS button is clicked; closes on ×.
 */
export default function InvestigationQueue({
  statistics,
  hotspots = [],
  selectedGridId = 'HYD_1220',
  onSelectHotspot,
  loading = false,
  error = null,
  onRetry,
  onClose
}) {
  const highCount = statistics?.high ?? 27;
  const mediumCount = statistics?.medium ?? 453;

  // Filter top priority list
  const topList = useMemo(() => {
    if (!Array.isArray(hotspots) || hotspots.length === 0) return [];
    return hotspots.slice(0, 30);
  }, [hotspots]);

  return (
    <div
      className="investigation-drawer-overlay"
      role="dialog"
      aria-label="Investigations Queue"
    >
      <div className="drawer-header-bar">
        <div className="drawer-title-stack">
          <span className="drawer-main-title font-mono">INVESTIGATIONS</span>
          <div className="drawer-triage-counts font-mono">
            <span className="text-red">{highCount} HIGH</span>
            <span className="count-sep">&bull;</span>
            <span className="text-amber">{mediumCount} MEDIUM</span>
          </div>
        </div>

        <button
          type="button"
          className="drawer-close-icon"
          onClick={onClose}
          title="Close investigations drawer"
          aria-label="Close investigations drawer"
        >
          &times;
        </button>
      </div>

      <div className="drawer-divider-line" />

      {/* Candidates List */}
      <div className="investigation-drawer-list" role="list">
        {loading && (
          <div className="drawer-empty-msg font-mono">
            ANALYZING SATELLITE OBSERVATIONS...
          </div>
        )}

        {error && (
          <div className="drawer-empty-msg error-msg font-mono">
            <span>INTELLIGENCE SERVICE UNAVAILABLE</span>
            {onRetry && (
              <button
                type="button"
                className="btn btn-outline-primary btn-sm"
                onClick={onRetry}
              >
                RETRY
              </button>
            )}
          </div>
        )}

        {!loading && !error && topList.length === 0 && (
          <div className="drawer-empty-msg font-mono">
            NO INVESTIGATION TARGETS
          </div>
        )}

        {!loading && !error && topList.map((item, idx) => {
          const id = item.grid_id || item.id || item.cellId;
          const isSelected = id === selectedGridId;
          const rankStr = String(idx + 1).padStart(2, '0');
          const rawScore = item.priorityScore ?? item.priority_score ?? 0;
          const score =
            typeof rawScore === 'number' && rawScore < 1
              ? (rawScore * 100).toFixed(0)
              : Number(rawScore).toFixed(0);
          const level = (item.priorityLevel || item.priority_level || 'LOW').toUpperCase();
          const isHigh = level === 'HIGH';

          return (
            <div
              key={id}
              role="listitem"
              tabIndex={0}
              className={`drawer-candidate-row ${isSelected ? 'selected' : ''}`}
              onClick={() => {
                if (onSelectHotspot) onSelectHotspot(id);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  if (onSelectHotspot) onSelectHotspot(id);
                }
              }}
            >
              <div className="candidate-left">
                <span className="candidate-rank font-mono">{rankStr}</span>
                <div className="candidate-id-stack">
                  <span className="candidate-id font-mono">{id}</span>
                  <span className={`candidate-level font-mono ${isHigh ? 'text-red' : 'text-amber'}`}>
                    {level}
                  </span>
                </div>
              </div>

              <div className="candidate-right">
                <span className={`candidate-score font-mono ${isHigh ? 'text-red' : 'text-amber'}`}>
                  {score}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
