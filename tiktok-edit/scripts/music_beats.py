#!/usr/bin/env python3
"""Beat-synced montage cutting: find the beats, cut on them, lay the track.

i-hate-editing times everything from speech. A montage has no speech; the
music is the clock instead. Same principle (audio is the authority on time),
different audio.

    music_beats.py analyze track.mp3 -o studio/beats.json
    music_beats.py edl    --beats studio/beats.json --clips studio/clips.json
    music_beats.py render --studio studio                  # -> studio/cut.mp4
    music_beats.py mux    studio/cut.mp4 other.mp3 --edl studio/edl.json -o x.mp4

`analyze` writes tempo, every beat, the downbeats (bar starts) and the
strongest onsets (drops, hits), each in seconds of the track.

`edl` reads a clips.json you write after looking at contact sheets:

    {"start_beat": 0, "clips": [
      {"source": "/abs/fitted/a.mp4", "in": 3.2, "beats": 4},
      {"source": "/abs/fitted/b.mp4", "in": 0.8, "beats": 2},
      {"source": "/abs/fitted/c.mp4", "in": 5.0, "beats": 1, "beat": "DROP"}
    ]}

Each clip holds for `beats` beats from its `in` point. Cuts land on
frame-rounded beat times on the OUTPUT timeline. `start_beat` picks where in
the track the edit begins (use a downbeat).

`render` cuts the EDL frame-exact and lays the track under it. Do NOT use
i-hate-editing's render.py for a montage: it concatenates segments that each
carry their own AAC audio, and the encoder padding adds ~17ms per seam, which
is invisible under speech and half a second off the beat after thirty cuts.
Here the segments are video-only with exact frame counts, so the grid holds.
It also writes timeline.json in render.py's shape, so i-hate-editing's
captions, compose and beats scripts read the cut as usual.

`mux` re-lays a different track (or the same one at another level) without
re-cutting.

Needs numpy for `analyze`.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import FPS, die, probe, sh  # noqa: E402

SR = 22050
HOP = 512
NFFT = 1024
TIGHTNESS = 6.0     # how hard the tracker holds tempo against stray onsets


def decode(path):
    import numpy as np
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if p.returncode != 0 or not p.stdout:
        die(f"could not decode {path}")
    return np.frombuffer(p.stdout, dtype=np.float32)


def hop_time(i):
    """Seconds for envelope index i. Frames are timed at their centre: timed at
    their start, every onset read about a window early."""
    return (i * HOP + NFFT / 2) / SR


def onset_envelope(y, max_hz=None):
    """Log-magnitude spectral flux, half-wave rectified, one value per hop.
    `max_hz` keeps only the bins below it (the kick band, for downbeats)."""
    import numpy as np
    n = 1 + (len(y) - NFFT) // HOP
    if n < 8:
        die("track too short to analyse")
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = y[idx] * np.hanning(NFFT)[None, :]
    mag = np.log1p(10.0 * np.abs(np.fft.rfft(frames, axis=1)))
    if max_hz:
        mag = mag[:, :max(2, int(max_hz * NFFT / SR))]
    flux = np.maximum(0.0, np.diff(mag, axis=0)).sum(axis=1)
    flux = np.concatenate([[0.0], flux])
    # Remove the slow trend so loud sections do not swamp quiet ones.
    k = max(1, int(0.5 * SR / HOP))
    trend = np.convolve(flux, np.ones(k) / k, mode="same")
    env = np.maximum(0.0, flux - trend)
    return env / (env.max() or 1.0)


def estimate_period(env, lo_bpm=70, hi_bpm=180):
    """Tempo from the onset autocorrelation, scored on a fine BPM grid.

    Integer-hop lags are too coarse (one hop is ~23ms) and a hi-hat on the
    off-beat puts a strong peak at 3/2 of the beat, so each candidate is scored
    by the autocorrelation at its period AND its multiples, read with
    interpolation."""
    import numpy as np
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    ac = ac / (ac[0] or 1.0)
    fps = SR / HOP
    lags = np.arange(len(ac), dtype=float)
    grid = np.arange(lo_bpm, hi_bpm + 0.01, 0.25)
    period = 60.0 * fps / grid
    score = sum(np.interp(k * period, lags, ac) / k for k in (1, 2, 3, 4))
    # Weight toward ~120 BPM so half/double-time ambiguity resolves the way
    # editors count (a log-normal prior, as in most beat trackers).
    score = score * np.exp(-0.5 * (np.log2(grid / 120.0) / 1.0) ** 2)
    best = int(np.argmax(score))
    return float(period[best]), float(grid[best])


def track_beats(env, period):
    """Dynamic-programming beat tracker (Ellis 2007), period in hops."""
    import numpy as np
    n = len(env)
    score = env.copy()
    back = np.full(n, -1)
    lo, hi = int(round(period * 0.5)), int(round(period * 2.0))
    offs = np.arange(lo, hi + 1).astype(float)
    penalty = -TIGHTNESS * (np.log(offs / period)) ** 2
    for t in range(hi, n):
        prev = t - offs.astype(int)
        cand = score[prev] + penalty
        j = int(np.argmax(cand))
        score[t] = env[t] + cand[j]
        back[t] = prev[j]
    # Start from the best-scoring frame in the last period and walk back.
    t = int(n - hi + np.argmax(score[n - hi:]))
    beats = []
    while t >= 0:
        beats.append(t)
        t = back[t]
    return np.array(beats[::-1])


def analyze(args):
    import numpy as np
    y = decode(args.track)
    env = onset_envelope(y)
    period, bpm = estimate_period(env)
    frames = track_beats(env, period)
    beats = [round(float(hop_time(f)), 3) for f in frames]
    # Downbeats: of the four phases, the one whose beats carry the most KICK
    # energy. Full-band energy picks the snare on 2 and 4 as often as the one.
    # A guess for 4/4 pop and EDM; listen before trusting it on anything else.
    low = onset_envelope(y, max_hz=150)
    phase = max(range(4), key=lambda p: float(low[frames[p::4]].mean()))
    downbeats = beats[phase::4]
    # Strongest onsets: local maxima in the top 3% of the envelope.
    thr = float(np.quantile(env, 0.97))
    peaks = [i for i in range(1, len(env) - 1)
             if env[i] >= thr and env[i] >= env[i - 1] and env[i] >= env[i + 1]]
    strong, last = [], -1e9
    for i in peaks:
        t = hop_time(i)
        if t - last >= 0.25:
            strong.append(round(t, 3))
            last = t
    out = {"track": str(Path(args.track).resolve()),
           "duration": round(len(y) / SR, 3), "tempo": round(bpm, 1),
           "beat_period": round(60.0 / bpm, 4), "beats": beats,
           "downbeats": downbeats, "strong_onsets": strong}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"{bpm:.1f} BPM · {len(beats)} beats · {len(downbeats)} bars · "
          f"{len(strong)} strong onsets · first downbeat {downbeats[0]:.2f}s"
          f"\n-> {args.out}")


def frame_round(t, fps):
    return round(t * fps) / fps


def build_edl(args):
    beats_doc = json.loads(Path(args.beats).read_text())
    beats = beats_doc["beats"]
    spec = json.loads(Path(args.clips).read_text())
    i0 = int(spec.get("start_beat", 0))
    if i0 >= len(beats):
        die("start_beat is past the end of the track")
    t0 = beats[i0]
    sources, ranges, cursor = {}, [], i0
    for n, c in enumerate(spec["clips"]):
        span = int(c.get("beats", 2))
        nxt = cursor + span
        if nxt >= len(beats):
            print(f"  note: track ends; stopping after {n} clips", file=sys.stderr)
            break
        out_a = frame_round(beats[cursor] - t0, args.fps)
        out_b = frame_round(beats[nxt] - t0, args.fps)
        dur = out_b - out_a
        src = str(Path(c["source"]).expanduser().resolve())
        info = probe(src)
        if not info["w"]:
            die(f"could not probe {src}")
        start = float(c.get("in", 0.0))
        if start + dur > info["duration"] + 1e-3:
            die(f"{Path(src).name}: in={start} + {dur:.2f}s runs past its "
                f"{info['duration']:.2f}s; move `in` earlier or use fewer beats")
        key = f"c{n:02d}_{Path(src).stem}"
        sources[key] = src
        ranges.append({"source": key, "start": round(start, 3),
                       "end": round(start + dur, 3),
                       "frames": int(round(dur * args.fps)),
                       "beat": c.get("beat") or f"b{cursor}",
                       "reason": f"{span} beat(s) from {beats[cursor]:.2f}s"})
        cursor = nxt
    edl = {"sources": sources, "ranges": ranges,
           "fps": args.fps, "montage": True,
           "music": {"track": beats_doc["track"], "start": t0,
                     "end": beats[cursor]}}
    Path(args.out).write_text(json.dumps(edl, indent=1))
    total = beats[cursor] - t0
    print(f"{len(ranges)} cuts · {total:.2f}s · track {t0:.2f}-{beats[cursor]:.2f}s"
          f"\n-> {args.out}")
    unfit = [k for k, v in sources.items()
             if (lambda i: (i["w"], i["h"]))(probe(v)) != (1080, 1920)]
    if unfit:
        print(f"note: not 1080x1920, fit with fit_vertical.py first: "
              f"{', '.join(unfit)}", file=sys.stderr)


def render(args):
    studio = Path(args.studio)
    edl = json.loads((Path(args.edl) if args.edl else studio / "edl.json").read_text())
    if not edl.get("montage"):
        die("not a montage EDL (write it with `music_beats.py edl`)")
    fps = int(edl.get("fps", FPS))
    work = studio / "segments"
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("mseg_*.mp4"):
        old.unlink()
    parts, timeline, cursor = [], [], 0
    for i, r in enumerate(edl["ranges"]):
        src = edl["sources"][r["source"]]
        n = int(r["frames"])
        dst = work / f"mseg_{i:03d}.mp4"
        # -ss before -i seeks to the keyframe and decodes forward: exact,
        # and -frames:v pins the length to the frame.
        sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{r['start']:.3f}",
            "-i", src, "-frames:v", str(n), "-an",
            "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                   f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-video_track_timescale", str(fps * 1000),
            str(dst)], check=True)
        got = int(sh(["ffprobe", "-v", "error", "-count_frames", "-select_streams",
                      "v:0", "-show_entries", "stream=nb_read_frames", "-of",
                      "csv=p=0", str(dst)]).stdout.strip() or 0)
        if got != n:
            die(f"segment {i} ({Path(src).name} @ {r['start']}) gave {got} "
                f"frames, wanted {n}: the source ends too early")
        timeline.append({"index": i, "beat": r.get("beat"), "source": r["source"],
                         "source_start": r["start"], "source_end": r["end"],
                         "out_start": round(cursor / fps, 3),
                         "out_end": round((cursor + n) / fps, 3)})
        cursor += n
        parts.append(dst)
    listfile = work / "concat.txt"
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    silent = work / "montage_video.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(listfile), "-c", "copy", str(silent)], check=True)
    out = Path(args.out) if args.out else studio / "cut.mp4"
    track = args.track or (edl.get("music") or {}).get("track")
    if track:
        lay(silent, track, (edl.get("music") or {}).get("start", 0.0), out, 1.0)
    else:
        silent.replace(out)
    (studio / "timeline.json").write_text(json.dumps({
        "output": str(out.resolve()), "speed": 1.0,
        "predicted_duration": round(cursor / fps, 3), "segments": timeline,
        "seams": [t["out_start"] for t in timeline[1:]]}, indent=2))
    print(f"{len(parts)} cuts · {cursor} frames · {cursor / fps:.3f}s"
          f"{' · track laid' if track else ' · no audio'}\n-> {out}")


def lay(video, track, start, out, level):
    """Lay `track` from `start` under `video`, trimmed and faded at the end."""
    dur = probe(video)["duration"]
    fade = min(0.5, dur / 4)
    af = (f"atrim=start={start:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,"
          f"afade=t=out:st={dur - fade:.3f}:d={fade:.3f}")
    if level != 1.0:
        af += f",volume={level}"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(track),
        "-filter_complex", f"[1:a]{af}[m]", "-map", "0:v:0", "-map", "[m]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(out)], check=True)


def mux(args):
    start = args.start
    if start is None and args.edl:
        start = (json.loads(Path(args.edl).read_text()).get("music")
                 or {}).get("start")
    lay(args.cut, args.track, start or 0.0, args.out, args.level)
    print(f"track from {start or 0.0:.2f}s laid -> {args.out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("track")
    a.add_argument("-o", "--out", default="studio/beats.json")
    e = sub.add_parser("edl")
    e.add_argument("--beats", required=True)
    e.add_argument("--clips", required=True)
    e.add_argument("-o", "--out", default="studio/edl.json")
    e.add_argument("--fps", type=int, default=FPS)
    r = sub.add_parser("render")
    r.add_argument("--studio", default="studio")
    r.add_argument("--edl")
    r.add_argument("--track", help="override the EDL's track")
    r.add_argument("-o", "--out")
    m = sub.add_parser("mux")
    m.add_argument("cut")
    m.add_argument("track")
    m.add_argument("--edl", help="read the track start from this EDL's music block")
    m.add_argument("--start", type=float, default=None,
                   help="track time (s) that lines up with the cut's frame 0")
    m.add_argument("--level", type=float, default=1.0)
    m.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    if args.cmd == "analyze":
        try:
            import numpy  # noqa: F401
        except ImportError:
            die("numpy is required: uv pip install numpy")
    {"analyze": analyze, "edl": build_edl, "render": render,
     "mux": mux}[args.cmd](args)


if __name__ == "__main__":
    main()
