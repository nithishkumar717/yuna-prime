/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║                                                                  ║
 * ║   ░█▄░█░█▀▀░█▀▄░█▀▄   ░█░█   ░█░░░▀█▀░█░█░█▀▀                 ║
 * ║   ░█░▀█░█▀▀░█▀▄░█░█   ░▄▀▄   ░█░░░░█░░▀▄▀░█▀▀                 ║
 * ║   ░▀░░▀░▀▀▀░▀░▀░▀▀░   ░▀░▀   ░▀▀▀░▀█▀░░▀░░▀▀▀                 ║
 * ║                                                                  ║
 * ║           © 2026 Nerd X Live — All Rights Reserved              ║
 * ║                                                                  ║
 * ║   discord  ──  https://discord.gg/YzHCx5yQXv                    ║
 * ║   github   ──  https://github.com/nithishkumar717/zyuna         ║
 * ║                                                                  ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

"use client";

import React, { useState, useEffect } from "react";
import { 
  Bell, 
  Tv, 
  Youtube, 
  CheckCircle2, 
  AlertCircle,
  Radio,
  ExternalLink
} from "lucide-react";
import { api } from "@/lib/api";
import { AlertsConfig, DiscordChannel, DiscordRole } from "@/types/api";

export default function GuildAlertsPage({ params }: { params: { guildId: string } }) {
  const [config, setConfig] = useState<AlertsConfig | null>(null);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);
  const [loading, setLoading] = useState(true);
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [alertsData, channelsData, rolesData] = await Promise.all([
          api.getAlertsConfig(params.guildId).catch(() => ({ guild_id: params.guildId, alerts: [] })),
          api.getChannels(params.guildId).catch(() => []),
          api.getRoles(params.guildId).catch(() => [])
        ]);
        setConfig(alertsData);
        setChannels(channelsData);
        setRoles(rolesData);
      } catch (err) {
        console.warn("Failed to load alerts page data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [params.guildId]);

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <Bell className="h-6 w-6 text-primary" />
          Social Stream Alerts
        </h2>
        <p className="text-slate-400 mt-1">
          Real-time webhook notifications when your favorite creators go live on YouTube or Twitch.
        </p>
      </div>

      {notification && (
        <div className="p-3 bg-primary/10 border border-primary/30 rounded-xl text-xs text-primary flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notification}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* YouTube Card */}
        <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center justify-center text-red-500">
                <Youtube className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-bold text-white text-base">YouTube Broadcasts</h3>
                <p className="text-xs text-slate-400">Video uploads and livestream drops</p>
              </div>
            </div>
            <span className="text-[10px] font-black uppercase text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              Automated
            </span>
          </div>

          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3 text-xs">
            <p className="text-slate-400 leading-relaxed">
              Configure targeted announcement channels and role mentions using the Discord chat command:
            </p>
            <div className="bg-black/40 p-2.5 rounded-xl font-mono text-[11px] text-red-400 border border-white/5">
              &gt;setnotif youtube &lt;@role&gt; &lt;#channel&gt;
            </div>
          </div>
        </div>

        {/* Twitch Card */}
        <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-purple-500/10 border border-purple-500/20 rounded-xl flex items-center justify-center text-purple-400">
                <Tv className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-bold text-white text-base">Twitch Livestreams</h3>
                <p className="text-xs text-slate-400">Instant go-live push pings</p>
              </div>
            </div>
            <span className="text-[10px] font-black uppercase text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              Automated
            </span>
          </div>

          <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3 text-xs">
            <p className="text-slate-400 leading-relaxed">
              Configure Twitch live notifications with zero-latency webhook delivery:
            </p>
            <div className="bg-black/40 p-2.5 rounded-xl font-mono text-[11px] text-purple-400 border border-white/5">
              &gt;setnotif twitch &lt;@role&gt; &lt;#channel&gt;
            </div>
          </div>
        </div>
      </div>

      {/* Overview Box */}
      <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-3">
        <div className="flex items-center gap-2">
          <Radio className="h-5 w-5 text-primary" />
          <h3 className="font-bold text-white text-sm">Monitoring Status</h3>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          The background stream poller checks RSS feeds and streaming webhooks every 5 minutes to deliver embeds immediately with viewer preview cards and direct stream links. Use <code className="text-primary font-mono">&gt;setnotif list</code> or <code className="text-primary font-mono">&gt;setnotif reset</code> in server chat to inspect or reset.
        </p>
      </div>
    </div>
  );
}
