#!/usr/bin/env python3
"""Contact sheets: how the agent looks at footage with nothing to transcribe.

Talking-head cuts are read from takes.md. B-roll, montage clips and silent
screen recordings have no transcript, so the agent picks in-points by looking
at a grid of frames instead. One sheet per clip, frames in reading order,
the time of each printed alongside (your ffmpeg may lack drawtext, so times
are listed, not burned in).

    contact_sheet.py clips/*.mp4 --out-dir studio/sheets
    contact_sheet.py long.mov --out-dir studio/sheets --every 2

Then Read each PNG. Pick `in` points from the times listed for each cell.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import probe, sh  # noqa: E402

COLS = 6
CELL_W = 180


def sheet(src, out_dir, every, max_cells):
    info = probe(src)
    dur = info["duration"]
    if not dur:
        print(f"skip {src}: no duration")
        return None
    step = every or max(0.25, dur / max_cells)
    n = min(max_cells, max(1, int(dur / step)))
    rows = math.ceil(n / COLS)
    cell_h = int(CELL_W * info["h"] / max(1, info["w"])) // 2 * 2
    out = Path(out_dir) / f"{Path(src).stem}.png"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-vf", f"fps=1/{step:.4f},scale={CELL_W}:{cell_h},"
               f"tile={COLS}x{rows}:padding=4:margin=4:color=0x202020",
        "-frames:v", "1", str(out)], check=True)
    times = [round(step * i + step / 2, 2) for i in range(n)]
    print(f"{Path(src).name}: {dur:.1f}s {info['w']}x{info['h']} -> {out}")
    print("  " + "  ".join(f"[{i + 1}]{t}s" for i, t in enumerate(times)))
    return {"clip": str(Path(src).resolve()), "sheet": str(out),
            "duration": dur, "size": [info["w"], info["h"]],
            "cols": COLS, "times": times}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--out-dir", default="studio/sheets")
    ap.add_argument("--every", type=float, default=None,
                    help="seconds between frames (default: fit --cells)")
    ap.add_argument("--cells", type=int, default=24)
    args = ap.parse_args()
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    index = [s for s in (sheet(p, args.out_dir, args.every, args.cells)
                         for p in args.sources) if s]
    (Path(args.out_dir) / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
