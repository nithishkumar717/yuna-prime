"use client";

import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import { PublicBotServer, UniverseDepth } from './types';

// Discord Partner Badge (Scalloped emblem with partner glyph)
const DiscordPartnerBadge: React.FC<{ className?: string }> = ({ className = "w-3.5 h-3.5" }) => (
  <svg className={`${className} shrink-0 text-[#5865F2]`} viewBox="0 0 16 16" fill="currentColor">
    <title>Discord Partner</title>
    <path d="M7.425.414a.79.79 0 0 1 1.15 0l1.246 1.306a.79.79 0 0 0 .736.242l1.78-.363a.79.79 0 0 1 .93.676l.192 1.796a.79.79 0 0 0 .487.647l1.644.757a.79.79 0 0 1 .432.99l-.757 1.644a.79.79 0 0 0 0 .808l.757 1.644a.79.79 0 0 1-.432.99l-1.644.757a.79.79 0 0 0-.487.647l-.192 1.796a.79.79 0 0 1-.93.676l-1.78-.363a.79.79 0 0 0-.736.242l-1.246 1.306a.79.79 0 0 1-1.15 0l-1.246-1.306a.79.79 0 0 0-.736-.242l-1.78.363a.79.79 0 0 1-.93-.676l-.192-1.796a.79.79 0 0 0-.487-.647L.414 9.475a.79.79 0 0 1-.432-.99l.757-1.644a.79.79 0 0 0 0-.808L.002 4.39a.79.79 0 0 1 .432-.99l1.644-.757a.79.79 0 0 0 .487-.647l.192-1.796a.79.79 0 0 1 .93-.676l1.78.363a.79.79 0 0 0 .736-.242L7.425.414z"/>
    <path fill="#fff" d="M10.8 5.6a1.8 1.8 0 0 0-2.4 0L8 6l-.4-.4a1.8 1.8 0 0 0-2.4 2.6L8 11l2.8-2.8a1.8 1.8 0 0 0 0-2.6z"/>
  </svg>
);

// Discord Verified Community Badge (Scalloped emblem with checkmark)
const DiscordVerifiedBadge: React.FC<{ className?: string }> = ({ className = "w-3.5 h-3.5" }) => (
  <svg className={`${className} shrink-0 text-[#38bdf8]`} viewBox="0 0 16 16" fill="currentColor">
    <title>Verified Community</title>
    <path d="M7.425.414a.79.79 0 0 1 1.15 0l1.246 1.306a.79.79 0 0 0 .736.242l1.78-.363a.79.79 0 0 1 .93.676l.192 1.796a.79.79 0 0 0 .487.647l1.644.757a.79.79 0 0 1 .432.99l-.757 1.644a.79.79 0 0 0 0 .808l.757 1.644a.79.79 0 0 1-.432.99l-1.644.757a.79.79 0 0 0-.487.647l-.192 1.796a.79.79 0 0 1-.93.676l-1.78-.363a.79.79 0 0 0-.736.242l-1.246 1.306a.79.79 0 0 1-1.15 0l-1.246-1.306a.79.79 0 0 0-.736-.242l-1.78.363a.79.79 0 0 1-.93-.676l-.192-1.796a.79.79 0 0 0-.487-.647L.414 9.475a.79.79 0 0 1-.432-.99l.757-1.644a.79.79 0 0 0 0-.808L.002 4.39a.79.79 0 0 1 .432-.99l1.644-.757a.79.79 0 0 0 .487-.647l.192-1.796a.79.79 0 0 1 .93-.676l1.78.363a.79.79 0 0 0 .736-.242L7.425.414z"/>
    <path fill="#fff" d="M11.3 5.3a.75.75 0 0 1 .05 1.05l-4 4.5a.75.75 0 0 1-1.08.02l-2-2a.75.75 0 0 1 1.06-1.06l1.45 1.45 3.47-3.91a.75.75 0 0 1 1.05-.05z"/>
  </svg>
);

// Discord Community Badge (Blurple emblem with star)
const DiscordCommunityBadge: React.FC<{ className?: string }> = ({ className = "w-3.5 h-3.5" }) => (
  <svg className={`${className} shrink-0 text-[#818cf8]`} viewBox="0 0 16 16" fill="currentColor">
    <title>Active Community</title>
    <path d="M7.425.414a.79.79 0 0 1 1.15 0l1.246 1.306a.79.79 0 0 0 .736.242l1.78-.363a.79.79 0 0 1 .93.676l.192 1.796a.79.79 0 0 0 .487.647l1.644.757a.79.79 0 0 1 .432.99l-.757 1.644a.79.79 0 0 0 0 .808l.757 1.644a.79.79 0 0 1-.432.99l-1.644.757a.79.79 0 0 0-.487.647l-.192 1.796a.79.79 0 0 1-.93.676l-1.78-.363a.79.79 0 0 0-.736.242l-1.246 1.306a.79.79 0 0 1-1.15 0l-1.246-1.306a.79.79 0 0 0-.736-.242l-1.78.363a.79.79 0 0 1-.93-.676l-.192-1.796a.79.79 0 0 0-.487-.647L.414 9.475a.79.79 0 0 1-.432-.99l.757-1.644a.79.79 0 0 0 0-.808L.002 4.39a.79.79 0 0 1 .432-.99l1.644-.757a.79.79 0 0 0 .487-.647l.192-1.796a.79.79 0 0 1 .93-.676l1.78.363a.79.79 0 0 0 .736-.242L7.425.414z"/>
    <path fill="#fff" d="M8 3.5l1.3 2.7 3 .4-2.2 2.1.5 3-2.6-1.4-2.6 1.4.5-3-2.2-2.1 3-.4z"/>
  </svg>
);

