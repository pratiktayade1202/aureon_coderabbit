import React from "react";
import { useUser } from "@clerk/clerk-react";
import { User, Shield, Key, Clock, LogOut } from "lucide-react";
import {
  TerminalCard,
  SectionHeader,
  FieldRow,
  Tag,
  StatusDot,
} from "./SettingsShared";

const ProfilePanel = ({ onLogout }) => {
  const { user } = useUser();

  const name = user?.fullName || "Aureon User";
  const email = user?.primaryEmailAddress?.emailAddress || "demo@example.com";
  const userId = user?.id?.slice(0, 12) || "usr_demo_001";

  return (
    <TerminalCard>
      <SectionHeader
        title="Profile"
        description="Your identity and workspace-level role within this Aureon deployment."
      />

      {/* Profile header */}
      <div className="mb-4 flex items-center gap-3 border-b border-slate-200 pb-3">
        <div className="relative">
          {user?.imageUrl ? (
            <img
              src={user.imageUrl}
              alt={name}
              className="h-12 w-12 rounded-lg border border-slate-200 bg-white object-cover"
            />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-slate-200 bg-slate-50">
              <User size={20} className="text-slate-500" />
            </div>
          )}
          <div className="absolute -bottom-1 -right-1">
            <StatusDot status="healthy" />
          </div>
        </div>
        <div>
          <p className="text-sm font-semibold text-ink-strong">{name}</p>
          <p className="text-xs font-mono text-ink-muted">{email}</p>
          <p className="mt-0.5 text-[11px] font-mono text-slate-500">ID: {userId}</p>
        </div>
      </div>

      {/* Profile details */}
      <div className="space-y-2">
        <FieldRow label="Workspace Role">
          <div className="flex items-center justify-end gap-2">
            <Shield size={13} className="text-aureon-gold" />
            <Tag variant="warning">Owner</Tag>
            <span className="text-[11px] font-mono text-ink-muted">Full access</span>
          </div>
        </FieldRow>

        <FieldRow label="Auth Provider">
          <div className="flex items-center justify-end gap-2">
            <Key size={13} className="text-slate-500" />
            <span className="text-xs font-mono text-ink-strong">
              Clerk · Email / SSO
            </span>
          </div>
        </FieldRow>

        <FieldRow label="MFA Status">
          <div className="flex items-center justify-end gap-2">
            <StatusDot status="healthy" />
            <span className="text-xs font-mono text-emerald-700">Enabled</span>
            <Tag variant="success">TOTP</Tag>
          </div>
        </FieldRow>

        <FieldRow label="Session">
          <div className="flex items-center justify-end gap-2">
            <Clock size={13} className="text-slate-500" />
            <span className="text-[11px] font-mono text-ink-muted">
              Active · Expires in 3h 42m
            </span>
          </div>
        </FieldRow>

        <FieldRow label="Last Login">
          <span className="text-[11px] font-mono text-ink-muted">
            2025-12-09T08:15:32Z · 192.168.1.45
          </span>
        </FieldRow>
      </div>

      {/* Session info */}
      <div className="mt-4 border-t border-slate-200 pt-3">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-mono text-ink-muted">
            Session: secure cookie · Browser: Chrome 120
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 rounded-md border border-red-200 px-2 py-1 text-[11px] font-mono text-red-600 hover:bg-red-50"
            >
              <LogOut size={11} />
              Logout
            </button>
          )}
        </div>
      </div>
    </TerminalCard>
  );
};

export default ProfilePanel;
