/**
 * UrbanPulse - API Routes
 *
 * Implements standard REST endpoints:
 * - GET /api/statistics
 * - GET /api/areas
 * - GET /api/hotspots/:gridId
 * - GET /api/change/:gridId
 * - GET /api/evidence/:gridId
 *
 * Requirements:
 * - 404 JSON for unknown ids.
 * - Every response includes the meta block (source, is_mock, warning).
 * - No calculation of priority or anomaly scores. Simple subtraction for metric differences.
 */

import { Router } from 'express';
import { dataService } from '../services/dataService.js';

const router = Router();

// GET /api/statistics
// Returns analyzed_cells, anomalous (MEDIUM+HIGH), high, medium, low counts.
router.get('/statistics', (req, res) => {
  try {
    const stats = dataService.getStatistics();
    res.json(stats);
  } catch (err) {
    res.status(500).json({
      meta: dataService.getMeta(),
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/areas
// Returns all cells with grid_id, lat, lng, geometry, priority_level, priority_score.
router.get('/areas', (req, res) => {
  try {
    const areas = dataService.getAreas();
    res.json(areas);
  } catch (err) {
    res.status(500).json({
      meta: dataService.getMeta(),
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/hotspots/:gridId
// Returns full record, score_breakdown, reasons, and per-metric 2020->2026 differences.
router.get('/hotspots/:gridId', (req, res) => {
  try {
    const { gridId } = req.params;
    const detail = dataService.getHotspotDetail(gridId);

    if (!detail) {
      return res.status(404).json({
        meta: dataService.getMeta(),
        error: 'Not found',
        message: `Hotspot with ID '${gridId}' not found`
      });
    }

    res.json(detail);
  } catch (err) {
    res.status(500).json({
      meta: dataService.getMeta(),
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/change/:gridId
// Returns built_up, vegetation, water (and bare_land) as [{year, value}] for 2020, 2023, 2026.
router.get('/change/:gridId', (req, res) => {
  try {
    const { gridId } = req.params;
    const change = dataService.getChange(gridId);

    if (!change) {
      return res.status(404).json({
        meta: dataService.getMeta(),
        error: 'Not found',
        message: `Change series for grid ID '${gridId}' not found`
      });
    }

    res.json(change);
  } catch (err) {
    res.status(500).json({
      meta: dataService.getMeta(),
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/evidence/:gridId
// Returns observed change, historical_change, local_percentile, temporal_anomaly,
// spatial_anomaly, persistence, priority_score, and image URLs that exist.
router.get('/evidence/:gridId', (req, res) => {
  try {
    const { gridId } = req.params;
    const evidence = dataService.getEvidence(gridId);

    if (!evidence) {
      return res.status(404).json({
        meta: dataService.getMeta(),
        error: 'Not found',
        message: `Evidence dossier for grid ID '${gridId}' not found`
      });
    }

    res.json(evidence);
  } catch (err) {
    res.status(500).json({
      meta: dataService.getMeta(),
      error: 'Internal server error',
      details: err.message
    });
  }
});

export default router;
