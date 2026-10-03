---
name: image-generation
description: >-
  Generate images from a text description by delegating to the codex CLI agent, which has a
  native image-generation model. Use this whenever the user wants to CREATE, generate, make,
  draw, render, design, or produce a picture, image, illustration, logo, icon, mascot, avatar,
  banner, hero image, background, poster, sticker, concept art, product shot, mockup, social /
  OG / thumbnail image, or any visual ASSET that must end up as an actual image file on disk —
  even when they don't say the word "image" (e.g. "make me a logo for my coffee shop", "I need
  a hero graphic for the landing page", "draw a cute robot for the app"). Also use it to EDIT or
  restyle an existing image (provide it as a reference). Every run writes the final PNG to an
  exact output path the caller specifies — that delivered file is the whole point. Do NOT use
  this for reading/describing an existing image, for data charts/graphs (write code instead),
  or for Figma/diagram work.
---

# Image Generation (via codex)

## Why this exists

You (Claude) can't render pixels, but the **codex CLI agent** has a built-in image-generation
tool. This skill makes you the *harness*: you turn the user's intent into a clean spec, hand it
to codex, and guarantee the resulting image lands at a specific path on disk. codex writes images
into its own internal store (`~/.codex/generated_images/...`); the user almost never wants it
there, so the contract of this skill is: **the image always arrives at the `--output` path you
choose.** A bundled script enforces that contract so you don't have to re-derive the plumbing.

## The one thing that matters: the output path

Every generation MUST specify an absolute `--output` path, and the job is not done until a valid
image file exists there. The bundled script (`scripts/generate_image.py`) drives codex and then
*independently verifies* the file — if codex didn't place it, the script recovers the freshly
generated PNG from codex's internal store and copies it over. Trust the script's exit code and
JSON, but if you ever generate images another way, still confirm the file exists at the path.

## Workflow

1. **Pin down the spec.** From the user's request, assemble three things:
   - **Subject** (`--prompt`): what to depict, concretely. Describe the scene, subject, framing,
     mood. Specific beats vague ("a corner coffee shop at golden hour with people seated outside"
     beats "a coffee shop").
   - **Style / brand guidelines** (`--style`): the look — medium (photo, flat vector, 3D render,
     watercolor…), palette (name hex codes if the user has brand colors), lighting, texture, and
     hard constraints like "no text" or "transparent-feel background". This is where brand kits go.
   - **Output path** (`--output`): an absolute path ending in `.png`. If the user didn't give one,
     pick a sensible location (their project's assets dir, or ask if truly ambiguous) — never skip it.

2. **Pick orientation** (`--size`): `square`, `portrait`, or `landscape` (or an explicit `WxH`
   like `1536x1024`). Match the asset's use — `landscape` for hero/banner, `portrait` for posters,
   `square` for logos/avatars/social tiles.

3. **Run the script.** `SKILL_DIR` is this skill's base directory (Claude Code shows it when the
   skill loads; for a personal install it is `~/.claude/skills/image-generation`):

   ```bash
   python3 "$SKILL_DIR/scripts/generate_image.py" \
     --prompt "<subject>" \
     --style "<style / brand guidelines>" \
     --size landscape \
     --output /absolute/path/to/asset.png
   ```

   It prints progress to stderr and, on success, a JSON line to stdout:
   `{"status": "success", "output": "...", "bytes": 3166389, "dimensions": "1536x1024", "source": "codex"}`.
   Exit code `0` = a valid image is at `--output`; `2` = failure (read the stderr tail for codex's error).

4. **Show the result.** Read the output file back to confirm it matches the brief, then tell the
   user the path. If it's off (wrong subject, ignored a constraint), refine the `--prompt`/`--style`
   and run again — image models respond well to more specific, concrete direction.

## Editing or restyling an existing image

Pass the source image(s) as references; codex uses them as visual input:

```bash
python3 "$SKILL_DIR/scripts/generate_image.py" \
  --prompt "Put this product on a marble kitchen counter in soft morning light" \
  --reference /path/to/product.png \
  --output /path/to/product_on_counter.png
```

`--reference` is repeatable (e.g., one image for the subject, one for the style to transfer).

## Writing good specs (this drives quality more than anything)

- **Be concrete and visual.** Name the subject, the setting, the camera/framing, the time of day,
  the mood. Models fill vague prompts with averages; specifics give you intent.
- **Put brand rules in `--style`.** Palette (with hex), typography feel, "flat/minimal/photoreal",
  texture, and especially *negative* constraints ("no text", "no people", "no harsh shadows").
- **One asset per run.** Ask for a single final image unless the user wants variations; then run
  multiple times to different `--output` paths.
- **Text-in-image is hard.** If the user needs legible words baked in, say so explicitly in the
  prompt and verify the result carefully — consider adding text in post instead.

## When NOT to use this skill

- The user wants you to **read, describe, or analyze** an existing image → just view it.
- They want a **chart, graph, or data visualization** → generate it with code (matplotlib, a JS
  charting lib, etc.), not an image model.
- They want **Figma designs or diagrams** → use the Figma / diagram skills.

## Deeper mechanics & troubleshooting

codex's invocation details, sandbox/auth notes, the internal `generated_images` layout, the
fallback-recovery logic, and codex's own image use-case taxonomy (edits, compositing, style
transfer, etc.) live in `references/codex-image-generation.md`. Read it if a run fails, if you
need an edit mode beyond plain generation, or if you want to call codex directly without the script.
