/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Next 16 otherwise writes its own app/CLAUDE.md and app/AGENTS.md on every
  // build. A nested CLAUDE.md would shadow the project constitution at the
  // repo root (see root CLAUDE.md §4), so generation is turned off here.
  agentRules: false,

  images: {
    // The Next image optimizer is NOT reachable in this deployment. Production
    // runs two services from one vercel.json (Next.js plus FastAPI), and under
    // that routing a request for /_next/image is answered by the application's
    // own catch-all rather than by the platform's optimizer, so it returns the
    // 404 HTML page instead of an image. Every <Image> therefore rendered a
    // broken src, which is why the logo disappeared in production while
    // working under `next start` locally.
    //
    // Turning optimization off makes <Image> emit the plain static path, which
    // the deployment does serve. width and height are still required and still
    // reserve the box, so nothing shifts on load. The sources in public/brand
    // are pre-sized for their display size, so there is nothing for an
    // optimizer to save here anyway.
    unoptimized: true,
  },
};

export default nextConfig;
