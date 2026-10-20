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
  Headphones, 
  Play, 
  Pause, 
  SkipForward, 
  Square, 
  Volume2, 
  Radio, 
  Sparkles, 
  ListMusic, 
  Disc3,
  Sliders,
  RefreshCw,
  CheckCircle2,
  AlertCircle
} from "lucide-react";
import { api } from "@/lib/api";
import { MusicPlayerState } from "@/types/api";

const DSP_PRESETS = [
  "Flat", "Bassboost", "8D", "Nightcore", "Vaporwave", 
  "Pop", "Soft", "Treblebass", "Karaoke", "Vibrato", "Tremolo"
];

export default function GuildMusicPage({ params }: { params: { guildId: string } }) {
  const [playerState, setPlayerState] = useState<MusicPlayerState | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedFilter, setSelectedFilter] = useState("Flat");
  const [volume, setVolume] = useState(100);
  const [notification, setNotification] = useState<string | null>(null);

  const fetchPlayer = async () => {
    try {
      const data = await api.getMusicState(params.guildId);
      setPlayerState(data);
      if (data?.volume !== undefined) setVolume(data.volume);
      if (data?.filter_preset) setSelectedFilter(data.filter_preset);
    } catch (err) {
      console.warn("Could not fetch music state", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlayer();
    const interval = setInterval(fetchPlayer, 5000);
    return () => clearInterval(interval);
  }, [params.guildId]);

  const handleAction = async (action: any, value?: any) => {
    setActionLoading(true);
    try {
      await api.controlMusic(params.guildId, { action, value });
      setNotification(`Action '${action}' executed successfully.`);
      setTimeout(() => setNotification(null), 3000);
      await fetchPlayer();
    } catch (err: any) {
      setNotification(`Action failed: ${err.message || "Unknown error"}`);
      setTimeout(() => setNotification(null), 3000);
    } finally {
      setActionLoading(false);
    }
  };

  const isPlaying = playerState?.is_playing && !playerState?.is_paused;
  const currentTrack = playerState?.current_track;

  return (
    <div className="max-w-6xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Headphones className="h-6 w-6 text-primary animate-pulse" />
            Studio Audio Player
          </h2>
          <p className="text-slate-400 mt-1">
            Wavelink-powered high-fidelity audio engine with real-time CV2 controls & uninterrupted restart recovery.
          </p>
        </div>
        <button
          onClick={fetchPlayer}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-bold transition-all border border-slate-700/60 self-start"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {notification && (
        <div className="p-3 bg-primary/10 border border-primary/30 rounded-xl text-xs text-primary flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notification}</span>
        </div>
      )}

      {/* Main Player Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Now Playing & Controls */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 relative overflow-hidden shadow-2xl">
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
                  <Disc3 className={`h-6 w-6 ${isPlaying ? "animate-spin" : ""}`} />
                </div>
                <div>
                  <span className="text-[10px] font-black uppercase text-slate-400 tracking-wider">Now Playing</span>
                  <h3 className="text-lg font-bold text-white truncate max-w-md">
                    {currentTrack?.title || "No track currently playing"}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {currentTrack?.author ? `By ${currentTrack.author}` : "Queue is empty or bot is idle"}
                  </p>
                </div>
              </div>
              <span className={`text-[10px] font-black uppercase px-3 py-1 rounded-full border ${
                isPlaying 
                  ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" 
                  : "text-amber-400 bg-amber-500/10 border-amber-500/30"
              }`}>
                {playerState?.is_connected ? (isPlaying ? "Streaming" : "Paused") : "Idle"}
              </span>
            </div>

            {/* Playback Progress */}
            <div className="space-y-2 mb-6">
              <div className="h-2 w-full bg-slate-900 rounded-full overflow-hidden border border-slate-800">
                <div 
                  className="h-full bg-primary transition-all duration-300 rounded-full"
                  style={{ 
                    width: currentTrack?.duration 
                      ? `${Math.min(100, ((playerState?.position || 0) / currentTrack.duration) * 100)}%` 
                      : "0%" 
                  }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                <span>{playerState?.position ? `${Math.floor(playerState.position / 60)}:${String(Math.floor(playerState.position % 60)).padStart(2, "0")}` : "0:00"}</span>
                <span>{currentTrack?.duration ? `${Math.floor(currentTrack.duration / 60)}:${String(Math.floor(currentTrack.duration % 60)).padStart(2, "0")}` : "0:00"}</span>
              </div>
            </div>

            {/* Core Controls */}
            <div className="flex flex-wrap items-center justify-center gap-4 pt-4 border-t border-slate-800">
              {isPlaying ? (
                <button
                  disabled={actionLoading}
                  onClick={() => handleAction("pause")}
                  className="p-4 bg-slate-800 hover:bg-slate-700 text-white rounded-2xl transition-all shadow-lg active:scale-95"
                  title="Pause"
                >
                  <Pause className="h-5 w-5" />
                </button>
              ) : (
                <button
                  disabled={actionLoading}
                  onClick={() => handleAction("resume")}
                  className="p-4 bg-primary hover:bg-primary/90 text-white rounded-2xl transition-all shadow-lg active:scale-95"
                  title="Play"
                >
                  <Play className="h-5 w-5" />
                </button>
              )}

              <button
                disabled={actionLoading}
                onClick={() => handleAction("skip")}
                className="p-4 bg-slate-800 hover:bg-slate-700 text-white rounded-2xl transition-all shadow-lg active:scale-95"
                title="Skip Track"
              >
                <SkipForward className="h-5 w-5" />
              </button>

              <button
                disabled={actionLoading}
                onClick={() => handleAction("stop")}
                className="p-4 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 text-red-400 rounded-2xl transition-all shadow-lg active:scale-95"
                title="Stop & Clear"
              >
                <Square className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* DSP Filter Presets */}
          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <Sliders className="h-5 w-5 text-primary" />
              <h3 className="font-bold text-white text-sm">DSP Audio FX Filters</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">Select a real-time hardware filter to apply on the active voice stream.</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {DSP_PRESETS.map((preset) => (
                <button
                  key={preset}
                  onClick={() => {
                    setSelectedFilter(preset);
                    handleAction("set_filter", preset);
                  }}
                  className={`p-2.5 rounded-xl text-xs font-bold transition-all border ${
                    selectedFilter.toLowerCase() === preset.toLowerCase()
                      ? "bg-primary text-white border-primary shadow-lg shadow-primary/20"
                      : "bg-slate-900/60 text-slate-300 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Audio Queue & Telemetry */}
        <div className="space-y-6">
          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ListMusic className="h-5 w-5 text-primary" />
                <h3 className="font-bold text-white text-sm">Track Queue</h3>
              </div>
              <span className="text-[10px] font-black uppercase text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
                {playerState?.queue?.length || 0} Tracks
              </span>
            </div>

            {playerState?.queue && playerState.queue.length > 0 ? (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {playerState.queue.map((track, idx) => (
                  <div key={idx} className="p-3 bg-slate-900/60 border border-slate-800/80 rounded-xl flex items-center justify-between">
                    <div className="truncate mr-2">
                      <p className="text-xs font-bold text-white truncate">{track.title}</p>
                      <p className="text-[10px] text-slate-400 truncate">{track.author}</p>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 shrink-0">
                      {Math.floor(track.duration / 60)}:{String(Math.floor(track.duration % 60)).padStart(2, "0")}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-slate-500 text-xs">
                No tracks currently queued.
              </div>
            )}
          </div>

          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6">
            <h3 className="font-bold text-white text-sm mb-4">Audio Recovery Engine</h3>
            <div className="space-y-3 text-xs text-slate-400">
              <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                <span>Persistence State</span>
                <span className="text-emerald-400 font-bold">Enabled</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                <span>Audio Engine</span>
                <span className="text-white font-mono">Wavelink v3 / Lavalink</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span>Yuna UI Preset</span>
                <span className="text-primary font-bold">music_card.png</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
