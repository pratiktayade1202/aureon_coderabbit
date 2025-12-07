import React from "react";
import { ShieldCheck } from "lucide-react";

const AccessControlPanel = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">Access Control</h2>
      <p className="text-sm text-ink-muted mb-4">
        RBAC (role-based access control) will be added for multi-user workspaces.
      </p>

      <div className="border border-aureon-border rounded-md p-4 flex items-center gap-3">
        <ShieldCheck size={20} className="text-ink-muted" />
        <p className="text-sm">Single-user workspace · Full access</p>
      </div>
    </div>
  );
};

export default AccessControlPanel;
