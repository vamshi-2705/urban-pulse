import React, { useState, useEffect } from 'react';
import { fetchStatistics, fetchAreas, fetchPipeline } from '../api/client';
import PipelineBreadcrumb from './PipelineBreadcrumb';
import Breadcrumbs from './Breadcrumbs';
import SummaryStrip from './SummaryStrip';
import CityOverviewMap from './CityOverviewMap';

export default function CityOverviewPage({ overview }) {
  const [statistics, setStatistics] = useState(null);
  const [areas, setAreas] = useState([]);
  const [pipeline, setPipeline] = useState(null);
  const [selectedGridId, setSelectedGridId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [retryTrigger, setRetryTrigger] = useState(0);

  useEffect(() => {
    async function loadOverviewData() {
      try {
        setLoading(true);
        setError(null);

        const [statsRes, areasRes, pipelineRes] = await Promise.all([
          fetchStatistics(),
          fetchAreas(),
          fetchPipeline().catch(() => null)
        ]);

        setStatistics(statsRes);
        setAreas(areasRes?.areas || []);
        setPipeline(pipelineRes);

        // Preselect first high priority hotspot if available
        const firstHigh = (areasRes?.areas || []).find(
          (a) => (a.priority_level || '').toUpperCase() === 'HIGH'
        );
        if (firstHigh) {
          setSelectedGridId(firstHigh.grid_id);
        }
      } catch (err) {
        console.error('Failed to load City Overview data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadOverviewData();
  }, [retryTrigger]);

  const handleRetry = () => {
    setRetryTrigger((prev) => prev + 1);
  };

  return (
    <div className="city-overview-page" style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '0 20px 24px' }}>
      {/* Standardized Municipal Breadcrumbs */}
      <Breadcrumbs items={[{ label: 'Overview' }]} />

      {/* 7-Stage Pipeline Chain */}
      <PipelineBreadcrumb pipeline={pipeline} />

      {/* Slim Summary Strip from /api/statistics + Mandatory Sentence */}
      <SummaryStrip
        statistics={statistics}
        loading={loading}
        error={error}
      />

      {/* Geospatial Decision-Support Map */}
      <CityOverviewMap
        areas={areas}
        selectedGridId={selectedGridId}
        onSelectCell={setSelectedGridId}
        loading={loading}
        error={error}
        onRetry={handleRetry}
      />
    </div>
  );
}
