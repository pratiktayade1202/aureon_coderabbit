// src/components/BreakDrawer.jsx
import React from 'react';
import { 
  X, Check, AlertTriangle, BrainCircuit, ArrowRight, 
  Hash, Calendar, DollarSign, Activity, FileText, Scale
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const BreakDrawer = ({ isOpen, onClose, breakItem, onResolve }) => {
  if (!isOpen || !breakItem) return null;

  // Safe access
  const trade = breakItem.trade || {};
  const candidate = breakItem.candidate || {};
  
  // AI Parsing
  const isAiResolved = breakItem.resolution_type === 'AI' || (breakItem.resolution_note && breakItem.resolution_note.startsWith("AI"));
  const aiReasoning = breakItem.resolution_note || "Analysis pending...";
  
  // Diff Calculation
  const tradeAmt = Math.abs(trade.amount || 0);
  const cashAmt = Math.abs(candidate.amount || 0);
  const diff = Math.abs(tradeAmt - cashAmt);
  const isPerfectMatch = diff < 0.01;

  // Render Helpers
  const formatCurrency = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
  const formatDate = (val) => val ? new Date(val).toLocaleDateString('en-GB') : '-';

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40" 
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <motion.div 
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className="fixed inset-y-0 right-0 w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col border-l border-slate-200"
      >
        
        {/* --- 1. HEADER (Dark Terminal Style) --- */}
        <div className="bg-slate-900 text-white p-5 flex justify-between items-start shrink-0">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="font-mono text-[10px] uppercase tracking-widest text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                ID: #{breakItem.id}
              </span>
              {isAiResolved && (
                <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-[#D4AF37] bg-[#D4AF37]/10 px-2 py-0.5 rounded border border-[#D4AF37]/20">
                  <BrainCircuit size={10} /> AI_PROPOSAL
                </span>
              )}
            </div>
            <h2 className="text-lg font-bold tracking-tight flex items-center gap-2">
              <Activity size={18} className="text-slate-400" />
              {breakItem.break_type || "Trade Break Analysis"}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-800 rounded-full transition-colors text-slate-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        {/* --- 2. SCROLLABLE CONTENT --- */}
        <div className="flex-1 overflow-y-auto bg-slate-50 p-6 space-y-6">
          
          {/* A. AI INSIGHT (Terminal Block) */}
          {(isAiResolved || breakItem.resolution_note) && (
            <div className="bg-black rounded-lg border border-slate-800 overflow-hidden shadow-sm">
              <div className="bg-slate-800/50 px-4 py-1.5 flex justify-between items-center border-b border-slate-800">
                <span className="text-[10px] font-mono uppercase text-slate-400 flex items-center gap-1.5">
                  <BrainCircuit size={10} /> Neural_Cortex_v2.1
                </span>
                <span className="text-[10px] font-mono text-green-500">CONFIDENCE: HIGH</span>
              </div>
              <div className="p-4 font-mono text-xs leading-relaxed text-gray-300">
                <span className="text-green-500 mr-2">root@aureon:~$</span>
                {aiReasoning}
                <span className="animate-pulse inline-block w-1.5 h-3 bg-green-500 ml-1 align-middle"/>
              </div>
            </div>
          )}

          {/* B. THE COMPARISON ENGINE */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="grid grid-cols-2 bg-slate-50 border-b border-slate-200 text-[10px] font-bold uppercase tracking-widest text-slate-500 py-2 px-4">
              <div>Broker Ledger</div>
              <div>Bank Statement</div>
            </div>

            {/* Row 1: Symbol / Desc */}
            <div className="grid grid-cols-2 border-b border-slate-100 divide-x divide-slate-100">
              <div className="p-4">
                <label className="text-[10px] text-slate-400 font-mono block mb-1">SYMBOL</label>
                <div className="font-bold text-sm text-slate-900">{trade.symbol}</div>
                <div className="text-xs text-slate-500 font-mono mt-0.5">{trade.isin || "NO_ISIN"}</div>
              </div>
              <div className="p-4 bg-slate-50/50">
                <label className="text-[10px] text-slate-400 font-mono block mb-1">NARRATION</label>
                <div className="font-medium text-xs text-slate-700 leading-snug font-mono break-all">
                  {candidate.description || "NO MATCH CANDIDATE"}
                </div>
              </div>
            </div>

            {/* Row 2: Amounts (The Critical Part) */}
            <div className="grid grid-cols-2 divide-x divide-slate-100 relative">
              <div className="p-4">
                 <label className="text-[10px] text-slate-400 font-mono block mb-1">AMOUNT</label>
                 <div className="text-lg font-bold font-mono text-slate-900">
                    {formatCurrency(tradeAmt)}
                 </div>
              </div>
              <div className="p-4 relative">
                 <label className="text-[10px] text-slate-400 font-mono block mb-1">MATCH AMOUNT</label>
                 <div className={`text-lg font-bold font-mono ${!candidate.id ? 'text-slate-300' : 'text-slate-900'}`}>
                    {candidate.id ? formatCurrency(cashAmt) : "---"}
                 </div>
                 
                 {/* Visual Connector for Diff */}
                 {candidate.id && !isPerfectMatch && (
                   <div className="absolute top-1/2 -left-3 -translate-y-1/2 bg-red-100 text-red-700 border border-red-200 px-1.5 py-0.5 rounded text-[10px] font-bold font-mono z-10 shadow-sm">
                      Δ {formatCurrency(diff)}
                   </div>
                 )}
              </div>
            </div>
            
            {/* Row 3: Dates */}
            <div className="grid grid-cols-2 border-t border-slate-100 divide-x divide-slate-100">
               <div className="p-3 flex justify-between items-center">
                  <span className="text-[10px] text-slate-400 font-mono">DATE</span>
                  <span className="text-xs font-mono font-medium">{formatDate(trade.date)}</span>
               </div>
               <div className="p-3 flex justify-between items-center">
                  <span className="text-[10px] text-slate-400 font-mono">VAL_DATE</span>
                  <span className={`text-xs font-mono font-medium ${trade.date !== candidate.date ? 'text-amber-600' : ''}`}>
                    {formatDate(candidate.date)}
                  </span>
               </div>
            </div>
          </div>

          {/* C. METADATA GRID */}
          <div className="grid grid-cols-2 gap-3">
             <div className="p-3 bg-white border border-slate-200 rounded-lg">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                   <Hash size={12} /> <span className="text-[10px] font-bold uppercase">Source File</span>
                </div>
                <div className="text-xs font-mono truncate" title={trade.source_file}>
                  {trade.source_file || "Unknown"}
                </div>
             </div>
             <div className="p-3 bg-white border border-slate-200 rounded-lg">
                <div className="flex items-center gap-2 text-slate-400 mb-1">
                   <Scale size={12} /> <span className="text-[10px] font-bold uppercase">Break Type</span>
                </div>
                <div className="text-xs font-mono font-medium text-slate-700">
                  {breakItem.break_type || "UNCLASSIFIED"}
                </div>
             </div>
          </div>

        </div>

        {/* --- 3. FOOTER ACTIONS --- */}
        <div className="p-5 border-t border-slate-200 bg-white shrink-0 space-y-3">
          {breakItem.status !== 'MATCHED' ? (
            <button 
              onClick={() => onResolve(breakItem.id)}
              className="w-full py-3.5 bg-slate-900 hover:bg-black text-white text-sm font-bold uppercase tracking-wide rounded-lg shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2 group active:scale-[0.98]"
            >
              <Check size={16} className="text-[#D4AF37]" />
              Confirm Resolution
            </button>
          ) : (
            <div className="w-full py-3 bg-green-50 border border-green-200 text-green-700 text-sm font-bold uppercase tracking-wide rounded-lg flex items-center justify-center gap-2">
               <Check size={16} /> Resolved
            </div>
          )}
          
          <button 
            onClick={onClose}
            className="w-full py-3 text-xs font-bold text-slate-400 hover:text-slate-600 uppercase tracking-wide transition-colors"
          >
            Dismiss Analysis
          </button>
        </div>

      </motion.div>
    </>
  );
};

export default BreakDrawer;
