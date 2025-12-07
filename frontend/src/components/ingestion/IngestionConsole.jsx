// src/components/ingestion/IngestionConsole.jsx
import React, { useEffect, useRef } from "react";

const IngestionConsole = ({ realLogs = [] }) => {
  const endRef = useRef(null);

  // Robust Auto-scroll
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
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

      {/* CHANGED: Removed flex-1, added h-64 (or h-96) to stop bouncing */}
      <div className="h-64 max-h-64 bg-paper-surface border border-aureon-border rounded-md p-3 font-mono text-[11px] text-ink-strong overflow-y-auto shadow-inner relative">   
        {realLogs.length === 0 ? (
          <p className="text-ink-muted italic opacity-50 absolute top-3 left-3">
            System Idle. Waiting for data...
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            {realLogs.map((line, idx) => (
              <div 
                key={idx} 
                className="whitespace-pre-wrap border-b border-slate-50 pb-1 break-words"
              >
                {line}
              </div>
            ))}
            {/* Invisible element to anchor scrolling */}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  );
};

export default IngestionConsole;