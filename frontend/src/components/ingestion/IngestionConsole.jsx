// src/components/ingestion/IngestionConsole.jsx
import React, { useEffect, useRef } from "react";

const IngestionConsole = ({ realLogs = [] }) => {
  const consoleRef = useRef(null);

  // Robust Auto-scroll
  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTo({
        top: consoleRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [realLogs]);

  return (
    <div className="flex flex-col bg-paper-canvas h-full p-4 border-l border-aureon-border">
      <div className="border-b border-aureon-border pb-2 mb-3">
        <h2 className="text-[13px] font-semibold text-ink-strong uppercase tracking-wide">
          Engine Telemetry
        </h2>
        <p className="text-[11px] text-ink-muted mt-1">
          Live events from the ingestion subsystem
        </p>
      </div>

      <div
        ref={consoleRef}
        className="flex-1 bg-paper-surface border border-aureon-border rounded-md p-3 font-mono text-[11px] text-ink-strong overflow-auto shadow-inner"
      >
        {realLogs.length === 0 ? (
          <p className="text-ink-muted italic opacity-50">
            System Idle. Waiting for data...
          </p>
        ) : (
          realLogs.map((line, idx) => (
            <div 
              key={idx} 
              className={`whitespace-pre-wrap mb-1 break-words border-b border-slate-50/50 pb-0.5
                ${line.includes("ERROR") || line.includes("❌") ? "text-red-600 font-semibold" : ""}
                ${line.includes("SUCCESS") || line.includes("✅") ? "text-emerald-700" : ""}
                ${line.includes("🚀") ? "text-indigo-600 font-semibold" : ""}
              `}
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default IngestionConsole;