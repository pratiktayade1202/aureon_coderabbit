// src/components/Sidebar.jsx
import React from "react";
import {
  LayoutDashboard,
  FileInput,
  BrainCircuit,
  Settings,
  Building2,
  LogOut,
} from "lucide-react";
import { useUser, useClerk } from "@clerk/clerk-react";
import logo from "../assets/logo.png";

/**
 * Titanium Sidebar
 * - Fixed-width rail
 * - High-density nav
 * - No softness, no glow
 */
const NAV_ITEMS = [
  { id: "Dashboard", name: "Overview", icon: LayoutDashboard },
  { id: "Ingestion", name: "Ingestion", icon: FileInput },
  { id: "Neural Core", name: "Neural Core", icon: BrainCircuit },
  { id: "Settings", name: "Settings", icon: Settings },
];

const Sidebar = ({ activeTab, setActiveTab }) => {
  const { user, isLoaded } = useUser();
  const { signOut } = useClerk();

  return (
    <aside className="fixed top-0 left-0 h-screen w-60 bg-paper-surface border-r border-aureon-border flex flex-col z-40">
      {/* Product identity */}
      <div className="h-14 flex items-center px-4 border-b border-aureon-border bg-slate-50">
        <div className="flex items-center gap-3 overflow-hidden">
          <img src={logo} alt="Aureon" className="w-6 h-6 object-contain" />
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-ink-strong tracking-tight">
              AUREON
            </span>
            <span className="text-[9px] font-mono text-ink-faint uppercase tracking-[0.2em]">
              Titanium
            </span>
          </div>
        </div>
      </div>

      {/* Context: workspace / fund (can be wired later) */}
      <div className="px-3 py-3 border-b border-aureon-border bg-paper-cream">
        <div className="flex items-center gap-2 px-3 py-2 bg-paper-surface border border-aureon-border rounded-md">
          <Building2 size={14} className="text-ink-faint" />
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-ink-strong truncate">
              HDFC AMC (Sandbox)
            </span>
            <span className="text-[10px] font-mono text-ink-faint truncate">
              Workspace ID: AUR-883A
            </span>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-semibold transition-colors
                ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-ink-muted hover:bg-slate-100 hover:text-ink-strong"
                }`}
            >
              <Icon
                size={16}
                className={
                  isActive ? "text-white" : "text-ink-faint group-hover:text-ink-muted"
                }
              />
              <span className="truncate">{item.name}</span>
            </button>
          );
        })}
      </nav>

      {/* User block */}
      <div className="px-3 py-3 border-t border-aureon-border bg-slate-50">
        <div className="flex items-center gap-2">
          <img
            src={user?.imageUrl}
            alt="User"
            className="w-7 h-7 rounded-sm border border-aureon-border object-cover"
          />
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-ink-strong truncate">
              {isLoaded ? user?.fullName || "User" : "Loading..."}
            </span>
            <span className="text-[10px] text-ink-faint truncate">
              Analyst · Aureon
            </span>
          </div>
          <button
            onClick={() => signOut()}
            className="ml-auto p-1.5 text-ink-faint hover:text-status-danger"
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
