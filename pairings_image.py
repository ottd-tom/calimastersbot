"""
Image rendering for BCP pairings tables.

Drop this in next to your bot code and `from pairings_image import render_pairings_images`.
Requires Pillow:  pip install Pillow
"""

from __future__ import annotations

import asyncio
import io
import os
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

# ─── Look and feel ────────────────────────────────────────────────────────────

SCALE = 2          # render at 2x so phones can zoom without it going fuzzy
FONT_SIZE = 15
TITLE_SIZE = 17
SUB_SIZE = 13
ROW_H = 30
HEAD_H = 28
PAD = 16
COL_GAP = 14

MIN_NAME_W = 96
MAX_NAME_W = 210   # past this, names get shortened rather than widening the image
MIN_PTS_W = 34
MIN_TABLE_W = 30

BG      = (30, 31, 34)
HEAD_BG = (43, 45, 49)
STRIPE  = (35, 36, 40)
LINE    = (58, 60, 66)
TEXT    = (219, 222, 225)
MUTED   = (148, 155, 164)
ACCENT  = (88, 101, 242)
WIN     = (87, 242, 135)

MAX_ROWS_PER_IMAGE = 24   # split long events across several images

# Fonts bundled next to this file win, so the render is identical everywhere and
# doesn't depend on whatever the host image happens to ship.
_HERE = os.path.dirname(os.path.abspath(__file__))

