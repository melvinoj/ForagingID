"""
Walkthroughs A–H: automated browser pass (Melvin, 25 Oct 2026).

Runs the CHANGELOG walkthrough items against a SCRATCH server only — never the
live app on :8000. The scratch server is a clone of the project tree with a
snapshot DB, HOME pointed at a throwaway folder (so publish goes to a local
bare repo), ID/AI keys disabled, bound to 127.0.0.1:8765.

Sessions:
  * curator desktop (1280px) and curator phone (390px) — localhost = curator.
  * participant (390px) — joined through a real one-time /join/<token> link.
    Its requests carry X-Forwarded-For, so the server treats it as a LAN
    device, not the laptop (app/services/access.py is_local_request).

Each item: do the action, assert what can be asserted, take a screenshot.
Results: <out>/results.csv (item, result, asserted, screenshot, note) and one
<letter><nn>_<short>.png per item. Result is PASS / FAIL / NEEDS EYES /
MELVIN ONLY. This script never fixes anything.

Run:  ~/foragingid-venv/bin/python scripts/dev/walkthrough_check.py \
          --base http://localhost:8765 --out ~/Documents/ForagingID/walkthrough_run_<date>
      add --only AH to run some walkthroughs.
"""
import argparse
import csv
import json
import re
import sys
import traceback
import urllib.parse
from datetime import date
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

PASS, FAIL, EYES, MELVIN = "PASS", "FAIL", "NEEDS EYES", "MELVIN ONLY"
GUEST_XFF = {"X-Forwarded-For": "192.168.178.50"}   # a LAN phone, not the laptop

TEST_SPECIES = {
    "Conium maculatum": "Conium", "Oenanthe crocata": "Oenanthe", "Sambucus nigra": "Sambucus",
    "Hypericum perforatum": "229-hypericum", "Allium ursinum": "295-ramsons",
    "Populus tremula": "97-aspen", "Matricaria discoidea": "pineapple-weed",
}


class Check(Exception):
    """An assertion that failed: the message says what was expected and what was found."""


def need(cond, msg):
    if not cond:
        raise Check(msg)


def q(name):
    return urllib.parse.quote(name)


class Run:
    def __init__(self, base, out):
        self.base = base.rstrip("/")
        self.out = out
        self.rows = []
        self.page_errors = []
        out.mkdir(parents=True, exist_ok=True)

    # ── API helpers (curator, localhost) ────────────────────────────────────
    def api(self, method, path, **kw):
        r = requests.request(method, self.base + path, timeout=120, **kw)
        return r

    def jget(self, path):
        r = self.api("GET", path)
        need(r.ok, f"GET {path} → HTTP {r.status_code}")
        return r.json()

    # ── Browser ─────────────────────────────────────────────────────────────
    def start(self, pw):
        self.browser = pw.chromium.launch()
        self.desk = self._ctx(1280, 900)
        self.phone = self._ctx(390, 844, mobile=True)
        self.guest = None

    def _ctx(self, w, h, mobile=False, headers=None):
        ctx = self.browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile,
                                       has_touch=mobile, extra_http_headers=headers or {},
                                       service_workers="block")
        ctx.set_default_timeout(30000)
        return ctx

    def page(self, ctx):
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: self.page_errors.append(str(e)[:200]))
        return pg

    def goto(self, pg, path, wait=1200):
        # Pages that poll (Scan: syncthing status every 2 s) never reach networkidle.
        until = "load" if path.startswith(("/scan", "/encounters")) else "networkidle"
        r = pg.goto(self.base + path, wait_until=until, timeout=90000)
        pg.wait_for_timeout(wait)
        return r

    def guest_ctx(self, name="WT Guest A"):
        """A participant phone joined through a real one-time link (the Workshops flow's endpoints)."""
        if self.guest is not None:
            return self.guest
        p = self.api("POST", "/api/workshop/participants/find-or-create", json={"name": name}).json()
        s = self.api("POST", "/api/workshop/sessions", json={"name": "Walkthrough session"}).json()
        t = self.api("POST", "/api/workshop/tokens",
                     json={"participant_id": p["id"], "workshop_session_id": s["id"]}).json()
        ctx = self._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        pg = self.page(ctx)
        r = pg.goto(self.base + "/join/" + t["token"], wait_until="networkidle")
        me = pg.evaluate("fetch('/api/me').then(r => r.json())")
        need(me.get("is_participant"), f"participant join failed: {me}")
        pg.close()
        self.guest = ctx
        self.guest_info = {"participant": p, "session": s, "token": t}
        return ctx

    # ── Items ───────────────────────────────────────────────────────────────
    def item(self, iid, short, fn, *, pg=None):
        """Run one item. fn(pg) returns (result, asserted, note) or (asserted, note) for PASS."""
        shot = f"{iid}_{short}.png"
        self.page_errors.clear()
        try:
            res = fn(pg) if pg is not None else fn()
            if len(res) == 2:
                res = (PASS,) + tuple(res)
            result, asserted, note = res
        except Check as e:
            result, asserted, note = FAIL, "", str(e)
        except Exception as e:                                   # a script/page failure, not a verdict
            result, asserted, note = FAIL, "", f"script error: {type(e).__name__}: {str(e)[:300]}"
            traceback.print_exc()
        if self.page_errors:
            note = (note + " | " if note else "") + "page errors: " + "; ".join(self.page_errors[:3])
        if pg is not None and result != MELVIN:
            try:
                pg.screenshot(path=str(self.out / shot), full_page=False)
            except Exception as e:
                note += f" | screenshot failed: {e}"
                shot = ""
        else:
            shot = ""
        self.rows.append({"item": iid, "result": result, "asserted": asserted, "screenshot": shot, "note": note})
        print(f"{iid:5} {result:11} {short} — {note[:160]}", flush=True)

    def melvin(self, iid, short, why):
        self.rows.append({"item": iid, "result": MELVIN, "asserted": "", "screenshot": "", "note": why})
        print(f"{iid:5} {MELVIN:11} {short} — {why}", flush=True)

    def write(self):
        with open(self.out / "results.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["item", "result", "asserted", "screenshot", "note"])
            w.writeheader()
            w.writerows(self.rows)


# ═══════════════════════════════════════════════════════════════════════════
# A. Species page
# ═══════════════════════════════════════════════════════════════════════════
def walk_a(R):
    pg = R.page(R.desk)
    R.goto(pg, "/species", 2500)

    def a01(pg):
        counts = {}
        for v in ("large", "grid", "list"):
            pg.click(f".sp-view-btn[data-view='{v}']")
            pg.wait_for_timeout(1500)
            active = pg.eval_on_selector(".sp-view-btn.active", "b => b.dataset.view")
            need(active == v, f"view {v}: active button is {active}")
            counts[v] = pg.locator("#species-grid [data-name]").count()
        need(len(set(counts.values())) == 1 and counts["list"] > 0, f"views show different counts {counts}")
        need(pg.locator("table.sp-table").count() == 1, "List view has no table.sp-table")
        return (f"Large/Grid/List each become active; same species count in all three ({counts['list']}); "
                "List renders a table", "")
    R.item("A01", "three_views", a01, pg=pg)

    def a02(pg):
        pg.click(".sp-view-btn[data-view='list']"); pg.wait_for_timeout(800)
        seen = []
        for key, label in (("name", "Name"), ("latin", "Latin"), ("family", "Family"),
                           ("sightings", "Sightings"), ("safety", "Safety")):
            pg.evaluate(f"sortSpeciesList('{key}')"); pg.wait_for_timeout(300)
            sorted_th = pg.locator("th[aria-sort='ascending'], th[aria-sort='descending']").count()
            need(sorted_th == 1, f"sort {key}: {sorted_th} columns marked sorted")
            seen.append(key)
        # Safety ascending: deadly/toxic first.
        if pg.locator("th[aria-sort='descending'] .sp-sort-btn", has_text="Safety").count():
            pg.evaluate("sortSpeciesList('safety')"); pg.wait_for_timeout(300)
        cells = pg.eval_on_selector_all("td.col-safety", "els => els.map(e => e.textContent.trim())")
        ranks = []
        for c in cells:
            ranks.append(0 if "deadly" in c else 1 if "☠" in c else 2 if "unknown" in c else 3 if "caution" in c else 4)
        firsts = cells[:3]
        need(ranks[0] <= 1, f"safety sort: first row is {firsts}")
        # Monotonic for the badge levels we can read (edible vs not edible both rank 4 here).
        need(all(a <= b for a, b in zip(ranks, ranks[1:])), "safety sort: rows not in deadly→toxic→unknown→caution→other order")
        # Sightings numeric descending.
        pg.evaluate("sortSpeciesList('sightings')"); pg.wait_for_timeout(300)
        nums = [int(x) for x in pg.eval_on_selector_all("td.col-sightings", "els => els.map(e => e.textContent.trim())")]
        need(nums == sorted(nums, reverse=True), "sightings sort is not descending")
        pg.evaluate("sortSpeciesList('safety')"); pg.wait_for_timeout(300)
        return (f"List sorts by every column ({', '.join(seen)}); safety order deadly→toxic→unknown→caution→rest "
                f"(first rows {firsts}); sightings descending", "")
    R.item("A02", "list_sort_safety", a02, pg=pg)

    def a03(pg):
        pg.evaluate("togglePropFilter('caution')"); pg.wait_for_timeout(800)
        counts = {}
        for v in ("grid", "large", "list"):
            pg.click(f".sp-view-btn[data-view='{v}']"); pg.wait_for_timeout(1000)
            on = pg.locator(".filter-chip.active[data-value='caution']").count()
            need(on == 1, f"view {v}: Caution chip no longer active")
            counts[v] = pg.locator("#species-grid [data-name]").count()
        need(len(set(counts.values())) == 1, f"filtered counts differ across views {counts}")
        pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1500)
        after_reload = pg.locator(".filter-chip.active[data-value='caution']").count()
        view_after = pg.eval_on_selector(".sp-view-btn.active", "b => b.dataset.view")
        note = (f"after reload: view kept = {view_after}; Caution filter "
                f"{'kept' if after_reload else 'reset (filters are not persisted across reloads)'}")
        if after_reload:
            pg.evaluate("togglePropFilter('caution')")
        else:
            pass
        return (f"⚠ Caution filter stays active across Grid/Large/List with the same count ({counts['grid']})", note)
    R.item("A03", "filters_kept", a03, pg=pg)

    def a04(pg):
        pg.click(".sp-view-btn[data-view='grid']"); pg.wait_for_timeout(800)
        R.goto(pg, "/species", 2000)
        names = pg.eval_on_selector_all("#species-grid [data-name] .common, #species-grid [data-name] .sp-common, "
                                        "#species-grid [data-name] .common-name",
                                        "els => els.map(e => e.textContent.trim())")
        if not names:
            pg.click(".sp-view-btn[data-view='list']"); pg.wait_for_timeout(800)
            names = pg.eval_on_selector_all("td.col-name .common", "els => els.map(e => e.textContent.trim())")
        names = [re.sub(r"^[^\wÀ-ɏ]+", "", n) for n in names if n]
        bad = [n for n in names if n and n[0].isalpha() and not n[0].isupper()]
        need(names, "no common names found to check")
        need(not bad, f"{len(bad)} lowercase common names, e.g. {bad[:5]}")
        return (f"{len(names)} common names on the list all start with a capital", "")
    R.item("A04", "capitalised_names", a04, pg=pg)

    # Test species pages
    for i, (sci, short) in enumerate(TEST_SPECIES.items()):
        def a05(pg, sci=sci):
            prof = R.jget(f"/api/species/{q(sci)}/profile")
            s = prof["safety"]
            R.goto(pg, f"/species?s={q(sci)}", 2500)
            body = pg.inner_text("#profile-view")
            asserted = []
            if s.get("level") in ("deadly", "toxic"):
                box = pg.locator(f"#profile-view .safety-{s['level']}")
                need(box.count() >= 1, f"no .safety-{s['level']} NOT SAFE box")
                asserted.append(f"{s['level']} box ({' '.join(box.first.inner_text().split())[:30]})")
            elif s.get("label"):
                need(s["label"] in body, f"badge '{s['label']}' not on page")
                asserted.append(f"badge {s['label']}")
            flat = " ".join(body.split())
            for k, w in (s.get("warnings") or {}).items():
                if not w or not w.get("text"):
                    continue
                txt = " ".join(w["text"].split())
                need(txt in flat, f"{k} warning text not shown in full ({txt[:50]}…)")
                if not w.get("reviewed"):
                    need("Source text — not yet reviewed" in body, f"uncurated {k} warning not labelled")
                    asserted.append(f"{k} warning (labelled unreviewed)")
                else:
                    asserted.append(f"{k} warning (curator)")
            if sci == "Populus tremula":
                need(pg.locator("#recipe-card-48").count() == 1, "recipe #48 not on the Aspen page")
                asserted.append("recipe #48 present")
            blocked = not s.get("culinary_allowed")
            if blocked:
                n = pg.locator(".recipe-bank-card").count()
                need(n == 0, f"culinary blocked ({s['level']}) but {n} recipe cards shown")
                asserted.append("no recipe cards (culinary blocked)")
            return ("; ".join(asserted) or "page loads", "")
        R.item(f"A05{chr(97 + i)}", f"species_{short}", a05, pg=pg)

    def a06(pg):
        sp = "Meum athamanticum"
        resp = []
        pg.on("response", lambda r: resp.append((r.url, r.status)) if "/resources" in r.url else None)
        R.goto(pg, f"/species?s={q(sp)}", 2500)
        hits = [s for u, s in resp if f"{q(sp)}/resources" in u or f"{sp.replace(' ', '%20')}/resources" in u]
        need(hits and all(s == 200 for s in hits), f"resources request statuses {hits}")
        txt = pg.inner_text("#resources-list")
        need("Loading" not in txt, "resources list still 'Loading…'")
        need("❌" not in txt and "Error" not in txt, f"resources list shows an error: {txt[:100]}")
        pg.locator("#sec-other-resources").scroll_into_view_if_needed()
        return (f"GET …/resources 200, list rendered ({txt.strip()[:60]!r})", "")
    R.item("A06", "species_resources", a06, pg=pg)

    def a07(pg):
        out = []
        # Ramsons: caution, warnings beside culinary content, every recipe card, taste notes.
        sp = "Allium ursinum"
        prof = R.jget(f"/api/species/{q(sp)}/profile")
        R.goto(pg, f"/species?s={q(sp)}", 2500)
        cul = pg.locator("#culinary-content .culinary-warnings").count()
        need(cul == 1, f"Ramsons Culinary section: {cul} warning blocks (want 1)")
        out.append("Culinary section warnings")
        tw = pg.locator("#taste-notes-warnings .culinary-warnings").count()
        need(tw == 1, f"Ramsons Taste notes: {tw} warning blocks")
        out.append("Taste notes warnings")
        cards = pg.locator(".recipe-bank-card")
        n = cards.count()
        missing = [i for i in range(n) if cards.nth(i).locator(".culinary-warnings").count() != 1]
        need(n > 0 and not missing, f"{len(missing)} of {n} recipe cards without exactly one warning block")
        out.append(f"{n} recipe cards each carry warnings")
        unrev = [k for k, w in (prof["safety"].get("warnings") or {}).items() if w and not w.get("reviewed")]
        if unrev:
            need(pg.locator("#culinary-content .sw-unreviewed").count() >= 1, "unreviewed text not labelled")
            out.append(f"unreviewed {unrev} labelled")
        fr = pg.locator(".field-recipe-card")
        if fr.count():
            bad = [i for i in range(fr.count()) if fr.nth(i).locator(".culinary-warnings").count() != 1]
            need(not bad, f"{len(bad)} field recipe cards without warnings")
            out.append(f"{fr.count()} field recipes carry warnings")
        # A species with no warning text looks unchanged.
        sp2 = "Populus tremula"
        p2 = R.jget(f"/api/species/{q(sp2)}/profile")
        has = any(w and w.get("text") for w in (p2["safety"].get("warnings") or {}).values())
        R.goto(pg, f"/species?s={q(sp2)}", 2500)
        n2 = pg.locator(".culinary-warnings").count()
        if not has:
            need(n2 == 0, f"Aspen has no warning text but {n2} warning blocks render")
            out.append("Aspen (no warnings): no warning blocks")
        R.goto(pg, f"/species?s={q(sp)}", 2500)
        pg.locator(".recipe-bank-card").first.scroll_into_view_if_needed()
        return ("Ramsons: " + "; ".join(out), "")
    R.item("A07", "culinary_warnings", a07, pg=pg)
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# H. Recipes
# ═══════════════════════════════════════════════════════════════════════════
def walk_h(R):
    pg = R.page(R.desk)
    R.goto(pg, "/recipes", 2500)

    def h01(pg):
        R.goto(pg, "/species", 1500)
        pg.click("#site-nav-chip"); pg.wait_for_timeout(500)
        link = pg.locator("#nav-drawer-links a[href='/recipes']")
        need(link.count() == 1, "no Recipes link in the nav drawer")
        link.click(); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
        need(pg.url.rstrip("/").endswith("/recipes"), f"nav link went to {pg.url}")
        return ("nav drawer has Recipes; it opens /recipes", "")
    R.item("H01", "nav_link", h01, pg=pg)

    api = R.jget("/api/recipes")
    n_api = len(api["recipes"])

    for v in ("now", "season", "walk", "type", "species", "part", "az", "recent"):
        def h02(pg, v=v):
            pg.select_option("#rc-view", v); pg.wait_for_timeout(800)
            groups = pg.locator(".rc-group-h").count()
            tiles = pg.locator(".recipe-tile").count()
            need(groups >= 1 and tiles >= 1, f"view {v}: {groups} groups, {tiles} tiles")
            if v in ("season", "type", "az", "recent", "species"):
                need(tiles == n_api, f"view {v}: {tiles} tiles, API has {n_api}")
            if v == "walk":
                need(pg.locator("#rc-walk").is_visible(), "walk view: walk dropdown hidden")
            return (f"view {v}: {groups} groups, {tiles} tiles" + (f" (= all {n_api})" if tiles == n_api else ""), "")
        R.item(f"H02{v[:2]}", f"view_{v}", h02, pg=pg)

    def h03(pg):
        pg.select_option("#rc-view", "az")
        pg.fill("#recipe-search", "elder"); pg.wait_for_timeout(1500)
        tiles = pg.locator(".recipe-tile").count()
        sub = pg.inner_text("#rc-subtitle")
        need(tiles >= 1 and "matching" in sub, f"search 'elder': {tiles} tiles, subtitle {sub!r}")
        need(tiles < n_api, "search did not narrow the list")
        pg.fill("#recipe-search", "zzqqxx"); pg.wait_for_timeout(1500)
        empty = pg.inner_text("#rc-results")
        need("No recipes found" in empty, f"no-match search shows {empty[:80]!r}")
        pg.fill("#recipe-search", "elder"); pg.wait_for_timeout(1500)
        return (f"'elder' → {tiles} tiles (of {n_api}); nonsense → 'No recipes found'", "")
    R.item("H03", "search", h03, pg=pg)

    def h04(pg):
        pg.fill("#recipe-search", ""); pg.wait_for_timeout(1500)
        pg.select_option("#rc-view", "az"); pg.wait_for_timeout(800)
        caution = pg.locator(".recipe-tile:has(.rt-chip.caution)")
        n = caution.count()
        need(n >= 1, "no caution tiles")
        no_warn = [i for i in range(n) if caution.nth(i).locator("details .culinary-warnings").count() != 1]
        need(not no_warn, f"{len(no_warn)} of {n} caution tiles without a warnings block")
        api_caution = sum(1 for r in api["recipes"]
                          if (api["safety"].get(str(r["species"]["id"])) or {}).get("level") == "caution")
        need(n == api_caution, f"{n} ⚠ tiles, API has {api_caution} caution recipes")
        first = caution.first
        first.locator("details summary").click(); pg.wait_for_timeout(300)
        first.scroll_into_view_if_needed()
        return (f"{n} caution tiles (= API), each with ⚠ chip and a Warnings block", "")
    R.item("H04", "caution_tiles", h04, pg=pg)

    def h05(pg):
        cur = pg.locator(".rt-chip.curator").count()
        exp = sum(1 for r in api["recipes"] if r.get("needs_title")) + sum(1 for r in api["recipes"] if r.get("hide_from_public"))
        need(cur == exp, f"{cur} curator chips, expected {exp}")
        gctx = R.guest_ctx()
        gp = R.page(gctx)
        R.goto(gp, "/recipes?view=az", 2500)
        vis = gp.eval_on_selector_all(".rt-chip.curator", "els => els.filter(e => e.offsetParent !== null).length")
        need(vis == 0, f"guest sees {vis} curator chips")
        gp.close()
        return (f"curator sees {cur} curator chips (needs a title / hidden from public); participant sees none", "")
    R.item("H05", "curator_chips", h05, pg=pg)

    def h06(pg):
        R.goto(pg, "/recipes?view=az", 2000)
        tile = pg.locator(".recipe-tile").first
        rid = tile.get_attribute("data-recipe-id")
        tile.locator(".rt-title").click()
        pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2500)
        need(f"recipe={rid}" in pg.url, f"tile went to {pg.url}")
        card = pg.locator(f"#recipe-card-{rid}")
        need(card.count() == 1, f"recipe card {rid} not on the species page")
        need("recipe-linked" in (card.get_attribute("class") or ""), "card not outlined (recipe-linked)")
        need("recipe-bank-collapsed" not in (card.get_attribute("class") or ""), "card still collapsed")
        inview = card.evaluate("e => { const r = e.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; }")
        need(inview, "card not scrolled into view")
        return (f"tile → /species?…&recipe={rid}; card {rid} open, outlined, in view", "")
    R.item("H06", "tile_opens_card", h06, pg=pg)

    # Pick a recipe on a species page for the edit checks.
    target = next(r for r in api["recipes"] if r["species"]["scientific_name"] == "Sambucus nigra") \
        if any(r["species"]["scientific_name"] == "Sambucus nigra" for r in api["recipes"]) else api["recipes"][0]
    sp, rid = target["species"]["scientific_name"], target["id"]

    def h07(pg):
        R.goto(pg, f"/species?s={q(sp)}&recipe={rid}", 2500)
        card = pg.locator(f"#recipe-card-{rid}")
        card.locator(".recipe-edit-btn").click(); pg.wait_for_timeout(300)
        f = pg.locator(f"#recipe-edit-{rid}")
        new_title = "WT edited title " + str(rid)
        f.locator("input[name=title]").fill(new_title)
        f.locator("textarea[name=summary]").fill("Walkthrough summary line.")
        f.locator("select[name=recipe_type]").select_option("drink")
        f.locator("input[name=website_url]").fill("https://melvinjarman.co.uk/recipes/wt-test")
        f.locator("button[type=submit]").click(); pg.wait_for_timeout(2500)
        pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2500)
        card = pg.locator(f"#recipe-card-{rid}")
        t = card.locator(".recipe-bank-title").inner_text()
        meta = card.locator(".recipe-meta-line").inner_text()
        need(new_title in t, f"after reload title is {t!r}")
        need("Drink" in meta and "full recipe" in meta, f"after reload meta line is {meta!r}")
        api_r = next(x for x in R.jget(f"/api/species/{q(sp)}/profile")["recipes"] if x["id"] == rid)
        need(api_r.get("summary") == "Walkthrough summary line.", f"summary in API {api_r.get('summary')!r}")
        return (f"recipe {rid} ({sp}): title, summary, type, link saved and shown after reload; API agrees", "")
    R.item("H07", "edit_details_saves", h07, pg=pg)

    def h08(pg):
        card = pg.locator(f"#recipe-card-{rid}")
        card.locator(".recipe-edit-btn").click(); pg.wait_for_timeout(300)
        f = pg.locator(f"#recipe-edit-{rid}")
        f.locator("input[name=website_url]").fill("https://evil.example.com/x")
        f.locator("button[type=submit]").click(); pg.wait_for_timeout(2000)
        msg = pg.inner_text(f"#recipe-edit-msg-{rid}")
        need("❌" in msg, f"bad link not refused; message {msg!r}")
        api_r = next(x for x in R.jget(f"/api/species/{q(sp)}/profile")["recipes"] if x["id"] == rid)
        need("evil" not in (api_r.get("website_url") or ""), "bad link was stored")
        r = R.api("PATCH", f"/api/species/{q(sp)}/recipes/{rid}", json={"website_url": "javascript:alert(1)"})
        need(r.status_code >= 400, f"javascript: link → HTTP {r.status_code}")
        return (f"non-melvinjarman.co.uk link refused in the form ({msg.strip()[:70]!r}); javascript: link → {r.status_code}; "
                "nothing stored", "")
    R.item("H08", "bad_link_refused", h08, pg=pg)

    def h09():
        gp = R.page(R.guest_ctx())
        R.goto(gp, f"/species?s={q(sp)}&recipe={rid}", 3000)
        vis = gp.eval_on_selector_all(".recipe-edit-btn, .recipe-meta-line, .recipe-edit-form",
                                      "els => els.filter(e => e.offsetParent !== null).length")
        r = gp.evaluate(f"""fetch('/api/species/{q(sp)}/recipes/{rid}', {{method:'PATCH',
                            headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{title:'guest'}})}}).then(r => r.status)""")
        gp.screenshot(path=str(R.out / "H09_guest_no_edit.png"))
        gp.close()
        need(vis == 0, f"guest sees {vis} edit controls")
        need(r in (401, 403), f"guest PATCH → HTTP {r}")
        return (PASS, f"participant: no ✎ Edit details / meta line visible; PATCH → {r}", "screenshot is the participant's view")
    R.item("H09", "guest_no_edit", h09)
    R.rows[-1]["screenshot"] = "H09_guest_no_edit.png"

    def h10(pg):
        walks = R.jget("/api/walk/saves")
        walks = walks.get("walks", walks) if isinstance(walks, dict) else walks
        need(walks, "no saved walks")
        return find_make(R, pg, walks)
    R.item("H10", "find_make_opens_recipes", h10, pg=pg)

    def h11(pg):
        return publish_plan_recipes(R, pg)
    R.item("H11", "publish_plan_recipes_tab", h11, pg=pg)

    R.item("H13", "publish_unpublish_test_walk", lambda pg: publish_unpublish_test_walk(R, pg), pg=pg)
    R.item("H14", "publish_no_network", lambda pg: publish_no_network(R, pg), pg=pg)

    def h12(pg):
        return republish_recipes(R, pg)
    R.item("H12", "republish_recipes_tab", h12, pg=pg)
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# B. Map + walks
# ═══════════════════════════════════════════════════════════════════════════
_DIALOGS = {}


