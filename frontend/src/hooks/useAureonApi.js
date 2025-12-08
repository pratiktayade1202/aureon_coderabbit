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
    getStats: () => request("/dashboard-stats"),
    
    // 2. INGESTION (Updated Path)
    uploadIngestionFile: (formData) => request("/ingestion/upload", { 
      method: "POST", 
      body: formData 
    }),
    
    // 3. ENGINE & RECONCILIATION
    // Triggers the Orchestrator
    getTrades: () => request("/recon/run", { method: "POST" }), 
    
    // Fetches Open Breaks
    getBreaks: () => request("/recon/breaks"),
    
    // 4. AI & TOOLS
    // Asks AI Agent to analyze a specific trade/break
    getBreakAnalysis: (tradeId) => request(`/recon/analyze/${tradeId}`),
    
    // Fetches patterns learned by the system
    getLearnedRules: () => request("/learned-rules"),
    
    // 5. MANUAL RESOLUTION
    // Resolves a trade via the new backend endpoint
    manualResolve: (tradeId, reason) => request(`/recon/resolve-trade/${tradeId}`, {
      method: "POST",
      body: JSON.stringify({
        note: reason // Backend expects 'note' in payload
      })
    }),

    // 6. SYSTEM (Updated Path)
    resetDb: () => request("/system/reset", { method: "POST" }),
    
  }), [request]); 
};