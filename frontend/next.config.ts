import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },

  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/output/**',
      },
      {
        protocol: 'https',
        hostname: '*.onrender.com',
        pathname: '/output/**',
      },
    ],
  },
};

export default nextConfig;
