# Design System

The established visual system of the ResearchForge frontend. **Every new screen and component
must use these tokens and classes.** Don't introduce a second palette, a component library,
Tailwind, a web font or a different radius or shadow scale.

Source of truth: `app/src/app/globals.css` (about 3,400 lines, plain CSS, no preprocessor).
The line numbers below are approximate anchors as of 2026-09-26.

---

## 1. Principles

- **Plain CSS with custom properties.** Styling is global classes in `globals.css`,
  BEM-flavoured (`block__element--modifier`), with no CSS modules or CSS-in-JS.
- **Tokens, never raw values.** Colours, radii and shadows come from `:root` variables, so
  both themes follow automatically.
- **State is never shown by colour alone.** Active nav uses fill + weight + colour; field
  errors use colour + a message; statuses use a badge label.
- **Honest UI.** Empty, loading, not-configured and error states each get their own wording.
- **Quiet, professional, research-dashboard tone.** No gradients on controls, no decorative
  animation in the app, and the decorative backdrop (`ResearchBackdrop`) stays faint.

## 2. Colour tokens (`:root`, globals.css ~L16–75)

| Role | Light | Dark |
|---|---|---|
| `--bg` page | `#f4f6f9` | `#0d1117` |
| `--panel` card | `#ffffff` | `#161b22` |
| `--panel-2` / `--panel-3` | `#f8fafc` / `#eef2f7` | `#1b212b` / `#212936` |
| `--border` / `--border-soft` | `#dbe2ec` / `#e9eef4` | `#2b323d` / `#232a34` |
| `--text` / `--text-2` | `#16202e` / `#3d4a5c` | `#e6ebf2` / `#b6c1d0` |
| `--muted` / `--faint` | `#64748b` / `#94a3b8` | `#8b97a8` / `#6b7684` |
| `--accent` (primary blue) | `#1668e3` | `#5aa0ff` |
| `--accent-hover` | `#1257c0` | `#7ab3ff` |
| `--accent-soft` / `--accent-line` | `#e8f0fd` / `#b9d2f8` | `#13233c` / `#24406b` |
| `--ok` / `--ok-soft` | `#12783a` / `#e7f6ec` | `#46b563` / `#10251a` |
| `--warn` / `--warn-soft` | `#92610a` / `#fdf5e3` | `#d0a02c` / `#241d0d` |
| `--err` / `--err-soft` / `--err-line` | `#b3261e` / `#fdecea` / `#f3c2bd` | `#f0796b` / `#2a1513` / `#4a241f` |
| `--ring` (focus) | `rgba(22,104,227,.35)` | `rgba(90,160,255,.4)` |

Brand navy (`--navy-900 #0b1f42`, `--navy-800`, `--navy-700`) and `--blue-600`/`--blue-500`
are brand constants used by the logo and header.

**Dark theme** is applied in two ways: `@media (prefers-color-scheme: dark)` when the theme
is *System*, and `[data-theme="dark"]` / `[data-theme="light"]` on `<html>`, which wins over
the media query, when the user picks explicitly (see `lib/theme.tsx`).
**Any new token must be defined in all three blocks.**

## 3. Typography

| Token / use | Value |
|---|---|
| `--font` | System UI stack: `ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, …`. **No web fonts.** |
| `--mono` | `ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace`. Used for model names, badges (`.badge--mono`) and code |
| Body | 15px, line-height 1.6, antialiased |
| Page title `.pagehead__title` | 1.55rem, letter-spacing -0.02em |
| Page subtitle `.pagehead__sub` | 0.94rem, muted |
| Eyebrow `.pagehead__eyebrow`, `.hero__eyebrow` | 0.72rem, weight 700, uppercase, tracking 0.1–0.11em, accent |
| Section label `.section__title` | 0.79rem, weight 700, uppercase, tracking 0.09em |
| App hero title `.hero__title` | 2rem, tracking -0.03em |
| Landing hero title | `clamp(2.1rem, 5.2vw, 3.4rem)`, weight 800 |
| Landing section titles | `clamp(1.5rem, 3vw, 2rem)` |
| Controls / tabs | 0.89–0.9rem, weight 600 |
| Small / meta text | 0.76–0.85rem |

Weights in use: **500, 550, 600, 650, 700, 800**. 600 is the default for controls and 700 for
labels and headings. Don't add 300/400-weight display text.

## 4. Shape and elevation

| Token | Value | Use |
|---|---|---|
| `--r-sm` | 6px | Focus outline, small chips |
| `--r-md` | 9px | Buttons, inputs |
| `--r-lg` | 13px | Cards, panels |
| `999px` | — | Badges and pills |
| `--shadow-sm` | `0 1px 2px rgba(11,31,66,.06)` | Cards at rest |
| `--shadow-md` | two-layer, soft | Raised / hover |
| `--shadow-lg` | `0 12px 32px rgba(11,31,66,.12)` | Menus, popovers |

