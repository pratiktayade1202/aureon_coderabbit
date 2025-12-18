// src/components/DataTable.jsx
import React, { useEffect, useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
} from "@tanstack/react-table";
import {
  ArrowUpDown,
  Wrench,
  AlertCircle,
  CheckCircle2,
  Clock,
  ChevronLeft,
  ChevronRight,
  Layers,
  Square,
  CheckSquare,
} from "lucide-react";

// Numeric formatters with terminal-like precision
const formatCurrency = (val) => {
  if (val === null || val === undefined || val === "") return "-";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(Number(val));
};

const formatNumber = (val) => {
  if (val === null || val === undefined || val === "") return "-";
  return new Intl.NumberFormat("en-US").format(Number(val));
};

// Status badge with traffic-light confidence for AI matches
const StatusCell = ({ value, bankRef }) => {
  let statusStr = "UNSETTLED";

  if (typeof value === "object" && value !== null) {
    statusStr = value.status || "UNSETTLED";
  } else if (typeof value === "string") {
    statusStr = value;
  }

  const status = String(statusStr || "UNSETTLED").toUpperCase();

  // 1) Breaks (Red)
  if (status === "BREAK") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-red-50 text-red-700 border border-red-200">
        <AlertCircle size={12} /> ESCALATED
      </span>
    );
  }

  // 2) Matches (AI / Manual / Rule)
  if (status === "MATCHED" || status.includes("SETTLED") || status.includes("MATCH")) {
    const ref = String(bankRef || "");
    const refUpper = ref.toUpperCase();
    const isAi = refUpper.startsWith("AI:") || refUpper.startsWith("AI") || refUpper.includes("AI AUTO-RESOLVED");
    const isManual = refUpper.startsWith("MANUAL:") || refUpper.includes("MANUAL");
    const isRule = refUpper.startsWith("RULE:") || refUpper.includes("RULE");

    if (isAi) {
      // Extract confidence: "AI: ... (conf: 0.95)"
      let confidence = 0;
      const match = ref.match(/conf[:\s]+(0\.\d+|1(?:\.0+)?)/i);
      if (match) confidence = parseFloat(match[1]);
      const pct = confidence > 0 ? `${(confidence * 100).toFixed(0)}%` : "";

      if (confidence >= 0.9) {
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
            <CheckCircle2 size={12} /> AI MATCH {pct}
          </span>
        );
      } else if (confidence >= 0.8) {
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-purple-50 text-purple-600 border border-purple-200">
            <CheckCircle2 size={12} /> AI MATCH {pct}
          </span>
        );
      } else {
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertCircle size={12} /> LOW CONFIDENCE {pct}
          </span>
        );
      }
    }

    // Manual / Rule match (Green)
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold border ${
          isManual
            ? "bg-emerald-50 text-emerald-700 border-emerald-200"
            : "bg-green-50 text-green-700 border-green-200"
        }`}
      >
        {isManual ? <Wrench size={12} /> : <CheckCircle2 size={12} />}
        {isManual ? "MANUAL MATCH" : isRule ? "RULE MATCH" : "MATCHED"}
      </span>
    );
  }

  // 3) Unsettled / fallback
  if (status === "UNSETTLED") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
        <Clock size={12} /> UNSETTLED
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
      <Clock size={12} /> {status}
    </span>
  );
};

/**
 * Titanium Ledger Table
 * - High density
 * - Vertical dividers
 * - Terminal-like typography
 */
const DataTable = ({
  view,
  reconData,
  holdingsData,
  navData,
  onResolve,
  onSelectionChange,
  selectionResetKey,
}) => {
  const [rowSelection, setRowSelection] = useState({});

  // Clear selection when switching views or after parent-triggered reset
  useEffect(() => {
    setRowSelection({});
  }, [view, selectionResetKey]);

  // Notify parent when selection changes (Trades view only)
  useEffect(() => {
    if (!onSelectionChange) return;
    if (view !== "Trades") {
      onSelectionChange([]);
      return;
    }

    const selectedIds = Object.keys(rowSelection)
      .map((k) => parseInt(k, 10))
      .filter((n) => Number.isFinite(n));

    onSelectionChange(selectedIds);
  }, [rowSelection, onSelectionChange, view]);

  const columns = useMemo(() => {
    if (view === "Trades") {
      const selectColumn = {
        id: "select",
        header: ({ table }) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              table.getToggleAllRowsSelectedHandler()(e);
            }}
            className="p-1 hover:bg-slate-200 rounded text-slate-500"
            aria-label="Select all"
            title="Select all"
          >
            {table.getIsAllRowsSelected() ? (
              <CheckSquare size={14} />
            ) : (
              <Square size={14} />
            )}
          </button>
        ),
        cell: ({ row }) => (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              row.getToggleSelectedHandler()(e);
            }}
            className={`p-1 rounded ${
              row.getIsSelected()
                ? "text-aureon-blue"
                : "text-slate-300 hover:text-slate-500"
            }`}
            aria-label="Select row"
            title="Select row"
          >
            {row.getIsSelected() ? (
              <CheckSquare size={14} />
            ) : (
              <Square size={14} />
            )}
          </button>
        ),
        size: 44,
        enableSorting: false,
      };

      return [
        selectColumn,
        {
          header: "Status",
          accessorKey: "status",
          cell: (info) => <StatusCell value={info.getValue()} bankRef={info.row.original.bank_ref} />,
          enableSorting: true,
          size: 160,
          sortingFn: (rowA, rowB) => {
            // Custom sort: Breaks > Unsettled > AI-Settled > Manually-Settled
            const getPriority = (row) => {
              const status = row.original.status;
              const statusStr = typeof status === "object" ? status.status : status;
              const bankRef = row.original.bank_ref || "";
              
              if (statusStr === "BREAK") return 1;
              if (statusStr === "UNSETTLED") return 2;
              if (statusStr === "MATCHED" && (bankRef.startsWith("AI Matched") || bankRef.includes("AI Auto-Resolved"))) return 3;
              if (statusStr === "MATCHED") return 4;
              return 5;
            };
            
            return getPriority(rowA) - getPriority(rowB);
          },
        },
        {
          header: "Date",
          accessorKey: "timestamp",
          size: 100,
          cell: (info) => (
            <span className="font-mono text-[11px] text-ink-muted">
              {info.getValue()}
            </span>
          ),
        },
        {
          header: "Security",
          accessorKey: "security",
          size: 120,
          cell: (info) => (
            <span className="text-sm font-medium text-ink-strong">
              {info.getValue()}
            </span>
          ),
        },
        {
          header: "Side",
          accessorKey: "side",
          size: 70,
          cell: (info) => {
            const s = (info.getValue() || "").toUpperCase();
            const isBuy = s === "BUY";
            return (
              <span
                className={`text-[10px] font-bold px-1.5 py-[1px] rounded-sm ${
                  isBuy
                    ? "bg-blue-50 text-aureon-blue"
                    : "bg-amber-50 text-status-warning"
                }`}
              >
                {s}
              </span>
            );
          },
        },
        {
          header: "Qty",
          accessorKey: "quantity",
          size: 100,
          cell: (info) => (
            <span className="font-mono text-[12px] text-ink-strong tabular-nums">
              {formatNumber(info.getValue())}
            </span>
          ),
          meta: { align: "right" },
        },
        {
          header: "Price",
          accessorKey: "price",
          size: 100,
          cell: (info) => (
            <span className="font-mono text-[12px] text-ink-muted tabular-nums">
              {formatNumber(info.getValue())}
            </span>
          ),
          meta: { align: "right" },
        },
        {
          header: "Net Amount",
          accessorKey: "amount",
          size: 120,
          cell: (info) => (
            <span className="font-mono text-[12px] font-semibold text-ink-strong tabular-nums">
              {formatCurrency(info.getValue())}
            </span>
          ),
          meta: { align: "right" },
        },
        {
          header: "Bank Ref",
          accessorKey: "bank_ref",
          size: 160,
          cell: (info) => (
            <span
              className="text-[11px] text-ink-faint truncate max-w-[160px] block"
              title={info.getValue()}
            >
              {info.getValue() || "---"}
            </span>
          ),
        },
        {
          id: "actions",
          header: "",
          enableSorting: false,
          size: 120,
          minSize: 120,
          maxSize: 120,
          cell: ({ row }) => {
            const statusObj = row.original.status || {};
            const status = typeof statusObj === "object" && statusObj !== null
              ? (statusObj.status || "")
              : (statusObj || "");
            
            // Show Resolve button only for BREAK and UNSETTLED statuses
            const showResolve = status === "BREAK" || status === "UNSETTLED";
            
            if (!showResolve) return null;

            return (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onResolve(row.original);
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-[10px] font-semibold px-2 py-1 rounded-sm border border-aureon-border bg-paper-surface hover:bg-aureon-blue hover:text-white hover:border-aureon-blue text-aureon-blue flex items-center gap-1"
              >
                <Wrench size={10} /> Resolve
              </button>
            );
          },
        },
      ];
    }

    if (view === "Holdings") {
      return [
        {
          header: "Status",
          accessorKey: "status",
          cell: (info) => <StatusCell value={info.getValue() || "STORED"} />,
          enableSorting: false,
        },
        {
          header: "Date",
          accessorKey: "date",
          cell: (info) => (
            <span className="font-mono text-[11px] text-ink-muted">
              {info.getValue()}
            </span>
          ),
        },
        {
          header: "ISIN",
          accessorKey: "isin",
          cell: (info) => (
            <span className="font-mono text-[11px] text-ink-strong">
              {info.getValue()}
            </span>
          ),
        },
        {
          header: "Symbol",
          accessorKey: "symbol",
          cell: (info) => (
            <span className="text-sm font-medium text-ink-strong">
              {info.getValue()}
            </span>
          ),
        },
        {
          header: "Quantity",
          accessorKey: "quantity",
          cell: (info) => (
            <span className="font-mono text-[12px] tabular-nums">
              {formatNumber(info.getValue())}
            </span>
          ),
          meta: { align: "right" },
        },
        {
          header: "Market Value",
          accessorKey: "total_value",
          cell: (info) => (
            <span className="font-mono text-[12px] font-semibold tabular-nums">
              {formatCurrency(info.getValue())}
            </span>
          ),
          meta: { align: "right" },
        },
      ];
    }

    // NAV view
    return [
      {
        header: "Date",
        accessorKey: "date",
        cell: (info) => (
          <span className="font-mono text-[11px] text-ink-muted">
            {info.getValue()}
          </span>
        ),
      },
      {
        header: "Fund Name",
        accessorKey: "fund_name",
        cell: (info) => (
          <span className="text-sm font-medium text-ink-strong">
            {info.getValue()}
          </span>
        ),
      },
      {
        header: "NAV",
        accessorKey: "nav_value",
        cell: (info) => (
          <span className="font-mono text-[12px] tabular-nums">
            {formatCurrency(info.getValue())}
          </span>
        ),
        meta: { align: "right" },
      },
      {
        header: "AUM",
        accessorKey: "aum",
        cell: (info) => (
          <span className="font-mono text-[12px] tabular-nums">
            {formatCurrency(info.getValue())}
          </span>
        ),
        meta: { align: "right" },
      },
      {
        header: "Source",
        accessorKey: "source_file",
        cell: (info) => (
          <span className="text-[11px] text-ink-faint">{info.getValue()}</span>
        ),
      },
    ];
  }, [view, onResolve]);

  const data = useMemo(() => {
    if (view === "Trades") return reconData || [];
    if (view === "Holdings") return holdingsData || [];
    return navData || [];
  }, [view, reconData, holdingsData, navData]);

  const table = useReactTable({
    data,
    columns,
    getRowId: (row) => String(row?.id ?? ""),
    state: {
      rowSelection,
    },
    enableRowSelection:
      view === "Trades"
        ? (row) => {
            const statusObj = row.original?.status;
            const statusStr =
              typeof statusObj === "object" && statusObj !== null
                ? statusObj.status
                : statusObj;
            const s = String(statusStr || "").toUpperCase();
            return !(s === "MATCHED" || s.includes("SETTLED"));
          }
        : false,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 50 },
      sorting: view === "Trades" ? [{ id: "status", desc: false }] : [],
    },
  });

  return (
    <div className="border border-aureon-border rounded-md bg-paper-surface flex flex-col h-[520px]">
      {/* Header bar – view label + pagination */}
      <div className="px-4 py-2.5 border-b border-aureon-border bg-slate-50 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-ink-muted uppercase tracking-wide">
          <Layers size={14} className="text-ink-faint" />
          <span>{view} Ledger</span>
          <span className="px-1.5 py-0.5 rounded-sm border border-aureon-border bg-paper-surface font-mono text-[10px] text-ink-faint">
            {data.length} rows
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            className="p-1 rounded-sm border border-aureon-border text-ink-muted disabled:opacity-40 hover:bg-slate-50"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-[11px] font-mono text-ink-muted px-1">
            {table.getState().pagination.pageIndex + 1} /{" "}
            {table.getPageCount() || 1}
          </span>
          <button
            className="p-1 rounded-sm border border-aureon-border text-ink-muted disabled:opacity-40 hover:bg-slate-50"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Data grid */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-slate-50 sticky top-0 z-10 border-b border-aureon-border">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const sortable = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  const align =
                    header.column.columnDef.meta?.align || "left";

                  return (
                    <th
                      key={header.id}
                      onClick={
                        sortable
                          ? header.column.getToggleSortingHandler()
                          : undefined
                      }
                      className={`py-1.5 px-3 text-[10px] font-semibold text-ink-faint uppercase tracking-wider border-r border-aureon-border last:border-r-0 select-none
                        ${
                          sortable
                            ? "cursor-pointer hover:bg-slate-100"
                            : ""
                        }
                        ${align === "right" ? "text-right" : "text-left"}
                      `}
                    >
                      <div
                        className={`flex items-center gap-1 ${
                          align === "right"
                            ? "justify-end"
                            : "justify-start"
                        }`}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                        {sortable && (
                          <>
                            {sorted === "asc" && (
                              <ArrowUpDown
                                size={10}
                                className="text-ink-muted rotate-180"
                              />
                            )}
                            {sorted === "desc" && (
                              <ArrowUpDown
                                size={10}
                                className="text-ink-muted"
                              />
                            )}
                            {!sorted && (
                              <ArrowUpDown
                                size={10}
                                className="text-ink-faint"
                              />
                            )}
                          </>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-aureon-border">
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={`group hover:bg-slate-50 transition-colors ${
                    row.getIsSelected() ? "bg-blue-50/30" : ""
                  }`}
                >
                  {row.getVisibleCells().map((cell) => {
                    const align =
                      cell.column.columnDef.meta?.align || "left";
                    return (
                      <td
                        key={cell.id}
                        className={`py-1.5 px-3 text-xs text-ink-strong border-r border-aureon-border last:border-r-0
                          ${
                            align === "right"
                              ? "text-right font-mono tabular-nums"
                              : "text-left"
                          }`}
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-16 text-center text-ink-muted text-sm"
                >
                  No data loaded. Upload files or run the engine to populate
                  this ledger.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DataTable;
