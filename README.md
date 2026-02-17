# [MonoLisa](https://www.monolisa.dev/) Avatar Generator

Generate square or circular avatar images using a local MonoLisa font with explicit OpenType feature control (`ss02`, `zero`, `liga`, etc.).

This project renders text using HarfBuzz + FreeType, then composites a styled avatar with Pillow.

## Preview

Default 1x circular output (`1024x1024`):

<p align="center">
  <img src="examples/avatar-0xB-nord.png" alt="Default 1x circular avatar" width="320" />
</p>

## Requirements

- Python `>=3.11`
- `uv` installed
- A local MonoLisa font file (default path in this project: `/var/lib/fonts/monolisa/ttf/MonoLisa-Bold.ttf`)

## Setup

Install dependencies and run via `uv`:

```bash
uv run python generate_avatar.py --help
```

`uv` will create a local virtual environment and install dependencies from `pyproject.toml`/`uv.lock`.

## Quick Start

Generate the default Nord circular avatar:

```bash
uv run python generate_avatar.py
```

Generate a 1x square avatar:

```bash
uv run python generate_avatar.py \
  --shape square \
  --size 1024 \
  --output avatar-0xB-nord-square-1x.png
```

Generate a 2x circular avatar:

```bash
uv run python generate_avatar.py \
  --shape circle \
  --size 2048 \
  --margin 144 \
  --output avatar-0xB-nord-2x.png
```

## Defaults

- Text: `{0xB}`
- Font: `/var/lib/fonts/monolisa/ttf/MonoLisa-Bold.ttf`
- Shape: `circle`
- Size: `1024`
- Nord colors:
  - Background: `#2E3440`
  - Foreground: `#88C0D0`
  - Glow: `#5E81AC`
- Features:
  - `calt=1,liga=0,ss02=1,zero=1,ss07=1,aalt=1`

## Common Options

- `--text "{0xB}"`: text to render.
- `--shape circle|square`: avatar background shape.
- `--size 1024`: output dimensions (`size x size`).
- `--margin 72`: circle inset margin (used for `circle` only).
- `--font /path/to/font.ttf`: font file path.
- `--features "calt=1,liga=0,ss02=1,zero=1"`: comma-separated feature flags.
- `--bg "#2E3440"`: background color.
- `--fg "#88C0D0"`: text color.
- `--glow "#5E81AC"`: glow color.
- `--glow-alpha 190`: glow opacity.
- `--glow-blur 8.0`: glow blur radius.
- `--fit-width-ratio 0.72`: max text width as fraction of canvas.
- `--fit-height-ratio 0.36`: max text height as fraction of canvas.

## Notes

- If your MonoLisa install path is different, pass `--font`.
- OpenType feature behavior depends on the specific MonoLisa build you installed.
