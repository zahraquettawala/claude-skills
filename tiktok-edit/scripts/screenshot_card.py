#!/usr/bin/env python3
"""Turn a screenshot into a floating card clip, with its pop/whoosh.

    screenshot_card.py chat.png --studio studio --start 6.2 --duration 3
    screenshot_card.py chat.png --studio studio --start 6.2 --crop 0,310,1170,420

Crop first to just the part that matters (one message, one number): --crop
x,y,w,h in pixels of the screenshot. The card is scaled to 968 px wide with a
4 px border, turned into a short still clip with silent audio, and written
into <studio>/assets/cards/.

It is registered in <studio>/floats.json (cards floated over the speaker,
placed by apply_style.py and capcut_export.py), and a pop/whoosh is added to
<studio>/sfx.json starting 0.17 s before the card, so the peak lands as it
appears. Run once per card.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import die, probe, sh  # noqa: E402

STYLE = json.loads((Path(__file__).resolve().parent.parent / "styles" /
                    "shivani.json").read_text())["cards"]
POP_LEN = 0.35


def pop_whoosh(dst):
    """0.35 s: a band-passed noise swell into a short decaying chirp at 0.18 s,
    peak-normalised. The same recipe as Shivani's skill, in ffmpeg."""
    expr = ("0.55*(random(0)*2-1)*if(lt(t\\,0.18)\\,pow(t/0.18\\,2)\\,exp(-(t-0.18)*28))"
            "+if(gte(t\\,0.18)\\,0.9*sin(2*PI*(900+500*(t-0.18))*(t-0.18))"
            "*exp(-(t-0.18)*22)\\,0)")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
        f"aevalsrc=exprs='{expr}':s=48000:d={POP_LEN}",
        "-af", "highpass=f=250,lowpass=f=7000,alimiter=limit=0.98:level=true",
        "-ac", "2", str(dst)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--studio", default="studio")
    ap.add_argument("--start", type=float, required=True,
                    help="output-timeline second the card appears")
    ap.add_argument("--duration", type=float, default=3.0)
    ap.add_argument("--crop", default=None, help="x,y,w,h in screenshot pixels")
    ap.add_argument("--border", default="white")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    img = Path(args.image)
    if not img.is_file():
        die(f"no image at {img}")
    if not STYLE["seconds"][0] <= args.duration <= STYLE["seconds"][1]:
        print(f"note: cards read best at {STYLE['seconds'][0]}-"
              f"{STYLE['seconds'][1]} s", file=sys.stderr)
    studio = Path(args.studio)
    out_dir = studio / "assets" / "cards"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = args.name or img.stem
    clip = out_dir / f"{name}.mp4"

    w, b = STYLE["width_px"], STYLE["border_px"]
    vf = []
    if args.crop:
        x, y, cw, ch = (int(v) for v in args.crop.split(","))
        vf.append(f"crop={cw}:{ch}:{x}:{y}")
    vf += [f"scale={w - 2 * b}:-2:flags=lanczos",
           f"pad=iw+{2 * b}:ih+{2 * b}:{b}:{b}:color={args.border}",
           "format=yuv420p"]
    secs = max(6.0, args.duration + 1)
    sh(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{secs}",
        "-r", "30", "-vf", ",".join(vf), "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-shortest", str(clip)], check=True)
    info = probe(clip)

    pop = studio / "assets" / "sfx" / "pop_whoosh.wav"
    if not pop.is_file():
        pop.parent.mkdir(parents=True, exist_ok=True)
        pop_whoosh(pop)

    floats_path = studio / "floats.json"
    floats = json.loads(floats_path.read_text()) if floats_path.is_file() else {"floats": []}
    floats["floats"] = [f for f in floats["floats"] if f["file"] != str(clip.resolve())]
    floats["floats"].append({"file": str(clip.resolve()), "start": args.start,
                             "end": round(args.start + args.duration, 3),
                             "width": info["w"], "height": info["h"],
                             "scale": STYLE["scale"], "x": STYLE["x"], "y": STYLE["y"]})
    floats["floats"].sort(key=lambda f: f["start"])
    floats_path.write_text(json.dumps(floats, indent=2))

    sfx_path = studio / "sfx.json"
    sfx = json.loads(sfx_path.read_text()) if sfx_path.is_file() else {"sounds": []}
    hit = round(args.start, 3)
    sfx["sounds"] = [s for s in sfx["sounds"]
                     if not (s.get("category") == "card_pop" and s.get("hit_at") == hit)]
    sfx["sounds"].append({"file": str(pop.resolve()), "category": "card_pop",
                          "why": f"card {name}", "hit_at": hit,
                          "start": round(max(0.0, args.start - STYLE["sfx_lead"]), 3),
                          "duration": POP_LEN, "track": 21, "volume": 1.0,
                          "peak_offset": STYLE["sfx_lead"]})
    sfx["sounds"].sort(key=lambda s: s["start"])
    sfx_path.write_text(json.dumps(sfx, indent=2))

    print(f"{img.name} -> {clip} ({info['w']}x{info['h']}), "
          f"{args.start:.2f}-{args.start + args.duration:.2f}s, pop at "
          f"{max(0.0, args.start - STYLE['sfx_lead']):.2f}s")
    if len(floats["floats"]) > STYLE["count"][1]:
        print(f"note: {len(floats['floats'])} cards; {STYLE['count'][0]}-"
              f"{STYLE['count'][1]} is the style's range", file=sys.stderr)


if __name__ == "__main__":
    main()