_FONT_CANDIDATES = {
    "regular": [
        os.path.join(_HERE, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "DejaVuSans.ttf",
    ],
    "bold": [
        os.path.join(_HERE, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "DejaVuSans-Bold.ttf",
    ],
}


def _load_font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    raise RuntimeError("No usable TrueType font found for pairings images")


def fonts_available() -> bool:
    """Cheap startup check so you can fall back to text if the host has no fonts."""
    try:
        _load_font("regular", 12)
        return True
    except RuntimeError:
        return False


# ─── Text fitting ─────────────────────────────────────────────────────────────

def _w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _shrink_name(draw, name: str, font, max_w: float) -> str:
    """Fit a name into max_w: full name → first + initial → truncate with ellipsis."""
    if _w(draw, name, font) <= max_w:
        return name

    parts = name.split()
    if len(parts) >= 2:
        # "Christopher Vandenbergh" -> "Christopher V."
        short = f"{' '.join(parts[:-1])} {parts[-1][0]}."
        if _w(draw, short, font) <= max_w:
            return short
        # "Christopher V." -> "C. Vandenbergh"
        short = f"{parts[0][0]}. {parts[-1]}"
        if _w(draw, short, font) <= max_w:
            return short

    out = name
    while out and _w(draw, out + "…", font) > max_w:
        out = out[:-1]
    return (out + "…") if out else "…"


# ─── Rendering ────────────────────────────────────────────────────────────────

def _render_one(
    title: str,
    subtitle: str,
    rows: Sequence[tuple[str, str, str, str, str]],
    show_table_col: bool,
) -> io.BytesIO:
    """rows = (table, name1, pts1, name2, pts2). Blank strings are fine."""
    f_reg = _load_font("regular", FONT_SIZE * SCALE)
    f_bold = _load_font("bold", FONT_SIZE * SCALE)
    f_title = _load_font("bold", TITLE_SIZE * SCALE)
    f_sub = _load_font("regular", SUB_SIZE * SCALE)

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    pad = PAD * SCALE
    gap = COL_GAP * SCALE
    row_h = ROW_H * SCALE
    head_h = HEAD_H * SCALE

    # --- measure columns against real glyph widths, not character counts
    name_max = MAX_NAME_W * SCALE
    name_w = MIN_NAME_W * SCALE
    for _, n1, _, n2, _ in rows:
        name_w = max(name_w, _w(probe, n1, f_reg), _w(probe, n2, f_reg))
    name_w = min(name_w, name_max)
    name_w = max(name_w, _w(probe, "Player 1", f_bold), _w(probe, "Player 2", f_bold))

    pts_w = MIN_PTS_W * SCALE
    for _, _, p1, _, p2 in rows:
        pts_w = max(pts_w, _w(probe, p1, f_bold), _w(probe, p2, f_bold))
    pts_w = max(pts_w, _w(probe, "Pts", f_bold))

    table_w = 0.0
    if show_table_col:
        table_w = MIN_TABLE_W * SCALE
        for t, *_ in rows:
            table_w = max(table_w, _w(probe, t, f_reg))
        table_w = max(table_w, _w(probe, "#", f_bold))

    cols = ([table_w] if show_table_col else []) + [name_w, pts_w, name_w, pts_w]
    table_width = sum(cols) + gap * (len(cols) - 1)

    title_block = int(TITLE_SIZE * 1.5 * SCALE) + (int(SUB_SIZE * 1.6 * SCALE) if subtitle else 0)
    width = int(max(table_width, _w(probe, title, f_title), _w(probe, subtitle, f_sub)) + pad * 2)
    height = int(pad + title_block + head_h + row_h * len(rows) + pad)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    # --- header text
    y = pad
    d.text((pad, y), title, font=f_title, fill=TEXT)
    y += int(TITLE_SIZE * 1.5 * SCALE)
    if subtitle:
        d.text((pad, y), subtitle, font=f_sub, fill=MUTED)
        y += int(SUB_SIZE * 1.6 * SCALE)

    # --- column x positions
    xs, x = [], float(pad)
    for c in cols:
        xs.append(x)
        x += c + gap

    labels = (["#"] if show_table_col else []) + ["Player 1", "Pts", "Player 2", "Pts"]
    centered = {i for i, l in enumerate(labels) if l in ("Pts", "#")}

    # --- column header band
    d.rectangle([0, y, width, y + head_h], fill=HEAD_BG)
    for i, (label, cx, cw) in enumerate(zip(labels, xs, cols)):
        tx = cx + cw / 2 if i in centered else cx
        d.text((tx, y + head_h / 2), label, font=f_bold, fill=MUTED,
               anchor=("mm" if i in centered else "lm"))
    y += head_h

    # --- rows
    for r, (t, n1, p1, n2, p2) in enumerate(rows):
        if r % 2:
            d.rectangle([0, y, width, y + row_h], fill=STRIPE)
        d.line([(0, y), (width, y)], fill=LINE, width=1)

        bye = n2 == "(bye)"
        try:
            i1, i2 = int(p1), int(p2)
        except ValueError:
            i1 = i2 = 0
        c1 = WIN if i1 > i2 else TEXT
        c2 = WIN if i2 > i1 else TEXT
        if bye:
            c2 = MUTED

        cells = ([(t, MUTED, True)] if show_table_col else []) + [
            (n1, c1, False), (p1, c1, True),
            (n2, c2, False), (p2, c2, True),
        ]
        mid = y + row_h / 2
        for (val, colour, center), cx, cw in zip(cells, xs, cols):
            if not center:
                val = _shrink_name(d, val, f_reg, cw)
            font = f_bold if center else f_reg
            tx = cx + cw / 2 if center else cx
            d.text((tx, mid), val, font=font, fill=colour,
                   anchor=("mm" if center else "lm"))
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def render_pairings_images(
    title: str,
    subtitle: str,
    rows: Sequence[tuple[str, str, str, str, str]],
    show_table_col: bool = True,
) -> list[io.BytesIO]:
    """Render rows into one or more PNGs, splitting long lists across images."""
    if not rows:
        return []
    show_table_col = show_table_col and any(r[0] for r in rows)

    chunks = [rows[i:i + MAX_ROWS_PER_IMAGE] for i in range(0, len(rows), MAX_ROWS_PER_IMAGE)]
    out = []
    for n, chunk in enumerate(chunks, 1):
        sub = subtitle
        if len(chunks) > 1:
            sub = f"{subtitle} · page {n}/{len(chunks)}" if subtitle else f"page {n}/{len(chunks)}"
        out.append(_render_one(title, sub, chunk, show_table_col))
    return out


async def render_pairings_images_async(*args, **kwargs) -> list[io.BytesIO]:
    """Pillow is CPU-bound and blocking — keep it off the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: render_pairings_images(*args, **kwargs))
