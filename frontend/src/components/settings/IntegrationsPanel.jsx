import React from "react";
import { PlugZap } from "lucide-react";

const IntegrationsPanel = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">Integrations</h2>
      <p className="text-sm text-ink-muted mb-4">External connectors coming soon.</p>

      <div className="border border-aureon-border rounded-md p-4 flex items-center gap-3">
        <PlugZap size={20} className="text-ink-muted" />
        <p className="text-sm">No integrations configured.</p>
      </div>
    </div>
  );
};

export default IntegrationsPanel;
