# Install

This skill sits on top of i-hate-editing. Install both.

## 1. i-hate-editing

```bash
git clone https://github.com/ranahaani/i-hate-editing ~/Developer/i-hate-editing
ln -sfn ~/Developer/i-hate-editing ~/.claude/skills/i-hate-editing
cd ~/Developer/i-hate-editing
uv venv .venv && uv pip install --python .venv playwright pillow
.venv/bin/playwright install chromium
```

Then follow its `install.md` for ffmpeg, whisper.cpp and Node 22+:

```bash
brew install ffmpeg whisper-cpp node uv     # macOS
# Linux: your package manager for ffmpeg + node; build whisper.cpp from
# https://github.com/ggml-org/whisper.cpp
```

If it lives somewhere other than `~/.claude/skills/i-hate-editing` or
`~/Developer/i-hate-editing`, set `IHE_DIR` to its path.

## 2. This skill

Clone this repo and link the skill into your skills folder:

```bash
mkdir -p ~/Developer ~/.claude/skills
git clone https://github.com/zahraquettawala/claude-skills ~/Developer/claude-skills
ln -sfn ~/Developer/claude-skills/tiktok-edit ~/.claude/skills/tiktok-edit
```

Updating later is `git -C ~/Developer/claude-skills pull`.

For beat-synced montages, numpy (in whichever python runs the scripts):

```bash
uv pip install --python ~/Developer/i-hate-editing/.venv numpy
# then run music_beats.py with ~/Developer/i-hate-editing/.venv/bin/python
```

For the CapCut export (on the computer that has CapCut desktop):

```bash
uv pip install --python ~/Developer/i-hate-editing/.venv "pycapcut==0.0.4"
# then run capcut_export.py with ~/Developer/i-hate-editing/.venv/bin/python
```

pyCapCut is pinned to 0.0.4 because its next release renames the track API.
Its projects are verified against CapCut for Windows; on a Mac, try it once
and check the project opens before relying on it.

## 3. Check

```bash
python3 ~/.claude/skills/tiktok-edit/scripts/doctor.py
```

Everything marked `MISS` is required. `--` lines are optional and show the
fallback this skill uses instead.

## Use

```bash
cd /path/to/your/footage
claude
> make this into a tiktok
```
