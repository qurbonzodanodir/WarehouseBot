import type { NextConfig } from "next";

const allowedRevalidateHeaderKeys = (process.env.NEXT_ALLOWED_REVALIDATE_KEYS ?? "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "localhost")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  devIndicators: false,
  experimental: {
    allowedRevalidateHeaderKeys,
  },
  allowedDevOrigins,
};

export default nextConfig;
