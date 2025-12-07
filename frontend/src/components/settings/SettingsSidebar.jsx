import React from "react";
import {
  User,
  Building2,
  CreditCard,
  KeyRound,
  Shield,
  Bell,
  PlugZap,
  AlertTriangle,
} from "lucide-react";

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

const SettingsSidebar = ({ active, onSelect }) => {
  return (
    <div className="w-56 border border-slate-200 rounded-md bg-white">
      {SECTIONS.map(({ id, label, icon: Icon }) => {
        const activeTab = active === id;
        return (
          <button
            key={id}
            onClick={() => onSelect(id)}
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
            {activeTab && (
              <span className="text-[9px] font-mono text-slate-200">
                ACTIVE
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

export default SettingsSidebar;