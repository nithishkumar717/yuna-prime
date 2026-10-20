import React from 'react';

export const OrbitalRings: React.FC = () => {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden select-none -z-10 flex items-center justify-center">
      {/* Deep Space Background Radial Vignette */}
      <div 
        className="absolute w-[800px] h-[550px] sm:w-[1100px] sm:h-[700px] rounded-full opacity-40 blur-[130px] -z-20"
        style={{
          background: 'radial-gradient(ellipse at center, rgba(88,101,242,0.18) 0%, rgba(225,29,72,0.12) 40%, transparent 75%)'
        }}
      />

      {/* Primary SVG Cosmic Ellipse Orbital Tracks (Subtle & Atmospheric) */}
      <svg 
        className="absolute w-[95%] max-w-[1400px] h-auto aspect-[16/10] opacity-[0.06] sm:opacity-[0.08] -z-10" 
        viewBox="0 0 1000 650" 
        fill="none" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Subtle gradient for orbit 1 (Soft Cyan & Indigo shimmer) */}
          <linearGradient id="orbit-grad-1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.0" />
            <stop offset="35%" stopColor="#38bdf8" stopOpacity="0.12" />
            <stop offset="65%" stopColor="#818cf8" stopOpacity="0.14" />
            <stop offset="85%" stopColor="#f43f5e" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.0" />
          </linearGradient>

          {/* Subtle gradient for orbit 2 (Soft Purple & Sky shimmer) */}
          <linearGradient id="orbit-grad-2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#818cf8" stopOpacity="0.0" />
            <stop offset="30%" stopColor="#c084fc" stopOpacity="0.10" />
            <stop offset="65%" stopColor="#38bdf8" stopOpacity="0.12" />
            <stop offset="90%" stopColor="#38bdf8" stopOpacity="0.01" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0.0" />
          </linearGradient>

          {/* Faint outer boundary ring */}
          <linearGradient id="orbit-grad-outer" x1="0%" y1="50%" x2="100%" y2="50%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.04" />
            <stop offset="50%" stopColor="#818cf8" stopOpacity="0.02" />
            <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.04" />
          </linearGradient>
        </defs>

        {/* Orbit Path 1: Primary Ellipse with gentle -9deg inclination */}
        <g transform="rotate(-9 500 325)">
          <ellipse
            cx="500"
            cy="325"
            rx="460"
            ry="230"
            stroke="url(#orbit-grad-1)"
            strokeWidth="0.75"
            strokeDasharray="3 14"
          />
        </g>

        {/* Orbit Path 2: Inner Ellipse with 11deg inclination */}
        <g transform="rotate(11 500 325)">
          <ellipse
            cx="500"
            cy="325"
            rx="390"
            ry="185"
            stroke="url(#orbit-grad-2)"
            strokeWidth="0.75"
            strokeDasharray="2 12"
          />
        </g>

        {/* Orbit Path 3: Outer Distant Ellipse */}
        <g transform="rotate(-3 500 325)">
          <ellipse
            cx="500"
            cy="325"
            rx="490"
            ry="270"
            stroke="url(#orbit-grad-outer)"
            strokeWidth="0.6"
            strokeDasharray="2 18"
            opacity="0.4"
          />
        </g>

        {/* Ambient celestial stardust / nodes on orbit tracks */}
        <circle cx="160" cy="240" r="1.2" fill="#38bdf8" opacity="0.3" />
        <circle cx="820" cy="210" r="1.4" fill="#818cf8" opacity="0.35" />
        <circle cx="280" cy="460" r="1.2" fill="#f43f5e" opacity="0.25" />
        <circle cx="740" cy="450" r="1.4" fill="#38bdf8" opacity="0.3" />
        <circle cx="490" cy="115" r="1.2" fill="#c084fc" opacity="0.4" />
        <circle cx="510" cy="535" r="1.0" fill="#818cf8" opacity="0.25" />
      </svg>
    </div>
  );
};
