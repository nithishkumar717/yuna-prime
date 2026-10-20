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
 * ║   github   ──  https://github.com/nithishkumar717/yuna-bot      ║
 * ║                                                                  ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn, signOut, useSession } from "next-auth/react";
import { LanguageCode } from "@/lib/translations";
import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { FeaturesGrid } from "@/components/landing/FeaturesGrid";
import { HeroShowcase } from "@/components/landing/HeroShowcase";
import { CommandVsWebSection } from "@/components/landing/CommandVsWebSection";
import { SecuritySection } from "@/components/landing/SecuritySection";
import { WorkflowPreviewSection } from "@/components/landing/WorkflowPreviewSection";
import { PrimeSection } from "@/components/landing/PrimeSection";
import { WhyYunaSection } from "@/components/landing/WhyYunaSection";
import { CtaSection } from "@/components/landing/CtaSection";
import { Footer } from "@/components/landing/Footer";
import { CommandsView } from "@/components/landing/CommandsView";
import { DocsView } from "@/components/landing/DocsView";
import { SupportView } from "@/components/landing/SupportView";
import { PremiumView } from "@/components/landing/PremiumView";
import { LegalModal } from "@/components/landing/LegalModal";

export default function LandingPage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [landingTab, setLandingTab] = useState<'home' | 'commands' | 'docs' | 'support' | 'premium'>('home');
  const [currentLang, setCurrentLang] = useState<LanguageCode>('EN');
  const [legalModalType, setLegalModalType] = useState<'terms' | 'privacy' | 'shipping' | 'refund' | 'scta' | 'sdta' | null>(null);

  const inviteUrl = "https://discord.com/oauth2/authorize?client_id=1525728642913669260&permissions=8&integration_type=0&scope=bot+applications.commands";

  const handleOpenLogin = () => {
    signIn('discord', { callbackUrl: '/dashboard' });
  };

  const handleOpenDashboard = () => {
    router.push('/dashboard');
  };

  const handleOpenInvite = () => {
    window.open(inviteUrl, '_blank');
  };

  const handleLogout = () => {
    signOut({ callbackUrl: '/' });
  };

  const scrollToSection = (sectionId: string) => {
    if (landingTab !== 'home') {
      setLandingTab('home');
      setTimeout(() => {
        const el = document.getElementById(sectionId);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth' });
        }
      }, 100);
    } else {
      const el = document.getElementById(sectionId);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth' });
      }
    }
  };

  return (
    <div className="min-h-screen bg-[#06080d] text-slate-200 selection:bg-red-500/30 font-sans flex flex-col justify-between overflow-x-hidden">
      {/* Top Fixed Navbar */}
      <Navbar 
        currentTab={landingTab}
        onSelectTab={(tab) => {
          setLandingTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onOpenLogin={handleOpenLogin}
        onOpenDashboard={handleOpenDashboard}
        onOpenInvite={handleOpenInvite}
        currentLang={currentLang}
        onSelectLang={setCurrentLang}
        user={session?.user}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {landingTab === 'home' && (
          <>
            {/* 1. Hero Section with Live Server Universe & Counters */}
            <HeroSection 
              currentLang={currentLang}
              user={session?.user}
              onOpenLogin={handleOpenLogin}
              onOpenDashboard={handleOpenDashboard}
              onOpenInvite={handleOpenInvite}
              onExploreFeatures={() => scrollToSection('features')}
              onOpenShowcase={() => scrollToSection('dashboard-showcase')}
            />

            {/* 2. Core Capabilities Bento Grid with Infinite Marquee */}
            <FeaturesGrid 
              onSelectFeatureTab={() => scrollToSection('dashboard-showcase')}
            />

            {/* 3. Interactive Web Control Center Mockup Showcase */}
            <HeroShowcase 
              onOpenDashboard={session?.user ? handleOpenDashboard : handleOpenLogin}
            />

            {/* 4. Comparison Section: Slash Commands vs Web Platform */}
            <CommandVsWebSection />

            {/* 5. Defense In Depth: Military-Grade Security Architecture */}
            <SecuritySection 
              onOpenDashboard={session?.user ? handleOpenDashboard : handleOpenLogin}
            />

            {/* 6. Automate Everything Simulation Modules */}
            <WorkflowPreviewSection 
              onOpenDashboard={session?.user ? handleOpenDashboard : handleOpenLogin}
            />

            {/* 7. Prime / Ultimate Tier Bento Grid */}
            <PrimeSection 
              onOpenDashboard={session?.user ? handleOpenDashboard : handleOpenLogin}
            />

            {/* 8. Why Choose Advantage Showcase */}
            <WhyYunaSection 
              onOpenDashboard={session?.user ? handleOpenDashboard : handleOpenLogin}
              onExploreCommands={() => {
                setLandingTab('commands');
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            />

            {/* 9. Final Call To Action & Metrics Counters */}
            <CtaSection 
              onOpenLogin={handleOpenLogin}
              onOpenInvite={handleOpenInvite}
            />
          </>
        )}

        {/* Commands Tab View */}
        {landingTab === 'commands' && (
          <CommandsView onOpenLogin={handleOpenLogin} />
        )}

        {/* Docs Tab View */}
        {landingTab === 'docs' && (
          <DocsView 
            onOpenLogin={handleOpenLogin} 
            onOpenInvite={handleOpenInvite} 
          />
        )}

        {/* Support Tab View */}
        {landingTab === 'support' && (
          <SupportView 
            onOpenLogin={handleOpenLogin} 
            onOpenInvite={handleOpenInvite} 
          />
        )}

        {/* Premium Tab View */}
        {landingTab === 'premium' && (
          <PremiumView 
            onOpenLogin={handleOpenLogin} 
            onOpenInvite={handleOpenInvite} 
          />
        )}
      </main>

      {/* Luxury Dark Footer */}
      <Footer 
        onOpenLogin={handleOpenLogin}
        onOpenInvite={handleOpenInvite}
        onSelectTab={(tab) => {
          setLandingTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        onOpenLegal={(type) => setLegalModalType(type)}
      />

      {/* Legal Dialog Modal */}
      <LegalModal 
        type={legalModalType} 
        onClose={() => setLegalModalType(null)} 
      />
    </div>
  );
}
