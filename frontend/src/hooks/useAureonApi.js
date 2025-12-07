// src/hooks/useAureonApi.js
import { useAuth } from "@clerk/clerk-react";
import { useCallback, useMemo } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export const useAureonApi = () => {
  const { getToken } = useAuth();

  const request = useCallback(async (endpoint, options = {}) => {
    try {
      const token = await getToken();
      
      const defaultHeaders = {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      };

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
      if (res.status === 403) throw new Error("Access Restricted: Waitlist");

      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.message || data.detail || "API Error");
      }

      return data;
    } catch (error) {
      console.error(`API Call Failed [${endpoint}]:`, error);
      throw error;
    }
  }, [getToken]);

  return useMemo(() => ({
    // 1. DASHBOARD
    getStats: () => request("/dashboard-stats"),
    
    // 2. INGESTION
    uploadFile: (formData) => request("/upload", { 
      method: "POST", 
      body: formData 
    }),
    // NEW: Get analysis for specific trade
    getBreakAnalysis: (tradeId) => request(`/analyze-break/${tradeId}`),
    
    // 3. ENGINE (Tier 1)
    getTrades: () => request("/run-engine", { method: "POST" }),
    runPositionRecon: () => request("/run-positions-check", { method: "POST" }),
    
    getHoldings: async (jwt, userId) =>
      api.get(`/holdings/${userId}`, {
        headers: { Authorization: `Bearer ${jwt}` },
      }),
    getNAV: async (jwt, userId) =>
      api.get(`/nav/${userId}`, {
        headers: { Authorization: `Bearer ${jwt}` },
      }),
    
    // 4. AI AGENT (Tier 2)
    runAiResolve: () => request("/run-ai-resolve", { method: "POST" }),
    getAuditLogs: () => request("/audit-logs"),
    
    // 5. HUMAN INTERVENTION (Tier 3)
    manualResolve: (tradeId, reason) => request("/manual-resolve", {
      method: "POST",
      body: JSON.stringify({
        trade_id: tradeId,
        status: "✅ SETTLED (MANUAL)",
        reason: reason
      })
    }),
    
    applySuggestion: (breakId, suggestionId) => request("/apply-suggestion", {
      method: "POST",
      body: JSON.stringify({ break_id: breakId, suggestion_id: suggestionId })
    }),
    
    // 6. LEARNER
    getLearnedRules: () => request("/learned-rules"),
    learnRules: () => request("/learn-rules", { method: "POST" }),

    // 7. SYSTEM
    resetDb: () => request("/reset-db", { method: "POST" }),
    
  }), [request]); 
};