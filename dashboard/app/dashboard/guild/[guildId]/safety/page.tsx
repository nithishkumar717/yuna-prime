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
  ShieldCheck, 
  Plus, 
  Trash2, 
  ShieldAlert, 
  Users, 
  Mail, 
  CheckCircle2, 
  AlertCircle,
  RefreshCw
} from "lucide-react";
import { api } from "@/lib/api";
import { SafetyConfig } from "@/types/api";

export default function GuildSafetyPage({ params }: { params: { guildId: string } }) {
  const [config, setConfig] = useState<SafetyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [newWord, setNewWord] = useState("");
  const [newRole, setNewRole] = useState("");
  const [notification, setNotification] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchSafety = async () => {
    try {
      const data = await api.getSafetyConfig(params.guildId);
      setConfig(data);
    } catch (err) {
      console.warn("Could not fetch safety config", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSafety();
  }, [params.guildId]);

  const handleAddWord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWord.trim()) return;
    setIsSubmitting(true);
    try {
      await api.updateSafetyConfig(params.guildId, { add_word: newWord.trim().toLowerCase() });
      setNotification(`Added '${newWord.trim()}' to blacklist.`);
      setNewWord("");
      await fetchSafety();
    } catch (err: any) {
      setNotification(`Failed: ${err.message || "Could not add word"}`);
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setNotification(null), 3000);
    }
  };

  const handleRemoveWord = async (word: string) => {
    setIsSubmitting(true);
    try {
      await api.updateSafetyConfig(params.guildId, { remove_word: word });
      setNotification(`Removed '${word}' from blacklist.`);
      await fetchSafety();
    } catch (err: any) {
      setNotification(`Failed: ${err.message || "Could not remove word"}`);
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setNotification(null), 3000);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" />
          Chat Safety & Word Filter
        </h2>
        <p className="text-slate-400 mt-1">
          Automated text protection: filter forbidden vocabulary and configure role bypass exemptions.
        </p>
      </div>

      {notification && (
        <div className="p-3 bg-primary/10 border border-primary/30 rounded-xl text-xs text-primary flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{notification}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Word Blacklist Section */}
        <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-red-400" />
              <h3 className="font-bold text-white text-sm">Forbidden Words</h3>
            </div>
            <span className="text-[10px] font-black uppercase text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
              {config?.blacklisted_words?.length || 0} Blocked
            </span>
          </div>

          <form onSubmit={handleAddWord} className="flex gap-2">
            <input
              type="text"
              placeholder="Add word to blacklist..."
              value={newWord}
              onChange={(e) => setNewWord(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-primary transition-all"
            />
            <button
              type="submit"
              disabled={isSubmitting || !newWord.trim()}
              className="px-4 py-2.5 bg-primary hover:bg-primary/90 text-white rounded-xl text-xs font-bold transition-all disabled:opacity-50 flex items-center gap-1.5"
            >
              <Plus className="h-4 w-4" />
              Add
            </button>
          </form>

          {config?.blacklisted_words && config.blacklisted_words.length > 0 ? (
            <div className="flex flex-wrap gap-2 max-h-[300px] overflow-y-auto">
              {config.blacklisted_words.map((w) => (
                <span 
                  key={w} 
                  className="px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-300 flex items-center gap-2 group hover:border-red-500/40"
                >
                  <span>{w}</span>
                  <button
                    onClick={() => handleRemoveWord(w)}
                    className="text-slate-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-slate-500 text-xs">
              No words blacklisted. Chat is currently operating without explicit word blocklist rules.
            </div>
          )}
        </div>

        {/* Staff Emergency & Policies */}
        <div className="space-y-6">
          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              <h3 className="font-bold text-white text-sm">Staff Dispatch System</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Server members can use the <code className="text-primary font-mono">&gt;dm_staff</code> command to open a direct, secure line with moderators and administrators for emergency assistance or abuse reports.
            </p>
            <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-2xl space-y-2 text-xs">
              <div className="flex justify-between text-slate-300">
                <span>Dispatch Mode</span>
                <span className="text-emerald-400 font-bold">Direct Messaging</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Admin Bypass</span>
                <span className="text-emerald-400 font-bold">Enabled</span>
              </div>
            </div>
          </div>

          <div className="bg-[#141B2D] border border-slate-800 rounded-3xl p-6 space-y-3">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <h3 className="font-bold text-white text-sm">Bypass Rules</h3>
            </div>
            <p className="text-xs text-slate-400">
              Users possessing Discord Administrator permissions automatically bypass blacklisted phrase scanning. Custom role bypasses can be toggled using <code className="text-primary font-mono">&gt;blacklistword bypass</code> in chat.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
