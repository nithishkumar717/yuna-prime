"use client";

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { BrandLogo } from './BrandLogo';
import { LANGUAGES, LanguageCode, getTranslation } from '@/lib/translations';
import { 
  ShieldCheck, 
  Sparkles, 
  Menu, 
  X, 
  ChevronDown, 
  LayoutDashboard, 
  Terminal, 
  BookOpen, 
  HelpCircle, 
  Crown, 
  LogOut 
} from 'lucide-react';

interface NavbarProps {
  currentTab: 'home' | 'commands' | 'docs' | 'support' | 'premium';
  onSelectTab: (tab: 'home' | 'commands' | 'docs' | 'support' | 'premium') => void;
  onOpenLogin: () => void;
  onOpenDashboard?: () => void;
  onOpenInvite: () => void;
  currentLang?: LanguageCode;
  onSelectLang?: (lang: LanguageCode) => void;
  user?: {
    name?: string | null;
    email?: string | null;
    image?: string | null;
  } | null;
  onLogout?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ 
  currentTab, 
  onSelectTab,
  onOpenLogin, 
  onOpenDashboard,
  onOpenInvite,
  currentLang = 'EN',
  onSelectLang,
  user,
  onLogout,
}) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const langRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (langRef.current && !langRef.current.contains(event.target as Node)) {
        setLangMenuOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeFlag = LANGUAGES.find(l => l.code === currentLang)?.flag || '🇺🇸';

  return (
    <header 
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        isScrolled 
          ? 'bg-[#06080d]/95 backdrop-blur-xl border-b border-red-950/40 shadow-xl shadow-black/80 py-3.5' 
          : 'bg-transparent border-b border-transparent py-4 sm:py-5'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        
        {/* Left: Brand Logo */}
        <button 
          onClick={() => onSelectTab('home')}
          className="flex items-center gap-2 group focus:outline-none cursor-pointer"
        >
          <BrandLogo size="md" />
          <span className="font-extrabold text-white text-lg tracking-wider hidden sm:inline-block">
            {process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA"}
          </span>
        </button>

        {/* Center: Interactive Nav Menu */}
        <nav className="hidden md:flex items-center gap-1 bg-[#10121a]/80 border border-slate-800/80 rounded-full px-3 py-1.5 shadow-lg backdrop-blur-md">
          {/* Home Tab */}
          <button
            onClick={() => onSelectTab('home')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 cursor-pointer ${
              currentTab === 'home'
                ? 'bg-red-600 text-white shadow-md shadow-red-600/30'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            {getTranslation(currentLang, 'nav_home')}
          </button>

          {/* Commands Tab */}
          <button
            onClick={() => onSelectTab('commands')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 flex items-center gap-1.5 cursor-pointer ${
              currentTab === 'commands'
                ? 'bg-red-600 text-white shadow-md shadow-red-600/30'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Terminal className="w-3.5 h-3.5 text-red-400" />
            <span>{getTranslation(currentLang, 'nav_commands')}</span>
          </button>

          {/* Docs Tab */}
          <button
            onClick={() => onSelectTab('docs')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 flex items-center gap-1.5 cursor-pointer ${
              currentTab === 'docs'
                ? 'bg-red-600 text-white shadow-md shadow-red-600/30'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-indigo-400" />
            <span>{getTranslation(currentLang, 'nav_docs')}</span>
          </button>

          {/* Support Tab */}
          <button
            onClick={() => onSelectTab('support')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 flex items-center gap-1.5 cursor-pointer ${
              currentTab === 'support'
                ? 'bg-red-600 text-white shadow-md shadow-red-600/30'
                : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <HelpCircle className="w-3.5 h-3.5 text-cyan-400" />
            <span>{getTranslation(currentLang, 'nav_support')}</span>
          </button>

          {/* Premium Tab */}
          <button
            onClick={() => onSelectTab('premium')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-150 flex items-center gap-1.5 cursor-pointer ${
              currentTab === 'premium'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-md shadow-amber-500/10'
                : 'text-amber-400/90 hover:text-amber-300 hover:bg-amber-500/10'
            }`}
          >
            <Crown className="w-3.5 h-3.5 text-amber-400" />
            <span>{getTranslation(currentLang, 'nav_premium')}</span>
          </button>
        </nav>

        {/* Right: Language Selector & Login / User Profile */}
        <div className="flex items-center gap-4 sm:gap-6">
          {/* Language Selector Dropdown */}
          <div className="relative hidden xs:block" ref={langRef}>
            <button
              type="button"
              onClick={() => setLangMenuOpen(!langMenuOpen)}
              className="flex items-center gap-1.5 text-sm font-bold text-white hover:text-slate-200 transition-colors cursor-pointer select-none focus:outline-none py-1"
            >
              <span className="text-base leading-none">{activeFlag}</span>
              <span className="font-bold tracking-wide">{currentLang}</span>
              <ChevronDown className={`w-3.5 h-3.5 text-white/90 transition-transform duration-200 ${langMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {langMenuOpen && (
              <div className="absolute right-0 mt-2 w-44 bg-[#12141c] border border-slate-800 rounded-xl shadow-2xl p-1 z-50 animate-in fade-in zoom-in-95 duration-150">
                {LANGUAGES.map(l => (
                  <button
                    key={l.code}
                    type="button"
                    onClick={() => {
                      if (onSelectLang) onSelectLang(l.code);
                      setLangMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg text-left transition-colors cursor-pointer ${
                      currentLang === l.code ? 'bg-red-500/20 text-red-400 font-bold' : 'text-slate-300 hover:bg-slate-800/80 hover:text-white'
                    }`}
                  >
                    <span>{l.flag}</span>
                    <span>{l.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Auth Section */}
          {user ? (
            <div className="relative" ref={userMenuRef}>
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 focus:outline-none cursor-pointer group py-1"
                aria-label="User profile menu"
              >
                {user.image ? (
                  <Image 
                    src={user.image} 
                    alt={user.name || "User"} 
                    width={32}
                    height={32}
                    className="w-8 h-8 rounded-full ring-2 ring-red-500/80 group-hover:ring-red-400 object-cover" 
                    unoptimized
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full ring-2 ring-red-500/80 bg-red-600/30 flex items-center justify-center text-xs font-bold text-white">
                    {(user.name || "U").slice(0, 2).toUpperCase()}
                  </div>
                )}
                <span className="text-xs font-bold text-white hidden sm:inline max-w-[100px] truncate">{user.name}</span>
                <ChevronDown className={`w-3.5 h-3.5 text-white/90 group-hover:text-white transition-transform duration-200 ${userMenuOpen ? 'rotate-180' : ''}`} />
              </button>

              {/* User Dropdown */}
              {userMenuOpen && (
                <div className="absolute right-0 mt-2.5 w-56 bg-[#11131c] border border-slate-800 rounded-2xl shadow-2xl shadow-black/80 p-2 z-50 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
                  <div className="px-3 py-2.5 rounded-xl bg-slate-900/70 border border-slate-800/60 flex items-center gap-2.5">
                    {user.image && (
                      <Image src={user.image} alt={user.name || "User"} width={28} height={28} className="w-7 h-7 rounded-full" unoptimized />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-bold text-white truncate">{user.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">{user.email || 'Authenticated'}</div>
                    </div>
                  </div>

                  <div className="my-1.5 border-t border-slate-800/80" />

                  <div className="space-y-0.5">
                    <Link
                      href="/dashboard"
                      onClick={() => setUserMenuOpen(false)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-200 hover:text-white hover:bg-slate-800/70 rounded-xl transition-colors cursor-pointer text-left"
                    >
                      <LayoutDashboard className="w-4 h-4 text-red-500" />
                      <span>Open Dashboard</span>
                    </Link>
                  </div>

                  {onLogout && (
                    <>
                      <div className="my-1.5 border-t border-slate-800/80" />
                      <button
                        onClick={() => {
                          setUserMenuOpen(false);
                          onLogout();
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-xl transition-colors cursor-pointer text-left"
                      >
                        <LogOut className="w-4 h-4 text-red-400" />
                        <span>Log Out</span>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={onOpenLogin}
              className="flex items-center gap-2 px-3.5 sm:px-4 py-1.5 sm:py-2 rounded-full text-xs font-bold text-white bg-[#5865F2]/90 hover:bg-[#5865F2] border border-[#5865F2]/50 hover:border-[#5865F2] shadow-md shadow-[#5865F2]/25 hover:shadow-[#5865F2]/45 active:scale-[0.98] transition-all duration-200 cursor-pointer group"
            >
              <svg 
                className="w-3.5 h-3.5 fill-current transition-transform group-hover:scale-110" 
                viewBox="0 0 24 24"
              >
                <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994.021-.041.001-.09-.041-.106a13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.929 1.793 8.18 1.793 12.061 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.894.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.028zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
              </svg>
              <span>Login</span>
            </button>
          )}

          {/* Mobile Hamburger Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-slate-300 hover:text-white bg-[#14161f] border border-slate-800 rounded-xl cursor-pointer"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#0a0c12]/98 border-b border-slate-800 px-4 py-4 space-y-2.5 animate-in slide-in-from-top-2 duration-200">
          <button
            onClick={() => {
              onSelectTab('home');
              setMobileMenuOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold ${currentTab === 'home' ? 'bg-red-500/20 text-red-400' : 'text-slate-300'}`}
          >
            {getTranslation(currentLang, 'nav_home')}
          </button>
          <button
            onClick={() => {
              onSelectTab('commands');
              setMobileMenuOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold ${currentTab === 'commands' ? 'bg-red-500/20 text-red-400' : 'text-slate-300'}`}
          >
            {getTranslation(currentLang, 'nav_commands')}
          </button>
          <button
            onClick={() => {
              onSelectTab('docs');
              setMobileMenuOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold ${currentTab === 'docs' ? 'bg-red-500/20 text-red-400' : 'text-slate-300'}`}
          >
            {getTranslation(currentLang, 'nav_docs')}
          </button>
          <button
            onClick={() => {
              onSelectTab('support');
              setMobileMenuOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold ${currentTab === 'support' ? 'bg-red-500/20 text-red-400' : 'text-slate-300'}`}
          >
            {getTranslation(currentLang, 'nav_support')}
          </button>
          <button
            onClick={() => {
              onSelectTab('premium');
              setMobileMenuOpen(false);
            }}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs font-bold ${currentTab === 'premium' ? 'bg-amber-500/20 text-amber-300' : 'text-amber-400'}`}
          >
            👑 {getTranslation(currentLang, 'nav_premium')}
          </button>

          <div className="pt-2 border-t border-slate-800 flex items-center gap-2">
            <button
              onClick={() => {
                setMobileMenuOpen(false);
                onOpenInvite();
              }}
              className="flex-1 py-2.5 bg-gradient-to-r from-red-600 to-rose-600 text-white font-bold rounded-xl text-xs text-center"
            >
              {getTranslation(currentLang, 'add_to_discord')}
            </button>
            <button
              onClick={() => {
                setMobileMenuOpen(false);
                if (user && onOpenDashboard) onOpenDashboard();
                else onOpenLogin();
              }}
              className="flex-1 py-2.5 bg-[#5865F2] text-white font-bold rounded-xl text-xs text-center"
            >
              {user ? 'Dashboard' : 'Login'}
            </button>
          </div>
        </div>
      )}
    </header>
  );
};
