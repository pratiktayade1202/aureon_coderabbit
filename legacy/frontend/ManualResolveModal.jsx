// src/components/ManualResolveModal.jsx
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Wrench, X, CheckCircle, Loader2 } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/**
 * ManualResolveModal
 *
 * Small, focused dialog for manual settlement override.
 * Keeps the interaction "surgical": one trade, one note, one action.
 *
 * Props:
 *  - isOpen: boolean
 *  - onClose: () => void
 *  - trade: { id, security, amount, status }
 *  - onSuccess: () => void   // called after successful resolve
 */
const ManualResolveModal = ({ isOpen, onClose, trade, onSuccess }) => {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !trade) return null;

  const handleSubmit = async () => {
    if (!reason.trim()) {
      alert("Please provide a resolution note / cash reference.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/manual-resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trade_id: trade.id,
          reason,
        }),
      });

      const data = await res.json();
      if (data.status === "success") {
        onSuccess && onSuccess();
        onClose();
      } else {
        alert("Error: " + data.message);
      }
    } catch (err) {
      console.error(err);
      alert("Network Error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[110] flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.55 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-slate-900/70 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Dialog */}
        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: 4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 4 }}
          transition={{ duration: 0.16, ease: "easeOut" }}
          className="relative w-full max-w-md bg-white border border-slate-200 rounded-lg shadow-lg overflow-hidden"
        >
          {/* Header */}
          <div className="px-5 py-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Wrench size={16} className="text-slate-700" />
              Manual Resolve
            </h3>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-slate-500 hover:bg-slate-100 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Body */}
          <div className="px-5 py-4 space-y-4">
            {/* Trade context */}
            <div className="px-3 py-3 rounded-md border border-slate-200 bg-slate-50">
              <p className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">
                Resolving trade
              </p>
              <p className="text-xs text-slate-900 font-mono mt-1">
                {trade.security} • ₹{trade.amount}
              </p>
              <p className="text-[11px] text-red-600 mt-1 font-medium">
                Current status: {trade.status}
              </p>
            </div>

            {/* Input */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">
                Resolution note / cash reference
              </label>
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g. Matched with HDFC Cash Ref 554..."
                className="w-full px-3 py-2 text-sm rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-600 focus:border-blue-600"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                This note will be stamped into the audit log and visible to reviewers.
              </p>
            </div>
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-slate-200 bg-slate-50">
            <button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md text-xs font-semibold py-2.5 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  <CheckCircle size={16} />
                  Confirm Settlement Override
                </>
              )}
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default ManualResolveModal;
