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
  
  // Explicitly track if we found breaks to keep the button stable
  const [hasBreaks, setHasBreaks] = useState(false);
  const [resolveTrade, setResolveTrade] = useState(null);
  
  // Prevent double-fetching on mount
  const hasFetched = useRef(false);

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
        
        // Pending settlements = unsettled trades + open breaks
        const pending = (data.trades?.unsettled || 0) + (data.breaks?.open || 0);
        
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
    } catch (e) { 
      console.error("Failed to fetch stats:", e); 
    }
  }, [getToken]);

  // Full data refresh function
  const refreshAllData = useCallback(async () => {
    try {
      const token = await getToken();
      
      // Fetch stats
      fetchStats();
      
      // Fetch trades
      const { rows, pagination } = await api.getTrades(token);
      setReconData(rows);
      setTradePagination(pagination);
      checkBreaks(rows);
      
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

  const checkBreaks = (rows) => {
    const foundBreaks = rows.some((row) => {
      const status = row.status;
      // Handle both old string format and new object format
      if (typeof status === "object" && status !== null) {
        return status.status === "BREAK" || status.status === "UNSETTLED";
      }
      const statusStr = (status || "").toLowerCase();
      return statusStr.includes("break") || statusStr.includes("unsettled");
    });
    setHasBreaks(foundBreaks);
  };

  // -----------------------------
  // RUN ENGINE
  // -----------------------------
  const runSettlementEngine = async () => {
    setIsProcessing(true);
    try {
      const token = await getToken();
      if (dataView === "Trades") {
        // Run reconciliation first
        await api.runReconciliation(token);
        // Then fetch updated trades
        const { rows, pagination } = await api.getTrades(token);
        setReconData(rows);
        setTradePagination(pagination);
        checkBreaks(rows); // Update button state immediately
      } else if (dataView === "Holdings") {
        const data = await api.runPositionRecon(token);
        const rows = Array.isArray(data) ? data : [];
        setHoldingsData(rows);
        setHasBreaks(false);
      }
      await fetchStats();
    } catch (e) {
      alert(`Engine Run Failed: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // -----------------------------
  // AI AUTO-RESOLVE
  // -----------------------------
  const runAiResolve = async () => {
    setIsProcessing(true);
    try {
      const token = await getToken();
      const result = await api.runAiResolve(token);
      // Refresh list to show "SETTLED (AI)"
      const { rows, pagination } = await api.getTrades(token); 
      setReconData(rows);
      setTradePagination(pagination);
      checkBreaks(rows);
      await fetchStats();
      
      if (result?.resolved > 0) alert(`AI Successfully Resolved ${result.resolved} breaks.`);
      else alert("AI found no high-confidence matches.");

    } catch (e) {
      alert("AI agent failed: " + e.message);
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
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/recon/export-data`, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      if (!res.ok) {
        const data = await res.json();
        alert(data.message || "Export not yet implemented");
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; 
      a.download = "aureon_export.csv";
      document.body.appendChild(a); 
      a.click(); 
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) { 
      alert("Export failed: " + e.message); 
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

                  {/* STABLE BUTTON LOGIC */}
                  {hasBreaks && dataView === "Trades" ? (
                    <button onClick={runAiResolve} disabled={isProcessing} className="h-9 px-4 bg-aureon-blue text-white rounded-md flex items-center gap-2 text-xs hover:bg-blue-700">
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <BrainCircuit size={14} />}
                      Auto-Resolve ({stats.pending_settlements})
                    </button>
                  ) : (
                    <button onClick={runSettlementEngine} disabled={isProcessing} className="h-9 px-4 bg-slate-900 text-white rounded-md flex items-center gap-2 text-xs hover:bg-black">
                      {isProcessing ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />}
                      Run Settlement
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

                <DataTable view={dataView} reconData={reconData} holdingsData={holdingsData} navData={navData} onResolve={setResolveTrade} />
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
            trade={resolveTrade} 
            onClose={() => setResolveTrade(null)} 
            onSuccess={() => {
                fetchStats();
                // Manually update the row locally to avoid full reload flicker
                setReconData(prev => prev.map(r => r.id === resolveTrade.id ? { ...r, status: "SETTLED (MANUAL)" } : r));
                setResolveTrade(null);
            }} 
          />
        </div>
      </SignedIn>
    </>
  );
}

export default App;