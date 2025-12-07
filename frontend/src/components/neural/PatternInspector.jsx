// src/components/neural/PatternInspector.jsx
import React from "react";
import { BrainCircuit, Activity, Clock4, Info } from "lucide-react";

/**
 * Simple radial confidence gauge reused inside the inspector.
 */
const ConfidenceGauge = ({ score }) => {
  const clamped = Math.max(0, Math.min(score || 0, 1));
  const percent = Math.round(clamped * 100);
  const dash = `${percent}, 100`;

  let label = "Low Trust";
  if (percent >= 85) label = "High Trust";
  else if (percent >= 60) label = "Medium Trust";

  return (
    <div className="flex items-center gap-3">
      <div className="relative w-12 h-12 flex items-center justify-center">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
          <path
            className="text-slate-200"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
          />
          <path
            className="text-aureon-gold"
            strokeDasharray={dash}
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
          />
        </svg>
        <span className="absolute text-[10px] font-bold text-ink-strong">
          {percent}%
        </span>
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] font-semibold text-ink-muted uppercase">
          Confidence
        </span>
        <span className="text-[11px] text-ink-strong">{label}</span>
      </div>
    </div>
  );
};

/**
 * PatternInspector
 *
 * Right-hand detail view for the selected pattern.
 *
 * Props:
 *  - pattern: selected rule object
 */
const PatternInspector = ({ pattern }) => {
  if (!pattern) {
    return (
      <div className="h-full border border-aureon-border rounded-md bg-paper-surface flex items-center justify-center text-[12px] text-ink-muted">
        Select a pattern on the left to inspect its logic.
      </div>
    );
  }

  const {
    id,
    type,
    pattern: patternText,
    confidence,
    applied,
    last_seen,
    examples,
    source,
  } = pattern;

  const safeExamples = Array.isArray(examples) ? examples : [];

  return (
    <div className="h-full border border-aureon-border rounded-md bg-paper-surface flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-aureon-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BrainCircuit size={16} className="text-aureon-gold" />
          <div>
            <p className="text-[11px] font-semibold text-ink-strong uppercase tracking-wide">
              {type || "Learned Pattern"}
            </p>
            <p className="text-[10px] text-ink-muted">
              ID: {id || "N/A"}
            </p>
          </div>
        </div>
        <ConfidenceGauge score={confidence} />
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-4 text-[12px]">
        {/* Pattern text */}
        <div>
          <p className="text-[10px] font-semibold text-ink-muted uppercase mb-1">
            Pattern Logic
          </p>
          <pre className="bg-paper-subtle border border-aureon-border rounded-sm p-2 font-mono text-[11px] text-ink-strong whitespace-pre-wrap">
            {patternText || "// No pattern text provided"}
          </pre>
        </div>

        {/* Metrics row */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="border border-aureon-border rounded-sm p-2 flex items-center gap-2">
            <Activity size={14} className="text-ink-muted" />
            <div>
              <p className="text-[10px] text-ink-muted uppercase">Times applied</p>
              <p className="text-[13px] font-mono text-ink-strong">
                {applied || 0}
              </p>
            </div>
          </div>
          <div className="border border-aureon-border rounded-sm p-2 flex items-center gap-2">
            <Clock4 size={14} className="text-ink-muted" />
            <div>
              <p className="text-[10px] text-ink-muted uppercase">Last seen</p>
              <p className="text-[11px] text-ink-strong">
                {last_seen || "N/A"}
              </p>
            </div>
          </div>
          <div className="border border-aureon-border rounded-sm p-2 flex items-center gap-2">
            <Info size={14} className="text-ink-muted" />
            <div>
              <p className="text-[10px] text-ink-muted uppercase">Source</p>
              <p className="text-[11px] text-ink-strong">
                {source || "Engine"}
              </p>
            </div>
          </div>
        </div>

        {/* Examples */}
        <div>
          <p className="text-[10px] font-semibold text-ink-muted uppercase mb-1">
            Examples
          </p>
          {safeExamples.length === 0 ? (
            <p className="text-[11px] text-ink-muted">
              No sample breaks recorded for this rule yet.
            </p>
          ) : (
            <div className="space-y-2">
              {safeExamples.map((ex, idx) => (
                <div
                  key={idx}
                  className="border border-aureon-border rounded-sm p-2 text-[11px] bg-paper-subtle"
                >
                  <p className="font-mono text-ink-strong whitespace-pre-wrap">
                    {ex}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PatternInspector;
