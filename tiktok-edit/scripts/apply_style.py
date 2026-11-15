#!/usr/bin/env python3
"""Restyle i-hate-editing's composition to a style preset, then render.

    python3 $IHE/scripts/compose.py --studio studio            # no --render
    apply_style.py --studio studio --title "how I got\\nmy first client" --render

i-hate-editing's compose.py builds the composition (captions, cards, B-roll,
sound) as an HTML page and renders it with HyperFrames. Its caption position
and font are fixed in code, so a different look is applied to the page it
wrote, after it writes it and before the render:

  - captions move to the style's height (centre for Shivani's style), in its
    font, all one size and colour
  - a title is held for the whole video (--title, "\\n" between lines)
  - screenshot cards from floats.json (screenshot_card.py) float over the
    speaker at the style's place and size
  - the style's font file is embedded, so the render never falls back

Run compose.py again before re-applying: the patch refuses a page it has
already patched.
"""

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import H, W, die, ihe_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MARK = "<!-- tiktok-edit style -->"
TRACK_TITLE, TRACK_FLOAT = 58, 50     # under captions (60), over cards/proof


def to_px(x, y):
    """CapCut-style offsets (half-frame units, y up) to a frame centre in px."""
    return W / 2 + x * W / 2, H / 2 - y * H / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--studio", default="studio")
    ap.add_argument("--style", default="shivani")
    ap.add_argument("--title", default=None, help='two short lines: "line one\\nline two"')
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--low-memory", action="store_true")
    args = ap.parse_args()

    style = json.loads((ROOT / "styles" / f"{args.style}.json").read_text())
    studio = Path(args.studio)
    comp = studio / "composition"
    page = comp / "index.html"
    if not page.is_file():
        die(f"no {page}: run $IHE/scripts/compose.py --studio {studio} first")
    doc = page.read_text()
    if MARK in doc:
        die("this composition is already styled; re-run compose.py first")
    m = re.search(r'id="root"[^>]*data-duration="([\d.]+)"', doc)
    if not m:
        die("unexpected composition layout (no root duration); has "
            "i-hate-editing changed compose.py?")
    duration = float(m.group(1))

    font = style["font"]
    font_src = ROOT / style["font_file"]
    shutil.copy2(font_src, comp / font_src.name)
    cap, ttl = style["captions"], style["title"]
    color = style.get("text_color", "#FFFFFF")
    _, cap_cy = to_px(0, cap["y"])
    _, title_cy = to_px(0, ttl["y"])
    outline = ("0 0 8px #000, 4px 4px 0 #000, -4px -4px 0 #000, "
               "4px -4px 0 #000, -4px 4px 0 #000")
    css = f"""
      /* tiktok-edit style: {style['name']} */
      @font-face {{ font-family: "{font}"; src: url("{font_src.name}"); }}
      .caption, .caption.split {{
        bottom: auto; top: {cap_cy - cap['size_px'] * 0.6:.0f}px;
        font-family: "{font}", sans-serif;
      }}
      .caption .w, .caption .w.em {{
        font-size: {cap['size_px']}px; color: {color};
      }}
      .tt-title {{
        position: absolute; left: 6%; width: 88%;
        top: {title_cy:.0f}px; transform: translateY(-50%);
        text-align: center; color: {color};
        font-family: "{font}", sans-serif; font-size: {ttl['size_px']}px;
        line-height: 1.08; text-shadow: {outline};
      }}
"""
    doc = doc.replace("    </style>", css + "    </style>", 1)

    clips = []
    if args.title:
        lines = args.title.replace("\\n", "\n").split("\n")
        if len(lines) > ttl.get("max_lines", 2):
            print(f"note: {len(lines)} title lines; the style uses "
                  f"{ttl.get('max_lines', 2)}", file=sys.stderr)
        inner = "<br>".join(html.escape(x.strip()) for x in lines)
        clips.append(
            f'      <div id="tt-title" class="clip" data-start="0" '
            f'data-duration="{duration:.2f}" data-track-index="{TRACK_TITLE}">\n'
            f'        <div class="tt-title">{inner}</div>\n      </div>')

    floats_path = studio / "floats.json"
    floats = json.loads(floats_path.read_text())["floats"] if floats_path.is_file() else []
    for i, f in enumerate(floats):
        src = Path(f["file"])
        shutil.copy2(src, comp / src.name)
        # Sized the way CapCut sizes it (fit to frame width, then scale), so
        # the MP4 and the CapCut project put the card in the same place.
        w = W * f["scale"]
        h = f["height"] * w / max(1, f["width"])
        cx, cy = to_px(f["x"], f["y"])
        dur = float(f["end"]) - float(f["start"])
        clips.append(
            f'      <video id="tt-float{i}" class="clip" muted src="{html.escape(src.name)}"\n'
            f'             data-start="{float(f["start"]):.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="{TRACK_FLOAT + i}"\n'
            f'             style="position:absolute;left:{cx - w / 2:.0f}px;'
            f'top:{cy - h / 2:.0f}px;width:{w:.0f}px;height:{h:.0f}px;'
            f'border-radius:14px;box-shadow:0 10px 40px rgba(0,0,0,.45);"></video>')

    anchor = "    </div>\n\n    <script>"
    if anchor not in doc:
        die("unexpected composition layout (no root close); has i-hate-editing "
            "changed compose.py?")
    doc = doc.replace(anchor, "\n".join(clips) + "\n" + anchor, 1)
    page.write_text(MARK + "\n" + doc)
    print(f"styled {page}: {style['name']} · captions at y={cap_cy:.0f}px"
          f"{' · title' if args.title else ''} · {len(floats)} card(s)")

    if not args.render:
        return 0
    ihe = ihe_dir()
    if not ihe:
        die("i-hate-editing not found (set IHE_DIR)")
    sys.path.insert(0, str(ihe / "scripts"))
    from compose import HYPERFRAMES_PKG  # noqa: E402
    out = (studio / "out").resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Same settings as compose.py --render: high quality, PNG frame extraction.
    cmd = ["npx", "--yes", HYPERFRAMES_PKG, "render", ".", "-q", "high",
           "--crf", "16", "--video-frame-format", "png"]
    if args.low_memory:
        cmd.append("--low-memory-mode")
    r = subprocess.run(cmd + ["-o", str(out / "master.mp4")], cwd=comp,
                       capture_output=True, text=True, errors="replace")
    print((r.stdout or "")[-800:].strip() or (r.stderr or "")[-800:])
    if r.returncode != 0:
        return 1
    print(f"-> {out / 'master.mp4'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
