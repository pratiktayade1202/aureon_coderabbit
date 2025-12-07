import React from "react";

export const SectionHeader = ({ title, description }) => (
  <div className="mb-4 border-b border-slate-200 pb-3">
    <h2 className="text-sm font-semibold text-ink-strong">{title}</h2>
    {description && (
      <p className="text-[11px] text-ink-muted mt-1">{description}</p>
    )}
  </div>
);

export const FieldRow = ({ label, children, hint }) => (
  <div className="py-2.5 flex flex-col gap-1 border-b border-slate-100 last:border-b-0">
    <div className="flex items-center justify-between gap-4">
      <span className="text-[11px] font-medium text-ink-muted uppercase tracking-wide">
        {label}
      </span>
      <div className="flex-1 max-w-md text-right">{children}</div>
    </div>
    {hint && (
      <p className="text-[10px] text-ink-faint text-right max-w-md ml-auto">
        {hint}
      </p>
    )}
  </div>
);

export const Tag = ({ children }) => (
  <span className="inline-flex items-center px-1.5 py-[2px] rounded-sm border border-slate-300 bg-slate-50 text-[10px] font-mono text-ink-muted">
    {children}
  </span>
);