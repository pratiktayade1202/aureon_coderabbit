// src/components/LogViewerModal.jsx
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileClock, Bot, Cpu, Search } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { API_BASE_URL } from "../config";

const API_BASE = API_BASE_URL;

const LogViewerModal = ({ isOpen, onClose }) => {
  const { getToken } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("ALL"); // ALL | SYSTEM | AI

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

  // Filter Logic (support both `agent_model` and legacy `model`)
  const filteredLogs = logs.filter((log) => {
    if (activeTab === "ALL") return true;
    const model = (log.agent_model || log.model || "").toUpperCase();
    if (activeTab === "AI") return model.includes("AI") || model.includes("GPT") || model.includes("GEMINI");
    if (activeTab === "SYSTEM") return !model.includes("AI") && !model.includes("GPT") && !model.includes("GEMINI");
    return true;
  });

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
                <FileClock size={20} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">System Audit Trail</h3>
                <p className="text-[11px] text-slate-500">Immutable record of decisions</p>
              </div>
            </div>
            
            {/* Tab Switcher */}
            <div className="flex p-1 bg-slate-100 rounded-lg border border-slate-200">
              {["ALL", "SYSTEM", "AI"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 text-[10px] font-bold rounded-md transition-all ${
                    activeTab === tab
                      ? "bg-white text-slate-900 shadow-sm border border-slate-200"
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {tab === "ALL" ? "All Events" : tab === "AI" ? "AI Decisions" : "Engine Logs"}
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
            ) : filteredLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-40 text-slate-400">
                <Search size={24} className="mb-2 opacity-50" />
                <span className="text-xs">No logs found for this filter.</span>
              </div>
            ) : (
              <ul className="space-y-2">
                {filteredLogs.map((log, idx) => {
                  const model = (log.agent_model || log.model || "").toUpperCase();
                  const isAi = model.includes("AI") || model.includes("GPT") || model.includes("GEMINI");
                  return (
                    <li
                      key={log.id ?? idx}
                      className="bg-white border border-slate-200 rounded-lg p-3 flex gap-3 shadow-sm"
                    >
                      <div
                        className={`mt-0.5 w-6 h-6 flex items-center justify-center rounded-full border ${
                          isAi
                            ? "bg-purple-50 border-purple-200 text-purple-600"
                            : "bg-slate-100 border-slate-200 text-slate-500"
                        }`}
                      >
                        {isAi ? <Bot size={14} /> : <Cpu size={14} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start">
                          <span className="text-xs font-bold text-slate-800">{log.action || "System Event"}</span>
                          <span className="text-[10px] font-mono text-slate-400">{log.timestamp}</span>
                        </div>
                        <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                          {log.details || log.reason}
                        </p>
                        <div className="mt-2 flex gap-2">
                          <span className="px-1.5 py-0.5 bg-slate-50 border border-slate-100 rounded text-[10px] text-slate-500">
                            {log.agent_model || log.model || "System"}
                          </span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default LogViewerModal;
