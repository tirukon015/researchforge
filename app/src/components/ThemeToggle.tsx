"use client";

/**
 * Light, dark, or system, as a three-way segmented control.
 *
 * A two-state toggle would be smaller, but it cannot express "follow my
 * system", and that is the option a laptop user who switches at sunset
 * actually wants. Three labelled segments say what the choices are instead of
 * hiding them behind an icon whose meaning has to be guessed.
 */

import { IconMoon, IconSun, IconSystem } from "@/components/Icons";
import { useTheme, type ThemeChoice } from "@/lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; Icon: typeof IconSun }[] = [
  { value: "light", label: "Light", Icon: IconSun },
  { value: "dark", label: "Dark", Icon: IconMoon },
  { value: "system", label: "System", Icon: IconSystem },
];

export default function ThemeToggle({ full = false }: { full?: boolean }) {
  const { choice, setChoice } = useTheme();

  return (
    <div
      className={`segmented${full ? " segmented--full" : ""}`}
      role="radiogroup"
      aria-label="Colour theme"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const selected = choice === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`segmented__btn${selected ? " segmented__btn--on" : ""}`}
            onClick={() => setChoice(value)}
            title={`${label} theme`}
          >
            <Icon size={15} />
            <span className={full ? "" : "segmented__label"}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}
