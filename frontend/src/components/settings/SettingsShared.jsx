import React from "react";

// Shared typography + card primitives for Aureon Settings (Titanium + Slate theme)

export const SectionHeader = ({ title, description }) => (
  <div className="mb-4">
    <h2 className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
      {title}
    </h2>
    {description && (
      <p className="mt-1 text-xs text-ink-muted">
        {description}
      </p>
    )}
  </div>
);

export const FieldRow = ({ label, children, hint }) => (
  <div className="py-3 flex flex-col gap-1 border-b border-slate-100 last:border-b-0">
    <div className="flex items-center justify-between gap-4">
      <span className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
        {label}
      </span>
      <div className="flex-1 max-w-md text-right text-sm text-ink-strong">
        {children}
      </div>
    </div>
    {hint && (
      <p className="text-[11px] text-ink-muted text-right max-w-md ml-auto">
        {hint}
      </p>
    )}
  </div>
);

export const Tag = ({ children, variant = "default" }) => {
  const variants = {
    default: "border-slate-300 bg-slate-50 text-slate-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    danger: "border-red-200 bg-red-50 text-red-700",
    info: "border-blue-200 bg-blue-50 text-blue-700",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-[3px] rounded-full border text-[10px] font-medium ${variants[variant]}`}
    >
      {children}
    </span>
  );
};

export const StatusDot = ({ status = "healthy" }) => {
  const colors = {
    healthy: "bg-emerald-500",
    warning: "bg-amber-400",
    error: "bg-red-500",
    syncing: "bg-blue-400 animate-pulse",
  };
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[status]}`} />;
};

export const TerminalCard = ({ children, className = "" }) => (
  <div
    className={`rounded-xl border border-slate-200/60 backdrop-blur-xl bg-white/70 p-6 shadow-sm ${className}`}
  >
    {children}
  </div>
);

export const SectionDivider = ({ label }) => (
  <div className="flex items-center gap-3 py-3 mt-2">
    <span className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
      {label}
    </span>
    <div className="flex-1 h-px bg-slate-200" />
  </div>
);

export const Toggle = ({ checked, onChange, disabled = false }) => (
  <button
    type="button"
    onClick={() => !disabled && onChange?.(!checked)}
    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
      disabled
        ? "cursor-not-allowed opacity-60 bg-slate-200"
        : checked
        ? "bg-emerald-500"
        : "bg-slate-300"
    }`}
  >
    <span
      className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
        checked ? "translate-x-4" : "translate-x-0.5"
      }`}
    />
  </button>
);

export const Sparkline = ({ data = [2, 4, 3, 7, 5, 8, 6, 9, 4, 6] }) => {
  const max = Math.max(...data);
  const points = data.map((v, i) => `${i * 8},${20 - (v / max) * 16}`).join(" ");

  return (
    <div className="inline-flex items-center rounded-md border border-slate-200/60 backdrop-blur-sm bg-white/50 px-2 py-1">
      <svg width="72" height="20" className="text-emerald-500">
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    </div>
  );
};
