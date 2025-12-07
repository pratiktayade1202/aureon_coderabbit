import React from "react";
import { Key } from "lucide-react";

const ApiKeysPanel = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">API Keys</h2>

      <p className="text-sm text-ink-muted mb-4">
        Manage API credentials for programmatic access.
      </p>

      <div className="border border-aureon-border rounded-md p-4">
        <p className="text-sm font-mono text-ink-muted">No API keys generated yet.</p>
      </div>
    </div>
  );
};

export default ApiKeysPanel;
