"use client";

import React, { useState } from 'react';
import { BrandLogo } from './BrandLogo';
import { 
  Shield, 
  Github, 
  Twitter, 
  Mail, 
  MessageSquare, 
  BookOpen, 
  LayoutDashboard, 
  Bot, 
  Terminal, 
  Crown, 
  HelpCircle, 
  FileText 
} from 'lucide-react';

interface FooterProps {
  onOpenLogin: () => void;
  onOpenInvite: () => void;
  onSelectTab?: (tab: 'home' | 'commands' | 'docs' | 'support' | 'premium') => void;
  onOpenLegal?: (type: 'terms' | 'privacy' | 'shipping' | 'refund' | 'scta' | 'sdta') => void;
}

export const Footer: React.FC<FooterProps> = ({ 
  onOpenLogin, 
  onOpenInvite,
  onSelectTab,
  onOpenLegal 
}) => {
  const [supportLink] = useState(process.env.NEXT_PUBLIC_SUPPORT_SERVER_URL || 'https://discord.gg/YzHCx5yQXv');
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  return (
    <footer className="bg-[#050608] border-t border-slate-900 text-slate-400 text-xs relative overflow-hidden">
      
      {/* Upper Footer Links */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10">
          
          {/* Brand Info Column (Span 2) */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center gap-3">
              <BrandLogo size="md" />
              <span className="font-extrabold text-white text-base tracking-wider">{botName}</span>
            </div>
            
            <p className="text-xs text-slate-400 leading-relaxed max-w-sm">
              The ultimate multipurpose Discord bot engineered for modern servers with advanced features and reliable performance.
            </p>

            <div className="flex items-center gap-3 pt-2">
              <button 
                onClick={onOpenInvite}
                className="w-8 h-8 rounded-lg bg-[#12141c] border border-slate-800 hover:border-red-500/40 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
                title="Discord Community"
              >
                <MessageSquare className="w-4 h-4 text-red-400" />
              </button>
              <a 
                href="https://github.com/nithishkumar717/yuna-bot" 
                target="_blank" 
                rel="noreferrer" 
                className="w-8 h-8 rounded-lg bg-[#12141c] border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
                title="GitHub"
              >
                <Github className="w-4 h-4" />
              </a>
              <a 
                href="https://twitter.com" 
                target="_blank" 
                rel="noreferrer" 
                className="w-8 h-8 rounded-lg bg-[#12141c] border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
                title="Twitter"
              >
                <Twitter className="w-4 h-4" />
              </a>
            </div>
          </div>

          {/* Quick Links Column */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Quick Links
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <button onClick={onOpenLogin} className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer">
                  <LayoutDashboard className="w-3.5 h-3.5 text-slate-500" /> Dashboard
                </button>
              </li>
              <li>
                <button onClick={onOpenInvite} className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer">
                  <Bot className="w-3.5 h-3.5 text-slate-500" /> Add Bot
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onSelectTab && onSelectTab('docs')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <BookOpen className="w-3.5 h-3.5 text-slate-500" /> Documentation
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onSelectTab && onSelectTab('commands')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Terminal className="w-3.5 h-3.5 text-slate-500" /> Commands
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onSelectTab && onSelectTab('premium')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 text-amber-400 cursor-pointer"
                >
                  <Crown className="w-3.5 h-3.5 text-amber-400" /> Premium
                </button>
              </li>
              <li>
                <button onClick={() => window.open(supportLink, '_blank')} className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer">
                  <HelpCircle className="w-3.5 h-3.5 text-slate-500" /> Support Server
                </button>
              </li>
            </ul>
          </div>

          {/* Legal Column */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Legal
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <button 
                  onClick={() => onSelectTab && onSelectTab('support')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Mail className="w-3.5 h-3.5 text-slate-500" /> Contact Us
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('terms')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5 text-slate-500" /> Terms of Use
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('privacy')}
                  className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <Shield className="w-3.5 h-3.5 text-slate-500" /> Privacy Policy
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('shipping')}
                  className="hover:text-white transition-colors cursor-pointer text-left"
                >
                  Shipping & Delivery
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('refund')}
                  className="hover:text-white transition-colors cursor-pointer text-left"
                >
                  Refund & Cancellation
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('scta')}
                  className="hover:text-white transition-colors cursor-pointer text-left"
                >
                  SCTA
                </button>
              </li>
              <li>
                <button 
                  onClick={() => onOpenLegal && onOpenLegal('sdta')}
                  className="hover:text-white transition-colors cursor-pointer text-left"
                >
                  SDTA
                </button>
              </li>
            </ul>
          </div>

          {/* Social Links Column */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white">
              Social Links
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <button onClick={onOpenInvite} className="hover:text-white transition-colors cursor-pointer">
                  Discord
                </button>
              </li>
              <li>
                <a href="https://instagram.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">
                  Instagram
                </a>
              </li>
              <li>
                <a href="https://twitter.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">
                  Twitter
                </a>
              </li>
              <li>
                <a href="https://youtube.com" target="_blank" rel="noreferrer" className="hover:text-white transition-colors">
                  YouTube
                </a>
              </li>
            </ul>
          </div>

        </div>

        {/* Bottom Bar with Copyright */}
        <div className="pt-8 mt-12 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-slate-400 text-xs">
          <p>
            © {new Date().getFullYear()} <strong className="text-slate-300 font-bold">{botName}</strong>. All rights reserved.
          </p>
          
          <div className="flex items-center gap-1">
            <span>Powered by</span>
            <span className="text-red-400 font-bold">{botName} Engine</span>
          </div>
        </div>

      </div>
    </footer>
  );
};
