/**
 * UrbanPulse Frontend API Client
 *
 * Connects directly to backend endpoints.
 * Never calculates or overrides priority or anomaly data.
 */

const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchOverview() {
  const res = await fetch(`${API_BASE}/overview`);
  if (!res.ok) throw new Error(`Failed to fetch overview: ${res.statusText}`);
  return res.json();
}

export async function fetchPipeline() {
  const res = await fetch(`${API_BASE}/pipeline`);
  if (!res.ok) throw new Error(`Failed to fetch pipeline: ${res.statusText}`);
  return res.json();
}

export async function fetchHotspots(filters = {}) {
  const params = new URLSearchParams();
  if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
  if (filters.category) params.append('category', filters.category);
  if (filters.zone) params.append('zone', filters.zone);

  const url = `${API_BASE}/hotspots${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch hotspots: ${res.statusText}`);
  return res.json();
}

export async function fetchHotspotEvidence(hotspotId) {
  const res = await fetch(`${API_BASE}/hotspots/${hotspotId}/evidence`);
  if (!res.ok) throw new Error(`Failed to fetch evidence for ${hotspotId}: ${res.statusText}`);
  return res.json();
}

export async function fetchGridCells(filters = {}) {
  const params = new URLSearchParams();
  if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
  if (filters.anomalyStatus) params.append('anomalyStatus', filters.anomalyStatus);

  const url = `${API_BASE}/grid-cells${params.toString() ? `?${params.toString()}` : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch grid cells: ${res.statusText}`);
  return res.json();
}
