import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Modern Tactical Datatable for Urban IQ Prioritized Anomaly Investigation
 * Features:
 * - Live keyword search by Grid ID, ward name, or reasoning
 * - Priority level filter chips (All / High / Medium)
 * - Multi-criteria sorting (Score, Rank, Grid ID)
 * - Paginated & performant rendering of 1,462+ Sentinel-2 cells
 * - Direct Map flight action ("Map ↗") & Dossier action ("Evidence →")
 */
export default function HotspotTable({
  hotspots = [],
  hoveredId = null,
  onHoverHotspot = () => {},
  filterLevel = 'ALL',
  onFilterChange = () => {}
}) {
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('rank_asc');
  const [pageSize, setPageSize] = useState(50);
  const [currentPage, setCurrentPage] = useState(1);

  // Counts for filter pills
  const totalCount = hotspots.length;
  const highCount = useMemo(() => {
    return hotspots.filter(
      (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'HIGH'
    ).length;
  }, [hotspots]);

  const mediumCount = useMemo(() => {
    return hotspots.filter(
      (h) => (h.priority_level || h.priorityLevel || '').toUpperCase() === 'MEDIUM'
    ).length;
  }, [hotspots]);

  // Filtering & Sorting
  const filteredHotspots = useMemo(() => {
    let result = hotspots;

    // 1. Level filter
    if (filterLevel !== 'ALL') {
      result = result.filter((item) => {
        const level = (item.priority_level || item.priorityLevel || '').toUpperCase();
        return level === filterLevel;
      });
    }

    // 2. Search query filter
    const query = searchQuery.trim().toLowerCase();
    if (query) {
      result = result.filter((item) => {
        const id = (item.grid_id || item.id || '').toLowerCase();
        const ward = (item.ward_name || item.wardName || '').toLowerCase();
        const coords = item.coordinates ? item.coordinates.join(' ') : '';
        const reasons = (item.reasons || []).join(' ').toLowerCase();
        const metric = (item.keyMetric || '').toLowerCase();
        return (
          id.includes(query) ||
          ward.includes(query) ||
          coords.includes(query) ||
          reasons.includes(query) ||
          metric.includes(query)
        );
      });
    }

    // 3. Sorting
    result = [...result].sort((a, b) => {
      if (sortBy === 'score_desc') {
        const sA = a.priority_score ?? a.priorityScore ?? 0;
        const sB = b.priority_score ?? b.priorityScore ?? 0;
        return sB - sA;
      }
      if (sortBy === 'grid_asc') {
        const idA = a.grid_id || a.id || '';
        const idB = b.grid_id || b.id || '';
        return idA.localeCompare(idB);
      }
      // default: rank_asc
      return (a.rank || 0) - (b.rank || 0);
    });

    return result;
  }, [hotspots, filterLevel, searchQuery, sortBy]);

  // Reset page when filter or search changes
  const totalPages = pageSize === 'ALL' ? 1 : Math.ceil(filteredHotspots.length / pageSize) || 1;
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const displayedHotspots = useMemo(() => {
    if (pageSize === 'ALL') return filteredHotspots;
    const start = (safeCurrentPage - 1) * pageSize;
    return filteredHotspots.slice(start, start + pageSize);
  }, [filteredHotspots, safeCurrentPage, pageSize]);

  const handleRowClick = (gridId) => {
    navigate(`/hotspot/${gridId}`);
  };

  const handleFlyToMap = (e, gridId) => {
    e.stopPropagation();
    navigate(`/?target=${gridId}`);
  };

  const handleViewEvidence = (e, gridId) => {
    e.stopPropagation();
    navigate(`/hotspot/${gridId}`);
  };

  const startIndex = (safeCurrentPage - 1) * (pageSize === 'ALL' ? filteredHotspots.length : pageSize) + 1;
  const endIndex = pageSize === 'ALL'
    ? filteredHotspots.length
    : Math.min(safeCurrentPage * pageSize, filteredHotspots.length);

  return (
    <div className="hotspot-table-container">
      {/* 1. Header Toolbar with Search & Filter Chips */}
      <div className="table-toolbar">
        <div className="toolbar-top-row">
          <div className="toolbar-headline">
            <h2 className="toolbar-title">Prioritized Investigation List</h2>
            <span className="toolbar-subtitle font-mono">
              {filteredHotspots.length > 0
                ? `Showing ${startIndex.toLocaleString()}–${endIndex.toLocaleString()} of ${filteredHotspots.length.toLocaleString()} flagged municipal sites`
                : '0 municipal sites matching current criteria'}
            </span>
          </div>

          {/* Quick Level Filter Tabs */}
          <div className="level-filter-group" role="group" aria-label="Filter hotspots by priority level">
            <button
              type="button"
              className={`filter-tab-pill ${filterLevel === 'ALL' ? 'active' : ''}`}
              onClick={() => {
                onFilterChange('ALL');
                setCurrentPage(1);
              }}
            >
              <span>ALL</span>
              <span className="tab-badge-counter">{totalCount.toLocaleString()}</span>
            </button>
            <button
              type="button"
              className={`filter-tab-pill pill-high ${filterLevel === 'HIGH' ? 'active' : ''}`}
              onClick={() => {
                onFilterChange('HIGH');
                setCurrentPage(1);
              }}
            >
              <span className="dot-indicator dot-red" aria-hidden="true" />
              <span>HIGH PRIORITY</span>
              <span className="tab-badge-counter text-red">{highCount.toLocaleString()}</span>
            </button>
            <button
              type="button"
              className={`filter-tab-pill pill-medium ${filterLevel === 'MEDIUM' ? 'active' : ''}`}
              onClick={() => {
                onFilterChange('MEDIUM');
                setCurrentPage(1);
              }}
            >
              <span className="dot-indicator dot-amber" aria-hidden="true" />
              <span>MEDIUM</span>
              <span className="tab-badge-counter text-amber">{mediumCount.toLocaleString()}</span>
            </button>
          </div>
        </div>

        {/* 2. Search & Sort Controls Row */}
        <div className="toolbar-controls-row">
          {/* Search Input */}
          <div className="table-search-box">
            <span className="search-box-icon" aria-hidden="true">&#9906;</span>
            <input
              type="text"
              className="table-search-input font-mono"
              placeholder="Filter by grid ID (e.g. HYD_1220), ward, coords..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              aria-label="Filter hotspots table"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-box-clear"
                onClick={() => setSearchQuery('')}
                aria-label="Clear filter query"
              >
                &times;
              </button>
            )}
          </div>

          <div className="toolbar-right-actions">
            {/* Sort Selector */}
            <div className="table-sort-wrapper font-mono">
              <label htmlFor="table-sort-select" className="sort-label">SORT:</label>
              <select
                id="table-sort-select"
                className="table-select-input font-mono"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
              >
                <option value="rank_asc">Rank # (1 &rarr; N)</option>
                <option value="score_desc">Priority Score (Highest)</option>
                <option value="grid_asc">Grid ID (A &rarr; Z)</option>
              </select>
            </div>

            {/* Page Size Selector */}
            <div className="table-pagesize-wrapper font-mono">
              <label htmlFor="table-pagesize-select" className="sort-label">SHOW:</label>
              <select
                id="table-pagesize-select"
                className="table-select-input font-mono"
                value={pageSize}
                onChange={(e) => {
                  setPageSize(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value));
                  setCurrentPage(1);
                }}
              >
                <option value="25">25</option>
                <option value="50">50</option>
                <option value="100">100</option>
                <option value="ALL">All ({filteredHotspots.length})</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* 3. The Datatable */}
      <div className="table-scroll-wrapper">
        <table className="ranking-table" aria-label="Prioritized hotspot ranking table">
          <thead>
            <tr>
              <th className="th-rank" style={{ width: '70px', textAlign: 'center' }}>RANK</th>
              <th className="th-location" style={{ minWidth: '180px' }}>GRID LOCATION</th>
              <th className="th-score" style={{ width: '160px' }}>PRIORITY SCORE</th>
              <th className="th-reason">DETECTION RATIONALE & SPECTRAL CHANGE</th>
              <th className="th-status" style={{ width: '110px', textAlign: 'center' }}>STATUS</th>
              <th className="th-actions" style={{ width: '160px', textAlign: 'center' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {displayedHotspots.length === 0 ? (
              <tr>
                <td colSpan={6} className="table-empty-cell">
                  <div className="empty-message-box">
                    <span className="empty-icon">&#9888;</span>
                    <p className="empty-text">No municipal sites matching &ldquo;{searchQuery}&rdquo;</p>
                    <button
                      type="button"
                      className="btn-reset-filters font-mono"
                      onClick={() => {
                        setSearchQuery('');
                        onFilterChange('ALL');
                      }}
                    >
                      Reset Filters
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              displayedHotspots.map((item) => {
                const id = item.grid_id || item.id || item.cellId;
                const isHovered = id === hoveredId;
                const level = (item.priority_level || item.priorityLevel || 'LOW').toUpperCase();
                const score = item.priority_score ?? item.priorityScore ?? 0;
                const mainReason = (item.reasons && item.reasons.length > 0)
                  ? item.reasons[0]
                  : item.changeSummary || 'Observed spectral change is unusually strong relative to the scene distribution.';
                const wardName = item.ward_name || item.wardName || 'Hyderabad Urban';
                const coordsFormatted = item.coordinates
                  ? `[${item.coordinates[0]?.toFixed(3)}, ${item.coordinates[1]?.toFixed(3)}]`
                  : null;

                const isTopThree = item.rank && item.rank <= 3;

                return (
                  <tr
                    key={id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Hotspot rank ${item.rank}, ${id}, score ${score}, ${mainReason}`}
                    className={`ranking-row ${isHovered ? 'row-hovered' : ''} ${isTopThree ? 'top-ranked-row' : ''}`}
                    onClick={() => handleRowClick(id)}
                    onMouseEnter={() => onHoverHotspot(id)}
                    onMouseLeave={() => onHoverHotspot(null)}
                    onFocus={() => onHoverHotspot(id)}
                    onBlur={() => onHoverHotspot(null)}
                  >
                    {/* 1. Rank Column */}
                    <td className="rank-cell">
                      <div className={`rank-pill-badge font-mono ${isTopThree ? 'badge-flame-top' : ''}`}>
                        #{item.rank || '-'}
                      </div>
                    </td>

                    {/* 2. Location Column */}
                    <td className="location-cell">
                      <div className="location-grid-id font-mono">{id}</div>
                      <div className="location-meta-row font-mono">
                        <span className="location-ward">{wardName}</span>
                        {coordsFormatted && (
                          <span className="location-coords">{coordsFormatted}</span>
                        )}
                      </div>
                    </td>

                    {/* 3. Priority Score Column with Meter */}
                    <td className="score-cell font-mono">
                      <div className="score-number-row">
                        <span className={`score-value ${level === 'HIGH' ? 'text-red' : 'text-amber'}`}>
                          {score}
                        </span>
                        <span className="score-max">/ 100</span>
                      </div>
                      <div className="score-meter-track" aria-hidden="true">
                        <div
                          className={`score-meter-fill ${level === 'HIGH' ? 'meter-high' : 'meter-medium'}`}
                          style={{ width: `${Math.min(100, Math.max(8, score))}%` }}
                        />
                      </div>
                    </td>

                    {/* 4. Main Reason Column with Metrics */}
                    <td className="reason-cell">
                      <div className="main-reason-quote">&ldquo;{mainReason}&rdquo;</div>
                      <div className="reason-tags-row font-mono">
                        {item.keyMetric && (
                          <span className="metric-pill metric-displacement">
                            {item.keyMetric}
                          </span>
                        )}
                        {item.metrics?.ndvi_delta !== undefined && (
                          <span className="metric-pill metric-ndvi">
                            NDVI {item.metrics.ndvi_delta > 0 ? `+${item.metrics.ndvi_delta.toFixed(2)}` : item.metrics.ndvi_delta.toFixed(2)}
                          </span>
                        )}
                        {item.metrics?.ndbi_delta !== undefined && (
                          <span className="metric-pill metric-ndbi">
                            NDBI {item.metrics.ndbi_delta > 0 ? `+${item.metrics.ndbi_delta.toFixed(2)}` : item.metrics.ndbi_delta.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* 5. Status Column */}
                    <td className="status-cell">
                      <span
                        className={`status-pill font-mono ${
                          level === 'HIGH'
                            ? 'status-pill-high'
                            : level === 'MEDIUM'
                            ? 'status-pill-medium'
                            : 'status-pill-monitored'
                        }`}
                      >
                        <span
                          className={`status-dot ${level === 'HIGH' ? 'bg-red' : 'bg-amber'}`}
                          aria-hidden="true"
                        />
                        {level}
                      </span>
                    </td>

                    {/* 6. Quick Action Buttons */}
                    <td className="actions-cell font-mono">
                      <div className="row-action-cluster">
                        <button
                          type="button"
                          className="action-btn-fly"
                          onClick={(e) => handleFlyToMap(e, id)}
                          title={`Fly to ${id} on central map`}
                        >
                          Map ↗
                        </button>
                        <button
                          type="button"
                          className="action-btn-evidence"
                          onClick={(e) => handleViewEvidence(e, id)}
                          title={`Open ${id} evidence dossier`}
                        >
                          Evidence &rarr;
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 4. Pagination Footer */}
      {pageSize !== 'ALL' && totalPages > 1 && (
        <div className="table-pagination-bar font-mono">
          <div className="pagination-info">
            Showing <strong>{startIndex.toLocaleString()}–{endIndex.toLocaleString()}</strong> of <strong>{filteredHotspots.length.toLocaleString()}</strong>
          </div>

          <div className="pagination-controls">
            <button
              type="button"
              className="pagination-btn"
              disabled={safeCurrentPage <= 1}
              onClick={() => setCurrentPage(1)}
              title="First page"
            >
              &laquo;
            </button>
            <button
              type="button"
              className="pagination-btn"
              disabled={safeCurrentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              title="Previous page"
            >
              &lsaquo; Prev
            </button>

            <span className="pagination-current-page">
              Page <strong>{safeCurrentPage}</strong> of <strong>{totalPages}</strong>
            </span>

            <button
              type="button"
              className="pagination-btn"
              disabled={safeCurrentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              title="Next page"
            >
              Next &rsaquo;
            </button>
            <button
              type="button"
              className="pagination-btn"
              disabled={safeCurrentPage >= totalPages}
              onClick={() => setCurrentPage(totalPages)}
              title="Last page"
            >
              &raquo;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
