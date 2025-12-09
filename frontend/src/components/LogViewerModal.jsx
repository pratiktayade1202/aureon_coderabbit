// src/components/LogViewerModal.jsx
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileClock, CheckCircle, AlertTriangle, Bot } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

/**
 * LogViewerModal
 *
 * Read-only audit surface for AI + system decisions.
 * Shows a dense, scrollable list of audit events.
 */
const LogViewerModal = ({ isOpen, onClose }) => {
  const { getToken } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      if (!isOpen) return;

      setLoading(true);
      try {
        const token = await getToken();
        const res = await fetch(`${API_BASE}/audit-logs`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setLogs(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchLogs();
  }, [isOpen, getToken]);

  if (!isOpen) return null;

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

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 6 }}
          transition={{ duration: 0.16, ease: "easeOut" }}
          className="relative w-full max-w-4xl bg-white border border-slate-200 rounded-lg shadow-lg flex flex-col max-h-[85vh]"
        >
          {/* Header */}
          <div className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex items-center justify-center rounded-md bg-slate-900 text-white">
                <FileClock size={20} />
              </div>
              <div className="flex flex-col">
                <h3 className="text-sm font-semibold text-slate-900 tracking-tight">
                  System Audit Trail
                </h3>
                <p className="text-[11px] text-slate-600 flex items-center gap-1.5">
                  <Bot size={12} className="text-slate-500" />
                  Immutable record of AI & system decisions
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-3 flex-1 overflow-y-auto bg-slate-50/60">
            {loading ? (
              <div className="py-10 text-center text-xs text-slate-500">
                Loading audit events…
              </div>
            ) : logs.length === 0 ? (
              <div className="py-10 text-center text-xs text-slate-500">
                No audit events recorded yet.
              </div>
            ) : (
              <ul className="space-y-2">
                {logs.map((log, idx) => {
                  const isError = log.status === "error";
                  const isSuccess = log.status === "success";

                  return (
                    <li
                      key={log.id ?? idx}
                      className="bg-white border border-slate-200 rounded-md px-3 py-2.5 flex gap-3 text-xs"
                    >
                      {/* Status icon */}
                      <div className="pt-0.5">
                        {isError ? (
                          <div className="w-6 h-6 flex items-center justify-center rounded-full bg-red-50 border border-red-200">
                            <AlertTriangle size={14} className="text-red-600" />
                          </div>
                        ) : (
                          <div className="w-6 h-6 flex items-center justify-center rounded-full bg-emerald-50 border border-emerald-200">
                            <CheckCircle size={14} className="text-emerald-600" />
                          </div>
                        )}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="inline-flex items-center px-2 py-[2px] rounded-sm border border-slate-200 bg-slate-50 text-[10px] font-mono text-slate-700">
                              {log.id ?? `EVT-${idx + 1}`}
                            </span>
                            {log.action && (
                              <span className="text-[11px] font-semibold text-slate-800 truncate">
                                {log.action}
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {log.timestamp}
                          </span>
                        </div>

                        {log.details && (
                          <p className="text-[11px] text-slate-700 leading-snug">
                            {log.details}
                          </p>
                        )}

                        <div className="flex flex-wrap gap-1 pt-1">
                          {log.user && (
                            <span className="px-1.5 py-[1px] rounded-sm bg-slate-50 border border-slate-200 text-[10px] text-slate-600">
                              User: {log.user}
                            </span>
                          )}
                          {log.model && (
                            <span className="px-1.5 py-[1px] rounded-sm bg-slate-50 border border-slate-200 text-[10px] text-slate-600">
                              Model: {log.model}
                            </span>
                          )}
                          {log.context_id && (
                            <span className="px-1.5 py-[1px] rounded-sm bg-slate-50 border border-slate-200 text-[10px] text-slate-600">
                              Context: {log.context_id}
                            </span>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-2.5 border-t border-slate-200 bg-white flex items-center justify-between">
            <p className="text-[11px] text-slate-500">
              Logs are immutable and stored for regulatory review.
            </p>
            <span className="text-[11px] font-mono text-slate-500">
              Total events: {logs.length}
            </span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default LogViewerModal;
