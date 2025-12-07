import React from "react";
import { SectionHeader, FieldRow, Tag } from "./SettingsShared";

const WorkspacePanel = () => {
  return (
    <div className="bg-white border border-slate-200 rounded-md p-4">
      <SectionHeader
        title="Workspace"
        description="Workspace-level configuration that applies to all users and funds onboarded to Aureon."
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
            <button className="text-[11px] text-blue-600 hover:underline">
              Request Production Workspace
            </button>
          </div>
        </FieldRow>

        <FieldRow label="Workspace ID">
          <div className="flex items-center justify-end gap-2">
            <code className="text-[11px] font-mono bg-slate-100 px-2 py-0.5 rounded">
              AUR-WSPC-883-A
            </code>
            <button className="text-[10px] text-blue-600 hover:underline">
              Copy
            </button>
          </div>
        </FieldRow>
      </div>
    </div>
  );
};

export default WorkspacePanel;