#!/usr/bin/env python3
"""
Survivors-only contact sheets — the 141 rows marked triage_keep=1 (migration 0050).

Rebuild of the generator that produced the 25 whole-queue sheets on 15 July.
Those sheets were written to ~/Documents/ForagingID/triage/ at the time and
were moved into data/triage_sheets/triage/ on 18 July; nothing writes outside
PROJECT_ROOT any more. The original script was not in the repo, so this is a
reimplementation matched to the surviving artifacts rather than the original
tool. Conventions taken from no_plant_signal_sheet_14.jpg:

  canvas      2488x1360, 10 cols x 6 rows = 60 photos/sheet
  ordering    photo_taken_at ASC, NULLs last, id as tiebreak
  header      "<band>  sheet N/T  <count> photos  ids <min>–<max>  (order: ...)"
              The header is load-bearing: its printed "60 photos" is what
              resolved the sheet-size ambiguity that arithmetic alone could not
              (60 and 63 both fit every band). Keep it.
  id range    min–max of the ids ON the sheet, NOT first–last in order. Verified
              against sheet 14: header reads 11132–20553 while the ordering runs
              20504 … 19861.
  per photo   "#<id>  <YYYY-MM-DD>"

One deliberate deviation, flagged in the report: the survivor set spans three
prefilter bands (125 no_plant_signal + 8 sky_blue + 8 person_animal), so the
header cannot name a single band and each cell carries a small band tag. The
whole-queue sheets were single-band and needed neither.

Reads only. Writes JPEGs to a distinct directory; never touches the DB and never
overwrites the 15 July sheets, which remain the whole-queue reference.
"""
import sqlite3
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parent.parent
DB = PROJECT / "data" / "foragingid.db"
OUT_DIR = PROJECT / "data" / "triage_sheets" / "triage_survivors"

PER_SHEET = 60
COLS, ROWS = 10, 6
CANVAS_W, CANVAS_H = 2488, 1360
HEADER_H = 40
PAD = 8
LABEL_H = 26

BG_PAGE = (32, 38, 34)
BG_TILE = (17, 22, 18)
FG_HEAD = (222, 232, 222)
FG_ID = (222, 232, 222)
FG_DATE = (132, 146, 132)
FG_BAND = (108, 126, 108)

_F = "/System/Library/Fonts/Helvetica.ttc"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_F, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()


def fetch_keepers() -> list:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT id, thumbnail_path, photo_taken_at, prefilter_category
           FROM observations
           WHERE triage_keep = 1
           ORDER BY (photo_taken_at IS NULL), photo_taken_at, id"""
    ).fetchall()
    db.close()
    return rows


def build_sheet(chunk: list, idx: int, total: int) -> Path:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_PAGE)
    d = ImageDraw.Draw(img)

    ids = [r["id"] for r in chunk]
    head = (f"keepers (survivors)   sheet {idx}/{total}   {len(chunk)} photos   "
            f"ids {min(ids)}–{max(ids)}   (order: photo_taken_at asc)")
    d.text((10, 11), head, font=_font(19, bold=True), fill=FG_HEAD)

    cw = CANVAS_W / COLS
    ch = (CANVAS_H - HEADER_H) / ROWS

    for i, r in enumerate(chunk):
        cx, cy = i % COLS, i // COLS
        x0 = int(cx * cw)
        y0 = int(HEADER_H + cy * ch)
        x1 = int((cx + 1) * cw) - 2
        y1 = int(HEADER_H + (cy + 1) * ch) - 2
        d.rectangle([x0 + 2, y0, x1, y1], fill=BG_TILE)

        # Thumbnail, aspect-preserved, centred in the cell above the label strip
        tp = r["thumbnail_path"] or ""
        p = Path(tp)
        if not p.is_absolute():
            p = PROJECT / p
        box_w = (x1 - x0) - 2 * PAD
        box_h = (y1 - y0) - LABEL_H - PAD
        if p.exists():
            try:
                th = Image.open(p).convert("RGB")
                th.thumbnail((box_w, box_h), Image.LANCZOS)
                ox = x0 + 2 + ((x1 - x0 - 2) - th.width) // 2
                oy = y0 + PAD + (box_h - th.height) // 2
                img.paste(th, (ox, oy))
            except Exception as exc:
                d.text((x0 + PAD, y0 + PAD), f"[thumb error]\n{exc}",
                       font=_font(11), fill=(200, 90, 90))
        else:
            d.text((x0 + PAD, y0 + PAD), "[thumbnail missing]",
                   font=_font(11), fill=(200, 90, 90))

        ly = y1 - LABEL_H + 6
        d.text((x0 + PAD, ly), f"#{r['id']}", font=_font(13, bold=True), fill=FG_ID)
        date = (str(r["photo_taken_at"])[:10] if r["photo_taken_at"] else "no date")
        d.text((x0 + PAD + 58, ly + 1), date, font=_font(11), fill=FG_DATE)
        band = (r["prefilter_category"] or "")
        if band and band != "no_plant_signal":
            d.text((x0 + PAD + 132, ly + 1), band, font=_font(10), fill=FG_BAND)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"keepers_sheet_{idx:02d}.jpg"
    img.save(out, "JPEG", quality=88)
    return out


def main() -> int:
    keepers = fetch_keepers()
    if not keepers:
        print("No rows with triage_keep=1 — nothing to build.")
        return 1
    chunks = [keepers[i:i + PER_SHEET] for i in range(0, len(keepers), PER_SHEET)]
    total = len(chunks)
    print(f"{len(keepers)} keepers -> {total} sheet(s) at {PER_SHEET}/sheet")
    for n, chunk in enumerate(chunks, start=1):
        out = build_sheet(chunk, n, total)
        ids = [r["id"] for r in chunk]
        print(f"  {out}")
        print(f"     {len(chunk)} photos | ids {min(ids)}–{max(ids)} | "
              f"order {ids[0]} … {ids[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
