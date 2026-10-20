"use client";

import React, { useState } from 'react';
import { 
  Bot, 
  MessageSquare, 
  Mail, 
  Send, 
  CheckCircle2
} from 'lucide-react';

interface SupportViewProps {
  onOpenInvite: () => void;
  onOpenLogin: () => void;
}

export const SupportView: React.FC<SupportViewProps> = ({ onOpenInvite }) => {
  const [submitted, setSubmitted] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [supportLink] = useState(process.env.NEXT_PUBLIC_SUPPORT_SERVER_URL || 'https://discord.gg/YzHCx5yQXv');

  const handleJoinSupport = () => {
    window.open(supportLink, '_blank');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="pt-28 pb-20 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
      
      {/* Top Header */}
      <div className="text-center max-w-3xl mx-auto mb-12">
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white font-sans">
          Support & Help Center
        </h1>
        <p className="mt-3 text-sm sm:text-base text-slate-400">
          Get real-time assistance from our engineers or join our community
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Left Box: Discord Support Server */}
        <div className="bg-[#0e1017] border border-slate-800 rounded-3xl p-8 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400">
              <MessageSquare className="w-6 h-6" />
            </div>

            <h3 className="text-2xl font-black text-white">Join Official Discord</h3>
            <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
              Have questions about configuration, bot permissions, or custom plans? Connect with our 24/7 moderation team and developers directly on Discord.
            </p>

            <div className="space-y-2 pt-2 text-xs font-semibold text-slate-300">
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Active 24/7 Community & Staff</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Instant Ticket System</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Priority Prime Support Roles</span>
              </div>
            </div>
          </div>

          <button
            onClick={handleJoinSupport}
            className="w-full py-3.5 bg-[#5865F2] hover:bg-[#4752C4] text-white text-xs sm:text-sm font-black uppercase tracking-wider rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer font-sans"
          >
            <Bot className="w-4 h-4" />
            <span>Join Discord Support Server</span>
          </button>
        </div>

        {/* Right Box: Contact Message Form */}
        <div className="bg-[#0e1017] border border-slate-800 rounded-3xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-black text-white">Send Direct Message</h3>
              <p className="text-xs text-slate-400">We reply in under 2 hours</p>
            </div>
          </div>

          {submitted ? (
            <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-center space-y-3">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
              <h4 className="text-base font-bold text-white">Message Dispatched!</h4>
              <p className="text-xs text-slate-300">
                Thanks for reaching out! A senior support specialist will get back to you at <strong>{email}</strong> shortly.
              </p>
              <button
                onClick={() => setSubmitted(false)}
                className="text-xs font-bold text-emerald-400 underline cursor-pointer"
              >
                Send another message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="text-[11px] font-bold uppercase text-slate-400 block mb-1">Your Name / Tag</label>
                <input 
                  type="text" 
                  required 
                  value={name} 
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. @User"
                  className="w-full bg-[#08090e] border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-red-500/50"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase text-slate-400 block mb-1">Email Address</label>
                <input 
                  type="email" 
                  required 
                  value={email} 
                  onChange={e => setEmail(e.target.value)}
                  placeholder="name@domain.com"
                  className="w-full bg-[#08090e] border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-red-500/50"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase text-slate-400 block mb-1">Subject</label>
                <input 
                  type="text" 
                  required 
                  value={subject} 
                  onChange={e => setSubject(e.target.value)}
                  placeholder="Inquiry / Technical Question"
                  className="w-full bg-[#08090e] border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-red-500/50"
                />
              </div>

              <div>
                <label className="text-[11px] font-bold uppercase text-slate-400 block mb-1">Message</label>
                <textarea 
                  required 
                  rows={3}
                  value={message} 
                  onChange={e => setMessage(e.target.value)}
                  placeholder="Describe your server requirements or problem..."
                  className="w-full bg-[#08090e] border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-red-500/50 resize-none"
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white text-xs font-bold uppercase tracking-wider rounded-xl shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer font-sans"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Submit Ticket</span>
              </button>
            </form>
          )}
        </div>

      </div>

    </div>
  );
};
