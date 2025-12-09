import React, { useState } from "react";
import { Key, RefreshCw, Copy, AlertTriangle, X } from "lucide-react";
import { TerminalCard, SectionHeader, Tag, Sparkline } from "./SettingsShared";

const API_KEYS = [
  {
    id: "key_ops_001",
    name: "Ops Service Account",
    scope: "Recons · Breaks API",
    created: "2025-11-02T09:14:00Z",
    lastUsed: "2025-12-09T06:42:00Z",
    status: "active",
    limit: "15 RPM · 300 RPD",
    burst: "50 requests",
    sparkData: [4, 7, 5, 9, 6, 8, 5, 7, 8, 6],
  },
  {
    id: "key_analytics_002",
    name: "Read-only Analytics",
    scope: "NAV history · Reports API",
    created: "2025-11-27T17:03:00Z",
    lastUsed: "2025-12-08T22:18:00Z",
    status: "active",
    limit: "10 RPM · 200 RPD",
    burst: "30 requests",
    sparkData: [2, 3, 4, 2, 5, 3, 4, 6, 3, 4],
  },
];

const ApiKeysPanel = () => {
  const [rotateModal, setRotateModal] = useState(null);

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toISOString().replace("T", " · ").slice(0, 18);
  };

  return (
    <TerminalCard>
      <SectionHeader
        title="API Keys"
        description="Manage credentials for programmatic access. Keys are scoped to this workspace."
      />

      {/* Controls */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Key size={14} className="text-aureon-gold" />
          <span className="text-xs font-mono text-ink-muted">
            {API_KEYS.length} active keys
          </span>
        </div>
        <button className="inline-flex items-center gap-1.5 rounded-md bg-aureon-blue px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-blue-700">
          <Key size={12} />
          Generate New Key
        </button>
      </div>

      {/* Keys list */}
      <div className="space-y-3">
        {API_KEYS.map((key) => (
          <div
            key={key.id}
            className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3 hover:border-slate-300/80 hover:bg-white/70 hover:shadow-md transition"
          >
            {/* Header row */}
            <div className="mb-2 flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-ink-strong">
                    {key.name}
                  </span>
                  <Tag variant="success">Active</Tag>
                </div>
                <span className="text-xs font-mono text-ink-muted">
                  {key.scope}
                </span>
              </div>
              <Sparkline data={key.sparkData} />
            </div>

            {/* Details grid */}
            <div className="mb-2 grid grid-cols-4 gap-4 text-[11px] font-mono">
              <div>
                <span className="block text-slate-500">Created</span>
                <span className="text-ink-muted">{formatDate(key.created)}</span>
              </div>
              <div>
                <span className="block text-slate-500">Last Used</span>
                <span className="text-ink-muted">{formatDate(key.lastUsed)}</span>
              </div>
              <div>
                <span className="block text-slate-500">Rate Limit</span>
                <span className="text-ink-muted">{key.limit}</span>
              </div>
              <div>
                <span className="block text-slate-500">Burst</span>
                <span className="text-ink-muted">{key.burst}</span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 border-t border-slate-200 pt-2">
              <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
                <Copy size={10} />
                Copy Key ID
              </button>
              <button
                onClick={() => setRotateModal(key.id)}
                className="inline-flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-[11px] font-mono text-red-600 hover:bg-red-50"
              >
                <RefreshCw size={10} />
                Rotate Secret
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Security notice */}
      <div className="mt-4 flex items-start gap-2 text-[11px] font-mono text-ink-muted">
        <Key size={11} className="mt-0.5 flex-shrink-0" />
        <span>
          Secrets are shown once at creation and stored hashed. Rotate keys
          regularly.
        </span>
      </div>

      {/* Rotate Secret Modal */}
      {rotateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-sm bg-white/20">
          <div className="mx-4 w-full max-w-md rounded-xl border border-slate-200/80 backdrop-blur-xl bg-white/90 p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RefreshCw size={16} className="text-red-500" />
                <h3 className="text-sm font-semibold text-ink-strong">
                  Rotate API Secret?
                </h3>
              </div>
              <button
                onClick={() => setRotateModal(null)}
                className="text-slate-500 hover:text-slate-800"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2">
              <AlertTriangle
                size={14}
                className="mt-0.5 flex-shrink-0 text-red-500"
              />
              <p className="text-[11px] font-mono text-red-700">
                This will immediately invalidate the existing secret. You must
                update all downstream systems using this key before rotation.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setRotateModal(null)}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-mono text-ink-muted hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => setRotateModal(null)}
                className="rounded-md bg-red-600 px-3 py-1.5 text-[11px] font-mono text-white hover:bg-red-500"
              >
                Rotate Secret
              </button>
            </div>
          </div>
        </div>
      )}
    </TerminalCard>
  );
};

export default ApiKeysPanel;
