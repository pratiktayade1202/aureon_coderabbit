import React from "react";
import {
  Building2,
  MapPin,
  ShieldCheck,
  Calendar,
  Copy,
  ExternalLink,
} from "lucide-react";
import {
  TerminalCard,
  SectionHeader,
  SectionDivider,
  FieldRow,
  Tag,
  StatusDot,
} from "./SettingsShared";

const WorkspacePanel = () => {
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <TerminalCard>
      <SectionHeader
        title="Workspace Configuration"
        description="Workspace-level settings for all users and funds onboarded to Aureon."
      />

      {/* Basic Info */}
      <div className="space-y-3">
        <FieldRow label="Workspace Name">
          <input
            type="text"
            className="w-full max-w-xs rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-ink-strong focus:outline-none focus:ring-1 focus:ring-aureon-gold"
            defaultValue="HDFC AMC - Aureon Lab"
          />
        </FieldRow>

        <FieldRow label="Workspace ID">
          <div className="flex items-center gap-2 justify-end">
            <code className="rounded-md bg-slate-50 px-2 py-0.5 text-xs font-mono text-ink-strong border border-slate-200">
              AUR-WSPC-883-A
            </code>
            <button
              onClick={() => copyToClipboard("AUR-WSPC-883-A")}
              className="text-slate-500 hover:text-slate-800"
            >
              <Copy size={12} />
            </button>
          </div>
        </FieldRow>

        <FieldRow label="Environment">
          <div className="flex items-center justify-end gap-2">
            <Tag variant="warning">NON-PROD</Tag>
            <button className="inline-flex items-center gap-1 text-[11px] font-mono text-aureon-gold hover:text-amber-700">
              Request Prod <ExternalLink size={10} />
            </button>
          </div>
        </FieldRow>
      </div>

      {/* Compliance & Region */}
      <SectionDivider label="Compliance & Region" />
      <div className="space-y-3">
        <FieldRow label="Data Residency">
          <div className="flex items-center justify-end gap-2">
            <MapPin size={14} className="text-slate-500" />
            <span className="text-sm font-mono text-ink-strong">
              Frankfurt (AWS eu-central-1)
            </span>
          </div>
        </FieldRow>

        <FieldRow label="Primary Region">
          <select className="w-full max-w-xs rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm font-mono text-ink-strong focus:outline-none focus:ring-1 focus:ring-aureon-gold">
            <option>APAC (Mumbai) · ap-south-1</option>
            <option defaultValue>EU (Frankfurt) · eu-central-1</option>
            <option>US (Virginia) · us-east-1</option>
          </select>
        </FieldRow>

        <FieldRow label="Compliance">
          <div className="flex items-center justify-end gap-2">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1">
              <StatusDot status="healthy" />
              <span className="text-[11px] font-mono text-emerald-800">
                SOC 2 Type II
              </span>
            </div>
            <span className="text-[11px] font-mono text-ink-muted">
              Monitoring Active
            </span>
          </div>
        </FieldRow>
      </div>

      {/* Maintenance Windows */}
      <SectionDivider label="Maintenance Windows" />
      <div className="space-y-3">
        <FieldRow label="Preferred Patch Window">
          <div className="flex items-center justify-end gap-2">
            <Calendar size={14} className="text-slate-500" />
            <span className="text-sm font-mono text-ink-strong">
              Sunday 02:00 UTC
            </span>
            <button className="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
              Change
            </button>
          </div>
        </FieldRow>

        <FieldRow label="Last Maintenance">
          <span className="text-xs font-mono text-ink-muted">
            2025-12-08T02:00:00Z · 12m downtime
          </span>
        </FieldRow>

        <FieldRow label="Next Scheduled">
          <div className="flex items-center justify-end gap-2">
            <span className="text-xs font-mono text-ink-strong">
              2025-12-15T02:00:00Z
            </span>
            <Tag>Planned</Tag>
          </div>
        </FieldRow>
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
        <span className="text-[11px] font-mono text-ink-muted">
          Workspace created: 2025-11-02 · Owner: ops@hdfc-amc.example
        </span>
        <div className="flex items-center gap-1">
          <ShieldCheck size={12} className="text-emerald-600" />
          <span className="text-[11px] font-mono text-emerald-700">
            Verified
          </span>
        </div>
      </div>
    </TerminalCard>
  );
};

export default WorkspacePanel;
