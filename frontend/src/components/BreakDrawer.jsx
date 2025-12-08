// src/components/BreakDrawer.jsx
import React, { useState, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, AlertTriangle, CheckCircle2, BrainCircuit, Loader2, Wrench } from "lucide-react";
import { useAureonApi } from "../hooks/useAureonApi";

const BreakDrawer = ({ isOpen, onClose, trade, onSuccess }) => {
  const api = useAureonApi();
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  // 1. Fetch Analysis on Open
  useEffect(() => {
    if (isOpen && trade) {
      setLoading(true);
      setAnalysis(null);
      
      api.getBreakAnalysis(trade.id)
        .then(data => setAnalysis(data))
        .catch(err => console.error("Analysis failed", err))
        .finally(() => setLoading(false));
    }
  }, [isOpen, trade]);

  if (!isOpen || !trade) return null;

  const handleApply = async () => {
    setIsApplying(true);
    try {
      // Determine what note to save
      let note = "Manual Resolve";
      if (analysis?.found && analysis?.best_candidate) {
        note = `Matched with Cash ID ${analysis.best_candidate.id} (${analysis.ai_suggestion.explanation})`;
      } else {
        note = "Manual Force Resolve - No matching cash linked.";
      }

      await api.manualResolve(trade.id, note);
      
      if (onSuccess) onSuccess();
      onClose();
    } catch (e) {
      alert("Failed to apply match: " + e.message);
    } finally {
      setIsApplying(false);
    }
  };

  // Determine UI State
  const matchFound = analysis?.found && analysis?.best_candidate;
  const confidence = analysis?.ai_suggestion?.confidence || 0;
  
  let confColor = "bg-slate-100 text-slate-600";
  if (confidence > 0.9) confColor = "bg-emerald-100 text-emerald-700";
  else if (confidence > 0.5) confColor = "bg-amber-100 text-amber-700";

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[50] flex justify-end">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.4 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-900 backdrop-blur-[2px]"
          onClick={onClose}
        />

        <motion.aside
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
          className="relative h-[100dvh] w-full max-w-md bg-white shadow-2xl flex flex-col border-l border-slate-200"
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-white z-10">
            <div>
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-500" />
                Break Resolution
              </h2>
              <p className="text-[11px] text-slate-500 mt-0.5 font-mono">
                Trade ID: {trade.id}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-100 rounded-full transition-colors text-slate-400 hover:text-slate-600"
            >
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto bg-slate-50/50 p-6 space-y-6">
            
            {/* Trade Details */}
            <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Unsettled Trade
              </span>
              <div className="mt-2 flex justify-between items-start">
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    {trade.security || trade.symbol}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {trade.side} • Qty: {trade.quantity}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-sm font-medium text-slate-900">
                    {Number(trade.amount).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>

            {/* Analysis Section */}
            <div className="relative">
              <div className="flex items-center gap-2 mb-3">
                <BrainCircuit size={14} className="text-aureon-blue" />
                <span className="text-xs font-bold text-slate-700 uppercase">
                  Match Candidate
                </span>
              </div>

              {loading ? (
                <div className="h-32 flex flex-col items-center justify-center border-2 border-dashed border-slate-200 rounded-lg bg-slate-50">
                  <Loader2 size={20} className="animate-spin text-aureon-blue mb-2" />
                  <span className="text-xs text-slate-500">Searching Ledger...</span>
                </div>
              ) : matchFound ? (
                <div className="bg-white border border-aureon-blue/30 rounded-lg p-4 shadow-sm ring-1 ring-aureon-blue/10">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] font-bold text-aureon-blue uppercase tracking-wider">
                      Recommended Match
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${confColor}`}>
                      {(confidence * 100).toFixed(0)}% Match
                    </span>
                  </div>
                  
                  <div className="flex justify-between items-center group cursor-default">
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-slate-800 truncate">
                        {analysis.best_candidate.description}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                        Txn ID: {analysis.best_candidate.id} • {analysis.best_candidate.date}
                      </div>
                    </div>
                    <div className="ml-3 text-right">
                      <div className="font-mono text-xs font-bold text-slate-900">
                        {Number(analysis.best_candidate.amount).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-100 rounded-lg p-4 text-center">
                  <p className="text-xs text-amber-800 font-medium">
                    No automatic match found.
                  </p>
                  <p className="text-[10px] text-amber-600 mt-1">
                    You can force-resolve this break manually below.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Footer - UNLOCKED BUTTON */}
          <div className="p-5 border-t border-slate-200 bg-white z-10">
            <button
              onClick={handleApply}
              disabled={isApplying}
              className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-md text-xs font-bold transition-all
                ${isApplying
                  ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                  : "bg-slate-900 text-white hover:bg-black shadow-md hover:shadow-lg"
                }`}
            >
              {isApplying ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Resolving...
                </>
              ) : matchFound ? (
                <>
                  <CheckCircle2 size={14} />
                  Accept Match & Resolve
                </>
              ) : (
                <>
                  <Wrench size={14} />
                  Force Manual Resolve
                </>
              )}
            </button>
          </div>

        </motion.aside>
      </div>
    </AnimatePresence>
  );
};

export default BreakDrawer;