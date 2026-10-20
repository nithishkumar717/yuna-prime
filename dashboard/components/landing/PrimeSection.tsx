"use client";

import React from 'react';
import { 
  Crown, 
  Shield, 
  ArrowUp, 
  Sparkles, 
  Check, 
  Zap, 
  ShieldCheck, 
  Lock, 
  Key, 
  Headphones,
  Award
} from 'lucide-react';

interface PrimeSectionProps {
  onOpenDashboard?: () => void;
}

export const PrimeSection: React.FC<PrimeSectionProps> = ({ onOpenDashboard }) => {
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  const pills = [
    { label: 'Advanced Limits', icon: Shield },
    { label: 'Automod Core+', icon: Zap },
    { label: 'Auto Emergency', icon: ShieldCheck },
    { label: 'Anti-Betray', icon: Lock },
    { label: 'Vanity Guard', icon: Sparkles },
    { label: 'No Prefix', icon: Key },
    { label: 'Autorole', icon: Award },
    { label: 'Member Recovery', icon: Headphones }
  ];

  return (
    <section id="prime-section" className="py-24 bg-[#08090d] relative overflow-hidden">
      {/* Background Gold & Crimson Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[850px] h-[550px] bg-gradient-to-tr from-amber-600/15 via-red-600/15 to-transparent blur-[160px] rounded-full pointer-events-none -z-10"></div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-14">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-950/40 border border-amber-800/50 text-amber-400 text-xs font-bold uppercase tracking-wider mb-4 shadow-lg shadow-amber-950/50 animate-pulse">
            <Crown className="w-3.5 h-3.5" />
            <span>{botName} PRIME</span>
          </div>

          <h2 className="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight bg-gradient-to-r from-white via-amber-200 via-yellow-100 to-white bg-clip-text text-transparent drop-shadow-[0_2px_15px_rgba(245,158,11,0.3)]">
            Unlock Infinite Potential
          </h2>

          <p className="mt-4 text-sm sm:text-base text-slate-400">
            Experience Ultimate <strong className="text-amber-300 font-bold">Control</strong>, <strong className="text-red-400 font-bold">Performance</strong> & <strong className="text-rose-400 font-bold">Security</strong>
          </p>
        </div>

        {/* 3 Prime Bento Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          
          {/* Card 1: Autonomous Security */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-gradient-to-b from-[#140b0d] to-[#0d0708] border border-red-900/40 hover:border-red-500/70 rounded-2xl p-6 transition-all duration-300 ease-out transform hover:-translate-y-2.5 hover:scale-[1.02] hover:shadow-[0_15px_40px_rgba(239,68,68,0.25)] group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-red-500 to-rose-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-red-500/20 border border-red-500/40 flex items-center justify-center mb-5 group-hover:scale-110 group-hover:rotate-6 group-hover:bg-red-500/30 group-hover:border-red-500/70 transition-all duration-300 shadow-md">
              <Shield className="w-5.5 h-5.5 text-red-400 group-hover:drop-shadow-[0_0_10px_rgba(239,68,68,0.8)] transition-all" />
            </div>

            <h3 className="text-xs font-black uppercase tracking-wider text-red-400 mb-4 group-hover:text-red-300 transition-colors">
              AUTONOMOUS SECURITY
            </h3>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Advanced Limit System</span>
                <Check className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Automod Core+</span>
                <Check className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Anti-Betray System</span>
                <Check className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Auto Emergency</span>
                <Check className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Secure Channel Lock</span>
                <Check className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
              </div>
            </div>
          </div>

          {/* Card 2: 5x Higher Limits */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-gradient-to-b from-[#14100b] to-[#0d0b07] border border-amber-900/40 hover:border-amber-500/70 rounded-2xl p-6 transition-all duration-300 ease-out transform hover:-translate-y-2.5 hover:scale-[1.02] hover:shadow-[0_15px_40px_rgba(245,158,11,0.25)] group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-amber-400 to-yellow-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center mb-5 group-hover:scale-110 group-hover:-translate-y-1 group-hover:bg-amber-500/30 group-hover:border-amber-500/70 transition-all duration-300 shadow-md">
              <ArrowUp className="w-5.5 h-5.5 text-amber-400 group-hover:drop-shadow-[0_0_10px_rgba(245,158,11,0.8)] transition-all" />
            </div>

            <h3 className="text-xs font-black uppercase tracking-wider text-amber-400 mb-4 group-hover:text-amber-300 transition-colors">
              5X HIGHER LIMITS
            </h3>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Autoresponder Triggers</span>
                <Check className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Autoreact Triggers</span>
                <Check className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Custom Role Aliases</span>
                <Check className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Active Giveaways</span>
                <Check className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
              </div>
            </div>
          </div>

          {/* Card 3: Full Control */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-gradient-to-b from-[#140b17] to-[#0c070f] border border-purple-900/40 hover:border-purple-500/70 rounded-2xl p-6 transition-all duration-300 ease-out transform hover:-translate-y-2.5 hover:scale-[1.02] hover:shadow-[0_15px_40px_rgba(168,85,247,0.25)] group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-purple-500 to-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-purple-500/20 border border-purple-500/40 flex items-center justify-center mb-5 group-hover:scale-110 group-hover:rotate-6 group-hover:bg-purple-500/30 group-hover:border-purple-500/70 transition-all duration-300 shadow-md">
              <Crown className="w-5.5 h-5.5 text-purple-400 group-hover:drop-shadow-[0_0_10px_rgba(168,85,247,0.8)] transition-all" />
            </div>

            <h3 className="text-xs font-black uppercase tracking-wider text-purple-400 mb-4 group-hover:text-purple-300 transition-colors">
              FULL CONTROL
            </h3>

            <div className="space-y-3 text-xs text-slate-300">
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Premium Autorole</span>
                <Check className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Vanity Protection</span>
                <Check className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>No Prefix Access</span>
                <Check className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              </div>
              <div className="flex items-center justify-between group-hover:text-white transition-colors">
                <span>Member Recovery</span>
                <Check className="w-4 h-4 text-purple-400 group-hover:scale-110 transition-transform" />
              </div>
            </div>
          </div>

        </div>

        {/* Feature Badges List */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          {pills.map((pill, idx) => {
            const Icon = pill.icon;
            return (
              <div
                key={idx}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-[#12141d] border border-slate-800 hover:border-amber-500/50 hover:bg-[#1a1d2b] hover:scale-105 text-[11px] font-semibold text-slate-300 hover:text-white transition-all duration-200 cursor-pointer shadow-md"
              >
                <Icon className="w-3.5 h-3.5 text-amber-400" />
                <span>{pill.label}</span>
              </div>
            );
          })}
        </div>

        {/* Upgrade Callout Bar */}
        <div className="bg-gradient-to-r from-amber-950/40 via-red-950/40 to-amber-950/40 border border-amber-600/40 hover:border-amber-500/80 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-4 transition-all duration-300 shadow-xl hover:shadow-[0_0_30px_rgba(245,158,11,0.2)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-300 shrink-0">
              <Crown className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
                UPGRADE TO {botName} PRIME
              </h4>
              <p className="text-xs text-slate-400">Unlock priority clusters, dedicated shards & 24/7 VIP engineers.</p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-semibold text-slate-300">
            <div className="flex items-center gap-1 text-amber-300">
              <Check className="w-3.5 h-3.5" /> Priority Support
            </div>
            <div className="flex items-center gap-1 text-amber-300">
              <Check className="w-3.5 h-3.5" /> Instant Access
            </div>
            <div className="flex items-center gap-1 text-amber-300">
              <Check className="w-3.5 h-3.5" /> Exclusive Badge
            </div>
          </div>
        </div>

      </div>
    </section>
  );
};
