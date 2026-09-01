/**
 * The page frame: top navigation, content, footer. There is no sidebar.
 *
 * Replaces the previous vertical rail. The header is the only navigation at
 * every width, so the full page width belongs to the content, which in this
 * product is dense academic text.
 */

import Footer from "@/components/Footer";
import TopNav from "@/components/TopNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <TopNav />
      <main id="main" className="page">
        {children}
      </main>
      <Footer />
    </div>
  );
}
