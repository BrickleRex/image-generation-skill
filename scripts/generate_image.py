#!/usr/bin/env python3
"""
generate_image.py — Generate an image with codex and guarantee it lands at an exact output path.

Codex (the OpenAI CLI agent) has a native image-generation tool. When run, it writes
PNGs into its own internal store at ~/.codex/generated_images/<session>/ig_*.png. This
wrapper drives codex non-interactively, then INDEPENDENTLY guarantees the image ends up
at the caller-specified --output path: if codex doesn't copy it there itself, this script
locates the freshly generated PNG in codex's internal store and copies it over.

The output path is the contract. This script does not exit 0 unless a valid image file
exists at --output.

Usage:
    python3 generate_image.py \
        --prompt "A friendly robot mascot waving hello" \
        --style "Flat vector, pastel mint + coral, thick outlines, no text" \
        --output /abs/path/to/image.png \
        [--size square|portrait|landscape|"1536x1024"] \
        [--reference /path/to/ref1.png --reference /path/to/ref2.png] \
        [--workdir /dir/to/run/codex/in] \
        [--model gpt-5.5] \
        [--sandbox workspace-write|danger-full-access] \
        [--timeout 420] \
        [--extra "any additional freeform guidance for codex"]

Exit codes: 0 = image delivered to --output; 2 = failure (no valid image at --output).
"""

import argparse
import glob
import json
import os
import shutil
import struct
import subprocess
import sys
import time

CODEX_GENERATED_DIR = os.path.expanduser("~/.codex/generated_images")
SIZE_HINTS = {
    "square": "Square 1:1 composition (about 1024x1024).",
    "portrait": "Portrait / vertical orientation, taller than wide (about 1024x1536).",
    "landscape": "Landscape / horizontal orientation, wider than tall (about 1536x1024).",
}


def use_utf8_output() -> None:
    """Print UTF-8 whatever the terminal's code page (Windows often defaults to cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def png_dimensions(path: str):
    """Return (width, height) for a PNG, or None if not a parseable PNG."""
    try:
        with open(path, "rb") as f:
            header = f.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        width, height = struct.unpack(">II", header[16:24])
        return width, height
    except Exception:
        return None


def is_valid_image(path: str) -> bool:
    """A delivered file must exist and be non-trivially sized."""
    return os.path.isfile(path) and os.path.getsize(path) > 1024


def snapshot_generated() -> set:
    """Set of PNG paths currently in codex's internal image store."""
    if not os.path.isdir(CODEX_GENERATED_DIR):
        return set()
    return set(glob.glob(os.path.join(CODEX_GENERATED_DIR, "**", "ig_*.png"), recursive=True))


def newest_generated_since(before: set, start_time: float):
    """Find the PNG codex just produced: prefer files absent from the pre-run snapshot,
    else any ig_*.png modified at/after the run started. Returns the newest match or None."""
    if not os.path.isdir(CODEX_GENERATED_DIR):
        return None
    current = glob.glob(os.path.join(CODEX_GENERATED_DIR, "**", "ig_*.png"), recursive=True)
    new_files = [p for p in current if p not in before]
    pool = new_files or [p for p in current if os.path.getmtime(p) >= start_time - 2]
    if not pool:
        return None
    return max(pool, key=os.path.getmtime)


def build_prompt(args) -> str:
    lines = [
        "Use your built-in image generation tool to generate ONE image, then deliver it to an exact path.",
        "",
        "=== IMAGE SPEC ===",
        f"Primary request: {args.prompt}",
    ]
    if args.style:
        lines.append(f"Style / brand guidelines: {args.style}")
    if args.size:
        lines.append(f"Aspect / orientation: {SIZE_HINTS.get(args.size.lower(), args.size)}")
    if args.reference:
        lines.append(
            "Reference images: the attached image(s) are provided as visual references / inputs. "
            "Use them to guide the result (subject, style, or composition as the request implies)."
        )
    if args.extra:
        lines.append(f"Additional guidance: {args.extra}")

    lines += [
        "",
        "=== MANDATORY OUTPUT (the task is not done until this is true) ===",
        "After generating, the final PNG MUST exist at this EXACT absolute path:",
        f"  {args.output}",
        "",
        "Steps:",
        "  1. Generate the image with your image generation tool.",
        "  2. Copy the resulting PNG to the exact path above (its folder already exists).",
        "  3. Check that the file now exists at that path.",
        "  4. In your final message, state the absolute output path and the file size in bytes.",
        "",
        "Produce only one final image unless the request explicitly asks for variations.",
    ]
    return "\n".join(lines)


