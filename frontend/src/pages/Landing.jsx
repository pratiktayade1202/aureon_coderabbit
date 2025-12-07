// src/pages/Landing.jsx
import React from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, Shield, Zap, Globe, CheckCircle, Database,
  Lock, Server, Layers, Cpu, FileText, Activity, BrainCircuit, X,
  Terminal, ChevronRight, Code2, Users
} from "lucide-react";
import AnimatedBackground from "../components/AnimatedBackground"; 

// --- IMPORT IMAGES ---
import heroImg from "../assets/dashboard-hero.png";
import archImg from "../assets/architecture-diagram.png";
import founderImg from "../assets/founder-pratik.jpg";
import logoImg from "../assets/logo.png";

// --- REUSABLE COMPONENTS ---

const Badge = ({ text }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white border border-gray-200 shadow-sm text-xs font-mono font-medium text-gray-600 mb-8"
  >
    <span className="relative flex h-2 w-2">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#D4AF37] opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#D4AF37]"></span>
    </span>
    {text}
  </motion.div>
);

const Navbar = ({ onLogin }) => (
  <nav className="fixed top-0 w-full z-50 border-b border-gray-200/80 bg-[#FDFCF8]/80 backdrop-blur-xl supports-[backdrop-filter]:bg-[#FDFCF8]/60">
    <div className="max-w-7xl mx-auto px-6 h-16 flex justify-between items-center">
      <div className="flex items-center">
        {/* LOGO - Increased Size */}
        <img 
            src={logoImg} 
            alt="Aureon" 
            className="h-20 w-auto object-contain" 
        />
      </div>
      
      <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-500">
        {["Product", "Security", "Pricing", "Docs"].map((item) => (
            <a key={item} href={`#${item.toLowerCase()}`} className="hover:text-[#1A1A1A] transition-colors duration-200">
                {item}
            </a>
        ))}
      </div>

      <div className="flex gap-4 items-center">
        <button onClick={onLogin} className="text-xs font-medium text-gray-500 hover:text-[#1A1A1A] transition-colors border border-transparent hover:border-gray-200 px-3 py-1.5 rounded-md">
          Client Login
        </button>
        <button onClick={onLogin} className="group px-4 py-2 bg-[#1A1A1A] text-white text-sm font-medium rounded-lg hover:bg-black transition-all shadow-md hover:shadow-lg flex items-center gap-2 transform hover:-translate-y-0.5">
          Join Waitlist
          <ChevronRight size={14} className="text-[#D4AF37] group-hover:translate-x-0.5 transition-transform" />
        </button>
      </div>
    </div>
  </nav>
);

const LogoTicker = () => {
  const logos = ["BlackRock", "HDFC AMC", "ICICI Prudential", "Zerodha", "Kotak", "State Street", "BNY Mellon", "Citibank"];
  return (
    <div className="relative z-20 border-y border-gray-100 py-12 overflow-hidden flex">
      {/* Dark Faded Glass Background Layer */}
      <div className="absolute inset-0 bg-black/5 backdrop-blur-sm" />

      <div className="absolute left-0 top-0 w-32 h-full bg-gradient-to-r from-[#FDFCF8] to-transparent z-10" />
      <div className="absolute right-0 top-0 w-32 h-full bg-gradient-to-l from-[#FDFCF8] to-transparent z-10" />
      
      <div className="flex whitespace-nowrap animate-ticker gap-24 opacity-60 grayscale hover:grayscale-0 hover:opacity-100 transition-all duration-500 relative z-10">
        {[...logos, ...logos].map((logo, i) => (
          <span key={i} className="text-lg font-semibold text-[#1A1A1A] flex items-center gap-3">
             <span className="w-6 h-6 rounded bg-gray-200 block"></span> {logo}
          </span>
        ))}
      </div>
    </div>
  );
};

const ComparisonRow = ({ feature, us, them }) => (
  <div className="grid grid-cols-3 py-4 border-b border-gray-100 text-sm last:border-0 group hover:bg-gray-50/50 transition-colors px-4 -mx-4 rounded-lg">
    <div className="font-medium text-gray-700 flex items-center gap-2">{feature}</div>
    <div className="text-center flex justify-center">
        {us ? (
          <div className="w-6 h-6 rounded-full bg-[#D4AF37]/10 flex items-center justify-center">
             <CheckCircle size={14} className="text-[#D4AF37] fill-[#D4AF37]/20" /> 
          </div>
        ) : <X size={16} className="text-gray-300" />}
    </div>
    <div className="text-center flex justify-center opacity-30 grayscale">
        {them ? <CheckCircle size={16} /> : <X size={16} />}
    </div>
  </div>
);

