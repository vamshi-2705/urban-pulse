/**
 * UrbanPulse Frontend API Client
 *
 * Connects directly to backend endpoints.
 * Supports period-aware queries for:
 * - 2020_2026 (default)
 * - 2020_2023
 * - 2023_2026
 * Implements intelligent in-memory caching and startup preloading for instant responsiveness.
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
 * Preloads and caches intelligence data across all 3 supported periods at startup
 */
export async function preloadAllData() {
  const periods = ['2020_2026', '2020_2023', '2023_2026'];
  const endpoints = [];

  endpoints.push(`${API_BASE}/health`);
  endpoints.push(`${API_BASE}/pipeline`);

  for (const p of periods) {
    endpoints.push(`${API_BASE}/overview?period=${p}`);
    endpoints.push(`${API_BASE}/statistics?period=${p}`);
    endpoints.push(`${API_BASE}/areas?period=${p}`);
    endpoints.push(`${API_BASE}/hotspots?period=${p}`);
    endpoints.push(`${API_BASE}/hotspots/HYD_1220?period=${p}`);
    endpoints.push(`${API_BASE}/change/HYD_1220?period=${p}`);
    endpoints.push(`${API_BASE}/evidence/HYD_1220?period=${p}`);
  }

  await Promise.allSettled(endpoints.map((url) => cachedFetch(url)));
}

export async function fetchHealth() {
  return cachedFetch(`${API_BASE}/health`);
}

export async function fetchPipeline(period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/pipeline${q}`);
}

export async function fetchOverview(period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/overview${q}`);
}

export async function fetchStatistics(period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/statistics${q}`);
}

export async function fetchAreas(period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/areas${q}`);
}

export async function fetchHotspots(filters = {}) {
  let period = typeof filters === 'string' ? filters : filters.period;
  const params = new URLSearchParams();
  if (period) params.append('period', period);
  if (typeof filters === 'object') {
    if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
    if (filters.category) params.append('category', filters.category);
    if (filters.zone) params.append('zone', filters.zone);
  }

  const url = `${API_BASE}/hotspots${params.toString() ? `?${params.toString()}` : ''}`;
  return cachedFetch(url);
}

export async function fetchHotspotDetail(gridId, period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/hotspots/${gridId}${q}`);
}

export async function fetchChange(gridId, period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/change/${gridId}${q}`);
}

export async function fetchEvidence(gridId, period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/evidence/${gridId}${q}`);
}

export async function fetchHotspotEvidence(hotspotId, period) {
  const q = period ? `?period=${encodeURIComponent(period)}` : '';
  return cachedFetch(`${API_BASE}/hotspots/${hotspotId}/evidence${q}`);
}

export async function fetchGridCells(filters = {}) {
  let period = typeof filters === 'string' ? filters : filters.period;
  const params = new URLSearchParams();
  if (period) params.append('period', period);
  if (typeof filters === 'object') {
    if (filters.priorityLevel) params.append('priorityLevel', filters.priorityLevel);
    if (filters.anomalyStatus) params.append('anomalyStatus', filters.anomalyStatus);
  }

  const url = `${API_BASE}/grid-cells${params.toString() ? `?${params.toString()}` : ''}`;
  return cachedFetch(url);
}
