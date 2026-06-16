/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  transpilePackages: [],
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
  // Allow long-running API requests (LLM planning can take 60+ seconds)
  experimental: {
    proxyTimeout: 120000,
  },
};

module.exports = nextConfig;