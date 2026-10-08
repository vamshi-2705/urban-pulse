/**
 * UrbanPulse - Express API Server
 *
 * Decision-support API for municipal authorities.
 * Strictly adheres to project rules:
 * - Selectable persistence via DATA_PROVIDER (mock, file, postgres)
 * - In-memory path preserved and completely decoupled from external DBs
 * - Never calculates or recalculates priority or anomaly scores
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { getProvider, getProviderType, verifyActiveProvider } from './providers/index.js';
import apiRoutes from './routes/api.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5001;

// Provider selection
const provider = getProvider();
const providerType = getProviderType();

// Middlewares
app.use(cors());
app.use(express.json());

// Serve placeholder imagery from data/images (both /images and /data/images)
app.use('/images', express.static(path.resolve(__dirname, '../../data/images')));
app.use('/data/images', express.static(path.resolve(__dirname, '../../data/images')));

// Serve real evidence assets and API artifacts
const EVIDENCE_DIR = path.resolve(__dirname, '../../data/outputs/evidence');
const API_DIR = path.resolve(__dirname, '../../data/outputs/api');
app.use('/data/outputs/evidence', express.static(EVIDENCE_DIR));
app.use('/evidence', express.static(EVIDENCE_DIR));
app.use('/data/outputs/api', express.static(API_DIR));

// Fallback image resolver: if an image request arrives for /images/:gridId/:year.svg or .png,
// resolve to real Sentinel-2 satellite observation image when available
app.get('/images/:gridId/:year.:ext', (req, res, next) => {
  const { gridId, year } = req.params;
  const cleanId = String(gridId).toUpperCase();
  const yr = String(year);

  let candidatePath = null;
  if (yr === '2020') {
    candidatePath = path.join(EVIDENCE_DIR, '2020_2026', cleanId, 'before_rgb.png');
    if (!fs.existsSync(candidatePath)) {
      candidatePath = path.join(EVIDENCE_DIR, '2020_2023', cleanId, 'before_rgb.png');
    }
  } else if (yr === '2023') {
    candidatePath = path.join(EVIDENCE_DIR, '2020_2023', cleanId, 'after_rgb.png');
    if (!fs.existsSync(candidatePath)) {
      candidatePath = path.join(EVIDENCE_DIR, '2023_2026', cleanId, 'before_rgb.png');
    }
  } else if (yr === '2026') {
    candidatePath = path.join(EVIDENCE_DIR, '2020_2026', cleanId, 'after_rgb.png');
    if (!fs.existsSync(candidatePath)) {
      candidatePath = path.join(EVIDENCE_DIR, '2023_2026', cleanId, 'after_rgb.png');
    }
  }

  if (candidatePath && fs.existsSync(candidatePath)) {
    return res.sendFile(candidatePath);
  }
  next();
});

// Mount modular REST routes (/api/statistics, /api/areas, /api/hotspots/:gridId, /api/change/:gridId, /api/evidence/:gridId)
app.use('/api', apiRoutes);

// Request logging middleware
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`[API] ${req.method} ${req.originalUrl} - ${res.statusCode} (${duration}ms)`);
  });
  next();
});

// Health check
app.get('/api/health', async (req, res) => {
  try {
    const isMock = await provider.isMockActive();
    res.json({
      status: 'ok',
      service: 'urban-pulse-backend',
      version: '1.0.0',
      mode: providerType === 'postgres' ? 'postgres' : (providerType === 'file' ? 'file' : (providerType === 'real' ? 'real' : 'development-mock')),
      isMock,
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    res.status(500).json({ status: 'error', message: err.message });
  }
});

// City / Region Overview
app.get('/api/overview', async (req, res) => {
  try {
    const overview = await provider.getOverview(req.query.period);
    res.json(overview);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve region overview', details: error.message });
  }
});

// Pipeline Architecture & Chain Definition
app.get('/api/pipeline', async (req, res) => {
  try {
    const pipeline = await provider.getPipeline();
    res.json(pipeline);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve pipeline metadata', details: error.message });
  }
});

// Full Investigation List (Standard Member 1 contract)
app.get('/api/investigation-list', async (req, res) => {
  try {
    const list = await provider.getInvestigationList(req.query.period);
    res.json(list);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve investigation list', details: error.message });
  }
});

// Monitored Grid Cells
app.get('/api/grid-cells', async (req, res) => {
  try {
    const cells = await provider.getGridCells({
      priorityLevel: req.query.priorityLevel,
      anomalyStatus: req.query.anomalyStatus,
      period: req.query.period
    });
    res.json(cells);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve grid cells', details: error.message });
  }
});

// Ranked Hotspots / Prioritized Investigation List
app.get('/api/hotspots', async (req, res) => {
  try {
    const hotspots = await provider.getHotspots({
      priorityLevel: req.query.priorityLevel,
      category: req.query.category,
      zone: req.query.zone,
      period: req.query.period,
      limit: req.query.limit
    });
    res.json(hotspots);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve hotspots', details: error.message });
  }
});

// Single Hotspot
app.get('/api/hotspots/:id', async (req, res) => {
  try {
    const hotspot = await provider.getHotspotById(req.params.id, req.query.period);
    if (!hotspot) {
      return res.status(404).json({ error: `Hotspot with ID '${req.params.id}' not found` });
    }
    res.json(hotspot);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve hotspot', details: error.message });
  }
});

// Full Evidence Dossier for a Hotspot
app.get('/api/hotspots/:id/evidence', async (req, res) => {
  try {
    const evidence = await provider.getEvidence(req.params.id, req.query.period);
    if (!evidence) {
      return res.status(404).json({ error: `Evidence dossier for '${req.params.id}' not found` });
    }
    res.json(evidence);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve evidence dossier', details: error.message });
  }
});

// Global 404 handler
app.use('/api', async (req, res) => {
  let meta = null;
  try {
    const overview = await provider.getOverview();
    meta = overview?.meta;
  } catch {
    // fallback
  }

  res.status(404).json({
    meta: meta || {
      source: providerType,
      is_mock: providerType !== 'postgres',
      warning: "DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo."
    },
    error: 'Not found',
    message: `Endpoint '${req.originalUrl}' not found`
  });
});

// Single-URL Production Deployment: Serve frontend build and SPA fallback
const FRONTEND_DIST = path.resolve(__dirname, '../../frontend/dist');
if (fs.existsSync(FRONTEND_DIST)) {
  console.log(`[UrbanPulse] Serving frontend distribution bundle from ${FRONTEND_DIST}`);
  app.use(express.static(FRONTEND_DIST));

  // SPA fallback for all remaining client routes (e.g. /ranking, /hotspot/:gridId)
  app.get('*', (req, res, next) => {
    if (req.path.startsWith('/api') || req.path.startsWith('/images') || req.path.startsWith('/data/images')) {
      return next();
    }
    res.sendFile(path.join(FRONTEND_DIST, 'index.html'));
  });
}

// Start listening after provider verification
async function startServer() {
  // If PostgreSQL persistence selected, verify DB connectivity
  if (providerType === 'postgres') {
    try {
      console.log('[UrbanPulse] Verifying PostgreSQL connection...');
      await verifyActiveProvider();
      console.log('[UrbanPulse] PostgreSQL connection established successfully.');
    } catch (err) {
      console.error(`\n[UrbanPulse Server FATAL] Cannot start server with DATA_PROVIDER=postgres:`);
      console.error(err.message);
      console.error('To run with in-memory mock data instead, unset DATA_PROVIDER or set DATA_PROVIDER=mock.\n');
      process.exit(1);
    }
  }

  app.listen(PORT, () => {
    console.log(`=======================================================`);
    console.log(` UrbanPulse Backend API running on port ${PORT}`);
    console.log(` Active Provider: [${providerType.toUpperCase()}]`);
    console.log(` Health check:    http://localhost:${PORT}/api/health`);
    console.log(` Overview:        http://localhost:${PORT}/api/overview`);
    console.log(` Hotspots:        http://localhost:${PORT}/api/hotspots`);
    console.log(`=======================================================`);
  });
}

startServer();

export default app;