def _dialogs(pg):
    """Accept every confirm/alert on this page; return the list their messages go to (one handler per page)."""
    seen = getattr(pg, "_wt_dialogs", None)
    if seen is None:
        seen = []

        def on(d):
            seen.append(d.message)
            try:
                d.accept()
            except Exception:
                pass
        pg.on("dialog", on)
        pg._wt_dialogs = seen
    return seen


def _wait_dialog(pg, seen, start, text, timeout=60000):
    for _ in range(timeout // 500):
        hit = [m for m in seen[start:] if text in m]
        if hit:
            return hit[-1]
        pg.wait_for_timeout(500)
    raise Check(f"no dialog containing {text!r} (got {[m[:60] for m in seen[start:]]})")


WALK_LOAD_FAILURES = []   # (walk id, attempt, dialog text) — the leaflet.heat '_animating' failure


def _open_saved_walk(R, pg, walk_id, wait=6000, start="/", tries=3):
    """Open a saved walk the way the map does: Tools → Open a saved walk → the walk's row.
    A 'Failed to load walk' alert is recorded (WALK_LOAD_FAILURES) and the load retried
    from a fresh page, so the checks after it can still run."""
    seen = _dialogs(pg)
    how = ""
    first = R.jget(f"/api/walk/saves/{walk_id}")["waypoints"][0]
    for attempt in range(1, tries + 1):
        R.goto(pg, start, 2500)
        k = len(seen)
        prezoom = attempt == tries and attempt > 1
        if prezoom:
            # Last try: start the map at the walk so fitBounds has only a small zoom
            # change (it then animates and zoomend fires after the load finishes).
            lat = first.get("lat", first.get("latitude")); lng = first.get("lng", first.get("longitude"))
            pg.evaluate(f"map.setView([{lat}, {lng}], 15, {{animate: false}})"); pg.wait_for_timeout(1500)
        pg.click("#config-sheet-chip"); pg.wait_for_timeout(400)
        pg.click("#btn-open-saved-walk"); pg.wait_for_timeout(1500)
        row = pg.locator(f".saved-walk-info[onclick='loadSavedWalk({walk_id})']")
        if row.count() and row.first.is_visible():
            row.first.click()
            how = "clicked its row"
        else:
            pg.evaluate(f"loadSavedWalk({walk_id})")
            how = "row not visible — called loadSavedWalk()"
        pg.wait_for_timeout(wait)
        failed = [m for m in seen[k:] if "Failed to load walk" in m]
        if failed:
            WALK_LOAD_FAILURES.append((walk_id, attempt, failed[0]))
            continue
        need(pg.locator("#walk-stops-scroll .walk-stop-card").count() > 0, f"walk {walk_id}: no stop cards")
        if attempt > 1:
            how += (f"; loaded on attempt {attempt}" + (" only after pre-zooming the map to the walk" if prezoom else "")
                    + " (earlier: 'Failed to load walk' — see WALK LOAD)")
        return how
    raise Check(f"walk {walk_id}: 'Failed to load walk: {failed[0].split(': ', 1)[-1]}' on all {tries} attempts")


def _detail_for(R, pg, obs_id):
    R.goto(pg, f"/?highlight={obs_id}", 5000)
    need(pg.locator("#detail-view").is_visible(), f"obs {obs_id}: detail view not shown")
    return pg.inner_text("#detail-view")


def walk_b(R):
    pg = R.page(R.desk)
    pins = {"Conium maculatum": 8212, "Allium ursinum": 11477, "Amanita muscaria": 8363,
            "Heracleum mantegazzianum": 21723, "Hedera helix": 22150}

    def b01(pg):
        prof = R.jget(f"/api/species/{q('Conium maculatum')}/profile")
        la = prof["safety"]["warnings"]["look_alike"]["text"]
        body = " ".join(_detail_for(R, pg, pins["Conium maculatum"]).split())
        need(" ".join(la.split()) in body, "look-alike text not shown in full in the pin's panel")
        need("☠ deadly" in body, "no ☠ deadly label")
        return (f"pin 8212 panel: ☠ deadly + full look-alike text ({len(la)} chars)", "")
    R.item("B01", "conium_pin_lookalike", b01, pg=pg)

    def b02(pg):
        prof = R.jget(f"/api/species/{q('Allium ursinum')}/profile")
        w = prof["safety"]["warnings"]
        body = _detail_for(R, pg, pins["Allium ursinum"])
        need("⚠ caution" in body, "no ⚠ caution label")
        out = ["⚠ caution"]
        for k, x in w.items():
            if x and x.get("text"):
                if not x.get("reviewed"):
                    need("Source text — not yet reviewed" in body, f"uncurated {k} not labelled")
                    out.append(f"{k} labelled 'Source text — not yet reviewed'")
                else:
                    out.append(f"{k} curator")
        return ("Ramsons pin 11477: " + "; ".join(out), "")
    R.item("B02", "ramsons_labelled", b02, pg=pg)

    def b03(pg):
        got = []
        for sid, sci in ((155, "Amanita muscaria"), (688, "Heracleum mantegazzianum"), (745, "Hedera helix")):
            body = _detail_for(R, pg, pins[sci])
            need("☠" in body, f"{sid} {sci}: no ☠ in the pin panel")
            got.append(f"{sid} ☠")
        return ("pin panels: " + ", ".join(got), "screenshot is 745 Hedera helix")
    R.item("B03", "skull_155_688_745", b03, pg=pg)

    def b11(pg):
        body = _detail_for(R, pg, pins["Allium ursinum"])
        boxes = pg.eval_on_selector_all("#detail-view .safety-warn-text", "els => els.map(e => e.textContent.trim().slice(0, 30))")
        titles = [b.split("\n")[0] for b in boxes]
        la = sum(1 for t in titles if "Look-alike" in t)
        pr = sum(1 for t in titles if "Preparation" in t)
        need(la <= 1 and pr <= 1, f"warnings repeated in the pop-up: {titles}")
        need(la + pr >= 1, "no warnings in the Ramsons pop-up")
        return (f"Ramsons pop-up: look-alike ×{la}, preparation ×{pr}", "")
    R.item("B11", "popup_warnings_once", b11, pg=pg)

    def b04(pg):
        how = _open_saved_walk(R, pg, 4)
        cards = pg.locator("#walk-stops-scroll .walk-stop-card")
        n = cards.count()
        also = pg.locator("#walk-stops-scroll .walk-stop-also").count()
        need(also >= 1, "no 'Also here' lines on walk 4")
        out = [f"{n} stop cards", f"{also} 'Also here' lines"]
        sp = pg.locator("#walk-stops-scroll .walk-stop-sp", has_text="Agaricus campestris")
        if sp.count():
            need(sp.first.locator(".safety-warn-text", has_text="Look-alike").count() >= 1, "817 Agaricus campestris: no look-alike warning on its stop")
            out.append("817 look-alike on its stop")
        else:
            out.append("817 Agaricus campestris not on walk 4 (not checked)")
        sb = pg.locator("#walk-stops-scroll .walk-stop-sp", has_text="Sambucus nigra")
        if sb.count():
            open_prep = sb.first.locator("div.safety-warn-text", has_text="Preparation").count()
            need(open_prep >= 1, "Sambucus: preparation warning not shown open")
            out.append("Sambucus preparation warning open")
        sb.first.scroll_into_view_if_needed() if sb.count() else None
        return ("walk 4: " + "; ".join(out), f"opened by: {how}")
    R.item("B04", "walk4_stop_cards", b04, pg=pg)

    def b10(pg):
        w = R.jget("/api/walk/saves/5")
        how = _open_saved_walk(R, pg, 5)
        sub = pg.inner_text("#walk-sub") + " " + pg.inner_text("#walk-title")
        need("7.6" in sub or "7,6" in sub or "7609" in sub, f"walk panel does not show 7.6 km: {sub!r}")
        need(round(w["distance_m"]) == 7609 and w["duration_min"] == 93, f"API: {w['distance_m']} m / {w['duration_min']} min")
        straight = w["route_geojson"]["foragingid"].get("straight_ranges", [])
        members = len(w["membership"]["member_obs_ids"])
        return (EYES, f"walk 5 panel: {sub.strip()[:80]!r}; API 7609 m / 93 min; {len(straight)} straight (dashed) ranges stored",
                f"members now {members} (CHANGELOG 22 Oct said 108 — check whether later decisions changed it); "
                f"dashed legs and stop order need eyes on the map")
    R.item("B10", "walk5_tidied", b10, pg=pg)

    def b05(pg):
        seen = _dialogs(pg)
        how = _open_saved_walk(R, pg, 3)
        before = R.jget("/api/walk/saves/3")
        pg.click("#walk-edit-btn"); pg.wait_for_timeout(1500)
        # The tap a pin makes (handlePinClick → _walkPinToggle); a throw inside the redraw is recorded.
        res = pg.evaluate("""() => { const m = _walkMemberSet();
            const f = allFeatures.find(f => f.properties.id != null && !m.has(Number(f.properties.id)) && f.properties.species_primary);
            if (!f) return [null, null]; let err = null;
            try { _walkPinToggle(f.properties); } catch (e) { err = String(e); }
            return [f.properties.id, err]; }""")
        pid, tap_err = res
        need(pid, "no non-member pin in view to add")
        btn = pg.inner_text("#walk-save-btn")
        need("(1)" in btn, f"save button after marking one pin: {btn!r}")
        k = len(seen)
        pg.click("#walk-save-btn")
        msg = _wait_dialog(pg, seen, k, "Re-routed", 120000)
        status = pg.inner_text("#walk-save-status")
        after = R.jget("/api/walk/saves/3")
        need(pid in after["membership"]["member_obs_ids"], f"obs {pid} not a member after Save changes")
        need("1 added" in status, f"save status {status!r}")
        return (f"walk 3: ✎ Edit walk, marked obs {pid} → '{btn.strip()}' → saved ({status.strip()[:60]}); Re-route dialog "
                f"accepted → {msg.splitlines()[0][:90]}",
                f"the pin tap threw inside the map redraw: {tap_err}" if tap_err else "")
    R.item("B05", "edit_save_reroute", b05, pg=pg)

    def b06(pg):
        seen = _dialogs(pg)
        _open_saved_walk(R, pg, 3)
        k = len(seen)
        pg.click("#walk-tidy-btn")
        plan = _wait_dialog(pg, seen, k, "Tidy the stop order")
        done = _wait_dialog(pg, seen, k, "Tidied:", 120000)
        m = re.search(r"Crossing legs (\d+) → (\d+)", done)
        need(m and int(m.group(2)) <= int(m.group(1)), f"crossings did not go down: {done[:120]}")
        return (f"walk 3: dry run shown ({plan.splitlines()[2][:60]}); applied → {done.splitlines()[0][:100]}", "")
    R.item("B06", "tidy_route_order", b06, pg=pg)

    def b07(pg):
        _open_saved_walk(R, pg, 4)
        with R.desk.expect_page(timeout=60000) as newp:
            pg.click("#walk-export-btn")
        ex = newp.value
        ex.wait_for_load_state(); ex.wait_for_timeout(1000)
        blocks = ex.locator(".walk-sp")
        n = blocks.count()
        need(n > 0, "export has no species blocks")
        rep, inrec = [], []
        for i in range(n):
            t = blocks.nth(i).inner_text()
            if t.count("⚠ Look-alikes:") > 1 or t.count("⚠ Caution:") + t.count("⚠ Preparation:") > 1:
                rep.append(t.split("\n")[0])
            rec = blocks.nth(i).locator(".recipe-md")
            if rec.count() and "⚠" in rec.first.inner_text():
                inrec.append(t.split("\n")[0])
        need(not rep, f"warnings repeated in species blocks: {rep[:5]}")
        need(not inrec, f"warnings inside the recipe box: {inrec[:5]}")
        warned = ex.locator(".walk-sp:has-text('⚠ Look-alikes:')").count()
        ex.screenshot(path=str(R.out / "B07_export_summary_page.png"), full_page=False)
        ex.close()
        return (f"Export summary (walk 4): {n} species blocks, {warned} with look-alikes, each warning once, none inside a recipe box",
                "second screenshot: B07_export_summary_page.png")
    R.item("B07", "export_summary", b07, pg=pg)

    def b08():
        site = Path(R.site_dir) / "w" / "rummelsbuhl-foray" / "index.html"
        need(site.exists(), f"{site} missing")
        pg2 = R.page(R.desk)
        pg2.goto(site.as_uri(), wait_until="load"); pg2.wait_for_timeout(2000)
        data = pg2.evaluate("window.DATA")
        sp = {x["id"]: x for x in data["species"]}
        need(any(x["sci"] == "Stellaria graminea" for x in data["species"]), "Stellaria graminea not on the page")
        cau = [(r["dish"], sp[r["species_id"]]["sci"]) for r in data["recipes"]
               if (sp.get(r["species_id"], {}).get("badge") or {}).get("kind") == "caution"]
        allowed = []
        for dish, sci in cau:
            s = R.jget(f"/api/species/{q(sci)}/profile")["safety"]
            allowed.append((dish, sci, s.get("handout_culinary_allowed")))
        bad = [a for a in allowed if not a[2]]
        need(not bad, f"caution recipes on the page without a curator warning: {bad}")
        pg2.screenshot(path=str(R.out / "B08_published_rummelsbuhl.png"))
        pg2.close()
        note = ("caution recipes on the page, allowed by the 22 Oct handout rule (curator warning): "
                + ", ".join(f"{d} ({s})" for d, s, _ in allowed)) if allowed else "no caution recipes on the page"
        return (f"published walk 4 page (site clone): {len(data['species'])} species incl. Stellaria graminea; "
                f"{len(data['recipes'])} recipes", note)
    R.item("B08", "published_rummelsbuhl", b08)
    R.rows[-1]["screenshot"] = "B08_published_rummelsbuhl.png"

    def b09a(pg):
        R.goto(pg, "/", 2500)
        pg.click("#search-chip-btn"); pg.wait_for_timeout(800)
        pg.click("#find-mode-season"); pg.wait_for_timeout(3000)
        cards = pg.locator("#discover-results .find-card").count()
        hdr = pg.inner_text("#discover-results .find-section-hdr")
        need(cards > 0, "Find → In season: no cards")
        pg.locator("#discover-results .find-card").first.click(); pg.wait_for_timeout(2500)
        return (f"Find → In season: {cards} cards ({hdr.strip()}); a card opens its species", "")
    R.item("B09a", "find_cards", b09a, pg=pg)

    def b09b(pg):
        _detail_for(R, pg, pins["Allium ursinum"])
        pg.locator("#detail-view button", has_text="✎ rename").first.click(); pg.wait_for_timeout(500)
        form = pg.locator(f"#rename-form-{pins['Allium ursinum']}")
        need(form.is_visible(), "rename form did not open")
        val = pg.input_value(f"#rename-sci-{pins['Allium ursinum']}")
        need(val == "Allium ursinum", f"rename form prefilled with {val!r}")
        return ("✎ rename opens the form prefilled with the current name (not saved)", "")
    R.item("B09b", "rename_form", b09b, pg=pg)

    R.melvin("B09c", "enrich_button", "Every map pin is already enriched (no ⚡ Enrich button to show) and AI keys are "
             "disabled on the scratch server; check ⚡ Enrich on a new species in the app")

    def b09d(pg):
        R.goto(pg, "/", 2500)
        pg.click("#config-sheet-chip"); pg.wait_for_timeout(400)
        pg.click("#btn-layer-note"); pg.wait_for_timeout(800)
        pg.click("#note-placing-confirm"); pg.wait_for_timeout(800)
        pg.fill("#note-text-input", "Walkthrough note with tags")
        pg.fill("#note-species-input", "Allium urs"); pg.wait_for_timeout(500)
        pg.locator("#note-species-dd .nsp-item").first.click()
        pg.fill("#note-species-input", "Sambucus nig"); pg.wait_for_timeout(500)
        pg.locator("#note-species-dd .nsp-item").first.click()
        tags = pg.eval_on_selector_all("#note-tags-row .np-tag", "els => els.map(e => e.textContent)")
        need(len(tags) == 2, f"tags row {tags}")
        pg.click(".np-btn-save"); pg.wait_for_timeout(2500)
        notes = R.jget("/api/notes/geojson")["features"]
        mine = [f["properties"] for f in notes if f["properties"].get("text") == "Walkthrough note with tags"]
        need(mine and sorted(mine[-1]["species_tags"]) == ["Allium ursinum", "Sambucus nigra"], f"saved note {mine[-1:] }")
        return ("Drop a note: placed, tagged Allium ursinum + Sambucus nigra, saved; API returns the note with both tags", "")
    R.item("B09d", "note_tags", b09d, pg=pg)

    def b12(pg):
        R.goto(pg, "/", 2500)
        pg.click("#search-chip-btn"); pg.wait_for_timeout(800)
        pg.click("#find-mode-recipes"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2500)
        need(pg.url.rstrip("/").endswith("/recipes"), f"Make? went to {pg.url}")
        pg.select_option("#rc-view", "az"); pg.wait_for_timeout(600)
        tiles = pg.locator(".recipe-tile:has(.rt-chip.caution)")
        n = tiles.count()
        both = 0
        for i in range(n):
            t = tiles.nth(i).locator(".culinary-warnings").inner_text()
            both += ("Look-alike" in t and "Preparation" in t)
        need(n and all(tiles.nth(i).locator(".culinary-warnings").count() == 1 for i in range(n)),
             "a caution tile has no warnings")
        return (f"Find → 🍳 Make? opens /recipes; {n} caution tiles all carry warnings ({both} carry both look-alike and preparation)",
                "a tile carries the warning texts its species has; not every species has both")
    R.item("B12", "find_make_warnings", b12, pg=pg)

    def b13():
        gp = R.page(R.guest_ctx())
        _open_saved_walk(R, gp, 4, start="/map")
        btns = gp.locator("#walk-stops-scroll .walk-guest-note button", has_text="Add a note")
        n = btns.count()
        need(n > 0, "participant sees no '📝 Add a note' on walk stops")
        holder = gp.locator("#walk-stops-scroll .walk-guest-note").first
        sid = holder.get_attribute("data-guest-note-sid")
        btns.first.click(); gp.wait_for_timeout(800)
        holder.locator("textarea.guest-note-text").fill("WT participant walk-stop note")
        holder.locator(".guest-note-save").click(); gp.wait_for_timeout(2000)
        st = holder.inner_text()
        gp.screenshot(path=str(R.out / "B13_participant_walk_note.png"))
        gp.close()
        need("WT participant walk-stop note" in st or "Saved" in st or "saved" in st, f"after save the box shows {st[:120]!r}")
        return (f"participant phone: {n} '📝 Add a note' buttons on walk 4; note saved on species {sid}", "")
    R.item("B13", "participant_walk_note", b13)
    R.rows[-1]["screenshot"] = "B13_participant_walk_note.png"
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# C. Handouts
# ═══════════════════════════════════════════════════════════════════════════
C_SPECIES = ["Conium maculatum", "Hypericum perforatum", "Allium ursinum", "Macrolepiota procera",
             "Sambucus nigra", "Oenanthe crocata"]


def _flat(s):
    """Letters and digits only — compares text across PDF line wraps and hyphenation."""
    return re.sub(r"[^0-9a-zà-ÿ]", "", (s or "").lower())


def _set_list(pg, R, mode, toggles, names=C_SPECIES):
    """The Foraging List as select mode / Lists would leave it (localStorage), then Lists → layout."""
    R.goto(pg, "/lists", 1200)
    pg.evaluate("""([names, mode, ct]) => {
        localStorage.setItem('foragingid_current_list', JSON.stringify({species: names, photos: {}, modes: [mode], showPhotos: true}));
        const cur = JSON.parse(localStorage.getItem('foragingid_content_toggles') || '{}');
        localStorage.setItem('foragingid_content_toggles', JSON.stringify(Object.assign(cur, ct)));
        localStorage.setItem('foragingid_list_style', 'botanical');
    }""", [names, mode, toggles])
    R.goto(pg, "/lists", 2500)
    pg.click(f"#mode-toggle button[data-mode='{mode}']"); pg.wait_for_timeout(800)


def _open_print(R, pg):
    pg.click("#print-tab-btn")
    pg.wait_for_url("**/lists/print", timeout=30000)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_function("() => window._pdfData && document.getElementById('content').style.display !== 'none'", timeout=90000)
    pg.wait_for_timeout(1000)


def _handout(R, sci):
    return R.jget(f"/api/species/{q(sci)}/profile")["safety"]


def _pfaf_medicinal(R, names=C_SPECIES):
    """{species: medicinal_notes} for list species whose medicinal_notes is PFAF fallback (never printed)."""
    out = {}
    for sci in names:
        prof = R.jget(f"/api/species/{q(sci)}/profile")
        if "medicinal_notes" in (prof.get("pfaf_fallback_fields") or []):
            out[sci] = (prof.get("culinary") or {}).get("medicinal_notes") or ""
    return out


def walk_c(R):
    pg = R.page(R.desk)

    def c01(pg):
        _set_list(pg, R, "field", {"id_notes": False, "culinary": True, "recipes": True, "season": True})
        _open_print(R, pg)
        entries = {pg.locator(".fg-entry").nth(i).locator(".fg-sci").inner_text(): pg.locator(".fg-entry").nth(i)
                   for i in range(pg.locator(".fg-entry").count())}
        need(set(C_SPECIES) <= set(entries), f"entries {sorted(entries)}")
        out = []
        con = _handout(R, "Conium maculatum")["handout_warnings"]
        txt = " ".join(entries["Conium maculatum"].inner_text().split())
        need(" ".join(con["look_alike"].split()) in txt, "Conium look-alike text cut or missing")
        need(txt.count(" ".join(con["look_alike"].split())[:60]) == 1, "Conium look-alike printed more than once")
        out.append("Conium look-alike uncut, once")
        hyp = entries["Hypericum perforatum"]
        need("caution — warning not yet reviewed" in hyp.inner_text(), "229 withheld label missing")
        need(hyp.locator(".fg-note, .fg-recipe").count() == 0, "229 prints culinary content")
        out.append("229 '⚠ caution — warning not yet reviewed', no culinary")
        content = _flat(pg.inner_text("#content"))
        leaked = [sci for sci, t in _pfaf_medicinal(R).items() if _flat(t)[:80] in content]
        need(not leaked, f"PFAF fallback medicinal/folklore text printed for {leaked}")
        out.append("no PFAF Folklore text")
        need(pg.locator(".fg-id-primary").count() == 0, "ID notes printed with ID notes off")
        out.append("ID notes off → none printed")
        dup = []
        for sci, e in entries.items():
            t = e.inner_text()
            if t.count("⚠ Look-alikes:") > 1 or t.count("⚠ Caution:") + t.count("⚠ Preparation:") > 1:
                dup.append(sci)
        need(not dup, f"warnings repeated in entries {dup}")
        out.append("warnings once per entry")
        entries["Conium maculatum"].scroll_into_view_if_needed()
        return ("field guide print: " + "; ".join(out), "")
    R.item("C01", "field_guide_print", c01, pg=pg)

    def c04(pg):
        e = lambda sci: pg.locator(".fg-entry", has=pg.locator(".fg-sci", has_text=sci))
        out = []
        for sci in ("Allium ursinum", "Macrolepiota procera"):
            s = _handout(R, sci)
            if s.get("handout_culinary_allowed"):
                need(e(sci).locator(".fg-note, .fg-recipe").count() >= 1, f"{sci}: culinary content not printed")
                out.append(f"{sci} prints culinary content")
            else:
                out.append(f"{sci} handout_culinary_allowed=False (not printed) — check")
        need(e("Hypericum perforatum").locator(".fg-note, .fg-recipe").count() == 0, "229 printed culinary content")
        out.append("229 still withheld")
        e("Allium ursinum").scroll_into_view_if_needed()
        res = PASS if all("prints" in x or "withheld" in x for x in out) else FAIL
        return (res, "; ".join(out), "")
    R.item("C04", "ramsons_macrolepiota_229", c04, pg=pg)

    def c02(pg):
        _set_list(pg, R, "workshops", {"recipes": True, "foraging": True, "culinary": True, "id_notes": False})
        _open_print(R, pg)
        page = pg.locator(".ws-page", has=pg.locator(".ws-sci", has_text="Allium ursinum"))
        need(page.count() == 1, "no Ramsons workshop page")
        order = page.evaluate("""p => [...p.querySelectorAll('.culinary-warnings, .ws-recipe, .ws-forage, .ws-section-h')]
                                   .map(e => e.classList.contains('ws-section-h') ? 'H:' + e.textContent.trim() : e.className.split(' ')[0])""")
        # Every Recipe / Foraging section is preceded by a warnings block.
        bad = []
        for i, x in enumerate(order):
            if x in ("H:Recipe", "H:Foraging notes"):
                prev = order[i - 1] if i else ""
                nxt = order[i + 1] if i + 1 < len(order) else ""
                if not ("culinary-warnings" in (prev, nxt)):
                    bad.append(x)
        need("H:Recipe" in order, f"no Recipe section on the Ramsons page ({order})")
        need(not bad, f"sections without warnings beside them: {bad} (order {order})")
        page.scroll_into_view_if_needed()
        return (f"workshop print, Ramsons: warnings sit with Recipe and Foraging ({' → '.join(order)})", "")
    R.item("C02", "workshop_print", c02, pg=pg)

    for layout, mode in (("field_guide", "field"), ("recipe_booklet", "workshop"), ("workshop", "workshops")):
        def c03(pg, layout=layout, mode=mode):
            _set_list(pg, R, mode, {"recipes": True, "foraging": True, "culinary": True, "id_notes": False})
            _open_print(R, pg)
            with pg.expect_download(timeout=180000) as dl:
                pg.click("#pdf-btn")
            path = R.out / f"C03_{layout}.pdf"
            dl.value.save_as(str(path))
            import subprocess
            from pypdf import PdfReader
            text = subprocess.run(["pdftotext", "-raw", str(path), "-"], capture_output=True, text=True).stdout
            subprocess.run(["pdftoppm", "-png", "-r", "60", "-f", "2", "-l", "2", str(path),
                            str(R.out / f"C03{layout[:2]}_pdf_page2")], capture_output=True)
            reader = PdfReader(str(path))
            pages = len(reader.pages)
            imgs = [len(p.images) for p in reader.pages]
            f = _flat(text)
            out = [f"{pages} pages"]
            con = _handout(R, "Conium maculatum")["handout_warnings"]["look_alike"]
            need(_flat(con) in f, "Conium look-alike not uncut in the PDF")
            out.append("Conium look-alike uncut")
            pfaf = _pfaf_medicinal(R)
            leaked = [sci for sci, t in pfaf.items() if _flat(t)[:80] in f]
            need(not leaked, f"PFAF fallback medicinal/folklore text printed for {leaked}")
            out.append(f"no PFAF Folklore text ({', '.join(pfaf) or 'none on the list'} withheld)")
            need("warningnotyetreviewed" in f, "229 withheld label missing in the PDF")
            out.append("229 withheld label")
            n_con = f.count(_flat(con)[:80])
            need(n_con == 1, f"Conium look-alike printed {n_con}× in the PDF")
            out.append("warnings once (Conium)")
            corners_ok = sum(1 for n in imgs if n >= 4)
            out.append(f"pages with ≥4 images (corners): {corners_ok}/{pages}")
            png = next(iter(sorted(R.out.glob(f"C03{layout[:2]}_pdf_page2*.png"))), None)
            return (EYES, f"PDF {layout}: " + "; ".join(out),
                    f"corner ornaments need eyes: {png.name if png else 'no page render'}; PDF saved as {path.name}")
        R.item(f"C03{layout[:2]}", f"pdf_{layout}", c03, pg=pg)

    def c05():
        gctx = R.guest_ctx()
        gp = R.page(gctx)
        # The participant's own note (species page note box), then their print.
        R.goto(gp, f"/species?s={q('Allium ursinum')}", 3000)
        box = gp.locator(".guest-note-text")
        if not box.count():
            btn = gp.locator("button", has_text="Add a note")
            need(btn.count(), "participant has no note box on the Ramsons page")
            btn.first.click(); gp.wait_for_timeout(500)
        gp.locator(".guest-note-text").first.fill("WT Ramsons note from participant A")
        gp.locator(".guest-note-save").first.click(); gp.wait_for_timeout(2000)
        # A second participant's note must not reach A's print.
        p2 = R.api("POST", "/api/workshop/participants/find-or-create", json={"name": "WT Guest B"}).json()
        t2 = R.api("POST", "/api/workshop/tokens", json={"participant_id": p2["id"],
                                                         "workshop_session_id": R.guest_info["session"]["id"]}).json()
        bctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        bp = R.page(bctx)
        bp.goto(R.base + "/join/" + t2["token"], wait_until="networkidle")
        R.goto(bp, f"/species?s={q('Allium ursinum')}", 3000)
        if not bp.locator(".guest-note-text").count():
            bp.locator("button", has_text="Add a note").first.click(); bp.wait_for_timeout(500)
        bp.locator(".guest-note-text").first.fill("WT Ramsons note from participant B")
        bp.locator(".guest-note-save").first.click(); bp.wait_for_timeout(2000)
        bctx.close()
        _set_list(gp, R, "field", {"recipes": True})
        _open_print(R, gp)
        notes = gp.eval_on_selector_all(".guest-print-notes", "els => els.map(e => e.closest('.fg-entry, .ws-page').querySelector('.fg-sci, .ws-sci').textContent + ': ' + e.innerText)")
        gp.locator(".guest-print-notes").first.scroll_into_view_if_needed() if notes else None
        gp.screenshot(path=str(R.out / "C05_participant_print.png"))
        # Participant PDF (allowed for guests since batch 8).
        with gp.expect_download(timeout=180000) as dl:
            gp.click("#pdf-btn")
        ppath = R.out / "C05_participant.pdf"
        dl.value.save_as(str(ppath))
        import subprocess
        ptext = _flat(subprocess.run(["pdftotext", str(ppath), "-"], capture_output=True, text=True).stdout)
        gp.close()
        joined = " | ".join(notes)
        need(any("Allium ursinum" in n and "participant A" in n for n in notes), f"A's note not under Ramsons: {notes}")
        need("participant B" not in joined, "B's note on A's print")
        need(_flat("WT Ramsons note from participant A") in ptext, "A's note not in A's PDF")
        need(_flat("participant B") not in ptext, "B's note in A's PDF")
        # Curator's print shows none.
        cp = R.page(R.desk)
        _set_list(cp, R, "field", {"recipes": True})
        _open_print(R, cp)
        cn = cp.locator(".guest-print-notes").count()
        cp.close()
        need(cn == 0, f"curator print shows {cn} participant-note blocks")
        return ("participant A's print + PDF: own Ramsons note under Allium ursinum, B's note absent; curator print: none", "")
    R.item("C05", "participant_own_notes", c05)
    R.rows[-1]["screenshot"] = "C05_participant_print.png"
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# D. Review
# ═══════════════════════════════════════════════════════════════════════════
def _dismissing_page(R, ctx=None):
    """A page that CANCELS every confirm (dry runs stop there) and accepts alerts; messages recorded."""
    pg = R.page(ctx or R.desk)
    seen = []

    def on(d):
        seen.append((d.type, d.message))
        try:
            d.dismiss() if d.type == "confirm" else d.accept()
        except Exception:
            pass
    pg.on("dialog", on)
    return pg, seen


def _scope_then_cancel(R, pg, seen, click, walk_id=5):
    """Click a bulk button → scope dialog: Continue disabled until a scope is chosen →
    pick the walk → Continue → dry-run confirm (cancelled). Returns (confirm text, walk options)."""
    k = len(seen)
    click()
    pg.wait_for_selector(".lm-scope-box", timeout=30000)
    ok = pg.locator(".lm-scope-box .lm-scope-ok")
    need(ok.is_disabled(), "Continue enabled before a scope is chosen")
    opts = pg.eval_on_selector_all(".lm-scope-box .lm-scope-walk option", "els => els.map(e => e.textContent.trim())")
    pg.check(".lm-scope-box input[value=walk]")
    pg.select_option(".lm-scope-box .lm-scope-walk", str(walk_id))
    need(ok.is_enabled(), "Continue still disabled after choosing a scope")
    ok.click()
    for _ in range(120):
        conf = [m for t, m in seen[k:] if t == "confirm"]
        alerts = [m for t, m in seen[k:] if t == "alert"]
        if conf or alerts:
            break
        pg.wait_for_timeout(500)
    need(conf, f"no dry-run confirm (alerts: {alerts})")
    return conf[0], opts


def _active_jobs(R):
    return R.jget("/api/processes/active")


def _all_obs(R, status):
    out, off = [], 0
    while True:
        page = R.jget(f"/api/observations?review_status={status}&limit=500&offset={off}")
        out += page
        if len(page) < 500:
            return out
        off += 500


def walk_d(R):
    pg = R.page(R.desk)

    def d01(pg):
        R.goto(pg, "/review", 3000)
        crit = R.jget("/api/experience/critical")
        items = crit.get("items") or []
        sec = pg.locator("#critical-section")
        shown = sec.is_visible()
        cards = pg.locator("#critical-grid > *").count()
        need(shown == bool(items), f"critical section visible={shown}, API items={len(items)}")
        need(cards == len(items), f"{cards} critical cards, API {len(items)}")
        walky = [it for it in items if it.get("walks") or it.get("walk") or it.get("walk_names") or it.get("walk_ids")]
        txt = sec.inner_text() if shown else ""
        need("Hazard candidate" not in txt and "hazard candidate" not in txt, "a hazard-candidate block is in Critical")
        note = "" if len(walky) == len(items) else f"items without a walk field in the API: {len(items) - len(walky)} (field names {list(items[0].keys()) if items else []})"
        if shown:
            sec.scroll_into_view_if_needed()
        return (f"Critical: {len(items)} items (= API), heading '{txt.splitlines()[0] if txt else '—'}'; "
                "no hazard-candidate block at the top", note)
    R.item("D01", "critical_section", d01, pg=pg)

    def d02(pg):
        R.goto(pg, "/review", 2000)
        pg.click(".review-tab[data-tab='edibility']"); pg.wait_for_timeout(3000)
        vis = pg.locator("#vd-section").is_visible()
        cnt = pg.inner_text("#vd-count") if vis else ""
        rows = pg.locator("#vd-list > *").count()
        need(vis or rows == 0, "verdict section hidden but has rows")
        if vis:
            pg.locator("#vd-section").scroll_into_view_if_needed()
        return (f"Edibility Review: verdict queue {'shown' if vis else 'hidden (empty)'} — {cnt.strip() or rows} ({rows} rows)",
                "21 Oct CHANGELOG expected 5 (Hoheria, Fagus × taurica, Ulmus laciniata, Aspalathus, Bowlesia)")
    R.item("D02", "verdict_queue", d02, pg=pg)

    def _ai_tab(pg):
        R.goto(pg, "/review", 2000)
        pg.click(".review-tab[data-tab='enrichment']"); pg.wait_for_timeout(1000)
        pg.click(".enrich-sub-tab[data-etab='ai-draft']"); pg.wait_for_timeout(4000)

    def d03(pg):
        _ai_tab(pg)
        cards = pg.locator(".ai-draft-field.ai-draft-safety")
        n = cards.count()
        if not n:
            return (EYES, "no warning (look-alike / preparation) draft cards in the queue on this snapshot", "nothing to check")
        missing = []
        for i in range(n):
            c = cards.nth(i)
            t = c.locator(".ai-draft-actions").inner_text()
            for b in ("Approve", "Edit", "Remove"):
                if b not in t:
                    missing.append((c.get_attribute("id"), b))
        # Remove is never offered for a deadly species (server rule `removable`) — allowed to be missing there.
        c0 = cards.first
        c0.scroll_into_view_if_needed()
        c0.locator("button", has_text="Edit").first.click(); pg.wait_for_timeout(400)
        ed = c0.locator("textarea.ai-draft-edit-area").is_visible()
        c0.locator("button", has_text="Edit").first.click(); pg.wait_for_timeout(300)
        # Remove is withheld for a deadly species by design (server `removable`): those are fine.
        unexplained, deadly_ok = [], 0
        for cid, b in missing:
            sci = pg.eval_on_selector(f"#{cid}", "e => e.closest('.ai-draft-species-card').querySelector('.ai-draft-sci').textContent.trim()")
            lvl = R.jget(f"/api/species/{q(sci)}/profile")["safety"]["level"]
            if b == "Remove" and lvl == "deadly":
                deadly_ok += 1
            else:
                unexplained.append((cid, sci, b, lvl))
        need(not unexplained, f"cards missing a button: {unexplained[:6]}")
        return (f"{n} warning cards with ✓ Approve / ✎ Edit / Remove ({deadly_ok} deadly-species cards rightly have no Remove); "
                "Edit opens the text box (closed again, nothing saved)", "")
    R.item("D03", "warning_cards", d03, pg=pg)

    def d04(pg):
        vers = pg.locator(".ai-draft-versions")
        n = vers.count()
        if not n:
            return (MELVIN, "", "no field has two pending versions on this snapshot; ↻ Regenerate needs the AI key "
                    "(disabled on scratch) — check the side-by-side view after a Regenerate in the app")
        row = vers.first.locator(".ai-draft-versions-row > .ai-draft-field")
        boxes = [row.nth(i).bounding_box() for i in range(row.count())]
        side = len(boxes) >= 2 and abs(boxes[0]["y"] - boxes[1]["y"]) < 5
        vers.first.scroll_into_view_if_needed()
        need(side, f"versions not side by side: {boxes}")
        return (f"{n} fields with two versions; first shown side by side ({len(boxes)} columns)", "")
    R.item("D04", "regenerate_side_by_side", d04, pg=pg)

    def d06(pg):
        _ai_tab(pg)
        fields = pg.locator(".ai-draft-field")
        n = fields.count()
        need(n > 0, "AI draft queue empty")
        bad = [fields.nth(i).get_attribute("id") for i in range(min(n, 60))
               if not ("Approve" in fields.nth(i).locator(".ai-draft-actions").inner_text())]
        need(not bad, f"draft cards without Approve: {bad[:5]}")
        sp = pg.locator(".ai-draft-species-card").count()
        regen = pg.locator(".ai-draft-species-card button[title^='Regenerate all drafts']").count()
        return (f"AI drafts: {sp} species cards, {n} field cards each with ✓ Approve / ✎ Edit; {regen} per-species ↻ Regenerate buttons",
                "buttons present only — Approve/Regenerate not pressed (Regenerate needs the AI key)")
    R.item("D06", "ai_draft_buttons", d06, pg=pg)

    def d05():
        dp, seen = _dismissing_page(R)
        R.goto(dp, "/review", 2000)
        dp.click(".review-tab[data-tab='enrichment']"); dp.wait_for_timeout(1500)
        before = _active_jobs(R)
        text, opts = _scope_then_cancel(R, dp, seen, lambda: dp.click("#btn-run-enrich"))
        dp.wait_for_timeout(1500)
        after = _active_jobs(R)
        btn = dp.inner_text("#btn-run-enrich")
        dp.screenshot(path=str(R.out / "D05_run_now_dry_run.png"))
        dp.close()
        need("Nothing has been written yet" in text, "dry-run text missing")
        need(after == before == [], f"jobs after Cancel: {after}")
        need("Run now" in btn, f"button after Cancel: {btn!r}")
        scope = next((l for l in text.splitlines() if l.startswith("Scope:")), "")
        return (f"Run now → scope dialog → walk 5 → dry run shown ({scope[:100]}) → Cancel: no job started, button back to 'Run now'", "")
    R.item("D05", "run_now_dry_run_cancel", d05)
    R.rows[-1]["screenshot"] = "D05_run_now_dry_run.png"

    def d07(pg):
        R.goto(pg, "/review", 3000)
        card = pg.locator("[id^=card-]").first
        oid = card.get_attribute("id").split("-")[1]
        resp = []
        pg.on("response", lambda r: resp.append(r) if f"/api/observations/{oid}/notes" in r.url else None)
        pg.fill(f"#notes-{oid}", "WT reviewer note")
        card.locator("button", has_text="Save notes").click(); pg.wait_for_timeout(1500)
        need(resp and resp[-1].ok, f"PATCH …/{oid}/notes → {resp[-1].status if resp else 'not sent'}")
        saved = resp[-1].json().get("reviewer_notes")
        need(saved == "WT reviewer note", f"PATCH returned reviewer_notes {saved!r}")
        lst = _all_obs(R, "needs_review")
        o = next((x for x in lst if str(x["id"]) == oid), {})
        R.goto(pg, "/review", 3000)
        v = pg.input_value(f"#notes-{oid}") if pg.locator(f"#notes-{oid}").count() else None
        pg.locator(f"#card-{oid}").scroll_into_view_if_needed()
        need(v == "WT reviewer note",
             f"saved (PATCH 200, reviewer_notes stored) but after reload the box shows {v!r}: the Review list "
             f"(/api/observations, ObservationOut) does not send reviewer_notes (key present: {'reviewer_notes' in o})")
        return (f"obs {oid}: note saved and shown after reload", "")
    R.item("D07", "reviewer_notes", d07, pg=pg)

    def d08(pg):
        api = _all_obs(R, "needs_review")
        gate_bad, deep_bad, red, grey = [], [], 0, 0
        for o in api:
            for h in o.get("hazard_candidates") or []:
                red += 1
                ok = any((s.get("rank") is not None and int(s["rank"]) <= 3) or
                         (s.get("score") is not None and float(s["score"]) >= 0.05) for s in h.get("sources") or [])
                if not ok:
                    gate_bad.append((o["id"], h["scientific_name"]))
            for h in o.get("hazard_deep") or []:
                grey += 1
                if any((s.get("rank") is not None and int(s["rank"]) <= 3) or
                       (s.get("score") is not None and float(s["score"]) >= 0.05) for s in h.get("sources") or []):
                    deep_bad.append((o["id"], h["scientific_name"]))
        need(not gate_bad, f"red-line hazards outside top 3 / ≥5%: {gate_bad[:5]}")
        need(not deep_bad, f"grey-line hazards that qualify for the gate: {deep_bad[:5]}")
        cards_red = sum(1 for o in api if o.get("hazard_candidates"))
        # UI: first page of the queue — red line ⇔ API gate hazards; grey line ⇔ deep.
        R.goto(pg, "/review", 1500)
        pg.select_option("#page-size", "96"); pg.wait_for_timeout(4000)
        ids = [x.split("-")[1] for x in pg.eval_on_selector_all("[id^=card-]", "els => els.map(e => e.id)")]
        byid = {str(o["id"]): o for o in api}
        mism = []
        for i in ids:
            o = byid.get(i)
            if not o:
                continue
            has_red = pg.locator(f"#card-{i} .hazard-line").count() > 0
            has_grey = pg.locator(f"#card-{i} .hazard-deep-line").count() > 0
            if has_red != bool(o.get("hazard_candidates")) or has_grey != bool(o.get("hazard_deep")):
                mism.append(i)
        need(not mism, f"cards whose red/grey lines differ from the API: {mism[:8]}")
        first_red = next((i for i in ids if pg.locator(f"#card-{i} .hazard-line").count()), None)
        if first_red:
            pg.locator(f"#card-{first_red}").scroll_into_view_if_needed()
        deep_txt = pg.locator(".hazard-deep-line").first.inner_text() if pg.locator(".hazard-deep-line").count() else ""
        return (f"needs_review: {len(api)} cards, {cards_red} with a red line; every red-line hazard is top 3 or ≥5% "
                f"in some source, every grey line is not; first {len(ids)} UI cards match the API"
                + (f"; grey text e.g. {deep_txt[:60]!r}" if deep_txt else ""),
                "25 Oct CHANGELOG: red line on 29 of 376 queue cards")
    R.item("D08", "hazard_tiers", d08, pg=pg)

    def d09(pg):
        R.goto(pg, "/review", 1500)
        pg.select_option("#filter-status", "hazard_candidates"); pg.wait_for_timeout(4000)
        api = _all_obs(R, "hazard_candidates")
        ids = pg.eval_on_selector_all("[id^=card-]", "els => els.map(e => e.id)")
        no_red = [i for i in ids if not pg.locator(f"#{i} .hazard-line").count()]
        statuses = {}
        for o in api:
            statuses[o["review_status"]] = statuses.get(o["review_status"], 0) + 1
        need(ids, "filter shows no cards")
        need(not no_red, f"cards in the filter without a red line: {no_red[:5]}")
        return (f"Status → ☠ Hazard candidates: {len(api)} in the API ({statuses}); {len(ids)} cards on page 1, all with a red line",
                "25 Oct CHANGELOG: 47 in the filter incl. 18 AI-approved")
    R.item("D09", "hazard_filter", d09, pg=pg)

    def d10(pg):
        mv = _all_obs(R, "manually_verified")
        api_red = [o["id"] for o in mv if o.get("hazard_candidates")]
        need(not api_red, f"manually_verified rows served with hazard_candidates: {api_red[:5]}")
        # UI: Status → Approved (includes manually verified); check the manually verified cards on page 1.
        R.goto(pg, "/review", 1500)
        pg.select_option("#page-size", "96"); pg.wait_for_timeout(2500)
        pg.select_option("#filter-status", "approved"); pg.wait_for_timeout(4000)
        mv_ids = {str(o["id"]) for o in mv}
        ids = [x for x in pg.eval_on_selector_all("[id^=card-]", "els => els.map(e => e.id)") if x.split("-")[1] in mv_ids]
        red = [i for i in ids if pg.locator(f"#{i} .hazard-line").count()]
        need(not red, f"manually_verified cards with a red line: {red[:5]}")
        # 8262 was decided against two Chaerophyllum hazards (25 Oct): no line.
        o = R.jget("/api/observations/8262")
        need(not o.get("hazard_candidates"), f"8262 still carries hazard_candidates {o.get('hazard_candidates')}")
        return (f"{len(mv)} manually_verified rows: none served with a red-line hazard; {len(ids)} of them on Approved page 1, "
                "no red line; 8262 (decided 25 Oct against two hazard candidates) carries none", "")
    R.item("D10", "manually_verified_no_red", d10, pg=pg)
    pg.close()


# ═══════════════════════════════════════════════════════════════════════════
# E. Phone
# ═══════════════════════════════════════════════════════════════════════════
def _join(R, name, mobile=True, geo=None):
    """A fresh participant device joined through its own one-time link. Returns (ctx, token row)."""
    p = R.api("POST", "/api/workshop/participants/find-or-create", json={"name": name}).json()
    sid = R.guest_info["session"]["id"] if getattr(R, "guest_info", None) else \
        R.api("POST", "/api/workshop/sessions", json={"name": "Walkthrough session"}).json()["id"]
    t = R.api("POST", "/api/workshop/tokens", json={"participant_id": p["id"], "workshop_session_id": sid}).json()
    kw = {}
    ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=mobile, has_touch=mobile,
                                extra_http_headers=GUEST_XFF, service_workers="block",
                                **({"geolocation": geo, "permissions": ["geolocation"]} if geo else {}))
    pg = R.page(ctx)
    pg.goto(R.base + "/join/" + t["token"], wait_until="networkidle")
    pg.close()
    return ctx, t, p


