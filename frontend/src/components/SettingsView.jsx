// src/components/SettingsView.jsx
import React, { useState } from "react";
import {
  Settings,
  User,
  Building2,
  CreditCard,
  KeyRound,
  Shield,
  Bell,
  PlugZap,
  AlertTriangle,
} from "lucide-react";

/**
 * Aureon Settings
 * Side-tab institutional layout (Cleaned Up)
 */

const SECTIONS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "workspace", label: "Workspace", icon: Building2 },
  { id: "billing", label: "Billing & Usage", icon: CreditCard },
  { id: "access", label: "Access Control", icon: Shield },
  { id: "api", label: "API Keys", icon: KeyRound },
  { id: "integrations", label: "Integrations", icon: PlugZap },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "danger", label: "Danger Zone", icon: AlertTriangle },
];

/* ---------------------------------------
 * SMALL REUSABLE LAYOUT BITS
 * -------------------------------------*/

const SectionHeader = ({ title, description }) => (
  <div className="mb-4 border-b border-slate-200 pb-3">
    <h2 className="text-sm font-semibold text-ink-strong">{title}</h2>
    {description && (
      <p className="text-[11px] text-ink-muted mt-1">{description}</p>
    )}
  </div>
);

const FieldRow = ({ label, children, hint }) => (
  <div className="py-2.5 flex flex-col gap-1 border-b border-slate-100 last:border-b-0">
    <div className="flex items-center justify-between gap-4">
      <span className="text-[11px] font-medium text-ink-muted uppercase tracking-wide">
        {label}
      </span>
      <div className="flex-1 max-w-md text-right">{children}</div>
    </div>
    {hint && (
      <p className="text-[10px] text-ink-faint text-right max-w-md ml-auto">
        {hint}
      </p>
    )}
  </div>
);

const Tag = ({ children }) => (
  <span className="inline-flex items-center px-1.5 py-[2px] rounded-sm border border-slate-300 bg-slate-50 text-[10px] font-mono text-ink-muted">
    {children}
  </span>
);

/* ---------------------------------------
 * PANELS
 * -------------------------------------*/

const ProfilePanel = () => {
  return (
    <div className="bg-white border border-slate-200 rounded-md p-4">
      <SectionHeader
        title="Profile"
        description="Basic profile information for this login."
      />
      <div className="space-y-3">
        <FieldRow label="Name">
          <input
            type="text"
            className="w-full max-w-xs border border-slate-300 rounded-md px-2 py-1.5 text-[12px] text-ink-strong bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            defaultValue="Aureon Analyst"
          />
        </FieldRow>

        <FieldRow label="Email">
          <input
            type="email"
            className="w-full max-w-xs border border-slate-300 rounded-md px-2 py-1.5 text-[12px] text-ink-strong bg-slate-50"
            defaultValue="analyst@client-firm.com"
            disabled
          />
        </FieldRow>

        <FieldRow label="Role" hint="Role is managed by your workspace admin.">
          <Tag>ANALYST</Tag>
        </FieldRow>
      </div>
    </div>
  );
};

const WorkspacePanel = () => {
  return (
    <div className="bg-white border border-slate-200 rounded-md p-4">
      <SectionHeader
        title="Workspace"
        description="Workspace-level configuration that applies to all users."
      />
      <div className="space-y-3">
        <FieldRow label="Workspace Name">
          <input
            type="text"
            className="w-full max-w-xs border border-slate-300 rounded-md px-2 py-1.5 text-[12px] text-ink-strong bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            defaultValue="HDFC AMC - Aureon Lab"
          />
        </FieldRow>

        <FieldRow label="Region">
          <select className="w-full max-w-xs border border-slate-300 rounded-md px-2 py-1.5 text-[12px] bg-white text-ink-strong">
            <option>APAC (Mumbai)</option>
            <option>EU (Frankfurt)</option>
            <option>US (New York)</option>
          </select>
        </FieldRow>

        <FieldRow label="Environment">
          <div className="flex justify-end gap-2">
            <Tag>NON-PROD</Tag>
          </div>
        </FieldRow>

        <FieldRow label="Workspace ID">
          <div className="flex items-center justify-end gap-2">
            <code className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">
              AUR-WSPC-883-A
            </code>
          </div>
        </FieldRow>
      </div>
    </div>
  );
};

