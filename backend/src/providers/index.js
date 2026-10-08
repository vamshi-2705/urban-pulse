/**
 * UrbanPulse - Provider Factory & Selector
 *
 * Selects active provider based on DATA_PROVIDER environment variable:
 * - 'postgres': PostgreSQL persistence (requires DATABASE_URL)
 * - 'file': Direct filesystem JSON provider
 * - 'mock' (default): Preloaded in-memory development provider
 */

import { mockProvider } from './mockProvider.js';
import { fileProvider } from './fileProvider.js';
import { postgresProvider } from './postgresProvider.js';
import { realProvider } from './realProvider.js';

export function getProviderType() {
  return (process.env.DATA_PROVIDER || 'mock').toLowerCase();
}

export function getProvider() {
  const type = getProviderType();
  if (type === 'postgres') {
    if (!process.env.DATABASE_URL) {
      console.error('\n[UrbanPulse] FATAL CONFIG ERROR: DATA_PROVIDER=postgres requires DATABASE_URL to be set.');
      console.error('Example: DATABASE_URL="postgresql://user:pass@localhost:5432/dbname"\n');
      throw new Error('DATA_PROVIDER=postgres requires DATABASE_URL to be set.');
    }
    return postgresProvider;
  }
  if (type === 'real') {
    return realProvider;
  }
  if (type === 'file') {
    return fileProvider;
  }
  return mockProvider;
}

export async function verifyActiveProvider() {
  const type = getProviderType();
  if (type === 'postgres') {
    await postgresProvider.verifyConnection();
  }
  return true;
}

export { mockProvider, fileProvider, postgresProvider, realProvider };
export default getProvider;
