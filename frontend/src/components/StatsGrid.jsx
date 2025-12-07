// src/components/StatsGrid.jsx
import React from "react";
import { TrendingUp, AlertTriangle, ShieldCheck } from "lucide-react";

/**
 * Titanium KPI card
 * - No glow, no softness
 * - Compact, data-first
 */
const StatCard = ({ label, value, hint, tone }) => {
  const toneMap = {
    neutral: "text-ink-muted bg-slate-50 border-aureon-border",
    positive: "text-status-success bg-emerald-50 border-emerald-200",
    warning: "text-status-warning bg-amber-50 border-amber-200",
  };

  const toneClass = toneMap[tone] || toneMap.neutral;

  return (
    <div className="bg-paper-surface border border-aureon-border rounded-md px-4 py-3 flex flex-col gap-2">
      <span className="text-[11px] font-semibold tracking-wide text-ink-muted uppercase">
        {label}
      </span>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xl font-mono font-semibold text-ink-strong tabular-nums">
          {value}
        </span>
      </div>
      {hint && (
        <div
          className={`inline-flex items-center gap-1 px-2 py-1 rounded-sm border text-[11px] ${toneClass}`}
        >
          {tone === "positive" && <TrendingUp size={12} />}
          {tone === "warning" && <AlertTriangle size={12} />}
          {tone === "neutral" && <ShieldCheck size={12} />}
          <span>{hint}</span>
        </div>
      )}
    </div>
  );
};

const StatsGrid = ({ stats }) => {
  const totalAssets = stats?.total_assets || 0;
  const pending = stats?.pending_settlements || 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      <StatCard
        label="Assets Under Custody"
        value={`₹${totalAssets.toLocaleString("en-IN")}`}
        hint="Last NAV snapshot"
        tone="neutral"
      />
      <StatCard
        label="Pending Settlements"
        value={pending}
        hint={pending > 0 ? "Action required" : "All clear"}
        tone={pending > 0 ? "warning" : "positive"}
      />
      <StatCard
        label="Recon Accuracy"
        value="99.9%"
        hint="AI validation (7d window)"
        tone="positive"
      />
    </div>
  );
};

export default React.memo(StatsGrid);
