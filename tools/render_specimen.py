#!/usr/bin/env python3
"""Render images/specimen.png with correct kerning and OpenType features.

Uses HarfBuzz for shaping (kerning, ligatures, contextual alternates) and
FreeType for glyph rasterization — the same pipeline a browser uses, so the
result matches how the font actually renders. The character set is read
straight from the font, so arrows, brackets and punctuation appear too.

    pip install uharfbuzz freetype-py fonttools Pillow
    python3 tools/render_specimen.py

Everything you'd want to tweak lives in the EDIT ME block below.
"""
import os
import uharfbuzz as hb
import freetype
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, "fonts", "VTFViewer-Regular.otf")
OUT = os.path.join(ROOT, "images", "specimen.png")

# ============================ EDIT ME ============================
# Colors (R, G, B)
BG = (17, 17, 19)
FG = (240, 238, 232)
DIM = (120, 120, 125)
ACCENT = (232, 90, 60)

WIDTH = 1600          # image width in layout px (rendered at 2x)
MARGIN = 90           # side/top/bottom padding

LABEL = "PUSTOTA · DISPLAY TYPEFACE · v0.008"
TITLE = "VIEWER"

# Sample lines: (text, size, color)
SAMPLES = [
    ("Пустота · Viewer · Штучка", 60, FG),
    ("СЕВЕРНЫЙ ВЕТЕР · GAME OVER", 60, FG),
    ("Любя, съешь щипцы, — вздохнёт мэр, — кайф жгуч.", 38, DIM),
    ("The quick brown fox jumps over the lazy dog", 38, DIM),
]

SHOW_CHARSET = True   # a "CHARACTER SET" block read from the font's cmap
CHARSET_SIZE = 32
# =================================================================

SCALE = 2
W = WIDTH * SCALE
M = MARGIN * SCALE
MAXW = W - 2 * M

with open(FONT, "rb") as fh:
    data = fh.read()
hb_face = hb.Face(data)
hb_font = hb.Font(hb_face)
UPEM = hb_face.upem
ft_face = freetype.Face(FONT)


def shape(text):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {"kern": True, "liga": True, "calt": True})
    return buf.glyph_infos, buf.glyph_positions


def line_width(text, px):
    _, pos = shape(text)
    return sum(p.x_advance for p in pos) * (px / UPEM)


def fit_size(text, px):
    w = line_width(text, px)
    return int(px * MAXW / w) if w > MAXW else px


def draw_line(img, text, px, baseline, color):
    s = px / UPEM
    ft_face.set_pixel_sizes(0, px)
    infos, positions = shape(text)
    pen = float(M)
    for info, pos in zip(infos, positions):
        ft_face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bmp = ft_face.glyph.bitmap
        w, rows, pitch = bmp.width, bmp.rows, bmp.pitch
        if w and rows:
            rowbytes = [bytes(bmp.buffer[r * pitch:r * pitch + w]) for r in range(rows)]
            alpha = Image.frombytes("L", (w, rows), b"".join(rowbytes))
            gx = int(round(pen + pos.x_offset * s + ft_face.glyph.bitmap_left))
            gy = int(round(baseline - ft_face.glyph.bitmap_top - pos.y_offset * s))
            img.paste(Image.new("RGB", (w, rows), color), (gx, gy), alpha)
        pen += pos.x_advance * s


def charset_rows():
    """Group the font's encoded characters into printable rows."""
    cmap = TTFont(FONT).getBestCmap()
    def collect(lo, hi, extra=()):
        chars = [chr(c) for c in sorted(cmap) if lo <= c <= hi]
        return "".join(chars)
    rows = [
        collect(0x0410, 0x042F) + ("Ё" if ord("Ё") in cmap else ""),   # Cyrillic upper
        ("ё" if ord("ё") in cmap else "") + collect(0x0430, 0x044F),   # Cyrillic lower
        collect(0x0041, 0x005A),                                       # Latin upper
        collect(0x0061, 0x007A) + "  " + collect(0x0030, 0x0039),      # Latin lower + digits
        "".join(chr(c) for c in sorted(cmap) if 0x2190 <= c <= 0x21FF),  # arrows
        "( ) [ ] { }   " + "".join(chr(c) for c in [0x2013, 0x2014, 0x00AB, 0x00BB, 0x201C, 0x201D,
            0x2018, 0x2019, 0x00B7, 0x2022, 0x2026, 0x0040, 0x0026, 0x0023, 0x0025, 0x00A9, 0x00AE,
            0x2122, 0x00A7, 0x00B0] if c in cmap),                     # brackets + symbols
    ]
    return [r for r in rows if r.strip()]


# --- layout: build a list of (text, size, color) then flow vertically -------
BLOCKS = []                       # (kind, text, size, color)
BLOCKS.append(("label", LABEL, 22, DIM))
BLOCKS.append(("title", TITLE, 200, FG))
BLOCKS.append(("rule", "", 0, ACCENT))
for text, size, color in SAMPLES:
    BLOCKS.append(("sample", text, size, color))
if SHOW_CHARSET:
    BLOCKS.append(("seclabel", "CHARACTER SET", 18, ACCENT))
    for i, row in enumerate(charset_rows()):
        BLOCKS.append(("charset", row, CHARSET_SIZE, FG if i % 2 == 0 else DIM))

# gaps (layout px, before the block) by kind
GAP = {"label": 0, "title": 42, "rule": 40, "sample": 22, "seclabel": 60, "charset": 16}
ASCENT = 0.74                     # baseline offset from top of the line

placements = []                   # (text, size, color, baseline)  or ("rule", y)
y = M
for i, (kind, text, size, color) in enumerate(BLOCKS):
    y += GAP[kind] * SCALE if kind in GAP else 0
    if kind == "rule":
        placements.append(("rule", y))
        y += 4 * SCALE
        continue
    px = fit_size(text, size * SCALE)
    baseline = int(y + px * ASCENT)
    placements.append((text, px, color, baseline))
    y += px  # advance by the fitted cap/line height

H = int(y + M * 0.7)              # bottom padding

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)
for p in placements:
    if p[0] == "rule":
        draw.rectangle([M, p[1], W - M, p[1] + 4 * SCALE], fill=ACCENT)
    else:
        text, px, color, baseline = p
        draw_line(img, text, px, baseline, color)

img.save(OUT)
print("saved", OUT, img.size)
