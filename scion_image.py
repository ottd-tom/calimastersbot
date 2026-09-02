"""
scion_image.py — table renderer for the !sciontracker command.

Drop this next to pairings_image.py. Public API:

    scion_fonts_available() -> bool
    render_scion_images(sections, *, title, subtitle) -> list[BytesIO]
    render_scion_images_async(sections, *, title, subtitle) -> list[BytesIO]

`sections` is a list of dicts:

    {
        "event": "Big GT 2026",
        "round": "Round 3",
        "rows": [
            {
                "player":   "Alice Smith",
                "faction":  "SBGL",
                "colour":   "#6f42c1",     # optional, alliance colour
                "record":   "2-0",
                "score":    "18-14",
                "result":   "W",           # W / L / D / "" / "·"
                "opponent": "Bob Jones",
                "opp_faction": "NH",       # optional
            },
        ],
    }
"""

from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# ── Palette (Discord dark) ───────────────────────────────────────────────────
BG          = "#2b2d31"
TITLE_BAND  = "#1e1f22"
ROW_ALT     = "#303237"
EVENT_BAND  = "#383a40"
TEXT        = "#f2f3f5"
MUTED       = "#949ba4"
DIM         = "#72767d"
RULE        = "#40444b"
ACCENT      = "#5865f2"
WIN         = "#3ba55d"
LOSS        = "#ed4245"
DRAW        = "#faa81a"

RESULT_COLOURS = {"W": WIN, "L": LOSS, "D": DRAW}

# ── Layout ───────────────────────────────────────────────────────────────────
PAD          = 30
COL_GAP      = 28
ROW_H        = 46
HEADER_H     = 40
EVENT_H      = 52
TITLE_H      = 104
MIN_WIDTH    = 780
ROWS_PER_IMG = 22          # body units (rows + event headers) per image

FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "DejaVuSans.ttf",
]
FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "DejaVuSans-Bold.ttf",
]


def _font(paths: list[str], size: int):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return None


def scion_fonts_available() -> bool:
    """True if a real TrueType font is loadable — otherwise callers fall back to text."""
    return _font(FONT_REGULAR, 20) is not None and _font(FONT_BOLD, 20) is not None


def _width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    if not text:
        return 0
    try:
        return int(draw.textlength(text, font=font))
    except AttributeError:                       # very old Pillow
        return int(draw.textsize(text, font=font)[0])


def _opp_text(row: dict) -> tuple[str, str]:
    opp = row.get("opponent") or ""
    fac = row.get("opp_faction") or ""
    return opp, (f"  ({fac})" if fac else "")


def _blocks(sections: list[dict]) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for sec in sections:
        head = sec.get("event", "")
        rnd = sec.get("round") or ""
        out.append(("event", f"{head}   ·   {rnd}" if rnd else head))
        for row in sec.get("rows", []):
            out.append(("row", row))
    return out


def _paginate(blocks, limit: int) -> list[list]:
    pages, cur, units, last_event = [], [], 0, None
    for kind, payload in blocks:
        if kind == "event":
            last_event = payload
            if cur and units + 2 > limit:        # don't orphan a header
                pages.append(cur)
                cur, units = [], 0
        elif kind == "row" and units >= limit:
            pages.append(cur)
            cur, units = [], 0
            if last_event:
                cur.append(("event", f"{last_event}  (cont.)"))
                units += 1
        cur.append((kind, payload))
        units += 1
    if cur:
        pages.append(cur)
    return pages


