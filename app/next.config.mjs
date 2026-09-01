/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next 16 otherwise writes its own app/CLAUDE.md and app/AGENTS.md on every
  // build. A nested CLAUDE.md would shadow the project constitution at the
  // repo root (see root CLAUDE.md §4), so generation is turned off here.
  agentRules: false,
};

export default nextConfig;
