"use client";

import React from 'react';
import { Terminal, LayoutDashboard, Check, X, Sparkles } from 'lucide-react';

export const CommandVsWebSection: React.FC = () => {
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <section className="py-20 md:py-28 relative bg-[#0a0d16] border-y border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-xs font-semibold uppercase tracking-wider mb-3">
            <Sparkles className="w-3.5 h-3.5 text-[#818cf8]" />
            Modern Experience
          </div>
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
            Say goodbye to endless slash commands.
          </h2>
          <p className="mt-4 text-base sm:text-lg text-slate-300">
            Managing complex server rules in a Discord chat box is slow and frustrating. 
            {botName} replaces command clutter with a fast, modern web control center.
          </p>
        </div>

        {/* Side-by-Side Comparison Box */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
          
          {/* Left: Traditional Legacy Bot Commands */}
          <div className="rounded-2xl bg-[#0f121d] border border-red-500/20 p-6 sm:p-8 space-y-6 flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-800">
                <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400">
                  <Terminal className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Traditional Chat Commands</h3>
                  <p className="text-xs text-red-300/80">Fragmented, slow, and error-prone</p>
                </div>
              </div>

              {/* Terminal code snippet simulation */}
              <div className="bg-[#080a10] rounded-xl p-4 font-mono text-xs text-slate-400 space-y-2 border border-slate-900 shadow-inner">
                <p className="text-slate-500">{"// Complex, memorized parameter flags"}</p>
                <p className="text-red-400/90">/automod spam set_limit threshold:5 time:3s action:delete mute_time:3600 ignore_roles:@Admin</p>
                <p className="text-slate-600">❌ Error: Invalid role snowflake ID format</p>
                <p className="text-slate-500">{"// Blind embed formatting without preview"}</p>
                <p className="text-slate-300">
                  {'/welcome embed title:"Welcome!" color:0x5865F2 desc:"Hey {user} welcome to {guild}..."'}
                </p>
                <p className="text-slate-600">⚠️ Character limit exceeded: field truncated</p>
              </div>

              <div className="space-y-2.5 pt-2">
                {[
                  'No live preview: You must test in public channels',
                  'Hard to see which rules are enabled or conflicting',
                  'Requires memorizing 50+ subcommand arguments',
                  'Multiple bots require separate configurations and prefixes',
                  'Accidental typos can cause destructive bans'
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-xs text-slate-400">
                    <X className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80 text-[11px] text-slate-500 font-medium">
              Result: High staff friction, accidental rule misconfigurations.
            </div>
          </div>

          {/* Right: The Web Platform */}
          <div className="rounded-2xl bg-[#111728] border border-[#5865F2]/40 p-6 sm:p-8 space-y-6 flex flex-col justify-between relative shadow-xl shadow-[#5865F2]/10">
            {/* Top highlight pill */}
            <div className="absolute top-4 right-4 text-[10px] font-bold uppercase tracking-wider text-emerald-300 bg-emerald-500/20 border border-emerald-500/30 px-2.5 py-0.5 rounded-full">
              Recommended
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 pb-4 border-b border-slate-800">
                <div className="w-10 h-10 rounded-xl bg-[#5865F2]/20 border border-[#5865F2]/40 flex items-center justify-center text-[#818cf8]">
                  <LayoutDashboard className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{botName} Web Control Center</h3>
                  <p className="text-xs text-emerald-400 font-medium">Visual, instant, and reliable</p>
                </div>
              </div>

              {/* Visual preview snippet simulation */}
              <div className="bg-[#0a0e1a] rounded-xl p-4 text-xs text-slate-300 space-y-3 border border-slate-800/80 shadow-inner">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">Instant Toggle & Sliders:</span>
                  <span className="text-emerald-400 font-mono text-[11px]">Auto-Synced</span>
                </div>
                <div className="flex items-center gap-3 bg-[#13192b] p-2.5 rounded-lg border border-slate-700/60">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center text-emerald-400 font-bold">
                    ✓
                  </div>
                  <div className="flex-1">
                    <span className="text-white font-bold block text-[11px]">Spam Filter Active</span>
                    <span className="text-slate-400 text-[10px]">5 msgs in 3s • Auto-Action: Delete & Warn</span>
                  </div>
                </div>
                <p className="text-[11px] text-indigo-300">
                  ⚡ Live real-time Discord embed preview with one-click variable insertion.
                </p>
              </div>

              <div className="space-y-2.5 pt-2">
                {[
                  'Real-time live Discord dark-mode preview before publishing',
                  'Centralized switchboard: Enable or adjust rules in one click',
                  'Visual warning ladders and automatic escalation timers',
                  'One single bot handles AutoMod, Invites, Logs, and Welcome',
                  'Safe confirmation modals protect against accidental actions'
                ].map((item, i) => (
                  <div key={i} className="flex items-start gap-2.5 text-xs text-slate-200">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80 text-[11px] text-emerald-300/90 font-medium">
              Result: Effortless moderation, zero guesswork, full server transparency.
            </div>
          </div>

        </div>

      </div>
    </section>
  );
};
