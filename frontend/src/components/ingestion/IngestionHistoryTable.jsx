// src/components/ingestion/IngestionHistoryTable.jsx
import React from "react";
import { Clock3, CheckCircle2, AlertTriangle } from "lucide-react";

/**
 * IngestionHistoryTable
 * Bottom section: recent runs, status, row counts.
 * Static demo data for now.
 */
const SAMPLE_HISTORY = [
  {
    id: "RUN-2025-12-07-01",
    file: "01_trades_standard.csv",
    source: "Broker",
    rows: 4821,
    status: "Completed",
    at: "03:11 IST",
  },
  {
    id: "RUN-2025-12-07-02",
    file: "04_cash_ledger_hdfc.csv",
    source: "Bank",
    rows: 1298,
    status: "Completed",
    at: "03:16 IST",
  },
  {
    id: "RUN-2025-12-07-03",
    file: "07_holdings_cdsl_typo.csv",
    source: "Custodian",
    rows: 774,
    status: "Warning",
    at: "03:22 IST",
  },
];

const statusChip = (status) => {
  if (status === "Completed") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700">
        <CheckCircle2 size={12} />
        Completed
      </span>
    );
  }
  if (status === "Warning") {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-amber-700">
        <AlertTriangle size={12} />
        Warning
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-ink-muted">
      {status}
    </span>
  );
};

const IngestionHistoryTable = () => {
  return (
    <div className="mt-4 border border-aureon-border rounded-md bg-paper-surface">
      <div className="px-4 py-2 border-b border-aureon-border flex items-center gap-2">
        <Clock3 size={14} className="text-ink-muted" />
        <p className="text-[11px] font-semibold text-ink-strong uppercase tracking-wide">
          Recent Ingestion Runs
        </p>
      </div>

      <div className="overflow-auto">
        <table className="w-full text-left border-collapse text-[11px]">
          <thead className="bg-paper-subtle border-b border-aureon-border">
            <tr>
              <th className="px-3 py-2 border-r border-aureon-border">Run ID</th>
              <th className="px-3 py-2 border-r border-aureon-border">File</th>
              <th className="px-3 py-2 border-r border-aureon-border">
                Source
              </th>
              <th className="px-3 py-2 border-r border-aureon-border text-right">
                Rows
              </th>
              <th className="px-3 py-2 border-r border-aureon-border">
                Status
              </th>
              <th className="px-3 py-2 text-right">Started</th>
            </tr>
          </thead>
          <tbody>
            {SAMPLE_HISTORY.map((run) => (
              <tr
                key={run.id}
                className="border-t border-aureon-border hover:bg-slate-50"
              >
                <td className="px-3 py-1.5 font-mono text-[10px] text-ink-muted border-r border-aureon-border">
                  {run.id}
                </td>
                <td className="px-3 py-1.5 text-ink-strong border-r border-aureon-border">
                  {run.file}
                </td>
                <td className="px-3 py-1.5 text-ink-muted border-r border-aureon-border">
                  {run.source}
                </td>
                <td className="px-3 py-1.5 text-right font-mono border-r border-aureon-border">
                  {run.rows.toLocaleString()}
                </td>
                <td className="px-3 py-1.5 border-r border-aureon-border">
                  {statusChip(run.status)}
                </td>
                <td className="px-3 py-1.5 text-right text-ink-muted">
                  {run.at}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IngestionHistoryTable;
