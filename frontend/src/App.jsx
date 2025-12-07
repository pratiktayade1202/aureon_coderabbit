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

import { useAureonApi } from "./hooks/useAureonApi";
import Sidebar from "./components/Sidebar";
import StatsGrid from "./components/StatsGrid";
import DataTable from "./components/DataTable";
import SettingsView from "./components/SettingsView";
import LandingPage from "./pages/Landing";
import LogViewerModal from "./components/LogViewerModal";
import BreakDrawer from "./components/BreakDrawer";
import Learner from "./pages/Learner";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function App() {
  const { signOut } = useClerk();
  const { getToken } = useAuth();
  const api = useAureonApi();

  const [showSignIn, setShowSignIn] = useState(false);
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [dataView, setDataView] = useState("Trades");

  const [stats, setStats] = useState({ total_assets: 0, pending_settlements: 0 });
  const [reconData, setReconData] = useState([]);
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
      const data = await api.getStats();
      if (data) setStats(data);
    } catch (e) { console.error(e); }
  }, [api]);

  // Initial Load Logic
  useEffect(() => {
    if (activeTab === "Dashboard" && !hasFetched.current) {
      hasFetched.current = true;
      fetchStats();
      if (dataView === "Trades") {
        api.getTrades().then(data => {
           const rows = Array.isArray(data) ? data : [];
           setReconData(rows);
           checkBreaks(rows);
        }).catch(() => {});
      }
    }
  }, [activeTab, fetchStats, api, dataView]);

  const checkBreaks = (rows) => {
    const foundBreaks = rows.some((row) =>
      (row.status || "").toLowerCase().includes("break")
    );
    setHasBreaks(foundBreaks);
  };

  // -----------------------------
  // RUN ENGINE
  // -----------------------------
  const runSettlementEngine = async () => {
    setIsProcessing(true);
    try {
      if (dataView === "Trades") {
        const data = await api.getTrades(); // Trigger Engine
        const rows = Array.isArray(data) ? data : [];
        setReconData(rows);
        checkBreaks(rows); // Update button state immediately
      } else if (dataView === "Holdings") {
        const data = await api.runPositionRecon();
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
      const result = await api.runAiResolve();
      // Refresh list to show "SETTLED (AI)"
      const data = await api.getTrades(); 
      setReconData(Array.isArray(data) ? data : []);
      setHasBreaks(false); // Reset button since we just resolved them
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
    if(!window.confirm("Confirm reset?")) return;
    try {
      await api.resetDb();
      window.location.reload();
    } catch (e) { alert("Reset failed"); }
  };

  const handleExport = async () => {
    try {
      const token = await getToken();
      const res = await fetch(`${API_BASE}/export-data`, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "aureon_export.csv";
      document.body.appendChild(a); a.click(); a.remove();
    } catch (e) { alert("Export failed"); }
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