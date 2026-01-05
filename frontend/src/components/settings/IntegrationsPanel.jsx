import React from "react";
import { PlugZap, ExternalLink, RefreshCw } from "lucide-react";
import { TerminalCard, SectionHeader, StatusDot, Tag } from "./SettingsShared";

const INTEGRATIONS = [
  {
    id: "bloomberg_sftp",
    name: "Bloomberg SFTP",
    type: "Market Data Feed",
    status: "healthy",
    statusText: "Connected",
    subtext: "Last heartbeat: 2s ago",
    lastSync: "2025-12-09T14:25:43Z",
  },
  {
    id: "gs_prime",
    name: "Goldman Sachs (Prime)",
    type: "Prime Brokerage",
    status: "syncing",
    statusText: "Syncing (98%)",
    subtext: "Position feed: Next cut 03:00 UTC",
    lastSync: "2025-12-09T12:00:00Z",
  },
  {
    id: "custodian_sftp",
    name: "Custodian SFTP",
    type: "Trade & Position Files",
    status: "healthy",
    statusText: "Connected",
    subtext: "Daily file: Received 06:15 UTC",
    lastSync: "2025-12-09T06:15:22Z",
  },
  {
    id: "slack_webhook",
    name: "Slack Webhook",
    type: "Alerting",
    status: "healthy",
    statusText: "Configured",
    subtext: "Critical break alerts",
    lastSync: null,
    hasInput: true,
  },
  {
    id: "oms_pms",
    name: "OMS / PMS",
    type: "Order & Portfolio Data",
    status: "warning",
    statusText: "In Pilot",
    subtext: "Sandbox environment",
    lastSync: "2025-12-08T18:30:00Z",
  },
];

const IntegrationsPanel = () => {
  const formatTime = (iso) => {
    if (!iso) return "—";
    return new Date(iso).toISOString().replace("T", " ").slice(0, 19);
  };

  return (
    <TerminalCard>
      <SectionHeader
        title="Integrations"
        description="External connections for market data, prime brokerage, custody, and alerting."
      />

      {/* Status summary */}
      <div className="mb-3 flex items-center gap-4 text-xs font-mono text-ink-muted">
        <span className="flex items-center gap-1.5">
          <PlugZap size={13} />
          {INTEGRATIONS.length} connections
        </span>
        <span className="flex items-center gap-1.5 text-emerald-700">
          <StatusDot status="healthy" />
          {INTEGRATIONS.filter((i) => i.status === "healthy").length} healthy
        </span>
        <span className="flex items-center gap-1.5 text-blue-700">
          <StatusDot status="syncing" />
          {INTEGRATIONS.filter((i) => i.status === "syncing").length} syncing
        </span>
      </div>

      {/* Integration list */}
      <div className="space-y-2">
        {INTEGRATIONS.map((integration) => (
          <div
            key={integration.id}
            className="flex items-center gap-3 rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3 hover:border-slate-300/80 hover:bg-white/70 hover:shadow-md transition"
          >
            {/* Status dot */}
            <StatusDot status={integration.status} />

            {/* Main info */}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-ink-strong">
                  {integration.name}
                </span>
                <span className="text-[11px] font-mono text-ink-muted">
                  {integration.type}
                </span>
              </div>
              <span className="text-[11px] font-mono text-ink-muted">
                {integration.subtext}
              </span>
            </div>

            {/* Webhook input for Slack */}
            {integration.hasInput && (
              <input
                type="text"
                placeholder="https://hooks.slack.com/..."
                className="w-64 rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-mono text-ink-strong placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-aureon-gold"
              />
            )}

            {/* Status & last sync */}
            <div className="text-right">
              <Tag
                variant={
                  integration.status === "healthy"
                    ? "success"
                    : integration.status === "syncing"
                    ? "info"
                    : "warning"
                }
              >
                {integration.statusText}
              </Tag>
              <div className="mt-1 text-[11px] font-mono text-ink-muted">
                {integration.lastSync ? formatTime(integration.lastSync) : ""}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1">
              <button className="p-1 text-slate-500 hover:text-slate-800">
                <RefreshCw size={13} />
              </button>
              <button className="p-1 text-slate-500 hover:text-slate-800">
                <ExternalLink size={13} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
        <span className="text-[11px] font-mono text-ink-muted">
          Additional connectors (fund admin, GL) available during onboarding
        </span>
        <button className="inline-flex items-center gap-1 text-[11px] font-mono text-aureon-gold hover:text-amber-700">
          Integration Playbook <ExternalLink size={10} />
        </button>
      </div>
    </TerminalCard>
  );
};

export default IntegrationsPanel;
