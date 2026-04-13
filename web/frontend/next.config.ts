import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  experimental: {
    allowedRevalidateHeaderKeys: ["192.168.0.153"],
  },
  // @ts-ignore
  allowedDevOrigins: ["192.168.0.153", "192.168.1.153", "192.168.0.198", "localhost"],
};

export default nextConfig;
