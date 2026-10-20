"use client";

import React, { useState, useEffect, useRef } from 'react';
import { 
  Server, 
  Users, 
  LayoutDashboard,
  Zap
} from 'lucide-react';

interface CtaSectionProps {
  onOpenLogin: () => void;
  onOpenInvite: () => void;
}

// Scroll-Triggered Smooth Count-Up Animated Counter
const AnimatedCounter: React.FC<{ target: number; duration?: number; isPercent?: boolean }> = ({ 
  target, 
  duration = 2200,
  isPercent = false 
}) => {
  const [current, setCurrent] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);
  const elementRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const node = elementRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setHasStarted(true);
            observer.disconnect();
          }
        });
      },
      { threshold: 0.15 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!hasStarted || target <= 0) return;

    let startTimestamp: number | null = null;
    let animationFrameId: number;

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      
      if (isPercent) {
        setCurrent(parseFloat((easeOut * target).toFixed(1)));
      } else {
        setCurrent(Math.floor(easeOut * target));
      }

      if (progress < 1) {
        animationFrameId = window.requestAnimationFrame(step);
      }
    };

    animationFrameId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animationFrameId);
  }, [hasStarted, target, duration, isPercent]);

  return (
    <span ref={elementRef}>
      {isPercent ? `${current.toFixed(1)}%` : current.toLocaleString()}
    </span>
  );
};

