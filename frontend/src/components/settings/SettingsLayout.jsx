import React, { useState, useEffect } from "react";
import { Settings, Command, Activity, Cpu, Database } from "lucide-react";

// Components
import SettingsSidebar from "./SettingsSidebar";
import ProfilePanel from "./ProfilePanel";
import WorkspacePanel from "./WorkspacePanel";
import BillingPanel from "./BillingPanel";
import AccessControlPanel from "./AccessControlPanel";
import ApiKeysPanel from "./ApiKeysPanel";
import IntegrationsPanel from "./IntegrationsPanel";
import AlertsPanel from "./AlertsPanel";
import AuditLogPanel from "./AuditLogPanel";
import DangerZonePanel from "./DangerZonePanel";

const SettingsLayout = () => {
  const [active, setActive] = useState("workspace");
  const [showCmdHint, setShowCmdHint] = useState(false);

  // Command palette keyboard shortcut stub
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setShowCmdHint(true);
        setTimeout(() => setShowCmdHint(false), 1500);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const renderPanel = () => {
    switch (active) {
      case "profile":
        return <ProfilePanel />;
      case "workspace":
        return <WorkspacePanel />;
      case "billing":
        return <BillingPanel />;
      case "access":
        return <AccessControlPanel />;
      case "api":
        return <ApiKeysPanel />;
      case "integrations":
        return <IntegrationsPanel />;
      case "alerts":
        return <AlertsPanel />;
      case "audit":
        return <AuditLogPanel />;
      case "danger":
        return <DangerZonePanel />;
      default:
        return <WorkspacePanel />;
    }
  };

  return (
    <div className="max-w-5xl mx-auto h-full">
      {/* Top header */}
      <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <Settings size={18} className="text-aureon-gold" />
          <div>
            <h1 className="text-sm font-semibold text-ink-strong uppercase tracking-wide flex items-center gap-2">
              System Configuration
              <span className="text-[11px] font-mono text-ink-muted normal-case">
                v2.4.1
              </span>
            </h1>
            <p className="text-xs text-ink-muted">
              Workspace controls · Security · Integrations · Audit
            </p>
          </div>
        </div>

        {/* Command palette hint */}
        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-mono transition-colors ${
              showCmdHint
                ? "border-amber-400 bg-amber-50 text-amber-700"
                : "border-slate-200 bg-white text-ink-muted"
            }`}
          >
            <Command size={11} />
            <span>{showCmdHint ? "Command palette coming soon..." : "⌘K"}</span>
          </div>
        </div>
      </div>

      {/* Shell */}
      <div className="flex gap-4 items-stretch">
        <SettingsSidebar active={active} onSelect={setActive} />

        {/* Active panel + danger zone footer */}
        <div className="flex-1 flex flex-col gap-4">
          {renderPanel()}

          {/* Always keep danger zone tiny and at bottom */}
          <div className="w-full max-w-lg">
            <DangerZonePanel />
          </div>
        </div>
      </div>

      {/* System status ticker - bottom of settings */}
      <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-4 text-[11px] font-mono text-ink-muted">
          <span className="flex items-center gap-1">
            <Activity size={11} className="text-emerald-500" />
            <span>Latency:</span>
            <span className="text-emerald-600">12ms</span>
          </span>
          <span className="flex items-center gap-1">
            <Database size={11} className="text-emerald-500" />
            <span>Ingestion:</span>
            <span className="text-emerald-600">Operational</span>
          </span>
          <span className="flex items-center gap-1">
            <Cpu size={11} className="text-emerald-500" />
            <span>AI:</span>
            <span className="text-emerald-600">Healthy</span>
          </span>
        </div>
        <span className="text-[10px] font-mono text-ink-muted">
          Region: AWS ap-south-1 · Session: 847ms
        </span>
      </div>
    </div>
  );
};

export default SettingsLayout;
