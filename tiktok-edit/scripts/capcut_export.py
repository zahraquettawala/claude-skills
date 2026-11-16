#!/usr/bin/env python3
"""Export the edit as an editable CapCut project (draft).

The MP4 from tiktok_export.py is the finished video. This is the same edit as
a CapCut timeline, for fixing things by hand: every cut is a real clip you can
trim, captions and cards are text you can restyle, and B-roll, sound effects
and music sit on their own tracks.

    capcut_export.py --studio studio --name "my tiktok"
    capcut_export.py --studio studio --drafts "<CapCut drafts folder>"
    capcut_export.py --studio studio --voice-from-cut     # keep the cleaned voice

Run it on the computer that has CapCut desktop, with CapCut CLOSED, then open
CapCut and the project appears in the list (restart CapCut if it does not).
Built on pyCapCut (pip install pycapcut==0.0.4), which writes CapCut's
project format. That format is undocumented: pyCapCut's author verifies it
against CapCut for Windows, and a CapCut update can break it. The MP4 export
never depends on this.

Reads what the pipeline already wrote in <studio>/:
  edl.json + timeline.json   the cuts                -> main video track
  broll.json                 overlays and scenes     -> overlay video track(s)
  captions.json              captions                -> "captions" text track
  cards.json                 hook and headline cards -> "cards" text track
  sfx.json                   sound effects           -> sfx audio track(s)
  edl.json "music"           montage track           -> music audio track
  --music FILE               a music bed             -> music audio track

Every media file is copied into the project's own media/ folder, so the
project still opens after the studio folder is cleaned up.

What does not carry over (it is baked into the MP4 instead): the colour
grade, HyperFrames card designs and animations, proof-page zooms, and the
split-screen face move under half-screen panels. Cards come across as plain
editable text in the same place and time; restyle them in CapCut if needed.
"""

import argparse
import json
import os
import platform
import re
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import H, W, die, probe, sh  # noqa: E402

US = 1_000_000

# Text positions, in CapCut's units (transform_y: half canvas heights from the
# centre, up is positive). The caption line matches i-hate-editing's 27% from
# the bottom; cards sit in the upper third, below TikTok's top bar.
CAPTION_Y = -0.46
CARD_Y = 0.42
TEXT_WIDTH = 0.80     # share of frame width; keeps text clear of the side zones
# Words this short ride with the next word in one-word captions, so nothing
# flashes on screen for a single frame.
TINY = {"a", "an", "the", "i", "to", "of", "in", "on", "at", "is", "it", "my",
        "your", "and", "or", "so", "be", "we"}
ROOT = Path(__file__).resolve().parent.parent


def default_drafts():
    home = Path.home()
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        cands = [base / "CapCut/User Data/Projects/com.lveditor.draft"]
    elif platform.system() == "Darwin":
        cands = [home / "Movies/CapCut/User Data/Projects/com.lveditor.draft",
                 home / "Library/Containers/com.lemon.lvoverseas/Data/Movies/"
                        "CapCut/User Data/Projects/com.lveditor.draft"]
    else:
        cands = []
    return next((c for c in cands if c.is_dir()), None)


def capcut_running():
    if platform.system() == "Windows":
        out = sh(["tasklist"]).stdout.lower()
    else:
        out = sh(["ps", "-A", "-o", "comm="]).stdout.lower()
    return "capcut" in out


