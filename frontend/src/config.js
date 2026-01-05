// src/config.js
// Centralized API base URL normalization with production safety.

const isDev = import.meta.env.DEV;
const isProd = import.meta.env.PROD;

/**
 * Require an environment variable, with optional dev-only fallback.
 * In production, missing required env vars will throw errors.
 */
const requireEnv = (key, devFallback = null) => {
  const value = import.meta.env[key];

  if (!value || value.trim().length === 0) {
    if (devFallback !== null && isDev) {
      console.warn(`⚠️  ${key} not set, using fallback: ${devFallback}`);
      return devFallback;
    }
    throw new Error(`Missing required environment variable: ${key}`);
  }

  return value.trim();
};

// Get API URL with dev fallback
const rawBase = requireEnv(
  'VITE_API_URL',
  isDev ? 'http://localhost:8000' : null
);

// Validate URL format
try {
  new URL(rawBase);
} catch (e) {
  throw new Error(`Invalid VITE_API_URL format: ${rawBase}`);
}

// Security: Prevent localhost in production builds
if (isProd && rawBase.includes('localhost')) {
  throw new Error('Production build cannot use localhost API');
}

// Strip trailing slashes for consistency
const normalizedBase = rawBase.replace(/\/+$/, "");

// Ensure we always end with /api/v1
export const API_BASE_URL = normalizedBase.endsWith("/api/v1")
  ? normalizedBase
  : `${normalizedBase}/api/v1`;

// Log API config (safe - only in dev)
if (isDev) {
  console.log(`✅ API configured: ${API_BASE_URL}`);
}
