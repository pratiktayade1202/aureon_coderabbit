// src/pages/Landing.jsx
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, ShieldCheck, GitPullRequest, History,
  Lock, AlertTriangle, FileText, ChevronRight, 
  Terminal, X, Eye, RefreshCcw, Server, Activity
} from "lucide-react";
import AnimatedBackground from "../components/AnimatedBackground";
import PitchDeck from "./PitchDeck"; 

// --- IMPORT IMAGES ---
import heroImg from "../assets/dashboard-hero.png";
import founderImg from "../assets/founder-pratik.jpg";
import logoImg from "../assets/logo.png";

// --- REUSABLE COMPONENTS ---

const Badge = ({ text }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded bg-gray-50 border border-gray-200 text-[10px] font-mono font-medium text-gray-600 mb-8 uppercase tracking-widest"
  >
    <div className="w-1.5 h-1.5 rounded-full bg-[#D4AF37]" />
    {text}
  </motion.div>
);

const SectionDivider = ({ label }) => (
  <div className="flex items-center gap-4 py-16 opacity-40 max-w-7xl mx-auto px-6">
    <div className="h-[1px] bg-gray-300 flex-1"></div>
    <span className="font-mono text-[10px] uppercase tracking-widest text-gray-500">{label}</span>
    <div className="h-[1px] bg-gray-300 flex-1"></div>
  </div>
);

const Navbar = ({ onLogin, onInvestorAccess }) => (
  <nav className="fixed top-0 w-full z-50 border-b border-gray-200/80 bg-[#FDFCF8]/95 backdrop-blur-xl">
    <div className="max-w-7xl mx-auto px-6 h-16 flex justify-between items-center">
      <div className="flex items-center">
        <img 
            src={logoImg} 
            alt="Aureon" 
            className="h-14 w-auto object-contain grayscale opacity-90 hover:opacity-100 transition-opacity" 
        />
      </div>
      
      <div className="hidden md:flex items-center gap-8 text-xs font-mono font-medium text-gray-500 uppercase tracking-wide">
        {["Safety Model", "Audit", "Architecture", "Contact"].map((item) => (
            <a key={item} href={`#${item.toLowerCase().replace(/ /g, '-')}`} className="hover:text-[#1A1A1A] transition-colors duration-200">
                {item}
            </a>
        ))}
      </div>

      <div className="flex gap-4 items-center">
        <button 
          onClick={onInvestorAccess}
          className="hidden md:flex text-xs font-medium text-gray-500 hover:text-[#1A1A1A] transition-colors items-center gap-1.5"
        >
          <Lock size={12} />
          Investor Access
        </button>
        <button onClick={onLogin} className="px-5 py-2 bg-[#1A1A1A] text-white text-xs font-mono uppercase tracking-wide rounded hover:bg-black transition-all flex items-center gap-2">
          Request Pilot Access
        </button>
      </div>
    </div>
  </nav>
);

const ProtocolCard = ({ icon: Icon, title, status, desc }) => (
  <div className="p-6 border border-gray-200 bg-white rounded hover:border-gray-400 transition-colors duration-300 group">
    <div className="flex justify-between items-start mb-4">
        <div className="w-10 h-10 bg-gray-50 border border-gray-100 rounded flex items-center justify-center">
            <Icon size={18} className="text-[#1A1A1A]" />
        </div>
        <span className="text-[10px] font-mono text-gray-400 border border-gray-100 px-2 py-1 rounded bg-gray-50">{status}</span>
    </div>
    <h3 className="text-sm font-bold text-[#1A1A1A] uppercase tracking-wide mb-2">{title}</h3>
    <p className="text-sm text-gray-600 leading-relaxed font-light">{desc}</p>
  </div>
);

