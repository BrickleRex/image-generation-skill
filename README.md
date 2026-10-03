# Image Generation for Claude Code

Make and edit pictures just by asking Claude Code.

> "Make me a logo for my bakery, warm and minimal."
> "Turn this photo into a watercolor painting: ~/Pictures/dog.jpg"

Claude writes the brief, OpenAI's Codex draws the picture, and the image is saved where you asked.

## What you need

- **Claude Code** ([claude.com/claude-code](https://claude.com/claude-code))
- **A ChatGPT plan that includes Codex** (Plus, Pro, Business, Edu or Enterprise), or an OpenAI API key.
  The pictures use your ChatGPT / Codex allowance.
- **A Mac, Windows or Linux computer** with Python 3. Most Macs and Linux computers already have it;
  on Windows, install it from [python.org](https://www.python.org/downloads/).
  (Windows should work but has not been tested yet.)

## Install (about 5 minutes)

### The easy way: let Claude Code do it

1. Open Claude Code and paste this:

   ```
   Install the Codex CLI, then install this skill for all my projects:
   npx skills add BrickleRex/image-generation-skill -g -a claude-code -y
   ```

2. When it is done, type this in Claude Code and sign in with your ChatGPT account in the browser
   window that opens:

   ```
   ! codex login
   ```

3. Close Claude Code and open it again.

### Or do it yourself in a terminal

```bash
npm install -g @openai/codex          # 1. install Codex (Mac with Homebrew: brew install --cask codex)
codex login                           # 2. sign in with your ChatGPT account
npx skills add BrickleRex/image-generation-skill -g -a claude-code -y   # 3. install this skill
```

Then close Claude Code and open it again.

`npm` and `npx` come with Node.js. If you don't have them, install Node.js from
[nodejs.org](https://nodejs.org) first.

## Use it

Just ask Claude Code for a picture. Say what you want, the style, and where to save it:

- "Make a hero image for my landing page: calm, soft pastel colours, no text. Save it in images/."
- "Make a square icon of a paper plane, flat style, red and white."
- "Restyle this logo as a glossy 3D render: ./logo.png"

Each picture takes about 30 seconds to 2 minutes. Claude tells you where it saved the file.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| "codex not found" | Install Codex again (step 1), then close and reopen Claude Code. |
| A sign-in or login error | Run `codex login` again. |
| Claude doesn't make an image | Close and reopen Claude Code, then ask again and say "make an image". |
| Words inside the picture are garbled | Image models are bad at text. Ask for no text and add words later. |
| Windows: "python3 not found" | Install Python from [python.org](https://www.python.org/downloads/), then ask again. Claude will use `python` or `py`. |

## What's inside

- `SKILL.md`: the instructions Claude follows
- `scripts/generate_image.py`: runs Codex and makes sure the image is saved where you asked
- `references/codex-image-generation.md`: technical details and more troubleshooting

## License

MIT
