import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // API base URL for the Python server
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8787',
  },
};

export default nextConfig;