def walk_e(R):
    R.melvin("E01", "pair_add_device", "Curator device links need the https share link (ngrok) — pair a real phone "
             "via Settings → Add device. (Scratch check: ＋ Add device without sharing is refused, see E05b.)")
    R.melvin("E02", "installed_app_signed_in", "Real phone: installed app (PWA) opens signed in")

    def e03():
        R.guest_ctx()
        ctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        pg = R.page(ctx)
        r = pg.goto(R.base + "/join/" + R.guest_info["token"]["token"], wait_until="networkidle")
        body = pg.inner_text("body")
        pg.screenshot(path=str(R.out / "E03_used_link.png"))
        ctx.close()
        need(r.status == 410 and "Link already used" in body, f"used link → {r.status} {body[:60]!r}")
        return ("second use of a participant link → 410 'Link already used'", "")
    R.item("E03", "used_link", e03)
    R.rows[-1]["screenshot"] = "E03_used_link.png"

    def e04():
        ctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        pg = R.page(ctx)
        r = pg.goto(R.base + "/species", wait_until="networkidle")
        body = pg.inner_text("body")
        api = pg.evaluate("fetch('/api/species/').then(r => r.status)")
        pg.screenshot(path=str(R.out / "E04_bare_url.png"))
        ctx.close()
        need(r.status == 401 and "Ask Melvin" in body, f"bare URL → {r.status} {body[:80]!r}")
        need(api == 401, f"API without a device → {api}")
        return ("LAN device with no cookie: /species → 401 'Ask Melvin…' page; /api/species/ → 401", "")
    R.item("E04", "bare_url_ask_melvin", e04)
    R.rows[-1]["screenshot"] = "E04_bare_url.png"

    def e05():
        pg, seen = R.page(R.desk), _dialogs_accepting(R)
        pg.on("dialog", lambda d: (seen.append(d.message), d.accept()))
        R.goto(pg, "/settings", 2500)
        devs = R.jget("/api/sharing/devices")
        active = [d for d in devs if d.get("is_active")]
        pg.locator("text=Your devices").first.click(); pg.wait_for_timeout(1200)
        if not active:
            pg.screenshot(path=str(R.out / "E05_revoke.png"))
            return (EYES, f"device list shown ({len(devs)} devices, none active) — nothing to revoke on this snapshot", "")
        target = active[-1]
        btn = pg.locator(f"button[onclick='revokeDevice({target['id']})']")
        need(btn.count() == 1, f"no Revoke button for device {target['id']}")
        btn.scroll_into_view_if_needed()
        btn.click(); pg.wait_for_timeout(2000)
        after = next(d for d in R.jget("/api/sharing/devices") if d["id"] == target["id"])
        pg.screenshot(path=str(R.out / "E05_revoke.png"))
        pg.close()
        need(not after["is_active"], "device still active after Revoke")
        return (f"Settings → Curator devices: Revoke on device {target['id']} ({target.get('name')!r}) → confirm → inactive (scratch DB)", "")
    R.item("E05", "revoke_device", e05)
    R.rows[-1]["screenshot"] = "E05_revoke.png"

    def e05b():
        st = R.jget("/api/sharing/status")
        if st.get("ngrok_active") or st.get("tunnel_url") or st.get("url"):
            return (MELVIN, "", f"not testable here: the scratch server sees Melvin's running ngrok tunnel via ngrok's local "
                    f"API ({st.get('tunnel_url') or st.get('url')}), so ＋ Add device is allowed. Check the 'Start sharing first' "
                    "refusal with sharing stopped.")
        r = R.api("POST", "/api/sharing/devices", json={"name": "WT phone"})
        need(r.status_code == 409 and "Start sharing first" in r.text, f"Add device without sharing → {r.status_code} {r.text[:80]}")
        ctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        g = R.page(ctx)
        r2 = g.evaluate("fetch('/api/sharing/devices', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name:'x'})}).then(r => r.status)")
        ctx.close()
        need(r2 in (401, 403), f"Add device from a LAN device → {r2}")
        return ("＋ Add device without the https share link → 409 'Start sharing first…'; from a LAN device → refused", "")
    R.item("E05b", "add_device_refused_no_https", e05b)

    def e06():
        ctx, t, p = _join(R, "WT Guest Revoked")
        pg = R.page(ctx)
        R.goto(pg, "/map", 2500)
        R.api("POST", f"/api/workshop/tokens/{t['id']}/revoke")
        pg.evaluate("fetch('/api/species/').catch(() => null)")
        pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1500)
        body = pg.inner_text("body")
        pg.screenshot(path=str(R.out / "E06_signed_out.png"))
        ctx.close()
        need("isn't signed in" in body or "Ask Melvin" in body, f"revoked device sees {body[:80]!r}")
        need("offline" not in body.lower(), "revoked device is told it is offline")
        return ("revoked participant device: reload → 'not signed in / Ask Melvin', never 'offline'",
                "the in-page 🔒 banner (offline.js, on a 401 from an open page) is covered by tests/test_signed_out_vs_offline.py")
    R.item("E06", "signed_out_not_offline", e06)
    R.rows[-1]["screenshot"] = "E06_signed_out.png"

    def e07(pg):
        R.goto(pg, "/species", 1500)
        pg.click(".sp-view-btn[data-view='list']"); pg.wait_for_timeout(2000)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        rows = pg.locator("table.sp-table tr.sp-row").count()
        need(rows > 0, "no list rows at 390px")
        need(sw <= 392, f"page scrolls sideways: scrollWidth {sw}px at 390px")
        return (EYES, f"List view at 390px: {rows} rows, no sideways page scroll (scrollWidth {sw})", "column fit / readability needs eyes")
    R.item("E07", "list_view_390", e07, pg=R.page(R.phone))

    def e08():
        w = R.jget("/api/walk/saves/5")
        # A stop whose species carry warning text, so folding can be seen.
        st = w["stops"][0]
        for cand in w["stops"]:
            if any(any((x or {}).get("text") for x in (R.jget(f"/api/species/{q(sp['name'])}/profile")["safety"].get("warnings") or {}).values())
                   for sp in cand.get("species") or []):
                st = cand
                break
        lat = st.get("lat"); lng = st.get("lng")
        ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                                    geolocation={"latitude": lat, "longitude": lng}, permissions=["geolocation"],
                                    service_workers="block")
        pg = R.page(ctx)
        how = _open_saved_walk(R, pg, 5)
        pg.wait_for_timeout(4000)
        cards = pg.locator("#walk-prox-panel .walk-prox-card")
        n = cards.count()
        if not n:
            # Nudge the watch with a new fix at the same stop.
            ctx.set_geolocation({"latitude": lat + 0.00001, "longitude": lng}); pg.wait_for_timeout(4000)
            n = cards.count()
        need(n >= 1, "no proximity alert at walk 5 stop 1")
        det = pg.locator("#walk-prox-panel details.safety-warn-text")
        open_ = pg.locator("#walk-prox-panel details.safety-warn-text[open]").count()
        need(open_ == 0, f"{open_} alert warnings open (should be folded)")
        if det.count():
            det.first.locator("summary").click(); pg.wait_for_timeout(300)
            need(pg.locator("#walk-prox-panel details.safety-warn-text[open]").count() == 1, "warning does not open on tap")
        nd = det.count()
        pg.screenshot(path=str(R.out / "E08_proximity_alert.png"))
        ctx.close()
        return (f"walk 5, GPS at stop {st['label']} ({', '.join(x['name'] for x in st['species'])}): {n} proximity alert(s); {nd} warnings folded" + (", one opens on tap" if nd else
                " (this stop's species carry no warning text — folding not exercised)"), how)
    R.item("E08", "proximity_alert_folds", e08)
    R.rows[-1]["screenshot"] = "E08_proximity_alert.png"

    def e09():
        ctx = R.browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                                    geolocation={"latitude": 47.7039, "longitude": 7.8261}, permissions=["geolocation"],
                                    service_workers="block")
        pg = R.page(ctx)
        R.goto(pg, "/encounters", 2500)
        ctx.set_offline(True); pg.wait_for_timeout(1000)
        banner = pg.locator("#offline-banner").count()
        note = "WT outbox note offline"
        pg.fill("#rec-note", note)
        pg.click("#rec-save-btn"); pg.wait_for_timeout(2000)
        saved = pg.inner_text("#rec-saved") if pg.locator("#rec-saved").is_visible() else pg.inner_text("#rec-msg")
        before = [e for e in R.jget("/api/encounters") if (e.get("text_note") or "") == note] \
            if isinstance(R.jget("/api/encounters"), list) else []
        pg.screenshot(path=str(R.out / "E09_outbox_offline.png"))
        ctx.set_offline(False)
        found = []
        for _ in range(40):
            pg.wait_for_timeout(1500)
            data = R.jget("/api/encounters")
            items = data if isinstance(data, list) else data.get("encounters") or data.get("items") or []
            found = [e for e in items if (e.get("text_note") or "") == note]
            if found:
                break
        ctx.close()
        need("Saved" in saved, f"offline save message {saved!r}")
        need(not before, "the note reached the server while offline")
        need(found, "the queued note never reached the server after going back online (60 s)")
        return (f"offline (banner {'shown' if banner else 'not shown'}): Record → note → Save → '{saved.strip()}' (queued); "
                f"back online → synced as encounter {found[0].get('id')}",
                "emulated with context.setOffline — real airplane mode on a phone is Melvin's check")
    R.item("E09", "outbox_offline_walk", e09)
    R.rows[-1]["screenshot"] = "E09_outbox_offline.png"

    def e10():
        pg = R.page(R.guest_ctx())
        R.goto(pg, f"/species?s={q('Sambucus nigra')}", 3000)
        slot = pg.locator("#guest-notes-slot")
        need(slot.count() and slot.is_visible(), "no note box on the participant's species page")
        if not slot.locator("textarea").count():
            slot.locator("button").first.click(); pg.wait_for_timeout(400)
        ph = slot.locator("textarea").first.get_attribute("placeholder") or ""
        slot.locator("textarea").first.fill("WT Sambucus note")
        slot.locator(".guest-note-save").first.click(); pg.wait_for_timeout(2000)
        txt = slot.inner_text()
        slot.scroll_into_view_if_needed()
        pg.screenshot(path=str(R.out / "E10_participant_note_box.png"))
        pg.close()
        need("Type, or dictate using the mic on your keyboard." in ph, f"placeholder {ph!r}")
        need("WT Sambucus note" in txt, f"saved note not listed: {txt[:100]!r}")
        return ("participant species page: note box with 'Type, or dictate using the mic on your keyboard.'; typed note saved and listed",
                "keyboard dictation itself is Melvin's check on a real phone")
    R.item("E10", "participant_note_box", e10)
    R.rows[-1]["screenshot"] = "E10_participant_note_box.png"
    R.melvin("E10b", "keyboard_dictation", "Dictation with the phone keyboard's mic into the note box")

    def e11():
        pend = _all_obs(R, "needs_review")[:1] + R.jget("/api/observations?review_status=rejected&limit=1&offset=0")
        appr = R.jget("/api/observations?review_status=approved&limit=1&offset=0")
        pg = R.page(R.guest_ctx())
        R.goto(pg, "/map", 1500)
        res = []
        for o, want in [(x, 404) for x in pend] + [(x, 200) for x in appr]:
            thumb = (o.get("thumbnail_path") or "").split("/")[-1]
            st = pg.evaluate(f"fetch('/thumbnails/{thumb}').then(r => r.status)")
            ph = pg.evaluate(f"fetch('/api/observations/{o['id']}/photo').then(r => r.status)")
            res.append((o["id"], o["review_status"], st, ph, want))
        pg.close()
        bad = [r for r in res if r[2] != r[4]]
        need(not bad, f"participant media gate: {bad}")
        return ("participant: " + "; ".join(f"obs {i} ({s}) thumbnail {t}, photo API {p}" for i, s, t, p, _ in res), "")
    R.item("E11", "pending_rejected_404", e11)

    def e12():
        sci = "Sambucus nigra"
        cur = R.jget(f"/api/species/{q(sci)}/observations")
        pg = R.page(R.guest_ctx())
        R.goto(pg, "/map", 1000)
        g = pg.evaluate(f"fetch('/api/species/{q(sci)}/observations').then(r => r.json())")
        R.goto(pg, f"/species?s={q(sci)}", 3000)
        pg.screenshot(path=str(R.out / "E12_participant_gallery.png"))
        pg.close()
        items = lambda d: d if isinstance(d, list) else (d.get("observations") or d.get("items") or d.get("thumbnails") or [])
        gi = items(g)
        bad = [o.get("id") for o in gi if o.get("review_status") and o["review_status"] not in ("approved", "manually_verified")]
        need(not bad, f"participant gallery includes unconfirmed photos {bad[:5]}")
        return (f"{sci}: participant gallery {len(gi)} photos, all confirmed (curator sees {len(items(cur))})", "")
    R.item("E12", "gallery_confirmed_only", e12)
    R.rows[-1]["screenshot"] = "E12_participant_gallery.png"

    def e13():
        pg = R.page(R.guest_ctx())
        R.goto(pg, "/encounters", 2500)
        mic = pg.locator("#rec-btn").is_visible()
        photo = pg.locator("#rec-photo-row").is_visible()
        pg.fill("#rec-note", "WT participant record note"); pg.click("#rec-save-btn"); pg.wait_for_timeout(3000)
        msg = pg.inner_text("#rec-saved") if pg.locator("#rec-saved").is_visible() else pg.inner_text("#rec-msg")
        pg.screenshot(path=str(R.out / "E13_participant_record.png"))
        pg.close()
        cp = R.page(R.desk)
        R.goto(cp, "/encounters", 2500)
        cmic = cp.locator("#rec-btn").is_visible()
        cp.close()
        need(not mic, "participant sees the 🎙 button")
        need(not photo, "participant sees the 📷 Photo button")
        need("Saved" in msg, f"participant typed note: {msg!r}")
        need(cmic, "curator laptop has no 🎙 button")
        return ("Record tab: participant has no 🎙 / 📷, typed note saves ('Saved'); curator laptop shows 🎙",
                "recording audio on the laptop is Melvin's check")
    R.item("E13", "record_tab_roles", e13)
    R.rows[-1]["screenshot"] = "E13_participant_record.png"

    def e14(pg):
        r = R.api("GET", "/static/sw.js")
        m = re.search(r"CACHE_VERSION\s*=\s*'([^']+)'", r.text)
        need(m and m.group(1) == "foragingid-v17", f"service worker version {m.group(1) if m else None}")
        return (f"served sw.js CACHE_VERSION = {m.group(1)}", "the hard refresh on each device is Melvin's")
    R.item("E14", "service_worker_v17", e14, pg=R.page(R.phone))


