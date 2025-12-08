// frontend/src/services/aureonApi.js

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Generic request helper with Auth and Error handling
 */
async function request(path, { method = "GET", token, body, isFormData = false } = {}) {
  const headers = {};

  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: isFormData ? body : body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${method} ${path} failed: ${res.status} ${text}`);
  }

  return res.json();
}

// ==========================================
// 1. INGESTION (Synchronous)
// ==========================================

export async function uploadIngestionFile(file, token) {
  const form = new FormData();
  form.append("file", file);

  // We now use the sync endpoint. No need to poll for job IDs anymore.
  return request("/ingestion/upload", {
    method: "POST",
    token,
    body: form,
    isFormData: true,
  });
}

// ==========================================
// 2. RECONCILIATION ENGINE
// ==========================================

export async function runReconciliation(token) {
  // Triggers the Python Rule Engine
  return request("/recon/run", { method: "POST", token });
}

export async function getBreaks(token) {
  return request("/recon/breaks", { token });
}

export async function clearBreak(breakId, token) {
  // Manually resolves a break and logs a Learning Event
  return request(`/recon/clear/${breakId}`, { method: "POST", token });
}

// ==========================================
// 3. AI & ANALYSIS
// ==========================================

export async function getBreakAnalysis(tradeId, token) {
  // Calls the Co-Pilot to analyze a specific trade/break
  return request(`/analyze-break/${tradeId}`, { token });
}

export async function getLearnedRules(token) {
  // Fetches patterns learned by the AI Agent
  return request("/learned-rules", { token });
}

// ==========================================
// 4. DASHBOARD & SYSTEM
// ==========================================

export async function getDashboardStats(token) {
  return request("/dashboard-stats", { token });
}

export async function resetDatabase(token) {
  // The "Nuclear Option" - Wipes DB and resets memory
  return request("/reset-db", { method: "POST", token });
}

// ==========================================
// 5. RULE MANAGEMENT (Legacy/Optional)
// ==========================================

export async function listRules(token) {
  return request("/rules/list", { token });
}

export async function activateRule(ruleId, token) {
  return request(`/rules/activate/${ruleId}`, { method: "POST", token });
}

export async function deactivateRule(ruleId, token) {
  return request(`/rules/deactivate/${ruleId}`, { method: "POST", token });
}

export async function createRule(rule, token) {
  return request("/rules/create", {
    method: "POST",
    token,
    body: rule,
  });
}