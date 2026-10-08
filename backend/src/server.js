/**
 * UrbanPulse - Express API Server
 *
 * Decision-support API for municipal authorities.
 * Strictly adheres to project rules:
 * - Data served from preloaded memory via mockProvider.js
 * - Never calculates or recalculates priority or anomaly scores
 */

import path from 'path';
import { fileURLToPath } from 'url';
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { mockProvider } from './providers/mockProvider.js';
import apiRoutes from './routes/api.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 5001;

// Middlewares
app.use(cors());
app.use(express.json());

// Serve placeholder imagery from data/images (both /images and /data/images)
app.use('/images', express.static(path.resolve(__dirname, '../../data/images')));
app.use('/data/images', express.static(path.resolve(__dirname, '../../data/images')));

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
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'urban-pulse-backend',
    version: '1.0.0',
    mode: 'development-mock',
    isMock: mockProvider.isMockActive(),
    timestamp: new Date().toISOString()
  });
});

// City / Region Overview
app.get('/api/overview', (req, res) => {
  try {
    const overview = mockProvider.getOverview();
    res.json(overview);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve region overview', details: error.message });
  }
});

// Pipeline Architecture & Chain Definition
app.get('/api/pipeline', (req, res) => {
  try {
    const pipeline = mockProvider.getPipeline();
    res.json(pipeline);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve pipeline metadata', details: error.message });
  }
});

// Full Investigation List (Standard Member 1 contract)
app.get('/api/investigation-list', (req, res) => {
  try {
    const list = mockProvider.getInvestigationList();
    res.json(list);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve investigation list', details: error.message });
  }
});

// Monitored Grid Cells
app.get('/api/grid-cells', (req, res) => {
  try {
    const cells = mockProvider.getGridCells({
      priorityLevel: req.query.priorityLevel,
      anomalyStatus: req.query.anomalyStatus
    });
    res.json(cells);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve grid cells', details: error.message });
  }
});

// Ranked Hotspots / Prioritized Investigation List
app.get('/api/hotspots', (req, res) => {
  try {
    const hotspots = mockProvider.getHotspots({
      priorityLevel: req.query.priorityLevel,
      category: req.query.category,
      zone: req.query.zone
    });
    res.json(hotspots);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve hotspots', details: error.message });
  }
});

// Single Hotspot
app.get('/api/hotspots/:id', (req, res) => {
  try {
    const hotspot = mockProvider.getHotspotById(req.params.id);
    if (!hotspot) {
      return res.status(404).json({ error: `Hotspot with ID '${req.params.id}' not found` });
    }
    res.json(hotspot);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve hotspot', details: error.message });
  }
});

// Full Evidence Dossier for a Hotspot
app.get('/api/hotspots/:id/evidence', (req, res) => {
  try {
    const evidence = mockProvider.getEvidence(req.params.id);
    if (!evidence) {
      return res.status(404).json({ error: `Evidence dossier for '${req.params.id}' not found` });
    }
    res.json(evidence);
  } catch (error) {
    res.status(500).json({ error: 'Failed to retrieve evidence dossier', details: error.message });
  }
});

// Global 404 handler
app.use('/api', (req, res) => {
  res.status(404).json({
    meta: mockProvider.getOverview()?.meta || {
      source: "mock",
      is_mock: true,
      warning: "DEVELOPMENT DATA ONLY. Invented values for UI development. Not real satellite observations. Replace with Member 1 output before the demo."
    },
    error: 'Not found',
    message: `Endpoint '${req.originalUrl}' not found`
  });
});

// Start listening
app.listen(PORT, () => {
  console.log(`=======================================================`);
  console.log(` UrbanPulse Backend API running on port ${PORT}`);
  console.log(` Health check: http://localhost:${PORT}/api/health`);
  console.log(` Overview:     http://localhost:${PORT}/api/overview`);
  console.log(` Hotspots:     http://localhost:${PORT}/api/hotspots`);
  console.log(`=======================================================`);
});

export default app;
