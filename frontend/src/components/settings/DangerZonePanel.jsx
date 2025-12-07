import React from "react";
import { AlertTriangle } from "lucide-react";

const DangerZonePanel = () => {
  return (
    <div className="bg-white border border-red-200 rounded-md p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-red-600" size={14} />
          <div>
            <p className="text-[11px] font-semibold text-red-700 uppercase">
              Danger Zone
            </p>
            <p className="text-[10px] text-red-600">
              Use only under guidance. This is not reversible.
            </p>
          </div>
        </div>
        <button className="px-2.5 py-1 text-[11px] rounded-md border border-red-500 text-red-700 hover:bg-red-50">
          Reset Workspace
        </button>
      </div>
    </div>
  );
};

export default DangerZonePanel;