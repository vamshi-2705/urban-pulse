import React, { useState, useRef, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

/**
 * TrafficPulse-Inspired Clean Top Navigation
 * Left: [UP] URBANPULSE • Geospatial Change Intelligence
 * Center: Rounded Search Bar (Search hotspot, location or grid ID...)
 * Right: Telemetry (SENTINEL-2 • REAL DATA • 2020 → 2026 • ANALYSIS READY) + Nav Links
 */
export default function Header({
  hotspots = [],
  onSelectHotspot,
  activePeriod = '2020_2026',
  onStartGuidedTour
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  const periodLabel =
    activePeriod === '2020_2023'
      ? '2020 → 2023'
      : activePeriod === '2023_2026'
      ? '2023 → 2026'
      : '2020 → 2026';

  // Filter real hotspots by grid ID or coords
  const filteredHotspots = searchQuery.trim()
    ? (hotspots || [])
        .filter((h) => {
          const id = (h.grid_id || h.id || '').toLowerCase();
          const query = searchQuery.trim().toLowerCase();
          return id.includes(query) || (h.coordinates && h.coordinates.join(', ').includes(query));
        })
        .slice(0, 5)
    : [];

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (id) => {
    setSearchQuery('');
    setIsDropdownOpen(false);
    if (onSelectHotspot) {
      onSelectHotspot(id);
    }
    navigate(`/?target=${id}`);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      if (filteredHotspots.length > 0) {
        const first = filteredHotspots[0];
        handleSelect(first.grid_id || first.id);
      } else if (searchQuery.trim().toUpperCase().startsWith('HYD_')) {
        handleSelect(searchQuery.trim().toUpperCase());
      }
    }
  };

  return (
    <header className="traffic-topbar" id="main-header" aria-label="Urban IQ Navigation Bar">
      {/* LEFT: Branding */}
      <div className="topbar-left">
        <NavLink to="/" className="brand-logo-link">
          <div className="brand-badge-circle">
            <span className="brand-badge-text">UI</span>
          </div>
          <div className="brand-text-block">
            <span className="brand-title">URBAN IQ</span>
            <span className="brand-subtitle">Geospatial Change Intelligence</span>
          </div>
        </NavLink>
      </div>

      {/* CENTER: Rounded Search Bar */}
      <div className="topbar-search-wrapper" ref={dropdownRef}>
        <div className="topbar-search-bar">
          <span className="search-icon" aria-hidden="true">&#9906;</span>
          <input
            type="text"
            className="search-input font-mono"
            placeholder="Search hotspot, location or grid ID (e.g. HYD_1220)..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setIsDropdownOpen(true);
            }}
            onFocus={() => setIsDropdownOpen(true)}
            onKeyDown={handleKeyDown}
            aria-label="Search hotspots"
          />
          {searchQuery && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => {
                setSearchQuery('');
                setIsDropdownOpen(false);
              }}
              aria-label="Clear search"
            >
              &times;
            </button>
          )}
        </div>

        {/* Live Search Suggestions Dropdown */}
        {isDropdownOpen && searchQuery.trim().length > 0 && (
          <div className="search-dropdown-menu font-mono">
            {filteredHotspots.length > 0 ? (
              filteredHotspots.map((item) => {
                const id = item.grid_id || item.id;
                const score = item.priority_score ?? item.priorityScore ?? 80;
                const displayScore =
                  typeof score === 'number' && score < 1
                    ? Math.round(score * 100)
                    : Math.round(score);
                const level = (item.priority_level || item.priorityLevel || 'HIGH').toUpperCase();

                return (
                  <button
                    key={id}
                    type="button"
                    className="search-dropdown-item"
                    onClick={() => handleSelect(id)}
                  >
                    <div className="item-main">
                      <span className="item-id">{id}</span>
                      <span className={`item-level lvl-${level.toLowerCase()}`}>{level}</span>
                    </div>
                    <span className="item-score">{displayScore} / 100</span>
                  </button>
                );
              })
            ) : (
              <div className="search-dropdown-empty">
                No matching hotspots found
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT: Telemetry & Navigation */}
      <div className="topbar-right">
        <nav className="topbar-nav-links" aria-label="Page navigation">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-pill font-mono ${isActive ? 'active' : ''}`}
          >
            MAP
          </NavLink>
          <NavLink
            to="/ranking"
            className={({ isActive }) => `nav-pill font-mono ${isActive ? 'active' : ''}`}
          >
            RANKING
          </NavLink>
          {onStartGuidedTour && (
            <button
              type="button"
              className="nav-pill font-mono topbar-guided-btn"
              onClick={onStartGuidedTour}
              title="Launch automated 7-scene Guided Investigation demonstration"
            >
              <span className="guided-btn-icon">&#9654;</span>
              <span>GUIDED DEMO</span>
            </button>
          )}
        </nav>

        <div className="topbar-telemetry-badge font-mono">
          <span className="telemetry-sensor">SENTINEL-2</span>
          <span className="telemetry-sep">&bull;</span>
          <span className="telemetry-years">{periodLabel}</span>
        </div>

        <div className="topbar-status-indicator font-mono">
          <span className="pulse-dot-green" aria-hidden="true" />
          <span>ANALYSIS READY</span>
        </div>
      </div>
    </header>
  );
}
