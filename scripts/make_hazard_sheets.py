#!/usr/bin/env python3
"""
Hazard archive review — contact sheets (Melvin, 22 Oct 2026). READ-ONLY.

Rows: scripts/hazard_archive_report.py collect() — confirmed observations whose
candidates name a hazard species other than the confirmed one — minus rows
whose confirmed species is itself a hazard species.

  Set 1  AI-only approvals + photos on any saved walk (de-duplicated);
         walk 5 rows first, then walk 4, then the rest.
  Set 2  remaining rows with a deadly candidate.
  Set 3  everything else.
Within a group: the report's order (deadly first, strongest hazard score first).

Conventions from make_survivor_sheets.py: 60 photos per sheet, 10 cols x 6
rows, header "<set>  sheet N/T  <count> photos  ids <min>–<max>  (order: …)"
with the id range = min–max of the ids ON the sheet. One deliberate deviation:
a larger canvas (4800 px wide) with photos drawn from the full-size original,
so leaves can be judged at full size (the 225x300 thumbnails are too small).

Writes JPEG sheets + one CSV index per set to ~/Documents/ForagingID/hazard_review/
(outside the repo). Never writes to the DB.

    PYTHONPATH=. python scripts/make_hazard_sheets.py
"""
import asyncio
import csv
import sqlite3
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from hazard_archive_report import collect  # noqa: E402
from app.models.species import display_common_name  # noqa: E402

DB = PROJECT / "data" / "foragingid.db"
OUT_DIR = Path.home() / "Documents" / "ForagingID" / "hazard_review"

PER_SHEET = 60
COLS, ROWS = 10, 6
TILE_W, TILE_H = 480, 500
PHOTO_H = 360
HEADER_H = 56
PAD = 8
CANVAS_W, CANVAS_H = COLS * TILE_W, HEADER_H + ROWS * TILE_H

BG_PAGE = (32, 38, 34)
BG_TILE = (17, 22, 18)
FG_HEAD = (222, 232, 222)
FG_ID = (222, 232, 222)
FG_SP = (200, 214, 200)
FG_HAZ = (255, 110, 100)
FG_TAG = (240, 200, 90)

_F = "/System/Library/Fonts/Helvetica.ttc"
_F_SYM = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"   # Helvetica has no ☠
SETS = (("set1", "Set 1 — AI-only + on a saved walk", "walk 5, walk 4, other walks, AI-only; then report order"),
        ("set2", "Set 2 — deadly candidate", "report order: strongest hazard score first"),
        ("set3", "Set 3 — toxic candidate", "report order: strongest hazard score first"))


