// src/pages/Landing.jsx
import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, Shield, Zap, Globe, CheckCircle, Database,
  Lock, Server, Layers, Cpu, FileText, Activity, BrainCircuit, X,
  Terminal, ChevronRight, Code2, Users, Hash, GitCommit, FileJson
} from "lucide-react";
import AnimatedBackground from "../components/AnimatedBackground";
import PitchDeck from "./PitchDeck"; 

// --- IMPORT IMAGES ---
import heroImg from "../assets/dashboard-hero.png";
import archImg from "../assets/architecture-diagram.png";
import founderImg from "../assets/founder-pratik.jpg";
import logoImg from "../assets/logo.png";

// --- REUSABLE COMPONENTS ---

const Badge = ({ text, color = "bg-[#D4AF37]" }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-gray-200 shadow-sm text-xs font-mono font-medium text-gray-600 mb-8"
  >
    <span className="relative flex h-2 w-2">
      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${color} opacity-75`}></span>
      <span className={`relative inline-flex rounded-full h-2 w-2 ${color}`}></span>
    </span>
    {text}
  </motion.div>
);

const SectionDivider = ({ label }) => (
  <div className="flex items-center gap-4 py-8 opacity-40 max-w-7xl mx-auto px-6">
    <div className="h-[1px] bg-gray-400 flex-1"></div>
    <span className="font-mono text-[10px] uppercase tracking-widest text-gray-500">// {label}</span>
    <div className="h-[1px] bg-gray-400 flex-1"></div>
  </div>
);

const Navbar = ({ onLogin, onInvestorAccess }) => (
  <nav className="fixed top-0 w-full z-50 border-b border-gray-200/80 bg-[#FDFCF8]/80 backdrop-blur-xl supports-[backdrop-filter]:bg-[#FDFCF8]/60">
    <div className="max-w-7xl mx-auto px-6 h-16 flex justify-between items-center">
      <div className="flex items-center">
        <img 
            src={logoImg} 
            alt="Aureon" 
            className="h-20 w-auto object-contain" 
        />
      </div>
      
      <div className="hidden md:flex items-center gap-8 text-xs font-mono font-medium text-gray-500 uppercase tracking-wide">
        {["Architecture", "Security", "Protocols", "API"].map((item) => (
            <a key={item} href={`#${item.toLowerCase()}`} className="hover:text-[#1A1A1A] transition-colors duration-200">
                {item}
            </a>
        ))}
      </div>

      <div className="flex gap-4 items-center">
        <button 
          onClick={onInvestorAccess}
          className="text-xs font-medium text-gray-500 hover:text-[#1A1A1A] transition-colors border border-transparent hover:border-gray-200 px-3 py-1.5 rounded-md flex items-center gap-1.5"
        >
          <Lock size={12} />
          Investor Access
        </button>
        <button onClick={onLogin} className="text-xs font-medium text-gray-500 hover:text-[#1A1A1A] transition-colors border border-transparent hover:border-gray-200 px-3 py-1.5 rounded-md">
          Client Login
        </button>
        <button onClick={onLogin} className="group px-4 py-2 bg-[#1A1A1A] text-white text-sm font-medium rounded-lg hover:bg-black transition-all shadow-md hover:shadow-lg flex items-center gap-2 transform hover:-translate-y-0.5">
          Request Pilot
          <ChevronRight size={14} className="text-[#D4AF37] group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </div>
  </nav>
);

const ProtocolTicker = () => {
  // REPLACED BANKS WITH PROTOCOLS/STANDARDS
  const protocols = [
    "SWIFT MT940", "NSDL CAS", "CDSL", "FIX 4.4", "REST API", "GraphQL", 
    "PDF/Vision", "SHA-256", "Vectorized SQL", "ISO 20022", "OAuth 2.0"
  ];
  
  return (
    <div className="relative z-20 border-y border-gray-100 py-6 overflow-hidden flex bg-gray-50/50">
      <div className="absolute left-0 top-0 w-32 h-full bg-gradient-to-r from-[#FDFCF8] to-transparent z-10" />
      <div className="absolute right-0 top-0 w-32 h-full bg-gradient-to-l from-[#FDFCF8] to-transparent z-10" />
      
      <div className="flex whitespace-nowrap animate-ticker gap-16 opacity-60">
        {[...protocols, ...protocols, ...protocols].map((proto, i) => (
          <span key={i} className="text-sm font-mono font-medium text-gray-500 flex items-center gap-2">
             <Hash size={12} className="text-[#D4AF37]" /> {proto}
          </span>
        ))}
      </div>
    </div>
  );
};

