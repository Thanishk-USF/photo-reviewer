/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['localhost'],
    unoptimized: true,
  },
  // This allows the API proxy to work correctly
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: '/api/proxy/:path*',
      },
    ];
  },
};

export default nextConfig;
