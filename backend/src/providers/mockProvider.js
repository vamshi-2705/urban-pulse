/**
 * UrbanPulse - Mock Data Provider
 *
 * Serves preloaded development observations from data/mock.
 * Per project rules:
 * 1. Data is preloaded synchronously into memory at startup.
 * 2. NEVER calculates or adjusts anomaly scores, priority scores, or priority levels.
 * 3. Purely returns what the preloaded data contains.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Root path to data/mock
const MOCK_DATA_DIR = path.resolve(__dirname, '../../../data/mock');

function loadJsonFile(fileName) {
  const filePath = path.join(MOCK_DATA_DIR, fileName);
  try {
    const rawData = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(rawData);
  } catch (error) {
    console.error(`[MockProvider] Failed to load ${filePath}:`, error.message);
    throw error;
  }
}

// Preload datasets into memory at module load time for maximum reliability
const overviewData = loadJsonFile('overview.json');
const pipelineData = loadJsonFile('pipeline.json');
const hotspotsData = loadJsonFile('hotspots.json');
const evidenceData = loadJsonFile('evidence.json');
const cellsData = loadJsonFile('cells.json');

console.log(`[MockProvider] Successfully preloaded mock data:`);
console.log(` - Region: ${overviewData.regionName}`);
console.log(` - Monitored cells: ${cellsData.length}`);
console.log(` - Hotspots: ${hotspotsData.length}`);
console.log(` - Evidence dossiers: ${Object.keys(evidenceData).length}`);

export const mockProvider = {
  isMockActive() {
    return true;
  },

  getOverview() {
    return {
      ...overviewData,
      isMock: true,
      timestamp: new Date().toISOString()
    };
  },

  getPipeline() {
    return pipelineData;
  },

  getHotspots(filters = {}) {
    let result = [...hotspotsData];

    if (filters.priorityLevel) {
      result = result.filter(h => h.priorityLevel === filters.priorityLevel.toLowerCase());
    }

    if (filters.category) {
      result = result.filter(h => h.category === filters.category);
    }

    if (filters.zone) {
      result = result.filter(h => h.zone.toLowerCase() === filters.zone.toLowerCase());
    }

    // Sort by rank as recorded in the preloaded data
    return result.sort((a, b) => a.rank - b.rank);
  },

  getHotspotById(id) {
    const hotspot = hotspotsData.find(h => h.id === id || h.cellId === id);
    return hotspot || null;
  },

  getEvidence(hotspotId) {
    const evidence = evidenceData[hotspotId];
    if (!evidence) {
      // Check if mapped by cellId
      const targetHotspot = hotspotsData.find(h => h.cellId === hotspotId || h.id === hotspotId);
      if (targetHotspot && evidenceData[targetHotspot.id]) {
        return evidenceData[targetHotspot.id];
      }
      return null;
    }
    return evidence;
  },

  getGridCells(filters = {}) {
    let result = [...cellsData];

    if (filters.priorityLevel) {
      result = result.filter(c => c.priorityLevel === filters.priorityLevel.toLowerCase());
    }

    if (filters.anomalyStatus) {
      result = result.filter(c => c.anomalyStatus === filters.anomalyStatus.toLowerCase());
    }

    return result;
  }
};

export default mockProvider;
