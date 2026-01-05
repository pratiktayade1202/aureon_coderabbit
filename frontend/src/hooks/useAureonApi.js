// src/hooks/useAureonApi.js
import { useAuth } from "@clerk/clerk-react";
import { useCallback, useMemo } from "react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

export const useAureonApi = () => {
  const { getToken } = useAuth();

  const request = useCallback(async (endpoint, options = {}) => {
    try {
      const token = await getToken();

      const defaultHeaders = {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      };

      // If sending FormData (file upload), let browser set Content-Type
      if (options.body instanceof FormData) {
        delete defaultHeaders["Content-Type"];
      }

      const config = {
        ...options,
        headers: {
          ...defaultHeaders,
          ...options.headers,
        },
      };

      const res = await fetch(`${API_BASE}${endpoint}`, config);

      if (res.status === 401) throw new Error("Unauthorized");
      if (res.status === 403) throw new Error("Access Restricted");

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.message || data.detail || `API Error ${res.status}`);
      }

      return data;
    } catch (error) {
      console.error(`API Call Failed [${endpoint}]:`, error);
      throw error;
    }
  }, [getToken]);

  return useMemo(() => ({
    // 1. DASHBOARD
    // Align with backend route: /api/v1/recon/dashboard-stats
    getStats: () => request("/recon/dashboard-stats"),

    // 2. INGESTION (Updated Path)
    uploadIngestionFile: (formData) => request("/ingestion/upload", {
      method: "POST",
      body: formData
    }),

    // 2.1 GLASS-BOX INGESTION (v3)
    startIngestionSession: (formData) => request("/ingestion/sessions", {
      method: "POST",
      body: formData
    }),
    getSessionStatus: (sessionId) => request(`/ingestion/sessions/${sessionId}`),
    approveContract: (contractId, mapping, destructiveAck = false) => request(`/ingestion/contracts/${contractId}/approve`, {
      method: "POST",
      body: JSON.stringify({
        contract_id: contractId,
        final_mapping: mapping,
        destructive_ack: destructiveAck
      })
    }),

    // 3. ENGINE & RECONCILIATION
    // Fetch trades in frontend-ready format
    getTrades: () => request("/recon/trades"),

    // Fetches Open Breaks
    getBreaks: () => request("/recon/breaks"),

    // 4. AI & TOOLS
    // Asks AI Agent to analyze a specific trade/break
    getBreakAnalysis: (tradeId) => request(`/recon/analyze/${tradeId}`),

    // Fetches patterns learned by the system
    getLearnedRules: () => request("/learned-rules"),

    // 5. MANUAL RESOLUTION
    // Resolves a trade via the new backend endpoint
    manualResolve: (tradeId, payload = {}) => request(`/recon/resolve-trade/${tradeId}`, {
      method: "POST",
      body: JSON.stringify({
        note: payload.note,
        cash_id: payload.cashId ?? null,
      })
    }),

    // 6. SYSTEM (Updated Path)
    resetDb: () => request("/system/reset", { method: "POST" }),

    // 7. TRAINING (for Learner page)
    learnRules: () => request("/learned-rules/train", { method: "POST" }),

  }), [request]);
};