Borders are 1px `--border` (cards) or `--border-soft` (dividers).

## 5. Components (class vocabulary)

| Pattern | Classes | Rules |
|---|---|---|
| **Button** | `.btn` + `--primary` · `--ghost` · `--danger` · `--lg` · `--sm`; groups `.btnrow` | Padding `.55rem 1rem`, `--r-md`. Primary = `--accent` fill. Disabled lowers opacity. One primary per area |
| **Card** | `.card`, `.card__head`, `.card__title`, `.card__hint`, `.card__body` (padding 1.25rem) | `--panel`, 1px border, `--r-lg`, `--shadow-sm` |
| **Page frame** | `.page` (max 1180px, padding `2rem 1.5rem 4rem`), `.pagehead`, `.section`, `.section__head`, `.section__title` | Sections are 2rem apart |
| **Tabs** | `.tabs`, `.tab`, `.tab--active`, `.tabpanel` | Active = accent text + 2px accent underline |
| **Content blocks** | `.block`, `.block__head`, `.block h4` | Analysis sections; each has a `CopyButton` |
| **Research gap card** | (~L1117) | Gap title, "Why it matters", evidence quote block with accent left rule |
| **Badge** | `.badge`, `--mono`, `--accent`, `--ok`; `.tagrow` | Pill, 0.73rem, weight 600 |
| **Notice** | `.notice` + `--error` · `--warn` · `--info` · `--spaced` | Icon + text on the matching `*-soft` background |
| **Empty state** | `.empty`, `__art`, `__icon`, `__title`, `__body`, `__actions` (use `EmptyState`) | Always explains the *reason* for emptiness |
| **Progress** | `.progress`, `__bar`, `__head`, `__elapsed` | Indeterminate bar; steps listed but never falsely marked done |
| **Stats** | (~L622) | Dashboard overview tiles; show a neutral placeholder, not `0`, while loading |
| **Definition grid** | (~L1208) | Paper Information / Details tab |
| **Forms** | fields section (~L2015) | Error = colour **and** message beneath |
| **Top nav** | `.topnav*`, `.topnav__mobile` | Active route = fill + weight + colour |
| **Toolbar** | `.toolbar` | Search + selects above lists |
| **Landing** | `.lp-section`, `.hero*`, `.marketing*` (~L2130–2660) | Landing only; don't reuse inside the app |

**Icons:** use `components/Icons.tsx` only. They are hand-drawn inline SVG on a 24×24 viewBox,
`stroke="currentColor"`, **strokeWidth 1.8**, round caps and joins, default size 18, always
`aria-hidden`. Add new glyphs there in the same style. Don't add an icon library.

**Images:** the logo lives in `app/public/brand/`. The Next image optimizer is disabled
(`images.unoptimized: true`). `img`/`svg` never overflow their container.

## 6. Spacing rhythm

A rem-based scale, no spacing tokens. Common values: 0.35, 0.55, 0.7, 0.85, 1, 1.25, 1.5 and
2rem. Page gutter is 1.5rem (smaller on mobile). Card padding is 1.25rem. Section gap is 2rem.
Stay on these values.

## 7. Breakpoints (max-width media queries)

| Width | What changes |
|---|---|
| 1100px | Landing layout tightens |
| 980px | Multi-column layouts (workspace, library) stack |
| **900px** | **Top nav links hide and the menu button appears**; header tagline hides; page padding shrinks |
| 640px | Toolbars and grids simplify |
| 560px | Mobile: segmented controls, stats and landing sections stack |
| 380px | Smallest phones |

Also used: `@media print` (clean output) and `prefers-reduced-motion`.

## 8. Motion

- Only **functional** motion: the progress bar slide (`@keyframes rf-slide`), the spinner
  (`rf-spin`) and short hover transitions (~0.15s on `border-color`/`background`/`transform`).
- Every animation is disabled under `prefers-reduced-motion: reduce`.
- No entrance, scroll or parallax animations in the app.

## 9. Accessibility conventions

- `:focus-visible` outline: 2px `--accent`, offset 2px.
- Skip link to `#main` in the app shell.
- Decorative SVG and backdrop are `aria-hidden`. Controls carry their accessible names.
- Live regions (`role="status"`, `aria-live="polite"`) announce progress and session checks.

## 10. Adding UI: checklist

1. Can an existing class or component do it? Extend it with a modifier rather than duplicating it.
2. Use tokens only, and check both themes (Light, Dark, System).
3. Check at 1440, 900 and 390px, with no horizontal page scroll.
4. Check keyboard focus and reduced motion.
5. If you added a token or a reusable class, record it here.
