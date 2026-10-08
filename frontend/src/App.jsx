import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { fetchOverview, fetchHotspots, fetchHealth } from './api/client';
import DevelopmentDataBanner from './components/DevelopmentDataBanner';
import Header from './components/Header';
import CityOverviewPage from './components/CityOverviewPage';
import HotspotRankingPage from './components/HotspotRankingPage';
import HotspotDetailView from './components/HotspotDetailView';

export default function App() {
  const [overview, setOverview] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [selectedCellId, setSelectedCellId] = useState(null);
  const [healthInfo, setHealthInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoading(true);
        setError(null);

        const [healthRes, overviewRes, hotspotsRes] = await Promise.all([
          fetchHealth().catch(() => null),
          fetchOverview().catch(() => null),
          fetchHotspots().catch(() => [])
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
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div className="skeleton-spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ fontWeight: 600, fontSize: '15px', color: 'var(--text-primary)' }}>
          Loading UrbanPulse Decision-Support System...
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
            Unable to connect to UrbanPulse API at <code>http://localhost:5001</code>.
          </p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Error: {error}
          </p>
          <div style={{ marginTop: '16px' }}>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Please verify the backend server is running:
            </p>
            <pre style={{ backgroundColor: '#ffffff', padding: '8px', borderRadius: '4px', marginTop: '6px', fontSize: '11px', border: '1px solid var(--border-light)' }}>
              cd backend && npm run dev
            </pre>
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
      <Header overview={overview} isConnected={Boolean(healthInfo)} />

      {/* Main Routed View */}
      <main style={{ minHeight: 'calc(100vh - 120px)' }}>
        <Routes>
          {/* City Overview View (Map, Summary Strip, Mandatory Sentence) */}
          <Route
            path="/"
            element={<CityOverviewPage overview={overview} />}
          />
          <Route
            path="/overview"
            element={<CityOverviewPage overview={overview} />}
          />

          {/* Hotspot Ranking View (Second Nav Page) */}
          <Route
            path="/ranking"
            element={<HotspotRankingPage />}
          />
          <Route
            path="/hotspots"
            element={<Navigate to="/ranking" replace />}
          />

          {/* Hotspot Specific Detail Dossier */}
          <Route
            path="/hotspot/:gridId"
            element={<HotspotDetailView />}
          />
          <Route
            path="/hotspots/:gridId"
            element={<HotspotDetailView />}
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
