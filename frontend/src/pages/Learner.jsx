// src/pages/Learner.jsx
import React, { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  BrainCircuit,
  RefreshCw,
  Loader2,
  TrendingUp,
  CheckCircle2,
  Filter,
} from "lucide-react";
import { useAureonApi } from "../hooks/useAureonApi";

import PatternList from "../components/neural/PatternList";
import PatternInspector from "../components/neural/PatternInspector";

/**
 * Neural Core (Learner)
 *
 * Dual-pane institutional view:
 *  - Left: pattern list
 *  - Right: inspector
 *  - Top: KPIs + retrain
 */

const Learner = () => {
  const api = useAureonApi();
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [search, setSearch] = useState("");

  const fetchRules = async () => {
    setLoading(true);
    try {
      const data = await api.getLearnedRules();
      const arr = data || [];
      setPatterns(arr);
      if (arr.length > 0 && !selectedId) {
        setSelectedId(arr[0].id);
      }
    } catch (e) {
      console.error("[NeuralCore] fetchRules failed", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runTraining = async () => {
    setTraining(true);
    try {
      await api.learnRules();
      await fetchRules();
    } catch (e) {
      alert("Training failed: " + e.message);
    } finally {
      setTraining(false);
    }
  };

  const selectedPattern = useMemo(
    () => patterns.find((p) => p.id === selectedId),
    [patterns, selectedId]
  );

  const totalApplied = useMemo(
    () => patterns.reduce((acc, r) => acc + (r.applied || 0), 0),
    [patterns]
  );

  const avgConfidence = useMemo(() => {
    if (!patterns.length) return 0;
    const sum = patterns.reduce(
      (acc, r) => acc + (Math.max(0, Math.min(r.confidence ?? 0, 1)) || 0),
      0
    );
    return Math.round((sum / patterns.length) * 100);
  }, [patterns]);

  const highImpactCount = useMemo(
    () =>
      patterns.filter(
        (r) => (r.applied || 0) > 10 && (r.confidence || 0) >= 0.8
      ).length,
    [patterns]
  );

  return (
    <div className="max-w-[1300px]">
      {/* Header */}
      <div className="mb-6 border-b border-aureon-border pb-3 flex justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BrainCircuit size={18} className="text-aureon-gold" />
            <h1 className="text-[1.35rem] font-semibold text-ink-strong tracking-tight">
              Neural Core
            </h1>
          </div>
          <p className="text-[11px] text-ink-muted mt-1 flex items-center gap-2">
            <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-700">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              ONLINE
            </span>
            <span>Learned rules from manual resolutions and engine feedback.</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button className="h-8 px-2.5 text-[11px] rounded-md border border-aureon-border bg-paper-surface text-ink-muted flex items-center gap-1">
            <Filter size={12} /> Filters
          </button>
          <button
            onClick={runTraining}
            disabled={training}
            className="h-8 px-3 text-[11px] rounded-md bg-slate-900 text-white font-semibold flex items-center gap-1 hover:bg-black disabled:opacity-70"
          >
            {training ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RefreshCw size={12} />
            )}
            {training ? "Training..." : "Retrain Model"}
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        {[
          {
            label: "Active Patterns",
            val: patterns.length,
            icon: Filter,
          },
          {
            label: "Total Applications",
            val: totalApplied,
            icon: CheckCircle2,
          },
          {
            label: "Average Confidence",
            val: `${avgConfidence}%`,
            icon: TrendingUp,
          },
          {
            label: "High-Impact Rules",
            val: highImpactCount,
            icon: BrainCircuit,
          },
        ].map((stat, i) => (
          <div
            key={i}
            className="bg-paper-surface border border-aureon-border rounded-md px-3 py-3 flex items-center justify-between"
          >
            <div>
              <p className="text-[10px] font-semibold text-ink-muted uppercase tracking-wide">
                {stat.label}
              </p>
              <p className="text-[1.1rem] font-mono font-semibold text-ink-strong">
                {stat.val}
              </p>
            </div>
            <div className="p-1.5 rounded-sm bg-slate-100 text-ink-muted">
              <stat.icon size={18} />
            </div>
          </div>
        ))}
      </div>

      {/* Main content: dual pane */}
      {loading ? (
        <div className="py-16 text-center text-ink-muted text-sm flex items-center justify-center gap-2">
          <Loader2 className="animate-spin" size={16} /> Loading learned rules…
        </div>
      ) : patterns.length === 0 ? (
        <div className="py-16 text-center text-ink-muted text-sm">
          No patterns learned yet. Resolve a few breaks manually and retrain the
          model to see emerging rules here.
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-[320px_minmax(0,1fr)] gap-3 h-[520px]"
        >
          <PatternList
            patterns={patterns}
            selectedId={selectedId}
            onSelect={setSelectedId}
            search={search}
            onSearchChange={setSearch}
          />
          <PatternInspector pattern={selectedPattern} />
        </motion.div>
      )}
    </div>
  );
};

export default Learner;
