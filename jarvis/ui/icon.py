"""The JARVIS icon, drawn in code so there is no image file to keep in sync."""

from __future__ import annotations


def make_icon(size: int = 256):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = size // 16
    ring = max(2, size // 14)

    draw.ellipse((pad, pad, size - pad, size - pad), fill=(7, 11, 22, 255), outline=(0, 229, 255, 255), width=ring)

    try:
        font = ImageFont.truetype("seguisb.ttf", int(size * 0.55))
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", int(size * 0.55))
        except OSError:
            font = ImageFont.load_default()

    draw.text((size / 2, size / 2), "J", font=font, fill=(0, 229, 255, 255), anchor="mm")
    return image


def save_ico(path: str) -> None:
    make_icon(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
