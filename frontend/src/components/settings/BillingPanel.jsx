import React from "react";
import { CreditCard, TrendingUp, Download, FileText } from "lucide-react";
import {
  TerminalCard,
  SectionHeader,
  SectionDivider,
  FieldRow,
  Tag,
} from "./SettingsShared";

const USAGE_DATA = [
  { metric: "NAV recons run", current: 38, limit: "100 / month", pct: 38 },
  { metric: "Breaks created", current: 212, limit: "Unlimited", pct: null },
  { metric: "Ingestion jobs", current: 126, limit: "500 / month", pct: 25 },
  { metric: "API calls", current: "4,231", limit: "10,000 / month", pct: 42 },
  { metric: "Storage (GB)", current: "2.4", limit: "10 GB", pct: 24 },
];

// Simple inline bar chart for spend projection
const SpendProjection = () => {
  const days = [
    { day: 1, spend: 412 },
    { day: 5, spend: 1850 },
    { day: 10, spend: 4200 },
    { day: 15, spend: 7100 },
    { day: 20, spend: 9800 },
    { day: 25, spend: 12340 },
    { day: 30, spend: 18900 },
  ];
  const maxSpend = 20000;

  return (
    <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-mono uppercase tracking-wider text-slate-500">
          30-day spend projection (demo)
        </span>
        <TrendingUp size={12} className="text-emerald-600" />
      </div>
      <div className="flex h-14 items-end gap-1">
        {days.map((d, i) => (
          <div key={i} className="flex flex-1 flex-col items-center gap-0.5">
            <div
              className="w-full rounded-t bg-emerald-500/80"
              style={{ height: `${(d.spend / maxSpend) * 48}px` }}
            />
            <span className="text-[9px] font-mono text-slate-500">
              {d.day}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between border-t border-slate-200 pt-1.5">
        <span className="text-[10px] font-mono text-slate-500">Day of month</span>
        <span className="text-[10px] font-mono text-ink-muted">
          Projected: $18,900
        </span>
      </div>
    </div>
  );
};

const BillingPanel = () => {
  return (
    <TerminalCard>
      <SectionHeader
        title="Usage & Billing"
        description="Track plan details, usage metrics, and cost projections for this workspace."
      />

      {/* Spend summary - AWS invoice style */}
      <div className="mb-4 grid grid-cols-4 gap-3 text-xs font-mono">
        <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
          <span className="block text-[10px] text-slate-500">Current Month</span>
          <span className="text-lg text-emerald-700">$12,340.42</span>
        </div>
        <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
          <span className="block text-[10px] text-slate-500">Projected EOM</span>
          <span className="text-lg text-amber-700">$18,900.00</span>
        </div>
        <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
          <span className="block text-[10px] text-slate-500">Usage Tier</span>
          <span className="text-lg text-ink-strong">Enterprise</span>
        </div>
        <div className="rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/50 p-3">
          <span className="block text-[10px] text-slate-500">Billing Cycle</span>
          <span className="text-lg text-ink-muted">Dec 2025</span>
        </div>
      </div>

      {/* Projection chart */}
      <SpendProjection />

      {/* Plan details */}
      <SectionDivider label="Plan Details" />
      <div className="space-y-2">
        <FieldRow label="Plan">
          <div className="flex items-center justify-end gap-2">
            <span className="text-sm font-mono text-ink-strong">
              Founders (YC Demo)
            </span>
            <Tag variant="warning">Demo</Tag>
          </div>
        </FieldRow>
        <FieldRow label="Billing Contact">
          <span className="text-sm font-mono text-ink-muted">
            finance@hdfc-amc.example
          </span>
        </FieldRow>
        <FieldRow label="Payment Method">
          <div className="flex items-center justify-end gap-2">
            <CreditCard size={14} className="text-slate-500" />
            <span className="text-sm font-mono text-ink-muted">•••• 4242</span>
            <Tag>Visa</Tag>
          </div>
        </FieldRow>
      </div>

      {/* Usage table */}
      <SectionDivider label="Usage Breakdown" />
      <div className="overflow-hidden rounded-xl border border-slate-200/60 backdrop-blur-sm bg-white/60">
        <div className="grid grid-cols-4 gap-2 border-b border-slate-200/60 backdrop-blur-sm bg-white/40 px-2 py-1.5 text-[11px] font-mono uppercase tracking-wider text-slate-500">
          <span>Metric</span>
          <span className="text-right">Current</span>
          <span className="text-right">Limit</span>
          <span className="text-right">Usage</span>
        </div>
        {USAGE_DATA.map((row, idx) => (
          <div
            key={idx}
            className="grid grid-cols-4 gap-2 border-t border-slate-200/40 px-2 py-1.5 text-[11px] font-mono hover:bg-white/50"
          >
            <span className="text-ink-strong">{row.metric}</span>
            <span className="text-right text-amber-700">{row.current}</span>
            <span className="text-right text-ink-muted">{row.limit}</span>
            <span className="text-right">
              {row.pct !== null ? (
                <div className="flex items-center justify-end gap-1.5">
                  <div className="h-1.5 w-12 overflow-hidden rounded bg-slate-100">
                    <div
                      className={`h-full rounded ${
                        row.pct > 80
                          ? "bg-red-500"
                          : row.pct > 50
                          ? "bg-amber-500"
                          : "bg-emerald-500"
                      }`}
                      style={{ width: `${row.pct}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-ink-muted">
                    {row.pct}%
                  </span>
                </div>
              ) : (
                <span className="text-slate-400">—</span>
              )}
            </span>
          </div>
        ))}
      </div>

      {/* Footer actions */}
      <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
        <span className="text-[11px] font-mono text-ink-muted">
          Overages pro-rated in production. Demo workspace: not billed.
        </span>
        <div className="flex items-center gap-2">
          <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
            <FileText size={11} />
            View Invoices
          </button>
          <button className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-mono text-ink-muted hover:bg-slate-50">
            <Download size={11} />
            Export CSV
          </button>
        </div>
      </div>
    </TerminalCard>
  );
};

export default BillingPanel;
