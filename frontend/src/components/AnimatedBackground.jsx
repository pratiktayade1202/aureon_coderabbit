// src/components/AnimatedBackground.jsx
import React, { useMemo } from "react";
import { motion } from "framer-motion";

const AnimatedBackground = () => {
  // 1. Generate Drifting Nodes
  const points = useMemo(
    () =>
      Array.from({ length: 35 }).map(() => ({
        x: Math.random() * 100,
        y: Math.random() * 100,
        vx: (Math.random() - 0.5) * 0.15, // Horizontal drift
        vy: (Math.random() - 0.5) * 0.15, // Vertical drift
      })),
    []
  );

  // 2. Connections logic
  const connections = useMemo(() => {
    const lines = [];
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const dx = points[i].x - points[j].x;
        const dy = points[i].y - points[j].y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        // Keep connections tight (15% distance)
        if (distance < 15) {
          lines.push({ p1: points[i], p2: points[j], id: `${i}-${j}` });
        }
      }
    }
    return lines;
  }, [points]);

  return (
    <div className="absolute inset-0 z-0 pointer-events-none overflow-hidden bg-[#FDFCF8]">
      
      {/* 1. ENGINEERING GRID (The Static Base) */}
      <div className="absolute inset-0 opacity-[0.6]"
        style={{
          backgroundImage: `
            linear-gradient(#E5E5E5 1px, transparent 1px), 
            linear-gradient(to right, #E5E5E5 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
        }}
      >
        {/* Radial mask to fade edges softly */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_800px_at_50%_40%,transparent,white)]" />
      </div>

      {/* 2. THE NETWORK (Gold & Technical) */}
      <svg className="absolute inset-0 w-full h-full">
        <defs>
          <linearGradient id="techGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#D4AF37" stopOpacity="0.1" />
            <stop offset="50%" stopColor="#D4AF37" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#D4AF37" stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Lines */}
        {connections.map(({ p1, p2, id }) => (
          <motion.line
            key={id}
            x1={`${p1.x}%`}
            y1={`${p1.y}%`}
            x2={`${p2.x}%`}
            y2={`${p2.y}%`}
            stroke="url(#techGradient)"
            strokeWidth="1.5" // Thicker for visibility
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0.1, 0.6, 0.1], // Breathing effect
              x1: [`${p1.x}%`, `${p1.x + p1.vx * 15}%`, `${p1.x}%`],
              y1: [`${p1.y}%`, `${p1.y + p1.vy * 15}%`, `${p1.y}%`],
              x2: [`${p2.x}%`, `${p2.x + p2.vx * 15}%`, `${p2.x}%`],
              y2: [`${p2.y}%`, `${p2.y + p2.vy * 15}%`, `${p2.y}%`],
            }}
            transition={{
              duration: 10 + Math.random() * 5,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        ))}

        {/* Nodes (Squares instead of circles for "Tech" vibe) */}
        {points.map((p, i) => (
          <motion.rect
            key={i}
            x={`${p.x}%`}
            y={`${p.y}%`}
            width="4"
            height="4"
            fill="#1A1A1A" // Dark nodes for contrast
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0.2, 0.8, 0.2],
              x: [`${p.x}%`, `${p.x + p.vx * 15}%`, `${p.x}%`],
              y: [`${p.y}%`, `${p.y + p.vy * 15}%`, `${p.y}%`],
            }}
            transition={{
              duration: 10 + Math.random() * 5,
              repeat: Infinity,
              ease: "linear",
            }}
          />
        ))}
      </svg>

      {/* 3. FLOATING DATA PARTICLES (The "Magic") */}
      {/* These drift upwards like data streams */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(15)].map((_, i) => (
          <motion.div
            key={`particle-${i}`}
            className="absolute w-1 h-1 bg-[#D4AF37] rounded-full"
            initial={{ 
                x: Math.random() * window.innerWidth, 
                y: window.innerHeight + 100, 
                opacity: 0 
            }}
            animate={{ 
                y: -100, 
                opacity: [0, 0.8, 0] 
            }}
            transition={{
                duration: 10 + Math.random() * 10,
                repeat: Infinity,
                delay: Math.random() * 5,
                ease: "linear"
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default AnimatedBackground;