# claude-skills

Skills for [Claude](https://claude.ai). Each folder is one skill: a `SKILL.md` file with instructions Claude follows.

## Skills

| Skill | What it does |
|---|---|
| [responding-to-my-texts](responding-to-my-texts/SKILL.md) | Reads a text thread in Messages on your Mac, asks what tone you want, drafts a reply in *your* texting voice, and sends it only after you approve. Includes a triage mode for when you're buried in unread texts, plus an optional "(this was sent by AI)" tagline. |

## Install a skill

1. Download this repo (**Code → Download ZIP**) and unzip it.
2. Zip just the skill's folder (for example `responding-to-my-texts/`, with `SKILL.md` inside).
3. In Claude, go to **Customize → Skills** and upload the ZIP.
4. Turn the skill on, then ask Claude something like "help me respond to my texts".

### Requirements for responding-to-my-texts

- A Mac with the Messages app signed in (iMessage synced from your iPhone)
- The Claude desktop app with **Computer use** turned on (Settings → Desktop app → Computer use)

Without computer use, you can still paste a thread or screenshot into the chat and the skill will help you draft a reply.

## Privacy

The skill only opens the threads you ask about, never sends anything without your explicit OK, and doesn't copy your messages anywhere else.