// --- MAIN PAGE ---
const LandingPage = ({ onLogin }) => {
  const [showInvestorModal, setShowInvestorModal] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [showPitchDeck, setShowPitchDeck] = useState(false);
  
  const handleLoginClick = () => {
    onLogin();
  };

  const handleInvestorLogin = (e) => {
    e.preventDefault();
    if (password === "aureon2025") {
      setShowInvestorModal(false);
      setPassword("");
      setError("");
      setShowPitchDeck(true);
    } else {
      setError("ACCESS DENIED");
    }
  };

  if (showPitchDeck) {
    return <PitchDeck onExit={() => setShowPitchDeck(false)} />;
  }

  return (
    <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A] font-sans selection:bg-gray-200 selection:text-black overflow-x-hidden">
      
      <Navbar onLogin={handleLoginClick} onInvestorAccess={() => setShowInvestorModal(true)} />

      {/* HERO SECTION - AUTHORITY & TRUST */}
      <section className="relative pt-32 md:pt-40 pb-20 px-4 md:px-8 max-w-7xl mx-auto text-center">
        <AnimatedBackground /> 

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="relative z-10 flex flex-col items-center"
        >
          <Badge text="DESIGN PARTNER PROGRAM: OPEN (3/5 SPOTS)" />
          
          <h1 className="font-sans text-4xl md:text-6xl font-bold text-[#1A1A1A] leading-tight tracking-tight mb-6 max-w-4xl mx-auto">
            The Pre-Ledger <br/>
            Intelligence Layer.
          </h1>
          
          <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-8 leading-relaxed font-light px-4">
            Aureon normalizes unstructured broker data before it touches your accounting system. 
            <span className="block mt-2 font-medium text-gray-800">
                Hybrid Architecture. Deterministic Guardrails. Human-in-the-loop.
            </span>
          </p>

          <p className="font-mono text-[10px] text-gray-400 uppercase tracking-widest mb-10 border-b border-gray-200 pb-1">
             Built for Fund Controllers & Heads of Operations
          </p>

          <div className="flex flex-col md:flex-row justify-center gap-4 mb-16 w-full md:w-auto px-4">
              <button onClick={handleLoginClick} className="px-8 py-3 bg-[#1A1A1A] text-white font-mono text-xs uppercase tracking-widest rounded hover:bg-black transition-all flex items-center justify-center gap-3">
                 Request Pilot Access
                 <ArrowRight size={14} className="text-[#D4AF37]" />
              </button>
              <button className="px-8 py-3 bg-white border border-gray-200 text-[#1A1A1A] font-mono text-xs uppercase tracking-widest rounded hover:bg-gray-50 transition-all flex items-center justify-center gap-2">
                View Architecture
              </button>
          </div>

          {/* DASHBOARD PREVIEW - FOCUSED ON 'CONTROL' */}
          <div className="relative w-full max-w-5xl group px-4">
             <div className="absolute -inset-2 bg-gray-200/50 rounded-lg blur-xl opacity-50"></div>
            <motion.div 
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="relative rounded border border-gray-200 bg-white shadow-xl overflow-hidden"
            >
                <div className="absolute top-0 w-full h-8 bg-gray-50 border-b border-gray-200 flex items-center px-4 justify-between z-20">
                   <div className="flex items-center gap-2">
                      <Lock size={10} className="text-gray-400" />
                      <span className="font-mono text-[10px] text-gray-500">SECURE_ENV // READ_ONLY</span>
                   </div>
                   <span className="font-mono text-[10px] text-[#D4AF37]">AUDIT_LOG_ACTIVE</span>
                </div>
                <div className="pt-8 bg-gray-50">
                     <img src={heroImg} alt="Aureon Dashboard" className="w-full h-auto object-cover opacity-95 grayscale-[20%]" />
                </div>
            </motion.div>
            <p className="mt-4 font-mono text-[10px] text-gray-400 uppercase tracking-widest">
                Fig 1.0: Maker-Checker Interface with Explainable AI
            </p>
          </div>

        </motion.div>
      </section>
      
      <SectionDivider label="FAILURE & RECOVERY MODEL" />

      {/* THE "SAFETY" SECTION - CRITICAL ADDITION */}
      <section id="safety-model" className="py-12 bg-gray-50 border-y border-gray-200">
         <div className="max-w-7xl mx-auto px-6">
            <div className="text-center mb-16">
                <h2 className="text-2xl font-bold mb-2">Engineered for Skeptics.</h2>
                <p className="text-gray-500 text-sm font-mono uppercase tracking-wide">We assume systems fail. Here is how we handle it.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
                <ProtocolCard 
                    icon={ShieldCheck}
                    title="Read-Only Sandbox"
                    status="DEFAULT"
                    desc="Aureon operates in a strict pre-ledger environment. It suggests matches but cannot mutate your official accounting records. You retain the 'Commit' key."
                />
                <ProtocolCard 
                    icon={GitPullRequest}
                    title="Maker-Checker Native"
                    status="ENFORCED"
                    desc="AI acts as the 'Maker' (Drafting matches). A Human acts as the 'Checker' (Approving matches). Zero-touch automation is disabled by design."
                />
                <ProtocolCard 
                    icon={History}
                    title="Immutable Versioning"
                    status="LOGGED"
                    desc="No data is ever overwritten. Every change is logged, versioned, and replayable. If a match is incorrect, you can revert to the previous state instantly."
                />
            </div>

            {/* THE BLAST RADIUS PROMISE */}
            <div className="max-w-3xl mx-auto bg-white border border-gray-200 p-6 rounded-lg text-center shadow-sm">
                <div className="flex justify-center mb-3">
                    <Activity size={20} className="text-gray-400" />
                </div>
                <h4 className="text-sm font-bold text-[#1A1A1A] uppercase tracking-wide mb-2">The Worst-Case Failure Mode</h4>
                <p className="text-sm text-gray-600 leading-relaxed">
                    If the system cannot confidently match a trade, or if you reject a suggestion, it simply flags it as an exception. 
                    <span className="font-semibold text-gray-900"> The process gracefully degrades to your existing manual workflow. </span>
                    There is zero risk of data loss or silent corruption.
                </p>
            </div>

         </div>
      </section>

      <SectionDivider label="METHODOLOGY" />

      {/* ARCHITECTURE / HOW IT WORKS */}
      <section id="architecture" className="py-12 px-6 max-w-7xl mx-auto">
         <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
            <div>
                <h2 className="text-2xl font-bold mb-6">The Hybrid Pipeline.</h2>
                <div className="space-y-8">
                    <div className="flex gap-4 group">
                        <div className="w-8 h-8 rounded bg-gray-100 text-gray-500 group-hover:bg-[#1A1A1A] group-hover:text-white transition-colors flex items-center justify-center font-mono text-xs font-bold shrink-0">01</div>
                        <div>
                            <h4 className="font-bold text-sm uppercase tracking-wide mb-1">Unstructured Ingestion</h4>
                            <p className="text-sm text-gray-600">Drag-and-drop raw broker files (PDF/XLS). No templates required. The system identifies the schema automatically.</p>
                        </div>
                    </div>
                    <div className="flex gap-4 group">
                        <div className="w-8 h-8 rounded bg-gray-100 text-gray-500 group-hover:bg-[#1A1A1A] group-hover:text-white transition-colors flex items-center justify-center font-mono text-xs font-bold shrink-0">02</div>
                        <div>
                            <h4 className="font-bold text-sm uppercase tracking-wide mb-1">Hybrid Resolution</h4>
                            <p className="text-sm text-gray-600">
                                <span className="font-semibold">Layer 1:</span> Deterministic SQL (Exact Math).<br/>
                                <span className="font-semibold">Layer 2:</span> Context-Aware AI (Fuzzy Logic).<br/>
                                <span className="font-semibold">Layer 3:</span> Exception Queue (Human).
                            </p>
                        </div>
                    </div>
                    <div className="flex gap-4 group">
                        <div className="w-8 h-8 rounded bg-gray-100 text-gray-500 group-hover:bg-[#1A1A1A] group-hover:text-white transition-colors flex items-center justify-center font-mono text-xs font-bold shrink-0">03</div>
                        <div>
                            <h4 className="font-bold text-sm uppercase tracking-wide mb-1">Structured Export</h4>
                            <p className="text-sm text-gray-600">Standardized output files ready for ingestion into Geneva, Miles, or internal ledgers.</p>
                        </div>
                    </div>
                </div>
            </div>
            
            {/* ARCHITECTURE DIAGRAM REPLACEMENT */}
            <div className="bg-[#0A0A0A] p-8 rounded-lg border border-gray-800 font-mono text-xs shadow-2xl">
                <div className="flex justify-between text-gray-500 mb-6 pb-4 border-b border-gray-800">
                    <span>SYS_PIPELINE</span>
                    <span className="text-green-500">● LIVE</span>
                </div>
                <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-[#111] border border-gray-800 rounded text-gray-400">
                        <span className="flex items-center gap-2"><FileText size={12}/> Input: ICICI_Contract.pdf</span>
                        <span className="text-[10px] bg-gray-800 px-1 rounded">RAW</span>
                    </div>
                    <div className="flex justify-center">
                        <ArrowRight size={14} className="rotate-90 text-gray-600" />
                    </div>
                    <div className="flex items-center justify-between p-3 bg-[#111] border border-gray-700 text-white rounded">
                        <span className="flex items-center gap-2"><Server size={12}/> Process: Hybrid_Engine</span>
                        <span className="text-[#D4AF37] text-[10px]">RECONCILING</span>
                    </div>
                    <div className="flex justify-center">
                        <ArrowRight size={14} className="rotate-90 text-gray-600" />
                    </div>
                    <div className="flex items-center justify-between p-3 bg-green-900/20 border border-green-900/50 rounded text-green-400">
                        <span className="flex items-center gap-2"><Terminal size={12}/> Output: Trade_Log.csv</span>
                        <span className="font-bold text-[10px]">READY</span>
                    </div>
                </div>
            </div>
         </div>
      </section>

      {/* FOUNDER NOTE - AUTHORITY */}
      <section className="py-24 bg-white border-t border-gray-100 mt-12">
        <div className="max-w-4xl mx-auto px-6 flex flex-col md:flex-row items-start gap-8">
            <img 
                src={founderImg} 
                alt="Pratik Tayade" 
                className="w-20 h-20 grayscale object-cover rounded border border-gray-200"
            />
            <div className="flex-1">
                <div className="flex items-center gap-2 mb-4 text-[#1A1A1A]">
                    <Terminal size={14} />
                    <span className="text-xs font-mono uppercase tracking-widest">Architect's Note</span>
                </div>
                <p className="text-gray-700 text-lg leading-relaxed mb-6 font-light">
                    "We didn't build Aureon to 'disrupt' your operations; we built it to stabilize them. Having led integrations at FactSet for Tier-1 banks, I know that in infrastructure, 'boring' is a feature. We optimize for correctness first, automation second."
                </p>
                <div>
                    <p className="font-bold text-[#1A1A1A] text-sm">Pratik Tayade</p>
                    <p className="text-xs text-gray-500 font-mono mt-0.5">Ex-FactSet Lead Integration Specialist</p>
                </div>
            </div>
        </div>
      </section>

      {/* SCARCITY CTA */}
      <section className="py-20 bg-[#FDFCF8] border-t border-gray-200 text-center">
          <div className="max-w-2xl mx-auto px-6">
              <h2 className="text-2xl font-bold mb-4">Pilot Program: Design Partners</h2>
              <p className="text-gray-500 mb-8 text-sm leading-relaxed">
                  We are currently onboarding a limited set of AIFs/PMS to stress-test our ingestion engine. 
                  This is a hands-on implementation directly with the founder.
              </p>
              <button onClick={handleLoginClick} className="px-8 py-3 bg-[#1A1A1A] text-white font-mono text-xs uppercase tracking-widest rounded hover:bg-black transition-all mx-auto shadow-lg hover:shadow-xl">
                  Request Pilot Access (Ops-Led Funds Only)
              </button>
              <div className="mt-8 flex justify-center gap-8 opacity-50 grayscale">
                <div className="h-6 w-24 bg-gray-200 rounded"></div>
                <div className="h-6 w-24 bg-gray-200 rounded"></div>
                <div className="h-6 w-24 bg-gray-200 rounded"></div>
              </div>
          </div>
      </section>

      {/* FOOTER - INFRASTRUCTURE VIBE */}
      <footer className="bg-white pt-16 pb-8 px-6 border-t border-gray-200 font-mono text-xs text-gray-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start gap-8">
            <div>
                <img src={logoImg} alt="Aureon" className="h-8 w-auto object-contain mb-4 grayscale opacity-60" />
                <p className="max-w-xs">
                    Pre-Ledger Intelligence Layer.<br/>
                    Navi Mumbai, India.
                </p>
            </div>
            <div className="flex gap-12">
                <ul className="space-y-2">
                    <li className="uppercase text-gray-300 mb-2">Platform</li>
                    <li><a href="#" className="hover:text-black">Architecture</a></li>
                    <li><a href="#" className="hover:text-black">Failure Protocol</a></li>
                </ul>
                <ul className="space-y-2">
                    <li className="uppercase text-gray-300 mb-2">Legal</li>
                    <li><a href="#" className="hover:text-black">Terms</a></li>
                    <li><a href="#" className="hover:text-black">Privacy</a></li>
                </ul>
            </div>
        </div>
        <div className="max-w-7xl mx-auto pt-8 mt-12 border-t border-gray-100 flex justify-between items-center">
            <p>© 2025 Aureon.</p>
            <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                <span>SYSTEM_OPERATIONAL</span>
            </div>
        </div>
      </footer>

      {/* --- INVESTOR ACCESS MODAL --- */}
      <AnimatePresence>
        {showInvestorModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => { setShowInvestorModal(false); setPassword(""); setError(""); }}
              className="absolute inset-0 bg-[#FDFCF8]/90 backdrop-blur-sm"
            />
            
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-sm bg-white rounded border border-gray-200 shadow-2xl overflow-hidden"
            >
              <div className="px-6 py-8">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-[#1A1A1A] flex items-center gap-2 font-mono uppercase tracking-widest">
                      <Lock size={12} />
                      Restricted Area
                    </h3>
                  </div>
                  <button onClick={() => setShowInvestorModal(false)} className="text-gray-400 hover:text-black">
                    <X size={16} />
                  </button>
                </div>

                <form onSubmit={handleInvestorLogin} className="space-y-4">
                  <div>
                    <input 
                      type="password"
                      autoFocus
                      placeholder="ACCESS_CODE"
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setError(""); }}
                      className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-black transition-all text-xs font-mono"
                    />
                    {error && (
                      <p className="text-red-600 text-[10px] mt-2 font-mono flex items-center gap-1">
                        <AlertTriangle size={10} /> {error}
                      </p>
                    )}
                  </div>
                  
                  <button 
                    type="submit"
                    className="w-full bg-[#1A1A1A] hover:bg-black text-white font-bold py-3 rounded transition-all text-xs font-mono uppercase tracking-widest"
                  >
                    Authenticate
                  </button>
                </form>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default LandingPage;