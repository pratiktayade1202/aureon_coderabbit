import React from "react";
import { Bell } from "lucide-react";

const AlertsPanel = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">Alerts</h2>

      <p className="text-sm text-ink-muted mb-4">
        Configure alerting for breaks, NAV deviations, and failed ingestions.
      </p>

      <div className="border border-aureon-border rounded-md p-4">
        <p className="text-sm text-ink-muted">Alert engine not yet configured.</p>
      </div>
    </div>
  );
};

export default AlertsPanel;
