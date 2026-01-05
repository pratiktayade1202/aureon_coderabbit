// src/components/neural/PatternList.jsx
import React, { useMemo } from "react";
import { Filter, CheckCircle2, CircleDot } from "lucide-react";

/**
 * PatternList
 *
 * Left-hand column of Neural Core.
 * Shows learned patterns in a dense, scrollable list.
 *
 * Props:
 *  - patterns: array of rules
 *  - selectedId: id of currently selected rule
 *  - onSelect: fn(id)
 *  - search: string (current search term)
 *  - onSearchChange: fn(str)
 */
const PatternList = ({ patterns, selectedId, onSelect, search, onSearchChange }) => {
  const filtered = useMemo(() => {
    if (!search) return patterns || [];
    const q = search.toLowerCase();
    return (patterns || []).filter((p) => {
      const text =
        `${p.id || ""} ${p.type || ""} ${p.pattern || ""}`.toLowerCase();
      return text.includes(q);
    });
  }, [patterns, search]);

  return (
    <div className="h-full border border-aureon-border rounded-md bg-paper-surface flex flex-col">
      {/* Header */}
      <div className="px-3 py-2 border-b border-aureon-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter size={14} className="text-ink-muted" />
          <span className="text-[11px] font-semibold text-ink-strong uppercase tracking-wide">
            Learned Patterns
          </span>
        </div>
        <span className="text-[10px] text-ink-muted font-mono">
          {filtered.length}/{patterns?.length || 0}
        </span>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-aureon-border">
        <div className="relative">
          <input
            type="text"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by ID, type, text…"
            className="w-full pl-2 pr-2 py-1.5 text-[11px] border border-aureon-border rounded-sm bg-paper-subtle text-ink-strong placeholder:text-ink-faint focus:outline-none focus:ring-1 focus:ring-aureon-blue"
          />
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-auto text-[11px]">
        {filtered.length === 0 ? (
          <div className="px-3 py-4 text-ink-muted text-[11px]">
            No patterns match this search.
          </div>
        ) : (
          filtered.map((rule) => {
            const isActive = rule.id === selectedId;
            const applied = rule.applied || 0;
            const conf = Math.round(
              Math.max(0, Math.min(rule.confidence ?? 0, 1)) * 100
            );

            return (
              <button
                key={rule.id || rule.pattern}
                onClick={() => onSelect(rule.id)}
                className={[
                  "w-full text-left px-3 py-2 border-b border-aureon-border flex flex-col gap-1",
                  isActive ? "bg-slate-900 text-white" : "hover:bg-slate-50",
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={[
                      "text-[10px] font-semibold uppercase tracking-wide",
                      isActive ? "text-white" : "text-ink-muted",
                    ].join(" ")}
                  >
                    {rule.type || "PATTERN"}
                  </span>
                  <span
                    className={[
                      "text-[10px] font-mono",
                      isActive ? "text-slate-100" : "text-ink-faint",
                    ].join(" ")}
                  >
                    ID: {rule.id || "N/A"}
                  </span>
                </div>

                <div className="text-[11px] truncate font-mono">
                  {rule.pattern || "No pattern text"}
                </div>

                <div className="flex items-center justify-between gap-2 mt-1">
                  <div className="inline-flex items-center gap-1">
                    <CircleDot
                      size={11}
                      className={isActive ? "text-emerald-300" : "text-emerald-600"}
                    />
                    <span
                      className={[
                        "text-[10px]",
                        isActive ? "text-emerald-100" : "text-emerald-700",
                      ].join(" ")}
                    >
                      {conf || 0}% conf
                    </span>
                  </div>
                  <div className="inline-flex items-center gap-1">
                    <CheckCircle2
                      size={11}
                      className={isActive ? "text-slate-100" : "text-ink-faint"}
                    />
                    <span
                      className={[
                        "text-[10px]",
                        isActive ? "text-slate-100" : "text-ink-muted",
                      ].join(" ")}
                    >
                      {applied}× applied
                    </span>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
};

export default PatternList;
