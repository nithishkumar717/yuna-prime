"use client";

import React, { useState, useEffect } from 'react';
import { BrandLogo } from './BrandLogo';
import { LanguageCode, getTranslation } from '@/lib/translations';
import { 
  ShieldCheck, 
  Settings,
  Users,
  ChevronRight
} from 'lucide-react';
import { PublicBotServer } from './universe/types';
import { LiveServerUniverse } from './universe/LiveServerUniverse';

interface HeroSectionProps {
  onOpenLogin: () => void;
  onOpenInvite: () => void;
  onExploreFeatures: () => void;
  onOpenShowcase?: () => void;
  currentLang?: LanguageCode;
  user?: any;
  onOpenDashboard?: () => void;
}

const INITIAL_REAL_SERVERS: PublicBotServer[] = [
  {
    id: "1242075132261040260",
    name: "TAMILAGA GAMING KALAGAM",
    icon: "https://cdn.discordapp.com/icons/1242075132261040260/736b0929810e3d36ffb6be5f9405ec65.png?size=1024",
    memberCount: 1095,
    isPartner: true,
  },
  {
    id: "1381909147389399081",
    name: "𝑮𝑨𝑴𝑬𝑹 𝑺𝑼𝑫𝑯𝑨-𝒀𝑻",
    icon: "https://cdn.discordapp.com/icons/1381909147389399081/eaa524d4cb2e43a0f4b79a771d083a19.png?size=1024",
    memberCount: 457,
    isVerified: true,
  },
  {
    id: "1423165649722540138",
    name: "YELLOW⚓FLASH's server",
    icon: "https://cdn.discordapp.com/icons/1423165649722540138/10f954f356dbd0ca7e0eba439ef560d6.png?size=1024",
    memberCount: 31,
    isCommunity: true,
  },
  {
    id: "1396112043907481640",
    name: "L4NCY",
    icon: "https://cdn.discordapp.com/icons/1396112043907481640/929358af26e3236d406ff2760316626d.png?size=1024",
    memberCount: 247,
    isPartner: true,
  },
  {
    id: "1195253356705361931",
    name: "R E S P A W N   X",
    icon: "https://cdn.discordapp.com/icons/1195253356705361931/a20bf78c3c08b146bd94f3737624a7fb.png?size=1024",
    memberCount: 237,
    isVerified: true,
  },
  {
    id: "1525481611116806185",
    name: "❀ YUNΛ SUPPORT SERVER",
    icon: "https://cdn.discordapp.com/icons/1525481611116806185/b1fd7fea5288466c653069082910d2ec.png?size=1024",
    memberCount: 27,
    isPartner: true,
  },
  {
    id: "1517800166483165255",
    name: "NSG",
    icon: "https://cdn.discordapp.com/icons/1517800166483165255/9776344a4ee05609f0546aa1f7cb8320.png?size=1024",
    memberCount: 38,
    isCommunity: true,
  },
  {
    id: "1530865368229220373",
    name: "𝐂𝐇𝐈𝐋𝐋 𝐒𝐄𝐑𝐕𝐄𝐑 🦅",
    icon: "https://cdn.discordapp.com/icons/1530865368229220373/627d59164220ae45951ed5cb4abd8d2b.png?size=1024",
    memberCount: 33,
    isCommunity: true,
  },
  {
    id: "1228678147449290893",
    name: "MR RIO YT",
    icon: "https://cdn.discordapp.com/icons/1228678147449290893/de49e1f387a1906ee9576964fbc0baa1.png?size=1024",
    memberCount: 128,
    isVerified: true,
  },
  {
    id: "1489865525193609258",
    name: "AJU  LIVE",
    icon: "https://cdn.discordapp.com/icons/1489865525193609258/f301001ca130fd2ebcee187aa357aaea.png?size=1024",
    memberCount: 51,
    isCommunity: true,
  },
  {
    id: "1292783081811349525",
    name: "𝐂𝐎𝐍𝐐𝐔𝐄𝐑𝐎𝐑𝐒❧!!",
    icon: "https://cdn.discordapp.com/icons/1292783081811349525/4351e794ef98344aa7d75e941a3b1095.png?size=1024",
    memberCount: 1252,
    isPartner: true,
  },
  {
    id: "1243409741703811082",
    name: "WARMAC UCHIHA",
    icon: "https://cdn.discordapp.com/icons/1243409741703811082/2ad87af70a3f5f786906a715080cf940.png?size=1024",
    memberCount: 70,
    isCommunity: true,
  },
];

