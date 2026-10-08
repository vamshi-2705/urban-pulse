import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function HotspotTable({
  hotspots = [],
  hoveredId = null,
  onHoverHotspot = () => {},
  filterLevel = 'ALL',
  onFilterChange = () => {}
}) {
  const navigate = useNavigate();

  // Filter hotspots by level
  const filteredHotspots = hotspots.filter((item) => {
    if (filterLevel === 'ALL') return true;
    const level = (item.priority_level || item.priorityLevel || '').toUpperCase();
    return level === filterLevel;
  });

  const highCount = hotspots.filter(
    (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'HIGH'
  ).length;

  const mediumCount = hotspots.filter(
    (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'MEDIUM'
  ).length;

  const handleRowClick = (gridId) => {
    navigate(`/hotspot/${gridId}`);
  };

  const handleKeyDown = (e, gridId) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleRowClick(gridId);
    }
  };

  return (
    <div className="hotspot-table-container">
      {/* Table Header & Level Filter Toolbar */}
      <div className="table-toolbar">
        <div className="toolbar-left">
          <h2 className="toolbar-title">Prioritized Investigation List</h2>
          <span className="toolbar-subtitle">
            Showing {filteredHotspots.length} of {hotspots.length} flagged municipal sites
          </span>
        </div>

        {/* Filter by level: All / High / Medium */}
        <div className="level-filter-group" role="group" aria-label="Filter hotspots by priority level">
          <button
            type="button"
            className={`filter-tab ${filterLevel === 'ALL' ? 'active' : ''}`}
            onClick={() => onFilterChange('ALL')}
          >
            All <span className="tab-badge">{hotspots.length}</span>
          </button>
          <button
            type="button"
            className={`filter-tab ${filterLevel === 'HIGH' ? 'active' : ''}`}
            onClick={() => onFilterChange('HIGH')}
          >
            High <span className="tab-badge text-red">{highCount}</span>
          </button>
          <button
            type="button"
            className={`filter-tab ${filterLevel === 'MEDIUM' ? 'active' : ''}`}
            onClick={() => onFilterChange('MEDIUM')}
          >
            Medium <span className="tab-badge text-amber">{mediumCount}</span>
          </button>
        </div>
      </div>

      {/* Interactive Table with Keyboard-Focusable Rows */}
      <div className="table-scroll-wrapper">
        <table className="ranking-table" aria-label="Prioritized hotspot ranking table">
          <thead>
            <tr>
              <th style={{ width: '64px', textAlign: 'center' }}>Rank</th>
              <th style={{ minWidth: '180px' }}>Location</th>
              <th style={{ width: '120px', textAlign: 'right' }}>Priority score</th>
              <th>Main reason</th>
              <th style={{ width: '130px', textAlign: 'center' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {filteredHotspots.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                  No hotspots found matching the selected filter.
                </td>
              </tr>
            ) : (
              filteredHotspots.map((item) => {
                const id = item.grid_id || item.id || item.cellId;
                const isHovered = id === hoveredId;
                const level = (item.priority_level || item.priorityLevel || 'LOW').toUpperCase();
                const score = item.priority_score ?? item.priorityScore ?? 0;
                const mainReason = (item.reasons && item.reasons.length > 0)
                  ? item.reasons[0]
                  : item.changeSummary || 'Unusual land cover change detected';
                const wardName = item.ward_name || item.wardName || 'Hyderabad Urban';

                return (
                  <tr
                    key={id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Hotspot rank ${item.rank}, ${id}, ${wardName}, priority score ${score}, ${mainReason}`}
                    className={`ranking-row ${isHovered ? 'row-hovered' : ''}`}
                    onClick={() => handleRowClick(id)}
                    onKeyDown={(e) => handleKeyDown(e, id)}
                    onMouseEnter={() => onHoverHotspot(id)}
                    onMouseLeave={() => onHoverHotspot(null)}
                    onFocus={() => onHoverHotspot(id)}
                    onBlur={() => onHoverHotspot(null)}
                  >
                    {/* 1. Rank Column */}
                    <td className="rank-cell">
                      <span className="rank-badge">#{item.rank}</span>
                    </td>

                    {/* 2. Location Column */}
                    <td className="location-cell">
                      <div className="location-grid-id">{id}</div>
                      <div className="location-ward">{wardName}</div>
                    </td>

                    {/* 3. Priority Score Column */}
                    <td className="score-cell">
                      <span className="score-value">{score}</span>
                      <span className="score-max">/ 100</span>
                    </td>

                    {/* 4. Main Reason Column */}
                    <td className="reason-cell">
                      <div className="main-reason-text">&ldquo;{mainReason}&rdquo;</div>
                      {item.keyMetric && (
                        <div className="reason-metric-sub">{item.keyMetric}</div>
                      )}
                    </td>

                    {/* 5. Status Column */}
                    <td className="status-cell">
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
                          className={`status-dot-sm ${
                            level === 'HIGH' ? 'bg-red' : 'bg-amber'
                          }`}
                          aria-hidden="true"
                        />
                        {level}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
