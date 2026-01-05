// src/components/dashboard/UtilityBar.jsx
import React from "react";
import {
  Download,
  FileClock,
  SlidersHorizontal,
  Layers,
  Database,
} from "lucide-react";

const UtilityBar = ({
  onExport,
  onAudit,
  onRun,
  onAutoResolve,
  showAi,
  isProcessing,
  pendingCount,
}) => {
  return (
    <div className="w-full bg-paper-surface border border-aureon-border rounded-md px-4 py-2 mb-4 flex items-center justify-between shadow-sm">
      {/* LEFT SIDE */}
      <div className="flex items-center gap-3">
        {/* Filters */}
        <button className="h-8 px-3 text-[11px] border border-aureon-border rounded-md bg-paper-subtle text-ink-muted hover:bg-slate-50 flex items-center gap-1">
          <SlidersHorizontal size={12} />
          Filters
        </button>

        {/* Workspace (placeholder for now) */}
        <button className="h-8 px-3 text-[11px] border border-aureon-border rounded-md bg-paper-subtle text-ink-muted hover:bg-slate-50 flex items-center gap-1">
          <Layers size={12} />
          Workspace
        </button>
      </div>

      {/* RIGHT SIDE */}
      <div className="flex items-center gap-3">
        {/* Audit Trail */}
        <button
          onClick={onAudit}
          className="h-8 w-8 flex items-center justify-center border border-aureon-border rounded-md text-ink-muted hover:bg-slate-50"
        >
          <FileClock size={14} />
        </button>

        {/* Export */}
        <button
          onClick={onExport}
          className="h-8 px-3 text-[11px] border border-aureon-border rounded-md bg-paper-subtle text-ink-strong hover:bg-slate-50 flex items-center gap-1"
        >
          <Download size={12} /> Export
        </button>

        {/* Auto Resolve */}
        {showAi ? (
          <button
            onClick={onAutoResolve}
            disabled={isProcessing}
            className="h-8 px-4 text-[11px] rounded-md bg-aureon-blue text-white font-semibold hover:bg-blue-700 disabled:opacity-70 flex items-center gap-2"
          >
            <Database size={12} />
            Auto-Resolve ({pendingCount})
          </button>
        ) : (
          <button
            onClick={onRun}
            disabled={isProcessing}
            className="h-8 px-4 text-[11px] rounded-md bg-slate-900 text-white font-semibold hover:bg-black disabled:opacity-70 flex items-center gap-2"
          >
            <Database size={12} />
            Run Settlement
          </button>
        )}
      </div>
    </div>
  );
};

export default UtilityBar;
