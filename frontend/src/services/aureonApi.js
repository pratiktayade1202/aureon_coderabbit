// frontend/src/services/aureonApi.js

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

// ---------- Ingestion ----------
export async function uploadIngestionFile(file, token) {
  const form = new FormData();
  form.append("file", file);

  return request("/ingestion/upload", {
    method: "POST",
    token,
    body: form,
    isFormData: true,
  });
}

export async function getIngestionStatus(jobId, token) {
  return request(`/ingestion/status/${jobId}`, { token });
}

export async function getIngestionLogs(jobId, token) {
  return request(`/ingestion/logs/${jobId}`, { token });
}

// ---------- Reconciliation ----------
export async function runReconciliation(token) {
  return request("/recon/run", { method: "POST", token });
}

export async function getBreaks(token) {
  return request("/recon/breaks", { token });
}

export async function clearBreak(breakId, token) {
  return request(`/recon/clear/${breakId}`, { method: "POST", token });
}

// ---------- Rules ----------
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
