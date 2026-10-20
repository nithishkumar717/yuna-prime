"use client";

import React, { useState, useEffect, useRef } from 'react';
import { 
  Users, 
  Zap, 
  CheckCircle2, 
  Radio
} from 'lucide-react';

interface HeroShowcaseProps {
  onOpenDashboard: () => void;
}

// Scroll-Triggered Animated Counter for Numbers
const AnimatedCounter: React.FC<{ target: number; duration?: number }> = ({ 
  target, 
  duration = 2200 
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
      setCurrent(Math.floor(easeOut * target));

      if (progress < 1) {
        animationFrameId = window.requestAnimationFrame(step);
      }
    };

    animationFrameId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animationFrameId);
  }, [hasStarted, target, duration]);

  return (
    <span ref={elementRef}>
      {current.toLocaleString()}
    </span>
  );
};

// Scroll-Triggered Animated Circular Score Gauge (0% to 77%)
const ProtectionScoreGauge: React.FC<{ targetScore?: number }> = ({ targetScore = 77 }) => {
  const [score, setScore] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);
  const gaugeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = gaugeRef.current;
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
      { threshold: 0.2 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!hasStarted) return;
    let startTimestamp: number | null = null;
    let animationFrameId: number;
    const duration = 2200;

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const easeOut = 1 - Math.pow(1 - progress, 3);
      setScore(Math.floor(easeOut * targetScore));

      if (progress < 1) {
        animationFrameId = window.requestAnimationFrame(step);
      }
    };

    animationFrameId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animationFrameId);
  }, [hasStarted, targetScore]);

  return (
    <div ref={gaugeRef} className="relative w-32 h-32 flex items-center justify-center">
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
        <path
          className="text-slate-800"
          strokeWidth="3.5"
          stroke="currentColor"
          fill="none"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
        <path
          className="text-emerald-500 drop-shadow-[0_0_8px_rgba(16,185,129,0.6)] transition-all duration-75"
          strokeDasharray={`${score}, 100`}
          strokeWidth="3.5"
          strokeLinecap="round"
          stroke="currentColor"
          fill="none"
          d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-black text-white font-mono">{score}%</span>
        <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-wider">FORTIFIED</span>
      </div>
    </div>
  );
};

export const HeroShowcase: React.FC<HeroShowcaseProps> = ({ onOpenDashboard }) => {
  const [memberCount, setMemberCount] = useState(1963);
  const [eventList] = useState([
    { id: 1, module: '[AutoMod]', text: 'Blocked discord.gg phishing invite from @unknown_user', time: '2s ago', color: 'text-red-400' },
    { id: 2, module: '[AntiNuke]', text: 'Admin action rate-limit verified for @ModTeam', time: '14s ago', color: 'text-cyan-400' },
    { id: 3, module: '[Protection]', text: 'Verified active server members & permissions matrix', time: '30s ago', color: 'text-emerald-400' }
  ]);

  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <section id="dashboard-showcase" className="py-20 bg-[#08090d] relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-red-600/10 blur-[140px] rounded-full pointer-events-none -z-10"></div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Heading */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <h2 className="text-2xl sm:text-4xl lg:text-5xl font-black text-white tracking-tight">
            A Control Center Designed for{' '}
            <span className="bg-gradient-to-r from-red-400 to-amber-400 bg-clip-text text-transparent">
              Power & Simplicity
            </span>
          </h2>
          <p className="mt-3 text-xs sm:text-sm text-slate-400 max-w-2xl mx-auto">
            Ditch the clunky commands. Every aspect of {botName} is fully manageable through our beautifully designed, lightning-fast web dashboard.
          </p>
        </div>

        {/* Mac OS Dashboard Mockup Frame */}
        <div className="relative rounded-2xl bg-[#0e1017] border border-slate-800 shadow-2xl overflow-hidden">
          {/* Top Window Bar */}
          <div className="bg-[#14161f] border-b border-slate-800 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-emerald-500/80"></div>
            </div>
            
            <div className="text-xs font-mono text-slate-400 flex items-center gap-2">
              <span className="text-red-400">🛡️</span>
              <span>{botName} Dashboard • v2.6 Control Node</span>
            </div>

            <button 
              onClick={onOpenDashboard}
              className="text-[11px] font-bold text-red-400 hover:text-red-300 hover:underline cursor-pointer"
            >
              Open Live Dashboard &rarr;
            </button>
          </div>

          {/* Inner Dashboard Canvas Mockup */}
          <div className="p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 bg-[#0a0c12]">
            
            {/* Left Server Details Column */}
            <div className="lg:col-span-8 space-y-6">
              
              {/* Guild Header Box */}
              <div className="bg-[#12141d] rounded-xl border border-slate-800 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-red-600 to-rose-600 flex items-center justify-center text-white font-black text-lg shadow-lg shadow-red-900/40">
                    {botName.slice(0, 1)}
                  </div>
                  <div>
                    <h4 className="text-base font-bold text-white flex items-center gap-2">
                      {botName} Official Server
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold">
                        VERIFIED
                      </span>
                    </h4>
                    <p className="text-xs text-slate-400">Programming, Support & Tech</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold">
                    <Radio className="w-3.5 h-3.5 animate-pulse text-red-400" />
                    <span>ARMED & ACTIVE</span>
                  </div>
                </div>
              </div>

              {/* Subsystems Metric Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="bg-[#12141d] p-3.5 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-slate-400">AntiNuke System</span>
                  <div className="text-xs font-bold text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Armed & Ready
                  </div>
                </div>

                <div className="bg-[#12141d] p-3.5 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-slate-400">AutoMod Response</span>
                  <div className="text-xs font-bold text-cyan-400 flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5" /> 12ms Latency
                  </div>
                </div>

                <div className="bg-[#12141d] p-3.5 rounded-xl border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Server Members</span>
                  <div className="text-xs font-bold text-white flex items-center gap-1 font-mono">
                    <Users className="w-3.5 h-3.5 text-amber-400" />
                    <span><AnimatedCounter target={memberCount} duration={2200} /> Online</span>
                  </div>
                </div>
              </div>

              {/* Live Incident Stream */}
              <div className="bg-[#12141d] rounded-xl border border-slate-800 p-4 space-y-2.5">
                <div className="text-xs font-bold text-slate-300 flex items-center justify-between">
                  <span>Recent Intercepted Events</span>
                  <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span> Live
                  </span>
                </div>

                <div className="space-y-1.5 font-mono text-[11px]">
                  {eventList.map((item) => (
                    <div key={item.id} className="bg-[#0b0d13] p-2 rounded border border-slate-800/80 flex items-center justify-between text-slate-300 animate-in fade-in duration-200">
                      <span className={item.color}>
                        <strong>{item.module}</strong> {item.text}
                      </span>
                      <span className="text-slate-500 text-[10px] shrink-0 ml-2">{item.time}</span>
                    </div>
                  ))}
                </div>
              </div>

            </div>

            {/* Right Overall Protection Score Column */}
            <div className="lg:col-span-4 bg-[#12141d] rounded-xl border border-slate-800 p-5 flex flex-col items-center justify-center text-center space-y-4">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Overall Protection Score
              </span>

              {/* Circular Score Gauge */}
              <ProtectionScoreGauge targetScore={77} />

              <p className="text-[11px] text-slate-400">
                All 6 automated threat containment modules active and protecting 45 channels.
              </p>

              <button
                onClick={onOpenDashboard}
                className="w-full py-2.5 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white text-xs font-bold rounded-lg shadow-md transition-all cursor-pointer"
              >
                Launch Web Control Panel
              </button>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
};
