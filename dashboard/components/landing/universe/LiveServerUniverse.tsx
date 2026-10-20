"use client";

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { PublicBotServer, FloatingServerSlot, FloatingServerNode } from './types';
import { FloatingServerCard } from './FloatingServerCard';
import { OrbitalRings } from './OrbitalRings';

interface LiveServerUniverseProps {
  servers: PublicBotServer[];
  className?: string;
}

// 9 Carefully calibrated 3D slots surrounding the central hero (Target: 8–10 cards)
const UNIVERSE_SLOTS: FloatingServerSlot[] = [
  // Slot 0: Top-Left Near (sharp, cyan accent, diagonal drift inward/outward)
  {
    id: 'slot-tl-near',
    depth: 'near',
    trajectory: 'diag-a',
    baseX: 7,
    baseY: 10,
    duration: 24,
    delay: -4,
    accentColor: '#38bdf8',
  },
  // Slot 1: Top-Right Near (sharp, rose accent, diagonal drift inward/outward)
  {
    id: 'slot-tr-near',
    depth: 'near',
    trajectory: 'diag-b',
    baseX: 68,
    baseY: 11,
    duration: 26,
    delay: -12,
    accentColor: '#f43f5e',
  },
  // Slot 2: Bottom-Left Near (sharp, emerald accent, depth journey)
  {
    id: 'slot-bl-near',
    depth: 'near',
    trajectory: 'depth-journey',
    baseX: 10,
    baseY: 67,
    duration: 25,
    delay: -8,
    accentColor: '#34d399',
  },
  // Slot 3: Bottom-Right Near (sharp, orange accent, vertical wave float)
  {
    id: 'slot-br-near',
    depth: 'near',
    trajectory: 'vertical-wave',
    baseX: 71,
    baseY: 65,
    duration: 23,
    delay: -16,
    accentColor: '#fb923c',
  },
  // Slot 4: Mid-Left (mid depth, amber accent, shallow curve)
  {
    id: 'slot-ml-mid',
    depth: 'mid',
    trajectory: 'shallow-curve-left',
    baseX: 14,
    baseY: 36,
    duration: 22,
    delay: -7,
    accentColor: '#f59e0b',
    hideOnMobile: true,
  },
  // Slot 5: Mid-Right (mid depth, indigo accent, shallow curve)
  {
    id: 'slot-mr-mid',
    depth: 'mid',
    trajectory: 'shallow-curve-right',
    baseX: 73,
    baseY: 37,
    duration: 24,
    delay: -19,
    accentColor: '#818cf8',
    hideOnMobile: true,
  },
  // Slot 6: Distant Far Left (far depth, blurred 2px, opacity 0.20, scale 0.75)
  {
    id: 'slot-dl-far',
    depth: 'far',
    trajectory: 'diag-b',
    baseX: 2,
    baseY: 24,
    duration: 30,
    delay: -11,
    accentColor: '#64748b',
    hideOnMobile: true,
  },
  // Slot 7: Distant Far Right (far depth, blurred 2px, opacity 0.20, scale 0.75)
  {
    id: 'slot-dr-far',
    depth: 'far',
    trajectory: 'diag-a',
    baseX: 86,
    baseY: 26,
    duration: 32,
    delay: -21,
    accentColor: '#94a3b8',
    hideOnMobile: true,
  },
  // Slot 8: Distant Far Bottom-Center (far depth, blurred 2px, opacity 0.20, scale 0.75)
  {
    id: 'slot-dc-far',
    depth: 'far',
    trajectory: 'depth-journey',
    baseX: 42,
    baseY: 82,
    duration: 28,
    delay: -15,
    accentColor: '#a855f7',
    hideOnMobile: true,
    hideOnTablet: true,
  },
];