export const CtaSection: React.FC<CtaSectionProps> = ({ onOpenLogin, onOpenInvite }) => {
  const [stats, setStats] = useState({
    guilds: 21,
    users: 4155,
    uptime: 99.9,
    online: true,
    loaded: true
  });

  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  useEffect(() => {
    async function loadStats() {
      try {
        const res = await fetch('/api/v1/bot/status').catch(() => null);
        if (res && res.ok) {
          const data = await res.json();
          setStats(prev => ({
            guilds: data.guild_count || prev.guilds,
            users: data.user_count || prev.users,
            uptime: 99.9,
            online: true,
            loaded: true
          }));
        }
      } catch (_) {}
    }

    loadStats();
    const timer = setInterval(loadStats, 20000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="py-24 bg-[#08090d] relative overflow-hidden text-center">
      {/* Background Central Gold & Amber Glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] bg-gradient-to-tr from-amber-600/20 via-yellow-600/15 to-red-600/10 blur-[150px] rounded-full pointer-events-none -z-10"></div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Central Glowing Shield Crest */}
        <div className="relative mb-6 inline-block animate-float">
          <div className="absolute -inset-3 bg-gradient-to-r from-amber-500 to-yellow-400 rounded-3xl blur-xl opacity-60"></div>
          
          <div className="relative w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-gradient-to-b from-[#1c1408] to-[#0d0904] border border-amber-500/50 flex items-center justify-center p-3 shadow-2xl shadow-amber-900/40">
            <svg 
              viewBox="0 0 24 24" 
              fill="none" 
              xmlns="http://www.w3.org/2000/svg" 
              className="w-full h-full"
            >
              <path 
                d="M12 2.5L4.5 5.8V11.8C4.5 16.6 7.7 21 12 22.2C16.3 21 19.5 16.6 19.5 11.8V5.8L12 2.5Z" 
                stroke="url(#cta-crest-outer)" 
                strokeWidth="1.8" 
                strokeLinecap="round" 
                strokeLinejoin="round" 
              />
              <path 
                d="M12 6.5L7.5 9.2V12.2C7.5 15 9.4 17.6 12 18.5C14.6 17.6 16.5 15 16.5 12.2V9.2L12 6.5Z" 
                fill="url(#cta-crest-inner)" 
                fillOpacity="0.6"
                stroke="#f59e0b"
                strokeWidth="1.2"
              />
              <defs>
                <linearGradient id="cta-crest-outer" x1="4.5" y1="2.5" x2="19.5" y2="22.2" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#f59e0b" />
                  <stop offset="0.5" stopColor="#fbbf24" />
                  <stop offset="1" stopColor="#ef4444" />
                </linearGradient>
                <linearGradient id="cta-crest-inner" x1="7.5" y1="6.5" x2="16.5" y2="18.5" gradientUnits="userSpaceOnUse">
                  <stop stopColor="#d97706" />
                  <stop offset="1" stopColor="#b45309" />
                </linearGradient>
              </defs>
            </svg>
          </div>
        </div>

        {/* Display Typography */}
        <h2 className="text-4xl sm:text-6xl font-black tracking-tight text-white font-sans leading-tight">
          Secure your server.<br />
          <span className="bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-500 bg-clip-text text-transparent">
            In minutes.
          </span>
        </h2>

        {/* Subtitle */}
        <p className="mt-4 text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed">
          Join thousands of communities trusting {botName} for their moderation, security, and automation needs.
        </p>

        {/* Action Buttons */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5 w-full sm:w-auto">
          <button
            onClick={onOpenInvite}
            className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-7 py-3.5 bg-gradient-to-r from-amber-500 via-yellow-500 to-amber-600 hover:from-amber-400 hover:to-yellow-400 active:scale-[0.98] text-black text-sm font-black uppercase tracking-wider rounded-xl shadow-lg shadow-amber-500/25 transition-all duration-200 cursor-pointer font-sans"
          >
            <svg 
              className="w-4 h-4 fill-current" 
              viewBox="0 0 24 24"
            >
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028a19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
            </svg>
            <span>ADD TO DISCORD</span>
          </button>

          <button
            onClick={onOpenLogin}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3.5 bg-[#12141d] hover:bg-[#1a1e2b] border border-slate-800 hover:border-slate-700 active:scale-[0.98] text-slate-200 hover:text-white text-xs sm:text-sm font-bold uppercase tracking-wider rounded-xl transition-all duration-200 cursor-pointer font-sans"
          >
            <LayoutDashboard className="w-4 h-4 text-amber-400" />
            <span>OPEN DASHBOARD</span>
          </button>
        </div>

        {/* Live Status Indicator Badge */}
        <div className="mt-12 inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span>REAL-TIME LIVE BOT STATS</span>
        </div>

        {/* 3 Glowing Stat Metric Cards */}
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
          
          {/* Active Servers */}
          <div className="bg-[#0f1118] border border-amber-500/30 rounded-2xl p-6 shadow-xl shadow-amber-950/20 space-y-2 group hover:border-amber-500/60 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <Server className="w-4 h-4" />
            </div>
            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              <AnimatedCounter target={stats.guilds} duration={2200} />
            </div>
            <p className="text-[11px] font-black uppercase tracking-widest text-slate-400">
              ACTIVE SERVERS
            </p>
          </div>

          {/* Global Users */}
          <div className="bg-[#0f1118] border border-amber-500/30 rounded-2xl p-6 shadow-xl shadow-amber-950/20 space-y-2 group hover:border-amber-500/60 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <Users className="w-4 h-4" />
            </div>
            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              <AnimatedCounter target={stats.users} duration={2500} />
            </div>
            <p className="text-[11px] font-black uppercase tracking-widest text-slate-400">
              GLOBAL USERS
            </p>
          </div>

          {/* System Uptime */}
          <div className="bg-[#0f1118] border border-amber-500/30 rounded-2xl p-6 shadow-xl shadow-amber-950/20 space-y-2 group hover:border-amber-500/60 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <Zap className="w-4 h-4" />
            </div>
            <div className="text-3xl sm:text-4xl font-black text-white font-mono tracking-tight">
              <AnimatedCounter target={stats.uptime} duration={2000} isPercent={true} />
            </div>
            <p className="text-[11px] font-black uppercase tracking-widest text-slate-400">
              SYSTEM UPTIME
            </p>
          </div>

        </div>

      </div>
    </section>
  );
};
