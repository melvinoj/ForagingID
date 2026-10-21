"""
PFAF fallback refill + false "no medicinal uses" cleanup (Melvin D2–D5 and his
21 Oct follow-ups — audit REPORT section 0). Everything goes through the shared
rules: app/services/pfaf_fallback.py and the claim predicate in
app/services/ai_placeholder.py.

FIELDS (culinary_info.medicinal_notes):
  A. the text is only the "no medicinal uses" answer (a disclaimer / heading at
     most before it) — the 4b rule: PFAF's own Medicinal Uses text (history
     'pfaf_fallback'), else cleared; toxic/inedible always cleared, never PFAF
     ('system:clear_false_default').
  E. real text with a "no uses" sentence in it (after culinary text, or at the
     end) — ONLY those sentences are removed, the rest kept verbatim; no PFAF
     text ('system:clear_false_default'; the ai-approved flag stays).
  B. empty, PFAF text available — PFAF text.
  Human-locked fields are never written.

DRAFTS (species_ai_drafts, pending, medicinal_notes / medicinal_folklore):
  every draft making the claim where the stored PFAF page lists uses →
  status 'invalidated', reason in generation_context_json. Then, only with
  --redraft: one fresh medicinal_notes draft per non-toxic species through the
  normal path (enrichment._section_ai_draft — DeepSeek, PFAF context). Toxic /
  inedible species: invalidate only. The dry run and --apply never call DeepSeek;
  they count the calls.

Usage (project root):
  python scripts/pfaf_fallback_refill.py [--db PATH] [--out FILE]   # dry run (read-only DB)
  python scripts/pfaf_fallback_refill.py [--db PATH] --apply         # write fields + drafts, read back by id
  python scripts/pfaf_fallback_refill.py --apply --redraft           # …then the DeepSeek re-drafts (live only)
Take a Settings snapshot first.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model)
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species, SpeciesAIDraft, display_common_name  # noqa: E402
from app.services.ai_placeholder import (has_no_medicinal_uses_claim,  # noqa: E402
                                         is_only_no_medicinal_uses_claim)
from app.services.pfaf_fallback import (CLEAR_CHANGED_BY, ai_content_excluded,  # noqa: E402
                                        apply_pfaf_fallback, is_false_no_uses_claim,
                                        plan_pfaf_fallback, stored_pfaf)

FIELD = "medicinal_notes"
DRAFT_FIELDS = ("medicinal_notes", "medicinal_folklore")
INVALIDATE_REASON = "false no-uses, PFAF lists uses"

# Labels only (which earlier list a row belonged to) — the decisions use the shared predicate.
_OLD_LITERAL = re.compile(r"\bno\s+(?:known\s+)?traditional\s+medicinal\s+uses\b", re.I)


def _old_opening_claim(text: str) -> bool:
    """The pre-fix predicate (first sentence only) — to label 'the 45'."""
    t = (text or "").strip().lstrip("#*_ ").strip()
    m = re.search(r"(?<=[.!?])\s|\n", t)
    return bool(re.search(r"\bno\s+(?:known\s+)?traditional\s+medicinal\s+(?:uses|folklore)\b",
                          (t[:m.start()] if m else t)[:250].lower()))


def _name(sp: Species) -> str:
    common = display_common_name(sp.preferred_common_name, sp.common_names)
    return f"{common} (*{sp.scientific_name}*)" if common else f"*{sp.scientific_name}*"


def _cell(text, n=60) -> str:
    t = " ".join((text or "").split())
    if not t:
        return "∅"
    t = t if len(t) <= n else t[:n - 1] + "…"
    return t.replace("|", "\\|")


def _outcome(d) -> str:
    if d.action == "fill":
        return "PFAF fill"
    if d.action == "strip":
        return "claim removed, rest kept"
    if d.action == "clear":
        return "toxic cleared" if d.reason == "toxic_or_inedible" else f"cleared ({d.reason})"
    return f"untouched ({d.reason})"


async def _field_rows(s):
    out = []
    pairs = (await s.execute(
        select(CulinaryInfo, Species).join(Species, Species.id == CulinaryInfo.species_id)
        .order_by(Species.scientific_name)
    )).all()
    for ci, sp in pairs:
        current = ci.medicinal_notes
        if has_no_medicinal_uses_claim(current):
            group = "A" if is_only_no_medicinal_uses_claim(current) else "E"
        elif not (current or "").strip():
            group = "B"
        else:
            continue
        decision = (await plan_pfaf_fallback(s, sp, ci, [FIELD]))[0]
        if group == "B" and decision.action != "fill":
            continue
        pfaf = await stored_pfaf(s, sp)
        hist = (await s.execute(
            select(CulinaryInfoHistory.changed_by, CulinaryInfoHistory.changed_at)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == FIELD)
            .order_by(CulinaryInfoHistory.changed_at.desc(), CulinaryInfoHistory.id.desc())
        )).all()
        out.append({
            "group": group, "ci_id": ci.id, "species_id": sp.id, "name": _name(sp),
            "current": current, "decision": decision,
            "label": "the 55" if _OLD_LITERAL.search(current or "") else "newly caught",
            "pfaf": ("yes" if (pfaf and pfaf.medicinal_folklore) else "None known" if pfaf else "no page"),
            "locked": any(h[0] == "human" for h in hist),
            "toxic": ai_content_excluded(sp),
            "provenance": (f"{hist[0][0]} {hist[0][1]:%Y-%m-%d}" if hist else "no history"),
            "ci_before": {c.name: getattr(ci, c.name) for c in CulinaryInfo.__table__.columns},
        })
    return out


async def _draft_rows(s):
    out, true_claims = [], 0
    rows = (await s.execute(
        select(SpeciesAIDraft, Species).join(Species, Species.id == SpeciesAIDraft.species_id)
        .where(SpeciesAIDraft.field_name.in_(DRAFT_FIELDS)).where(SpeciesAIDraft.status == "pending")
        .order_by(Species.scientific_name, SpeciesAIDraft.id)
    )).all()
    for d, sp in rows:
        if not has_no_medicinal_uses_claim(d.draft_text):
            continue
        if not await is_false_no_uses_claim(s, sp, d.field_name, d.draft_text):
            true_claims += 1                         # PFAF has no uses — the claim may be true; left
            continue
        t = d.draft_text or ""
        out.append({
            "draft_id": d.id, "species_id": sp.id, "name": _name(sp), "field": d.field_name,
            "created": d.generated_at, "toxic": ai_content_excluded(sp),
            "label": ("the 45" if _old_opening_claim(t) else "the 41" if _OLD_LITERAL.search(t) else "newly caught"),
        })
    return out, true_claims


def _redraft_species(drafts) -> list:
    """One fresh medicinal_notes draft per non-toxic species (DeepSeek calls)."""
    seen, out = set(), []
    for r in drafts:
        if r["toxic"] or r["species_id"] in seen:
            continue
        seen.add(r["species_id"])
        out.append(r)
    return out


def _report(fields, drafts, true_claims) -> str:
    def ftable(rows):
        head = ("| ci | Species | List | Current value | PFAF text | Locked | Toxic | How it got here | Rule → |\n"
                "|---|---|---|---|---|---|---|---|---|\n")
        return head + "\n".join(
            f"| {r['ci_id']} | {r['name']} | {r['label']} | {_cell(r['current'])} | {r['pfaf']} | "
            f"{'yes' if r['locked'] else 'no'} | {'yes' if r['toxic'] else 'no'} | {r['provenance']} | "
            f"{_outcome(r['decision'])} |" for r in rows) + "\n"

    a = [r for r in fields if r["group"] == "A"]
    e = [r for r in fields if r["group"] == "E"]
    b = [r for r in fields if r["group"] == "B"]
    out = ["## Fields", "",
           "### A. The text is only the 'no medicinal uses' answer (disclaimer / heading first)", "", ftable(a),
           "### E. A 'no uses' sentence inside real text — only that sentence removed (full before → after)", ""]
    for r in e:
        d = r["decision"]
        out += [f"**{r['name']}** (ci {r['ci_id']}, {r['label']}, PFAF {r['pfaf']}, "
                f"{'locked' if r['locked'] else 'not locked'}{', toxic' if r['toxic'] else ''}) → {_outcome(d)}", "",
                "Before:", "", "> " + (r["current"] or "").replace("\n", "\n> "), "",
                "After:", "", "> " + ((d.new_value or "∅") if d.action == "strip" else (r["current"] or "")).replace("\n", "\n> "), ""]
    out += ["### B. Empty, PFAF text available", "", ftable(b),
            "## Drafts — pending, claiming no uses where PFAF lists them", "",
            "| Draft | Species | Field | Created | List | Toxic | → |", "|---|---|---|---|---|---|---|"]
    redraft_ids = {r["species_id"] for r in _redraft_species(drafts)}
    for r in drafts:
        to = "invalidate" + (" + re-draft" if (r["species_id"] in redraft_ids and r["field"] == FIELD) else "")
        out.append(f"| {r['draft_id']} | {r['name']} | {r['field']} | {r['created']:%Y-%m-%d} | {r['label']} | "
                   f"{'yes' if r['toxic'] else 'no'} | {to} |")
    out += ["", f"Pending drafts with the claim where PFAF has no uses (left alone): {true_claims}", ""]
    return "\n".join(out) + "\n"


def _summary(fields, drafts, true_claims) -> str:
    c = Counter(f"{r['group']} · {_outcome(r['decision'])}" for r in fields)
    lab = Counter(f"{r['group']} · {r['label']}" for r in fields)
    redraft = _redraft_species(drafts)
    lines = ["FIELDS: " + str(len(fields))] + [f"  {k}: {v}" for k, v in sorted(c.items())]
    lines += ["  lists: " + ", ".join(f"{k} {v}" for k, v in sorted(lab.items()))]
    lines += [f"DRAFTS to invalidate: {len(drafts)} ({dict(Counter(r['label'] for r in drafts))}; "
              f"fields {dict(Counter(r['field'] for r in drafts))}; "
              f"species {len({r['species_id'] for r in drafts})}, toxic species "
              f"{len({r['species_id'] for r in drafts if r['toxic']})})",
              f"RE-DRAFTS (non-toxic species, one DeepSeek call each): {len(redraft)}",
              f"Pending claim drafts where PFAF has no uses (left): {true_claims}"]
    return "\n".join(lines) + "\n"


async def _read_back(S, fields, drafts) -> list:
    """Re-query every written row by id; every column compared with the plan."""
    bad = []
    async with S() as s:
        for r in fields:
            d = r["decision"]
            if d.action == "skip":
                continue
            ci = await s.get(CulinaryInfo, r["ci_id"])
            after = {c.name: getattr(ci, c.name) for c in CulinaryInfo.__table__.columns}
            for col, before in r["ci_before"].items():
                want = before
                if col == FIELD:
                    want = d.new_value
                elif col == "ai_approved_fields_json" and before and d.action != "strip":
                    lst = json.loads(before)
                    want = json.dumps([f for f in lst if f != FIELD]) if FIELD in lst else before
                elif col == "updated_at":
                    continue
                if after[col] != want:
                    bad.append((r["ci_id"], col, want, after[col]))
            h = (await s.execute(
                select(CulinaryInfoHistory).where(CulinaryInfoHistory.culinary_info_id == r["ci_id"])
                .where(CulinaryInfoHistory.field_name == FIELD).order_by(CulinaryInfoHistory.id.desc()).limit(1)
            )).scalar_one_or_none()
            want_by = "pfaf_fallback" if d.action == "fill" else CLEAR_CHANGED_BY
            old = d.old_value if (d.old_value or "").strip() else None
            if not h or h.changed_by != want_by or h.new_value != d.new_value or h.old_value != old:
                bad.append((r["ci_id"], "history", (want_by, old, d.new_value),
                            (h.changed_by, h.old_value, h.new_value) if h else None))
        for r in drafts:
            d = await s.get(SpeciesAIDraft, r["draft_id"])
            ctx = json.loads(d.generation_context_json or "{}")
            if d.status != "invalidated" or ctx.get("invalidated_reason") != INVALIDATE_REASON:
                bad.append((r["draft_id"], "draft", "invalidated", (d.status, ctx.get("invalidated_reason"))))
    return bad


def _with_reason(ctx_json) -> str:
    try:
        ctx = json.loads(ctx_json) if ctx_json else {}
    except (ValueError, TypeError):
        ctx = {"context_raw": ctx_json}
    if not isinstance(ctx, dict):
        ctx = {"context": ctx}
    ctx["invalidated_reason"] = INVALIDATE_REASON
    ctx["invalidated_at"] = datetime.utcnow().isoformat()
    return json.dumps(ctx)


async def main_async(args) -> int:
    url = f"sqlite+aiosqlite:///file:{args.db}?mode=ro&uri=true" if not args.apply else f"sqlite+aiosqlite:///{args.db}"
    eng = create_async_engine(url)
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        fields = await _field_rows(s)
        drafts, true_claims = await _draft_rows(s)
    if args.out:
        Path(args.out).write_text(_report(fields, drafts, true_claims), encoding="utf-8")
    print(_summary(fields, drafts, true_claims))
    if not args.apply:
        print("DRY RUN — nothing written, no DeepSeek call." + (f" Report: {args.out}" if args.out else ""))
        await eng.dispose()
        return 0

    written = 0
    async with S() as s:
        for r in fields:
            if r["decision"].action == "skip":
                continue
            sp = await s.get(Species, r["species_id"])
            ci = await s.get(CulinaryInfo, r["ci_id"])
            got = (await apply_pfaf_fallback(s, sp, ci, [FIELD]))[0]
            if (got.action, got.new_value) != (r["decision"].action, r["decision"].new_value):
                print(f"PLAN CHANGED for ci {r['ci_id']}: {r['decision']} → {got}")
            written += got.action != "skip"
        for r in drafts:
            d = await s.get(SpeciesAIDraft, r["draft_id"])
            d.status = "invalidated"
            d.generation_context_json = _with_reason(d.generation_context_json)
        await s.commit()
    bad = await _read_back(S, fields, drafts)
    print(f"APPLIED: {written} fields written, {len(drafts)} drafts invalidated. Read-back by id: "
          f"{len(fields)} fields + {len(drafts)} drafts checked, {len(bad)} mismatches")
    for b in bad:
        print("  MISMATCH", b)
    redraft = _redraft_species(drafts)
    if not args.redraft:
        print(f"Re-drafts NOT run (no --redraft): {len(redraft)} DeepSeek calls would be made.")
    else:
        from app.services.enrichment import _section_ai_draft
        from app.services.settings_service import load_settings_from_db
        async with S() as s:
            await load_settings_from_db(s)
        queued = 0
        for r in redraft:
            async with S() as s:
                sp = await s.get(Species, r["species_id"])
                ok = await _section_ai_draft(s, sp, FIELD)
                await s.commit()
                queued += bool(ok)
                print(f"  re-draft {r['name']}: {'queued' if ok else 'no draft'}")
        print(f"RE-DRAFTS: {queued} of {len(redraft)} queued")
    await eng.dispose()
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true", help="write (default: dry run on a read-only DB)")
    ap.add_argument("--redraft", action="store_true", help="after --apply: queue the DeepSeek re-drafts")
    ap.add_argument("--out", help="write the dry-run report (Markdown) to this file")
    args = ap.parse_args(argv)
    if args.redraft and not args.apply:
        ap.error("--redraft needs --apply")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
