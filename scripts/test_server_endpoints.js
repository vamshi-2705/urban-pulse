/**
 * UrbanPulse - Express Server Endpoint Verification Test
 */

import http from 'http';

process.env.DATA_PROVIDER = 'real';
process.env.PORT = '5002'; // Use dedicated port for test

import app from '../backend/src/server.js';

const server = app.listen(5002, async () => {
  console.log('Test server started on port 5002');

  async function getJson(endpoint) {
    return new Promise((resolve, reject) => {
      http.get(`http://localhost:5002${endpoint}`, (res) => {
        let body = '';
        res.on('data', chunk => (body += chunk));
        res.on('end', () => {
          try {
            resolve({ status: res.statusCode, data: JSON.parse(body) });
          } catch (e) {
            resolve({ status: res.statusCode, body });
          }
        });
      }).on('error', reject);
    });
  }

  try {
    // 1. /api/health
    const health = await getJson('/api/health');
    console.log('1. Health check status:', health.status, 'isMock:', health.data.isMock, 'mode:', health.data.mode);
    if (health.status !== 200 || health.data.isMock !== false || health.data.mode !== 'real') {
      throw new Error(`Health check failed: ${JSON.stringify(health)}`);
    }

    // 2. /api/overview
    const overview = await getJson('/api/overview');
    console.log('2. Overview status:', overview.status, 'monitoredCellsCount:', overview.data.monitoredCellsCount, 'isMock:', overview.data.isMock);
    if (overview.status !== 200 || overview.data.monitoredCellsCount !== 1462 || overview.data.isMock !== false) {
      throw new Error(`Overview check failed: ${JSON.stringify(overview)}`);
    }

    // 3. /api/statistics
    const stats = await getJson('/api/statistics');
    console.log('3. Statistics status:', stats.status, 'high:', stats.data.high, 'medium:', stats.data.medium);
    if (stats.status !== 200 || stats.data.high !== 27) {
      throw new Error(`Statistics check failed: ${JSON.stringify(stats)}`);
    }

    // 4. /api/areas
    const areas = await getJson('/api/areas');
    console.log('4. Areas status:', areas.status, 'count:', areas.data.areas?.length);
    if (areas.status !== 200 || areas.data.areas?.length !== 1462) {
      throw new Error(`Areas check failed: count = ${areas.data.areas?.length}`);
    }

    // 5. /api/hotspots
    const hotspots = await getJson('/api/hotspots');
    console.log('5. Hotspots status:', hotspots.status, 'count:', hotspots.data.length, 'Rank 1:', hotspots.data[0]?.grid_id);
    if (hotspots.status !== 200 || hotspots.data[0]?.grid_id !== 'HYD_1220') {
      throw new Error(`Hotspots check failed: rank 1 is not HYD_1220`);
    }

    // 6. /api/hotspots/HYD_1220
    const detail = await getJson('/api/hotspots/HYD_1220');
    console.log('6. Hotspot detail status:', detail.status, 'grid_id:', detail.data.grid_id, 'score:', detail.data.priority_score, 'level:', detail.data.priority_level);
    if (detail.status !== 200 || detail.data.grid_id !== 'HYD_1220' || detail.data.priority_score !== 82) {
      throw new Error(`Hotspot detail check failed`);
    }

    // 7. /api/change/HYD_1220
    const change = await getJson('/api/change/HYD_1220');
    console.log('7. Change series status:', change.status, 'years:', change.data.built_up?.map(d => d.year));
    if (change.status !== 200 || change.data.built_up?.length !== 3) {
      throw new Error(`Change series check failed`);
    }

    // 8. /api/evidence/HYD_1220
    const evidence = await getJson('/api/evidence/HYD_1220');
    console.log('8. Evidence status:', evidence.status, 'images:', evidence.data.images?.length);
    if (evidence.status !== 200 || !evidence.data.images?.length) {
      throw new Error(`Evidence check failed`);
    }

    console.log('\n========================================');
    console.log('ALL HTTP REST ENDPOINTS VERIFIED (PASS)');
    console.log('========================================');
    server.close();
    process.exit(0);
  } catch (err) {
    console.error('Server endpoint test FAILED:', err);
    server.close();
    process.exit(1);
  }
});
