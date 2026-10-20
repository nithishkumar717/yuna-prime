"use client";

import React from 'react';
import { 
  ArrowRight, 
  Zap, 
  UserPlus, 
  Bot, 
  MessageSquare, 
  Gift, 
  Shield 
} from 'lucide-react';

interface WorkflowPreviewSectionProps {
  onOpenDashboard?: () => void;
}

export const WorkflowPreviewSection: React.FC<WorkflowPreviewSectionProps> = ({ onOpenDashboard }) => {
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <section id="workflow-section" className="py-20 bg-[#08090d] relative overflow-hidden">
      {/* Background Ambience */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[700px] h-[500px] bg-red-600/10 blur-[150px] rounded-full pointer-events-none -z-10"></div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-12 gap-6">
          <div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-red-950/40 border border-red-800/40 text-red-400 text-xs font-bold uppercase tracking-wider mb-4">
              <Zap className="w-3.5 h-3.5" />
              <span>SERVER MANAGEMENT</span>
            </div>

            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black text-white tracking-tight">
              Automate <span className="bg-gradient-to-r from-red-400 to-rose-400 bg-clip-text text-transparent">Everything</span>
            </h2>

            <p className="mt-3 text-xs sm:text-sm text-slate-400 max-w-xl leading-relaxed">
              Free your staff from repetitive tasks. {botName} handles the heavy lifting with highly configurable, lightning-fast automation flows designed for massive communities.
            </p>
          </div>

          <button
            onClick={onOpenDashboard}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#12141c] hover:bg-[#1a1d28] border border-slate-800 hover:border-slate-700 text-xs font-bold text-white transition-all self-start md:self-auto cursor-pointer"
          >
            <span>Explore Dashboard</span>
            <ArrowRight className="w-3.5 h-3.5 text-red-400" />
          </button>
        </div>

        {/* 5 Automation Live Cards */}
        <div className="space-y-6">
          
          {/* Card 1: Auto Moderation */}
          <div className="bg-[#0e1017] border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-red-400 text-xs font-bold">
              <Shield className="w-4 h-4" />
              <span>Auto Moderation</span>
            </div>

            <p className="text-xs text-slate-400">
              Enable automated rule enforcement to block spam, abuse, and unsafe content in real time, with per-rule exemptions and detailed logging.
            </p>

            <div className="bg-[#08090e] rounded-xl border border-slate-800/80 p-3.5 space-y-2 font-mono text-xs">
              <div className="flex items-center gap-2 text-slate-300">
                <span className="w-2 h-2 rounded-full bg-red-400 animate-ping"></span>
                <span>System event intercepted</span>
              </div>
              <div className="bg-[#141620] p-2.5 rounded border border-red-500/20 flex items-center justify-between">
                <span className="text-red-300 text-[11px]">🚫 Deleted: <strong className="text-white">Invite Link</strong></span>
                <span className="text-[10px] text-slate-400">#general-chat</span>
              </div>
              <div className="bg-[#141620] p-2.5 rounded border border-emerald-500/20 flex items-center justify-between">
                <span className="text-emerald-400 text-[11px]">✓ Action taken: <strong className="text-white">Timeout 1h</strong></span>
                <span className="text-[10px] text-slate-400">User: @spambot_49</span>
              </div>
            </div>
          </div>

          {/* Card 2: Autorole */}
          <div className="bg-[#0e1017] border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-bold">
              <Bot className="w-4 h-4" />
              <span>Autorole</span>
            </div>

            <p className="text-xs text-slate-400">
              Assign join-time roles automatically for faster server setup and seamless member onboarding.
            </p>

            <div className="bg-[#08090e] rounded-xl border border-slate-800/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between text-[11px] font-bold text-slate-400 border-b border-slate-800 pb-1.5">
                <span>TARGET</span>
                <span>ROLE</span>
              </div>
              <div className="flex items-center justify-between text-xs font-medium">
                <span className="text-slate-300">Humans</span>
                <span className="px-2.5 py-0.5 rounded bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs font-bold">
                  @Members
                </span>
              </div>
              <div className="flex items-center justify-between text-xs font-medium">
                <span className="text-slate-300">Bots</span>
                <span className="px-2.5 py-0.5 rounded bg-purple-500/20 border border-purple-500/30 text-purple-300 text-xs font-bold">
                  @Bots
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Auto Responder */}
          <div className="bg-[#0e1017] border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-amber-400 text-xs font-bold">
              <MessageSquare className="w-4 h-4" />
              <span>Auto Responder</span>
            </div>

            <p className="text-xs text-slate-400">
              Automatically reply or react to triggers with saved responses to improve channel interactions.
            </p>

            <div className="bg-[#08090e] rounded-xl border border-slate-800/80 p-3.5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[11px] uppercase font-bold text-slate-400">Trigger</span>
                <span className="px-2.5 py-1 rounded bg-[#161822] border border-slate-700 text-white font-mono text-xs">
                  !rules
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-[11px] uppercase font-bold text-slate-400">Response</span>
                <span className="text-xs text-slate-300 font-sans">
                  Please read our server guidelines in <strong className="text-blue-400">#rules</strong>.
                </span>
              </div>
            </div>
          </div>

          {/* Card 4: Welcomer */}
          <div className="bg-[#0e1017] border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-rose-400 text-xs font-bold">
              <UserPlus className="w-4 h-4" />
              <span>Welcomer</span>
            </div>

            <p className="text-xs text-slate-400">
              Personalize welcome messages with custom configuration, built-in and reusable templates.
            </p>

            {/* Discord Welcome Card Simulator */}
            <div className="bg-[#08090e] rounded-xl border border-slate-800/80 p-4">
              <div className="bg-[#2f3136] rounded-xl p-4 border border-[#202225] space-y-2 max-w-xl mx-auto">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-red-500 flex items-center justify-center text-white font-bold text-sm">
                    {botName.slice(0, 1)}
                  </div>
                  <div>
                    <span className="text-xs font-bold text-white">{botName} Bot</span>
                    <span className="ml-1.5 px-1 py-0.2 bg-[#5865f2] text-white text-[9px] font-bold rounded">BOT</span>
                    <p className="text-[10px] text-slate-400">Today at 5:24 PM</p>
                  </div>
                </div>
                
                {/* Embed */}
                <div className="border-l-4 border-red-500 bg-[#2b2d31] p-3 rounded text-xs space-y-1.5">
                  <p className="text-sm font-black text-white">⚡ WELCOME TO OUR COMMUNITY ⚡</p>
                  <p className="text-slate-300 text-xs">
                    Welcome <span className="text-[#00aff4] font-semibold">@User</span>! You are our <strong className="text-white">#1,482nd</strong> member. Make sure to check rules!
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Card 5: Giveaway System */}
          <div className="bg-[#0e1017] border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-purple-400 text-xs font-bold">
              <Gift className="w-4 h-4" />
              <span>Giveaway System</span>
            </div>

            <p className="text-xs text-slate-400">
              Advanced Giveaway system to run engaging contests with automated winner selection and seamless participation.
            </p>

            {/* Discord Giveaway Card Simulator */}
            <div className="bg-[#08090e] rounded-xl border border-slate-800/80 p-4">
              <div className="bg-[#2f3136] rounded-xl p-4 border border-[#202225] space-y-2 max-w-xl mx-auto">
                <div className="border-l-4 border-amber-500 bg-[#2b2d31] p-3.5 rounded text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-black text-amber-400 flex items-center gap-1.5">
                      <Gift className="w-4 h-4" /> NEW GIVEAWAY
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">Ends in 2h 45m</span>
                  </div>

                  <p className="text-white font-bold text-xs">
                    🎁 Prize: <span className="text-amber-300">1x Discord Nitro Classic</span>
                  </p>
                  <p className="text-slate-300 text-[11px]">
                    Hosted by: <strong className="text-white">@ServerOwner</strong> • Winners: <strong>1</strong>
                  </p>

                  <div className="pt-2">
                    <div className="inline-flex px-3.5 py-1.5 bg-[#5865f2] text-white text-xs font-bold rounded items-center gap-1.5 cursor-pointer">
                      🎉 React with 🎉 to enter (142 entries)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
};
