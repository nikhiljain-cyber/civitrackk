import type { NextConfig } from "next";
const publicApiBase = process.env.NEXT_PUBLIC_API_BASE_URL;
const nextConfig: NextConfig = publicApiBase
  ? { output: "export" }
  : {
      async rewrites() {
        const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
        return [
          { source: "/api/:path*", destination: `${backend}/:path*` },
          { source: "/uploads/:path*", destination: `${backend}/uploads/:path*` },
        ];
      },
    };
export default nextConfig;
