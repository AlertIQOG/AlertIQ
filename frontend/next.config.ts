import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The repo root has a stray package-lock.json, which makes Turbopack infer
  // the wrong workspace root and break module resolution — pin it here.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
