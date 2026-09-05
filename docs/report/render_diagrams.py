"""Render the report's Mermaid diagrams to PNG at a legible size.

    python docs/report/render_diagrams.py

WHY THIS IS NOT JUST "mmdc -i x.mmd -o x.png"
---------------------------------------------
A diagram is placed in the report scaled to fit the text column. Mermaid lays
out to whatever viewport width it is given, so the *effective* font size on the
printed page is:

    font_pt = 16 / natural_width_px * fitted_width_in * 72

A wider render viewport therefore makes the printed text SMALLER, not larger,
because the whole drawing is scaled down further to fit the column. Rendering
the activity diagram at the default viewport produced 5.4 pt text - unreadable
in print - while rendering the same diagram at a 400 px viewport produced
11 pt.

So this script sweeps candidate viewport widths for each diagram, computes the
effective printed font size for each, and keeps the widest-reading option that
still fits the page box. The final pass re-renders at scale 3 for print
resolution; scale changes pixel density only, not layout, so the chosen
legibility is preserved.

Requires Chrome (puppeteer-core has no bundled browser here).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
DIA = HERE / "diagrams"
PROBE = HERE / "_probe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# The area a figure may occupy on an A4 page with 1 inch margins, leaving room
# for the caption.
BOX_W, BOX_H = 6.0, 8.4
CANDIDATE_WIDTHS = [350, 400, 450, 500, 600, 700, 800, 1000]
MERMAID_BASE_FONT_PX = 16


def mmdc(src: pathlib.Path, out: pathlib.Path, width: int, scale: int) -> bool:
    cfg = HERE / "_pptr.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({"args": ["--no-sandbox", "--disable-dev-shm-usage"]}),
                       encoding="utf-8")
    env_cmd = [
        "npx", "-y", "@mermaid-js/mermaid-cli@11",
        "-i", str(src), "-o", str(out),
        "-b", "white", "-s", str(scale), "-w", str(width),
        "-p", str(cfg),
    ]
    import os
    env = dict(os.environ, PUPPETEER_EXECUTABLE_PATH=CHROME)
    r = subprocess.run(env_cmd, capture_output=True, text=True, env=env, shell=True)
    return out.exists() and r.returncode == 0


def fitted(w: int, h: int) -> tuple[float, float]:
    s = min(BOX_W / w, BOX_H / h)
    return w * s, h * s


def effective_pt(natural_w: int, fit_w: float) -> float:
    return MERMAID_BASE_FONT_PX / natural_w * fit_w * 72


def main() -> int:
    PROBE.mkdir(exist_ok=True)
    sources = sorted(DIA.glob("*.mmd"))
    if not sources:
        print("no .mmd sources found")
        return 1

    chosen: dict[str, tuple[int, float, float, float]] = {}
    for src in sources:
        best = None
        for w in CANDIDATE_WIDTHS:
            probe = PROBE / f"{src.stem}_{w}.png"
            if not mmdc(src, probe, w, 1):
                continue
            nw, nh = Image.open(probe).size
            fw, fh = fitted(nw, nh)
            pt = effective_pt(nw, fw)
            if best is None or pt > best[1]:
                best = (w, pt, fw, fh)
        if best is None:
            print(f"  FAILED to render {src.name}")
            return 1
        chosen[src.stem] = best
        print(f"  {src.stem:24} viewport {best[0]:>5}  ->  "
              f"{best[2]:.1f} x {best[3]:.1f} in   {best[1]:.1f} pt text")

    print("\nfinal render at scale 3:")
    manifest = {}
    for src in sources:
        w, pt, fw, fh = chosen[src.stem]
        out = DIA / f"{src.stem}.png"
        if not mmdc(src, out, w, 3):
            print(f"  FAILED {src.name}")
            return 1
        px = Image.open(out).size
        manifest[src.stem] = {"width_in": round(fw, 2), "height_in": round(fh, 2),
                              "effective_pt": round(pt, 1), "pixels": list(px)}
        print(f"  {out.name:28} {px[0]:>5}x{px[1]:<5} -> place at "
              f"{fw:.2f} x {fh:.2f} in  ({px[0] / fw:.0f} dpi)")

    (DIA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    smallest = min(v["effective_pt"] for v in manifest.values())
    print(f"\nsmallest effective text across all diagrams: {smallest} pt")
    if smallest < 8:
        print("WARNING: below 8 pt is hard to read in print")
    return 0


if __name__ == "__main__":
    sys.exit(main())
