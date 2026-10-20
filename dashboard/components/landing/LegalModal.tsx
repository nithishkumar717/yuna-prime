"use client";

import React from 'react';
import { FileText } from 'lucide-react';

interface LegalModalProps {
  type: 'terms' | 'privacy' | 'shipping' | 'refund' | 'scta' | 'sdta' | null;
  onClose: () => void;
}

export const LegalModal: React.FC<LegalModalProps> = ({ type, onClose }) => {
  if (!type) return null;
  const botName = process.env.NEXT_PUBLIC_BRAND_NAME || "YUNA";

  const titles: Record<string, string> = {
    terms: 'Terms of Use & Service',
    privacy: 'Privacy Policy & Data Security',
    shipping: 'Shipping & Delivery Policy',
    refund: 'Refund & Cancellation Policy',
    scta: 'SCTA Policy (Server Content & Telemetry)',
    sdta: 'SDTA Legal Disclaimer'
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-150">
      <div className="bg-[#0e1017] border border-slate-800 w-full max-w-2xl rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 relative max-h-[85vh] overflow-y-auto">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-black text-white">{titles[type] || 'Legal Policy'}</h3>
              <p className="text-xs text-slate-400">{botName} Development • Effective 2026</p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-xs font-bold px-3 py-1.5 rounded-lg bg-[#141620] hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700 cursor-pointer"
          >
            Close
          </button>
        </div>

        {/* Policy Body */}
        <div className="space-y-4 text-xs sm:text-sm text-slate-300 leading-relaxed">
          {type === 'terms' && (
            <>
              <p>
                By inviting or authorizing <strong>{botName}</strong> into your Discord server or connecting via our web dashboard, you agree to adhere to these Terms of Service.
              </p>
              <h4 className="font-bold text-white text-sm">1. Server Security & Authorization</h4>
              <p>
                {botName} performs antinuke, antispam, and permission management as explicitly configured by server administrators. We are not liable for accidental user kicks or bans caused by misconfigured action limit rules.
              </p>
              <h4 className="font-bold text-white text-sm">2. Service Uptime</h4>
              <p>
                We strive for 99.9% uptime across all clustered shards. Routine maintenance windows will be announced in advance on our official Discord server.
              </p>
            </>
          )}

          {type === 'privacy' && (
            <>
              <p>
                Your privacy and community safety are paramount. {botName} stores only the necessary metadata required to execute Discord bot functionalities.
              </p>
              <h4 className="font-bold text-white text-sm">1. Data Collected</h4>
              <p>
                We store server IDs, channel IDs, configured auto-roles, moderation strike histories, and web dashboard preferences. We do NOT store message content permanently.
              </p>
              <h4 className="font-bold text-white text-sm">2. Data Deletion</h4>
              <p>
                You may request immediate deletion of all server configuration data by removing {botName} from your Discord server or contacting support.
              </p>
            </>
          )}

          {type === 'shipping' && (
            <>
              <p>
                <strong>Digital Delivery Policy:</strong> All Prime subscriptions, add-ons, and vanity protection licenses are digital goods. Activation is instant and synchronized with your Discord server ID upon payment confirmation.
              </p>
            </>
          )}

          {type === 'refund' && (
            <>
              <p>
                <strong>Refund Policy:</strong> If you experience technical incompatibility or downtime within 48 hours of upgrading, contact our Discord support for an immediate full refund or plan adjustment.
              </p>
            </>
          )}

          {(type === 'scta' || type === 'sdta') && (
            <>
              <p>
                The Server Content & Telemetry Agreement (SCTA / SDTA) defines compliant bot operational standards in accordance with the Discord Developer Terms of Service and API policies.
              </p>
            </>
          )}
        </div>

        {/* Footer OK */}
        <div className="pt-4 border-t border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2.5 bg-gradient-to-r from-red-600 to-rose-600 text-white text-xs font-bold rounded-xl shadow cursor-pointer font-sans"
          >
            I Understand
          </button>
        </div>

      </div>
    </div>
  );
};
