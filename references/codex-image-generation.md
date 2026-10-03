# Codex Image Generation — Mechanics & Troubleshooting

Deep reference for the `image-generation` skill. Read when a run fails, when you need an edit mode
beyond plain text-to-image, or when you want to drive codex directly instead of via the wrapper.

## How codex generates images

`codex` (the OpenAI CLI agent, `codex-cli`) runs a model (default `gpt-5.5`, set in
`~/.codex/config.toml`) that has a **native image-generation tool** (`image_gen`). It is an
agent, not an image API: you give it a natural-language task and it calls its image tool, then can
run shell commands. There is **no `codex generate-image` subcommand** — image generation happens
because the *prompt* asks for it.

When the tool runs, it writes the PNG into codex's own store:

```
~/.codex/generated_images/<session-uuid>/ig_<hash>.png
```

These are real PNGs at sizes like `1024x1024`, `1024x1536`, `1536x1024`, and other aspect ratios
the model chooses. The wrapper's whole job is to get one of these to the caller's `--output` path.

## The non-interactive invocation

The wrapper runs (effectively):

```bash
codex exec --skip-git-repo-check -C <workdir> -s workspace-write -o <last_msg_file> < <prompt-on-stdin>
```

Key points, each learned the hard way:

- **`codex exec`** is the non-interactive mode. It does **not** accept `-a/--ask-for-approval`
  (that flag exists only on the top-level `codex` command). `exec` doesn't prompt, so you don't
  need it.
- **Pipe the prompt via stdin** (`< file` or `printf ... |`). `codex exec` reads instructions from
  stdin when no prompt arg is given. This avoids all shell-quoting pain with multi-line prompts.
- **`-C <workdir>`** sets the working directory. The wrapper uses the output file's parent dir so
  codex can also copy the image there itself under `workspace-write`.
- **`-s workspace-write`** is enough and is the least-privilege choice: it lets codex read anywhere
  and write inside the workspace + tmp. It runs **without a trust prompt even in untrusted dirs**
  (verified). Escalate to `-s danger-full-access` only if a run genuinely needs to write outside
  the workspace and the fallback copy isn't sufficient (rare — the wrapper copies the file itself).
- **`-o <file>`** captures codex's final message; the wrapper deletes it after reading.
- **`-i <image>`** attaches an input/reference image (repeatable). Used for edits/restyles.
- **`--skip-git-repo-check`** lets codex run outside a git repo.
- **`-m <model>`** overrides the model (default comes from config).

## The delivery guarantee (why the wrapper is reliable)

codex usually copies the image to the requested path when the prompt insists on it — but "usually"
isn't "always," and the output file is the entire point of the skill. So the wrapper does NOT trust
codex to deliver:

1. Before running, it snapshots the set of existing `ig_*.png` files and records the start time.
2. After codex returns, it checks `--output`. If a valid (>1 KB) image is there, done.
3. Otherwise it finds the PNG codex just produced — files **new** since the snapshot, else any
   `ig_*.png` with mtime ≥ start — picks the newest, and copies it to `--output` itself. This copy
   runs as the user (outside codex's sandbox), so it works regardless of codex's sandbox/trust.
4. It re-verifies and reports `source: codex` or `source: fallback-copy` in the JSON.

This means even if codex errors *after* generating, or refuses to run the `cp`, the image still
lands at `--output`.

## Auth & prerequisites

- codex must be installed and logged in. Check: `codex --version`, and `~/.codex/auth.json` exists.
  Login is via `codex login` (ChatGPT account or API key). Image generation consumes the account's
  usage.
- If `codex` isn't on PATH for the script, pass `--codex-bin /full/path/to/codex` (find it with
  `which codex`).

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| Script exits 2, stderr shows codex auth/login error | Run `codex login`; confirm `~/.codex/auth.json`. |
| Script exits 2, "no generated image found" | codex never called its image tool — make the prompt unambiguous: lead with "Use your built-in image generation tool to generate ONE image." The wrapper already does this. |
| `error: unexpected argument '-a'` | Don't pass `-a` to `codex exec`; it's top-level only. (Wrapper already avoids this.) |
| Hang / very slow | Image gen takes ~30–120 s. Raise `--timeout`. On timeout the wrapper still attempts fallback recovery. |
| Wrong subject / ignored constraint | Refine `--prompt`/`--style` with more specific, concrete direction; rerun. Models reward specificity. |
| Need to write outside workspace and fallback isn't enough | Add `--sandbox danger-full-access`. |
| Text in the image is garbled | Image models struggle with legible text; minimize baked-in text or add it in post. |
| Windows: `python3` not found | Use `python` or `py` instead (python.org installs those names). |

## codex's own image use-case taxonomy

codex ships an internal image skill with labeled modes. You don't invoke these directly, but naming
the mode in your `--prompt`/`--extra` steers it well:

- **text-localization** — translate/replace in-image text, preserve layout.
- **identity-preserve** — virtual try-on, person-in-scene; lock face/body/pose (use a `--reference`).
- **precise-object-edit** — remove/replace a specific element, including interior swaps.
- **lighting-weather** — change time-of-day / season / atmosphere only.
- **background-extraction** — transparent background / clean cutout.
- **style-transfer** — apply a reference style while changing subject/scene.
- **compositing** — insert/merge multiple images with matched lighting & perspective.
- **sketch-to-render** — turn line art / a drawing into a photoreal render.

For edits, pass the source as `--reference` and describe the change precisely (what to keep vs. what
to change).

## codex's shared prompt schema (optional scaffolding)

For complex asks, codex responds well to a labeled spec. The wrapper already structures the prompt;
if you call codex directly, this is the shape to use:

```text
Use case: <taxonomy slug, e.g. style-transfer>
Asset type: <where the asset will be used, e.g. landing-page hero>
Primary request: <the main prompt>
Input images: <Image 1: role; Image 2: role>   (optional)
Scene/backdrop: <environment>
Subject: <main subject>
Style: <medium, palette, lighting, texture, constraints>
Output: save the final PNG to <absolute path>, then verify with `ls -l`.
```

## Calling codex directly (without the wrapper)

Only if you need behavior the wrapper doesn't expose. Remember to still verify + recover the file:

```bash
printf '%s' "Use your built-in image generation tool to generate ONE image of <…>.
Style: <…>. After generating, copy the PNG to EXACTLY /abs/out.png (mkdir -p its parent),
then run: ls -l /abs/out.png" \
| codex exec --skip-git-repo-check -C /abs -s workspace-write -o /tmp/last.txt

# Then guarantee delivery yourself if needed:
test -s /abs/out.png || cp "$(ls -t ~/.codex/generated_images/**/ig_*.png | head -1)" /abs/out.png
```
