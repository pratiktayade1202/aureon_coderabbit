import React, { useState } from "react";
import {
  Bell,
  AlertTriangle,
  TrendingDown,
  Database,
  Mail,
  ExternalLink,
} from "lucide-react";
import {
  TerminalCard,
  SectionHeader,
  SectionDivider,
  Tag,
  Toggle,
  StatusDot,
} from "./SettingsShared";

const ALERT_RULES = [
  {
    id: "nav_deviation",
    name: "NAV Deviation",
    icon: TrendingDown,
    description: "Triggers when NAV moves beyond threshold intraday",
    condition: "> 30 bps vs prior close",
    channels: ["EMAIL", "SLACK"],
    enabled: true,
    severity: "high",
  },
  {
    id: "break_detection",
    name: "Break Detection",
    icon: AlertTriangle,
    description: "Alerts on new breaks or SLA violations",
    condition: "New high-severity break created",
    channels: ["EMAIL", "SLACK", "TEAMS"],
    enabled: true,
    severity: "critical",
  },
  {
    id: "ingestion_failure",
    name: "Ingestion Failures",
    icon: Database,
    description: "Notify when ingestion jobs fail or stall",
    condition: "Job fails or > 2× median runtime",
    channels: ["EMAIL", "PAGERDUTY"],
    enabled: true,
    severity: "high",
  },
  {
    id: "daily_digest",
    name: "Daily Digest",
    icon: Mail,
    description: "Consolidated summary of breaks and NAV",
    condition: "Sent at 07:30 local time",
    channels: ["OPS", "RISK", "FRONT OFFICE"],
    enabled: true,
    severity: "info",
  },
];

const getSeverityColor = (severity) => {
  switch (severity) {
    case "critical":
      return "text-red-600";
    case "high":
      return "text-amber-600";
    case "medium":
      return "text-yellow-600";
    default:
      return "text-blue-600";
  }
};

const AlertsPanel = () => {
  const [rules, setRules] = useState(ALERT_RULES);

  const toggleRule = (id) => {
    setRules(rules.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r)));
  };

  return (
    <TerminalCard>
      <SectionHeader
        title="Alerts & Notifications"
        description="Configure real-time alerting for NAV deviations, breaks, and ingestion failures."
      />

      {/* Summary stats */}
      <div className="mb-3 flex items-center gap-4 text-xs font-mono text-ink-muted">
        <span className="flex items-center gap-1.5">
          <Bell size={13} />
          {rules.length} alert rules
        </span>
        <span className="flex items-center gap-1.5 text-emerald-700">
          <StatusDot status="healthy" />
          {rules.filter((r) => r.enabled).length} active
        </span>
        <span className="flex items-center gap-1.5">
          Last 24h: 3 alerts fired
        </span>
      </div>

      {/* Alert rules */}
      <div className="space-y-2">
        {rules.map((rule) => {
          const Icon = rule.icon;
          return (
            <div
              key={rule.id}
              className={`rounded-xl border p-3 transition hover:shadow-md ${
                rule.enabled
                  ? "border-slate-200/60 backdrop-blur-sm bg-white/50 hover:bg-white/70"
                  : "border-slate-200/60 backdrop-blur-sm bg-white/30 opacity-70"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                {/* Left side */}
                <div className="flex flex-1 items-start gap-2">
                  <div className={`mt-0.5 ${getSeverityColor(rule.severity)}`}>
                    <Icon size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-sm font-medium text-ink-strong">
                        {rule.name}
                      </span>
                      <Tag
                        variant={
                          rule.severity === "critical"
                            ? "danger"
                            : rule.severity === "high"
                            ? "warning"
                            : "info"
                        }
                      >
                        {rule.severity}
                      </Tag>
                    </div>
                    <p className="mb-1 text-xs font-mono text-ink-muted">
                      {rule.description}
                    </p>
                    <div className="flex items-center gap-2 text-[11px] font-mono">
                      <span className="text-slate-500">Condition:</span>
                      <span className="text-ink-muted">{rule.condition}</span>
                    </div>
                  </div>
                </div>

                {/* Right side - channels and toggle */}
                <div className="flex flex-col items-end gap-2">
                  <Toggle
                    checked={rule.enabled}
                    onChange={() => toggleRule(rule.id)}
                  />
                  <div className="flex flex-wrap justify-end gap-1">
                    {rule.channels.map((ch) => (
                      <Tag key={ch}>{ch}</Tag>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Escalation policy */}
      <SectionDivider label="Escalation Policy" />
      <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3 text-[11px] font-mono text-ink-muted">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <span className="block text-slate-500">L1 Response</span>
            <span>Slack + Email · Immediate</span>
          </div>
          <div>
            <span className="block text-slate-500">L2 Escalation</span>
            <span>PagerDuty · After 15min</span>
          </div>
          <div>
            <span className="block text-slate-500">L3 Escalation</span>
            <span>Phone · After 30min</span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
        <div className="flex items-center gap-2 text-[11px] font-mono text-ink-muted">
          <Bell size={11} />
          <span>
            Alert routing pre-wired for demo. Fully configurable in production.
          </span>
        </div>
        <button className="inline-flex items-center gap-1 text-[11px] font-mono text-aureon-gold hover:text-amber-700">
          Routing Map <ExternalLink size={10} />
        </button>
      </div>
    </TerminalCard>
  );
};

export default AlertsPanel;
