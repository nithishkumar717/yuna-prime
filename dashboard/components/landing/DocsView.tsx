"use client";

import React, { useState } from 'react';
import { 
  BookOpen, 
  ShieldCheck, 
  Zap, 
  Sliders, 
  Layers, 
  UserPlus, 
  Gift, 
  Radio, 
  ChevronRight
} from 'lucide-react';

interface DocsViewProps {
  onOpenLogin: () => void;
  onOpenInvite: () => void;
}

export const DocsView: React.FC<DocsViewProps> = ({ onOpenLogin, onOpenInvite }) => {
  const [activeTab, setActiveTab] = useState<string>('getting-started');
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  const topics = [
    { id: 'getting-started', title: 'Getting Started', icon: BookOpen },
    { id: 'antinuke', title: 'Antinuke Protection', icon: ShieldCheck },
    { id: 'automod', title: 'Auto Moderation', icon: Zap },
    { id: 'limits', title: 'Action Limits', icon: Sliders },
    { id: 'emergency', title: 'Emergency Lockdown', icon: Radio },
    { id: 'custom-roles', title: 'Custom Roles', icon: Layers },
    { id: 'welcomer', title: 'Welcomer System', icon: UserPlus },
    { id: 'giveaway', title: 'Giveaways', icon: Gift }
  ];

  return (
    <div className="pt-28 pb-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      
      {/* Top Header */}
      <div className="text-center max-w-3xl mx-auto mb-12">
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white font-sans">
          Documentation
        </h1>
        <p className="mt-3 text-sm sm:text-base text-slate-400">
          Complete guide to setting up and optimizing {botName} for your Discord server
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Sidebar Navigation */}
        <div className="lg:col-span-4 space-y-1.5 bg-[#0b0d14] p-3 rounded-2xl border border-slate-800/80 h-fit">
          <span className="px-3 py-2 text-[10px] font-black uppercase tracking-widest text-slate-500 block">
            Navigation Topics
          </span>

          {topics.map((t) => {
            const Icon = t.icon;
            const isSelected = activeTab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  isSelected 
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30' 
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span>{t.title}</span>
                </div>
                <ChevronRight className="w-3.5 h-3.5 opacity-60" />
              </button>
            );
          })}

          <div className="pt-4 mt-4 border-t border-slate-800 space-y-2">
            <button
              onClick={onOpenInvite}
              className="w-full py-2 bg-gradient-to-r from-red-600 to-rose-600 text-white text-xs font-bold rounded-lg shadow cursor-pointer font-sans"
            >
              Add {botName} Bot
            </button>
            <button
              onClick={onOpenLogin}
              className="w-full py-2 bg-[#141620] hover:bg-[#1c202e] border border-slate-700 text-slate-200 text-xs font-bold rounded-lg cursor-pointer font-sans"
            >
              Open Dashboard
            </button>
          </div>
        </div>

        {/* Right Content Body */}
        <div className="lg:col-span-8 bg-[#0e1017] border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-6">
          {activeTab === 'getting-started' && (
            <div className="space-y-4">
              <h2 className="text-2xl font-black text-white">Getting Started with {botName}</h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {botName} is engineered to provide instant out-of-the-box protection without requiring complex command syntax. Follow the quick guide below:
              </p>

              <div className="space-y-3 pt-2">
                <div className="p-4 rounded-xl bg-[#08090e] border border-slate-800 space-y-1">
                  <span className="text-xs font-bold text-red-400 uppercase">Step 1: Invite Bot</span>
                  <p className="text-xs text-slate-300">
                    Click &ldquo;Add to Discord&rdquo; and invite {botName} with <strong>Administrator permissions</strong>. Ensure {botName}&apos;s role is placed high in your server role hierarchy.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-[#08090e] border border-slate-800 space-y-1">
                  <span className="text-xs font-bold text-red-400 uppercase">Step 2: Enable Antinuke</span>
                  <p className="text-xs text-slate-300">
                    Use <code className="text-amber-300 font-mono text-[11px]">&antinuke enable</code> or activate the AntiNuke toggle in your web dashboard.
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-[#08090e] border border-slate-800 space-y-1">
                  <span className="text-xs font-bold text-red-400 uppercase">Step 3: Configure Limits</span>
                  <p className="text-xs text-slate-300">
                    Set strict channel deletion, ban, and kick quotas so compromised staff accounts are automatically contained.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'antinuke' && (
            <div className="space-y-4">
              <h2 className="text-2xl font-black text-white">Antinuke Protection</h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                Our Antinuke engine monitors Discord audit logs with zero delay. It halts mass bans, channel purges, webhook creations, and role deletions instantly.
              </p>
              <div className="p-4 rounded-xl bg-[#08090e] border border-slate-800 font-mono text-xs text-red-400 space-y-1">
                <p>&antinuke enable</p>
                <p>&antinuke whitelist add @User</p>
                <p>&antinuke logs #mod-logs</p>
              </div>
            </div>
          )}

          {activeTab !== 'getting-started' && activeTab !== 'antinuke' && (
            <div className="space-y-4">
              <h2 className="text-2xl font-black text-white">{topics.find(t => t.id === activeTab)?.title}</h2>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                Configure this module visually through your {botName} Dashboard or via standard Discord prefix commands.
              </p>
              <div className="p-4 rounded-xl bg-[#08090e] border border-slate-800 text-xs text-slate-300">
                Full documentation and schema options for this subsystem are synced in real-time with the web control panel.
              </div>
            </div>
          )}
        </div>

      </div>

    </div>
  );
};