def _font(size, bold=False):
    try:
        return ImageFont.truetype(_F, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()


def _fit(d, text, font, width):
    """Shorten text with … until it fits width."""
    if d.textlength(text, font=font) <= width:
        return text
    while text and d.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


def _pct(v):
    return f"{v * 100:.2f}%" if isinstance(v, (int, float)) else "—"


def best_source(h):
    """The hazard's strongest source (highest score)."""
    return max(h["sources"], key=lambda s: s["score"] if isinstance(s["score"], (int, float)) else -1)


def _photo(o):
    for p in (o["file_path"], o["confirmed_copy_path"], o["thumbnail_path"]):
        if not p:
            continue
        pp = Path(p) if Path(p).is_absolute() else PROJECT / p
        if pp.is_file():
            return pp
    return None


def build_sheet(set_key, label, order_note, chunk, idx, total):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_PAGE)
    d = ImageDraw.Draw(img)
    ids = [t["id"] for t in chunk]
    d.text((14, 14), f"{label}   sheet {idx}/{total}   {len(chunk)} photos   ids {min(ids)}–{max(ids)}   "
                     f"(order: {order_note})", font=_font(26, bold=True), fill=FG_HEAD)
    f_id, f_sp, f_hz, f_tag = _font(21, True), _font(18), _font(17, True), _font(17, True)
    try:
        f_skull = ImageFont.truetype(_F_SYM, 17)
    except Exception:
        f_skull = f_hz
    inner = TILE_W - 2 * PAD - 4
    for i, t in enumerate(chunk):
        cx, cy = i % COLS, i // COLS
        x0, y0 = cx * TILE_W, HEADER_H + cy * TILE_H
        d.rectangle([x0 + 2, y0 + 2, x0 + TILE_W - 2, y0 + TILE_H - 2], fill=BG_TILE)
        p = t["photo"]
        if p:
            try:
                im = Image.open(p)
                im.draft("RGB", (inner * 2, PHOTO_H * 2))
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((inner, PHOTO_H), Image.LANCZOS)
                img.paste(im, (x0 + 2 + (TILE_W - 4 - im.width) // 2, y0 + PAD + (PHOTO_H - im.height) // 2))
            except Exception as exc:
                d.text((x0 + PAD, y0 + PAD), f"[photo error] {exc}"[:60], font=f_sp, fill=FG_HAZ)
        else:
            d.text((x0 + PAD, y0 + PAD), "[photo missing]", font=f_sp, fill=FG_HAZ)
        y = y0 + PAD + PHOTO_H + 6
        d.text((x0 + PAD, y), f"#{t['id']}", font=f_id, fill=FG_ID)
        tags = "  ".join(t["tags"])
        if tags:
            d.text((x0 + TILE_W - PAD - d.textlength(tags, font=f_tag), y + 2), tags, font=f_tag, fill=FG_TAG)
        y += 28
        d.text((x0 + PAD, y), _fit(d, t["confirmed_label"], f_sp, inner), font=f_sp, fill=FG_SP)
        y += 25
        hz = t["hazards"]
        shown = hz[:3]
        skull_w = d.textlength("☠ ", font=f_skull)
        for k, h in enumerate(shown):
            # "☠ <hazard> <source> <score>" — the name is shortened, never the score.
            tail = f" {h['source']} {_pct(h['score'])}"
            if k == len(shown) - 1 and len(hz) > 3:
                tail += f"  +{len(hz) - 3} more"
            name = _fit(d, h["label"], f_hz, inner - skull_w - d.textlength(tail, font=f_hz))
            d.text((x0 + PAD, y), "☠", font=f_skull, fill=FG_HAZ)
            d.text((x0 + PAD + skull_w, y), name + tail, font=f_hz, fill=FG_HAZ)
            y += 22
    out = OUT_DIR / f"{set_key}_sheet_{idx:02d}.jpg"
    img.save(out, "JPEG", quality=88)
    return out


def main():
    c = asyncio.run(collect())
    rows, walk_ids, index = c["rows"], c["walk_ids"], c["index"]
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    sp = {r["id"]: display_common_name(r["preferred_common_name"], r["common_names"]) or None
          for r in db.execute("SELECT id, preferred_common_name, common_names FROM species")}

    tiles = []
    skipped_self = 0
    for o, hits in rows:
        if index.resolve(o.species_primary):
            skipped_self += 1
            continue
        r = db.execute("SELECT file_path, confirmed_copy_path, thumbnail_path FROM observations WHERE id = ?",
                       (o.id,)).fetchone()
        common = sp.get(o.species_id)
        name = o.species_primary or "— (scene)"
        ai_only = o.review_status == "approved" and o.reviewed_at is None
        walks = sorted(walk_ids.get(o.id, []), reverse=True)
        hz = []
        for h in hits:
            b = best_source(h)
            hz.append({"label": h["label"], "level": h["level"], "source": b["source"], "score": b["score"],
                       "all": "; ".join(f"{s['source']} {_pct(s['score'])}" + (f" #{s['rank']}" if s["rank"] else "")
                                        for s in h["sources"])})
        tiles.append({
            "id": o.id, "photo": _photo(r), "walks": walks, "ai_only": ai_only,
            "deadly": any(h["level"] == "deadly" for h in hits),
            "confirmed": name, "common": common,
            "confirmed_label": f"{common} ({name})" if common else name,
            "tags": (["AI-only"] if ai_only else []) + (["walk " + ",".join(map(str, walks))] if walks else []),
            "hazards": hz,
        })

    def walk_rank(t):
        w = t["walks"]
        return 0 if 5 in w else 1 if 4 in w else 2 if w else 3
    s1 = sorted([t for t in tiles if t["ai_only"] or t["walks"]], key=walk_rank)    # stable: report order kept
    s1_ids = {t["id"] for t in s1}
    s2 = [t for t in tiles if t["id"] not in s1_ids and t["deadly"]]
    s3 = [t for t in tiles if t["id"] not in s1_ids and not t["deadly"]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{len(rows)} report rows; {skipped_self} skipped (confirmed species is itself a hazard); "
          f"{len(tiles)} on sheets")
    for (key, label, note), group in zip(SETS, (s1, s2, s3)):
        chunks = [group[i:i + PER_SHEET] for i in range(0, len(group), PER_SHEET)]
        with open(OUT_DIR / f"{key}_index.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["obs_id", "sheet", "tile", "row", "col", "confirmed_species", "confirmed_common",
                        "hazard_candidate", "hazard_level", "source", "score", "all_sources", "walk", "ai_only"])
            for n, chunk in enumerate(chunks, start=1):
                out = build_sheet(key, label, note, chunk, n, len(chunks))
                print(f"  {out}  ({len(chunk)} photos)")
                for i, t in enumerate(chunk):
                    for h in t["hazards"]:
                        w.writerow([t["id"], out.name, i + 1, i // COLS + 1, i % COLS + 1, t["confirmed"],
                                    t["common"] or "", h["label"], h["level"], h["source"],
                                    f"{h['score']:.4f}" if isinstance(h["score"], (int, float)) else "",
                                    h["all"], ",".join(map(str, t["walks"])), "yes" if t["ai_only"] else ""])
        missing = sum(1 for t in group if t["photo"] is None)
        print(f"{label}: {len(group)} photos, {len(chunks)} sheet(s), {missing} without a photo file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
