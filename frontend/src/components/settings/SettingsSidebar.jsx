import React, { useEffect, useCallback } from "react";
import {
  User,
  Building2,
  CreditCard,
  KeyRound,
  Shield,
  Bell,
  PlugZap,
  AlertTriangle,
  ScrollText,
} from "lucide-react";

const SECTIONS = [
  {
    group: "CORE",
    items: [
      { id: "profile", label: "Profile", icon: User },
      { id: "workspace", label: "Workspace", icon: Building2 },
    ],
  },
  {
    group: "SECURITY",
    items: [
      { id: "access", label: "Access Control", icon: Shield },
      { id: "api", label: "API Keys", icon: KeyRound },
      { id: "audit", label: "Audit Log", icon: ScrollText },
    ],
  },
  {
    group: "BILLING",
    items: [{ id: "billing", label: "Usage & Billing", icon: CreditCard }],
  },
  {
    group: "INTEGRATIONS",
    items: [
      { id: "integrations", label: "Connections", icon: PlugZap },
      { id: "alerts", label: "Alerts", icon: Bell },
    ],
  },
  {
    group: "SYSTEM",
    items: [{ id: "danger", label: "Danger Zone", icon: AlertTriangle }],
  },
];

const allIds = SECTIONS.flatMap((s) => s.items.map((i) => i.id));

const SettingsSidebar = ({ active, onSelect }) => {
  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const currentIdx = allIds.indexOf(active);
        if (currentIdx === -1) return;
        const nextIdx =
          e.key === "ArrowDown"
            ? Math.min(currentIdx + 1, allIds.length - 1)
            : Math.max(currentIdx - 1, 0);
        onSelect(allIds[nextIdx]);
      }
    },
    [active, onSelect]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="w-56 backdrop-blur-xl bg-white/60 border border-slate-200/50 rounded-xl flex flex-col shadow-sm">
      {/* Sidebar sections */}
      <div className="flex-1">
        {SECTIONS.map(({ group, items }) => (
          <div key={group}>
            {/* Group label */}
            <div className="px-3 pt-4 pb-1">
              <span className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase">
                {group}
              </span>
            </div>

            {/* Items */}
            {items.map(({ id, label, icon: Icon }) => {
              const isActive = active === id;
              const isDanger = id === "danger";

              const baseClasses =
                "w-full flex items-center justify-between px-3 py-2 text-xs transition-colors border-l";

              const stateClasses = isActive
                ? isDanger
                  ? "bg-red-50/80 backdrop-blur-sm text-red-700 border-red-400"
                  : "bg-slate-100/80 backdrop-blur-sm text-ink-strong border-slate-400"
                : isDanger
                ? "text-red-600 border-transparent hover:bg-red-50/50 hover:text-red-700"
                : "text-ink-muted border-transparent hover:bg-slate-50/60 hover:text-ink-strong";

              return (
                <button
                  key={id}
                  onClick={() => onSelect(id)}
                  className={[baseClasses, stateClasses].join(" ")}
                >
                  <span className="flex items-center gap-2">
                    <Icon size={13} />
                    <span>{label}</span>
                  </span>
                  {isActive && (
                    <span className="text-[9px] font-mono text-slate-500">●</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Bottom status ticker */}
      <div className="border-t border-slate-200/50 px-3 py-2">
        <div className="space-y-1 text-[10px] font-mono text-ink-muted">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span>All systems nominal</span>
          </div>
          <div className="text-slate-500">↑↓ Navigate · Enter Select</div>
        </div>
      </div>
    </div>
  );
};

export default SettingsSidebar;
