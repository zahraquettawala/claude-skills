# Making a TikTok with tiktok-edit: step by step

Everything below happens on your Mac, in the **Terminal** app (Cmd+Space, type
"Terminal", Enter). Lines in grey boxes are commands: copy the whole box, paste
it into Terminal, press Enter.

Each video gets its own folder in `~/Movies`. In the commands below it is
called **`my-video`**. Change it to a short name for each new video (no spaces,
for example `coffee-vlog`), the same name everywhere.

---

## Once only: setup (already done)

You only ever do this on a new laptop. Skip to "Every new video".

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg whisper-cpp node uv
mkdir -p ~/Developer ~/.claude/skills ~/Movies/tiktok-keep
git clone https://github.com/ranahaani/i-hate-editing ~/Developer/i-hate-editing
ln -sfn ~/Developer/i-hate-editing ~/.claude/skills/i-hate-editing
git clone -b add-tiktok-edit https://github.com/zahraquettawala/claude-skills ~/Developer/claude-skills
ln -sfn ~/Developer/claude-skills/tiktok-edit ~/.claude/skills/tiktok-edit
cd ~/Developer/i-hate-editing
uv venv .venv
uv pip install --python .venv playwright pillow numpy "pycapcut==0.0.4"
.venv/bin/playwright install chromium
python3 ~/.claude/skills/tiktok-edit/scripts/doctor.py
```

The last line checks everything. No line should say `MISS`.

In CapCut desktop: make one empty project, add one text clip in the
**ChunkFive** font (so CapCut downloads it), then quit CapCut.

---

## Every new video

### 1. Get the latest version of the skill

```bash
git -C ~/Developer/claude-skills pull
```

### 2. Make a folder for the video

```bash
mkdir -p ~/Movies/my-video
```

### 3. Copy the footage off the Osmo

Plug in the Osmo and turn it on (pick the file transfer option on its screen if
it asks). Then copy just the videos and photos, leaving the camera's `.LRF`
preview files behind:

```bash
find /Volumes -path "*DCIM*" \( -iname "*.mp4" -o -iname "*.jpg" \) -exec cp -n {} ~/Movies/my-video/ \; 2>/dev/null
open ~/Movies/my-video
```

The folder opens in Finder. Check a couple of the videos play. Delete any you
don't want in this TikTok.

Eject the Osmo before unplugging it: click ⏏ next to it in Finder's sidebar.

### 4. Quit CapCut

Cmd+Q in CapCut if it is open. It has to be closed when Claude writes the
CapCut project.

### 5. Keep the laptop awake (for long edits)

Open a **second** Terminal window (Cmd+N) and run:

```bash
caffeinate -i
```

Leave that window alone. Press Ctrl+C in it when you are done for the day.

### 6. Start Claude in the video's folder

Back in the first window:

```bash
cd ~/Movies/my-video
claude
```

### 7. Tell it what to make

Paste this (edit the title part if you already know your title):

> Make these clips into a TikTok using the tiktok-edit skill, in Shivani's
> style. Only use the .MP4 files (and the photos if they fit). Some clips may
> be sideways, so check they're upright. For the title, write two short lines
> from what I say and show me before adding it. Use
> ~/Developer/i-hate-editing/.venv/bin/python for every Python script. Use my
> taste.md and profile.yml from ~/Movies/tiktok-keep if they exist. Also
> export the CapCut project.

The first video takes longest (it downloads a speech model). Claude shows you
the rough cut and **waits for your OK** before adding captions and the title.

**Sit-down ramble instead?** If it's one long take of you talking it through,
paste this instead:

> This is a sit-down ramble. Use the tiktok-edit skill's ramble workflow in
> Shivani's style. Cut the ums and dead air, find the story, and keep every
> important fact. Show me the outline and what you plan to cut before you cut
> anything. Use ~/Developer/i-hate-editing/.venv/bin/python for every Python
> script. Use my taste.md and profile.yml from ~/Movies/tiktok-keep if they
> exist. Also export the CapCut project.

It will show you the story it found and everything it plans to cut, and wait
for your OK, before cutting.

### 8. Give feedback

Just talk to it, with timestamps where you can:

- "0:08 feels clipped"
- "cut the part where I say hold on"
- "make the title: how I got / my first client"
- "captions are coming in too early"

### 9. Where the results are

- Finished video: `~/Movies/my-video/studio/out/tiktok/tiktok.mp4`
- CapCut project: open CapCut, it is in your project list (restart CapCut if
  not)

```bash
open ~/Movies/my-video/studio/out/tiktok
```

---

## Stopping for the day

Paste this to Claude:

> I'm stopping for now. Save every change I've asked for as a taste note
> (taste.py add, with my own words), and write a short studio/NEXT.md listing
> where the edit is and what's still left to do. Don't render anything else.

Then type `/exit`. You can close Terminal and the laptop; nothing is lost.

## Picking up again

```bash
cd ~/Movies/my-video
claude --continue
```

Then say: "Read studio/NEXT.md and pick up where we left off."

(`claude --resume` instead of `--continue` lets you pick an older
conversation.)

---

## When the video is done

### 1. Save your style for next time

This keeps everything you've taught it, so the next video starts there:

```bash
cp ~/Movies/my-video/studio/taste.md ~/Movies/my-video/studio/profile.yml ~/Movies/tiktok-keep/
```

### 2. Free up space

Only once you're happy with the final video, and the CapCut project opens and
plays (if you want to keep editing there). After this Claude can no longer
re-cut this video.

See what would go (only the original videos and `.LRF` files directly in the
folder; your photos and the finished video are not touched):

```bash
find ~/Movies/my-video -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.lrf" \)
```

If that list looks right, move them to the Trash:

```bash
find ~/Movies/my-video -maxdepth 1 -type f \( -iname "*.mp4" -o -iname "*.lrf" \) -exec mv -n {} ~/.Trash/ \;
```

Empty the Trash when you're sure (right-click the Trash in the Dock).

### 3. Clear the camera

Once the copies on the laptop play, format the card in the Osmo's settings, or
delete the files on it in Finder and **empty the Trash before unplugging**.
(Leave the `.LRF` files on the camera if you want to keep watching clips on its
screen.)

---

## Good to know

- **Record in 1080p** on the Osmo unless you want room for zooms: TikTok shows
  1080p at most and the files are about a quarter of the size of 4K.
- **D-Log M**: if you shot in this flat colour mode, tell Claude so it gets
  colour-corrected.
- **Browser tools** can stay off; the skill doesn't need your browser.
- **Problems with the skill itself** (a step that crashes, something it always
  gets wrong): bring them to Claude on claude.ai, which fixes the skill in the
  `claude-skills` repo. Then run step 1 ("Get the latest version") again.

## If something goes wrong

| What you see | What to do |
|---|---|
| `command not found: claude` | `curl -fsSL https://claude.ai/install.sh \| bash`, then open a new Terminal window |
| `Login expired` in Claude | type `/login` |
| No videos found | check the folder: `ls ~/Movies/my-video` |
| The Osmo doesn't show up | unplug, plug back in while it's on, pick file transfer on its screen; or use the Image Capture app |
| CapCut project not in the list | quit and reopen CapCut |
| Text in the wrong font in CapCut | add one ChunkFive text clip in CapCut once, then ask Claude to export the CapCut project again |
| A clip is red / "File not accessible" in CapCut | ask Claude to export the CapCut project again |