def _dialogs_accepting(R):
    return []


# ═══════════════════════════════════════════════════════════════════════════
# F. Settings / system
# ═══════════════════════════════════════════════════════════════════════════
SCAN_SCOPED = [  # (button id, label) — every Scan bulk button that goes through the scope dialog
    ("btn-enrich", "▶ Run Enrichment"), ("btn-re-enrich-empty", "Re-enrich empty"),
    ("btn-backfill-run-all", "Backfill all domains"), ("btn-backfill-fungi", "🍄 Fungi edibility"),
    ("btn-redraft-medicinal", "💊 Re-draft medicinal notes"),
]


def _reveal(pg, sel):
    """Open the Scan tab and the collapsed panel (Backfill toggle / Data Trust card) holding sel,
    by clicking the same controls a person would."""
    for _ in range(4):
        if pg.locator(sel).count() and pg.locator(sel).first.is_visible():
            return True
        info = pg.evaluate("""s => { const e = document.querySelector(s); if (!e) return null;
            const pane = e.closest('.tab-pane'); const hidden = [];
            let a = e.parentElement; while (a && a !== document.body) {
              if (getComputedStyle(a).display === 'none' && a.id) hidden.push(a.id); a = a.parentElement; }
            return { pane: pane ? pane.id : null, hidden }; }""", sel)
        if not info:
            return False
        if info["pane"] and not pg.locator(f"#{info['pane']}").is_visible():
            pg.click(f".scan-tab-btn[data-tab='{info['pane'][4:]}']"); pg.wait_for_timeout(800)
            continue
        for hid in info["hidden"]:
            if hid == "backfill-panel":
                pg.click("[onclick='_backfillToggle()']"); pg.wait_for_timeout(1200)
            elif hid.startswith("trust-body-"):
                pg.click(f"#trust-collapse-{hid.split('-')[-1]}"); pg.wait_for_timeout(1200)
    return pg.locator(sel).count() > 0 and pg.locator(sel).first.is_visible()


