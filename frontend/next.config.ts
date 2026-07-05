import type { NextConfig } from "next";
import path from "path";

// @tailwindcss/node builds its enhanced-resolve module list from
// ["node_modules", ...NODE_PATH].  When Turbopack's PostCSS worker calls
// the @tailwindcss/postcss plugin without setting opts.from, the plugin
// computes its resolution base as path.dirname(process.cwd()) which is the
// monorepo root (AlertIQ/) rather than this package root.  Adding this
// package's node_modules as an absolute NODE_PATH entry makes the resolver
// find tailwindcss regardless of what directory the plugin thinks it's in.
const localNodeModules = path.join(__dirname, "node_modules");
if (!process.env.NODE_PATH?.split(path.delimiter).includes(localNodeModules)) {
  process.env.NODE_PATH = process.env.NODE_PATH
    ? `${process.env.NODE_PATH}${path.delimiter}${localNodeModules}`
    : localNodeModules;
}

const nextConfig: NextConfig = {
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