def load(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.is_file() else default


class Media:
    """Copies each source once into the project's media/ folder."""

    def __init__(self, cc, folder):
        self.cc, self.folder, self.done = cc, folder, {}
        folder.mkdir(parents=True, exist_ok=True)

    def _copy(self, src):
        src = Path(src).expanduser().resolve()
        if not src.is_file():
            die(f"media not found: {src}")
        if src not in self.done:
            dst = self.folder / f"{len(self.done):03d}_{src.name}"
            shutil.copy2(src, dst)
            self.done[src] = dst
        return self.done[src]

    def video(self, src):
        return self.cc.VideoMaterial(str(self._copy(src)))

    def audio(self, src):
        return self.cc.AudioMaterial(str(self._copy(src)))


class Lanes:
    """Tracks of one type, opened on demand so segments never overlap
    (a CapCut track holds one clip at a time)."""

    def __init__(self, script, kind, prefix):
        self.script, self.kind, self.prefix, self.ends = script, kind, prefix, []

    def add(self, seg):
        start, end = seg.target_timerange.start, seg.target_timerange.end
        for i, last in enumerate(self.ends):
            if start >= last:
                self.ends[i] = end
                return self.script.add_segment(seg, f"{self.prefix}{i + 1}")
        self.ends.append(end)
        name = f"{self.prefix}{len(self.ends)}"
        self.script.add_track(self.kind, name)
        self.script.add_segment(seg, name)


def us(t):
    return int(round(float(t) * US))


def zoom_settings(cc, zoom, zoom_y):
    """i-hate-editing's punch-in crop (render.py) as a CapCut scale + move."""
    if zoom <= 1.001:
        return None
    centre = (1 - 1 / zoom) * zoom_y + 1 / (2 * zoom)
    return cc.ClipSettings(scale_x=zoom, scale_y=zoom,
                           transform_y=(centre - 0.5) * 2 * zoom)


def clamp_source(mat, start, end):
    end = min(end, mat.duration)
    return start, max(start + 1, end)


def plain(text):
    return re.sub(r"\*([^*]+)\*", r"\1", text or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--studio", default="studio")
    ap.add_argument("--name", default=None, help="project name in CapCut")
    ap.add_argument("--drafts", default=None, help="CapCut's drafts folder")
    ap.add_argument("--voice-from-cut", action="store_true",
                    help="mute the clips and lay the rendered cut's audio "
                         "(cleaned voice) as one track instead")
    ap.add_argument("--music", default=None)
    ap.add_argument("--music-level", type=float, default=0.15)
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--style", default=None,
                    help="a preset from styles/ (e.g. shivani): one-word "
                         "captions, font, held title, card placement")
    ap.add_argument("--title-seconds", type=float, default=None,
                    help="show the title for this long only; default from the style")
    ap.add_argument("--title", default=None,
                    help='title held for the whole video: "line one\\nline two"')
    ap.add_argument("--mac", action="store_true", default=platform.system() == "Darwin",
                    help="also write draft_info.json (Mac CapCut's project file); "
                         "on by default on macOS")
    ap.add_argument("--force", action="store_true",
                    help="replace a project with the same name; write even "
                         "if CapCut seems to be running")
    args = ap.parse_args()

    try:
        import pycapcut as cc
    except ImportError:
        die("pyCapCut is not installed: pip install pycapcut==0.0.4")

    studio = Path(args.studio).resolve()
    edl = load(studio / "edl.json") or die(f"no edl.json in {studio}")
    tl = load(studio / "timeline.json") or die(
        "no timeline.json: render the cut first (render.py or music_beats.py render)")
    drafts = Path(args.drafts).expanduser() if args.drafts else default_drafts()
    if not drafts or not drafts.is_dir():
        die("could not find CapCut's drafts folder. Open CapCut > Settings > "
            "'Drafts location', and pass that folder with --drafts")
    if capcut_running() and not args.force:
        die("CapCut is open. Close it first: it overwrites project files it "
            "has loaded (or pass --force)")
    name = args.name or f"{studio.parent.name} tiktok"

    folder = cc.DraftFolder(str(drafts))
    try:
        script = folder.create_draft(name, W, H, fps=int(edl.get("fps", 30)),
                                     allow_replace=args.force)
    except FileExistsError:
        die(f"a CapCut project called '{name}' exists; pass --name or --force")
    try:
        report = build(cc, script, drafts / name, studio, edl, tl, args)
    except BaseException:
        # A half-written project shows up in CapCut as a broken entry.
        shutil.rmtree(drafts / name, ignore_errors=True)
        raise
    script.save()
    if args.mac and args.style:
        report.append(fix_font(cc, drafts, name, args.style))
    finish(drafts, name, tl, args.mac)
    print(f"CapCut project '{name}' -> {drafts / name}")
    for r in report:
        print(f"  {r}")
    print("Open CapCut (restart it if the project is not listed). Grade, card "
          "designs and proof zooms are only in the MP4.")
    if args.style:
        print("If the text shows in the wrong font: in CapCut, add one text clip "
              "in that font once so CapCut downloads it, then reopen the project.")


def find_capcut_font(user_data, meta):
    """The font file CapCut downloaded for this resource, if it has."""
    hits = []
    for dirpath, _, files in os.walk(user_data):
        if "com.lveditor.draft" in dirpath:
            continue
        for f in files:
            if f.lower().endswith((".ttf", ".otf")) and (
                    meta.resource_id in dirpath or meta.md5 in dirpath
                    or meta.name.lower() in f.lower()):
                hits.append(Path(dirpath) / f)
    return hits[0] if hits else None


def fix_font(cc, drafts, name, style_name):
    """Point the project's text at a real font file on this Mac.

    pyCapCut's font entries carry a Windows path ("D:/..."). Mac CapCut reads
    the path, so text silently falls back to the default font. Prefer the file
    CapCut itself downloaded; otherwise the bundled copy, placed in the
    project's media folder."""
    style = json.loads((ROOT / "styles" / f"{style_name}.json").read_text())
    meta = getattr(cc.FontType, style["font"]).value
    project = drafts / name
    font = find_capcut_font(drafts.parents[1], meta)
    how = "CapCut's downloaded copy"
    if not font:
        font = project / "media" / Path(style["font_file"]).name
        shutil.copy2(ROOT / style["font_file"], font)
        how = "the copy bundled with this skill"

    def walk(node):
        if isinstance(node, dict):
            if node.get("id") == meta.resource_id and "path" in node:
                node["path"] = str(font.resolve())
            for k, v in node.items():
                if k == "content" and isinstance(v, str) and v.startswith("{"):
                    inner = json.loads(v)
                    walk(inner)
                    node[k] = json.dumps(inner, ensure_ascii=False)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    content = project / "draft_content.json"
    doc = json.loads(content.read_text())
    walk(doc)
    content.write_text(json.dumps(doc, ensure_ascii=False))
    return f"font {style['font']} from {how}"


def finish(drafts, name, tl, mac):
    """Fill the project's meta file and write the Mac file names.

    pyCapCut copies a fixed meta template: every project would share one
    draft_id and have no name or folder, which CapCut can treat as the same
    project. Mac CapCut reads draft_info.json (with a .bak beside it) where
    Windows reads draft_content.json; writing all three is harmless."""
    project = drafts / name
    meta_path = project / "draft_meta_info.json"
    meta = json.loads(meta_path.read_text())
    now = int(time.time() * US)
    meta.update({"draft_id": str(uuid.uuid4()).upper(), "draft_name": name,
                 "draft_fold_path": str(project.resolve()),
                 "draft_root_path": str(drafts.resolve()),
                 "tm_draft_create": now, "tm_draft_modified": now,
                 "tm_duration": us(tl.get("predicted_duration", 0))})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))
    if mac:
        content = project / "draft_content.json"
        shutil.copy2(content, project / "draft_info.json")
        shutil.copy2(content, project / "draft_info.json.bak")


