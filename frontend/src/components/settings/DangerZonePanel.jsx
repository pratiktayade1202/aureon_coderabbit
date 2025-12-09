import React from "react";
import { AlertTriangle } from "lucide-react";

const DangerZonePanel = () => {
  return (
    <div className="rounded-xl border border-red-200 bg-white p-4 shadow-sm">
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
        <button className="rounded-md border border-red-500 px-3 py-1.5 text-[11px] font-mono text-red-700 hover:bg-red-50">
          Reset Workspace
        </button>
      </div>
    </div>
  );
};

export default DangerZonePanel;
