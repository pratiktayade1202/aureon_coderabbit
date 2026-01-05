// src/components/AuditModal.jsx
import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, CheckCircle, X, ShieldAlert, BrainCircuit } from "lucide-react";

/**
 * AuditModal
 *
 * Institution-grade audit surface for AI anomaly reports.
 * - Cool slate palette, sharp radius, strong borders
 * - Handles both "clean" and "anomalies found" states
 *
 * Props:
 *  - isOpen: boolean
 *  - onClose: () => void
 *  - data: { anomalies?: Array<{ id, issue, severity }> }
 */
const AuditModal = ({ isOpen, onClose, data }) => {
  if (!isOpen) return null;

  const anomalies = data?.anomalies || [];
  const hasIssues = anomalies.length > 0;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.6 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal Shell */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 6 }}
          transition={{ duration: 0.16, ease: "easeOut" }}
          className="relative w-full max-w-2xl bg-white border border-slate-200 rounded-lg shadow-lg flex flex-col max-h-[80vh]"
        >
          {/* Header */}
          <div
            className={`px-5 py-4 border-b border-slate-200 flex items-center justify-between ${
              hasIssues ? "bg-red-50" : "bg-emerald-50"
            }`}
          >
            <div className="flex items-center gap-3">
              <div
                className={`flex items-center justify-center w-10 h-10 rounded-md border text-sm ${
                  hasIssues
                    ? "bg-red-100 border-red-200 text-red-700"
                    : "bg-emerald-100 border-emerald-200 text-emerald-700"
                }`}
              >
                {hasIssues ? <ShieldAlert size={20} /> : <CheckCircle size={20} />}
              </div>
              <div className="flex flex-col">
                <h3 className="text-sm font-semibold text-slate-900 tracking-tight">
                  AI Audit Report
                </h3>
                <p className="text-xs text-slate-600 flex items-center gap-1.5">
                  <BrainCircuit size={12} className="text-slate-500" />
                  Analysis by Aureon Neural Governance Layer
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 transition-colors"
            >
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="px-5 py-4 overflow-y-auto space-y-4">
            {!hasIssues ? (
              <div className="py-10 text-center">
                <div className="inline-flex p-4 rounded-full bg-emerald-50 border border-emerald-200 mb-4">
                  <CheckCircle size={36} className="text-emerald-600" />
                </div>
                <h4 className="text-sm font-semibold text-slate-900 mb-1">
                  Ledger passes automated checks
                </h4>
                <p className="text-xs text-slate-600 max-w-sm mx-auto">
                  No logical anomalies or compliance breaches detected in this batch.  
                  All rules, tolerances, and AI pattern checks passed successfully.
                </p>
              </div>
            ) : (
              <>
                {/* Summary banner */}
                <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-xs font-semibold text-red-700 flex items-center gap-2">
                    <AlertTriangle size={14} />
                    {anomalies.length} anomaly
                    {anomalies.length > 1 ? " instances" : ""} detected across the ledger.
                  </p>
                  <p className="text-[11px] text-red-700/80 mt-1">
                    Review and sign off before EOD settlement. These are included in the permanent
                    audit trail.
                  </p>
                </div>

                {/* Anomaly list */}
                <div className="space-y-3">
                  {anomalies.map((issue, idx) => (
                    <motion.div
                      key={issue.id ?? idx}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      className="flex gap-3 border border-red-100 bg-white rounded-md px-3 py-3"
                    >
                      {/* Severity rail */}
                      <div className="pt-0.5">
                        <div className="w-6 h-6 flex items-center justify-center rounded-full bg-red-50 border border-red-200">
                          <AlertTriangle size={14} className="text-red-600" />
                        </div>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="inline-flex items-center px-2 py-[2px] text-[10px] font-semibold uppercase tracking-wide rounded-sm bg-slate-100 text-slate-700 border border-slate-200">
                            Row {issue.id}
                          </span>
                          {issue.severity && (
                            <span className="inline-flex items-center px-2 py-[2px] text-[10px] font-semibold uppercase tracking-wide rounded-sm bg-red-50 text-red-700 border border-red-200">
                              {issue.severity}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-800 leading-relaxed">
                          {issue.issue}
                        </p>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
            <p className="text-[11px] text-slate-500">
              Verified by Aureon Governance. This review is archived for compliance.
            </p>
            <button
              onClick={onClose}
              className="inline-flex items-center justify-center px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 text-white hover:bg-slate-800 transition-colors"
            >
              Acknowledge Report
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default AuditModal;
