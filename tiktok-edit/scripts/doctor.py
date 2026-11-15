#!/usr/bin/env python3
"""Check what this machine can do before an edit, and say what falls back.

    python3 scripts/doctor.py
    python3 scripts/doctor.py --json

i-hate-editing does the heavy lifting. A few of its steps depend on its
author's own setup (an Adobe Podcast session in ego-browser, a local Gemini
proxy, a separate broll-gen skill). Those are reported as optional with the
fallback this skill uses, so a missing one never stalls an edit.
"""

import argparse
import json
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ihe_dir, sh  # noqa: E402


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def has_module(name):
    return sh([sys.executable, "-c", f"import {name}"]).returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ihe = ihe_dir()
    whisper = next((b for b in ("whisper-cli", "whisper-cpp", "main")
                    if shutil.which(b)), None)
    checks = {
        "i-hate-editing": (str(ihe) if ihe else None, True,
                           "install it: see install.md in this skill"),
        "ffmpeg": (shutil.which("ffmpeg"), True, "brew/apt install ffmpeg"),
        "ffprobe": (shutil.which("ffprobe"), True, "ships with ffmpeg"),
        "whisper.cpp": (whisper, True,
                        "brew install whisper-cpp (needed for any speech)"),
        "node": (shutil.which("node"), True,
                 "Node 22+: captions and cards render through HyperFrames"),
        "numpy": ("yes" if has_module("numpy") else None, False,
                  "uv pip install numpy (only for music_beats.py)"),
        "pycapcut (CapCut export)": ("yes" if has_module("pycapcut") else None,
                                     False, 'pip install "pycapcut==0.0.4"'),
        "yt-dlp": (shutil.which("yt-dlp"), False, "optional, reference clips"),
        "ego-browser (Adobe Enhance)": (shutil.which("ego-browser"), False,
                                        "fallback: scripts/voice_clean.py"),
        "Gemini proxy :8081 (gen_image)": (
            "listening" if port_open("127.0.0.1", 8081) else None, False,
            "fallback: real B-roll, a designed scene, or a card"),
        "broll-gen skill": (
            str(Path("~/.claude/skills/broll-gen").expanduser())
            if Path("~/.claude/skills/broll-gen").expanduser().is_dir() else None,
            False, "fallback: footage the user supplied"),
    }

    here = str(Path(__file__).resolve().parent.parent)
    if args.json:
        print(json.dumps({"tiktok-edit": here, **{
            k: {"found": v[0], "required": v[1], "fix": v[2]}
            for k, v in checks.items()}}, indent=2))
    else:
        print(f"TT   {'tiktok-edit (this skill)':<32} {here}")
        for name, (found, required, fix) in checks.items():
            mark = "ok  " if found else ("MISS" if required else "--  ")
            print(f"{mark} {name:<32} {found or fix}")
    missing = [k for k, v in checks.items() if v[1] and not v[0]]
    if missing:
        print(f"\nrequired missing: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
