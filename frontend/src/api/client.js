/**
 * UrbanPulse Frontend API Client
 *
 * Connects directly to backend endpoints.
 * Never calculates or overrides priority or anomaly data.
 * Implements intelligent in-memory caching and startup preloading for slow network resilience.
 */

const API_BASE = '/api';

// In-memory request cache: URL -> Promise<data>
const apiCache = new Map();

/**
 * Cached fetch wrapper with error eviction and request deduplication
 */
export async function cachedFetch(url) {
  if (apiCache.has(url)) {
    return apiCache.get(url);
  }

  const fetchPromise = fetch(url)
    .then(async (res) => {
      if (!res.ok) {
        apiCache.delete(url);
        throw new Error(`Request failed (${res.status}): ${res.statusText}`);
      }
      return res.json();
    })
    .catch((err) => {
      apiCache.delete(url);
      throw err;
    });

  apiCache.set(url, fetchPromise);
  return fetchPromise;
}

export function clearCache(url) {
  if (url) {
    apiCache.delete(url);
  } else {
    apiCache.clear();
  }
}

/**
 * Preloads and caches intelligence data across the entire demo path at startup
 */
export async function preloadAllData() {
  const coreEndpoints = [
    `${API_BASE}/health`,
    `${API_BASE}/overview`,
    `${API_BASE}/pipeline`,
    `${API_BASE}/statistics`,
    `${API_BASE}/areas`,
    `${API_BASE}/hotspots`,
    `${API_BASE}/hotspots/HYD_1220`,
    `${API_BASE}/change/HYD_1220`,
    `${API_BASE}/evidence/HYD_1220`,
    `${API_BASE}/hotspots/HYD_0421`,
    `${API_BASE}/change/HYD_0421`,
    `${API_BASE}/evidence/HYD_0421`
  ];

  await Promise.allSettled(coreEndpoints.map((url) => cachedFetch(url)));
}

export async function fetchHealth() {
  return cachedFetch(`${API_BASE}/health`);
}

export async function fetchOverview() {
  return cachedFetch(`${API_BASE}/overview`);
}

export async function fetchPipeline() {
  return cachedFetch(`${API_BASE}/pipeline`);
}

export async function fetchStatistics() {
  return cachedFetch(`${API_BASE}/statistics`);
}

export async function fetchAreas() {
  return cachedFetch(`${API_BASE}/areas`);
}

export async function fetchHotspots(filters = {}) {
  const params = new URLSearchParams();
  if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
  if (filters.category) params.append('category', filters.category);
  if (filters.zone) params.append('zone', filters.zone);

  const url = `${API_BASE}/hotspots${params.toString() ? `?${params.toString()}` : ''}`;
  return cachedFetch(url);
}

export async function fetchHotspotDetail(gridId) {
  return cachedFetch(`${API_BASE}/hotspots/${gridId}`);
}

export async function fetchChange(gridId) {
  return cachedFetch(`${API_BASE}/change/${gridId}`);
}

export async function fetchEvidence(gridId) {
  return cachedFetch(`${API_BASE}/evidence/${gridId}`);
}

export async function fetchHotspotEvidence(hotspotId) {
  return cachedFetch(`${API_BASE}/hotspots/${hotspotId}/evidence`);
}

export async function fetchGridCells(filters = {}) {
  const params = new URLSearchParams();
  if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
  if (filters.anomalyStatus) params.append('anomalyStatus', filters.anomalyStatus);

  const url = `${API_BASE}/grid-cells${params.toString() ? `?${params.toString()}` : ''}`;
  return cachedFetch(url);
}
