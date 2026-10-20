"""Generated label / sign textures (PIL, DejaVu fonts). Text only - no brand names or logos.

Usage: from assets.common.decals import text_png
"""

import os

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def text_png(path, lines, size=(1024, 256), bg=(255, 255, 255, 255), fg=(0, 0, 0, 255), bold=True, margin=0.06):
    """Render centred lines of text (list of str, or list of (str, rel_size, rgba)) into a PNG; returns the path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGBA", size, bg)
    d = ImageDraw.Draw(img)
    W, H = size
    spec = [(ln, 1.0, fg) if isinstance(ln, str) else ln for ln in lines]
    total = sum(s for _, s, _ in spec)
    usable = H * (1 - 2 * margin)
    y = H * margin
    for text, rel, col in spec:
        h = usable * rel / total
        fs = int(h * 0.78)
        font = ImageFont.truetype(FONT if bold else FONT_REG, fs)
        while font.getlength(text) > W * (1 - 2 * margin) and fs > 8:
            fs -= 2
            font = ImageFont.truetype(FONT if bold else FONT_REG, fs)
        tw = font.getlength(text)
        d.text(((W - tw) / 2, y + (h - fs) / 2 - fs * 0.1), text, font=font, fill=col)
        y += h
    # content-hashed file name: Isaac Sim caches textures by path, so regenerated labels need new paths
    import hashlib
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    stem, ext = os.path.splitext(path)
    out = f"{stem}_{hashlib.sha1(buf.getvalue()).hexdigest()[:8]}{ext}"
    if not os.path.exists(out):
        with open(out, "wb") as f:
            f.write(buf.getvalue())
    return out