def walk_f(R):
    def f01(pg):
        R.goto(pg, "/settings", 2500)
        g = pg.locator("text=Your devices & sharing")
        need(g.count() >= 1, "no 'Your devices & sharing' group")
        g.first.click(); pg.wait_for_timeout(800)
        body = pg.inner_text("body")
        toggles = pg.eval_on_selector_all("input[type=checkbox]", "els => els.map(e => (e.closest('label') || e.parentElement).innerText.trim()).filter(t => /guest/i.test(t))")
        need(not toggles, f"guest toggle(s) still in Settings: {toggles}")
        pg.locator("#devices-box").scroll_into_view_if_needed()
        return ("Settings: 'Your devices & sharing' group opens; no guest-mode toggle", "")
    R.item("F01", "devices_and_sharing", f01, pg=R.page(R.desk))

    def f02(pg):
        R.goto(pg, "/settings", 2500)
        pg.locator("text=Your devices & sharing").first.click(); pg.wait_for_timeout(1500)
        rows = pg.inner_text("#devices-box")
        add = pg.locator("#devices-box button", has_text="Add device")
        vis = add.count() and add.first.is_visible()
        pg.locator("#devices-box").scroll_into_view_if_needed()
        return (EYES, f"phone width (localhost = curator): device list shows ({len(rows.splitlines())} lines); "
                f"＋ Add device {'VISIBLE' if vis else 'hidden'}",
                "'no Add device on phone' means on a paired curator PHONE (https device cookie) — the scratch phone is "
                "the laptop at 390px, so this can't stand in for it; Melvin checks on the phone")
    R.item("F02", "device_list_phone", f02, pg=R.page(R.phone))

    def f03():
        pg, seen = _dismissing_page(R)
        R.goto(pg, "/scan", 3000)
        walks = R.jget("/api/walk/saves")
        walks = walks.get("walks", walks) if isinstance(walks, dict) else walks
        out, bad = [], []
        for bid, label in SCAN_SCOPED:
            if not _reveal(pg, f"#{bid}"):
                bad.append(f"{label}: button not found/visible")
                continue
            if not pg.locator(f"#{bid}").first.is_enabled():
                out.append(f"{label}: disabled ({' '.join(pg.inner_text(f'#{bid}').split())[:50]}) — not clicked")
                continue
            before = _active_jobs(R)
            try:
                text, opts = _scope_then_cancel(R, pg, seen, lambda: pg.click(f"#{bid}"))
            except Check as e:
                bad.append(f"{label}: {e}")
                continue
            pg.wait_for_timeout(800)
            after = _active_jobs(R)
            scope = next((l for l in text.splitlines() if l.startswith("Scope:")), "(no Scope line)")
            if after != before:
                bad.append(f"{label}: job started after Cancel {after}")
            want = [w["name"] for w in walks]
            if not all(any(n in o for o in opts) for n in want):
                bad.append(f"{label}: walk dropdown {opts} misses saved walks {want}")
            out.append(f"{label} → {scope[:90]}")
        # Per-domain Backfill "Run" buttons (rendered rows).
        rb = pg.locator("button[onclick^='_backfillRunDomain']")
        if rb.count():
            try:
                text, _ = _scope_then_cancel(R, pg, seen, lambda: rb.first.click())
                out.append("Backfill domain Run → " + next((l for l in text.splitlines() if l.startswith("Scope:")), "dry run")[:80])
            except Check as e:
                bad.append(f"Backfill domain Run: {e}")
        pg.screenshot(path=str(R.out / "F03_scope_buttons.png"))
        pg.close()
        need(not bad, "; ".join(bad))
        return ("every bulk button opens the scope dialog, Continue disabled until a scope is chosen, walk dropdown lists "
                "the saved walks, dry run shows 'Scope: … queued (cap 25)', Cancel starts nothing: " + " | ".join(out), "")
    R.item("F03", "bulk_buttons_scope_first", f03)
    R.rows[-1]["screenshot"] = "F03_scope_buttons.png"

    def f04():
        pg, seen = _dismissing_page(R)
        R.goto(pg, "/settings", 2500)
        if not pg.locator("#btn-draft-backfill").is_visible():
            pg.evaluate("(() => { const e = document.getElementById('btn-draft-backfill'); let d = e && e.closest('details'); while (d) { d.open = true; d = d.parentElement.closest('details'); } })()")
            pg.locator("#btn-draft-backfill").scroll_into_view_if_needed()
        text, opts = _scope_then_cancel(R, pg, seen, lambda: pg.click("#btn-draft-backfill"))
        pg.screenshot(path=str(R.out / "F04_settings_backfill_scope.png"))
        pg.close()
        scope = next((l for l in text.splitlines() if l.startswith("Scope:")), "")
        need("queued (cap 25)" in scope, f"Scope line {scope!r}")
        return (f"Settings → AI draft backfill: scope dialog, walk dropdown {opts}, dry run '{scope[:90]}', Cancel", "")
    R.item("F04", "settings_backfill_scope", f04)
    R.rows[-1]["screenshot"] = "F04_settings_backfill_scope.png"

    R.melvin("F05", "paused_no_network", "Needs a real enrichment run that loses the network (AI key disabled on scratch)")
    R.melvin("F06", "run_summary_skip_counts", "Needs a completed enrichment run (AI key disabled on scratch): Review run "
             "summary skip counts and 'Not queued (cap 25)'")
    R.melvin("F07", "deepseek_key", "The DeepSeek key was blanked in the scratch DB on purpose; check Settings shows it set in the app")
    R.melvin("F08", "jobs_popup", "No background job was run on scratch (dry runs only); check the Jobs pop-up during a real run")
    R.melvin("F09", "caffeinate_exits", "System check: at session start caffeinate (pid 43452) was tied to the live server "
             "with -w 16003, so it should exit with it — confirm after stopping the server")


