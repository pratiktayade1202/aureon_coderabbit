// src/components/ingestion/IngestionConsole.jsx
import React, { useEffect, useRef } from "react";
import { Activity, Terminal, Trash2, Pause, Play } from "lucide-react";

/**
 * IngestionConsole (FINAL)
 *
 * ✔ Keeps your Bloomberg-style UI
 * ✔ Removes ALL demo timers & fake streams
 * ✔ Purely displays realLogs passed from parent
 * ✔ Auto-scrolls on new logs
 *
 * Props:
 *   - realLogs: string[]
 *   - title?: string
 */
const IngestionConsole = ({ realLogs = [], title = "Model Logs" }) => {
  const scrollRef = useRef(null);

  // Auto-scroll whenever log list updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [realLogs]);

  const handleClear = () => {
    // Clear ONLY locally — parent owns actual log history
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  };

  return (
    <div className="flex flex-col border border-slate-300 rounded-md bg-slate-950 text-slate-100 h-full">

      {/* Header */}
      <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 flex items-center justify-center rounded-sm bg-slate-900 border border-slate-700">
            <Terminal size={14} className="text-emerald-300" />
          </div>
          <div className="flex flex-col">
            <span className="text-[11px] font-semibold tracking-wide">
              {title}
            </span>
            <span className="text-[10px] text-slate-400">
              Live ingestion telemetry
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Pause/Play kept but disabled for real logs */}
          <button
            type="button"
            className="inline-flex items-center justify-center w-6 h-6 rounded-sm border border-slate-700 bg-slate-900 text-slate-600 cursor-not-allowed"
            title="Streaming controlled by backend"
          >
            <Pause size={12} />
          </button>

          <button
            type="button"
            onClick={handleClear}
            className="inline-flex items-center justify-center w-6 h-6 rounded-sm border border-slate-700 bg-slate-900 text-slate-400 hover:bg-slate-800"
            title="Clear view"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Status row */}
      <div className="px-3 py-1.5 border-b border-slate-800 flex items-center justify-between text-[10px] text-slate-400">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>
            {realLogs.length === 0 ? "Waiting for backend events" : "Receiving telemetry"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Activity size={12} className="text-emerald-300" />
          <span>{realLogs.length} events</span>
        </div>
      </div>

      {/* Log body */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed px-3 py-2 bg-slate-950/95"
      >
        {realLogs.length === 0 ? (
          <p className="text-slate-500 italic">
            Awaiting ingestion pipeline…
          </p>
        ) : (
          realLogs.map((line, idx) => (
            <div key={idx} className="text-slate-200 whitespace-pre-wrap">
              <span className="text-slate-500 pr-2">›</span>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default IngestionConsole;