const ComparisonRow = ({ feature, us, them }) => (
  <div className="grid grid-cols-3 py-4 border-b border-gray-100 text-sm last:border-0 group hover:bg-gray-50/50 transition-colors px-4 -mx-4 rounded-lg">
    <div className="font-medium text-gray-700 flex items-center gap-2 font-mono text-xs uppercase tracking-tight">{feature}</div>
    <div className="text-center flex justify-center">
        {us ? (
          <div className="w-5 h-5 rounded bg-[#1A1A1A] flex items-center justify-center">
             <CheckCircle size={12} className="text-[#D4AF37]" /> 
          </div>
        ) : <div className="w-5 h-5 border border-gray-200 rounded flex items-center justify-center"><X size={12} className="text-gray-300" /></div>}
    </div>
    <div className="text-center flex justify-center opacity-30">
        {them ? <CheckCircle size={16} /> : <div className="w-1.5 h-1.5 rounded-full bg-gray-300" />}
    </div>
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
      setError("ACCESS DENIED: Invalid credentials.");
    }
  };

  if (showPitchDeck) {
    return <PitchDeck onExit={() => setShowPitchDeck(false)} />;
  }

  return (
    <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A] font-sans selection:bg-[#D4AF37]/20 selection:text-[#1A1A1A] overflow-x-hidden">
      
      <Navbar onLogin={handleLoginClick} onInvestorAccess={() => setShowInvestorModal(true)} />

      {/* HERO SECTION */}
      <section className="relative pt-32 md:pt-40 pb-20 px-4 md:px-8 max-w-7xl mx-auto text-center overflow-visible">
        <AnimatedBackground /> 

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="relative z-10 flex flex-col items-center"
        >
          <Badge text="SYSTEM_STATUS: ONLINE" />
          
          <h1 className="font-sans text-5xl md:text-8xl font-bold text-[#1A1A1A] leading-tight tracking-tight mb-8 max-w-5xl mx-auto px-4">
            The Deterministic <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#1A1A1A] via-[#444] to-[#888] inline-block py-1">
              Settlement Engine
            </span>
          </h1>
          
          <p className="text-xl text-gray-500 max-w-3xl mx-auto mb-10 leading-relaxed font-light px-4">
            SHA256-locked ingestion, vectorized matching core, and air-gapped AI reasoning. <br className="hidden md:block"/>
            <span className="font-mono text-sm text-[#1A1A1A] bg-gray-100 px-2 py-1 rounded mt-2 inline-block">Zero-Hallucination Architecture</span> for modern custodial ops.
          </p>

          <div className="flex flex-col items-center mb-20 w-full">
            <div className="flex flex-col md:flex-row justify-center gap-4 mb-4 w-full md:w-auto px-4">
                <button onClick={handleLoginClick} className="group w-full md:w-auto px-8 py-4 bg-[#1A1A1A] text-white font-semibold rounded-xl shadow-lg hover:-translate-y-1 transition-all duration-300 flex items-center justify-center gap-3">
                  <Terminal size={18} className="text-[#D4AF37]" /> Initialize Pilot
                </button>
                <button className="group w-full md:w-auto px-8 py-4 bg-white border border-gray-200 text-[#1A1A1A] font-medium rounded-xl hover:bg-gray-50 transition-all flex items-center justify-center gap-2 shadow-sm">
                  <FileJson size={18} className="text-gray-400" /> API Documentation
                </button>
            </div>
            <p className="text-[10px] text-gray-400 font-mono uppercase tracking-widest flex items-center gap-2">
                <Lock size={10} /> Enterprise Environment • Invite Only
            </p>
          </div>

          {/* DASHBOARD PREVIEW */}
          <div className="relative w-full max-w-6xl group perspective-1000 px-4">
            <div className="absolute -inset-4 bg-gradient-to-t from-[#D4AF37]/10 to-transparent rounded-[2rem] blur-3xl opacity-40"></div>
            
            <motion.div 
              initial={{ rotateX: 5 }}
              animate={{ rotateX: 0 }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="relative rounded-xl border border-gray-200 bg-white shadow-2xl overflow-hidden ring-1 ring-black/5"
            >
                <div className="absolute top-0 w-full h-8 bg-[#F5F5F5] border-b border-gray-200 flex items-center px-4 gap-2 z-20">
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-300" />
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-300" />
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-300" />
                    </div>
                    <div className="ml-auto font-mono text-[9px] text-gray-400">
                      SECURE_CONNECTION_ESTABLISHED
                    </div>
                </div>
                <div className="pt-8 bg-white">
                     <img src={heroImg} alt="Aureon Dashboard" className="w-full h-auto object-cover" />
                </div>
            </motion.div>
          </div>

        </motion.div>
      </section>
      
      <ProtocolTicker />
      
      <SectionDivider label="CORE_MODULES" />

      {/* FEATURE GRID - UPDATED COPY */}
      <section id="architecture" className="py-24 px-6 max-w-7xl mx-auto">
         <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* CARD 1: INGESTION */}
            <div className="md:col-span-2 p-10 rounded-xl bg-white border border-gray-200 relative overflow-hidden group hover:border-gray-300 transition-all duration-300">
                <div className="relative z-10">
                    <div className="w-10 h-10 bg-gray-100 rounded flex items-center justify-center mb-6">
                        <Database size={20} className="text-[#1A1A1A]" />
                    </div>
                    <h3 className="text-xl font-bold mb-3 font-mono uppercase tracking-tight">SHA256-Locked Gatekeeper</h3>
                    <p className="text-gray-500 max-w-lg leading-relaxed text-sm">
                        Idempotent ingestion engine. Every file is cryptographically hashed upon entry to prevent duplicate uploads. Raw chaos (PDF/CSV/XLSX) is normalized into strict schemas before ever touching the ledger.
                    </p>
                    <div className="mt-8 flex gap-2 font-mono text-[10px] uppercase">
                        <span className="px-2 py-1 bg-gray-100 rounded text-gray-600">Conflict_409_Protection</span>
                        <span className="px-2 py-1 bg-gray-100 rounded text-gray-600">Audit_Log_Immutable</span>
                    </div>
                </div>
            </div>

            {/* CARD 2: AI CORTEX */}
            <div className="p-10 rounded-xl bg-[#1A1A1A] text-white relative overflow-hidden shadow-2xl shadow-black/10">
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#333_1px,transparent_1px),linear-gradient(to_bottom,#333_1px,transparent_1px)] bg-[size:16px_16px] opacity-20" />
                <div className="relative z-10">
                    <div className="w-10 h-10 bg-white/10 rounded flex items-center justify-center mb-6 border border-white/10">
                        <BrainCircuit size={20} className="text-[#D4AF37]" />
                    </div>
                    <h3 className="text-xl font-bold mb-3 font-mono uppercase tracking-tight">Air-Gapped Cortex</h3>
                    <p className="text-gray-400 leading-relaxed text-sm">
                        Gemini 2.0 Flash operates in a read-only sandbox. It proposes resolutions but never mutates the system of record. 
                    </p>
                    <div className="mt-6 pt-6 border-t border-white/10">
                      <div className="flex items-center gap-2 text-xs font-mono text-[#D4AF37]">
                        <Shield size={12} /> ZERO_HALLUCINATION_RISK
                      </div>
                    </div>
                </div>
            </div>

            {/* CARD 3: VECTOR ENGINE */}
            <div className="p-10 rounded-xl bg-white border border-gray-200 hover:border-gray-300 transition-all duration-300">
                <div className="w-10 h-10 bg-gray-100 rounded flex items-center justify-center mb-6">
                    <Zap size={20} className="text-[#1A1A1A]" />
                </div>
                <h3 className="text-xl font-bold mb-3 font-mono uppercase tracking-tight">Vectorized Resolution</h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                    Non-probabilistic matching engine. Processes 10,000+ trades in &lt;400ms using vectorized linear algebra. 95% straight-through processing.
                </p>
            </div>

            {/* CARD 4: AUDIT */}
            <div className="md:col-span-2 p-10 rounded-xl bg-gray-50 border border-gray-200 flex flex-col md:flex-row items-center justify-between gap-8">
                <div>
                    <h3 className="text-xl font-bold mb-2 font-mono uppercase tracking-tight">Enterprise Governance</h3>
                    <p className="text-gray-500 text-sm">Full forensic trails for every AI decision. Exportable "Certificate of Truth" for compliance.</p>
                </div>
                <div className="font-mono text-[10px] text-gray-400 bg-white px-4 py-3 rounded border border-gray-200 shadow-sm">
                  LOG: ID_9921 MATCHED [CONF: 0.98] VIA RULE_TIER_2
                </div>
            </div>
         </div>
      </section>

      <SectionDivider label="SYSTEM_ARCHITECTURE" />

      {/* ARCHITECTURE SECTION - TERMINAL VIBE */}
      <section className="py-24 bg-[#0A0A0A] text-white relative overflow-hidden">
         <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: `linear-gradient(#333 1px, transparent 1px), linear-gradient(90deg, #333 1px, transparent 1px)`, backgroundSize: '30px 30px' }}></div>

         <div className="max-w-7xl mx-auto px-6 relative z-10 flex flex-col md:flex-row gap-16 items-center">
            
            <div className="flex-1">
                <Badge text="INFRASTRUCTURE" color="bg-green-500" />
                <h2 className="font-sans text-4xl md:text-5xl font-bold mb-6 tracking-tight">Engineered for <br/>High-Frequency Ops.</h2>
                <p className="text-gray-400 text-lg font-light mb-8">
                    A proprietary Hybrid Architecture combining the determinism of SQL with the reasoning of LLMs.
                </p>

                {/* FAKE TERMINAL STATUS */}
                <div className="bg-black border border-gray-800 rounded-lg p-6 font-mono text-xs shadow-2xl">
                  <div className="flex justify-between text-gray-500 mb-4 border-b border-gray-800 pb-2">
                    <span>SYS_MONITOR_V2.1</span>
                    <span>UPTIME: 99.99%</span>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-green-500">● INGESTION_GATEWAY</span>
                      <span className="text-gray-400">SHA256_ACTIVE</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-500">● VECTOR_CORE</span>
                      <span className="text-gray-400">LATENCY: 12ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#D4AF37]">● NEURAL_CORTEX</span>
                      <span className="text-gray-400">STANDBY [AIR_GAPPED]</span>
                    </div>
                    <div className="flex justify-between opacity-50">
                      <span className="text-gray-500">○ LEGACY_RECON</span>
                      <span className="text-gray-600">OFFLINE</span>
                    </div>
                  </div>
                </div>
            </div>

            <div className="flex-1 relative">
               <div className="absolute -inset-4 bg-[#D4AF37] opacity-10 blur-3xl rounded-full"></div>
               <img src={archImg} alt="Aureon Architecture" className="relative rounded-lg border border-gray-800 shadow-2xl bg-black" />
            </div>
         </div>
      </section>

      <SectionDivider label="COMPARATIVE_ANALYSIS" />

      {/* COMPARISON */}
      <section className="py-24 px-6 max-w-4xl mx-auto">
         <div className="text-center mb-16">
             <h2 className="text-3xl font-bold mb-4 tracking-tight">Stop building internal tools.</h2>
             <p className="text-gray-500">Focus on alpha generation, not back-office maintenance.</p>
         </div>

         <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
             <div className="grid grid-cols-3 py-4 bg-gray-50 border-b border-gray-200 text-[10px] font-bold uppercase tracking-widest text-gray-500">
                 <div className="pl-6">Capability</div>
                 <div className="text-center text-[#1A1A1A]">Aureon Core</div>
                 <div className="text-center">Legacy Ops</div>
             </div>
             <div className="bg-white p-6 space-y-1">
                <ComparisonRow feature="SHA256 Idempotency" us={true} them={false} />
                <ComparisonRow feature="Air-Gapped AI Proposals" us={true} them={false} />
                <ComparisonRow feature="Self-Healing Schema" us={true} them={false} />
                <ComparisonRow feature="Vectorized SQL Engine" us={true} them={false} />
                <ComparisonRow feature="SOC-2 Audit Trails" us={true} them={false} />
             </div>
         </div>
      </section>

      {/* ARCHITECT'S LOG */}
      <section className="py-24 bg-white border-t border-gray-100">
        <div className="max-w-4xl mx-auto px-6 flex flex-col md:flex-row items-center gap-10">
            <div className="relative group grayscale hover:grayscale-0 transition-all duration-500">
                <img 
                    src={founderImg} 
                    alt="Pratik Tayade" 
                    className="w-24 h-24 md:w-32 md:h-32 object-cover rounded-lg border border-gray-200 shadow-lg"
                />
            </div>
            <div className="text-center md:text-left flex-1">
                <div className="flex items-center justify-center md:justify-start gap-2 mb-3 text-[#1A1A1A]">
                    <GitCommit size={16} />
                    <span className="text-xs font-mono uppercase tracking-widest">Architect's Log</span>
                </div>
                <p className="text-gray-600 text-lg leading-relaxed mb-6 font-light">
                    "We didn't build Aureon to be a 'tool'. We built it to be an operating system. The technology to automate high-frequency reconciliation exists—it just needed to be engineered with the safety constraints of Indian Custody."
                </p>
                <div>
                    <p className="font-bold text-[#1A1A1A] text-sm">Pratik Tayade</p>
                    <p className="text-xs text-gray-400 font-mono mt-0.5">Systems Architect</p>
                </div>
            </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-[#FAFAFA] pt-20 pb-10 px-6 border-t border-gray-200 font-mono text-xs">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start gap-10">
            <div>
                <img src={logoImg} alt="Aureon" className="h-12 w-auto object-contain mb-4 grayscale opacity-50" />
                <p className="text-gray-400 max-w-xs">
                    Deterministic Settlement Engine v2.1.0<br/>
                    Build: 2025.12.18_ALPHA
                </p>
            </div>
            <div className="flex gap-12 text-gray-500">
                <ul className="space-y-2">
                    <li className="uppercase tracking-widest text-gray-300 mb-2">System</li>
                    <li><a href="#" className="hover:text-black">Status</a></li>
                    <li><a href="#" className="hover:text-black">Docs</a></li>
                    <li><a href="#" className="hover:text-black">API</a></li>
                </ul>
                <ul className="space-y-2">
                    <li className="uppercase tracking-widest text-gray-300 mb-2">Legal</li>
                    <li><a href="#" className="hover:text-black">Privacy</a></li>
                    <li><a href="#" className="hover:text-black">Terms</a></li>
                    <li><a href="#" className="hover:text-black">Security</a></li>
                </ul>
            </div>
        </div>
        <div className="max-w-7xl mx-auto pt-8 mt-12 border-t border-gray-200 text-gray-400 flex justify-between">
            <p>© 2025 Aureon Technologies.</p>
            <p>Navi Mumbai, MH</p>
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
              className="absolute inset-0 bg-[#0A0A0A]/80 backdrop-blur-sm"
            />
            
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="relative w-full max-w-sm bg-white rounded-lg shadow-2xl overflow-hidden border border-gray-200"
            >
              <div className="px-6 py-8">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-lg font-bold text-[#1A1A1A] flex items-center gap-2 font-mono uppercase tracking-tight">
                      <Lock className="text-[#D4AF37]" size={16} />
                      Restricted Access
                    </h3>
                    <p className="text-xs text-gray-500 mt-2">
                      Enter authorized access code to view the System Architecture Deck.
                    </p>
                  </div>
                  <button onClick={() => setShowInvestorModal(false)} className="text-gray-400 hover:text-black">
                    <X size={20} />
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
                      className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-[#1A1A1A] focus:bg-white transition-all text-sm font-mono tracking-widest"
                    />
                    {error && (
                      <p className="text-red-600 text-[10px] mt-2 font-mono font-bold flex items-center gap-1">
                        <Shield size={10} /> {error}
                      </p>
                    )}
                  </div>
                  
                  <button 
                    type="submit"
                    className="w-full bg-[#1A1A1A] hover:bg-black text-white font-bold py-3 rounded transition-all flex items-center justify-center gap-2 text-sm"
                  >
                    AUTHENTICATE <ArrowRight size={14} />
                  </button>
                </form>
              </div>
              <div className="h-1 w-full bg-[#D4AF37]" />
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
};

export default LandingPage;
