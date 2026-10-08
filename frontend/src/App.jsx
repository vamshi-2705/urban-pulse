import React, { useState, useEffect } from 'react';
import { fetchOverview, fetchPipeline, fetchHotspots, fetchHealth, fetchGridCells } from './api/client';
import DevelopmentDataBanner from './components/DevelopmentDataBanner';
import Header from './components/Header';
import PipelineBreadcrumb from './components/PipelineBreadcrumb';
import CityOverviewBar from './components/CityOverviewBar';
import MapView from './components/MapView';
import Phase1Dashboard from './components/Phase1Dashboard';

export default function App() {
  const [overview, setOverview] = useState(null);
  const [pipeline, setPipeline] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [cells, setCells] = useState([]);
  const [selectedCellId, setSelectedCellId] = useState(null);
  const [healthInfo, setHealthInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadInitialData() {
      try {
        setLoading(true);
        setError(null);

        const [healthRes, overviewRes, pipelineRes, hotspotsRes, cellsRes] = await Promise.all([
          fetchHealth(),
          fetchOverview(),
          fetchPipeline(),
          fetchHotspots(),
          fetchGridCells()
        ]);

        setHealthInfo(healthRes);
        setOverview(overviewRes);
        setPipeline(pipelineRes);
        setHotspots(hotspotsRes);
        setCells(cellsRes);

        if (hotspotsRes.length > 0) {
          setSelectedCellId(hotspotsRes[0].id || hotspotsRes[0].grid_id);
        } else if (cellsRes.length > 0) {
          setSelectedCellId(cellsRes[0].grid_id || cellsRes[0].cellId);
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
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <p style={{ fontWeight: 600 }}>Loading UrbanPulse decision-support system...</p>
        <p style={{ fontSize: '12px', marginTop: '6px' }}>Connecting to backend API & mock provider...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px', maxWidth: '600px', margin: '40px auto' }}>
        <div style={{ padding: '20px', backgroundColor: 'var(--status-high-bg)', border: '1px solid var(--status-high-border)', borderRadius: 'var(--radius-md)' }}>
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
            <pre style={{ backgroundColor: '#ffffff', padding: '8px', borderRadius: '4px', marginTop: '6px', fontSize: '11px' }}>
              cd backend && npm run dev
            </pre>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Rule 3: Development data banner active while mock data is served */}
      <DevelopmentDataBanner
        isMock={overview?.isMock || healthInfo?.isMock}
        dataSource={overview?.dataSource}
        legalNotice={overview?.legalNotice}
      />

      <Header overview={overview} isConnected={Boolean(healthInfo)} />

      <PipelineBreadcrumb pipeline={pipeline} />

      <CityOverviewBar overview={overview} />

      <main style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Phase 2: Interactive Leaflet Map View */}
        <MapView
          cells={cells}
          selectedCellId={selectedCellId}
          onSelectCell={setSelectedCellId}
          overview={overview}
        />
      </main>

      <Phase1Dashboard
        hotspots={hotspots}
        healthInfo={healthInfo}
        overview={overview}
        selectedHotspotId={selectedCellId}
        onSelectHotspot={setSelectedCellId}
      />
    </>
  );
}
