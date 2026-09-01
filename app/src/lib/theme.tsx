"use client";

/**
 * Theme: light, dark, or follow the operating system.
 *
 * Light is the default, which is why `resolve` treats an unreadable stored
 * value as light rather than as "system": a research tool is read in daylight
 * far more often than not, and an ambiguous state should land on the choice
 * the product actually made.
 *
 * WHY THE CHOICE IS WRITTEN TO THE ROOT ELEMENT
 * ---------------------------------------------
 * `globals.css` defines light tokens on bare `:root`, a dark block guarded by
 * `prefers-color-scheme`, and a `[data-theme]` block that wins over both. So
 * setting one attribute switches every colour in the application, and no
 * component needs to know which theme is active.
 *
 * WHY localStorage IS ACCEPTABLE HERE
 * -----------------------------------
 * This is a per-viewer display preference, not application data. It is exactly
 * what browser storage is for, and it is unrelated to the rule that the paper
 * library must not be faked with localStorage.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "researchforge-theme";

/**
 * Runs before first paint, inlined into the document head.
 *
 * Without it the page renders with the default light palette and then flips to
 * dark once React hydrates, which is a visible flash on every single
 * navigation for anyone using a dark theme.
 *
 * It must stay dependency-free and total: any throw here happens before the
 * app exists, so it would break the page rather than the theme. Reading
 * localStorage throws outright in some privacy modes, hence the try/catch.
 */
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem(${JSON.stringify(STORAGE_KEY)});
    var choice = stored === "dark" || stored === "light" || stored === "system"
      ? stored : "light";
    var dark = choice === "dark" || (choice === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  } catch (e) {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();
`.trim();

interface ThemeValue {
  /** What the user chose. */
  choice: ThemeChoice;
  /** What that resolves to right now. */
  resolved: ResolvedTheme;
  setChoice: (choice: ThemeChoice) => void;
}

const ThemeContext = createContext<ThemeValue | null>(null);

function readStored(): ThemeChoice {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light" || stored === "system") return stored;
  } catch {
    /* private mode, or site data blocked */
  }
  return "light";
}

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function resolve(choice: ThemeChoice): ResolvedTheme {
  if (choice === "system") return systemPrefersDark() ? "dark" : "light";
  return choice;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // The first render must match the server-rendered HTML, so state starts at
  // the default and the stored value is adopted in an effect. The inline
  // script has already painted the correct colours by then, so there is no
  // flash despite the one-tick delay.
  const [choice, setChoiceState] = useState<ThemeChoice>("light");
  const [resolved, setResolved] = useState<ResolvedTheme>("light");

  useEffect(() => {
    const stored = readStored();
    setChoiceState(stored);
    setResolved(resolve(stored));
  }, []);

  // "System" must keep tracking the system after it is chosen, not sample it
  // once. Someone whose machine switches at sunset expects the app to follow.
  useEffect(() => {
    if (choice !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolved(media.matches ? "dark" : "light");
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [choice]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", resolved);
    document.documentElement.style.colorScheme = resolved;
  }, [resolved]);

  const setChoice = useCallback((next: ThemeChoice) => {
    setChoiceState(next);
    setResolved(resolve(next));
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // A blocked write means the choice lasts for this visit only. That is a
      // worse experience, not a broken one, so it is not surfaced as an error.
    }
  }, []);

  const value = useMemo(
    () => ({ choice, resolved, setChoice }),
    [choice, resolved, setChoice],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside <ThemeProvider>.");
  return ctx;
}
