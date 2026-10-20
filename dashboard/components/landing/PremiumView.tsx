"use client";

import React, { useState } from 'react';
import { 
  Crown, 
  Check, 
  Sparkles, 
  Zap, 
  ShieldCheck, 
  Lock, 
  Layers, 
  Radio, 
  ArrowRight, 
  Shield, 
  Award, 
  Gift 
} from 'lucide-react';

interface PremiumViewProps {
  onOpenLogin: () => void;
  onOpenInvite: () => void;
  onOpenRedeemModal?: () => void;
  onTriggerToast?: (type: 'success' | 'warning' | 'info' | 'error', title: string, message?: string) => void;
}

export const PremiumView: React.FC<PremiumViewProps> = ({ 
  onOpenLogin, 
  onOpenInvite,
  onOpenRedeemModal,
  onTriggerToast 
}) => {
  const [currency, setCurrency] = useState<'INR' | 'USD'>('INR');
  const [, setActivatedPlan] = useState<string | null>('Ultra Pro');
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  const plans = [
    {
      id: 'plus',
      name: 'Plus Plan',
      badge: 'Standard',
      badgeColor: 'bg-slate-800 text-slate-300 border-slate-700',
      price: currency === 'INR' ? '₹299' : '$3.99',
      period: '1 Month',
      features: [
        { text: '5x Higher Limits (Custom role, Autoresponder, Autoreact and Active Giveaways)', highlight: true },
        { text: 'Limit System (Advanced security)', icon: Shield },
        { text: 'Anti Token Spam (Automod)', icon: Zap },
        { text: 'Secure Channel Protection', icon: Lock },
        { text: 'Anti Betray System', icon: ShieldCheck },
        { text: 'Auto Emergency Mode', icon: Radio },
        { text: '24/7 Support', icon: Check }
      ],
      buttonText: 'Activate Plus Plan',
      buttonBg: 'bg-slate-800 hover:bg-slate-700 text-white font-bold'
    },
    {
      id: 'pro',
      name: 'Pro Plan',
      badge: 'Best Value',
      badgeColor: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
      price: currency === 'INR' ? '₹499' : '$6.49',
      period: '1 Month',
      popular: true,
      features: [
        { text: '5x Higher Limits (Custom role, Autoresponder, Autoreact and Active Giveaways)', highlight: true },
        { text: 'Full Customization (Avatar, Banner, About-me and Nickname)', highlight: true, icon: Sparkles },
        { text: 'Limit System (Advanced security)', icon: Shield },
        { text: 'Anti Token Spam (Automod)', icon: Zap },
        { text: 'Secure Channel Protection', icon: Lock },
        { text: 'Anti Betray System', icon: ShieldCheck },
        { text: 'Auto Emergency Mode', icon: Radio },
        { text: 'Multiple moderation & admin role instances with custom permissions', icon: Layers },
        { text: 'No Prefix (1x User)', icon: Award },
        { text: '24/7 Support', icon: Check }
      ],
      buttonText: 'Activate Pro Plan',
      buttonBg: 'bg-[#f59e0b] hover:bg-[#d97706] text-black font-black'
    },
    {
      id: 'ultra',
      name: 'Ultra Pro',
      badge: 'Maximum Defense',
      badgeColor: 'bg-red-500/20 text-red-400 border-red-500/40',
      price: currency === 'INR' ? '₹749' : '$9.99',
      period: '1 Month',
      features: [
        { text: '5x Higher Limits (Custom role, Autoresponder, Autoreact and Active Giveaways)', highlight: true },
        { text: 'Full Customization (Avatar, Banner, About-me and Nickname)', highlight: true, icon: Sparkles },
        { text: 'Limit System (Advanced security)', icon: Shield },
        { text: 'Anti Token Spam (Automod)', icon: Zap },
        { text: 'Secure Channel Protection', icon: Lock },
        { text: 'Anti Betray System', icon: ShieldCheck },
        { text: 'Auto Emergency Mode', icon: Radio },
        { text: 'Multiple moderation & admin role instances with custom permissions', icon: Layers },
        { text: 'No Prefix (1x User)', icon: Award },
        { text: 'Auto Member Recovery (Server Insurance Plan)', highlight: true, icon: ShieldCheck },
        { text: '24/7 Priority Support', icon: Check }
      ],
      buttonText: 'Activate Ultra Pro (All Unlocked)',
      buttonBg: 'bg-gradient-to-r from-amber-500 via-orange-500 to-amber-600 hover:from-amber-400 hover:to-orange-400 text-black font-black'
    }
  ];

  const addons = [
    {
      id: 'addon-insurance',
      title: 'Server Insurance',
      badge: 'Protection',
      price: currency === 'INR' ? '₹299' : '$3.99',
      period: '1 Month',
      desc: 'Auto Member Recovery protects your Discord server by automatically recovering all members if your server gets nuked.',
      extra: 'Instead of manually recovering members one by one, your bot will restore your server member list automatically.',
      buttonText: 'Activate Insurance',
    },
    {
      id: 'addon-noprefix',
      title: 'No Prefix',
      badge: 'Smoothness',
      price: currency === 'INR' ? '₹99' : '$1.49',
      period: '1 Month',
      desc: `Allow you to use ${botName} commands without prefix, making your experience even faster and smoother.`,
      extra: 'With No Prefix, every command becomes effortless, saving time while managing your server faster.',
      buttonText: 'Activate No-Prefix',
    },
    {
      id: 'addon-vanity',
      title: 'Vanity Protection Only',
      badge: 'Protect',
      price: currency === 'INR' ? '₹265' : '$3.49',
      period: '1 Month Only',
      desc: `Protect your Discord Server Vanity (custom server invite link) with ${botName}. Only the owner can change it; others will be banned instantly.`,
      extra: 'Your original vanity will be restored within a microsecond. Keep your brand identity safe with instant recovery.',
      buttonText: 'Activate Vanity Lock',
    }
  ];

  const handleActivatePlan = (planName: string) => {
    setActivatedPlan(planName);
    if (onTriggerToast) {
      onTriggerToast(
        'success', 
        `👑 ${planName} Activated!`, 
        'All premium security shields, Limit System, and extra role profiles are unlocked and ready.'
      );
    }
  };

  return (
    <div className="pt-28 pb-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12 animate-in fade-in duration-300">
      
      {/* Top Header */}
      <div className="text-center max-w-3xl mx-auto space-y-4">
        <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold uppercase tracking-wider">
          <Crown className="w-3.5 h-3.5" />
          <span>Complete Premium Defense Suite</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white font-sans">
          {botName} <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 via-orange-400 to-yellow-300">Premium</span>
        </h1>
        <p className="text-sm sm:text-base text-slate-300 max-w-2xl mx-auto">
          Unlock sub-millisecond rate limits, heuristic anti-betray insider protection, unlimited autoroles, and automated server restoration.
        </p>

        {/* Currency Switcher */}
        <div className="pt-2 flex items-center justify-center">
          <div className="bg-[#12141c] border border-slate-800 rounded-xl p-1 flex items-center gap-1">
            <button
              onClick={() => setCurrency('INR')}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                currency === 'INR' ? 'bg-amber-500 text-black' : 'text-slate-400 hover:text-white'
              }`}
            >
              ₹ in INR
            </button>
            <button
              onClick={() => setCurrency('USD')}
              className={`px-3 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                currency === 'USD' ? 'bg-amber-500 text-black' : 'text-slate-400 hover:text-white'
              }`}
            >
              $ in USD
            </button>
          </div>
        </div>
      </div>

      {/* Prominent Admin & Promo Redeem Code Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-amber-950/40 via-[#131627] to-amber-950/40 border-2 border-amber-500/50 rounded-3xl p-6 sm:p-8 shadow-2xl shadow-amber-950/60 space-y-4">
        <div className="absolute top-0 right-0 w-96 h-full bg-gradient-to-l from-amber-500/10 to-transparent pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start sm:items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-500 text-black flex items-center justify-center shadow-lg shadow-amber-500/30 shrink-0">
              <Gift className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  ADMIN & GIFT CODES
                </span>
                <h3 className="text-xl font-black text-white tracking-tight">
                  Have a Promo or Gift Code?
                </h3>
              </div>
              <p className="text-xs sm:text-sm text-slate-300">
                Redeem your voucher or promo keys to instantly upgrade any server.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            <button
              onClick={onOpenRedeemModal || onOpenLogin}
              className="px-6 py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-orange-500 hover:from-amber-400 hover:to-orange-400 active:scale-95 text-black font-black text-xs sm:text-sm uppercase tracking-wider shadow-xl shadow-amber-500/40 transition-all flex items-center gap-2 cursor-pointer group font-sans"
            >
              <Crown className="w-4 h-4 text-black group-hover:rotate-12 transition-transform" />
              <span>Redeem Code</span>
              <ArrowRight className="w-4 h-4 text-black group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </div>
      </div>

      {/* 3 Main Pricing Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {plans.map((plan) => (
          <div 
            key={plan.id}
            className={`rounded-3xl border transition-all duration-300 p-6 sm:p-7 flex flex-col justify-between relative overflow-hidden shadow-xl ${
              plan.popular 
                ? 'bg-gradient-to-b from-[#1b1509] to-[#0f0c05] border-amber-500/60 shadow-2xl shadow-amber-950/40 ring-1 ring-amber-500/40' 
                : 'bg-[#10121a] border-slate-800/90 hover:border-amber-500/30'
            }`}
          >
            <div>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-black text-white">{plan.name}</h3>
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${plan.badgeColor}`}>
                  {plan.badge}
                </span>
              </div>

              {/* Price */}
              <div className="mb-5 pb-4 border-b border-slate-800/80">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl sm:text-5xl font-black text-amber-400 font-mono tracking-tight">
                    {plan.price}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">/{plan.period}</span>
                </div>
              </div>

              {/* Feature Checklist */}
              <div className="space-y-3 mb-8">
                {plan.features.map((feat, idx) => (
                  <div key={idx} className="flex items-start gap-2.5 text-xs text-slate-300 leading-relaxed">
                    <span className="text-amber-400 font-bold shrink-0 mt-0.5">✦</span>
                    <span className={feat.highlight ? 'text-amber-200 font-semibold' : ''}>
                      {feat.text}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom Button */}
            <button
              onClick={() => handleActivatePlan(plan.name)}
              className={`w-full py-3.5 rounded-xl text-xs sm:text-sm uppercase tracking-wider shadow-lg transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 font-sans ${plan.buttonBg}`}
            >
              <Crown className="w-4 h-4" />
              <span>{plan.buttonText}</span>
            </button>
          </div>
        ))}
      </div>

      {/* Premium Add-Ons Header */}
      <div className="text-center max-w-2xl mx-auto pt-6 space-y-2">
        <h2 className="text-2xl sm:text-4xl font-black text-white tracking-tight">
          Premium <span className="text-amber-400">Add-Ons</span>
        </h2>
        <p className="text-xs sm:text-sm text-slate-400">
          Enhance specific server capabilities with standalone modules
        </p>
      </div>

      {/* 3 Add-Ons Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {addons.map((addon) => (
          <div
            key={addon.id}
            className="bg-[#10121a] border border-slate-800 rounded-3xl p-6 flex flex-col justify-between space-y-5 hover:border-amber-500/40 transition-all shadow-lg"
          >
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-black text-white">{addon.title}</h3>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border border-amber-500/30 bg-amber-500/10 text-amber-300 uppercase">
                  {addon.badge}
                </span>
              </div>

              <div className="flex items-baseline gap-2 mb-4 pb-3 border-b border-slate-800/80">
                <span className="text-3xl font-black text-amber-400 font-mono">{addon.price}</span>
                <span className="text-xs text-slate-400">/{addon.period}</span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed mb-3">
                {addon.desc}
              </p>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                {addon.extra}
              </p>
            </div>

            <button
              onClick={() => {
                if (onTriggerToast) {
                  onTriggerToast('success', `${addon.title} Activated`, 'Standalone security addon linked to active guild.');
                }
              }}
              className="w-full py-3 bg-[#f59e0b] hover:bg-[#d97706] text-black text-xs font-black uppercase tracking-wider rounded-xl transition-all cursor-pointer shadow-md font-sans"
            >
              {addon.buttonText}
            </button>
          </div>
        ))}
      </div>

    </div>
  );
};
