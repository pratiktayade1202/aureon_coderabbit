// src/App.jsx
import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import Ingestion from "./pages/Ingestion";
import {
  Download,
  Loader2,
  BrainCircuit,
  FileClock,
  RotateCw,
  CheckSquare,
  CheckCircle,
} from "lucide-react";

import {
  SignedIn,
  SignedOut,
  SignIn,
  useClerk,
  useAuth,
} from "@clerk/clerk-react";

import Sidebar from "./components/Sidebar";
import StatsGrid from "./components/StatsGrid";
import DataTable from "./components/DataTable";
import SettingsView from "./components/SettingsView";
import LandingPage from "./pages/Landing";
import LogViewerModal from "./components/LogViewerModal";
import BreakDrawer from "./components/BreakDrawer";
import Learner from "./pages/Learner";
import PitchDeck from "./pages/PitchDeck";
import api from "./services/aureonApi";
import { API_BASE_URL } from "./config";

const API_BASE = API_BASE_URL;

function App() {
  const { signOut } = useClerk();
  const { getToken } = useAuth();

  const [showSignIn, setShowSignIn] = useState(false);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [dataView, setDataView] = useState("Trades");

  const [stats, setStats] = useState({ total_assets: 0, pending_settlements: 0 });
  const [reconData, setReconData] = useState([]);
  const [tradePagination, setTradePagination] = useState(null);
  const [holdingsData, setHoldingsData] = useState([]);
  const [navData, setNavData] = useState([]);

  const [isProcessing, setIsProcessing] = useState(false);
  const [showLogModal, setShowLogModal] = useState(false);
  
  // Track workflow phase and button to display
  const [workflowStatus, setWorkflowStatus] = useState({
    button_to_show: null,
    current_phase: "PHASE_0_NO_DATA",
    next_action: "",
    pending_proposals: 0,
  });
  const [resolveTrade, setResolveTrade] = useState(null);
  const [selectedTradeIds, setSelectedTradeIds] = useState([]);
  const [selectionResetKey, setSelectionResetKey] = useState(0);
  
  // Prevent double-fetching on mount
  const hasFetched = useRef(false);

  // -----------------------------
  // FETCH WORKFLOW STATUS
  // -----------------------------
  const fetchWorkflowStatus = useCallback(async () => {
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/recon/workflow-status`, {
        headers: { Authorization: `Bearer ${token || "dev-token"}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWorkflowStatus({
          button_to_show: data.workflow?.button_to_show || null,
          current_phase: data.workflow?.current_phase || "PHASE_0_NO_DATA",
          next_action: data.workflow?.next_action || "",
          pending_proposals: data.workflow?.pending_proposals || 0,
        });
      }
    } catch (e) {
      console.error("Failed to fetch workflow status:", e);
    }
  }, [getToken]);

  // -----------------------------
  // FETCH DASHBOARD STATS
  // -----------------------------
  const fetchStats = useCallback(async () => {
    try {
      const token = await getToken();
      const data = await api.getStats(token);
      if (data) {
        // Map backend response to frontend format
        // AUC (Assets Under Custody) priority:
        // 1. holdings.total_auc - actual custody value
        // 2. summary.auc - pre-computed value
        // 3. trades.total_amount - fallback to trade volume
        let auc = data.holdings?.total_auc || 0;
        if (auc === 0) {
          auc = data.summary?.auc || data.trades?.total_amount || 0;
        }
        
        // Pending settlements:
        // Backend now provides a correct, non-double-counting number.
        // Fallback to legacy math only if the backend field isn't present.
        const pending =
          typeof data.pending_settlements === "number"
            ? data.pending_settlements
            : (data.trades?.unsettled || 0) + (data.breaks?.open || 0);
        
        setStats({
          total_assets: auc,
          pending_settlements: pending,
          // Include all backend data for reference
          holdings: data.holdings,
          nav: data.nav,
          trades: data.trades,
          cash: data.cash,
          breaks: data.breaks,
          reconciliation: data.reconciliation,
          summary: data.summary,
        });
      }
      
      // Also fetch workflow status
      await fetchWorkflowStatus();
    } catch (e) { 
      console.error("Failed to fetch stats:", e); 
    }
  }, [getToken, fetchWorkflowStatus]);

  // Full data refresh function
  const refreshAllData = useCallback(async () => {
    try {
      const token = await getToken();
      
      // Fetch stats and workflow status
      fetchStats();
      
      // Fetch trades
      const { rows, pagination } = await api.getTrades(token);
      setReconData(rows);
      setTradePagination(pagination);
      
      // Fetch holdings
      const holdingsRes = await api.runPositionRecon(token);
      setHoldingsData(Array.isArray(holdingsRes) ? holdingsRes : []);
      
      // Fetch NAV
      const navRes = await fetch(`${API_BASE}/recon/nav`, {
        headers: { Authorization: `Bearer ${token || "dev-token"}` }
      });
      if (navRes.ok) {
        const navData = await navRes.json();
        setNavData(Array.isArray(navData) ? navData : []);
      }
    } catch (e) {
      console.error("Failed to refresh data:", e);
    }
  }, [getToken, fetchStats]);

  // Initial Load Logic
  useEffect(() => {
    if (activeTab === "Dashboard" && !hasFetched.current) {
      hasFetched.current = true;
      refreshAllData();
    }
  }, [activeTab, refreshAllData]);

  // -----------------------------
  // RUN SETTLEMENT ENGINE (PHASE 2 - DETERMINISTIC)
  // -----------------------------
  const runSettlementEngine = async () => {
    setIsProcessing(true);
    try {
      const token = await getToken();
      
      // Call the new Phase 2 endpoint
      const res = await fetch(`${API_BASE}/recon/run-settlement-engine`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${token || "dev-token"}`,
          "Content-Type": "application/json"
        }
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || "Settlement engine failed");
      }
      
      // Refresh all data and workflow status
      await refreshAllData();
      
    } catch (e) {
      alert(`Settlement Engine Failed: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // -----------------------------
  // AUTO-RESOLVE (PHASE 3 - AI)
  // -----------------------------
  const runAiResolve = async () => {
    setIsProcessing(true);
    try {
      const token = await getToken();
      
      // Call the Phase 3 endpoint
      const res = await fetch(`${API_BASE}/recon/auto-resolve`, {
        method: "POST",
        headers: { 
          Authorization: `Bearer ${token || "dev-token"}`,
          "Content-Type": "application/json"
        }
      });
      
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || "AI auto-resolve failed");
      }
      
      const result = await res.json();
      
      // Refresh all data and workflow status
      await refreshAllData();
      
      const proposals = result?.proposals_count ?? result?.ai_results?.proposals_created ?? 0;
      if (proposals > 0) {
        alert(`AI generated ${proposals} proposals for review.`);
      } else if (result?.resolved > 0) {
        // Backward compatibility if any older behavior remains
        alert(`AI Successfully Resolved ${result.resolved} breaks.`);
      } else {
        alert("AI found no high-confidence proposals.");
      }

    } catch (e) {
      alert("AI agent failed: " + e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  // -----------------------------
  // COMMIT AI PROPOSALS (AIR GAP EXECUTOR)
  // -----------------------------
  const handleCommit = async () => {
    const count = workflowStatus.pending_proposals || "pending";
    if (!window.confirm(`Commit ${count} AI proposals to the ledger?`)) return;

    setIsProcessing(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/recon/proposals/commit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token || "dev-token"}`,
        },
        body: JSON.stringify({ min_confidence: 0.8 }),
      });

      if (!res.ok) throw new Error("Commit failed");

      const result = await res.json();
      alert(`Success! Committed ${result.committed} matches.`);
      await refreshAllData();
    } catch (e) {
      alert("Commit Error: " + e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const resetDatabase = async () => {
    if(!window.confirm("Confirm reset? This will delete all data for your tenant.")) return;
    try {
      const token = await getToken();
      await api.resetDb(token);
      window.location.reload();
    } catch (e) { 
      alert("Reset failed: " + e.message); 
    }
  };

  const handleExport = async () => {
    setIsProcessing(true); // Show loading spinner
    try {
      const token = await getToken();
      
      // 1. Call the new CSV endpoint
      const res = await fetch(`${API_BASE}/recon/export-csv`, { 
        headers: { Authorization: `Bearer ${token || "dev-token"}` } 
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || data.message || "Export failed");
      }
      
      // 2. Convert response to a Downloadable Blob
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      
      // 3. Trigger Browser Download
      const a = document.createElement("a");
      a.href = url;
      
      // Attempt to get filename from headers, else default
      const contentDisposition = res.headers.get("Content-Disposition");
      let filename = `aureon_export_${new Date().toISOString().split("T")[0]}.csv`;
      if (contentDisposition && contentDisposition.includes("filename=")) {
        filename = contentDisposition.split("filename=")[1].replace(/\"/g, "").trim();
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      
      // 4. Cleanup
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) { 
      console.error("Export Error:", e);
      alert("Failed to download report: " + e.message); 
    } finally {
      setIsProcessing(false);
    }
  };

  // -----------------------------
  // BULK RESOLVE (POWER USER)
  // -----------------------------
  const handleBulkResolve = async () => {
    const count = selectedTradeIds.length;
    if (!count) return;

    if (!window.confirm(`Are you sure you want to mark ${count} trades as Manually Resolved?`)) {
      return;
    }

    setIsProcessing(true);
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/recon/resolve-bulk`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token || "dev-token"}`,
        },
        body: JSON.stringify({
          trade_ids: selectedTradeIds,
          note: "Bulk Manual Resolve via Dashboard",
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || "Bulk resolve failed");
      }

      const result = await res.json();
      alert(`Success! Resolved: ${result.resolved_count}, Failed: ${result.failed_count}`);

      setSelectedTradeIds([]);
      setSelectionResetKey((k) => k + 1);
      await refreshAllData();
    } catch (e) {
      alert(e.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <SignedOut>
        {showSignIn && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="absolute inset-0" onClick={() => setShowSignIn(false)} />
            <div className="relative z-10"><SignIn /></div>
          </div>
        )}
        <LandingPage onLogin={() => setShowSignIn(true)} />
      </SignedOut>

      <SignedIn>
        {activeTab === "Investor Deck" ? (
          <PitchDeck onExit={() => setActiveTab("Dashboard")} />
        ) : (
          <div className="min-h-screen bg-paper-canvas text-ink-strong flex">
            <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
            <main className="flex-1 ml-60 px-8 py-8 max-w-[1600px] mx-auto">

            {activeTab === "Dashboard" && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <div className="mb-4 border-b border-aureon-border pb-4">
                  <h1 className="text-xl font-semibold">Settlement Overview</h1>
                  <p className="text-xs text-ink-muted mt-1 flex items-center gap-2">
                    <span className="w-2 h-2 bg-status-success rounded-full" />
                    System Operational • {new Date().toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-3 mb-4">
                  <button onClick={() => setShowLogModal(true)} className="h-9 w-9 border border-aureon-border rounded-md flex items-center justify-center bg-white hover:bg-slate-50">
                    <FileClock size={16} />
                  </button>
                  <button onClick={handleExport} className="h-9 px-3 border border-aureon-border rounded-md flex items-center gap-2 text-xs bg-white hover:bg-slate-50">
                    <Download size={14} /> Export
                  </button>

                  {/* 3-PHASE WORKFLOW BUTTONS - Based on backend button_to_show */}
                  {workflowStatus.button_to_show === "RUN_SETTLEMENT_ENGINE" && (
                    <button 
                      onClick={runSettlementEngine} 
                      disabled={isProcessing} 
                      className="h-9 px-4 bg-slate-900 text-white rounded-md flex items-center gap-2 text-xs hover:bg-black disabled:opacity-50"
                    >
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />}
                      Run Settlement Engine
                    </button>
                  )}
                  
                  {workflowStatus.button_to_show === "AUTO_RESOLVE" && (
                    <button 
                      onClick={runAiResolve} 
                      disabled={isProcessing} 
                      className="h-9 px-4 bg-aureon-blue text-white rounded-md flex items-center gap-2 text-xs hover:bg-blue-700 disabled:opacity-50"
                    >
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <BrainCircuit size={14} />}
                      Auto-Resolve (AI) {stats.pending_settlements > 0 && `(${stats.pending_settlements})`}
                    </button>
                  )}

                  {workflowStatus.button_to_show === "REVIEW_AND_COMMIT" && (
                    <button
                      onClick={handleCommit}
                      disabled={isProcessing}
                      className="h-9 px-4 bg-purple-600 text-white rounded-md flex items-center gap-2 text-xs hover:bg-purple-700 disabled:opacity-50 font-bold shadow-sm"
                    >
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                      Commit AI Proposals ({workflowStatus.pending_proposals || "..."})
                    </button>
                  )}
                  
                  {workflowStatus.current_phase === "PHASE_3_COMPLETE" && (
                    <div className="h-9 px-4 bg-green-50 border border-green-200 rounded-md flex items-center gap-2 text-xs text-green-700">
                      ✓ Reconciliation Complete
                    </div>
                  )}
                  
                  {/* Fallback: Show Run Settlement if we have data but workflow status failed */}
                  {workflowStatus.button_to_show === null && 
                   workflowStatus.current_phase === "PHASE_0_NO_DATA" && 
                   reconData.length > 0 && (
                    <button 
                      onClick={runSettlementEngine} 
                      disabled={isProcessing} 
                      className="h-9 px-4 bg-slate-900 text-white rounded-md flex items-center gap-2 text-xs hover:bg-black disabled:opacity-50"
                    >
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />}
                      Run Settlement Engine
                    </button>
                  )}
                </div>

                <StatsGrid stats={stats} />

                <div className="inline-flex border border-aureon-border rounded-md mb-3 bg-white">
                  {["Trades", "Holdings", "NAV"].map((tab) => (
                    <button key={tab} onClick={() => setDataView(tab)} className={`px-3 py-1.5 text-[11px] uppercase tracking-wide border-r border-aureon-border last:border-r-0 ${dataView === tab ? "bg-slate-900 text-white" : "text-ink-muted hover:bg-slate-50"}`}>
                      {tab}
                    </button>
                  ))}
                </div>

                <DataTable
                  view={dataView}
                  reconData={reconData}
                  holdingsData={holdingsData}
                  navData={navData}
                  onResolve={setResolveTrade}
                  onSelectionChange={setSelectedTradeIds}
                  selectionResetKey={selectionResetKey}
                />
              </motion.div>
            )}

            {activeTab === "Ingestion" && (
              <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <div className="mb-6 border-b border-aureon-border pb-4">
                  <h1 className="text-xl font-semibold">Data Ingestion</h1>
                </div>
                <Ingestion onUploadComplete={() => {
                    setActiveTab("Dashboard");
                    hasFetched.current = false; // Force refresh on arrival
                }} />
              </motion.div>
            )}

            {activeTab === "Neural Core" && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}><Learner /></motion.div>}
            {activeTab === "Settings" && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}><SettingsView resetDatabase={resetDatabase} /></motion.div>}

          </main>

          <LogViewerModal isOpen={showLogModal} onClose={() => setShowLogModal(false)} />
          <BreakDrawer 
            isOpen={!!resolveTrade} 
            breakItem={resolveTrade} 
            onClose={() => setResolveTrade(null)} 
            onResolve={async (breakId) => {
              if (!breakId) return;
              
              // 1. Optimistic UI Update (Instant feedback)
              setReconData(prev => prev.map(r => 
                r.id === breakId ? { ...r, status: "SETTLED (MANUAL)" } : r
              ));
              setResolveTrade(null);

              // 2. Call the Backend to save it
              try {
                const token = await getToken();
                // Assumes your API has a resolve endpoint. 
                // If not, we can use the generic update endpoint.
                await fetch(`${API_BASE}/recon/resolve-manual/${breakId}`, {
                   method: 'POST',
                   headers: { Authorization: `Bearer ${token}` }
                });
                
                // 3. Refresh real stats in background
                fetchStats();
              } catch (e) {
                console.error("Manual resolution failed:", e);
                // Optionally revert the UI change here on error
                alert("Failed to save resolution. Please try again.");
                refreshAllData();
              }
            }}
          />

            {/* Floating Bulk Action Bar */}
            {selectedTradeIds.length > 0 && (
              <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 z-50">
                <motion.div
                  initial={{ y: 20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  className="bg-slate-900 text-white px-6 py-3 rounded-full shadow-xl flex items-center gap-4 border border-slate-700"
                >
                  <div className="flex items-center gap-2">
                    <CheckSquare size={16} className="text-aureon-blue" />
                    <span className="font-semibold text-sm">{selectedTradeIds.length} Selected</span>
                  </div>
                  <div className="h-4 w-px bg-slate-700"></div>
                  <button
                    onClick={handleBulkResolve}
                    disabled={isProcessing}
                    className="text-sm font-bold text-aureon-blue hover:text-white transition-colors disabled:opacity-50"
                  >
                    Resolve Selected
                  </button>
                  <button
                    onClick={() => {
                      setSelectedTradeIds([]);
                      setSelectionResetKey((k) => k + 1);
                    }}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    Cancel
                  </button>
                </motion.div>
              </div>
            )}
          </div>
        )}
      </SignedIn>
    </>
  );
}

export default App;