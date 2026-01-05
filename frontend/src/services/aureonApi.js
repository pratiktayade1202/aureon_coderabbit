// src/services/aureonApi.js
import { API_BASE_URL } from '../config';
import { logger } from '../utils/logger';

const request = async (path, options = {}) => {
  const { token, method = "GET", body } = options;
  const headers = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
  };

  const config = {
    method,
    headers,
    ...(body && { body: JSON.stringify(body) }),
  };

  const url = `${API_BASE_URL}${path}`;
  logger.api(method, path);

  const res = await fetch(url, config);
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API error ${res.status}: ${errorText}`);
  }
  return await res.json();
};

// --- REAL ENDPOINTS ---

export const getDashboardStats = (token) => request("/recon/dashboard-stats", { token });

export const runReconciliation = (token) => request("/recon/run", { method: "POST", token });

export const getRules = (token) => request("/rules/list", { token });

export const getUploadHistory = (token) => request("/ingestion/upload/history", { token });

export const uploadFile = (formData) => {
  return fetch(`${API_BASE_URL}/ingestion/upload`, {
    method: "POST",
    headers: {
      Authorization: "Bearer dev-token",
    },
    body: formData,
  }).then(res => {
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  });
};

// --- COMPATIBILITY LAYER FOR App.jsx ---

// Alias getStats to getDashboardStats
export const getStats = getDashboardStats;

// Get trades - calls real backend endpoint
export const getTrades = async (token, params = {}) => {
  try {
    const search = new URLSearchParams();
    if (params.page) search.set("page", params.page);
    if (params.pageSize) search.set("page_size", params.pageSize);
    if (params.status) search.set("status", params.status);
    if (params.symbol) search.set("symbol", params.symbol);
    if (params.dateFrom) search.set("date_from", params.dateFrom);
    if (params.dateTo) search.set("date_to", params.dateTo);

    const query = search.toString();
    const response = await request(
      `/recon/trades${query ? `?${query}` : ""}`,
      { token }
    );

    if (Array.isArray(response)) {
      return { rows: response, pagination: null };
    }

    return {
      rows: response?.data || [],
      pagination: response?.pagination || null,
      status: response?.status || "success",
    };
  } catch (error) {
    console.error("Failed to fetch trades:", error);
    return { rows: [], pagination: null, status: "error" };
  }
};

// Run position reconciliation
export const runPositionRecon = async (token) => {
  try {
    const data = await request("/recon/position-recon", { method: "POST", token });
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("Failed to run position recon:", error);
    return [];
  }
};

// Run AI resolve
export const runAiResolve = async (token) => {
  try {
    const data = await request("/recon/ai-resolve", { method: "POST", token });
    return data;
  } catch (error) {
    console.error("Failed to run AI resolve:", error);
    throw error;
  }
};

// Reset database
export const resetDb = async (token) => {
  try {
    const data = await request("/recon/reset-db", { method: "POST", token });
    return data;
  } catch (error) {
    console.error("Failed to reset database:", error);
    throw error;
  }
};

// Default export object for backward compatibility with App.jsx imports
const api = {
  getStats,
  getTrades,
  getDashboardStats,
  runReconciliation,
  getRules,
  uploadFile,
  getUploadHistory,
  runPositionRecon,
  runAiResolve,
  resetDb,
};

export default api;
