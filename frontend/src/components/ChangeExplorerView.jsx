import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Polygon, CircleMarker, useMap } from 'react-leaflet';
import { fetchChange, fetchHotspotDetail, fetchEvidence } from '../api/client';

/**
 * Controller to ensure Leaflet map centers on the selected cell
 */
function MapRecenter({ center }) {
  const map = useMap();
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.setView(center, 14, { animate: true });
    }
  }, [center, map]);
  return null;
}

/**
 * Clean SVG Bar & Trendline Chart component
 * Renders 2020, 2023, 2026 sequence with proportional bars and connecting slope
 */
function MetricSvgChart({ items = [], color = '#4338ca', unit = '%' }) {
  if (!items || items.length === 0) return null;

  const width = 220;
  const height = 90;
  const paddingBottom = 22;
  const paddingTop = 20;
  const chartHeight = height - paddingBottom - paddingTop;

  const values = items.map((d) => Number(d.value) || 0);
  const maxVal = Math.max(...values, 50);

  const barWidth = 32;
  const xPositions = [36, 110, 184];

  const points = items.map((item, idx) => {
    const val = Number(item.value) || 0;
    const barH = Math.max(4, (val / maxVal) * chartHeight);
    const x = xPositions[idx];
    const y = height - paddingBottom - barH;
    return {
      x,
      y,
      barH,
      year: item.year,
      val: Math.round(val)
    };
  });

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="metric-svg-chart"
      style={{ width: '100%', height: '90px', display: 'block' }}
      aria-label="Metric trajectory chart"
    >
      {/* Baseline */}
      <line
        x1="12"
        y1={height - paddingBottom}
        x2={width - 12}
        y2={height - paddingBottom}
        stroke="var(--border-default, #e2e8f0)"
        strokeWidth="1.5"
      />

      {/* Bars */}
      {points.map((p) => (
        <g key={p.year}>
          <rect
            x={p.x - barWidth / 2}
            y={p.y}
            width={barWidth}
            height={p.barH}
            rx="3"
            fill={color}
            fillOpacity="0.85"
          />
          {/* Top Value Label */}
          <text
            x={p.x}
            y={p.y - 5}
            textAnchor="middle"
            fontSize="11"
            fontWeight="700"
            fill="var(--text-primary, #1e293b)"
          >
            {p.val}{unit}
          </text>
          {/* Bottom Year Label */}
          <text
            x={p.x}
            y={height - 6}
            textAnchor="middle"
            fontSize="11"
            fontWeight="600"
            fill="var(--text-muted, #64748b)"
          >
            {p.year}
          </text>
        </g>
      ))}

      {/* Trend line connecting tops of bars */}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeDasharray="3 3"
        opacity="0.9"
      />
      {points.map((p) => (
        <circle
          key={`dot-${p.year}`}
          cx={p.x}
          cy={p.y}
          r="3"
          fill="#ffffff"
          stroke={color}
          strokeWidth="2"
        />
      ))}
    </svg>
  );
}

