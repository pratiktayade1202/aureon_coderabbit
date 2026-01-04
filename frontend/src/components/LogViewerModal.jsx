// src/components/LogViewerModal.jsx
/**
 * Audit Trail Viewer (v2.1)
 * 
 * IMPORTANT: This now uses /audit-events (hash-chained governance trail)
 * NOT /audit-logs (internal debug telemetry).
 * 
 * AuditEvent = External audit surface for governance decisions
 * ReconLog = Internal debug telemetry (never exposed to UI)
 */
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Shield, ShieldCheck, ShieldAlert, RefreshCw, Bot, User, Search } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

const LogViewerModal = ({ isOpen, onClose }) => {
  const { getToken } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);
  const [activeTab, setActiveTab] = useState("ALL"); // ALL | HUMAN | AI

  useEffect(() => {
    const fetchEvents = async () => {
      if (!isOpen) return;
      setLoading(true);
      try {
        const token = await getToken();
        // Use /audit-events (hash-chained governance trail)
        const res = await fetch(`${API_BASE}/audit-events`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        setEvents(Array.isArray(data.events) ? data.events : []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, [isOpen, getToken]);

  const verifyChain = async () => {
    setVerifying(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/audit-verify`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const result = await res.json();
      setVerificationResult(result);
    } catch (err) {
      setVerificationResult({ valid: false, errors: [err.message] });
    } finally {
      setVerifying(false);
    }
  };

  if (!isOpen) return null;

  // Filter logic based on actor
  const filteredEvents = events.filter((event) => {
    if (activeTab === "ALL") return true;
    const actor = (event.actor || "").toUpperCase();
    if (activeTab === "AI") return actor.includes("AI") || actor.includes("AGENT");
    if (activeTab === "HUMAN") return !actor.includes("AI") && !actor.includes("AGENT");
    return true;
  });

  // Event type to human-readable label
  const getEventLabel = (type) => {
    const labels = {
      "PROPOSAL_CREATED": "Proposal Created",
      "PROPOSAL_APPROVED": "Proposal Approved",
      "PROPOSAL_REJECTED": "Proposal Rejected",
      "TRADE_RESOLVED": "Trade Resolved",
      "RUN_STARTED": "Run Started",
      "RUN_COMPLETED": "Run Completed",
      "RUN_FAILED": "Run Failed",
      "FILE_UPLOADED": "File Uploaded",
    };
    return labels[type] || type;
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.6 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm"
          onClick={onClose}
        />
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 6 }}
          className="relative w-full max-w-4xl bg-white border border-slate-200 rounded-lg shadow-lg flex flex-col max-h-[85vh]"
        >
          {/* Header */}
          <div className="px-5 py-4 border-b border-slate-200 bg-white flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 flex items-center justify-center rounded-md bg-slate-900 text-white">
                <Shield size={20} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Governance Audit Trail</h3>
                <p className="text-[11px] text-slate-500">Hash-chained • Tamper-evident • Immutable</p>
              </div>
            </div>

            {/* Verification Status */}
            <div className="flex items-center gap-2">
              {verificationResult && (
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium ${verificationResult.valid
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-red-50 text-red-700 border border-red-200"
                  }`}>
                  {verificationResult.valid ? (
                    <>
                      <ShieldCheck size={12} />
                      <span>Verified ({verificationResult.events_verified})</span>
                    </>
                  ) : (
                    <>
                      <ShieldAlert size={12} />
                      <span>Integrity Error</span>
                    </>
                  )}
                </div>
              )}

              <button
                onClick={verifyChain}
                disabled={verifying}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg border border-slate-200"
              >
                <RefreshCw size={12} className={verifying ? "animate-spin" : ""} />
                {verifying ? "Verifying..." : "Verify Chain"}
              </button>
            </div>

            {/* Tab Switcher */}
            <div className="flex p-1 bg-slate-100 rounded-lg border border-slate-200">
              {["ALL", "HUMAN", "AI"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${activeTab === tab
                      ? "bg-white text-slate-900 shadow-sm border border-slate-200"
                      : "text-slate-500 hover:text-slate-700"
                    }`}
                >
                  {tab === "ALL" ? "All Events" : tab === "AI" ? "AI Actions" : "Human Actions"}
                </button>
              ))}
            </div>

            <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400">
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-4 flex-1 overflow-y-auto bg-slate-50">
            {loading ? (
              <div className="flex items-center justify-center h-40 text-slate-400 text-xs">Loading...</div>
            ) : filteredEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-slate-400">
                <Search size={24} className="mb-2 opacity-50" />
                <span className="text-xs">No governance events found.</span>
                <span className="text-[10px] mt-1">Upload files and run reconciliation to generate audit events.</span>
              </div>
            ) : (
              <ul className="space-y-2">
                {filteredEvents.map((event, idx) => {
                  const isAI = (event.actor || "").toUpperCase().includes("AI");
                  return (
                    <li
                      key={event.id ?? idx}
                      className="bg-white border border-slate-200 rounded-lg p-3 flex gap-3 shadow-sm"
                    >
                      <div
                        className={`mt-0.5 w-6 h-6 flex items-center justify-center rounded-full border ${isAI
                            ? "bg-purple-50 border-purple-200 text-purple-600"
                            : "bg-blue-50 border-blue-200 text-blue-600"
                          }`}
                      >
                        {isAI ? <Bot size={14} /> : <User size={14} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start">
                          <span className="text-xs font-bold text-slate-800">
                            {getEventLabel(event.event_type)}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">
                            {event.created_at ? new Date(event.created_at).toLocaleString() : ""}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                          {event.entity_type}:{event.entity_id} by {event.actor}
                        </p>
                        <div className="mt-2 flex gap-2 flex-wrap">
                          <span className="px-1.5 py-0.5 bg-slate-50 border border-slate-100 rounded text-[10px] text-slate-500">
                            {event.actor}
                          </span>
                          <span className="px-1.5 py-0.5 bg-slate-50 border border-slate-100 rounded text-[9px] font-mono text-slate-400">
                            #{event.event_hash?.slice(0, 8)}...
                          </span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Footer - Safety Disclosure */}
          <div className="px-5 py-2 border-t border-slate-200 bg-amber-50 text-center">
            <p className="text-[10px] text-amber-700">
              Append-only audit trail with SHA256 hash chain. Aureon is assistive tooling, not a system of record.
            </p>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default LogViewerModal;

