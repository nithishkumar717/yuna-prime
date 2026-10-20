"use client";

import React from 'react';
import { 
  Sliders, 
  ShieldCheck, 
  Bot, 
  Sparkles, 
  Wrench, 
  Clock, 
  ArrowRight,
  FileCheck2,
  Star
} from 'lucide-react';

interface WhyYunaSectionProps {
  onOpenDashboard?: () => void;
  onExploreCommands?: () => void;
}

export const WhyYunaSection: React.FC<WhyYunaSectionProps> = ({ onOpenDashboard, onExploreCommands }) => {
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  const advantages = [
    {
      icon: Sliders,
      title: 'DASHBOARD CONTROL',
      desc: 'Configure everything visually through an intuitive real-time control panel.'
    },
    {
      icon: ShieldCheck,
      title: 'MULTI-LAYER PROTECTION',
      desc: 'Antinuke, limits, emergency and logging operate together seamlessly.'
    },
    {
      icon: Bot,
      title: 'INTELLIGENT MODERATION',
      desc: 'Advanced auto moderation with regex filters, smart detection, and secure moderation tools.'
    },
    {
      icon: Sparkles,
      title: 'EFFORTLESS MANAGEMENT',
      desc: 'Welcomes, automations and giveaways configured easily from dashboard.'
    },
    {
      icon: Wrench,
      title: 'POWERFUL UTILITIES',
      desc: 'Comprehensive tools for server info, roles, media, stats and actions.'
    },
    {
      icon: Clock,
      title: 'SETUP IN MINUTES',
      desc: `Deploy ${botName} with production-ready security without complex setup.`
    }
  ];

  return (
    <section id="why-yuna" className="py-24 bg-[#06070a] relative overflow-hidden">
      {/* Background Ambience */}
      <div className="absolute top-1/2 left-1/3 -translate-y-1/2 w-96 h-96 bg-amber-600/10 blur-[140px] rounded-full pointer-events-none"></div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-950/40 border border-amber-800/40 text-amber-400 text-xs font-bold uppercase tracking-wider mb-4">
            <Star className="w-3.5 h-3.5" />
            <span>THE {botName.toUpperCase()} ADVANTAGE</span>
          </div>

          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Why Choose {botName}?
          </h2>

          <p className="mt-3 text-xs sm:text-sm text-slate-400 max-w-2xl mx-auto">
            The ultimate infrastructure for standard-setting communities. Ditch the guesswork and upgrade to production-ready tools.
          </p>
        </div>

        {/* Content Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
          
          {/* Left Illustrated Graphic Card */}
          <div className="lg:col-span-5 flex items-center justify-center">
            <div className="relative w-full max-w-sm bg-gradient-to-b from-[#131520] to-[#0a0c12] rounded-3xl border border-amber-500/20 p-8 shadow-2xl shadow-amber-950/30 flex flex-col items-center text-center">
              <div className="w-24 h-24 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mb-6 text-amber-400">
                <FileCheck2 className="w-12 h-12" />
              </div>

              <h4 className="text-lg font-black text-white mb-2">Engineered for Excellence</h4>
              <p className="text-xs text-slate-400 leading-relaxed mb-6">
                Over 3.1 million users trust our zero-compromise architectural pipeline for safety, audio clarity, and immediate threat mitigation.
              </p>

              <div className="w-full pt-4 border-t border-slate-800 flex items-center justify-around text-[11px] font-bold text-amber-300">
                <span>⚡ 99.9% Uptime</span>
                <span>•</span>
                <span>🛡️ Zero Leaks</span>
                <span>•</span>
                <span>🚀 Fast Sync</span>
              </div>
            </div>
          </div>

          {/* Right 6 Advantage Points */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-5">
            {advantages.map((item, idx) => {
              const Icon = item.icon;
              return (
                <div 
                  key={idx} 
                  className="bg-[#0f1118] border border-slate-800/80 hover:border-amber-500/40 rounded-2xl p-4 transition-all duration-200 space-y-2 group"
                >
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                      <Icon className="w-4 h-4" />
                    </div>
                    <h5 className="text-xs font-black uppercase tracking-wider text-slate-200 group-hover:text-amber-300 transition-colors">
                      {item.title}
                    </h5>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed pl-9">
                    {item.desc}
                  </p>
                </div>
              );
            })}
          </div>

        </div>

        {/* Bottom Explore Commands Button */}
        <div className="mt-12 text-center">
          <button
            onClick={onExploreCommands || onOpenDashboard}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-400 hover:to-yellow-400 text-black text-xs sm:text-sm font-black uppercase tracking-wider shadow-lg shadow-amber-500/25 transition-all cursor-pointer font-sans"
          >
            <span>EXPLORE ALL COMMANDS</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

      </div>
    </section>
  );
};