# ═══════════════════════════════════════════════════════════════════════════
# G. Workshops
# ═══════════════════════════════════════════════════════════════════════════
def walk_g(R):
    state = {}

    def g01(pg):
        R.goto(pg, "/workshops", 3000)
        pg.click("#seg-new"); pg.wait_for_timeout(300)
        pg.fill("#mint-new-name", "WT Workshop Guest")
        if pg.locator("#mint-session-select option").count() == 0:
            raise Check("no workshop session to mint into")
        pg.click("#btn-mint"); pg.wait_for_timeout(3000)
        link = pg.inner_text("#token-link").strip()
        tok = pg.inner_text("#token-string").strip()
        need(link.endswith("/join/" + tok), f"link {link!r}")
        state["link"], state["token"] = link, tok
        pg.locator("#token-reveal").scroll_into_view_if_needed()
        host = urllib.parse.urlparse(link).netloc
        if "ngrok" in host:
            return (f"minted link uses the ngrok address ({host})",
                    "the scratch server picked up Melvin's running tunnel, which points at the LIVE server — this token exists "
                    "only in the scratch DB, so the link is dead there")
        return (FAIL, f"minted link host {host}", "expected the ngrok address")
    R.item("G01", "participant_link_ngrok", g01, pg=R.page(R.desk))

    def g02():
        need(state.get("token"), "no token from G01")
        ctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        pg = R.page(ctx)
        r = pg.goto(R.base + "/join/" + state["token"], wait_until="networkidle")
        pg.wait_for_timeout(1500)
        landing = pg.inner_text("body")
        R.goto(pg, "/map", 3000)
        pins = pg.evaluate("allFeatures.length")
        R.goto(pg, "/species", 2500)
        sp = pg.locator("#species-grid [data-name]").count()
        pg.screenshot(path=str(R.out / "G02_guest_view.png"))
        state["ctx"] = ctx
        me = pg.evaluate("fetch('/api/me').then(r => r.json())")
        need(me.get("is_participant"), f"/api/me {me}")
        need(pins > 0 and sp > 0, f"guest map pins {pins}, species {sp}")
        return (f"second (emulated LAN) phone: link → landing ('{landing.strip().splitlines()[0][:40]}'); map {pins} pins; species {sp}",
                "a real second phone over ngrok is Melvin's check")
    R.item("G02", "guest_view_loads", g02)
    R.rows[-1]["screenshot"] = "G02_guest_view.png"

    def g03():
        ctx = R._ctx(390, 844, mobile=True, headers=GUEST_XFF)
        pg = R.page(ctx)
        r = pg.goto(R.base + "/join/" + state["token"], wait_until="networkidle")
        body = pg.inner_text("body")
        pg.screenshot(path=str(R.out / "G03_used_link.png"))
        ctx.close()
        need(r.status == 410 and "Link already used" in body, f"{r.status} {body[:60]!r}")
        return ("the Workshops-minted link a second time → 410 'Link already used'", "")
    R.item("G03", "used_link_refused", g03)
    R.rows[-1]["screenshot"] = "G03_used_link.png"

    def g04(pg):
        seen = _dialogs(pg)
        R.goto(pg, "/workshops", 3000)
        parts = R.jget("/api/workshop/participants")
        parts = parts if isinstance(parts, list) else parts.get("participants", [])
        p = next(x for x in parts if x["name"] == "WT Workshop Guest")
        pg.click(f"button[onclick='revokeActiveToken({p['id']})']"); pg.wait_for_timeout(2500)
        gp = R.page(state["ctx"])
        r = gp.goto(R.base + "/species", wait_until="networkidle")
        st = gp.evaluate("fetch('/api/species/').then(r => r.status)")
        gp.close(); state["ctx"].close()
        need(r.status == 401 and st == 401, f"after Revoke the guest gets page {r.status}, API {st}")
        return (f"Workshops → Revoke ({p['name']}) → confirm → that phone gets 401 'Ask Melvin' on its next request", "")
    R.item("G04", "revoke", g04, pg=R.page(R.desk))

    R.melvin("G05", "mobile_data", "Participant phone on mobile data through the ngrok link")

    def g06():
        encs = R.jget("/api/encounters")
        encs = encs.get("encounters", encs) if isinstance(encs, dict) else encs
        mine = [e for e in encs if e.get("user_id") == 1]
        need(len(mine) >= 2, f"need two curator encounters, have {len(mine)}")
        pg = R.page(R.desk)
        R.goto(pg, "/encounters", 2500)
        pg.click("#tab-new"); pg.wait_for_timeout(2500)
        boxes = pg.locator("#panel-new .enc-share input[type=checkbox]")
        need(boxes.count() >= 2, f"{boxes.count()} 'Share with guests' boxes on the Encounters tab")
        # The first unticked one becomes shared; another stays unshared.
        ids = pg.eval_on_selector_all("#panel-new .enc-share input[type=checkbox]",
                                      "els => els.map(e => [Number(e.getAttribute('onchange').match(/\\((\\d+)/)[1]), e.checked])")
        share = next(i for i, c in ids if not c)
        keep = next(i for i, c in ids if not c and i != share)
        box = pg.locator(f"#panel-new .enc-share input[onchange*='({share},']")
        box.scroll_into_view_if_needed(); box.check(); pg.wait_for_timeout(1500)
        pg.screenshot(path=str(R.out / "G06_share_with_guests.png"))
        pg.close()
        gp = R.page(R.guest_ctx())
        R.goto(gp, "/map", 1000)
        s1 = gp.evaluate(f"fetch('/api/encounters/{share}').then(r => r.status)")
        s2 = gp.evaluate(f"fetch('/api/encounters/{keep}').then(r => r.status)")
        lst = gp.evaluate("fetch('/api/encounters').then(r => r.json())")
        lst = lst.get("encounters", lst) if isinstance(lst, dict) else lst
        seen_ids = {e["id"] for e in lst}
        others = [e for e in lst if e.get("user_id") not in (1, R.guest_info["participant"]["id"]) and e.get("user_id") is not None]
        R.goto(gp, "/encounters", 2500)
        gp.click("#tab-browse") if gp.locator("#tab-browse").count() else None
        gp.wait_for_timeout(2000)
        gp.screenshot(path=str(R.out / "G06_participant_browse.png"))
        gp.close()
        need(s1 == 200 and share in seen_ids, f"shared encounter {share}: GET {s1}, in list {share in seen_ids}")
        need(s2 in (403, 404) and keep not in seen_ids, f"unshared encounter {keep}: GET {s2}, in list {keep in seen_ids}")
        need(not others, f"participant sees other people's encounters {[e['id'] for e in others][:5]}")
        return (f"ticked 'Share with guests' on encounter {share}: participant sees it (200, listed); unshared {keep} → {s2}; "
                "no other participant's notes in their list",
                "shared audio / confirmed photos on that encounter: check by eye (G06_participant_browse.png)")
    R.item("G06", "share_with_guests", g06)
    R.rows[-1]["screenshot"] = "G06_share_with_guests.png"

    def g07(pg):
        # A participant whose name carries markup leaves a note.
        ctx, t, p = _join(R, "WT <b>Bold</b> Guest")
        gp = R.page(ctx)
        R.goto(gp, f"/species?s={q('Allium ursinum')}", 3000)
        slot = gp.locator("#guest-notes-slot")
        if not slot.locator("textarea").count():
            slot.locator("button").first.click(); gp.wait_for_timeout(400)
        slot.locator("textarea").first.fill("WT note from the bold-name participant")
        slot.locator(".guest-note-save").first.click(); gp.wait_for_timeout(2000)
        ctx.close()
        R.goto(pg, "/encounters", 2500)
        pg.click("#tab-participants"); pg.wait_for_timeout(2500)
        sess = pg.locator(".pn-session").count()
        people = pg.eval_on_selector_all(".pn-participant > div:first-child", "els => els.map(e => e.textContent.trim())")
        bold_tags = pg.locator("#participant-notes-content b").count()
        lit = [x for x in people if "<b>" in x]
        pg.locator(".pn-participant", has_text="<b>").first.scroll_into_view_if_needed() if lit else None
        need(sess >= 1 and people, f"{sess} sessions, people {people}")
        need(lit and bold_tags == 0, f"name with <b> not shown as plain text (people {people[:4]}, <b> elements {bold_tags})")
        return (f"Participant notes: {sess} session group(s), {len(people)} participant groups; '{lit[0]}' shown as plain text", "")
    R.item("G07", "participant_notes_tab", g07, pg=R.page(R.desk))


