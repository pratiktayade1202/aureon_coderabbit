import React, { useState } from "react";
import { Settings } from "lucide-react";

// Components
import SettingsSidebar from "./SettingsSidebar";
import ProfilePanel from "./ProfilePanel";
import WorkspacePanel from "./WorkspacePanel";
import BillingPanel from "./BillingPanel";
import AccessControlPanel from "./AccessControlPanel";
import ApiKeysPanel from "./ApiKeysPanel";
import IntegrationsPanel from "./IntegrationsPanel";
import AlertsPanel from "./AlertsPanel";
import DangerZonePanel from "./DangerZonePanel";

const SettingsLayout = () => {
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
        return <AccessControlPanel />;
      case "api":
        return <ApiKeysPanel />;
      case "integrations":
        return <IntegrationsPanel />;
      case "alerts":
        return <AlertsPanel />;
      case "danger":
        return <DangerZonePanel />;
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
        <SettingsSidebar active={active} onSelect={setActive} />

        {/* Active panel + tiny danger zone footer */}
        <div className="flex-1 flex flex-col gap-3">
          {renderPanel()}
          
          {/* Always keep danger zone tiny and at bottom, regardless of active tab */}
          <div className="w-full max-w-lg">
            <DangerZonePanel />
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsLayout;