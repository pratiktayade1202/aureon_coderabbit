// src/components/StatusBadge.jsx
import React from "react";

const statusMap = {
  MATCHED: {
    label: "Matched",
    classes: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  PENDING: {
    label: "Pending",
    classes: "bg-amber-50 text-amber-700 border-amber-200",
  },
  BREAK: {
    label: "Break",
    classes: "bg-red-50 text-red-700 border-red-200",
  },
};

const StatusBadge = ({ status }) => {
  const key = status?.toUpperCase?.() || "DEFAULT";
  const config =
    statusMap[key] ||
    {
      label: status || "Unknown",
      classes: "bg-slate-50 text-slate-700 border-slate-200",
    };

  return (
    <span
      className={[
        "inline-flex items-center justify-center px-2 py-[2px]",
        "border rounded-sm text-[10px] font-semibold uppercase tracking-wide",
        config.classes,
      ].join(" ")}
    >
      {config.label}
    </span>
  );
};

export default StatusBadge;
