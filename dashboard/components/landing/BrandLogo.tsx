"use client";

import React from 'react';

interface BrandLogoProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'hero';
  className?: string;
  showText?: boolean;
  showBadge?: boolean;
  badgeText?: string;
  botName?: string;
  subtext?: string;
  animated?: boolean;
  onClick?: () => void;
}

export const BrandLogo: React.FC<BrandLogoProps> = ({ 
  size = 'md', 
  className = '',
  onClick
}) => {
  const iconDimensions = {
    xs: 'w-6 h-6',
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
    '2xl': 'w-24 h-24 sm:w-28 sm:h-28',
    hero: 'w-32 h-32 sm:w-40 sm:h-40'
  };

  // Unique ID prefix for gradients, filters, clipPaths and animations to prevent SVG ID collisions
  const idPrefix = React.useId().replace(/:/g, '');

  // Exact futuristic shield path coordinate definition
  const shieldPath = "M 60 10 L 102 24 L 102 68 C 102 88 82 104 60 112 C 38 104 18 88 18 68 L 18 24 Z";
  const innerShieldPath = "M 60 14 L 98 26 L 98 66 C 98 84 80 98 60 106 C 40 98 22 84 22 66 L 22 26 Z";

  const handleClick = () => {
    if (onClick) {
      onClick();
    }
  };

  return (
    <div 
      onClick={onClick ? handleClick : undefined}
      className={`inline-flex items-center justify-center select-none relative ${
        onClick ? 'cursor-pointer group' : ''
      } ${className}`}
    >
      
      {/* Container with Responsive Dimensions */}
      <div 
        className={`relative flex items-center justify-center ${iconDimensions[size]}`}
      >
          {/* Ambient Outer Security Shield Glow Pulse */}
          <div 
            className="absolute -inset-2 rounded-2xl bg-gradient-to-tr from-red-600/30 via-amber-500/20 to-red-500/25 blur-lg opacity-75 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" 
          />

          {/* Vector SVG: Futuristic Biometric Shield with Y Breaking & Popping Inside Shield Only */}
          <svg 
            viewBox="0 0 120 120" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg" 
            className="w-full h-full relative z-10 filter drop-shadow-[0_4px_16px_rgba(220,38,38,0.45)] transition-transform duration-300 group-hover:scale-105"
            style={{ overflow: 'visible' }}
          >
            <defs>
              {/* 1. Pure Black Shield Interior */}
              <linearGradient id={`${idPrefix}-shield-bg`} x1="60" y1="10" x2="60" y2="112" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#000000" />
                <stop offset="100%" stopColor="#000000" />
              </linearGradient>

              {/* 2. Pulsing Shield Perimeter Border Gradient */}
              <linearGradient id={`${idPrefix}-shield-border-grad`} x1="20" y1="10" x2="100" y2="112" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#ef4444" />
                <stop offset="50%" stopColor="#dc2626" />
                <stop offset="100%" stopColor="#b91c1c" />
              </linearGradient>

              {/* 3. Traveling Energy Perimeter Photon Spark */}
              <linearGradient id={`${idPrefix}-energy-spark`} x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
                <stop offset="30%" stopColor="#fca5a5" stopOpacity="0.9" />
                <stop offset="70%" stopColor="#ef4444" stopOpacity="0.5" />
                <stop offset="100%" stopColor="#dc2626" stopOpacity="0" />
              </linearGradient>

              {/* 4. Scanning Laser Bar Gradient */}
              <linearGradient id={`${idPrefix}-laser-bar`} x1="18" y1="0" x2="102" y2="0" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0" />
                <stop offset="20%" stopColor="#ef4444" stopOpacity="0.8" />
                <stop offset="45%" stopColor="#fca5a5" stopOpacity="1" />
                <stop offset="50%" stopColor="#ffffff" stopOpacity="1" />
                <stop offset="55%" stopColor="#fca5a5" stopOpacity="1" />
                <stop offset="80%" stopColor="#ef4444" stopOpacity="0.8" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </linearGradient>

              {/* 5. Laser Scan Ambient Glow Cone */}
              <linearGradient id={`${idPrefix}-laser-cone`} x1="60" y1="-14" x2="60" y2="14" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#ef4444" stopOpacity="0" />
                <stop offset="30%" stopColor="#ef4444" stopOpacity="0.35" />
                <stop offset="50%" stopColor="#ffffff" stopOpacity="0.85" />
                <stop offset="70%" stopColor="#ef4444" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
              </linearGradient>

              {/* 6. Neon Glow Filter */}
              <filter id={`${idPrefix}-glow-filter`} x="-40%" y="-40%" width="180%" height="180%">
                <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor="#ef4444" floodOpacity="0.9" />
                <feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#dc2626" floodOpacity="0.6" />
              </filter>

              {/* Laser Intense Glow Filter */}
              <filter id={`${idPrefix}-laser-filter`} x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow dx="0" dy="0" stdDeviation="2.2" floodColor="#ef4444" floodOpacity="1" />
                <feDropShadow dx="0" dy="0" stdDeviation="5.5" floodColor="#dc2626" floodOpacity="0.7" />
              </filter>

              {/* Shield Interior Clipping Path */}
              <clipPath id={`${idPrefix}-shield-clip`}>
                <path d={shieldPath} />
              </clipPath>
            </defs>

            {/* LAYER 1: BASE FUTURISTIC SHIELD HOUSING & INTERIOR */}
            <path 
              d={shieldPath} 
              fill={`url(#${idPrefix}-shield-bg)`}
              stroke={`url(#${idPrefix}-shield-border-grad)`}
              strokeWidth="2.2"
              strokeLinejoin="round"
            >
              <animate 
                attributeName="stroke-opacity" 
                values="0.65;1;0.65" 
                dur="2.4s" 
                repeatCount="indefinite" 
              />
            </path>

            {/* Inner Decorative Micro-Tech Shield Groove */}
            <path 
              d={innerShieldPath} 
              stroke="#ef4444"
              strokeWidth="0.8"
              strokeOpacity="0.35"
              strokeDasharray="4 3"
              fill="none"
            />

            {/* LAYER 2: SHIELD INTERIOR WITH STABLE WHITE Y ALIGNED INSIDE SHIELD */}
            <g clipPath={`url(#${idPrefix}-shield-clip)`}>
              {/* Pure Black Interior Backplate */}
              <rect x="0" y="0" width="120" height="120" fill="#000000" />

              {/* STABLE WHITE 'Y' (SCALED SLIGHTLY SMALLER AND CENTERED) */}
              <g filter={`url(#${idPrefix}-glow-filter)`} transform="translate(15, 15) scale(0.75)">
                <path 
                  d="M 34,30 L 49,30 L 60,50 L 71,30 L 86,30 L 67,60 L 67,90 L 53,90 L 53,60 Z" 
                  fill="#ffffff"
                  stroke="#e2e8f0"
                  strokeWidth="1.2"
                  strokeLinejoin="round"
                />
                {/* Inner Bevel Detail for Modern Finish */}
                <path 
                  d="M 36,32 L 48,32 L 59,51 L 60,51 L 72,32 L 84,32 L 65,61 L 65,88 L 55,88 L 55,61 Z" 
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="0.8"
                  strokeOpacity="0.6"
                />
              </g>

              {/* LASER SCANNING EFFECT INSIDE SHIELD */}
              <g filter={`url(#${idPrefix}-laser-filter)`} style={{ mixBlendMode: 'screen' }}>
                <g>
                  <animateTransform
                    attributeName="transform"
                    type="translate"
                    values="0 106; 0 14; 0 106"
                    dur="2.8s"
                    repeatCount="indefinite"
                    calcMode="spline"
                    keySplines="0.45 0 0.55 1; 0.45 0 0.55 1"
                  />

                  {/* Laser Light Cone Aura passing over */}
                  <rect 
                    x="16" 
                    y="-12" 
                    width="88" 
                    height="24" 
                    fill={`url(#${idPrefix}-laser-cone)`}
                  />

                  {/* Intense Neon Laser Line */}
                  <line 
                    x1="18" 
                    y1="0" 
                    x2="102" 
                    y2="0" 
                    stroke={`url(#${idPrefix}-laser-bar)`} 
                    strokeWidth="2.6" 
                    strokeLinecap="round"
                  />
                </g>
              </g>
            </g>

            {/* LAYER 3: ENERGY TRAVELING AROUND COMPLETE SHIELD PERIMETER */}
            <path 
              d={shieldPath} 
              fill="none"
              stroke={`url(#${idPrefix}-energy-spark)`}
              strokeWidth="3.2"
              strokeLinecap="round"
              strokeDasharray="36 280"
              filter={`url(#${idPrefix}-glow-filter)`}
            >
              <animate 
                attributeName="stroke-dashoffset" 
                from="0" 
                to="-316" 
                dur="2.4s" 
                repeatCount="indefinite" 
              />
            </path>

            {/* Secondary Trailing Micro Spark */}
            <path 
              d={shieldPath} 
              fill="none"
              stroke="#ffffff"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray="10 306"
              opacity="0.9"
            >
              <animate 
                attributeName="stroke-dashoffset" 
                from="-158" 
                to="-474" 
                dur="2.4s" 
                repeatCount="indefinite" 
              />
            </path>

            {/* HUD Security Corner Ticks */}
            <g stroke="#ef4444" strokeWidth="1.4" strokeLinecap="round" opacity="0.8">
              <line x1="60" y1="8" x2="60" y2="12" />
              <line x1="60" y1="108" x2="60" y2="112" />
              <line x1="16" y1="24" x2="20" y2="24" />
              <line x1="100" y1="24" x2="104" y2="24" />
            </g>

          </svg>
        </div>

      </div>
  );
};
