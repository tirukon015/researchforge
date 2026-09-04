import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

/**
 * Vitest, for the parts of the frontend that are pure logic.
 *
 * SCOPE, DELIBERATELY NARROW
 * --------------------------
 * This covers redirect construction and return-path validation: small pure
 * functions whose failure modes are a dead sign-in link and an open redirect
 * respectively. Both are security- or availability-relevant, both are trivial
 * to get subtly wrong, and neither needs a browser.
 *
 * It is NOT a component-rendering suite. Adding jsdom and Testing Library to
 * assert that a button renders would be a large dependency for a small return,
 * and the API contracts those components depend on are already covered by the
 * Python suite.
 */
export default defineConfig({
  resolve: {
    // Matches the "@/*" path alias in tsconfig.json, so tests import modules
    // exactly the way the application does.
    alias: { "@": resolve(__dirname, "src") },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