def word_chunks(text, start, end):
    """Split a caption chunk into one-word captions, timed by word length."""
    words = text.split()
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if w.lower().strip(".,!?'\"") not in TINY:
            groups.append(" ".join(cur))
            cur = []
    if cur:
        if groups:
            groups[-1] += " " + " ".join(cur)
        else:
            groups.append(" ".join(cur))
    weights = [len(g) + 2 for g in groups]
    total, t, out = sum(weights), start, []
    for g, wgt in zip(groups, weights):
        d = (end - start) * wgt / total
        out.append((g, t, t + d))
        t += d
    return out


def build(cc, script, project, studio, edl, tl, args):
    media = Media(cc, project / "media")
    style = (json.loads((ROOT / "styles" / f"{args.style}.json").read_text())
             if args.style else None)
    montage = bool(edl.get("montage"))
    mute_clips = montage or args.voice_from_cut
    report = []

    # Main track: one clip per cut, from the original source, so trimming a
    # clip in CapCut trims its sound with it.
    script.add_track(cc.TrackType.video, "main")
    ranges = edl.get("ranges", [])
    for seg in tl["segments"]:
        src = edl["sources"].get(seg["source"], seg["source"])
        mat = media.video(src)
        out0, out1 = us(seg["out_start"]), us(seg["out_end"])
        s0, s1 = us(seg["source_start"]), us(seg["source_end"])
        # Rendered lengths are frame-rounded, so source/out drifts a percent
        # off the edit's real speed. Snap back to it: CapCut would otherwise
        # play the clip at 0.99x and shift the voice's pitch.
        nominal = float(edl.get("speed", 1.0))
        if abs((s1 - s0) / max(1, out1 - out0) / nominal - 1) < 0.03:
            s1 = s0 + round((out1 - out0) * nominal)
        s0, s1 = clamp_source(mat, s0, s1)
        r = ranges[seg["index"]] if seg["index"] < len(ranges) else {}
        script.add_segment(cc.VideoSegment(
            mat, cc.Timerange(out0, out1 - out0),
            source_timerange=cc.Timerange(s0, s1 - s0),
            volume=0.0 if mute_clips else 1.0,
            clip_settings=zoom_settings(cc, float(r.get("zoom", 1.0)),
                                        float(r.get("zoom_y", 0.42)))), "main")
    report.append(f"{len(tl['segments'])} cut(s) on the main track")

    # B-roll and rendered scenes above the main track.
    overlays = (load(studio / "broll.json", {}) or {}).get("overlays", [])
    if overlays:
        lanes = Lanes(script, cc.TrackType.video, "overlay ")
        for o in overlays:
            f = Path(o["file"])
            mat = media.video(f if f.is_absolute() else studio / f)
            dur = us(float(o["end"]) - float(o["start"]))
            settings = None if o.get("full") else cc.ClipSettings(
                scale_x=1.0, scale_y=1.0, transform_y=0.5)
            lanes.add(cc.VideoSegment(
                mat, cc.Timerange(us(o["start"]), min(dur, mat.duration)),
                volume=0.0, clip_settings=settings))
        report.append(f"{len(overlays)} overlay(s)")

    # Screenshot cards floated over the speaker (screenshot_card.py).
    floats = (load(studio / "floats.json", {}) or {}).get("floats", [])
    if floats:
        lanes = Lanes(script, cc.TrackType.video, "cards ")
        for f in floats:
            mat = media.video(f["file"])
            dur = us(float(f["end"]) - float(f["start"]))
            # CapCut fits a clip to the frame width before applying scale, so
            # 0.7 is 70% of 1080 px whatever the card's own width.
            sc = float(f["scale"])
            lanes.add(cc.VideoSegment(
                mat, cc.Timerange(us(f["start"]), min(dur, mat.duration)),
                volume=0.0, clip_settings=cc.ClipSettings(
                    scale_x=sc, scale_y=sc, transform_x=float(f["x"]),
                    transform_y=float(f["y"]))))
        report.append(f"{len(floats)} screenshot card(s)")

    # Audio.
    audio = Lanes(script, cc.TrackType.audio, "audio ")
    cut = Path(tl.get("output") or studio / "cut.mp4")
    clean = cut.with_name(cut.stem + "_clean.mp4")
    cut = clean if clean.is_file() else cut
    if args.voice_from_cut and not probe(cut)["audio"]:
        report.append(f"no voice track: {cut.name} has no audio")
    elif args.voice_from_cut:
        wav = studio / "capcut_voice.wav"
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cut), "-vn",
            "-ar", "48000", "-ac", "2", str(wav)], check=True)
        mat = media.audio(wav)
        audio.add(cc.AudioSegment(mat, cc.Timerange(0, mat.duration)))
        wav.unlink(missing_ok=True)
        report.append(f"voice from {cut.name}")
    music = edl.get("music") if montage else None
    if music or args.music:
        track = args.music or music["track"]
        mat = media.audio(track)
        start = us((music or {}).get("start", 0.0)) if not args.music else 0
        length = min(us(tl["predicted_duration"]), mat.duration - start)
        seg = cc.AudioSegment(mat, cc.Timerange(0, length),
                              source_timerange=cc.Timerange(start, length),
                              volume=1.0 if (music and not args.music) else args.music_level)
        seg.add_fade("0s", "0.5s")
        audio.add(seg)
        report.append(f"music: {Path(track).name}")
    sounds = (load(studio / "sfx.json", {}) or {}).get("sounds", [])
    for s in sounds:
        mat = media.audio(s["file"])
        audio.add(cc.AudioSegment(
            mat, cc.Timerange(us(s["start"]), min(us(s["duration"]), mat.duration)),
            volume=float(s.get("volume", 0.6))))
    if sounds:
        report.append(f"{len(sounds)} sound effect(s)")

    # Text.
    font = getattr(cc.FontType, style["font"], None) if style else None
    cap_size = style["captions"]["capcut_size"] if style else 9.0
    cap_y = style["captions"]["y"] if style else CAPTION_Y
    caption_style = cc.TextStyle(size=cap_size, bold=not style, align=1,
                                 auto_wrapping=True, max_line_width=TEXT_WIDTH)
    border = cc.TextBorder(width=40.0)
    caps = (load(studio / "captions.json", {}) or {}).get("chunks", [])
    if caps and not args.no_captions:
        if style and style["captions"]["words"] == 1:
            pieces = [p for c in caps
                      for p in word_chunks(c["text"], float(c["start"]), float(c["end"]))]
        else:
            pieces = [(c["text"], float(c["start"]), float(c["end"])) for c in caps]
        script.add_track(cc.TrackType.text, "captions")
        last, n = 0, 0
        for text, t0, t1 in pieces:
            a = max(us(t0), last)
            b = us(t1)
            if b - a < 30_000:
                continue
            script.add_segment(cc.TextSegment(
                text, cc.Timerange(a, b - a), font=font, style=caption_style,
                border=border, clip_settings=cc.ClipSettings(transform_y=cap_y)),
                "captions")
            last, n = b, n + 1
        report.append(f"{n} caption(s)")
    if args.title:
        ttl = style["title"] if style else {"y": CARD_Y, "capcut_size": 11.0}
        script.add_track(cc.TrackType.text, "title")
        script.add_segment(cc.TextSegment(
            args.title.replace("\\n", "\n"),
            cc.Timerange(0, us(min(tl["predicted_duration"], args.title_seconds or (
                tl["predicted_duration"] if ttl.get("whole_video", True)
                else float(ttl.get("seconds", 3.0)))))), font=font,
            style=cc.TextStyle(size=ttl["capcut_size"], align=1,
                               auto_wrapping=True, max_line_width=TEXT_WIDTH),
            border=border, clip_settings=cc.ClipSettings(transform_y=ttl["y"])),
            "title")
        report.append("title" + ("" if args.title_seconds or not ttl.get("whole_video", True)
                                 else " held for the whole video"))
    cards = (load(studio / "cards.json", {}) or {}).get("cards", [])
    if cards:
        lanes = Lanes(script, cc.TrackType.text, "cards ")
        card_style = cc.TextStyle(size=13.0, bold=True, align=1, auto_wrapping=True,
                                  max_line_width=TEXT_WIDTH)
        for c in cards:
            lines = [plain(c.get(k)) for k in ("kicker", "big", "sub")]
            lines += [plain(i.get("title")) for i in c.get("items") or []]
            text = "\n".join(x for x in lines if x)
            if not text:
                continue
            lanes.add(cc.TextSegment(
                text, cc.Timerange(us(c["start"]), us(c["duration"])),
                style=card_style, border=border,
                clip_settings=cc.ClipSettings(transform_y=0.0 if c.get("full") else CARD_Y)))
        report.append(f"{len(cards)} card(s) as text")
    return report


if __name__ == "__main__":
    main()
