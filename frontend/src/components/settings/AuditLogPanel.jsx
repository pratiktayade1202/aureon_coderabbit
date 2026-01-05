import React from "react";
import { ScrollText, Download, Filter } from "lucide-react";
import { TerminalCard, SectionHeader, Tag } from "./SettingsShared";

// Static demo audit log data
const AUDIT_LOGS = [
  {
    timestamp: "2025-12-09T14:23:45.123Z",
    actor: "pratik@aureon.ai",
    event: "API_KEY_CREATED",
    ip: "192.168.1.45",
    userAgent: "Chrome/120.0 (macOS)",
  },
  {
    timestamp: "2025-12-09T12:15:32.456Z",
    actor: "system",
    event: "MAINTENANCE_SCHEDULED",
    ip: "10.0.0.1",
    userAgent: "Aureon-Scheduler/2.4",
  },
  {
    timestamp: "2025-12-09T09:42:18.789Z",
    actor: "pratik@aureon.ai",
    event: "SESSION_TIMEOUT_CHANGED",
    ip: "192.168.1.45",
    userAgent: "Chrome/120.0 (macOS)",
  },
  {
    timestamp: "2025-12-08T22:31:05.234Z",
    actor: "ops@hdfc-amc.example",
    event: "INTEGRATION_CONNECTED",
    ip: "203.45.67.89",
    userAgent: "Safari/17.2 (macOS)",
  },
  {
    timestamp: "2025-12-08T18:55:41.567Z",
    actor: "pratik@aureon.ai",
    event: "MFA_ENABLED",
    ip: "192.168.1.45",
    userAgent: "Chrome/120.0 (macOS)",
  },
  {
    timestamp: "2025-12-08T15:12:33.890Z",
    actor: "system",
    event: "COMPLIANCE_CHECK_PASSED",
    ip: "10.0.0.1",
    userAgent: "Aureon-Compliance/1.2",
  },
  {
    timestamp: "2025-12-08T11:48:22.123Z",
    actor: "ops@hdfc-amc.example",
    event: "WORKSPACE_SETTING_UPDATED",
    ip: "203.45.67.89",
    userAgent: "Firefox/121.0 (Windows)",
  },
  {
    timestamp: "2025-12-07T23:05:15.456Z",
    actor: "pratik@aureon.ai",
    event: "IP_WHITELIST_ADDED",
    ip: "192.168.1.45",
    userAgent: "Chrome/120.0 (macOS)",
  },
  {
    timestamp: "2025-12-07T16:33:48.789Z",
    actor: "system",
    event: "AUTO_BACKUP_COMPLETED",
    ip: "10.0.0.1",
    userAgent: "Aureon-Backup/3.1",
  },
  {
    timestamp: "2025-12-07T09:21:37.012Z",
    actor: "ops@hdfc-amc.example",
    event: "USER_INVITED",
    ip: "203.45.67.89",
    userAgent: "Safari/17.2 (macOS)",
  },
  {
    timestamp: "2025-12-06T20:45:29.345Z",
    actor: "pratik@aureon.ai",
    event: "ALERT_RULE_CREATED",
    ip: "192.168.1.45",
    userAgent: "Chrome/120.0 (macOS)",
  },
  {
    timestamp: "2025-12-06T14:18:56.678Z",
    actor: "system",
    event: "CERTIFICATE_RENEWED",
    ip: "10.0.0.1",
    userAgent: "Aureon-PKI/1.0",
  },
];

const getEventColor = (event) => {
  if (
    event.includes("CREATED") ||
    event.includes("ENABLED") ||
    event.includes("CONNECTED")
  )
    return "text-emerald-700";
  if (
    event.includes("DELETED") ||
    event.includes("REMOVED") ||
    event.includes("REVOKED")
  )
    return "text-red-600";
  if (event.includes("CHANGED") || event.includes("UPDATED"))
    return "text-amber-700";
  return "text-ink-strong";
};

const AuditLogPanel = () => {
  return (
    <TerminalCard>
      <SectionHeader
        title="Audit Log"
        description="Recent configuration changes across this workspace. Data shown is a demo subset."
      />

      {/* Controls */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScrollText size={14} className="text-slate-500" />
          <span className="text-xs font-mono text-ink-muted">
            Showing last 12 events
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
            <Filter size={11} />
            Filter
          </button>
          <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
            <Download size={11} />
            Export
          </button>
        </div>
      </div>

      {/* Log table */}
      <div className="overflow-hidden rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/60">
        {/* Header */}
        <div className="grid grid-cols-12 gap-2 border-b border-slate-200/60 backdrop-blur-sm bg-white/40 px-2 py-1.5 text-[11px] font-mono uppercase tracking-wider text-slate-500">
          <span className="col-span-3">Timestamp</span>
          <span className="col-span-2">Actor</span>
          <span className="col-span-3">Event</span>
          <span className="col-span-2">IP</span>
          <span className="col-span-2">User Agent</span>
        </div>

        {/* Scrollable log entries */}
        <div className="max-h-[320px] overflow-auto bg-white/30">
          {AUDIT_LOGS.map((log, idx) => (
            <div
              key={idx}
              className="grid grid-cols-12 gap-2 border-b border-slate-200/40 px-2 py-1.5 text-[11px] font-mono last:border-b-0 hover:bg-white/50"
            >
              <span className="col-span-3 truncate text-ink-muted">
                {log.timestamp}
              </span>
              <span className="col-span-2 truncate text-ink-strong">
                {log.actor === "system" ? (
                  <span className="text-blue-600">system</span>
                ) : (
                  log.actor.split("@")[0]
                )}
              </span>
              <span className={`col-span-3 truncate ${getEventColor(log.event)}`}>
                {log.event}
              </span>
              <span className="col-span-2 truncate text-ink-muted">
                {log.ip}
              </span>
              <span className="col-span-2 truncate text-slate-500">
                {log.userAgent.split(" ")[0]}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[11px] font-mono text-ink-muted">
          Logs retained for 90 days · Full export available via API
        </span>
        <Tag>Demo Data</Tag>
      </div>
    </TerminalCard>
  );
};

export default AuditLogPanel;
