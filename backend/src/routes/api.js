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
router.get('/statistics', async (req, res) => {
  try {
    const stats = await dataService.getStatistics();
    res.json(stats);
  } catch (err) {
    const meta = await dataService.getMeta();
    res.status(500).json({
      meta,
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/areas
// Returns all cells with grid_id, lat, lng, geometry, priority_level, priority_score.
router.get('/areas', async (req, res) => {
  try {
    const areas = await dataService.getAreas();
    res.json(areas);
  } catch (err) {
    const meta = await dataService.getMeta();
    res.status(500).json({
      meta,
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/hotspots/:gridId
// Returns full record, score_breakdown, reasons, and per-metric 2020->2026 differences.
router.get('/hotspots/:gridId', async (req, res) => {
  try {
    const { gridId } = req.params;
    const detail = await dataService.getHotspotDetail(gridId);

    if (!detail) {
      const meta = await dataService.getMeta();
      return res.status(404).json({
        meta,
        error: 'Not found',
        message: `Hotspot with ID '${gridId}' not found`
      });
    }

    res.json(detail);
  } catch (err) {
    const meta = await dataService.getMeta();
    res.status(500).json({
      meta,
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/change/:gridId
// Returns built_up, vegetation, water (and bare_land) as [{year, value}] for 2020, 2023, 2026.
router.get('/change/:gridId', async (req, res) => {
  try {
    const { gridId } = req.params;
    const change = await dataService.getChange(gridId);

    if (!change) {
      const meta = await dataService.getMeta();
      return res.status(404).json({
        meta,
        error: 'Not found',
        message: `Change series for grid ID '${gridId}' not found`
      });
    }

    res.json(change);
  } catch (err) {
    const meta = await dataService.getMeta();
    res.status(500).json({
      meta,
      error: 'Internal server error',
      details: err.message
    });
  }
});

// GET /api/evidence/:gridId
// Returns observed change, historical_change, local_percentile, temporal_anomaly,
// spatial_anomaly, persistence, priority_score, and image URLs that exist.
router.get('/evidence/:gridId', async (req, res) => {
  try {
    const { gridId } = req.params;
    const evidence = await dataService.getEvidence(gridId);

    if (!evidence) {
      const meta = await dataService.getMeta();
      return res.status(404).json({
        meta,
        error: 'Not found',
        message: `Evidence dossier for grid ID '${gridId}' not found`
      });
    }

    res.json(evidence);
  } catch (err) {
    const meta = await dataService.getMeta();
    res.status(500).json({
      meta,
      error: 'Internal server error',
      details: err.message
    });
  }
});

export default router;