// Only renders when the Tab is Active
const DangerZonePanel = ({ onReset }) => {
  return (
    <div className="bg-white border border-red-200 rounded-md p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-red-600" size={14} />
          <div>
            <p className="text-[11px] font-semibold text-red-700 uppercase">
              Danger Zone
            </p>
            <p className="text-[10px] text-red-600">
              Use only under guidance. This is not reversible.
            </p>
          </div>
        </div>
        <button
          onClick={onReset}
          className="px-2.5 py-1 text-[11px] rounded-md border border-red-500 text-red-700 hover:bg-red-50 transition-colors"
        >
          Reset Workspace
        </button>
      </div>
    </div>
  );
};

const BillingPanel = () => <div className="bg-white border border-slate-200 rounded-md p-4"><SectionHeader title="Billing" description="Managed by Enterprise Admin." /></div>;
const AccessPanel = () => <div className="bg-white border border-slate-200 rounded-md p-4"><SectionHeader title="Access Control" description="Role Based Access Control." /></div>;
const ApiKeysPanel = () => <div className="bg-white border border-slate-200 rounded-md p-4"><SectionHeader title="API Keys" description="Manage programmatic access." /></div>;
const IntegrationsPanel = () => <div className="bg-white border border-slate-200 rounded-md p-4"><SectionHeader title="Integrations" description="Upstream/Downstream pipes." /></div>;
const AlertsPanel = () => <div className="bg-white border border-slate-200 rounded-md p-4"><SectionHeader title="Alerts" description="Notification settings." /></div>;


/* ---------------------------------------
 * MAIN SETTINGS VIEW
 * -------------------------------------*/

const SettingsView = ({ resetDatabase }) => {
  const [active, setActive] = useState("workspace");

  const renderPanel = () => {
    switch (active) {
      case "profile":
        return <ProfilePanel />;
      case "workspace":
        return <WorkspacePanel />;
      case "billing":
        return <BillingPanel />;
      case "access":
        return <AccessPanel />;
      case "api":
        return <ApiKeysPanel />;
      case "integrations":
        return <IntegrationsPanel />;
      case "alerts":
        return <AlertsPanel />;
      case "danger":
        return <DangerZonePanel onReset={resetDatabase} />;
      default:
        return <WorkspacePanel />;
    }
  };

  return (
    <div className="max-w-6xl mx-auto h-full">
      {/* Top header */}
      <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <Settings size={18} className="text-aureon-gold" />
          <div>
            <h1 className="text-sm font-semibold text-ink-strong uppercase tracking-wide">
              Settings
            </h1>
            <p className="text-[11px] text-ink-muted">
              Workspace-level controls for Aureon. Designed for ops, risk and
              engineering teams.
            </p>
          </div>
        </div>
      </div>

      {/* Shell */}
      <div className="flex gap-4 items-stretch">
        {/* Side nav */}
        <div className="w-56 border border-slate-200 rounded-md bg-white">
          {SECTIONS.map(({ id, label, icon: Icon }) => {
            const activeTab = active === id;
            return (
              <button
                key={id}
                onClick={() => setActive(id)}
                className={[
                  "w-full flex items-center justify-between px-3 py-2 text-[11px] border-b border-slate-200 last:border-b-0",
                  activeTab
                    ? "bg-slate-900 text-white"
                    : "bg-white text-ink-strong hover:bg-slate-50",
                ].join(" ")}
              >
                <span className="flex items-center gap-2">
                  <Icon size={13} />
                  <span>{label}</span>
                </span>
              </button>
            );
          })}
        </div>

        {/* Active panel only */}
        <div className="flex-1 flex flex-col gap-3">
          {renderPanel()}
        </div>
      </div>
    </div>
  );
};

export default SettingsView;