"use client";

import React, { useState } from 'react';
import { 
  ShieldAlert, 
  ShieldCheck, 
  UserPlus, 
  Gift, 
  Wrench, 
  Check, 
  Zap, 
  Sliders, 
  Headphones, 
  Clock, 
  Key, 
  Shield 
} from 'lucide-react';

interface FeaturesGridProps {
  onSelectFeatureTab?: (tab: string) => void;
}

export const FeaturesGrid: React.FC<FeaturesGridProps> = ({ onSelectFeatureTab }) => {
  const [activeCategory, setActiveCategory] = useState<string>('Automod');

  const categories = [
    { name: 'Automod', icon: Zap },
    { name: 'Moderation', icon: ShieldCheck },
    { name: 'Utilities', icon: Wrench },
    { name: 'Welcoming', icon: UserPlus },
    { name: 'Custom Roles', icon: Key },
    { name: 'Giveaways', icon: Gift },
    { name: 'Music', icon: Headphones }
  ];

  const cards = [
    {
      id: 'security',
      title: 'Advanced Security',
      description: 'Comprehensive protection with antinuke systems, whitelist management, and emergency lockdown capabilities to safeguard your community.',
      icon: Shield,
      accentColor: 'text-red-400',
      badgeBg: 'bg-red-500/10 border-red-500/30',
      bullets: [
        'Antinuke & Limit Protection',
        'Emergency Mode',
        'Anti-betray & Auto Emergency'
      ]
    },
    {
      id: 'moderation',
      title: 'Smart Moderation',
      description: 'Intelligent moderation tools with automated systems, custom filters, and comprehensive logging for effective community management.',
      icon: ShieldAlert,
      accentColor: 'text-cyan-400',
      badgeBg: 'bg-cyan-500/10 border-cyan-500/30',
      bullets: [
        'Auto Moderation',
        'Powerful Moderation Tools',
        'Admin & Moderation Setup'
      ]
    },
    {
      id: 'giveaway',
      title: 'Advanced Giveaway',
      description: 'Run engaging contests with automated winner selection, multiple requirements, and seamless participation.',
      icon: Gift,
      accentColor: 'text-purple-400',
      badgeBg: 'bg-purple-500/10 border-purple-500/30',
      bullets: [
        'Premium Giveaway',
        'Entry Role Requirements',
        'Winner\'s Ticket System'
      ]
    },
    {
      id: 'utilities',
      title: 'Powerful Utilities',
      description: 'Essential tools for server management including info, roles management, automation, voice management, and more.',
      icon: Wrench,
      accentColor: 'text-blue-400',
      badgeBg: 'bg-blue-500/10 border-blue-500/30',
      bullets: [
        'Server Analytics',
        'Voice Management',
        'Automations'
      ]
    },
    {
      id: 'customization',
      title: 'Deep Customization',
      description: 'Tailor every aspect to your server with custom roles, automated responses & reactions, and personalized welcome systems.',
      icon: Sliders,
      accentColor: 'text-amber-400',
      badgeBg: 'bg-amber-500/10 border-amber-500/30',
      bullets: [
        'Welcome System',
        'Custom Roles',
        'Auto Responders & Reactions'
      ]
    },
    {
      id: 'reliability',
      title: '24/7 Reliability',
      description: 'Industry-leading uptime with round-the-clock monitoring and dedicated support team ready to assist you.',
      icon: Clock,
      accentColor: 'text-rose-400',
      badgeBg: 'bg-rose-500/10 border-rose-500/30',
      bullets: [
        '99.99% Uptime',
        '24/7 Support',
        'Active Monitoring'
      ]
    }
  ];

  return (
    <section id="features" className="py-20 bg-[#08090d] relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/2 left-1/4 -translate-y-1/2 w-96 h-96 bg-red-600/10 blur-[130px] rounded-full pointer-events-none"></div>
      <div className="absolute top-1/3 right-1/4 -translate-y-1/2 w-96 h-96 bg-amber-600/10 blur-[130px] rounded-full pointer-events-none"></div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-950/40 border border-red-800/40 text-red-400 text-xs font-bold uppercase tracking-wider mb-4">
            <span>✦</span>
            <span>CORE CAPABILITIES</span>
          </div>
          
          <h2 className="text-3xl sm:text-5xl font-black text-white tracking-tight">
            Uncompromising Performance
          </h2>
          
          <p className="mt-3 text-sm sm:text-base text-slate-400">
            Everything your Discord server needs, engineered with precision and built for massive scaling.
          </p>
        </div>

        {/* Infinite Feature Ticker / Marquee Row */}
        <div className="relative w-full overflow-hidden mb-12 py-2 group-marquee">
          <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-12 sm:w-24 bg-gradient-to-r from-[#08090d] via-[#08090d]/80 to-transparent z-10" />
          <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-12 sm:w-24 bg-gradient-to-l from-[#08090d] via-[#08090d]/80 to-transparent z-10" />

          <div className="animate-marquee-left flex items-center gap-3">
            {[...categories, ...categories, ...categories, ...categories].map((cat, idx) => {
              const Icon = cat.icon;
              const isSelected = activeCategory === cat.name;
              return (
                <button
                  key={`${cat.name}-${idx}`}
                  type="button"
                  onClick={() => {
                    setActiveCategory(cat.name);
                    if (onSelectFeatureTab) onSelectFeatureTab(cat.name);
                  }}
                  className={`flex items-center gap-2.5 px-4 py-2 rounded-xl text-xs font-bold transition-all shrink-0 cursor-pointer border ${
                    isSelected
                      ? 'bg-red-950/40 text-white border-red-500 shadow-lg shadow-red-950/60 ring-1 ring-red-500/50'
                      : 'bg-[#10121a] text-slate-300 border-red-500/50 hover:border-red-400 shadow-md shadow-red-950/40'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 text-red-400" />
                  <span className="whitespace-nowrap">{cat.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 6 Bento Grid Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cards.map((card) => {
            const Icon = card.icon;
            return (
              <div
                key={card.id}
                className="bg-[#0f1118] border border-slate-800/80 hover:border-red-500/40 rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl hover:shadow-red-950/30 flex flex-col justify-between group relative overflow-hidden"
              >
                <div className="absolute top-0 right-0 w-32 h-32 bg-red-500/5 group-hover:bg-red-500/10 blur-2xl rounded-full transition-all"></div>

                <div>
                  <div className={`w-10 h-10 rounded-xl ${card.badgeBg} border flex items-center justify-center mb-5`}>
                    <Icon className={`w-5 h-5 ${card.accentColor}`} />
                  </div>

                  <h3 className="text-lg font-bold text-white mb-2">
                    {card.title}
                  </h3>

                  <p className="text-xs text-slate-400 leading-relaxed mb-6">
                    {card.description}
                  </p>
                </div>

                <div className="pt-4 border-t border-slate-800/60 space-y-2.5">
                  {card.bullets.map((bullet, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                      <div className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                        <Check className="w-2.5 h-2.5" />
                      </div>
                      <span>{bullet}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
};
