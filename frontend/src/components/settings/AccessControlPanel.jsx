import React, { useState } from "react";
import { Shield, Globe, Clock, KeyRound, AlertTriangle } from "lucide-react";
import {
  TerminalCard,
  SectionHeader,
  SectionDivider,
  Tag,
  Toggle,
} from "./SettingsShared";

const AccessControlPanel = () => {
  const [ipEnforced, setIpEnforced] = useState(false);
  const [mfaRequired, setMfaRequired] = useState(true);
  const [hardwareKey, setHardwareKey] = useState(false);

  return (
    <TerminalCard>
      <SectionHeader
        title="Access Control"
        description="Enterprise security policies for workspace access. Changes take effect immediately."
      />

      {/* IP Whitelisting Section */}
      <SectionDivider label="IP Whitelisting" />
      <div className="space-y-3">
        <p className="text-xs text-ink-muted">
          Restrict Aureon access to approved networks. Changes may immediately
          disconnect active sessions.
        </p>

        <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
          <div className="space-y-1.5 text-[12px] font-mono">
            <div className="flex items-center justify-between rounded-md px-2 py-1.5 text-ink-strong hover:bg-white/60">
              <span>192.168.1.0/24</span>
              <span className="text-slate-500">Office VPN</span>
            </div>
            <div className="flex items-center justify-between rounded-md px-2 py-1.5 text-ink-strong hover:bg-white/60">
              <span>10.0.0.0/16</span>
              <span className="text-slate-500">Internal Network</span>
            </div>
            <div className="flex items-center justify-between rounded-md px-2 py-1.5 text-ink-strong hover:bg-white/60">
              <span>203.45.67.0/24</span>
              <span className="text-slate-500">Mumbai DC</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-1">
          <div className="flex items-center gap-2">
            <Globe size={14} className="text-slate-500" />
            <span className="text-sm text-ink-strong">Enforce IP Restrictions</span>
            <Tag variant="warning">Pilot Only</Tag>
          </div>
          <Toggle checked={ipEnforced} onChange={setIpEnforced} />
        </div>
      </div>

      {/* Session Policy Section */}
      <SectionDivider label="Session Policy" />
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={14} className="text-slate-500" />
            <span className="text-sm text-ink-strong">Session Timeout</span>
          </div>
          <select className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm font-mono text-ink-strong focus:outline-none focus:ring-1 focus:ring-aureon-gold">
            <option>15 minutes</option>
            <option>1 hour</option>
            <option defaultValue>4 hours</option>
            <option>Full Trading Day (8h)</option>
          </select>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={14} className="text-slate-500" />
            <span className="text-sm text-ink-strong">Max Concurrent Sessions</span>
          </div>
          <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-sm font-mono text-amber-700">
            3
          </span>
        </div>

        <p className="text-[11px] text-ink-muted">
          Shorter timeouts are recommended for trading desks with wire approval
          permissions.
        </p>
      </div>

      {/* MFA Section */}
      <SectionDivider label="Multi-Factor Authentication" />
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound size={14} className="text-slate-500" />
            <span className="text-sm text-ink-strong">Require MFA for all users</span>
            <Tag variant="success">Recommended</Tag>
          </div>
          <Toggle checked={mfaRequired} onChange={setMfaRequired} />
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound size={14} className="text-slate-500" />
            <span className="text-sm text-ink-strong">Require Hardware Key (YubiKey)</span>
            <Tag>Optional</Tag>
          </div>
          <Toggle checked={hardwareKey} onChange={setHardwareKey} />
        </div>

        <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <AlertTriangle
            size={14}
            className="mt-0.5 flex-shrink-0 text-amber-500"
          />
          <p className="text-[11px] text-amber-800">
            Hardware key enforcement is recommended for users with wire approval
            permissions.
          </p>
        </div>
      </div>

      {/* Current Status */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
        <span className="text-[11px] font-mono text-ink-muted">
          Current mode: Single-user workspace · Full access
        </span>
        <Tag variant="info">Owner</Tag>
      </div>
    </TerminalCard>
  );
};

export default AccessControlPanel;