export default function ChangeExplorerView() {
  const { gridId } = useParams();
  const navigate = useNavigate();

  const [changeData, setChangeData] = useState(null);
  const [detail, setDetail] = useState(null);
  const [evidenceData, setEvidenceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Before/after imagery selected years
  const [beforeYear, setBeforeYear] = useState(2020);
  const [afterYear, setAfterYear] = useState(2026);
  const [imageErrors, setImageErrors] = useState({});

  useEffect(() => {
    async function loadData() {
      if (!gridId) return;
      try {
        setLoading(true);
        setError(null);

        const [changeRes, detailRes, evidenceRes] = await Promise.all([
          fetchChange(gridId),
          fetchHotspotDetail(gridId).catch(() => null),
          fetchEvidence(gridId).catch(() => null)
        ]);

        setChangeData(changeRes);
        setDetail(detailRes);
        setEvidenceData(evidenceRes);
      } catch (err) {
        console.error(`Failed to load change data for ${gridId}:`, err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [gridId]);

  // Convert GeoJSON polygon to Leaflet [lat, lng] format
  const polygonPositions = useMemo(() => {
    if (detail?.geometry?.coordinates?.[0]) {
      return detail.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]);
    }
    return null;
  }, [detail]);

  const mapCenter = useMemo(() => {
    if (detail?.lat && detail?.lng) {
      return [detail.lat, detail.lng];
    }
    return [17.385, 78.486];
  }, [detail]);

  // Priority level styling for mini map
  const priorityLevel = (detail?.priority_level || 'LOW').toUpperCase();
  const mapColor =
    priorityLevel === 'HIGH' ? '#dc2626' : priorityLevel === 'MEDIUM' ? '#d97706' : '#16a34a';

  // Helper to test if image exists for a given year
  const isImageAvailable = (year) => {
    if (imageErrors[year]) return false;
    if (!evidenceData?.images || evidenceData.images.length === 0) return false;
    return evidenceData.images.some((url) => url.includes(`/${year}.svg`));
  };

  const handleImageError = (year) => {
    setImageErrors((prev) => ({ ...prev, [year]: true }));
  };

  if (loading) {
    return (
      <div className="why-flagged-container loading-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ fontWeight: 600 }}>Loading Change Explorer for {gridId}...</p>
      </div>
    );
  }

  if (error || !changeData) {
    return (
      <div className="why-flagged-container" style={{ padding: '40px 20px', maxWidth: '640px', margin: '0 auto' }}>
        <div className="error-card">
          <h2>Change Series Not Found</h2>
          <p>{error || `No change trajectory found for grid ID '${gridId}'`}</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/ranking')}>
            &larr; Back to Hotspot ranking
          </button>
        </div>
      </div>
    );
  }

  // Sequences formatted as "31% -> 38% -> 47%"
  const formatSequence = (series) => {
    if (!series || series.length < 3) return 'N/A';
    const v0 = Math.round(series[0].value ?? 0);
    const v1 = Math.round(series[1].value ?? 0);
    const v2 = Math.round(series[2].value ?? 0);
    return `${v0}% -> ${v1}% -> ${v2}%`;
  };

  const builtUpSequence = formatSequence(changeData.built_up);
  const vegSequence = formatSequence(changeData.vegetation);
  const waterSequence = formatSequence(changeData.water);
  const bareLandSequence = changeData.bare_land ? formatSequence(changeData.bare_land) : null;

  // Differences for net tags
  const builtUpDiff = detail?.differences?.built_up ?? (
    (changeData.built_up?.[2]?.value ?? 0) - (changeData.built_up?.[0]?.value ?? 0)
  );
  const vegDiff = detail?.differences?.vegetation ?? (
    (changeData.vegetation?.[2]?.value ?? 0) - (changeData.vegetation?.[0]?.value ?? 0)
  );
  const waterDiff = detail?.differences?.water ?? (
    (changeData.water?.[2]?.value ?? 0) - (changeData.water?.[0]?.value ?? 0)
  );

  return (
    <div className="change-explorer-page">
      <div className="change-explorer-container">
        {/* Navigation Breadcrumb */}
        <div className="why-flagged-nav">
          <button
            type="button"
            className="back-link-btn"
            onClick={() => navigate(`/hotspot/${gridId}`)}
          >
            &larr; Back to Why Flagged ({gridId})
          </button>
          <button type="button" className="back-link-btn" onClick={() => navigate('/ranking')}>
            Hotspot ranking
          </button>
          <button type="button" className="back-link-btn" onClick={() => navigate('/')}>
            Overview map
          </button>
        </div>

        {/* Page Header */}
        <header className="change-explorer-header">
          <div className="header-badge-row">
            <span className="why-flagged-grid-id">{gridId}</span>
            <span
              className={`badge ${
                priorityLevel === 'HIGH'
                  ? 'badge-high'
                  : priorityLevel === 'MEDIUM'
                  ? 'badge-medium'
                  : 'badge-normal'
              }`}
            >
              <span
                className={`status-dot-sm ${priorityLevel === 'HIGH' ? 'bg-red' : 'bg-amber'}`}
                aria-hidden="true"
              />
              {priorityLevel} PRIORITY ({detail?.priority_score ?? 87} / 100)
            </span>
          </div>
          <h1 className="change-explorer-title">Change Explorer</h1>
          <p className="change-explorer-subtitle">
            Multi-temporal land cover trajectory across monitoring epochs (2020 &bull; 2023 &bull; 2026).
            Plain-language municipal transition evidence.
          </p>
        </header>

        {/* 1. Transition Panels for Built-up, Vegetation, Water */}
        <section className="change-panels-section" aria-label="Land cover transition panels">
          <div className="change-panels-grid">
            {/* Built-up Panel */}
            <div className="change-panel-card panel-built-up">
              <div className="panel-header">
                <div className="panel-title-group">
                  <span className="panel-indicator indicator-built-up" aria-hidden="true" />
                  <h2 className="panel-title">Built-up</h2>
                </div>
                <span className="panel-net-badge badge-expansion">
                  {builtUpDiff >= 0 ? `+${Math.round(builtUpDiff)}` : Math.round(builtUpDiff)} points
                </span>
              </div>

              {/* Value sequence "31% -> 38% -> 47%" */}
              <div className="panel-sequence-display">
                <span className="sequence-label">Value sequence:</span>
                <span className="sequence-value">{builtUpSequence}</span>
              </div>

              {/* Small plain SVG bar or line chart */}
              <div className="panel-chart-container">
                <MetricSvgChart items={changeData.built_up} color="#4338ca" />
              </div>

              <p className="panel-caption">
                Persistent conversion of natural surfaces to impervious urban built environment.
              </p>
            </div>

            {/* Vegetation Panel */}
            <div className="change-panel-card panel-vegetation">
              <div className="panel-header">
                <div className="panel-title-group">
                  <span className="panel-indicator indicator-vegetation" aria-hidden="true" />
                  <h2 className="panel-title">Vegetation</h2>
                </div>
                <span className="panel-net-badge badge-loss">
                  {vegDiff >= 0 ? `+${Math.round(vegDiff)}` : Math.round(vegDiff)} points
                </span>
              </div>

              {/* Value sequence "42% -> 37% -> 31%" */}
              <div className="panel-sequence-display">
                <span className="sequence-label">Value sequence:</span>
                <span className="sequence-value">{vegSequence}</span>
              </div>

              {/* Small plain SVG bar or line chart */}
              <div className="panel-chart-container">
                <MetricSvgChart items={changeData.vegetation} color="#15803d" />
              </div>

              <p className="panel-caption">
                Continuous decrease in vegetative canopy deviating from regional seasonal baselines.
              </p>
            </div>

            {/* Water Panel */}
            <div className="change-panel-card panel-water">
              <div className="panel-header">
                <div className="panel-title-group">
                  <span className="panel-indicator indicator-water" aria-hidden="true" />
                  <h2 className="panel-title">Water</h2>
                </div>
                <span className="panel-net-badge badge-water">
                  {waterDiff >= 0 ? `+${Math.round(waterDiff)}` : Math.round(waterDiff)} points
                </span>
              </div>

              {/* Value sequence "8% -> 6% -> 5%" */}
              <div className="panel-sequence-display">
                <span className="sequence-label">Value sequence:</span>
                <span className="sequence-value">{waterSequence}</span>
              </div>

              {/* Small plain SVG bar or line chart */}
              <div className="panel-chart-container">
                <MetricSvgChart items={changeData.water} color="#0284c7" />
              </div>

              <p className="panel-caption">
                Shrinkage or alteration of monitored open surface water bodies and catchment channels.
              </p>
            </div>

            {/* Optional Bare Land Panel if present */}
            {changeData.bare_land && (
              <div className="change-panel-card panel-bare-land">
                <div className="panel-header">
                  <div className="panel-title-group">
                    <span className="panel-indicator indicator-bare-land" aria-hidden="true" />
                    <h2 className="panel-title">Bare land</h2>
                  </div>
                  <span className="panel-net-badge badge-neutral">
                    {Math.round(
                      (changeData.bare_land[2]?.value ?? 0) - (changeData.bare_land[0]?.value ?? 0)
                    )}{' '}
                    points
                  </span>
                </div>

                <div className="panel-sequence-display">
                  <span className="sequence-label">Value sequence:</span>
                  <span className="sequence-value">{bareLandSequence}</span>
                </div>

                <div className="panel-chart-container">
                  <MetricSvgChart items={changeData.bare_land} color="#b45309" />
                </div>

                <p className="panel-caption">
                  Transition of open plots and vacant land parcels awaiting construction.
                </p>
              </div>
            )}
          </div>
        </section>

        {/* 2. Mini Map Centred on the Cell */}
        <section className="change-mini-map-section" aria-label="Spatial footprint mini map">
          <div className="mini-map-card">
            <div className="mini-map-header">
              <div className="mini-map-title-group">
                <h2 className="mini-map-title">Spatial Location & Grid Footprint</h2>
                <span className="mini-map-subtitle">
                  {detail?.ward_name || 'Hyderabad Growth Corridor'} &bull; Monitored cell (~500 m)
                </span>
              </div>
              <div className="mini-map-coords-badge">
                {detail?.lat ? `${detail.lat.toFixed(4)}° N, ${detail.lng.toFixed(4)}° E` : 'Hyderabad'}
              </div>
            </div>

            <div className="mini-map-viewport" style={{ height: '280px', width: '100%', position: 'relative' }}>
              <MapContainer
                center={mapCenter}
                zoom={14}
                scrollWheelZoom={false}
                style={{ height: '100%', width: '100%' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <MapRecenter center={mapCenter} />

                {polygonPositions ? (
                  <Polygon
                    positions={polygonPositions}
                    pathOptions={{
                      color: mapColor,
                      weight: 2.5,
                      fillColor: mapColor,
                      fillOpacity: 0.55
                    }}
                  />
                ) : (
                  <CircleMarker
                    center={mapCenter}
                    radius={14}
                    pathOptions={{
                      color: mapColor,
                      weight: 2,
                      fillColor: mapColor,
                      fillOpacity: 0.6
                    }}
                  />
                )}
              </MapContainer>
            </div>
          </div>
        </section>

        {/* 3. Before/After Imagery Side by Side with Year Selector */}
        <section className="change-imagery-section" aria-label="Before and after temporal imagery">
          <div className="imagery-section-header">
            <div>
              <h2 className="imagery-section-title">Before / After Verification Imagery</h2>
              <p className="imagery-section-subtitle">
                Compare multi-temporal observation tiles side-by-side using the year selectors below.
              </p>
            </div>
          </div>

          <div className="imagery-comparison-grid">
            {/* Before Panel */}
            <div className="imagery-card-frame">
              <div className="imagery-frame-header">
                <div className="frame-heading-group">
                  <span className="frame-type-badge">BEFORE</span>
                  <span className="frame-year-title">Observation: {beforeYear}</span>
                </div>

                {/* Year Selector (2020, 2023, 2026) */}
                <div className="year-selector-tabs" role="group" aria-label="Select Before Year">
                  {[2020, 2023, 2026].map((yr) => (
                    <button
                      key={`before-${yr}`}
                      type="button"
                      className={`year-tab-btn ${beforeYear === yr ? 'active' : ''}`}
                      onClick={() => setBeforeYear(yr)}
                    >
                      {yr}
                    </button>
                  ))}
                </div>
              </div>

              {/* Image View or Missing Notice */}
              <div className="imagery-canvas-wrapper">
                {isImageAvailable(beforeYear) ? (
                  <div className="imagery-display-container">
                    {/* Visible Mock imagery tag */}
                    <span className="mock-imagery-tag">Mock imagery</span>
                    {/* Year Label */}
                    <span className="imagery-year-badge">{beforeYear}</span>
                    <img
                      src={`/images/${gridId}/${beforeYear}.svg`}
                      alt={`Satellite observation tile for ${gridId} (${beforeYear})`}
                      className="temporal-observation-img"
                      onError={() => handleImageError(beforeYear)}
                    />
                  </div>
                ) : (
                  <div className="imagery-missing-notice">
                    <div className="missing-icon" aria-hidden="true">&#9888;</div>
                    <p className="missing-title">Imagery not available for this location.</p>
                    <p className="missing-desc">
                      Observation tiles are available for top prioritized cells. Metric trajectory above remains active.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* After Panel */}
            <div className="imagery-card-frame">
              <div className="imagery-frame-header">
                <div className="frame-heading-group">
                  <span className="frame-type-badge badge-after">AFTER</span>
                  <span className="frame-year-title">Observation: {afterYear}</span>
                </div>

                {/* Year Selector (2020, 2023, 2026) */}
                <div className="year-selector-tabs" role="group" aria-label="Select After Year">
                  {[2020, 2023, 2026].map((yr) => (
                    <button
                      key={`after-${yr}`}
                      type="button"
                      className={`year-tab-btn ${afterYear === yr ? 'active' : ''}`}
                      onClick={() => setAfterYear(yr)}
                    >
                      {yr}
                    </button>
                  ))}
                </div>
              </div>

              {/* Image View or Missing Notice */}
              <div className="imagery-canvas-wrapper">
                {isImageAvailable(afterYear) ? (
                  <div className="imagery-display-container">
                    {/* Visible Mock imagery tag */}
                    <span className="mock-imagery-tag">Mock imagery</span>
                    {/* Year Label */}
                    <span className="imagery-year-badge">{afterYear}</span>
                    <img
                      src={`/images/${gridId}/${afterYear}.svg`}
                      alt={`Satellite observation tile for ${gridId} (${afterYear})`}
                      className="temporal-observation-img"
                      onError={() => handleImageError(afterYear)}
                    />
                  </div>
                ) : (
                  <div className="imagery-missing-notice">
                    <div className="missing-icon" aria-hidden="true">&#9888;</div>
                    <p className="missing-title">Imagery not available for this location.</p>
                    <p className="missing-desc">
                      Observation tiles are available for top prioritized cells. Metric trajectory above remains active.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
