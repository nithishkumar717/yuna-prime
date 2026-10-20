"use client";

import React, { useState } from 'react';
import { 
  Search, 
  ChevronDown
} from 'lucide-react';

interface CommandsViewProps {
  onOpenLogin?: () => void;
}

interface CommandItem {
  name: string;
  aliases?: string;
  description: string;
  usage: string;
}

export const CommandsView: React.FC<CommandsViewProps> = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('Utilities');
  const [expandedCommand, setExpandedCommand] = useState<string | null>('help');

  const categories = [
    { name: 'Utilities', description: 'General Tools, Information, And Utility Commands For Server And User Management.', count: 32 },
    { name: 'Moderation', description: 'Enforce rules, kick, ban, mute, warn, and manage members safely.', count: 20 },
    { name: 'Emergency', description: 'Global lockdown, permission freezing, and incident containment.', count: 8 },
    { name: 'Admin & Mod Setup', description: 'Configure admin bypass roles, staff levels, and mod logs.', count: 12 },
    { name: 'Antinuke Security', description: 'Protect channels, roles, webhooks, and server settings from mass attacks.', count: 14 },
    { name: 'Ignore System', description: 'Exempt specific channels, roles, or bots from security rules.', count: 6 },
    { name: 'Automod', description: 'Automatic anti-invite, anti-spam, token raid defense, and regex filters.', count: 15, isPrime: true },
    { name: 'Custom Roles', description: 'Aliases, girl/vip roles, and automatic role distribution.', count: 9 },
    { name: 'Welcome System', description: 'Embedded welcome cards, direct messages, and goodbye alerts.', count: 11 },
    { name: 'Giveaway System', description: 'Host interactive prize drops with custom role and level requirements.', count: 7 },
    { name: 'Fun Commands', description: 'Interactive entertainment, memes, games, and server engagement.', count: 24 },
    { name: 'Music', description: 'Stream tracks, browse artist catalogs, and find movie soundtracks.', count: 1 }
  ];

  const commandsData: Record<string, CommandItem[]> = {
    'Utilities': [
      { name: 'help', aliases: 'h', description: 'Displays a list of available commands or detailed information of a command.', usage: '#help <optional: command>' },
      { name: 'server-profile', aliases: 'botprofile, sp', description: 'Displays or manages bot per-server custom profile (avatar, banner, nickname, status).', usage: '$server-profile' },
      { name: 'server-profile avatar', aliases: 'botprofile av', description: 'Uploads or sets custom per-server bot avatar image. Pass "reset" to revert.', usage: '$server-profile avatar <url/attachment>' },
      { name: 'server-profile banner', aliases: 'botprofile banner', description: 'Uploads or sets custom per-server bot profile banner image. Pass "reset" to revert.', usage: '$server-profile banner <url/attachment>' },
      { name: 'server-profile nickname', aliases: 'botprofile nick', description: 'Sets custom per-server bot nickname. Pass "reset" to revert to global bot name.', usage: '$server-profile nickname <new_nick>' },
      { name: 'server-profile reset', aliases: 'botprofile reset', description: 'Resets all per-server custom bot profile settings back to global defaults.', usage: '$server-profile reset' },
      { name: 'server-profile sync', aliases: 'botprofile sync', description: 'Triggers immediate synchronization of server profile with Discord HTTP API.', usage: '$server-profile sync' },
      { name: 'delete duplicate emoji', aliases: 'N/A', description: 'Deletes Duplicate Emojis In The Server.', usage: '&delete duplicate emoji' },
      { name: 'botinfo', aliases: 'bi, stats', description: 'Displays Detailed Information About The Bot.', usage: '&botinfo\n&bi\n&stats' },
      { name: 'invite', aliases: 'N/A', description: 'Provides The Bot\'s Invite Link.', usage: '&invite' },
      { name: 'website', aliases: 'site, dashboard, web', description: 'Displays official website and Web Dashboard link.', usage: '$website' },
      { name: 'serverinfo', aliases: 'si', description: 'Displays Information About The Current Server.', usage: '&serverinfo\n&si' },
      { name: 'userinfo', aliases: 'ui, whois', description: 'Displays Information About A Specified User.', usage: '&userinfo <@user/id>' },
      { name: 'roleinfo', aliases: 'ri', description: 'Shows detailed metadata for a specific role.', usage: '&roleinfo <@role/id>' },
      { name: 'boostcount', aliases: 'bc', description: 'Shows total server boosts and boost tier status.', usage: '&boostcount' },
      { name: 'unbanall', aliases: 'unban-all', description: 'Unbans all banned users in the server safely.', usage: '&unbanall' },
      { name: 'ping', aliases: 'latency', description: 'Checks bot latency and Discord API response times.', usage: '&ping' },
      { name: 'github', aliases: 'git', description: 'Displays GitHub repository stats for requested project.', usage: '&github <owner/repo>' },
      { name: 'vcinfo', aliases: 'voiceinfo', description: 'Displays active voice channels and connected listeners.', usage: '&vcinfo' },
      { name: 'channelinfo', aliases: 'ci', description: 'Shows channel settings, slowmode, and permissions.', usage: '&channelinfo <#channel>' },
      { name: 'banner', aliases: 'userbanner', description: 'Displays high-resolution user or server banner.', usage: '&banner <@user>' },
      { name: 'reminder', aliases: 'remindme', description: 'Sets a personal or server-wide timed reminder.', usage: '&reminder <time> <message>' },
      { name: 'permissions', aliases: 'perms', description: 'Lists all resolved Discord permissions for a user.', usage: '&permissions <@user>' },
      { name: 'timer', aliases: 'countdown', description: 'Starts an interactive countdown timer in channel.', usage: '&timer <duration>' },
      { name: 'status', aliases: 'botstatus', description: 'Shows bot cluster status, memory, and ping.', usage: '&status' },
      { name: 'afk', aliases: 'setafk', description: 'Sets an AFK status with optional mention responders.', usage: '&afk <reason>' },
      { name: 'avatar', aliases: 'av, pfp', description: 'Displays user avatar in full resolution.', usage: '&avatar <@user>' },
      { name: 'servericon', aliases: 'icon', description: 'Displays server icon with download link.', usage: '&servericon' },
      { name: 'membercount', aliases: 'mc', description: 'Counts bots, humans, and online members.', usage: '&membercount' },
      { name: 'poll', aliases: 'vote', description: 'Creates a custom reaction poll.', usage: '&poll <question>' },
      { name: 'hack', aliases: 'fakehack', description: 'Fun simulated hack terminal game.', usage: '&hack <@user>' },
      { name: 'token', aliases: 'generatetoken', description: 'Generates a secure alphanumeric hash token.', usage: '&token' },
      { name: 'users', aliases: 'listusers', description: 'Exports server member roster into clean format.', usage: '&users' },
      { name: 'urban', aliases: 'ud', description: 'Searches urban dictionary definitions.', usage: '&urban <term>' },
      { name: 'rickroll', aliases: 'rr', description: 'Sends a surprise animated musical embed.', usage: '&rickroll' },
      { name: 'hash', aliases: 'sha256', description: 'Generates cryptographic SHA256 string.', usage: '&hash <text>' },
      { name: 'snipe', aliases: 's', description: 'Retrieves recently deleted message in channel.', usage: '&snipe' },
      { name: 'list', aliases: 'roles', description: 'Lists all server roles and member counts.', usage: '&list roles' }
    ],
    'Moderation': [
      { name: 'ban', aliases: 'b', description: 'Bans a user from the server with optional reason.', usage: '&ban <@user> [reason]' },
      { name: 'kick', aliases: 'k', description: 'Kicks a user from the server.', usage: '&kick <@user> [reason]' },
      { name: 'mute', aliases: 'timeout', description: 'Times out a user for a specified duration.', usage: '&mute <@user> <1m/1h/1d> [reason]' },
      { name: 'unmute', aliases: 'untimeout', description: 'Removes timeout from a member.', usage: '&unmute <@user>' },
      { name: 'warn', aliases: 'w', description: 'Issues an official recorded infraction warning.', usage: '&warn <@user> <reason>' },
      { name: 'warnings', aliases: 'warns', description: 'Displays all warning cases for a user.', usage: '&warnings <@user>' },
      { name: 'clearwarns', aliases: 'delwarns', description: 'Clears warnings for a user.', usage: '&clearwarns <@user>' },
      { name: 'purge', aliases: 'clear', description: 'Deletes bulk messages from channel.', usage: '&purge <amount>' },
      { name: 'slowmode', aliases: 'sm', description: 'Sets channel message rate cooldown.', usage: '&slowmode <seconds>' },
      { name: 'lock', aliases: 'lockchannel', description: 'Locks down channel from @everyone messages.', usage: '&lock' },
      { name: 'unlock', aliases: 'unlockchannel', description: 'Restores chat permissions to channel.', usage: '&unlock' },
      { name: 'hide', aliases: 'hidechannel', description: 'Hides channel from non-staff members.', usage: '&hide' },
      { name: 'unhide', aliases: 'showchannel', description: 'Makes channel visible to @everyone.', usage: '&unhide' },
      { name: 'nuke', aliases: 'channelnuke', description: 'Duplicates the channel preserving position and deletes the original.', usage: '/nuke [channel]\n&nuke [channel]' },
      { name: 'clone', aliases: 'clonechannel', description: 'Duplicates a channel with all permissions and topic.', usage: '/clone [channel]\n&clone [channel]' }
    ],
    'Antinuke Security': [
      { name: 'antinuke', aliases: 'anti-nuke', description: 'Interactive security and antinuke setup control panel.', usage: '&antinuke <enable/disable>' },
      { name: 'extraowner', aliases: 'extraown', description: 'Grants full server-owner-equivalent access across all bot actions to trusted co-owners.', usage: '&extraowner set <@user>' },
      { name: 'whitelist', aliases: 'wl', description: 'Whitelists a trusted admin or bot from antinuke triggers.', usage: '&whitelist add <@user/role>' },
      { name: 'whitelisted', aliases: 'wled', description: 'Displays all whitelisted staff and administrators.', usage: '&whitelisted' },
      { name: 'nightmode', aliases: 'nm', description: 'Automated overnight permissions lock and security freeze.', usage: '&nightmode <enable/disable>' }
    ],
    'Automod': [
      { name: 'automod enable', aliases: 'am on', description: 'Enables real-time automated threat interceptor.', usage: '&automod enable' },
      { name: 'anti-invite', aliases: 'antiinvite', description: 'Blocks discord invite links from non-whitelisted users.', usage: '&anti-invite <enable/disable>' },
      { name: 'anti-spam', aliases: 'antispam', description: 'Detects fast repeat messages and mutes author.', usage: '&anti-spam <threshold>' },
      { name: 'anti-token', aliases: 'antitoken', description: 'Blocks automated user tokens and mass account raids.', usage: '&anti-token on' },
      { name: 'badwords add', aliases: 'filter add', description: 'Adds blacklisted keywords to automated filter.', usage: '&badwords add <word>' }
    ],
    'Emergency': [
      { name: 'emergency enable', aliases: 'lockdown all', description: 'One-click global lockdown across all 45 channels.', usage: '&emergency enable' },
      { name: 'emergency disable', aliases: 'unlock all', description: 'Restores standard community access post-incident.', usage: '&emergency disable' }
    ],
    'Fun Commands': [
      { name: 'memory-game', aliases: 'memory', description: 'Test and train your visual memory with interactive grid cards.', usage: '&memory-game\n&memory' },
      { name: '2048', aliases: 'twenty48', description: 'Classic 2048 grid puzzle game in Discord chat.', usage: '&2048' },
      { name: 'tic-tac-toe', aliases: 'ttt', description: 'Challenge a server member to Tic-Tac-Toe.', usage: '&tic-tac-toe <@user>' },
      { name: 'wordle', aliases: 'guessword', description: '5-letter word guess puzzle game.', usage: '&wordle' },
      { name: 'blackjack', aliases: 'bj', description: 'Play casino Blackjack with virtual chips.', usage: '&blackjack [bet]' },
      { name: 'slots', aliases: 'slot', description: 'Spin the casino slot machine.', usage: '&slots [bet]' }
    ],
    'Music': [
      { name: 'play', aliases: 'p', description: 'Plays a song, artist catalog, or movie soundtrack. Tamil song titles work in Tamil script or Tanglish. Known Tamil actor names followed by `songs` search movie tracks.', usage: '/play <song, artist, movie, or URL>\n$play vijay songs\n$play simbu songs\n$play ajith songs\n$play trisha songs' }
    ]
  };

  const activeCategoryObj = categories.find(c => c.name === selectedCategory) || categories[0];
  const listToRender = commandsData[selectedCategory] || commandsData['Utilities'] || [];
  
  const filteredCommands = listToRender.filter(cmd => 
    cmd.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    cmd.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="pt-28 pb-20 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      
      {/* Top Header */}
      <div className="text-center max-w-3xl mx-auto mb-10">
        <h1 className="text-4xl sm:text-6xl font-black tracking-tight text-white font-sans">
          Commands
        </h1>
        <p className="mt-3 text-sm sm:text-base text-slate-400">
          Explore all available commands by category
        </p>
      </div>

      {/* Search Bar + Category Dropdown Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 mb-8">
        
        {/* Search Input Box */}
        <div className="sm:col-span-8 relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search commands..."
            className="w-full bg-[#10121a] border border-slate-800 rounded-xl pl-10 pr-4 py-3 text-xs sm:text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-red-500/50 transition-colors"
          />
        </div>

        {/* Category Selector Dropdown */}
        <div className="sm:col-span-4 relative">
          <select
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              setExpandedCommand(null);
            }}
            className="w-full bg-[#10121a] border border-slate-800 rounded-xl px-4 py-3 text-xs sm:text-sm font-bold text-white focus:outline-none focus:border-red-500/50 appearance-none cursor-pointer"
          >
            {categories.map((cat) => (
              <option key={cat.name} value={cat.name}>
                {cat.name} {cat.isPrime ? '★' : ''}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        </div>

      </div>

      {/* Horizontal Touch Scroll Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-6 no-scrollbar">
        {categories.map((cat) => {
          const isSelected = selectedCategory === cat.name;
          return (
            <button
              key={cat.name}
              onClick={() => {
                setSelectedCategory(cat.name);
                setExpandedCommand(null);
              }}
              className={`flex-shrink-0 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all cursor-pointer ${
                isSelected
                  ? 'bg-red-600 text-white shadow-md shadow-red-600/30'
                  : 'bg-[#10121a] text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              {cat.name} {cat.isPrime ? '★' : ''}
            </button>
          );
        })}
      </div>

      {/* Category Header Title & Description */}
      <div className="mb-6">
        <h2 className="text-2xl font-black text-red-400 tracking-tight flex items-center gap-2">
          {activeCategoryObj.name}
          {activeCategoryObj.isPrime && (
            <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-bold border border-amber-500/40">
              PRIME
            </span>
          )}
        </h2>
        <p className="mt-1 text-xs text-slate-400">
          {activeCategoryObj.description}
        </p>
      </div>

      {/* Command Accordion List */}
      <div className="space-y-2.5">
        {filteredCommands.map((cmd) => {
          const isExpanded = expandedCommand === cmd.name;
          return (
            <div
              key={cmd.name}
              className={`rounded-2xl border transition-all overflow-hidden ${
                isExpanded 
                  ? 'bg-[#10121a] border-red-500/40 shadow-lg shadow-red-950/30' 
                  : 'bg-[#0b0d14] border-slate-800/80 hover:border-slate-700'
              }`}
            >
              <button
                type="button"
                onClick={() => setExpandedCommand(isExpanded ? null : cmd.name)}
                className="w-full px-5 py-3.5 flex items-center justify-between text-left cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{cmd.name}</span>
                </div>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isExpanded ? 'transform rotate-180 text-red-400' : ''}`} />
              </button>

              {isExpanded && (
                <div className="px-5 pb-5 pt-1 border-t border-slate-800/60 space-y-3 bg-[#0e1017]">
                  {cmd.aliases && (
                    <div className="text-xs">
                      <span className="text-slate-400 font-medium">Aliases: </span>
                      <span className="font-mono text-slate-300">{cmd.aliases}</span>
                    </div>
                  )}

                  <div className="text-xs">
                    <span className="text-slate-400 font-medium">Description: </span>
                    <span className="text-slate-300">{cmd.description}</span>
                  </div>

                  <div className="text-xs space-y-1">
                    <span className="text-slate-400 font-medium">Usage:</span>
                    <div className="p-2.5 rounded-lg bg-[#07080c] border border-slate-800 font-mono text-red-400 text-xs">
                      {cmd.usage}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {filteredCommands.length === 0 && (
          <div className="text-center py-12 text-slate-500 text-xs">
            No commands matched your query &ldquo;{searchQuery}&rdquo;.
          </div>
        )}
      </div>

    </div>
  );
};
