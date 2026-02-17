#!/usr/bin/env python3
"""Generate MonoLisa avatars with explicit OpenType feature control."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import freetype
from PIL import Image, ImageDraw, ImageFilter
import uharfbuzz as hb


DEFAULT_FEATURES = "calt=1,liga=0,ss02=1,zero=1,ss07=1,aalt=1"


@dataclass
class GlyphPlacement:
    x: float
    y: float
    width: int
    height: int
    buffer: bytes


def parse_color(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.strip()
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got: {value!r}")
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return (r, g, b, alpha)


def parse_features(features_text: str) -> dict[str, int]:
    features: dict[str, int] = {}
    for item in features_text.split(","):
        token = item.strip()
        if not token:
            continue
        if "=" in token:
            tag, raw_value = token.split("=", 1)
            features[tag.strip()] = int(raw_value.strip())
        else:
            features[token] = 1
    return features


def shape_and_measure(
    face: freetype.Face,
    hb_face: hb.Face,
    hb_font: hb.Font,
    text: str,
    features: dict[str, int],
    px_size: int,
) -> tuple[tuple[float, float, float, float], list[GlyphPlacement], list[str]] | None:
    face.set_pixel_sizes(0, px_size)
    hb_font.scale = (hb_face.upem, hb_face.upem)

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, features)

    infos = buf.glyph_infos
    positions = buf.glyph_positions
    scale = px_size / hb_face.upem

    pen_x = 0.0
    placements: list[GlyphPlacement] = []
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    glyph_names: list[str] = []

    for info, pos in zip(infos, positions):
        glyph_id = info.codepoint
        face.load_glyph(
            glyph_id,
            freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL,
        )
        glyph = face.glyph
        bitmap = glyph.bitmap
        x_offset = pos.x_offset * scale
        y_offset = pos.y_offset * scale

        gx = pen_x + x_offset + glyph.bitmap_left
        gy = -y_offset - glyph.bitmap_top

        if bitmap.width > 0 and bitmap.rows > 0:
            min_x = min(min_x, gx)
            min_y = min(min_y, gy)
            max_x = max(max_x, gx + bitmap.width)
            max_y = max(max_y, gy + bitmap.rows)

        placements.append(
            GlyphPlacement(
                x=gx,
                y=gy,
                width=bitmap.width,
                height=bitmap.rows,
                buffer=bytes(bitmap.buffer),
            )
        )
        try:
            glyph_names.append(face.get_glyph_name(glyph_id).decode("ascii", "ignore"))
        except Exception:
            glyph_names.append(str(glyph_id))

        pen_x += pos.x_advance * scale

    if min_x == float("inf"):
        return None
    return (min_x, min_y, max_x, max_y), placements, glyph_names


def make_text_mask(
    bbox: tuple[float, float, float, float], placements: list[GlyphPlacement]
) -> tuple[Image.Image, tuple[int, int]]:
    min_x, min_y, max_x, max_y = bbox
    text_width = max(1, int(round(max_x - min_x)))
    text_height = max(1, int(round(max_y - min_y)))
    mask = Image.new("L", (text_width, text_height), 0)

    for placement in placements:
        if placement.width <= 0 or placement.height <= 0:
            continue
        glyph_image = Image.frombytes("L", (placement.width, placement.height), placement.buffer)
        x = int(round(placement.x - min_x))
        y = int(round(placement.y - min_y))
        mask.paste(glyph_image, (x, y), glyph_image)

    return mask, (text_width, text_height)


def build_avatar(
    *,
    font_path: Path,
    output_path: Path,
    text: str,
    features: dict[str, int],
    shape: str,
    size: int,
    margin: int,
    bg_color: tuple[int, int, int, int],
    fg_color: tuple[int, int, int, int],
    glow_color: tuple[int, int, int, int],
    glow_blur: float,
    fit_width_ratio: float,
    fit_height_ratio: float,
) -> tuple[int, list[str]]:
    face = freetype.Face(str(font_path))
    font_data = font_path.read_bytes()
    hb_face = hb.Face(font_data)
    hb_font = hb.Font(hb_face)
    hb.ot_font_set_funcs(hb_font)

    target_w = size * fit_width_ratio
    target_h = size * fit_height_ratio

    max_px = max(220, int(size * 0.70))
    min_px = max(64, int(size * 0.08))
    step = max(2, int(size / 170))

    chosen = None
    for px_size in range(max_px, min_px - 1, -step):
        shaped = shape_and_measure(face, hb_face, hb_font, text, features, px_size)
        if shaped is None:
            continue
        bbox, placements, names = shaped
        min_x, min_y, max_x, max_y = bbox
        width = max_x - min_x
        height = max_y - min_y
        if width <= target_w and height <= target_h:
            chosen = (px_size, bbox, placements, names)
            break

    if chosen is None:
        shaped = shape_and_measure(face, hb_face, hb_font, text, features, 220)
        if shaped is None:
            raise RuntimeError("Shaping produced no drawable glyphs.")
        bbox, placements, names = shaped
        chosen = (220, bbox, placements, names)

    font_px, bbox, placements, glyph_names = chosen
    text_mask, (text_width, text_height) = make_text_mask(bbox, placements)

    if shape == "circle":
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        circle_mask = Image.new("L", (size, size), 0)
        draw_mask = ImageDraw.Draw(circle_mask)
        draw_mask.ellipse((margin, margin, size - margin, size - margin), fill=255)
        background = Image.new("RGBA", (size, size), bg_color)
        canvas.paste(background, (0, 0), circle_mask)
    elif shape == "square":
        canvas = Image.new("RGBA", (size, size), bg_color)
    else:
        raise ValueError(f"Unsupported shape: {shape!r}")

    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2

    if glow_blur > 0 and glow_color[3] > 0:
        glow_alpha = text_mask.filter(ImageFilter.GaussianBlur(glow_blur))
        glow_layer = Image.new("RGBA", (text_width, text_height), glow_color)
        canvas.paste(glow_layer, (text_x, text_y), glow_alpha)

    foreground = Image.new("RGBA", (text_width, text_height), fg_color)
    canvas.paste(foreground, (text_x, text_y), text_mask)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)

    return font_px, glyph_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an avatar with MonoLisa + OpenType features."
    )
    parser.add_argument("--font", default="/var/lib/fonts/monolisa/ttf/MonoLisa-Bold.ttf")
    parser.add_argument("--output", default="avatar-0xB-nord.png")
    parser.add_argument("--text", default="{0xB}")
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--shape", choices=["circle", "square"], default="circle")
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--margin", type=int, default=72)
    parser.add_argument("--fit-width-ratio", type=float, default=0.72)
    parser.add_argument("--fit-height-ratio", type=float, default=0.36)
    parser.add_argument("--bg", default="#2E3440", help="Background hex color.")
    parser.add_argument("--fg", default="#88C0D0", help="Text hex color.")
    parser.add_argument("--glow", default="#5E81AC", help="Glow hex color.")
    parser.add_argument("--glow-alpha", type=int, default=190)
    parser.add_argument("--glow-blur", type=float, default=8.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = parse_features(args.features)

    font_path = Path(args.font)
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    bg = parse_color(args.bg, 255)
    fg = parse_color(args.fg, 255)
    glow = parse_color(args.glow, max(0, min(255, args.glow_alpha)))

    font_px, glyph_names = build_avatar(
        font_path=font_path,
        output_path=Path(args.output),
        text=args.text,
        features=features,
        shape=args.shape,
        size=args.size,
        margin=args.margin,
        bg_color=bg,
        fg_color=fg,
        glow_color=glow,
        glow_blur=args.glow_blur,
        fit_width_ratio=args.fit_width_ratio,
        fit_height_ratio=args.fit_height_ratio,
    )

    print(f"wrote: {args.output}")
    print(f"font_px: {font_px}")
    print(f"features: {features}")
    print(f"glyphs: {glyph_names}")


if __name__ == "__main__":
    main()