def find_make(R, pg, walks):
    w = walks[0]
    _open_saved_walk(R, pg, w["id"])
    open_before = pg.evaluate("_walkSaved && _walkSaved.id")
    pg.click("#search-chip-btn"); pg.wait_for_timeout(800)
    open_after = pg.evaluate("_walkSaved && _walkSaved.id")
    pg.click("#find-mode-recipes"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(2500)
    need(f"/recipes?walk={w['id']}" in pg.url,
         f"Make? with walk {w['id']} open went to {pg.url}: the walk was open before Find (_walkSaved.id={open_before}) "
         f"but opening Find (showDiscoverView → _exitWalkMode) cleared it (_walkSaved.id={open_after}), so "
         "_openRecipesPage() never sees a walk")
    view = pg.input_value("#rc-view")
    sel = pg.input_value("#rc-walk")
    need(view == "walk" and sel == str(w["id"]), f"Recipes opened with view={view}, walk={sel}")
    groups = pg.eval_on_selector_all(".rc-group-h", "els => els.map(e => e.textContent.trim())")
    return (f"walk {w['id']} '{w['name']}' open → Make? → /recipes?walk={w['id']}, view By walk, walk selected; groups {groups[:2]}", "")


def _git(R, *args, cwd=None):
    import subprocess
    r = subprocess.run(["git", *args], cwd=str(cwd or R.site_dir), capture_output=True, text=True)
    return r.stdout.strip()


def _remote_count(R):
    return int(_git(R, "--git-dir", str(R.remote_dir), "rev-list", "--count", "main", cwd=R.remote_dir))


def _remote_file(R, rel):
    import subprocess
    r = subprocess.run(["git", "--git-dir", str(R.remote_dir), "show", f"main:{rel}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _publish_panel(R, pg, walk_id):
    how = _open_saved_walk(R, pg, walk_id)
    pg.click("#walk-tab-btn-stats"); pg.wait_for_timeout(1500)
    pg.wait_for_selector("#walk-publish .wpub-box", timeout=30000)
    return how


def _plan(pg):
    pg.locator("#walk-publish button", has_text="plan first").first.click()
    pg.wait_for_function("() => !document.querySelector('#walk-publish').textContent.includes('Planning…')", timeout=300000)
    pg.wait_for_timeout(800)
    return pg.inner_text("#walk-publish")


def _run_job(pg, again, timeout=600000):
    pg.locator("#walk-publish button", has_text=again + "…").last.click(); pg.wait_for_timeout(500)
    pg.check("#wpub-tick")
    pg.click("#wpub-go")
    pg.wait_for_function("() => { const t = document.querySelector('#walk-publish').textContent; "
                         "return /OK$/m.test(t) || document.querySelector('#walk-publish .wpub-ok, #walk-publish .wpub-err'); }",
                         timeout=timeout)
    pg.wait_for_timeout(1000)
    ok = pg.locator("#walk-publish .wpub-ok").count() > 0
    msg = pg.inner_text("#walk-publish .wpub-ok, #walk-publish .wpub-err") if pg.locator("#walk-publish .wpub-ok, #walk-publish .wpub-err").count() else ""
    return ok, msg


def publish_plan_recipes(R, pg):
    pub_count = sum(1 for r in R.jget("/api/recipes")["recipes"] if not r.get("hide_from_public"))
    how = _publish_panel(R, pg, 5)
    text = _plan(pg)
    m = re.search(r"Recipes tab — (\d+) public recipes", text)
    need(m, f"plan shows no 'Recipes tab — N' line: {text[:300]!r}")
    pg.locator("#walk-publish .wpub-sub", has_text="Recipes tab").scroll_into_view_if_needed()
    n = int(m.group(1))
    note = f"the Recipes page lists {pub_count} not hidden from public" + (" — 25 Oct CHANGELOG said 208" if n != 208 else "")
    return (PASS if n == 208 else EYES, f"walk 5 publish plan: 'Recipes tab — {n} public recipes'", note + f"; {how}")


def republish_recipes(R, pg):
    before = _remote_count(R)
    _publish_panel(R, pg, 5)
    _plan(pg)
    tick_front = pg.locator("#walk-publish input[type=checkbox]", has_text="Front page").count()
    ok, msg = _run_job(pg, "Republish")
    need(ok, f"republish failed: {msg[:300]}")
    after = _remote_count(R)
    need(after == before + 1, f"bare repo commits {before} → {after}")
    pub = R.jget("/api/experience/publications")
    pubs = pub if isinstance(pub, list) else pub.get("publications", [])
    slug = next(p["slug"] for p in pubs if p.get("saved_walk_id") == 5)
    page = _remote_file(R, f"w/{slug}/index.html") or b""
    prev = (_remote_file(R, "preview.html") or b"").decode("utf-8", "replace")
    walks = json.loads(_remote_file(R, "walks.json") or b"{}")
    need(b"recipes" in page.lower(), "published page has no Recipes tab")
    need("index.html#recipes" in prev or "#recipes" in prev, "preview.html (/b card) has no #recipes link")
    need(walks.get("featured") == slug, f"front page is {walks.get('featured')}, not {slug}")
    # Open the published files from a checkout of the bare repo.
    co = R.out / "_site_checkout"
    import shutil, subprocess
    shutil.rmtree(co, ignore_errors=True)
    subprocess.run(["git", "clone", "-q", str(R.remote_dir), str(co)], check=True)
    p2 = R.page(R.desk)
    p2.goto((co / "w" / slug / "index.html").as_uri() + "#recipes", wait_until="load"); p2.wait_for_timeout(2500)
    vis = p2.evaluate("""() => { const t = [...document.querySelectorAll('[id*=recipe], [data-tab=recipes], section')]
                         .filter(e => e.offsetParent !== null && /recipe/i.test(e.id + ' ' + (e.dataset.tab || '')));
                         return t.length; }""")
    p2.screenshot(path=str(R.out / "H12_published_recipes_tab.png"))
    links = re.findall(r'href="([^"]*#recipes[^"]*)"', prev)
    p2.goto((co / "preview.html").as_uri(), wait_until="load"); p2.wait_for_timeout(1000)
    p2.screenshot(path=str(R.out / "H12_preview_card.png"))
    target = links[0] if links else ""
    tpath = (co / target.split("#")[0].lstrip("/")) if target and not target.startswith("http") else None
    p2.close()
    shutil.rmtree(co, ignore_errors=True)
    need(vis > 0, "the #recipes tab is not shown when opening the page at #recipes")
    return (f"Republish walk 5 → local bare repo (+1 commit, front page = {slug}); w/{slug}/ has the Recipes tab and opens on it "
            f"at #recipes; preview.html card links {target!r}" + (f" (file exists: {tpath.exists()})" if tpath else ""),
            ("no Front page tick in the confirm (the panel always sends front_page=true) — CHANGELOG next-step says "
             "'republish walk 5 with Front page ticked'" if not tick_front else "") +
            "; screenshots H12_published_recipes_tab.png, H12_preview_card.png")


def publish_unpublish_test_walk(R, pg):
    before = _remote_count(R)
    _publish_panel(R, pg, 3)
    box = pg.locator("#walk-publish")
    if box.locator("#wpub-new-slug").count():
        box.locator("#wpub-new-slug").fill("wt-little-foray")
        box.locator("button", has_text="Set up publishing").click()
        pg.wait_for_timeout(2000)
    text = _plan(pg)
    if "Must be fixed before publishing" in text:
        probs = pg.inner_text("#walk-publish .wpub-list.wpub-bad")
        return (EYES, "walk 3 'little foray' plan has blockers, so the publish → unpublish round trip was not run",
                f"blockers: {' | '.join(probs.splitlines())[:300]}")
    ok, msg = _run_job(pg, "Publish")
    need(ok, f"test walk publish failed: {msg[:300]}")
    mid = _remote_count(R)
    pg.locator("#walk-publish button", has_text="OK").first.click(); pg.wait_for_timeout(1500)
    pg.locator("#walk-publish button", has_text="Unpublish…").click(); pg.wait_for_timeout(300)
    pg.check("#wpub-untick"); pg.click("#wpub-ungo")
    pg.wait_for_function("() => document.querySelector('#walk-publish .wpub-ok, #walk-publish .wpub-err')", timeout=600000)
    ok2 = pg.locator("#walk-publish .wpub-ok").count() > 0
    msg2 = pg.inner_text("#walk-publish .wpub-ok, #walk-publish .wpub-err")
    after = _remote_count(R)
    gone = _remote_file(R, "w/wt-little-foray/index.html") is None
    saved = any(w["id"] == 3 for w in (lambda d: d.get("walks", d) if isinstance(d, dict) else d)(R.jget("/api/walk/saves")))
    need(ok2, f"unpublish failed: {msg2[:300]}")
    need(mid == before + 1 and after == mid + 1, f"bare repo commits {before} → {mid} → {after}")
    need(gone, "w/wt-little-foray/ still in the bare repo after unpublish")
    need(saved, "saved walk 3 gone after unpublish")
    return (f"walk 3 published as wt-little-foray (+1 commit) then unpublished (+1 commit): page gone from the bare repo, "
            f"saved walk kept ({msg2.strip()[:80]})", "")


def publish_no_network(R, pg):
    real = _git(R, "remote", "get-url", "origin")
    need(Path(real).resolve() == R.remote_dir.resolve(), f"scratch clone origin is {real}, not the bare repo — refusing")
    _git(R, "remote", "set-url", "origin", "https://foraging-experience.invalid/site.git")
    try:
        before = _remote_count(R)
        _publish_panel(R, pg, 5)
        _plan(pg)
        ok, msg = _run_job(pg, "Republish", timeout=300000)
    finally:
        _git(R, "remote", "set-url", "origin", real)
    need(not ok and "No network" in msg, f"publish with an unreachable remote → {msg[:200]!r}")
    need(_remote_count(R) == before, "something reached the bare repo")
    status = _git(R, "status", "--porcelain")
    need(status == "", f"site clone left dirty: {status[:200]}")
    return (f"remote unreachable (unresolvable host) → publish stops: '{msg.strip()[:120]}'; nothing pushed; clone clean",
            "emulated server-side (the push is the server's, not the browser's)")


WALKS = {"A": walk_a, "B": walk_b, "C": walk_c, "D": walk_d, "E": walk_e, "F": walk_f, "G": walk_g, "H": walk_h}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8765")
    ap.add_argument("--out", default=str(Path.home() / "Documents" / "ForagingID" /
                                         f"walkthrough_run_{date.today():%Y%m%d}"))
    ap.add_argument("--only", default="ABCDEFGH")
    ap.add_argument("--site", required=True,
                    help="the scratch server's foraging-experience clone (its HOME/foraging-experience)")
    ap.add_argument("--remote", required=True, help="the local bare repo that clone pushes to")
    a = ap.parse_args()
    port = urllib.parse.urlparse(a.base).port
    if port == 8000:
        sys.exit("Refusing to run against :8000 — this script writes; use the scratch server.")
    R = Run(a.base, Path(a.out).expanduser())
    R.site_dir, R.remote_dir = Path(a.site).expanduser(), Path(a.remote).expanduser()
    if R.site_dir.resolve() == (Path.home() / "foraging-experience").resolve():
        sys.exit("Refusing: --site is the real ~/foraging-experience clone.")
    with sync_playwright() as pw:
        R.start(pw)
        try:
            for letter in a.only.upper():
                if letter in WALKS:
                    print(f"── Walkthrough {letter}", flush=True)
                    WALKS[letter](R)
        finally:
            if WALK_LOAD_FAILURES:
                R.rows.append({"item": "WALK LOAD", "result": FAIL, "screenshot": "",
                               "asserted": f"{len(WALK_LOAD_FAILURES)} failed saved-walk loads (retried)",
                               "note": "; ".join(f"walk {w} attempt {a}: {m[:90]}" for w, a, m in WALK_LOAD_FAILURES)})
            R.write()
            R.browser.close()
    counts = {}
    for r in R.rows:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    print("RESULTS", json.dumps(counts), "→", R.out / "results.csv")


if __name__ == "__main__":
    main()
