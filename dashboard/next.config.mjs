/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'cdn.discordapp.com',
      },
    ],
  },
  webpack: (config) => {
    config.cache = false;
    return config;
  },
  async rewrites() {
    const rawTarget = process.env.BOT_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    if (rawTarget && (rawTarget.startsWith('http://') || rawTarget.startsWith('https://'))) {
      const cleanBase = rawTarget.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');
      return [
        {
          source: '/api/v1/:path*',
          destination: `${cleanBase}/api/v1/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
