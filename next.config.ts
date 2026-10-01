import type { NextConfig } from "next";

const apiOrigin = process.env.FIELDSIGHT_API_ORIGIN ?? "http://127.0.0.1:43124";

const nextConfig: NextConfig = {
  // The dev server is bound on 0.0.0.0, so the browser origin is 127.0.0.1.
  // Without this, Next blocks the HMR socket and the page never hydrates.
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/vision/:path*",
        destination: `${apiOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
