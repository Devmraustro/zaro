import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Standalone output is enabled only for container builds (NEXT_STANDALONE=1
  // in docker/zaro-web.Dockerfile); its symlink-heavy tracing fails on plain
  // Windows hosts without Developer Mode.
  output: process.env.NEXT_STANDALONE === "1" ? "standalone" : undefined,
  outputFileTracingRoot: path.join(currentDir, "../../"),
  transpilePackages: ["@zaro/sdk"],
  poweredByHeader: false,
  async rewrites() {
    if (process.env.NODE_ENV !== "development") {
      return [];
    }
    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001/api/v1";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
