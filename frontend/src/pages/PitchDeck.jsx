import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronRight,
  ChevronLeft,
  Database,
  BrainCircuit,
  ShieldCheck,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FileSpreadsheet,
  TrendingUp,
  Users,
  Building2,
  ArrowRight,
  X,
  Lock,
  Activity,
  Terminal,
  Code2,
  FileCheck,
  Layout,
  LayoutDashboard
} from "lucide-react";
import logoImg from "../assets/logo.png";

// --- REUSABLE COMPONENTS FOR DECK ---

const Badge = ({ text, variant = "default" }) => {
  const variants = {
    default: "bg-gray-100 text-gray-600 border-gray-200",
    gold: "bg-amber-50 text-amber-700 border-amber-200", // Adapted for Tailwind colors
    red: "bg-red-50 text-red-600 border-red-200",
    green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${variants[variant]} uppercase tracking-wider`}
    >
      {text}
    </span>
  );
};

const TerminalCard = ({ title, children, className = "" }) => (
  <div
    className={`rounded-xl border border-gray-200 bg-white/50 backdrop-blur-sm shadow-xl ${className}`}
  >
    {title && (
      <div className="px-4 py-3 border-b border-gray-200/50 flex items-center gap-2 bg-gray-50/50 rounded-t-xl">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-gray-300"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-gray-300"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-gray-300"></div>
        </div>
        <span className="ml-2 text-[10px] font-mono text-gray-400 uppercase tracking-widest">
          {title}
        </span>
      </div>
    )}
    <div className="p-6">{children}</div>
  </div>
);

// --- SLIDES DATA ---
// Defined outside component to avoid recreation on render
const SLIDES = [
  // 1. TITLE
  {
    id: "title",
    layout: "centered",
    render: () => (
      <div className="text-center relative z-10">
        <Badge text="Series Seed Pitch" variant="gold" />
        <div className="mt-8 flex justify-center mb-6">
          <img 
            src={logoImg} 
            alt="Aureon" 
            className="h-24 md:h-32 w-auto object-contain" 
          />
        </div>
        <p className="mt-6 text-2xl md:text-3xl font-light text-gray-500 max-w-3xl mx-auto leading-relaxed">
          The Operating System for <br />
          <span className="text-ink-strong font-medium">
            Post-Trade Finance in India
          </span>
        </p>
        <div className="mt-12 flex justify-center gap-8 text-sm font-mono text-gray-400">
          <span className="flex items-center gap-2">
            <Zap size={14} /> AI-Native
          </span>
          <span className="flex items-center gap-2">
            <ShieldCheck size={14} /> Deterministic Settlement
          </span>
          <span className="flex items-center gap-2">
            <Activity size={14} /> Live Ops
          </span>
        </div>
      </div>
    ),
  },
  // 2. THE PROBLEM
  {
    id: "problem",
    layout: "split",
    title: "The Reality in Indian Asset Management",
    subtitle: "This is not a tech problem. It's an ops tax.",
    left: () => (
      <div className="space-y-6">
        <div className="p-4 rounded-lg bg-red-50 border border-red-100">
          <h3 className="flex items-center gap-2 text-red-800 font-semibold mb-2">
            <AlertTriangle size={18} /> The Current State
          </h3>
          <ul className="space-y-2 text-sm text-red-700/80">
            <li>• Multiple brokers & custodians (NSDL, CDSL)</li>
            <li>• Inconsistent PDF, CSV, Excel formats</li>
            <li>• Missing fields & manual "adjustments"</li>
            <li>• 6-8 hours/day spent on VLOOKUPs</li>
          </ul>
        </div>
        <div className="space-y-2">
          <p className="text-lg font-medium text-ink-strong">
            For one mid-sized fund:
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
              <div className="text-2xl font-bold text-ink-strong">2-4</div>
              <div className="text-xs text-gray-500 uppercase">Ops Analysts</div>
            </div>
            <div className="p-3 bg-white border border-gray-200 rounded-lg text-center">
              <div className="text-2xl font-bold text-ink-strong">40-60%</div>
              <div className="text-xs text-gray-500 uppercase">
                Time on Recon
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    right: () => (
      <TerminalCard
        title="legacy_ops_process.xlsx"
        className="h-full bg-gray-50"
      >
        <div className="space-y-3 font-mono text-xs opacity-75">
          <div className="flex gap-2 text-red-500">
            <span>[ERROR]</span>
            <span>Row 482: ISIN mismatch (INE002A01018)</span>
          </div>
          <div className="flex gap-2 text-red-500">
            <span>[ERROR]</span>
            <span>Row 912: Net amount deviation &gt; 0.05</span>
          </div>
          <div className="flex gap-2 text-gray-400">
            <span>[INFO]</span>
            <span>Attempting manual override...</span>
          </div>
          <div className="flex gap-2 text-gray-400">
            <span>[INFO]</span>
            <span>Loading "Final_Final_v3.xlsx"...</span>
          </div>
          <div className="mt-8 p-4 border-2 border-dashed border-red-200 rounded text-center text-red-400">
            Human Error Rate: High
            <br />
            Scalability: Zero
          </div>
        </div>
      </TerminalCard>
    ),
  },
  // 3. QUANTIFYING PAIN
  {
    id: "pain_quantified",
    layout: "split",
    title: "Quantifying the Pain",
    subtitle: "Real numbers from the Indian market.",
    left: () => (
      <div className="space-y-8">
        <div>
          <h3 className="text-xl font-bold mb-4">Annual Recon Cost Per Fund</h3>
          <div className="flex items-end gap-4">
            <div className="text-5xl font-mono font-bold text-aureon-gold">
              ₹18 Lakhs
            </div>
            <div className="text-sm text-gray-500 mb-2">
              / year (Conservative)
            </div>
          </div>
          <p className="text-sm text-gray-500 mt-2">
            Based on ₹8-12 LPA analysts x 3 headcount x 50% time allocation.
          </p>
        </div>
        <div className="p-4 bg-gray-100 rounded-lg border-l-4 border-gray-900">
          <p className="text-sm italic text-gray-700">
            "That’s just salary. It doesn't include the cost of{" "}
            <strong>compliance risks</strong>, <strong>trade breaks</strong>, or
            the <strong>opportunity cost</strong> of your best people doing data
            entry."
          </p>
        </div>
      </div>
    ),
    right: () => (
      <TerminalCard title="cost_breakdown.json">
        <div className="space-y-4">
          <div className="flex justify-between items-center text-sm pb-2 border-b border-gray-100">
            <span className="text-gray-500">Base Salary Load</span>
            <span className="font-mono">₹36,00,000</span>
          </div>
          <div className="flex justify-between items-center text-sm pb-2 border-b border-gray-100">
            <span className="text-gray-500">Reconciliation Allocation (50%)</span>
            <span className="font-mono text-red-600">- ₹18,00,000</span>
          </div>
          <div className="flex justify-between items-center text-sm pb-2 border-b border-gray-100">
            <span className="text-gray-500">Error Correction Overhead</span>
            <span className="font-mono text-red-600">- ₹4,50,000</span>
          </div>
          <div className="flex justify-between items-center text-sm font-bold pt-2">
            <span>Total Burn</span>
            <span className="font-mono">₹22,50,000 / yr</span>
          </div>
        </div>
      </TerminalCard>
    ),
  },
  // 4. TIME WASTED vs AUREON
  {
    id: "time_comparison",
    layout: "centered",
    title: "The Killer Metric: Time",
    render: () => (
      <div className="w-full max-w-4xl mx-auto mt-10">
        <div className="grid grid-cols-2 gap-8">
          {/* Today */}
          <div className="p-6 bg-white border border-gray-200 rounded-xl opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
            <div className="flex items-center gap-3 mb-6">
              <Clock className="text-gray-400" />
              <h3 className="text-xl font-bold">Today</h3>
            </div>
            <div className="space-y-3">
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-gray-400 w-full"></div>
              </div>
              <div className="flex justify-between text-sm text-gray-500 font-mono">
                <span>File Chasing</span>
                <span>60 min</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-gray-400 w-3/4"></div>
              </div>
              <div className="flex justify-between text-sm text-gray-500 font-mono">
                <span>Data Cleaning</span>
                <span>120 min</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-gray-400 w-full"></div>
              </div>
              <div className="flex justify-between text-sm text-gray-500 font-mono">
                <span>Matching Logic</span>
                <span>120 min</span>
              </div>
              <div className="mt-6 pt-6 border-t border-gray-100 flex justify-between items-center">
                <span className="font-bold text-ink-strong">Total Cycle</span>
                <span className="text-2xl font-mono font-bold text-red-600">
                  4-7 Hours
                </span>
              </div>
            </div>
          </div>

          {/* Aureon */}
          <div className="p-6 bg-white border border-aureon-gold/30 rounded-xl shadow-2xl relative overflow-hidden">
            <div className="absolute top-0 right-0 p-2 bg-aureon-gold text-white text-xs font-bold">
              95% SAVINGS
            </div>
            <div className="flex items-center gap-3 mb-6">
              <Zap className="text-aureon-gold" />
              <h3 className="text-xl font-bold">With Aureon</h3>
            </div>
            <div className="space-y-3">
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-aureon-gold w-[5%]"></div>
              </div>
              <div className="flex justify-between text-sm text-ink-strong font-mono">
                <span>Ingestion</span>
                <span>2 min</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-aureon-gold w-[2%]"></div>
              </div>
              <div className="flex justify-between text-sm text-ink-strong font-mono">
                <span>Auto-Match</span>
                <span>1 min</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full w-full overflow-hidden">
                <div className="h-full bg-aureon-gold w-[10%]"></div>
              </div>
              <div className="flex justify-between text-sm text-ink-strong font-mono">
                <span>AI Resolution</span>
                <span>5 min</span>
              </div>
              <div className="mt-6 pt-6 border-t border-gray-100 flex justify-between items-center">
                <span className="font-bold text-ink-strong">Total Cycle</span>
                <span className="text-2xl font-mono font-bold text-green-600">
                  ~15 Mins
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
  },
  // 5. WHY NOT SOLVED
  {
    id: "market_gap",
    layout: "centered",
    title: "Why This Hasn't Been Solved",
    render: () => (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10 max-w-6xl mx-auto">
        <div className="p-6 border border-gray-200 rounded-xl bg-white hover:border-gray-300 transition-colors">
          <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mb-4">
            <FileSpreadsheet size={20} className="text-gray-500" />
          </div>
          <h3 className="font-bold text-lg mb-2">Excel + Scripts</h3>
          <p className="text-sm text-gray-500">
            Cheap but fragile. Doesn't scale. Entirely dependent on one person
            knowing the macros.
          </p>
        </div>
        <div className="p-6 border border-gray-200 rounded-xl bg-white hover:border-gray-300 transition-colors">
          <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mb-4">
            <Building2 size={20} className="text-gray-500" />
          </div>
          <h3 className="font-bold text-lg mb-2">Global Giants</h3>
          <p className="text-sm text-gray-500">
            FactSet/Bloomberg are overkill, expensive, and rigid. They aren't
            built for messy Indian PDF formats.
          </p>
        </div>
        <div className="p-6 border border-gray-200 rounded-xl bg-white hover:border-gray-300 transition-colors">
          <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mb-4">
            <Terminal size={20} className="text-gray-500" />
          </div>
          <h3 className="font-bold text-lg mb-2">In-House Tools</h3>
          <p className="text-sm text-gray-500">
            One-off builds that die when the founder/CTO leaves. No learning loop
            across funds.
          </p>
        </div>
        <div className="md:col-span-3 mt-6 text-center">
          <p className="text-lg font-medium text-ink-strong">
            Nobody built a Post-Trade OS specifically for{" "}
            <span className="underline decoration-aureon-gold decoration-2">
              Indian Ops Reality
            </span>
            .
          </p>
        </div>
      </div>
    ),
  },
  // 6. SOLUTION
  {
    id: "solution",
    layout: "split",
    title: "Aureon: The Solution",
    subtitle: "AI-native reconciliation engine with deterministic safety.",
    left: () => (
      <div className="space-y-6">
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center font-bold text-sm">
            1
          </div>
          <div>
            <h4 className="font-bold">Ingest Anything</h4>
            <p className="text-sm text-gray-500">
              Broker notes, Bank PDFs, Custodian CSVs. Normalizes messy formats
              automatically.
            </p>
          </div>
        </div>
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center font-bold text-sm">
            2
          </div>
          <div>
            <h4 className="font-bold">Deterministic Core</h4>
            <p className="text-sm text-gray-500">
              Runs strict SQL logic first. 95% of trades match here. Zero
              hallucinations.
            </p>
          </div>
        </div>
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-aureon-gold text-white flex items-center justify-center font-bold text-sm">
            3
          </div>
          <div>
            <h4 className="font-bold">AI Agent (Glass Box)</h4>
            <p className="text-sm text-gray-500">
              Only handles breaks. Explains reasoning. Learns from human
              corrections.
            </p>
          </div>
        </div>
        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-sm font-semibold text-ink-strong">
            No Excel. No Scripts. No Hero Analysts.
          </p>
        </div>
      </div>
    ),
    right: () => (
      <TerminalCard
        title="system_status.log"
        className="bg-slate-900 text-white border-none"
      >
        <div className="font-mono text-xs space-y-2">
          <div className="text-green-400">✓ Ingestion Module: ACTIVE</div>
          <div className="text-green-400">✓ SQL Engine: 4,210 matched</div>
          <div className="text-yellow-400">⚠ Unresolved Breaks: 12</div>
          <div className="pl-4 border-l border-gray-700 my-2">
            <div className="text-blue-400">→ Handing over to AI Agent...</div>
            <div className="text-gray-400">
              Analyzing Trade #992 vs Cash Ledger...
            </div>
            <div className="text-gray-400">
              Pattern Found: "Forex Adjustment"
            </div>
            <div className="text-purple-400">
              Result: Match Proposed (98% Conf)
            </div>
          </div>
          <div className="text-green-400">✓ Ledger Updated.</div>
        </div>
      </TerminalCard>
    ),
  },
  // 7. ARCHITECTURE
  {
    id: "architecture",
    layout: "centered",
    title: "Hybrid Architecture",
    subtitle: "Our moat against generic AI wrappers.",
    render: () => (
      <div className="mt-10 max-w-5xl mx-auto flex flex-col md:flex-row items-stretch gap-4">
        {/* Phase 1 */}
        <div className="flex-1 p-6 bg-white border border-gray-200 rounded-xl flex flex-col items-center text-center">
          <Badge text="Phase 1" variant="default" />
          <div className="my-6 p-4 bg-gray-100 rounded-full">
            <Database size={32} />
          </div>
          <h3 className="font-bold text-lg">Deterministic Engine</h3>
          <p className="text-xs text-gray-500 mt-2 px-4">
            Fast, Auditable, Zero Hallucinations. Handles the bulk volume.
          </p>
        </div>

        <div className="flex items-center justify-center text-gray-300">
          <ArrowRight />
        </div>

        {/* Phase 2 */}
        <div className="flex-1 p-6 bg-amber-50/50 border border-aureon-gold/30 rounded-xl flex flex-col items-center text-center relative overflow-hidden">
          <div className="absolute top-0 right-0 p-1 bg-aureon-gold text-[10px] text-white font-bold px-2 rounded-bl">
            IP
          </div>
          <Badge text="Phase 2" variant="gold" />
          <div className="my-6 p-4 bg-amber-100/50 text-amber-700 rounded-full">
            <BrainCircuit size={32} />
          </div>
          <h3 className="font-bold text-lg text-ink-strong">
            AI Reasoning Layer
          </h3>
          <p className="text-xs text-gray-600 mt-2 px-4">
            Contextual matching for breaks. Confidence scored. "Glass-box"
            explanations.
          </p>
        </div>

        <div className="flex items-center justify-center text-gray-300">
          <ArrowRight />
        </div>

        {/* Phase 3 */}
        <div className="flex-1 p-6 bg-white border border-gray-200 rounded-xl flex flex-col items-center text-center">
          <Badge text="Phase 3" variant="green" />
          <div className="my-6 p-4 bg-emerald-50 text-emerald-600 rounded-full">
            <Users size={32} />
          </div>
          <h3 className="font-bold text-lg">Human Loop</h3>
          <p className="text-xs text-gray-500 mt-2 px-4">
            Manual overrides feed back into the model to improve future accuracy.
          </p>
        </div>
      </div>
    ),
  },
  // 8. PRICING
  {
    id: "pricing",
    layout: "centered",
    title: "Pricing Strategy",
    subtitle: "India-friendly, high-volume, reliable SaaS.",
    render: () => (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-10 max-w-5xl mx-auto">
        <div className="p-6 bg-white border border-gray-200 rounded-xl">
          <div className="text-sm font-bold text-gray-400 uppercase mb-2">
            Starter
          </div>
          <div className="text-3xl font-bold">
            ₹50k{" "}
            <span className="text-sm font-normal text-gray-500">/mo</span>
          </div>
          <ul className="mt-6 space-y-3 text-sm text-gray-600">
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> 1-2 Funds
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> Daily Recon
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> CSV Ingestion
            </li>
          </ul>
        </div>
        <div className="p-6 bg-white border-2 border-aureon-gold rounded-xl relative shadow-xl transform scale-105">
          <div className="absolute top-0 right-0 left-0 bg-aureon-gold text-white text-xs font-bold text-center py-1">
            TARGET WEDGE
          </div>
          <div className="text-sm font-bold text-aureon-gold uppercase mb-2 mt-4">
            Growth
          </div>
          <div className="text-3xl font-bold">
            ₹1 Lakh{" "}
            <span className="text-sm font-normal text-gray-500">/mo</span>
          </div>
          <ul className="mt-6 space-y-3 text-sm text-ink-strong font-medium">
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-aureon-gold" /> Multiple
              Funds
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-aureon-gold" /> Priority
              Ingestion
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-aureon-gold" /> Break
              Analytics
            </li>
          </ul>
        </div>
        <div className="p-6 bg-white border border-gray-200 rounded-xl">
          <div className="text-sm font-bold text-gray-400 uppercase mb-2">
            Enterprise
          </div>
          <div className="text-3xl font-bold">
            ₹3 Lakh+{" "}
            <span className="text-sm font-normal text-gray-500">/mo</span>
          </div>
          <ul className="mt-6 space-y-3 text-sm text-gray-600">
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> Custom Rules
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> Dedicated
              Instance
            </li>
            <li className="flex gap-2">
              <CheckCircle2 size={16} className="text-gray-400" /> On-Prem Option
            </li>
          </ul>
        </div>
      </div>
    ),
  },
  // 9. MARKET
  {
    id: "market",
    layout: "split",
    title: "Market Size (India Only)",
    subtitle: "No global fantasies. Just the immediate serviceable market.",
    left: () => (
      <div className="space-y-8">
        <div>
          <h3 className="text-lg font-bold">Target Customer</h3>
          <p className="text-gray-500">
            PMS, AIFs, and Mid-sized Mutual Funds. ~2,000 entities in India.
          </p>
        </div>
        <div>
          <h3 className="text-lg font-bold">The Math</h3>
          <ul className="mt-2 space-y-2 font-mono text-sm">
            <li className="flex justify-between border-b border-gray-200 pb-1">
              <span>Target Accounts</span>
              <span>200 (10% pen.)</span>
            </li>
            <li className="flex justify-between border-b border-gray-200 pb-1">
              <span>Avg. Contract</span>
              <span>₹12L / yr</span>
            </li>
            <li className="flex justify-between font-bold pt-2 text-lg">
              <span>ARR Potential</span>
              <span className="text-aureon-gold">₹240 Cr</span>
            </li>
          </ul>
        </div>
        <p className="text-xs text-gray-400 italic">
          *This excludes Banks, Brokers, and Wealth Platforms.
        </p>
      </div>
    ),
    right: () => (
      <div className="h-full flex flex-col justify-center items-center bg-gray-50 rounded-xl border border-gray-200 p-8">
        <div className="w-48 h-48 rounded-full border-[16px] border-gray-200 relative flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-[16px] border-aureon-gold border-l-transparent border-b-transparent rotate-45"></div>
          <div className="text-center">
            <div className="text-3xl font-bold">₹50L+</div>
            <div className="text-xs text-gray-500 uppercase">Crore AUM</div>
          </div>
        </div>
        <div className="mt-8 text-center">
          <p className="font-medium text-ink-strong">
            Indian Asset Management
          </p>
          <p className="text-sm text-gray-500">
            Fastest growing financial sector in APAC.
          </p>
        </div>
      </div>
    ),
  },
  // 10. TRACTION
  {
    id: "traction",
    layout: "centered",
    title: "Traction: Early But Real",
    subtitle: "This is not a mockup. It is a working ops system.",
    render: () => (
      <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-5xl mx-auto">
        <div className="p-6 bg-white border border-gray-200 rounded-lg text-center">
          <Code2 className="mx-auto mb-4 text-gray-400" />
          <h3 className="font-bold">Core Engine</h3>
          <Badge text="Built" variant="green" />
        </div>
        <div className="p-6 bg-white border border-gray-200 rounded-lg text-center">
          <Activity className="mx-auto mb-4 text-gray-400" />
          <h3 className="font-bold">End-to-End</h3>
          <p className="text-xs text-gray-500 mt-1">Live Workflow</p>
        </div>
        <div className="p-6 bg-white border border-gray-200 rounded-lg text-center">
          <FileCheck className="mx-auto mb-4 text-gray-400" />
          <h3 className="font-bold">Data handling</h3>
          <p className="text-xs text-gray-500 mt-1">Messy Real-World Data</p>
        </div>
        <div className="p-6 bg-white border border-gray-200 rounded-lg text-center">
          <Layout className="mx-auto mb-4 text-gray-400" />
          <h3 className="font-bold">UI/UX</h3>
          <p className="text-xs text-gray-500 mt-1">Glass-box Operational</p>
        </div>
        <div className="col-span-2 md:col-span-4 mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg flex items-center justify-center gap-4">
          <span className="font-bold text-ink-strong">Current Status:</span>
          <span>Design Partner Onboarding</span>
        </div>
      </div>
    ),
  },
  // 11. WHY BIGGER THAN FACTSET
  {
    id: "vision",
    layout: "split",
    title: "Why We Can Be Bigger Than FactSet",
    subtitle: "Transitioning from Data Terminal to Operating System.",
    left: () => (
      <div className="space-y-6">
        <div className="p-4 bg-gray-100 rounded-lg">
          <h3 className="font-bold text-gray-600 mb-1">
            FactSet / Bloomberg
          </h3>
          <p className="text-sm text-gray-500">
            Sell information for consumption.
          </p>
        </div>
        <div className="p-4 bg-amber-50/50 border border-aureon-gold rounded-lg">
          <h3 className="font-bold text-ink-strong mb-1">Aureon</h3>
          <p className="text-sm text-gray-600">
            Owns the <strong>workflow</strong> and the{" "}
            <strong>data exhaust</strong>.
          </p>
        </div>
        <p className="text-sm text-gray-600 leading-relaxed">
          Once we control reconciliation, we own the "source of truth" for
          holdings. From there, we expand to Risk, Performance Attribution, and
          Benchmarking—not as an external feed, but as the internal OS.
        </p>
      </div>
    ),
    right: () => (
      <div className="relative h-full pl-8 border-l border-dashed border-gray-300 space-y-8">
        <div className="relative">
          <div className="absolute -left-[37px] w-4 h-4 rounded-full bg-slate-900"></div>
          <h4 className="font-bold">Phase 1: Reconciliation</h4>
          <p className="text-xs text-gray-500">
            Sticky, daily usage. Hard to rip out.
          </p>
        </div>
        <div className="relative opacity-50">
          <div className="absolute -left-[37px] w-4 h-4 rounded-full bg-gray-300"></div>
          <h4 className="font-bold">Phase 2: Ops Intelligence</h4>
          <p className="text-xs text-gray-500">
            Broker quality scoring, cash forecasting.
          </p>
        </div>
        <div className="relative opacity-30">
          <div className="absolute -left-[37px] w-4 h-4 rounded-full bg-gray-200"></div>
          <h4 className="font-bold">Phase 3: Financial Intelligence</h4>
          <p className="text-xs text-gray-500">
            Cross-fund benchmarking. The "Bloomberg" killer.
          </p>
        </div>
      </div>
    ),
  },
  // 12. TEAM
  {
    id: "team",
    layout: "centered",
    title: "The Team",
    subtitle: "Ops-native. Not just code-native.",
    render: () => (
      <div className="mt-12 flex justify-center">
        <div className="flex flex-col md:flex-row items-center gap-8 p-8 bg-white border border-gray-200 rounded-xl shadow-lg max-w-2xl">
          <div className="w-32 h-32 rounded-full border-4 border-gray-100 bg-gray-200 overflow-hidden">
            <img
              src="/src/assets/founder-pratik.jpg"
              alt="Founder"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.src =
                  "https://ui-avatars.com/api/?name=Pratik+Tayade&background=0D0D0D&color=fff&size=128";
              }}
            />
          </div>
          <div className="text-center md:text-left">
            <h3 className="text-2xl font-bold text-ink-strong">
              Pratik Tayade
            </h3>
            <p className="text-aureon-gold font-medium mb-4">
              Founder & Builder
            </p>
            <ul className="space-y-2 text-sm text-gray-600">
              <li className="flex items-center gap-2 justify-center md:justify-start">
                <CheckCircle2 size={14} /> Deep exposure to recon pain
              </li>
              <li className="flex items-center gap-2 justify-center md:justify-start">
                <CheckCircle2 size={14} /> Built core engine solo
              </li>
              <li className="flex items-center gap-2 justify-center md:justify-start">
                <CheckCircle2 size={14} /> Ops-first mindset
              </li>
            </ul>
          </div>
        </div>
      </div>
    ),
  },
  // 13. ASK
  {
    id: "ask",
    layout: "split",
    title: "The Ask",
    subtitle: "Fueling the transition from Pilot to Production.",
    left: () => (
      <div className="space-y-8">
        <div>
          <h3 className="text-xl font-bold mb-4 text-aureon-gold">
            Use of Funds
          </h3>
          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="p-1 bg-gray-100 rounded mt-1">
                <Users size={16} />
              </div>
              <div>
                <div className="font-bold text-ink-strong">
                  Core Engineering (3 FTE)
                </div>
                <div className="text-xs text-gray-500">
                  Hiring backend & AI engineers to harden the stack.
                </div>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="p-1 bg-gray-100 rounded mt-1">
                <ShieldCheck size={16} />
              </div>
              <div>
                <div className="font-bold text-ink-strong">
                  Enterprise Compliance
                </div>
                <div className="text-xs text-gray-500">
                  SOC2, Audits, Security hardening.
                </div>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="p-1 bg-gray-100 rounded mt-1">
                <TrendingUp size={16} />
              </div>
              <div>
                <div className="font-bold text-ink-strong">Sales Motion</div>
                <div className="text-xs text-gray-500">
                  Direct sales to Mid-market AIFs.
                </div>
              </div>
            </li>
          </ul>
        </div>
      </div>
    ),
    right: () => (
      <div className="h-full flex flex-col justify-center items-center text-center p-8 bg-black text-white rounded-xl">
        <Terminal size={48} className="text-aureon-gold mb-6" />
        <h3 className="text-2xl font-bold mb-2">Join the Cap Table</h3>
        <p className="text-gray-400 mb-8 max-w-xs">
          Help us build the financial operating system for India.
        </p>
        <div className="px-6 py-3 bg-aureon-gold text-black font-bold rounded hover:bg-amber-600 cursor-pointer transition-colors">
           aureon.ai.12@gmail.com
        </div>
      </div>
    ),
  },
];

const PitchDeck = ({ onExit }) => {
  const [currentSlide, setCurrentSlide] = useState(0);

  const nextSlide = () => {
    if (currentSlide < SLIDES.length - 1) {
      setCurrentSlide((curr) => curr + 1);
    }
  };

  const prevSlide = () => {
    if (currentSlide > 0) {
      setCurrentSlide((curr) => curr - 1);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "ArrowRight") nextSlide();
      if (e.key === "ArrowLeft") prevSlide();
      if (e.key === "Escape") onExit && onExit();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentSlide, onExit]);

  const SlideContent = SLIDES[currentSlide];

  return (
    <div className="fixed inset-0 z-50 bg-[#FDFCF8] flex flex-col overflow-hidden text-ink-strong">
      {/* TOP BAR */}
      <div className="absolute top-0 left-0 w-full h-16 flex items-center justify-between px-8 z-50">
        <div className="flex items-center gap-2">
          <img 
            src={logoImg} 
            alt="Aureon" 
            className="h-8 w-auto object-contain" 
          />
        </div>
        <div className="flex items-center gap-4">
          <span className="font-mono text-[10px] text-gray-400">
            {currentSlide + 1} / {SLIDES.length}
          </span>
          <button
            onClick={onExit}
            className="p-1 rounded hover:bg-gray-100 text-gray-500"
            title="Exit Deck"
          >
            <X size={20} />
          </button>
        </div>
      </div>

      {/* SLIDE CANVAS */}
      <div className="flex-1 flex items-center justify-center p-8 md:p-16 relative">
        {/* Background Elements */}
        <div
          className="absolute inset-0 z-0 pointer-events-none opacity-20"
          style={{
            backgroundImage: `linear-gradient(#E5E5E5 1px, transparent 1px), linear-gradient(to right, #E5E5E5 1px, transparent 1px)`,
            backgroundSize: "40px 40px",
          }}
        ></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] bg-aureon-gold opacity-[0.03] rounded-full blur-[100px] pointer-events-none"></div>

        {/* CONTENT */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentSlide}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="w-full max-w-7xl h-full flex flex-col z-10"
          >
            {SlideContent.layout === "centered" && (
              <div className="flex flex-col items-center justify-center h-full">
                {SlideContent.title && (
                  <h2 className="text-4xl md:text-5xl font-bold mb-4 text-center">
                    {SlideContent.title}
                  </h2>
                )}
                {SlideContent.subtitle && (
                  <p className="text-xl text-gray-500 mb-12 text-center max-w-2xl">
                    {SlideContent.subtitle}
                  </p>
                )}
                {SlideContent.render()}
              </div>
            )}

            {SlideContent.layout === "split" && (
              <div className="flex flex-col md:flex-row h-full gap-12 items-center">
                <div className="flex-1">
                  {SlideContent.title && (
                    <h2 className="text-4xl md:text-5xl font-bold mb-4 leading-tight">
                      {SlideContent.title}
                    </h2>
                  )}
                  {SlideContent.subtitle && (
                    <p className="text-xl text-gray-500 mb-8 border-l-4 border-aureon-gold pl-4">
                      {SlideContent.subtitle}
                    </p>
                  )}
                  {SlideContent.left()}
                </div>
                <div className="flex-1 h-full max-h-[600px] flex items-center justify-center">
                  {SlideContent.right()}
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* CONTROLS */}
      <div className="absolute bottom-8 right-8 flex gap-2 z-50">
        <button
          onClick={prevSlide}
          disabled={currentSlide === 0}
          className="p-3 bg-white border border-gray-200 rounded-full hover:bg-gray-50 disabled:opacity-30 transition-all shadow-sm text-ink-strong"
        >
          <ChevronLeft size={20} />
        </button>
        <button
          onClick={nextSlide}
          disabled={currentSlide === SLIDES.length - 1}
          className="p-3 bg-black text-white rounded-full hover:bg-gray-800 disabled:opacity-30 transition-all shadow-lg"
        >
          <ChevronRight size={20} />
        </button>
      </div>

      {/* ADVISOR NOTE */}
      <div className="absolute bottom-0 left-0 w-full p-2 bg-red-50/90 border-t border-red-200 text-red-800 text-xs font-mono text-center opacity-0 hover:opacity-100 transition-opacity duration-300 z-50">
        ADVISOR NOTE: Keep the narrative focused on Indian Ops Pain. Do not
        mention "Global Expansion" until Series A.
      </div>
    </div>
  );
};

export default PitchDeck;