def main() -> int:
    use_utf8_output()
    ap = argparse.ArgumentParser(description="Generate an image via codex, guaranteed to an exact output path.")
    ap.add_argument("--prompt", required=True, help="What to depict (the image subject / primary request).")
    ap.add_argument("--output", required=True, help="Absolute path where the final PNG must be written.")
    ap.add_argument("--style", default="", help="Brand / style guidelines (palette, look, constraints).")
    ap.add_argument("--size", default="", help="square | portrait | landscape, or an explicit WxH hint.")
    ap.add_argument("--reference", action="append", default=[], help="Path to an input/reference image (repeatable).")
    ap.add_argument("--extra", default="", help="Any extra freeform guidance to pass to codex.")
    ap.add_argument("--workdir", default="", help="Directory to run codex in (default: the output's parent dir).")
    ap.add_argument("--model", default="", help="Override codex model (default: codex config, e.g. gpt-5.5).")
    ap.add_argument("--sandbox", default="workspace-write",
                    choices=["workspace-write", "danger-full-access", "read-only"],
                    help="codex sandbox mode (default: workspace-write).")
    ap.add_argument("--timeout", type=int, default=420, help="Max seconds to wait for codex (default: 420).")
    ap.add_argument("--codex-bin", default="", help="Path to the codex binary (default: auto-discover on PATH).")
    args = ap.parse_args()

    # --- Validate / normalize output ---
    args.output = os.path.abspath(os.path.expanduser(args.output))
    out_dir = os.path.dirname(args.output)
    if not out_dir:
        log("ERROR: --output must include a directory.")
        return 2
    os.makedirs(out_dir, exist_ok=True)

    for ref in args.reference:
        if not os.path.isfile(os.path.expanduser(ref)):
            log(f"ERROR: reference image not found: {ref}")
            return 2

    codex = args.codex_bin or shutil.which("codex")
    if not codex:
        log("ERROR: `codex` not found on PATH. Install/login to codex, or pass --codex-bin.")
        return 2

    workdir = os.path.abspath(os.path.expanduser(args.workdir)) if args.workdir else out_dir
    os.makedirs(workdir, exist_ok=True)

    prompt = build_prompt(args)
    last_msg_file = os.path.join(out_dir, ".codex_last_message.txt")

    cmd = [codex, "exec", "--skip-git-repo-check", "-C", workdir, "-s", args.sandbox, "-o", last_msg_file]
    if args.model:
        cmd += ["-m", args.model]
    for ref in args.reference:
        cmd += ["-i", os.path.abspath(os.path.expanduser(ref))]

    log(f"[generate_image] codex={codex}")
    log(f"[generate_image] workdir={workdir} sandbox={args.sandbox}")
    log(f"[generate_image] output={args.output}")
    log(f"[generate_image] running codex (timeout={args.timeout}s)...")

    before = snapshot_generated()
    start_time = time.time()
    try:
        # UTF-8 both ways: prompts and codex's replies can hold any character (quotes, accents, emoji).
        proc = subprocess.run(cmd, input=prompt, text=True, encoding="utf-8", errors="replace",
                              capture_output=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        log(f"ERROR: codex timed out after {args.timeout}s.")
        # Still try the fallback — codex may have produced the image before the wrapper gave up.
        proc = None
    else:
        if proc.stdout:
            log("----- codex stdout (tail) -----")
            log("\n".join(proc.stdout.strip().splitlines()[-12:]))
        if proc.returncode != 0:
            log(f"WARNING: codex exited with code {proc.returncode}.")
            if proc.stderr:
                log("----- codex stderr (tail) -----")
                log("\n".join(proc.stderr.strip().splitlines()[-12:]))

    # --- Guarantee delivery to --output ---
    source = "codex"
    if not is_valid_image(args.output):
        log("[generate_image] output not present (or too small); checking codex's internal store...")
        candidate = newest_generated_since(before, start_time)
        if candidate:
            shutil.copy2(candidate, args.output)
            source = "fallback-copy"
            log(f"[generate_image] recovered generated image: {candidate}")
        else:
            log("ERROR: no generated image found in codex's store, and --output was not written.")
            return 2

    if not is_valid_image(args.output):
        log("ERROR: failed to deliver a valid image to --output.")
        return 2

    size = os.path.getsize(args.output)
    dims = png_dimensions(args.output)
    dim_str = f"{dims[0]}x{dims[1]}" if dims else "unknown"
    result = {
        "status": "success",
        "output": args.output,
        "bytes": size,
        "dimensions": dim_str,
        "source": source,
    }
    # Clean up the transient last-message file.
    try:
        os.remove(last_msg_file)
    except OSError:
        pass

    log(f"[generate_image] DELIVERED: {args.output} ({size} bytes, {dim_str}, via {source})")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
