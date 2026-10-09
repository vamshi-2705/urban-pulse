import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  fetchStatistics,
  fetchAreas,
  fetchHotspots,
  fetchHotspotDetail,
  fetchPipeline
} from '../api/client';
import CityOverviewMap from './CityOverviewMap';
import InvestigationPanel from './InvestigationPanel';
import IntelligenceBrief from './IntelligenceBrief';
import InvestigationQueue from './InvestigationQueue';
import TemporalBar from './TemporalBar';
import GuidedInvestigationOverlay from './GuidedInvestigationOverlay';

/**
 * CityOverviewPage — TrafficPulse-Inspired Geospatial Product Experience
 * Supports active analysis period switching across:
 * - 2020_2026 (default)
 * - 2020_2023
 * - 2023_2026
 * All data (statistics, areas, hotspots, selected dossier) update dynamically.
 */
export default function CityOverviewPage({
  selectedGridId: propSelectedId,
  onSelectHotspot: propOnSelect,
  activePeriod: propActivePeriod,
  onSelectPeriod: propOnSelectPeriod,
  isGuidedOpen: propIsGuidedOpen,
  onToggleGuidedTour: propOnToggleGuidedTour
}) {
  const [searchParams] = useSearchParams();
  const queryGuided = searchParams.get('guided') === 'true';

  const [internalPeriod, setInternalPeriod] = useState('2020_2026');
  const activePeriod = propActivePeriod || internalPeriod;

  const [statistics, setStatistics] = useState(null);
  const [areas, setAreas] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [pipeline, setPipeline] = useState(null);

  // Active state
  const [selectedGridId, setSelectedGridId] = useState(propSelectedId || 'HYD_1220');
  const [selectedHotspot, setSelectedHotspot] = useState(null);

  // Guided Investigation demonstration state
  const [internalGuidedOpen, setInternalGuidedOpen] = useState(queryGuided);
  const isGuidedOpen = propIsGuidedOpen !== undefined ? propIsGuidedOpen : internalGuidedOpen;
  const setIsGuidedOpen = propOnToggleGuidedTour || setInternalGuidedOpen;
  const [cameraTarget, setCameraTarget] = useState(null);
  const [guidedScene, setGuidedScene] = useState(null);

  // Full queue modal / overlay state
  const [isFullQueueOpen, setIsFullQueueOpen] = useState(false);

  const [loading, setLoading] = useState(true);
  const [periodSwitching, setPeriodSwitching] = useState(false);
  const [briefLoading, setBriefLoading] = useState(false);
  const [error, setError] = useState(null);
  const [retryTrigger, setRetryTrigger] = useState(0);

  // Sync external prop or target query parameter
  useEffect(() => {
    const queryTarget = searchParams.get('target');
    if (queryTarget && queryTarget !== selectedGridId) {
      setSelectedGridId(queryTarget);
      if (propOnSelectHotspot) {
        propOnSelectHotspot(queryTarget);
      }
    } else if (propSelectedId && propSelectedId !== selectedGridId) {
      setSelectedGridId(propSelectedId);
    }
  }, [searchParams, propSelectedId]);

  const handlePeriodChange = (newPeriod) => {
    setInternalPeriod(newPeriod);
    if (propOnSelectPeriod) {
      propOnSelectPeriod(newPeriod);
    }
  };

  // Load period-specific dataset whenever activePeriod or retryTrigger changes
  useEffect(() => {
    async function loadPeriodDataset() {
      try {
        setPeriodSwitching(true);
        setError(null);

        const [statsRes, areasRes, hotspotsRes, pipelineRes] = await Promise.all([
          fetchStatistics(activePeriod).catch(() => null),
          fetchAreas(activePeriod).catch(() => ({ areas: [] })),
          fetchHotspots({ period: activePeriod }).catch(() => []),
          fetchPipeline(activePeriod).catch(() => null)
        ]);

        const loadedAreas = areasRes?.areas || [];
        const loadedHotspots = Array.isArray(hotspotsRes)
          ? hotspotsRes
          : (hotspotsRes?.hotspots || []);

        setStatistics(statsRes);
        setAreas(loadedAreas);
        setHotspots(loadedHotspots);
        setPipeline(pipelineRes);

        // Keep current selected hotspot if present in this period, otherwise choose top
        const hasCurrent =
          loadedHotspots.some((h) => (h.grid_id || h.id) === selectedGridId) ||
          loadedAreas.some((a) => a.grid_id === selectedGridId);

        if (!hasCurrent && loadedHotspots.length > 0) {
          const nextTop = loadedHotspots[0].grid_id || loadedHotspots[0].id;
          setSelectedGridId(nextTop);
          if (propOnSelect) propOnSelect(nextTop);
        }
      } catch (err) {
        console.error(`Failed to load dataset for period ${activePeriod}:`, err);
        setError(err.message);
      } finally {
        setLoading(false);
        setPeriodSwitching(false);
      }
    }

    loadPeriodDataset();
  }, [activePeriod, retryTrigger]);

  // Load hotspot detail when selectedGridId or activePeriod changes
  useEffect(() => {
    if (!selectedGridId) return;

    let isMounted = true;
    setBriefLoading(true);

    fetchHotspotDetail(selectedGridId, activePeriod)
      .then((data) => {
        if (isMounted) {
          setSelectedHotspot(data);
        }
      })
      .catch((err) => {
        console.warn(`Could not load details for ${selectedGridId} (${activePeriod}):`, err);
        if (isMounted) {
          const fallback =
            hotspots.find((h) => (h.grid_id || h.id) === selectedGridId) ||
            areas.find((a) => a.grid_id === selectedGridId);
          setSelectedHotspot(fallback || null);
        }
      })
      .finally(() => {
        if (isMounted) setBriefLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedGridId, activePeriod, hotspots, areas]);

  const handleSelectHotspot = (gridId) => {
    setSelectedGridId(gridId);
    if (propOnSelect) {
      propOnSelect(gridId);
    }
  };

  const handleRetry = () => {
    setRetryTrigger((prev) => prev + 1);
  };

  return (
    <div className="traffic-product-layout">
      {/* 1. LEFT COMPACT FLOATING PANEL (INVESTIGATION TRIAGE) */}
      <aside className="layout-col-left">
        <InvestigationPanel
          statistics={statistics}
          hotspots={hotspots}
          selectedGridId={selectedGridId}
          onSelectHotspot={handleSelectHotspot}
          onOpenFullQueue={() => setIsFullQueueOpen(true)}
          onStartGuidedTour={() => setIsGuidedOpen(true)}
          loading={loading || periodSwitching}
          error={error}
        />
      </aside>

      {/* 2. CENTER HERO MAP (~60% DOMINANT SURFACE) */}
      <section className="layout-col-center">
        <div className="hero-map-container">
          <CityOverviewMap
            areas={areas}
            hotspots={hotspots}
            selectedGridId={selectedGridId}
            onSelectCell={handleSelectHotspot}
            cameraTarget={cameraTarget}
            guidedScene={guidedScene}
          />

          {/* Floating Map Button to Launch Guided Investigation */}
          {!isGuidedOpen && (
            <button
              type="button"
              className="map-floating-guided-trigger font-mono"
              onClick={() => setIsGuidedOpen(true)}
              title="Launch automated 7-scene Guided Investigation demonstration"
            >
              <span className="guided-trigger-pulse">&#9654;</span>
              <span>START GUIDED INVESTIGATION</span>
              <span className="guided-trigger-badge">7 SCENES</span>
            </button>
          )}

          {/* Floating Guided Investigation Demonstration Overlay */}
          <GuidedInvestigationOverlay
            isOpen={isGuidedOpen}
            onClose={() => {
              setIsGuidedOpen(false);
              setGuidedScene(null);
              setCameraTarget(null);
            }}
            statistics={statistics}
            hotspots={hotspots}
            activePeriod={activePeriod}
            onSelectPeriod={handlePeriodChange}
            selectedGridId={selectedGridId}
            onSelectHotspot={handleSelectHotspot}
            onCameraChange={(cam) => {
              setCameraTarget(cam);
              if (cam.scene) setGuidedScene(cam.scene);
            }}
          />

          {/* Floating Period Transition Indicator */}
          {periodSwitching && (
            <div className="map-period-switching-pill font-mono">
              <span className="skeleton-spinner" style={{ width: '10px', height: '10px' }} />
              <span>SYNCING ANALYSIS {activePeriod.replace('_', ' → ')}...</span>
            </div>
          )}

          {/* Floating Bottom Analysis Period Control */}
          <div className="map-bottom-controls-dock">
            <TemporalBar
              activePeriod={activePeriod}
              onSelectPeriod={handlePeriodChange}
            />
          </div>
        </div>
      </section>

      {/* 3. RIGHT COMPACT FLOATING PANEL (SELECTED LOCATION DOSSIER) */}
      <aside className="layout-col-right">
        <IntelligenceBrief
          hotspot={selectedHotspot}
          selectedGridId={selectedGridId}
          activePeriod={activePeriod}
          loading={briefLoading}
        />
      </aside>

      {/* OPTIONAL SLIDE-IN FULL INVESTIGATION QUEUE OVERLAY */}
      {isFullQueueOpen && (
        <div className="full-queue-modal-backdrop" onClick={() => setIsFullQueueOpen(false)}>
          <div className="full-queue-modal-content" onClick={(e) => e.stopPropagation()}>
            <InvestigationQueue
              statistics={statistics}
              hotspots={hotspots}
              selectedGridId={selectedGridId}
              onSelectHotspot={(id) => {
                handleSelectHotspot(id);
                setIsFullQueueOpen(false);
              }}
              loading={loading}
              error={error}
              onRetry={handleRetry}
              onClose={() => setIsFullQueueOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
