// src/components/ingestion/IngestionUtilityBar.jsx
import React from "react";
import { FileInput, SlidersHorizontal } from "lucide-react";

/**
 * IngestionUtilityBar
 * Top-of-page strip for the Ingestion workstation.
 * Titanium: dense, minimal, institutional.
 */
const IngestionUtilityBar = () => {
  return (
    <div className="border-b border-aureon-border pb-3 mb-4 flex items-center justify-between">
      <div>
        <div className="flex items-center gap-2">
          <FileInput size={16} className="text-aureon-gold" />
          <h1 className="text-sm md:text-base font-semibold text-ink-strong tracking-tight">
            Data Ingestion
          </h1>
        </div>
        <p className="text-[11px] text-ink-muted mt-1">
          Stage broker, bank, and custodian files into the Titanium engine.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-700">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          READY
        </span>
        <button className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 border border-aureon-border rounded-md bg-paper-surface text-[11px] text-ink-muted hover:bg-slate-50">
          <SlidersHorizontal size={12} />
          Pipeline Config
        </button>
      </div>
    </div>
  );
};

export default IngestionUtilityBar;