// Smooth count-up animation hook
function useCountUp(target: number, duration: number = 1800): number {
  const [display, setDisplay] = React.useState(0);
  const prevTarget = React.useRef(0);

  React.useEffect(() => {
    if (target <= 0) { setDisplay(0); return; }
    const start = prevTarget.current;
    prevTarget.current = target;
    const diff = target - start;
    if (diff === 0) return;
    const startTime = performance.now();

    let raf: number;
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(start + diff * eased));
      if (progress < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return display;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onOpenLogin,
  onOpenInvite,
  onExploreFeatures,
  currentLang = 'EN',
  user,
  onOpenDashboard
}) => {
  const [servers, setServers] = useState<PublicBotServer[]>(INITIAL_REAL_SERVERS);
  const [guildCount, setGuildCount] = useState<number>(21);
  const [globalUsers, setGlobalUsers] = useState<number>(4155);

  const animatedGuildCount = useCountUp(guildCount);
  const animatedUserCount = useCountUp(globalUsers);

  // Sync real-time statistics if bot API is reachable
  useEffect(() => {
    let isMounted = true;

    const loadRealtimeData = async () => {
      try {
        const res = await fetch('/api/v1/bot/status').catch(() => null);
        if (res && res.ok) {
          const data = await res.json();
          if (!isMounted) return;
          if (data.guild_count) setGuildCount(data.guild_count);
          if (data.user_count) setGlobalUsers(data.user_count);
        }
      } catch (err) {
        // Fallback already initialized
      }
    };

    loadRealtimeData();
    const interval = setInterval(loadRealtimeData, 30000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <section className="relative min-h-[105vh] lg:min-h-[112vh] pt-32 pb-24 md:pt-44 md:pb-36 overflow-hidden flex flex-col items-center justify-center text-center">
      {/* Background Ambience Neon Glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[550px] bg-gradient-to-b from-indigo-600/20 via-purple-600/10 to-transparent blur-[140px] rounded-full pointer-events-none -z-20" />
      <div className="absolute top-20 right-1/4 w-[400px] h-[350px] bg-rose-500/10 blur-[110px] rounded-full pointer-events-none -z-20" />
      <div className="absolute bottom-20 left-1/4 w-[350px] h-[300px] bg-sky-500/10 blur-[120px] rounded-full pointer-events-none -z-20" />
      
      {/* Background subtle mesh grid */}
      <div className="absolute inset-0 bg-grid-pattern opacity-25 pointer-events-none -z-20" />

      {/* FLOATING SERVER UNIVERSE */}
      <LiveServerUniverse servers={servers} />

      {/* CENTRAL HERO CONTENT */}
      <div className="relative z-20 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center">
        
        {/* Subtle radial backdrop darkening for readability */}
        <div className="pointer-events-none absolute -inset-10 bg-gradient-to-b from-[#080b11]/0 via-[#080b11]/70 to-[#080b11]/0 blur-2xl -z-10 rounded-3xl" />

        {/* Large Central Glowing Crest Emblem */}
        <div className="relative mb-6 animate-float flex flex-col items-center">
          <BrandLogo size="2xl" showText={false} animated={true} />
        </div>

        {/* Main Brand Title */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black tracking-tight text-white font-sans drop-shadow-[0_4px_24px_rgba(0,0,0,0.8)]">
          {botName}
        </h1>

        {/* Glowing Subtitle / Slogan */}
        <p className="mt-3 text-lg sm:text-xl font-bold bg-gradient-to-r from-red-400 via-rose-400 to-indigo-400 bg-clip-text text-transparent tracking-wide max-w-2xl drop-shadow-sm">
          {getTranslation(currentLang, 'hero_title')}
        </p>

        {/* Supporting Copy */}
        <p className="mt-4 text-sm sm:text-base text-slate-300 max-w-xl mx-auto leading-relaxed font-normal">
          {getTranslation(currentLang, 'hero_subtitle')}
        </p>

        {/* Dual Primary Call-to-Actions */}
        <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3.5 w-full sm:w-auto relative z-30">
          {/* Add to Discord Button */}
          <button
            onClick={onOpenInvite}
            className="w-full sm:w-auto flex items-center justify-center gap-2.5 px-6 py-3 bg-[#1e202b]/90 hover:bg-[#282a39] border border-slate-700/70 hover:border-slate-500 active:scale-[0.98] text-white text-sm font-bold rounded-xl shadow-lg shadow-black/50 transition-all duration-200 cursor-pointer group"
          >
            <svg 
              className="w-4 h-4 fill-current transition-transform group-hover:scale-110" 
              viewBox="0 0 24 24"
            >
              <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
            </svg>
            <span>{getTranslation(currentLang, 'add_to_discord')}</span>
            <ChevronRight className="w-3.5 h-3.5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
          </button>

          {/* Manage Servers / Open Dashboard Button */}
          {user ? (
            <button
              onClick={onOpenDashboard || onOpenLogin}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-[#5865F2] hover:bg-[#4752C4] active:scale-[0.98] text-white text-sm font-bold rounded-xl shadow-lg shadow-[#5865F2]/30 transition-all duration-200 cursor-pointer group"
            >
              <Settings className="w-4 h-4 text-white group-hover:rotate-45 transition-transform duration-300" />
              <span>Manage Servers</span>
              <ChevronRight className="w-3.5 h-3.5 text-white/80 group-hover:translate-x-0.5 transition-transform" />
            </button>
          ) : (
            <button
              onClick={onOpenLogin}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-[#5865F2] hover:bg-[#4752C4] active:scale-[0.98] text-white text-sm font-bold rounded-xl shadow-lg shadow-[#5865F2]/30 transition-all duration-200 cursor-pointer group"
            >
              <ShieldCheck className="w-4 h-4 text-white group-hover:scale-110 transition-transform" />
              <span>{getTranslation(currentLang, 'open_dashboard')}</span>
              <ChevronRight className="w-3.5 h-3.5 text-white/80 group-hover:translate-x-0.5 transition-transform" />
            </button>
          )}
        </div>

        {/* Live Statistics Counter Badges */}
        <div className="mt-10 flex flex-wrap items-center justify-center gap-3 sm:gap-6 text-xs sm:text-sm font-medium text-slate-300">
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#0e121d]/80 border border-white/10 backdrop-blur-md shadow-sm">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
            <span>Used by <span className="text-white font-bold tabular-nums">{animatedGuildCount > 0 ? animatedGuildCount.toLocaleString() : '---'}</span> servers</span>
          </div>

          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#0e121d]/80 border border-white/10 backdrop-blur-md shadow-sm">
            <Users className="w-3.5 h-3.5 text-rose-400" />
            <span><span className="text-white font-bold tabular-nums">{animatedUserCount > 0 ? animatedUserCount.toLocaleString() : '---'}</span> global users</span>
          </div>
        </div>

        {/* Subtle Tagline Divider */}
        <div className="mt-12 flex items-center gap-3 text-[10px] font-semibold tracking-widest text-slate-500 uppercase select-none">
          <span className="w-8 h-[1px] bg-gradient-to-r from-transparent to-slate-700" />
          <span>Powering Communities Worldwide</span>
          <span className="w-8 h-[1px] bg-gradient-to-l from-transparent to-slate-700" />
        </div>

        {/* Animated Scroll to Explore Indicator */}
        <div 
          className="mt-10 flex flex-col items-center gap-1.5 text-slate-400 text-[11px] font-medium tracking-wide hover:text-red-400 transition-colors cursor-pointer group animate-bounce" 
          onClick={onExploreFeatures}
        >
          <span className="text-slate-400 group-hover:text-red-400 transition-colors">Scroll to explore</span>
          <div className="w-4 h-6.5 rounded-full border-[1.5px] border-red-500/40 group-hover:border-red-500 flex items-start justify-center p-0.5 transition-colors shadow-sm">
            <div className="w-0.5 h-1.5 bg-red-400 rounded-full animate-pulse mt-0.5" />
          </div>
        </div>

      </div>
    </section>
  );
};
