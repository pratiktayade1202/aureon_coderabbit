// src/components/DataTable.jsx
import React, { useMemo } from "react";
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

// Status badge with hard color semantics
const StatusCell = ({ value, bankRef }) => {
  // Handle both string format and object format from backend
  let statusStr = "UNSETTLED";
  let statusType = "unsettled";
  
  if (typeof value === "object" && value !== null) {
    statusStr = value.status || "UNSETTLED";
  } else if (typeof value === "string") {
    statusStr = value;
  }
  
  const status = statusStr.toUpperCase();

  // Determine display status based on backend fields
  // Priority: BREAK > MATCHED (AI/Manual) > UNSETTLED
  if (status === "BREAK") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-red-50 text-status-danger border border-red-200">
        <AlertCircle size={11} /> BREAK / ESCALATED
      </span>
    );
  }

  if (status === "MATCHED") {
    // Check bank_ref to determine if AI or Manual resolution
    const isAiResolved = bankRef && (
      bankRef.startsWith("AI Matched") || 
      bankRef.includes("AI Auto-Resolved")
    );
    
    if (isAiResolved) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-blue-50 text-aureon-blue border border-blue-200">
          <CheckCircle2 size={11} /> AI-SETTLED
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-emerald-50 text-status-success border border-emerald-200">
          <CheckCircle2 size={11} /> SETTLED MANUALLY
        </span>
      );
    }
  }

  if (status === "UNSETTLED") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-amber-50 text-status-warning border border-amber-200">
        <Clock size={11} /> UNSETTLED
      </span>
    );
  }

  // Legacy fallback for old string statuses
  if (
    status.includes("SETTLED") ||
    status.includes("MATCH") ||
    status.includes("STORED")
  ) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-emerald-50 text-status-success border border-emerald-200">
        <CheckCircle2 size={11} /> {status.replace("✅ ", "")}
      </span>
    );
  }

  if (
    status.includes("BREAK") ||
    status.includes("FAILED") ||
    status.includes("MISSING")
  ) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-red-50 text-status-danger border border-red-200">
        <AlertCircle size={11} /> {status}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-[2px] rounded-sm text-[10px] font-semibold bg-slate-100 text-ink-muted border border-slate-200">
      <Clock size={11} /> {status}
    </span>
  );
};

/**
 * Titanium Ledger Table
 * - High density
 * - Vertical dividers
 * - Terminal-like typography
 */
const DataTable = ({ view, reconData, holdingsData, navData, onResolve }) => {
  const columns = useMemo(() => {
    if (view === "Trades") {
      return [
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
                  className="group hover:bg-slate-50 transition-colors"
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
