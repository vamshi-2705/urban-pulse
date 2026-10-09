import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { fetchOverview, fetchHotspots, fetchHealth, preloadAllData } from './api/client';
import DevelopmentDataBanner from './components/DevelopmentDataBanner';
import Header from './components/Header';
import CityOverviewPage from './components/CityOverviewPage';
import HotspotRankingPage from './components/HotspotRankingPage';
import HotspotDetailView from './components/HotspotDetailView';
import ChangeExplorerView from './components/ChangeExplorerView';
import EvidenceView from './components/EvidenceView';

export default function App() {
  const navigate = useNavigate();
  const [activePeriod, setActivePeriod] = useState('2020_2026');
  const [overview, setOverview] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [selectedCellId, setSelectedCellId] = useState(null);
  const [isGuidedOpen, setIsGuidedOpen] = useState(false);
  const [healthInfo, setHealthInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoading(true);
        setError(null);

        // Preload demo flow data in background across all periods
        preloadAllData().catch((err) => console.warn('[UrbanPulse Preload]', err));

        const [healthRes, overviewRes, hotspotsRes] = await Promise.all([
          fetchHealth().catch(() => null),
          fetchOverview(activePeriod).catch(() => null),
          fetchHotspots({ period: activePeriod }).catch(() => [])
        ]);

        setHealthInfo(healthRes);
        setOverview(overviewRes);
        setHotspots(hotspotsRes || []);

        if (hotspotsRes && hotspotsRes.length > 0) {
          setSelectedCellId(hotspotsRes[0].id || hotspotsRes[0].grid_id);
        }
      } catch (err) {
        console.error('Failed to load initial data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadInitialData();
  }, [retryTrigger]);

  if (loading) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ fontWeight: 600, fontSize: '15px', color: 'var(--text-primary)' }}>
          Loading URBAN IQ Decision-Support System...
        </p>
        <p style={{ fontSize: '12px', marginTop: '6px' }}>Connecting to municipal intelligence provider...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px 20px', maxWidth: '600px', margin: '40px auto' }}>
        <div style={{ padding: '24px', backgroundColor: 'var(--status-high-bg)', border: '1px solid var(--status-high-border)', borderRadius: 'var(--radius-md)' }}>
          <h2 style={{ color: 'var(--status-high)', fontSize: '16px', marginBottom: '8px' }}>Backend connection error</h2>
          <p style={{ fontSize: '13px', color: 'var(--text-primary)', marginBottom: '12px' }}>
            Unable to connect to URBAN IQ API at <code>http://localhost:5001</code>.
          </p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Error: {error}
          </p>
          <div style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setRetryTrigger((prev) => prev + 1)}
            >
              Retry connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Rule 3: Development data banner active while mock data is served */}
      <DevelopmentDataBanner
        isMock={overview?.isMock || healthInfo?.isMock}
        dataSource={overview?.dataSource}
        legalNotice={overview?.legalNotice}
      />

      {/* Top Header with Brand & Navigation (Overview / Hotspot ranking) */}
      <Header
        overview={overview}
        hotspots={hotspots}
        activePeriod={activePeriod}
        isConnected={Boolean(healthInfo)}
        onSelectHotspot={setSelectedCellId}
        onStartGuidedTour={() => {
          setIsGuidedOpen(true);
          navigate('/');
        }}
      />

      {/* Main Routed View */}
      <main className="app-main-viewport">
        <Routes>
          {/* City Overview View (Map, Summary Strip, Mandatory Sentence) */}
          <Route
            path="/"
            element={
              <CityOverviewPage
                overview={overview}
                selectedGridId={selectedCellId}
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
                onSelectHotspot={setSelectedCellId}
                isGuidedOpen={isGuidedOpen}
                onToggleGuidedTour={setIsGuidedOpen}
              />
            }
          />
          <Route
            path="/overview"
            element={
              <CityOverviewPage
                overview={overview}
                selectedGridId={selectedCellId}
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
                onSelectHotspot={setSelectedCellId}
                isGuidedOpen={isGuidedOpen}
                onToggleGuidedTour={setIsGuidedOpen}
              />
            }
          />

          {/* Hotspot Ranking View (Second Nav Page) */}
          <Route
            path="/ranking"
            element={
              <HotspotRankingPage
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />
          <Route
            path="/hotspots"
            element={<Navigate to="/ranking" replace />}
          />

          {/* Hotspot Specific Detail Dossier */}
          <Route
            path="/hotspot/:gridId"
            element={
              <HotspotDetailView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />
          <Route
            path="/hotspots/:gridId"
            element={
              <HotspotDetailView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />

          {/* Change Explorer */}
          <Route
            path="/hotspot/:gridId/change"
            element={
              <ChangeExplorerView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />
          <Route
            path="/hotspots/:gridId/change"
            element={
              <ChangeExplorerView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />

          {/* Evidence View */}
          <Route
            path="/hotspot/:gridId/evidence"
            element={
              <EvidenceView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />
          <Route
            path="/hotspots/:gridId/evidence"
            element={
              <EvidenceView
                activePeriod={activePeriod}
                onSelectPeriod={setActivePeriod}
              />
            }
          />

          {/* Fallback to Overview */}
          <Route
            path="*"
            element={<Navigate to="/" replace />}
          />
        </Routes>
      </main>
    </div>
  );
}
