import path from "node:path";
import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
  // Next.js needs inline scripts for hydration; everything else is locked to this origin.
  ...(process.env.NODE_ENV === "production"
    ? [{
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: blob:", "font-src 'self'", "connect-src 'self'", "frame-ancestors 'self'",
          "frame-src 'self' http: https:", "object-src 'none'", "base-uri 'self'", "form-action 'self'",
        ].join("; "),
      }]
    : []),
];

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: process.env.NEXT_TRACING_ROOT ?? path.resolve(__dirname, "../.."),
  poweredByHeader: false,
  compress: false, // the reverse proxy compresses; compressing here buffers the live event stream
  async rewrites() {
    // The browser only ever talks to this origin; the API stays private behind it.
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