export const formatMemberCount = (count: number): string => {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M members`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K members`;
  }
  return `${count} members`;
};

interface FloatingServerCardProps {
  server: PublicBotServer;
  depth: UniverseDepth;
  accentColor?: string;
  className?: string;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
}

export const FloatingServerCard: React.FC<FloatingServerCardProps> = ({
  server,
  depth,
  accentColor,
  className = '',
  onMouseEnter,
  onMouseLeave,
}) => {
  const [imgError, setImgError] = useState(false);

  useEffect(() => {
    setImgError(false);
  }, [server.id, server.icon]);

  // Clean initials fallback
  const getInitials = (str: string) => {
    const cleaned = str.replace(/[^\p{L}\p{N}\s]/gu, '').trim();
    if (!cleaned) return 'SV';
    const words = cleaned.split(/\s+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return cleaned.slice(0, 2).toUpperCase();
  };

  const renderBadge = () => {
    if (server.isPartner) return <DiscordPartnerBadge />;
    if (server.isVerified) return <DiscordVerifiedBadge />;
    return <DiscordCommunityBadge />;
  };

  // Depth-specific styling strictly following 3-level depth hierarchy:
  // Far: opacity 0.20, scale 0.75, blur 2px
  // Middle: opacity 0.55, scale 0.90, blur 0px
  // Near: opacity 0.95, scale 1.05, blur 0px
  const depthStyles: Record<UniverseDepth, string> = {
    near: 'scale-100 sm:scale-105 opacity-95 z-20 shadow-[0_10px_36px_rgba(0,0,0,0.7)] border-white/20',
    mid: 'scale-[0.88] sm:scale-[0.90] opacity-55 hover:opacity-90 z-10 shadow-[0_4px_20px_rgba(0,0,0,0.45)] border-white/10',
    far: 'scale-[0.72] sm:scale-[0.75] opacity-20 hover:opacity-75 z-0 blur-[2px] hover:blur-none shadow-[0_2px_12px_rgba(0,0,0,0.3)] border-white/5',
  };

  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`group relative flex items-center gap-2.5 px-3 py-2 rounded-2xl border select-none transition-all duration-300 backdrop-blur-md cursor-default ${depthStyles[depth]} ${className}`}
      style={{
        backgroundColor: 'rgba(11, 15, 25, 0.82)',
        borderColor: accentColor ? `${accentColor}33` : 'rgba(255, 255, 255, 0.12)',
        boxShadow: accentColor ? `0 0 20px -5px ${accentColor}26, 0 8px 30px rgba(0,0,0,0.5)` : undefined,
      }}
    >
      {/* Subtle hover neon halo */}
      <div 
        className="pointer-events-none absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10"
        style={{
          background: accentColor 
            ? `radial-gradient(circle at center, ${accentColor}18 0%, transparent 70%)` 
            : 'radial-gradient(circle at center, rgba(56,189,248,0.12) 0%, transparent 70%)',
          boxShadow: accentColor ? `0 0 24px 2px ${accentColor}40` : '0 0 20px 2px rgba(56,189,248,0.25)'
        }}
      />

      {/* Server Icon with Online Ring */}
      <div className="relative shrink-0">
        {server.icon && !imgError ? (
          <Image
            src={server.icon}
            alt={server.name}
            width={36}
            height={36}
            onError={() => setImgError(true)}
            className="w-8 h-8 sm:w-9 sm:h-9 rounded-full object-cover ring-1 ring-white/15 group-hover:scale-105 transition-transform duration-200"
            unoptimized
          />
        ) : (
          <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full shrink-0 bg-gradient-to-br from-[#5865F2]/80 to-purple-800/80 border border-white/15 flex items-center justify-center text-[10px] sm:text-[11px] font-bold text-white group-hover:scale-105 transition-transform duration-200 shadow-inner">
            {getInitials(server.name)}
          </div>
        )}
      </div>

      {/* Server Info */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 leading-tight">
          <span
            className="text-xs font-bold text-white truncate max-w-[95px] sm:max-w-[125px] group-hover:text-slate-100 transition-colors drop-shadow-sm"
            title={server.name}
          >
            {server.name}
          </span>
          {renderBadge()}
        </div>

        <div className="flex items-center gap-1.5 mt-0.5 text-[10px] sm:text-[11px] leading-tight text-slate-400">
          <span className="font-medium tabular-nums">{formatMemberCount(server.memberCount)}</span>
          <span className="text-slate-600">•</span>
          <span className="flex items-center gap-1 text-emerald-400 font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_#34d399]" />
            Live
          </span>
        </div>
      </div>
    </div>
  );
};
