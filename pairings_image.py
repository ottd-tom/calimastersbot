"""
Image rendering for BCP tables (pairings and standings).

    from pairings_image import (
        render_pairings_images_async,
        render_standings_images_async,
        fonts_available,
    )

Requires Pillow. Bundle fonts/DejaVuSans.ttf and fonts/DejaVuSans-Bold.ttf
next to this file so rendering doesn't depend on the host image.
"""

from __future__ import annotations

import asyncio
import io
import os
from dataclasses import dataclass
from typing import Callable, Sequence

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

BG      = (30, 31, 34)
HEAD_BG = (43, 45, 49)
STRIPE  = (35, 36, 40)
LINE    = (58, 60, 66)
TEXT    = (219, 222, 225)
MUTED   = (148, 155, 164)
WIN     = (87, 242, 135)
GOLD    = (255, 196, 61)
SILVER  = (198, 216, 240)
BRONZE  = (215, 141, 74)

_HERE = os.path.dirname(os.path.abspath(__file__))

_FONT_CANDIDATES = {
    "regular": [
        os.path.join(_HERE, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "DejaVuSans.ttf",
    ],
    "bold": [
        os.path.join(_HERE, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
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
    raise RuntimeError("No usable TrueType font found for table images")


def fonts_available() -> bool:
    """Cheap startup check so you can fall back to text if the host has no fonts."""
    try:
        _load_font("regular", 12)
        return True
    except RuntimeError:
        return False


# ─── Column spec ──────────────────────────────────────────────────────────────

@dataclass
class Col:
    label: str
    kind: str = "text"      # "text" | "name" | "num"
    align: str = "left"     # "left" | "center"
    min_w: int = 40         # unscaled px
    max_w: int = 260        # unscaled px; content past this is shortened

    @property
    def bold(self) -> bool:
        return self.kind == "num"


# Colour hook: (row_index, col_index, value, row) -> RGB tuple or None
Colorizer = Callable[[int, int, str, Sequence[str]], "tuple[int, int, int] | None"]


# ─── Text fitting ─────────────────────────────────────────────────────────────

def _w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _ellipsize(draw, text: str, font, max_w: float) -> str:
    if _w(draw, text, font) <= max_w:
        return text
    out = text
    while out and _w(draw, out + "…", font) > max_w:
        out = out[:-1]
    return (out + "…") if out else "…"


def _shrink_name(draw, name: str, font, max_w: float) -> str:
    """Fit a name into max_w: full → first + initial → initial + last → ellipsis."""
    if _w(draw, name, font) <= max_w:
        return name

    parts = name.split()
    if len(parts) >= 2:
        for candidate in (
            f"{' '.join(parts[:-1])} {parts[-1][0]}.",   # Christopher Vandenbergh -> Christopher V.
            f"{parts[0][0]}. {parts[-1]}",               # -> C. Vandenbergh
        ):
            if _w(draw, candidate, font) <= max_w:
                return candidate

    return _ellipsize(draw, name, font, max_w)


def _fit(draw, col: Col, value: str, font, width: float) -> str:
    if col.kind == "name":
        return _shrink_name(draw, value, font, width)
    return _ellipsize(draw, value, font, width)


# ─── Core renderer ────────────────────────────────────────────────────────────

def _render_table(
    title: str,
    subtitle: str,
    cols: Sequence[Col],
    rows: Sequence[Sequence[str]],
    colorize: Colorizer | None = None,
) -> io.BytesIO:
    f_reg = _load_font("regular", FONT_SIZE * SCALE)
    f_bold = _load_font("bold", FONT_SIZE * SCALE)
    f_title = _load_font("bold", TITLE_SIZE * SCALE)
    f_sub = _load_font("regular", SUB_SIZE * SCALE)

    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    pad, gap = PAD * SCALE, COL_GAP * SCALE
    row_h, head_h = ROW_H * SCALE, HEAD_H * SCALE

    # --- measure each column against real glyph widths, not character counts
    widths = []
    for i, col in enumerate(cols):
        font = f_bold if col.bold else f_reg
        label_w = _w(probe, col.label, f_bold)
        w = max(col.min_w * SCALE, label_w)
        for row in rows:
            w = max(w, _w(probe, row[i], font))
        widths.append(min(w, max(col.max_w * SCALE, label_w)))

    table_w = sum(widths) + gap * (len(cols) - 1)
    title_block = int(TITLE_SIZE * 1.5 * SCALE) + (int(SUB_SIZE * 1.6 * SCALE) if subtitle else 0)
    width = int(max(table_w, _w(probe, title, f_title), _w(probe, subtitle, f_sub)) + pad * 2)
    height = int(pad + title_block + head_h + row_h * len(rows) + pad)

    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    y = pad
    d.text((pad, y), title, font=f_title, fill=TEXT)
    y += int(TITLE_SIZE * 1.5 * SCALE)
    if subtitle:
        d.text((pad, y), subtitle, font=f_sub, fill=MUTED)
        y += int(SUB_SIZE * 1.6 * SCALE)

    xs, x = [], float(pad)
    for w in widths:
        xs.append(x)
        x += w + gap

    # --- column header band
    d.rectangle([0, y, width, y + head_h], fill=HEAD_BG)
    for col, cx, cw in zip(cols, xs, widths):
        center = col.align == "center"
        d.text((cx + cw / 2 if center else cx, y + head_h / 2),
               _ellipsize(d, col.label, f_bold, cw),
               font=f_bold, fill=MUTED, anchor="mm" if center else "lm")
    y += head_h

    # --- body
    for r, row in enumerate(rows):
        if r % 2:
            d.rectangle([0, y, width, y + row_h], fill=STRIPE)
        d.line([(0, y), (width, y)], fill=LINE, width=1)

        mid = y + row_h / 2
        for c, (col, cx, cw) in enumerate(zip(cols, xs, widths)):
            value = row[c]
            font = f_bold if col.bold else f_reg
            colour = (colorize(r, c, value, row) if colorize else None) or TEXT
            center = col.align == "center"
            d.text((cx + cw / 2 if center else cx, mid),
                   _fit(d, col, value, font, cw),
                   font=font, fill=colour, anchor="mm" if center else "lm")
        y += row_h

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


def render_table_images(
    title: str,
    subtitle: str,
    cols: Sequence[Col],
    rows: Sequence[Sequence[str]],
    colorize: Colorizer | None = None,
    rows_per_image: int = 24,
) -> list[io.BytesIO]:
    """Render rows into one or more PNGs, splitting long tables across images."""
    if not rows:
        return []

    chunks = [rows[i:i + rows_per_image] for i in range(0, len(rows), rows_per_image)]
    out = []
    for n, chunk in enumerate(chunks, 1):
        sub = subtitle
        if len(chunks) > 1:
            sub = f"{subtitle} · page {n}/{len(chunks)}" if subtitle else f"page {n}/{len(chunks)}"

        # keep colorize row indices relative to the whole table, not the page
        page_colorize = None
        if colorize:
            offset = (n - 1) * rows_per_image

            def page_colorize(r, c, v, row, _o=offset):
                return colorize(r + _o, c, v, row)

        out.append(_render_table(title, sub, cols, chunk, page_colorize))
    return out


# ─── Pairings ─────────────────────────────────────────────────────────────────

def render_pairings_images(
    title: str,
    subtitle: str,
    rows: Sequence[tuple[str, str, str, str, str]],
    show_table_col: bool = True,
) -> list[io.BytesIO]:
    """rows = (table, name1, pts1, name2, pts2)."""
    if not rows:
        return []
    show_table_col = show_table_col and any(r[0] for r in rows)

    cols = [Col("#", "num", "center", min_w=30)] if show_table_col else []
    cols += [
        Col("Player 1", "name", min_w=96, max_w=210),
        Col("Pts", "num", "center", min_w=34),
        Col("Player 2", "name", min_w=96, max_w=210),
        Col("Pts", "num", "center", min_w=34),
    ]

    body = [list(r) if show_table_col else list(r[1:]) for r in rows]
    shift = 0 if show_table_col else 1   # column index shift when "#" is absent

    def colorize(r, c, value, row):
        idx = c + shift                  # index into the canonical 5-tuple
        if idx == 0:
            return MUTED
        bye = row[3 - shift] == "(bye)"
        try:
            i1, i2 = int(row[2 - shift]), int(row[4 - shift])
        except ValueError:
            i1 = i2 = 0
        if idx in (1, 2):
            return WIN if i1 > i2 else None
        if idx in (3, 4):
            if bye:
                return MUTED
            return WIN if i2 > i1 else None
        return None

    return render_table_images(title, subtitle, cols, body, colorize)


# ─── Standings ────────────────────────────────────────────────────────────────

def render_standings_images(
    title: str,
    subtitle: str,
    metric_names: Sequence[str],
    rows: Sequence[Sequence[str]],
    faction_col: bool = False,
) -> list[io.BytesIO]:
    """
    rows = (place, name, *metric values)             when faction_col is False
    rows = (place, faction, name, *metric values)    when faction_col is True
    """
    if not rows:
        return []

    cols = [Col("#", "num", "center", min_w=32)]
    if faction_col:
        cols.append(Col("Faction", "text", min_w=60, max_w=130))
    cols.append(Col("Name", "name", min_w=110, max_w=230))
    cols += [Col(m, "num", "center", min_w=40, max_w=110) for m in metric_names]

    medals = {"1": GOLD, "2": SILVER, "3": BRONZE}
    name_idx = 2 if faction_col else 1

    def colorize(r, c, value, row):
        medal = medals.get(str(row[0]).strip())
        if c == 0:
            return medal or MUTED
        if c == name_idx:
            return medal
        if faction_col and c == 1:
            return MUTED
        return None

    return render_table_images(title, subtitle, cols, [list(r) for r in rows],
                               colorize, rows_per_image=28)


# ─── Async wrappers (Pillow is blocking; keep it off the event loop) ──────────

async def _to_thread(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


async def render_pairings_images_async(*args, **kwargs) -> list[io.BytesIO]:
    return await _to_thread(render_pairings_images, *args, **kwargs)


async def render_standings_images_async(*args, **kwargs) -> list[io.BytesIO]:
    return await _to_thread(render_standings_images, *args, **kwargs)