def render_scion_images(
    sections: list[dict],
    *,
    title: str = "Scion Tracker",
    subtitle: str = "",
) -> list[BytesIO]:
    f_title = _font(FONT_BOLD, 34)
    f_sub   = _font(FONT_REGULAR, 20)
    f_event = _font(FONT_BOLD, 23)
    f_head  = _font(FONT_BOLD, 18)
    f_name  = _font(FONT_BOLD, 22)
    f_cell  = _font(FONT_REGULAR, 22)
    f_res   = _font(FONT_BOLD, 23)

    if not all([f_title, f_sub, f_event, f_head, f_name, f_cell, f_res]):
        raise RuntimeError("No usable TrueType font found")

    all_rows = [p for _, p in _blocks(sections) if isinstance(p, dict)]
    if not all_rows:
        raise ValueError("Nothing to render")

    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    headers = ["PLAYER", "FACTION", "REC", "SCORE", "", "OPPONENT"]
    mins    = [180, 90, 62, 92, 46, 200]
    widths  = [max(m, _width(probe, h, f_head)) for h, m in zip(headers, mins)]

    for r in all_rows:
        opp, opp_fac = _opp_text(r)
        cells = [
            (r.get("player", ""),   f_name),
            (r.get("faction", ""),  f_cell),
            (r.get("record", ""),   f_cell),
            (r.get("score", ""),    f_cell),
            (r.get("result", ""),   f_res),
            (opp + opp_fac,         f_cell),
        ]
        for i, (txt, fnt) in enumerate(cells):
            widths[i] = max(widths[i], _width(probe, txt, fnt))

    table_w = sum(widths) + COL_GAP * (len(widths) - 1)
    img_w = max(MIN_WIDTH, table_w + PAD * 2, _width(probe, title, f_title) + PAD * 2)

    xs, x = [], PAD
    for w in widths:
        xs.append(x)
        x += w + COL_GAP
    # let the opponent column soak up any slack
    widths[-1] = max(widths[-1], img_w - PAD - xs[-1])

    pages = _paginate(_blocks(sections), ROWS_PER_IMG)
    buffers: list[BytesIO] = []

    for page_no, page in enumerate(pages, 1):
        body_h = sum(EVENT_H if k == "event" else ROW_H for k, _ in page)
        img_h = TITLE_H + HEADER_H + body_h + PAD

        img = Image.new("RGB", (img_w, img_h), BG)
        d = ImageDraw.Draw(img)

        # ── Title band ──
        d.rectangle([0, 0, img_w, TITLE_H], fill=TITLE_BAND)
        d.rectangle([0, TITLE_H - 3, img_w, TITLE_H], fill=ACCENT)
        head_text = title if len(pages) == 1 else f"{title}  ({page_no}/{len(pages)})"
        d.text((PAD, 26), head_text, font=f_title, fill=TEXT)
        if subtitle:
            d.text((PAD, 68), subtitle, font=f_sub, fill=MUTED)

        # ── Column headers ──
        y = TITLE_H
        hy = y + (HEADER_H - 18) // 2
        for i, h in enumerate(headers):
            if not h:
                continue
            if i in (2, 3, 4):
                tx = xs[i] + (widths[i] - _width(d, h, f_head)) // 2
            else:
                tx = xs[i]
            d.text((tx, hy), h, font=f_head, fill=DIM)
        y += HEADER_H
        d.line([(PAD, y - 1), (img_w - PAD, y - 1)], fill=RULE, width=1)

        # ── Body ──
        stripe = 0
        for kind, payload in page:
            if kind == "event":
                d.rectangle([0, y, img_w, y + EVENT_H], fill=EVENT_BAND)
                d.rectangle([0, y, 5, y + EVENT_H], fill=ACCENT)
                d.text((PAD, y + (EVENT_H - 26) // 2), str(payload), font=f_event, fill=TEXT)
                y += EVENT_H
                stripe = 0
                continue

            row = payload
            if stripe % 2 == 1:
                d.rectangle([0, y, img_w, y + ROW_H], fill=ROW_ALT)
            stripe += 1
            ty = y + (ROW_H - 26) // 2

            d.text((xs[0], ty), row.get("player", ""), font=f_name, fill=TEXT)
            d.text((xs[1], ty), row.get("faction", ""), font=f_cell,
                   fill=row.get("colour") or MUTED)

            for idx, key in ((2, "record"), (3, "score")):
                val = row.get(key) or "—"
                tx = xs[idx] + (widths[idx] - _width(d, val, f_cell)) // 2
                d.text((tx, ty), val, font=f_cell, fill=TEXT if row.get(key) else DIM)

            res = (row.get("result") or "").strip()
            if res:
                tx = xs[4] + (widths[4] - _width(d, res, f_res)) // 2
                d.text((tx, ty), res, font=f_res, fill=RESULT_COLOURS.get(res, DIM))

            opp, opp_fac = _opp_text(row)
            d.text((xs[5], ty), opp, font=f_cell, fill=TEXT if opp else DIM)
            if opp_fac:
                d.text((xs[5] + _width(d, opp, f_cell), ty), opp_fac, font=f_cell, fill=MUTED)

            y += ROW_H
            d.line([(PAD, y - 1), (img_w - PAD, y - 1)], fill=RULE, width=1)

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buffers.append(buf)

    return buffers


async def render_scion_images_async(sections, *, title="Scion Tracker", subtitle="") -> list[BytesIO]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: render_scion_images(sections, title=title, subtitle=subtitle)
    )