// --- MAIN PAGE ---
const LandingPage = ({ onLogin }) => {
  
  const handleLoginClick = () => {
    onLogin();
  };

  return (
    <div className="min-h-screen bg-[#FDFCF8] text-[#1A1A1A] font-sans selection:bg-[#D4AF37]/20 selection:text-[#1A1A1A] overflow-x-hidden">
      
      <Navbar onLogin={handleLoginClick} />

      {/* HERO SECTION */}
      <section className="relative pt-40 md:pt-48 pb-28 px-4 md:px-8 max-w-7xl mx-auto text-center overflow-visible">
        
        {/* ANIMATED BACKGROUND */}
        <AnimatedBackground /> 

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="relative z-10 flex flex-col items-center"
        >
          <Badge text="v2.0 Private Beta" />
          
          {/* FIX: Removed break-words, adjusted max-width, and padding to prevent cutting */}
          <h1 className="font-sans text-5xl md:text-8xl font-bold text-[#1A1A1A] leading-tight tracking-tight mb-8 max-w-5xl mx-auto px-4">
            The Operating System <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#1A1A1A] via-[#444] to-[#888] inline-block py-1">
              for Custodial Ops
            </span>
          </h1>
          
          <p className="text-xl md:text-2xl text-gray-500 max-w-2xl mx-auto mb-10 leading-relaxed tracking-tight font-light px-4">
            Automate trade reconciliation, holdings verification, and cash ledger audits with <span className="font-medium text-[#1A1A1A] underline decoration-[#D4AF37]/30 decoration-2 underline-offset-4">AI-native precision</span>.
          </p>

          {/* BUTTON GROUP */}
          <div className="flex flex-col items-center mb-24 w-full">
            <div className="flex flex-col md:flex-row justify-center gap-4 mb-4 w-full md:w-auto px-4">
                <button onClick={handleLoginClick} className="group w-full md:w-auto px-8 py-4 bg-[#1A1A1A] text-white font-semibold rounded-xl shadow-[0_10px_40px_-10px_rgba(0,0,0,0.3)] hover:shadow-[0_20px_40px_-10px_rgba(0,0,0,0.4)] hover:-translate-y-1 transition-all duration-300 flex items-center justify-center gap-2 ring-1 ring-white/20">
                Join Waitlist <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </button>
                <button className="group w-full md:w-auto px-8 py-4 bg-white border border-gray-200 text-[#1A1A1A] font-medium rounded-xl hover:bg-gray-50 hover:border-gray-300 transition-all flex items-center justify-center gap-2 shadow-sm hover:shadow-md">
                <Terminal size={18} className="text-gray-400 group-hover:text-[#1A1A1A] transition-colors" /> Read Documentation
                </button>
            </div>
            <p className="text-xs text-gray-400 font-mono flex items-center gap-2">
                <Lock size={10} /> Private Pilot Environment. Direct sign-up disabled.
            </p>
          </div>

          {/* HERO IMAGE */}
          <div className="relative w-full max-w-6xl group perspective-1000 px-4">
            <div className="absolute -inset-4 bg-gradient-to-t from-[#D4AF37]/20 to-purple-500/10 rounded-[2rem] blur-2xl opacity-40 group-hover:opacity-60 transition duration-1000"></div>
            
            <motion.div 
              initial={{ rotateX: 5 }}
              animate={{ rotateX: 0 }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="relative rounded-xl border border-gray-200/80 bg-white/50 backdrop-blur-sm shadow-2xl overflow-hidden ring-1 ring-black/5"
            >
                <div className="absolute top-0 w-full h-10 bg-white/90 border-b border-gray-100 flex items-center px-4 gap-2 z-20">
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-200 border border-gray-300" />
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-200 border border-gray-300" />
                        <div className="w-2.5 h-2.5 rounded-full bg-gray-200 border border-gray-300" />
                    </div>
                    <div className="ml-4 px-3 py-1 bg-gray-50 rounded-md border border-gray-100 text-[10px] font-mono text-gray-400 flex items-center gap-2">
                        <Lock size={8} /> app.aureon.ai
                    </div>
                </div>
                <div className="pt-10 bg-white">
                     <img src={heroImg} alt="Aureon Dashboard" className="w-full h-auto object-cover opacity-100" />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-[#FDFCF8] via-transparent to-transparent opacity-20 pointer-events-none" />
            </motion.div>
          </div>

        </motion.div>
      </section>
      
      <LogoTicker />

      {/* FEATURE GRID */}
      <section id="product" className="py-32 px-6 max-w-7xl mx-auto">
         <div className="mb-20 max-w-3xl">
            <h2 className="text-4xl md:text-5xl font-bold mb-6 tracking-tight text-[#1A1A1A]">Built for high-frequency reconciliation.</h2>
            <p className="text-gray-500 text-xl font-light">Three layers of intelligence to ensure zero-break settlements.</p>
         </div>

         <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 p-10 rounded-3xl bg-white border border-gray-200 relative overflow-hidden group hover:shadow-2xl hover:shadow-gray-200/50 hover:-translate-y-1 transition-all duration-500">
                <div className="absolute -right-20 -bottom-20 p-10 opacity-[0.03] group-hover:opacity-[0.08] transition-opacity duration-500 rotate-12">
                    <Database size={300} />
                </div>
                <div className="relative z-10">
                    <div className="w-12 h-12 bg-[#FAFAFA] rounded-xl border border-gray-100 flex items-center justify-center mb-8 shadow-sm">
                        <Database size={24} className="text-[#D4AF37]" />
                    </div>
                    <h3 className="text-2xl font-bold mb-4 tracking-tight">Universal Ingestion</h3>
                    <p className="text-gray-500 max-w-md leading-relaxed">
                        Stop writing parsers for every broker. Our Gemini-powered vision engine reads raw PDFs, CSVs, and Swift messages instantly.
                    </p>
                    <div className="mt-8 flex gap-2">
                        {['PDF', 'CSV', 'SWIFT', 'XLSX'].map(fmt => (
                            <span key={fmt} className="px-2 py-1 bg-gray-50 border border-gray-100 rounded text-[10px] font-mono text-gray-500">{fmt}</span>
                        ))}
                    </div>
                </div>
            </div>

            <div className="p-10 rounded-3xl bg-[#1A1A1A] text-white relative overflow-hidden group hover:-translate-y-1 transition-all duration-500 shadow-2xl shadow-black/20">
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#333_1px,transparent_1px),linear-gradient(to_bottom,#333_1px,transparent_1px)] bg-[size:20px_20px] opacity-10" />
                <div className="relative z-10">
                    <div className="w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center mb-8 backdrop-blur-md border border-white/10">
                        <BrainCircuit size={24} className="text-[#D4AF37]" />
                    </div>
                    <h3 className="text-2xl font-bold mb-4 tracking-tight">Agentic Reasoning</h3>
                    <p className="text-gray-400 leading-relaxed text-sm">
                        GPT-4o auditors verify every trade against market logic. It catches "Ghost Trades" and "Price Shocks" that regex misses.
                    </p>
                </div>
            </div>

            <div className="p-10 rounded-3xl bg-white border border-gray-200 hover:shadow-xl hover:shadow-gray-200/50 hover:-translate-y-1 transition-all duration-500">
                <div className="w-12 h-12 bg-gray-50 rounded-xl border border-gray-100 flex items-center justify-center mb-8">
                    <CheckCircle size={24} className="text-[#D4AF37]" />
                </div>
                <h3 className="text-xl font-bold mb-3 tracking-tight">Deterministic Settlement</h3>
                <p className="text-gray-500 text-sm leading-relaxed">
                    95% of trades are settled instantly via SQL rules. The remaining 5% edge cases are handed to the AI agent for resolution.
                </p>
            </div>

            <div className="md:col-span-2 p-10 rounded-3xl bg-gradient-to-br from-gray-50 to-white border border-gray-200 flex flex-col md:flex-row items-center justify-between hover:shadow-xl hover:shadow-gray-200/50 hover:-translate-y-1 transition-all duration-500 gap-8">
                <div>
                    <h3 className="text-xl font-bold mb-2 tracking-tight">Enterprise Governance</h3>
                    <p className="text-gray-500">Full audit trails for every AI decision. Nothing is a black box.</p>
                </div>
                <button className="px-6 py-3 bg-white border border-gray-200 rounded-lg text-sm font-medium hover:border-gray-300 hover:shadow-md transition-all whitespace-nowrap">
                    View Audit Logs
                </button>
            </div>
         </div>
      </section>

      {/* ARCHITECTURE - UPDATED WITH MOVING GRID */}
      <section id="architecture" className="py-32 bg-[#0A0A0A] text-white relative overflow-hidden">
         
         {/* 1. Subtle Grid Background Pattern - NOW ANIMATED */}
         <motion.div 
              className="absolute inset-0 opacity-[0.1]"
              style={{
                  backgroundImage: `linear-gradient(to right, #333 1px, transparent 1px), linear-gradient(to bottom, #333 1px, transparent 1px)`,
                  backgroundSize: '40px 40px'
              }}
              animate={{
                  backgroundPosition: ["0px 0px", "40px 40px"] // Moves exactly one cell size for seamless loop
              }}
              transition={{
                  duration: 20, // Slow, steady drift
                  repeat: Infinity,
                  ease: "linear"
              }}
         />

         {/* 2. Central Gold Glow - Softened & Centered */}
         <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vh] bg-[radial-gradient(circle_at_center,rgba(212,175,55,0.08),transparent_60%)] blur-[100px] pointer-events-none" />

         <div className="max-w-7xl mx-auto px-6 relative z-10">
            <div className="text-center mb-20">
                <Badge text="Under the hood" />
                <h2 className="font-sans text-5xl font-bold mb-6 tracking-tight">Engineered for Scale</h2>
                <p className="text-gray-400 max-w-2xl mx-auto text-lg font-light">
                    A proprietary Hybrid Architecture that combines the speed of SQL with the reasoning of LLMs.
                </p>
            </div>

            {/* Image Container - Refined Border & Shadow */}
            <div className="mt-12 relative rounded-2xl border border-white/10 overflow-hidden bg-[#0A0A0A]/50 backdrop-blur-sm p-2 shadow-[0_0_60px_-20px_rgba(212,175,55,0.15)]">
                <img src={archImg} alt="Aureon Dual-LLM Architecture" className="w-full h-auto rounded-xl opacity-100 relative z-10" />
            </div>

            {/* Stats Grid - Cleaner Dividers */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-24 text-center divide-x divide-white/10">
                 <div className="px-4">
                    <div className="text-4xl font-mono font-bold text-white mb-2 tracking-tighter">99.9%</div>
                    <div className="text-xs uppercase tracking-widest text-gray-500 font-medium">Uptime SLA</div>
                 </div>
                 <div className="px-4">
                    <div className="text-4xl font-mono font-bold text-[#D4AF37] mb-2 tracking-tighter">~400ms</div>
                    <div className="text-xs uppercase tracking-widest text-gray-500 font-medium">Settlement Time</div>
                 </div>
                 <div className="px-4">
                    <div className="text-4xl font-mono font-bold text-white mb-2 tracking-tighter">SOC2</div>
                    <div className="text-xs uppercase tracking-widest text-gray-500 font-medium">Compliant</div>
                 </div>
                 <div className="px-4">
                    <div className="text-4xl font-mono font-bold text-white mb-2 tracking-tighter">0%</div>
                    <div className="text-xs uppercase tracking-widest text-gray-500 font-medium">Data Retention</div>
                 </div>
            </div>
         </div>
      </section>

      {/* COMPARISON */}
      <section className="py-32 px-6 max-w-4xl mx-auto">
         <div className="text-center mb-16">
             <h2 className="text-3xl md:text-4xl font-bold mb-4 tracking-tight">Stop building internal tools.</h2>
             <p className="text-gray-500 text-lg">Focus on alpha generation, not back-office maintenance.</p>
         </div>

         <div className="border border-gray-200 rounded-2xl overflow-hidden shadow-lg shadow-gray-200/40">
             <div className="grid grid-cols-3 py-5 bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-widest text-gray-500">
                 <div className="pl-8 flex items-center gap-2">Feature</div>
                 <div className="text-center text-[#1A1A1A] flex items-center justify-center gap-2"><Shield size={12} className="text-[#D4AF37]"/> Aureon</div>
                 <div className="text-center">Legacy Ops</div>
             </div>
             <div className="bg-white p-8 space-y-2">
                <ComparisonRow feature="AI Universal Ingestion" us={true} them={false} />
                <ComparisonRow feature="Real-time Reasoning Agent" us={true} them={false} />
                <ComparisonRow feature="Self-Healing Schema" us={true} them={false} />
                <ComparisonRow feature="Zero-Retention Privacy" us={true} them={false} />
                <ComparisonRow feature="Flat SaaS Pricing" us={true} them={false} />
             </div>
         </div>
      </section>

      {/* FOUNDER SECTION */}
      <section className="py-24 bg-white border-t border-gray-100">
        <div className="max-w-4xl mx-auto px-6 flex flex-col md:flex-row items-center gap-12">
            <div className="relative group cursor-pointer">
                <div className="absolute inset-0 bg-[#D4AF37] rounded-full blur-2xl opacity-20 group-hover:opacity-40 transition-opacity duration-500" />
                <img 
                    src={founderImg} 
                    alt="Pratik Tayade" 
                    className="relative w-32 h-32 md:w-40 md:h-40 object-cover rounded-full border-4 border-white shadow-xl grayscale group-hover:grayscale-0 transition-all duration-500"
                />
            </div>
            <div className="text-center md:text-left flex-1">
                <div className="flex items-center justify-center md:justify-start gap-2 mb-4 text-[#D4AF37]">
                    <Code2 size={20} />
                    <span className="text-xs font-mono uppercase tracking-widest text-black">Founder's Note</span>
                </div>
                <h3 className="text-2xl font-bold mb-4 text-[#1A1A1A] tracking-tight">From the trenches.</h3>
                <p className="text-gray-600 text-lg leading-relaxed mb-8 italic font-light">
                    "We built Aureon because we were tired of seeing brilliant fund managers waste hours on Excel reconciliation. 
                    The technology to automate this exists—it just needed to be built specifically for Indian Custody."
                </p>
                <div className="border-l-2 border-[#D4AF37] pl-4">
                    <p className="font-bold text-[#1A1A1A]">Pratik Tayade</p>
                    <p className="text-sm text-gray-500 font-mono mt-1">Founder • AI Infrastructure</p>
                </div>
            </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="bg-[#FAFAFA] pt-24 pb-10 px-6 border-t border-gray-200">
        <div className="max-w-7xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-10 mb-20">
            <div className="col-span-2">
                <div className="flex items-center mb-6">
                    <img 
                        src={logoImg} 
                        alt="Aureon" 
                        className="h-16 w-auto object-contain" 
                    />
                </div>
                <p className="text-sm text-gray-500 max-w-xs leading-relaxed">
                    The operating system for the next generation of asset management.
                </p>
            </div>
            <div>
                <h4 className="font-mono text-xs uppercase tracking-widest text-gray-400 mb-6 font-semibold">Platform</h4>
                <ul className="space-y-4 text-sm text-gray-600">
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Ingestion</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Reconciliation</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Audit Trails</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">API</a></li>
                </ul>
            </div>
            <div>
                <h4 className="font-mono text-xs uppercase tracking-widest text-gray-400 mb-6 font-semibold">Company</h4>
                <ul className="space-y-4 text-sm text-gray-600">
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">About</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Careers</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Security</a></li>
                    <li><a href="#" className="hover:text-[#1A1A1A] hover:underline decoration-1 underline-offset-4 transition-all">Contact</a></li>
                </ul>
            </div>
        </div>
        <div className="max-w-7xl mx-auto pt-8 border-t border-gray-200 flex flex-col md:flex-row justify-between text-xs text-gray-400 font-mono">
            <p>© 2025 Aureon Technologies. All rights reserved.</p>
            <div className="flex gap-6 mt-4 md:mt-0">
                <a href="#" className="hover:text-gray-600">Privacy Policy</a>
                <a href="#" className="hover:text-gray-600">Terms of Service</a>
            </div>
        </div>
      </footer>

    </div>
  );
};

export default LandingPage;