export const LiveServerUniverse: React.FC<LiveServerUniverseProps> = ({
  servers,
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredSlotId, setHoveredSlotId] = useState<string | null>(null);

  // Mouse Parallax smooth lerping state
  const mouseTargetRef = useRef({ x: 0, y: 0 });
  const mouseCurrentRef = useRef({ x: 0, y: 0 });
  const rafIdRef = useRef<number | null>(null);

  // Distribute real servers into calibrated slots
  const activeNodes: FloatingServerNode[] = useMemo(() => {
    if (!servers || servers.length === 0) return [];

    return UNIVERSE_SLOTS.map((slot, index) => {
      const server = servers[index % servers.length];
      return { slot, server };
    });
  }, [servers]);

  // Handle subtle mouse parallax with smooth requestAnimationFrame lerp
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (window.innerWidth < 1024) return;
      const { innerWidth, innerHeight } = window;
      mouseTargetRef.current = {
        x: (e.clientX / innerWidth) - 0.5,
        y: (e.clientY / innerHeight) - 0.5,
      };
    };

    const updateParallax = () => {
      const target = mouseTargetRef.current;
      const current = mouseCurrentRef.current;
      current.x += (target.x - current.x) * 0.06;
      current.y += (target.y - current.y) * 0.06;

      if (containerRef.current) {
        containerRef.current.style.setProperty('--mouse-x', current.x.toFixed(4));
        containerRef.current.style.setProperty('--mouse-y', current.y.toFixed(4));
      }

      rafIdRef.current = requestAnimationFrame(updateParallax);
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    rafIdRef.current = requestAnimationFrame(updateParallax);

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current);
    };
  }, []);

  // Map trajectory to corresponding CSS animation class
  const getTrajectoryClass = (trajectory: FloatingServerSlot['trajectory']) => {
    switch (trajectory) {
      case 'diag-a':
        return 'animate-universe-diag-a';
      case 'diag-b':
        return 'animate-universe-diag-b';
      case 'vertical-wave':
        return 'animate-universe-vertical';
      case 'shallow-curve-left':
        return 'animate-universe-curve-left';
      case 'shallow-curve-right':
        return 'animate-universe-curve-right';
      case 'depth-journey':
      default:
        return 'animate-universe-depth';
    }
  };

  // Parallax offset per depth layer
  const getParallaxMultiplier = (depth: FloatingServerSlot['depth']) => {
    switch (depth) {
      case 'near':
        return 14; // pixels
      case 'mid':
        return 8;  // pixels
      case 'far':
      default:
        return 4;  // pixels
    }
  };

  return (
    <div 
      ref={containerRef}
      className={`pointer-events-none absolute inset-0 overflow-hidden select-none z-10 ${className}`}
      style={{
        ['--mouse-x' as any]: '0',
        ['--mouse-y' as any]: '0',
      }}
    >
      {/* Background Celestial Orbital Tracks & Deep Glow */}
      <OrbitalRings />

      {/* Very faint occasional cosmic shooting shimmer (Upper-right corner) */}
      <div className="absolute top-16 right-36 pointer-events-none z-0">
        <div 
          className="h-[1px] bg-gradient-to-r from-transparent via-red-400/40 to-transparent"
          style={{ width: '120px' }}
        />
      </div>

      {/* Ambient background micro-stardust particles */}
      <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden opacity-30 sm:opacity-40">
        <div className="absolute top-[18%] left-[22%] w-1 h-1 rounded-full bg-cyan-400/60 animate-pulse" style={{ animationDuration: '4s' }} />
        <div className="absolute top-[28%] right-[18%] w-1.5 h-1.5 rounded-full bg-purple-400/50 animate-pulse" style={{ animationDuration: '5s', animationDelay: '-2s' }} />
        <div className="absolute top-[68%] left-[28%] w-1 h-1 rounded-full bg-rose-400/50 animate-pulse" style={{ animationDuration: '6s', animationDelay: '-3s' }} />
        <div className="absolute top-[75%] right-[24%] w-1 h-1 rounded-full bg-indigo-400/60 animate-pulse" style={{ animationDuration: '4.5s', animationDelay: '-1s' }} />
        <div className="absolute top-[48%] left-[8%] w-1 h-1 rounded-full bg-sky-300/40 animate-pulse" style={{ animationDuration: '5.5s', animationDelay: '-4s' }} />
        <div className="absolute top-[52%] right-[8%] w-1 h-1 rounded-full bg-pink-300/40 animate-pulse" style={{ animationDuration: '6.5s', animationDelay: '-2.5s' }} />
      </div>

      {/* Floating Server Universe Cards */}
      {activeNodes.map(({ slot, server }) => {
        const isHovered = hoveredSlotId === slot.id;
        const trajectoryClass = getTrajectoryClass(slot.trajectory);
        const parallaxPx = getParallaxMultiplier(slot.depth);

        // Hide slots gracefully according to screen size
        const visibilityClasses = [
          slot.hideOnMobile ? 'hidden md:block' : 'block',
          slot.hideOnTablet ? 'md:hidden lg:block' : '',
        ].filter(Boolean).join(' ');

        return (
          <div
            key={slot.id}
            className={`absolute pointer-events-auto transition-opacity duration-500 ${visibilityClasses}`}
            style={{
              left: `${slot.baseX}%`,
              top: `${slot.baseY}%`,
              zIndex: isHovered ? 50 : slot.depth === 'near' ? 22 : slot.depth === 'mid' ? 14 : 8,
              transform: `translate3d(calc(var(--mouse-x, 0) * ${parallaxPx}px), calc(var(--mouse-y, 0) * ${parallaxPx}px), 0)`,
              willChange: 'transform',
            }}
          >
            {/* Movement and 3D Lifecycle Transition Wrapper */}
            <div
              className={`${trajectoryClass} animate-universe-lifecycle`}
              style={{
                animationDuration: `${slot.duration}s`,
                animationDelay: `${slot.delay}s`,
                animationPlayState: isHovered ? 'paused' : 'running',
              }}
            >
              <FloatingServerCard
                server={server}
                depth={slot.depth}
                accentColor={slot.accentColor}
                onMouseEnter={() => setHoveredSlotId(slot.id)}
                onMouseLeave={() => setHoveredSlotId(null)}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};
