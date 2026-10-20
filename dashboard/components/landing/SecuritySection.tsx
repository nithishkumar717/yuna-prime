"use client";

import React from 'react';
import { 
  Zap, 
  AlertTriangle, 
  Shield, 
  ShieldCheck
} from 'lucide-react';

interface SecuritySectionProps {
  onOpenDashboard?: () => void;
}

export const SecuritySection: React.FC<SecuritySectionProps> = ({ onOpenDashboard }) => {
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <section id="security-section" className="py-20 bg-[#06070a] relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/2 right-1/4 -translate-y-1/2 w-96 h-96 bg-red-600/10 blur-[130px] rounded-full pointer-events-none"></div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-left mb-12">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-950/40 border border-red-800/40 text-red-400 text-xs font-bold uppercase tracking-wider mb-4">
            <Shield className="w-3.5 h-3.5" />
            <span>DEFENSE IN DEPTH</span>
          </div>

          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-white tracking-tight">
            Military-Grade<br />Security Architecture
          </h2>

          <p className="mt-3 text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed">
            {botName} employs a multi-layered defense mechanism to perfectly seal your server from raids, nuking attempts, and malicious actors before they even happen.
          </p>
        </div>

        {/* 3 Defensive Mechanism Cards */}
        <div className="space-y-4">
          
          {/* Card 1: Instant Antinuke */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-[#0f1118] border border-slate-800/80 hover:border-red-500/60 rounded-2xl p-5 sm:p-6 transition-all duration-300 ease-out transform hover:-translate-y-2 hover:scale-[1.015] hover:shadow-[0_12px_35px_rgba(239,68,68,0.2)] flex items-start gap-4 group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-red-500 to-rose-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:rotate-6 group-hover:bg-red-500/20 group-hover:border-red-500/60 transition-all duration-300 shadow-md">
              <Zap className="w-5.5 h-5.5 text-red-400 group-hover:drop-shadow-[0_0_8px_rgba(239,68,68,0.8)] transition-all" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white mb-1 group-hover:text-red-400 transition-colors flex items-center gap-2">
                Instant Antinuke
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">
                Detects and halts unauthorized mass-deletions, bans, and token raids in milliseconds.
              </p>
            </div>
          </div>

          {/* Card 2: Adaptive Limit System */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-[#0f1118] border border-slate-800/80 hover:border-amber-500/60 rounded-2xl p-5 sm:p-6 transition-all duration-300 ease-out transform hover:-translate-y-2 hover:scale-[1.015] hover:shadow-[0_12px_35px_rgba(245,158,11,0.2)] flex items-start gap-4 group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-amber-400 to-yellow-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:-rotate-6 group-hover:bg-amber-500/20 group-hover:border-amber-500/60 transition-all duration-300 shadow-md">
              <ShieldCheck className="w-5.5 h-5.5 text-amber-400 group-hover:drop-shadow-[0_0_8px_rgba(245,158,11,0.8)] transition-all" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white mb-1 group-hover:text-amber-400 transition-colors flex items-center gap-2">
                Adaptive Limit System
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">
                Set strict action thresholds for admins to prevent compromised accounts from doing damage.
              </p>
            </div>
          </div>

          {/* Card 3: Emergency Lockdown Mode */}
          <div 
            onClick={onOpenDashboard}
            className="relative bg-[#0f1118] border border-slate-800/80 hover:border-rose-500/60 rounded-2xl p-5 sm:p-6 transition-all duration-300 ease-out transform hover:-translate-y-2 hover:scale-[1.015] hover:shadow-[0_12px_35px_rgba(244,63,94,0.2)] flex items-start gap-4 group cursor-pointer overflow-hidden"
          >
            <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-gradient-to-b from-rose-500 to-red-600 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-l-2xl"></div>

            <div className="w-11 h-11 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0 mt-0.5 group-hover:scale-110 group-hover:rotate-6 group-hover:bg-rose-500/20 group-hover:border-rose-500/60 transition-all duration-300 shadow-md">
              <AlertTriangle className="w-5.5 h-5.5 text-rose-400 group-hover:drop-shadow-[0_0_8px_rgba(244,63,94,0.8)] transition-all" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white mb-1 group-hover:text-rose-400 transition-colors flex items-center gap-2">
                Emergency Lockdown Mode
              </h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors">
                One-click global server freeze that revokes risky permissions and pauses invites until the threat passes.
              </p>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
};
