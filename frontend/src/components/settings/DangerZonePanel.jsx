import React from "react";
import { AlertTriangle } from "lucide-react";

const DangerZonePanel = ({ onReset }) => {
  const handleReset = () => {
    if (!onReset) return;
    if (window.confirm("Are you sure you want to reset the workspace? This will delete all data for your tenant and is not reversible.")) {
      onReset();
    }
  };

  return (
    <div className="rounded-xl border border-red-200/60 backdrop-blur-sm bg-white/70 p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-red-600" size={16} />
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-red-700">
              Danger Zone
            </p>
            <p className="text-[11px] text-red-600">
              Use only under guidance. This action is not reversible.
            </p>
          </div>
        </div>
        <button
          onClick={handleReset}
          disabled={!onReset}
          className="rounded-md border border-red-500 px-3 py-1.5 text-[11px] font-mono text-red-700 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Reset Workspace
        </button>
      </div>
    </div>
  );
};

export default DangerZonePanel;
