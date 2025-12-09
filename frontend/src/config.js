// src/config.js
// Centralized API base URL normalization for the whole app.
// Guarantees that API_BASE_URL always points to the FastAPI v1 router: .../api/v1

const rawBase =
  import.meta.env.VITE_API_URL && import.meta.env.VITE_API_URL.trim().length > 0
    ? import.meta.env.VITE_API_URL.trim()
    : "http://localhost:8000";

// Strip trailing slashes for consistency
const normalizedBase = rawBase.replace(/\/+$/, "");

// Ensure we always end with /api/v1
export const API_BASE_URL = normalizedBase.endsWith("/api/v1")
  ? normalizedBase
  : `${normalizedBase}/api/v1`;

