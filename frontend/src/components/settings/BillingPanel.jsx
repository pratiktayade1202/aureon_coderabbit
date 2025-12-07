import React from "react";
import { CreditCard } from "lucide-react";

const BillingPanel = () => {
  return (
    <div>
      <h2 className="text-lg font-semibold text-ink-strong mb-4">Billing & Usage</h2>

      <p className="text-sm text-ink-muted mb-4">
        Billing integration coming soon. Track usage and plan limits here.
      </p>

      <div className="border border-aureon-border rounded-md p-4 flex items-center gap-3">
        <CreditCard size={20} className="text-ink-muted" />
        <p className="text-sm text-ink-muted">No billing information available.</p>
      </div>
    </div>
  );
};

export default BillingPanel;
