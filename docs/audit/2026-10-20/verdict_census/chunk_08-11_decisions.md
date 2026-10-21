# Verdict census — chunks 08–11 decisions (Melvin, 21 Oct 2026)

Applied 21 Oct 2026. 180 chunk rows = 179 verdicts written + 479 *Phyllospadix scouleri* (no verdict; observation sent back to Review). Every verdict through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunks 08–11"; severity through `severity_for_verdict` with the requested severity. DEFAULT rows (100) kept their verdict and severity and were marked human-verified (incl. rows verified as multi-source-tier-a / auto / pfaf / unlocked_for_review). The status endpoint (AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_153758.sqlite` (quick_check ok; no commit). No job, scan or background process was running.
- Verdict history: `species_edibility_history` ids **1358–1886** (529 rows: edibility_status 179, edibility_verified 162, edibility_verified_by 179, toxicity_severity 9). Read back by id: 0 mismatches.
- Curator text (species-page field path, changed_by='human', word for word; byte-identical in row and history): `culinary_info_history` ids **3366–3379**. Replaced existing PFAF text in 180, 527, 502, 290 preparation_warnings and 314 edible_parts (old text kept as old_value).
- **106 Keck look-alike: not written** (Melvin: keep the existing curator look-alike text). Its preparation_warnings placeholder stays for batch 6 (E-14).
- Common names (species-page common-names editor, human; history **3380–3383**): 501 preferred "Brown Funnel Polypore" → **"Suede bolete"**, names [Suede bolete, Brown Funnel Polypore]; 390 "Black Walnut" → **"Walnut"**, names [Walnut, Black Walnut, English walnut, Common Walnut]; 172 "نعناع" → **"Peppermint"** (Peppermint was already first; list unchanged); 187 "Зверобой" → **"St John's wort"**, names [St John's wort, Зверобой] (Melvin: "St John's Wort" de-duplicated).
- No pending verdict drafts on any of these species — none rejected. All draft counts identical before and after.
- Added to batch 11b scope: 608↔589, 103↔531, 600↔749, 82↔200, and a GBIF check of 187 "*Hypericum perfoliatum*" (likely *H. perforatum*). Nothing merged.

## 479 *Phyllospadix scouleri*
- Its one approved observation, **10176**, sent back to Review through `PATCH /api/observations/10176/review?status=needs_review` (same function), reviewer note "implausible ID — Pacific seagrass on a Black Forest walk; re-check". `observation_edits` logs review_status approved → needs_review and the note. identification_status stays 'identified'; species_primary unchanged.
- Now off the species page (633 → 632 species), off the map (no pin for 10176), and out of walk membership (walk 5 members 102 → 101).
- **Morning sunshine Gresgen to Adelsberg (walk 5): stops not renumbered** — still 59 stops, same labels. Stop 35 was 10176 alone; it stays as stop 35 with no species (a saved stop keeps its observation ids so a renumber keeps them). Re-check or relink 10176 in Review to fill it again, or renumber the walk.
- **Published copy unaffected**: walk 5 has never been published (no overrides file; `dist/` holds walk 4 only — root and `w/ruemmelsbuehl/`), and "Phyllospadix" appears nowhere in `dist/`. Not republished.
- Species 479 itself is unchanged (edible / none / unverified); no verdict was written for it.

## Culinary content
- **Newly shown: none.**
- **Newly hidden: 32** (all edible/caution → toxic or inedible). With content:
  - 19 White Butterbur (*Petasites albus*): edible parts + approved recipe #121 "White Butterbur Stems with Brown Butter, Capers, and Toasted Hazelnuts"
  - 196 Acanthus (*Acanthus spinosus*): approved recipe #119 "Acanthus Spinosus — Braised Young Leaves with Slow-Cooked White Beans, Preserved Lemon & Smoked Oil"
  - 309 Great Willowherb (*Epilobium hirsutum*): edible parts + approved recipe #69 "Kaporie Green — Willowherb Broth with Fermented Barley, Wild Garlic Oil & Soft-Boiled Egg"
  - edible parts only: 240 *Lonicera periclymenum*, 360 *Dactylorhiza maculata*, 364 *Equisetum sylvaticum*, 413 *Blechnum spicant*, 477 *Dryopteris crassirhizoma*, 485 *Hieracium umbellatum*, 518 *Cytisus scoparius*, 637 *Lilium martagon*, 684 *Nymphaea alba*
  - the other 20 had no culinary text.

## Curator text (verbatim)

- 295 Ramsons (Allium ursinum) — look_alike_warnings: "Deadly look-alikes: lily of the valley and autumn crocus can grow among it. Crush each leaf — only wild garlic smells of garlic (the smell stays on your fingers, so check leaf by leaf)."
- 363 Yellow gentian (Gentiana lutea) — look_alike_warnings: "Deadly look-alike: white hellebore grows in the same meadows — its leaves are alternate and pleated; yellow gentian's are opposite. Only dig roots of plants you saw in flower."
- 405 Parasol (Macrolepiota procera) — look_alike_warnings: "Deadly small Lepiotas look similar — pick only large ones with a movable double ring and a snakeskin-patterned stem; if in doubt, leave it."
- 355 chicken of the woods (Laetiporus sulphureus) — preparation_warnings: "Always cook well; some people react, so try a little first. Avoid ones growing on yew."
- 180 Water-cress (Nasturtium officinale) — preparation_warnings: "Wild watercress can carry liver fluke where sheep or cattle graze — cook it unless it comes from clean, stock-free water."
- 497 Brown Birch-bolete (Leccinum scabrum) — preparation_warnings: "Cook thoroughly — can upset the stomach raw or undercooked."
- 489 Orange Birch Bolete (Leccinum versipelle) — preparation_warnings: "Cook thoroughly — can upset the stomach raw or undercooked."
- 187 Зверобой (Hypericum perfoliatum) — preparation_warnings: "Interacts with many medicines, including the contraceptive pill and antidepressants; can make skin sun-sensitive."
- 527 field horsetail (Equisetum arvense) — preparation_warnings: "Only young spring shoots, cooked, in moderation."
- 527 field horsetail (Equisetum arvense) — look_alike_warnings: "Marsh horsetail (toxic) looks similar."
- 502 Honey Mushroom (Armillaria mellea) — preparation_warnings: "Toxic when raw — ensure it's thoroughly cooked. Can cause a reaction in some people; try a small amount first."
- 502 Honey Mushroom (Armillaria mellea) — look_alike_warnings: "Deadly funeral bell (Galerina) grows in the same places — brown spore print, where honey fungus is white. Sulphur tuft (toxic) has greenish-yellow gills."
- 290 White Melilot (Melilotus albus) — preparation_warnings: "Use fresh or well dried; mouldy or fermented sweet clover is toxic (thins the blood)."
- 314 Opium Poppy (Papaver somniferum) — edible_parts: "Seeds only — the rest of the plant is toxic."

## Rows

| group | chunk | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after | culinary |
|---|---|---|---|---|---|---|---|
| toxic/toxic | 09 | 566 | Boneset (Eupatorium cannabinum) | inedible/none/0/pfaf | toxic/toxic/1/human | ✗ not edible → ☠ toxic | blocked |
| toxic/toxic | 09 | 518 | Broom (Cytisus scoparius) | caution/none/0/None | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 11 | 335 | Butterburs (Petasites petasites) | caution/none/0/unlocked_for_review | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 11 | 334 | Common Butterbur (Petasites hybridus) | caution/none/0/unlocked_for_review | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 09 | 683 | crested woodfern (Dryopteris cristata) | inedible/none/0/pfaf | toxic/toxic/1/human | ✗ not edible → ☠ toxic | blocked |
| toxic/toxic | 10 | 283 | greater bird's-foot-trefoil (Lotus pedunculatus) | caution/none/0/unlocked_for_review | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 09 | 477 | Thick-stemmed woodfern (Dryopteris crassirhizoma) | caution/none/0/None | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 11 | 19 | White Butterbur (Petasites albus) | edible/none/0/unlocked_for_review | toxic/toxic/1/human | ✓ edible → ☠ toxic | **newly hidden** |
| toxic/toxic | 10 | 240 | Woodbine (Lonicera periclymenum) | caution/none/0/None | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| inedible/none | 08 | 196 | Acanthus (Acanthus spinosus) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 09 | 272 | Alice Eastwood's fleabane (Erigeron aliceae) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 66 | Bedstraw broomrape (Orobanche caryophyllacea) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 485 | Canada hawkweed (Hieracium umbellatum) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 529 | Dotted Loosestrife (Lysimachia punctata) | caution/none/0/unlocked_for_review | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 377 | Forget-me-not (Myosotis scorpioides) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 182 | Fox-and-cubs (Pilosella aurantiaca) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 94 | French cranesbill (Geranium endressii) | caution/none/0/unlocked_for_review | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 510 | Ganoderma carnosum | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 09 | 309 | Great Willowherb (Epilobium hirsutum) | edible/none/0/None | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 08 | 413 | Hard Fern (Blechnum spicant) | edible/none/0/None | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 526 | heath bedstraw (Galium saxatile) | caution/none/0/unlocked_for_review | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 311 | meadow pea (Lathyrus pratensis) | caution/none/1/multi-source-tier-a | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 474 | Netted shield lichen (Parmelia sulcata) | caution/none/0/unlocked_for_review | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 516 | New England Hawkweed (Hieracium sabaudum) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 684 | Nymphaea alba | edible/none/0/pfaf | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 11 | 387 | Pinesap (Monotropa hypopitys) | caution/none/0/unlocked_for_review | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 09 | 447 | Red-banded Polypore (Fomitopsis pinicola) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 195 | Scabious (Knautia arvernensis) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 09 | 360 | Spotted Orchis (Dactylorhiza maculata) | edible/none/0/None | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 82 | Thistle (Lophiolepis ferox) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 637 | Turk's cap (Lilium martagon) | caution/none/0/pfaf | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 266 | Wall hawkweed (Hieracium murorum) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 10 | 132 | Wood Bedstraw (Galium sylvaticum) | edible/none/0/unlocked_for_review | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 09 | 364 | Wood horsetail (Equisetum sylvaticum) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| caution → edible/none | 08 | 52 | Ajuga (Ajuga reptans) | caution/none/0/unlocked_for_review | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 308 | Alpine Lady's-mantle (Alchemilla alpina) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 598 | American watermat (Chrysosplenium americanum) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 339 | Beaked Hawksbeard (Crepis vesicaria) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 438 | black pine (Pinus nigra) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 651 | Blue Foxglove (Campanula trachelium) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 553 | Carpinus caroliniana | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 693 | Centaury (Centaurium erythraea) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 274 | Common Kidney-Vetch (Anthyllis vulneraria) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 638 | Dames rocket (Hesperis matronalis) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 667 | Eyebright (Euphrasia officinalis) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 654 | Great Maple (Acer platanoides) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 173 | Horehound (Marrubium vulgare) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 342 | horseweed (Erigeron canadensis) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 538 | Hydrocotyle sibthorpioides | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 176 | Lady's-mantle (Alchemilla mollis) | caution/none/0/unlocked_for_review | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 591 | Loosestrife (Lysimachia vulgaris) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 482 | marsh willowherb (Epilobium palustre) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 228 | mayweed (Matricaria chamomilla) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 439 | mica cap (Coprinellus micaceus) | caution/none/0/unlocked_for_review | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 344 | narrow-leaved hawksbeard (Crepis tectorum) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 646 | Narrowleaf Bittercress (Cardamine impatiens) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 691 | Oxalis grandis | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 512 | Papaver setiferum | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 50 | Running Jenny (Lysimachia nummularia) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 156 | Shaggy Mane (Coprinus comatus) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 219 | Shining Lady's-mantle (Alchemilla micans) | caution/none/0/unlocked_for_review | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 08 | 615 | Silver Thistle (Carlina acaulis) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 162 | square-stemmed willowherb (Epilobium tetragonum) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 11 | 612 | Vitrapunkel (Phyteuma spicatum) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 600 | Wall Lettuce (Lactuca muralis) | caution/none/0/pfaf | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 09 | 634 | Water Thistle (Cirsium oleraceum) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 10 | 682 | Yellow archangel (Lamium galeobdolon) | caution/none/0/pfaf | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution/none + text | 10 | 497 | Brown Birch-bolete (Leccinum scabrum) | edible/none/0/unlocked_for_review | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 10 | 355 | chicken of the woods (Laetiporus sulphureus) | edible/none/0/unlocked_for_review | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 09 | 527 | field horsetail (Equisetum arvense) | edible/none/0/None | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 08 | 502 | Honey Mushroom (Armillaria mellea) | caution/none/1/multi-source-tier-a | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| caution/none + text | 10 | 489 | Orange Birch Bolete (Leccinum versipelle) | edible/none/0/unlocked_for_review | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 10 | 405 | Parasol (Macrolepiota procera) | edible/none/0/unlocked_for_review | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 08 | 295 | Ramsons (Allium ursinum) | edible/none/1/auto | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 11 | 180 | Water-cress (Nasturtium officinale) | edible/none/0/None | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 11 | 290 | White Melilot (Melilotus albus) | edible/none/0/None | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| caution/none + text | 10 | 363 | Yellow gentian (Gentiana lutea) | caution/none/0/None | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| caution/none + text | 10 | 187 | Зверобой (Hypericum perfoliatum) | edible/none/0/unlocked_for_review | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| edible/none + text | 11 | 314 | Opium Poppy (Papaver somniferum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 486 | Acer ser. Acer (Acer pseudoplatanus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 322 | Annual Daisy (Bellis annua) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 608 | Anthemis tinctoria | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 11 | 15 | apetalous sandwort (Moehringia trinervia) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 358 | Ash (Fraxinus excelsior) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 431 | Azarole (Crataegus azarolus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 225 | Bay Bolete (Imleria badia) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 157 | Beefsteak Polypore (Fistulina hepatica) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 569 | Bigleaf maple (Acer macrophyllum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 390 | Black Walnut (Juglans regia) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 3 | Bog Heather (Erica tetralix) | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 11 | 370 | Bog spruce (Picea mariana) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 501 | Brown Funnel Polypore (Boletus subtomentosus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 375 | Bull Thistle (Cirsium vulgare) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 143 | Caucasian Spruce (Picea orientalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 160 | cep (Boletus edulis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 403 | chanterelle (Cantharellus cibarius) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 80 | Cleavers (Galium aparine) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 456 | common poppy (Papaver rhoeas) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 8 | corn mint (Mentha arvensis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 587 | Crab apple (Malus sylvestris) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 135 | cuckoo flower (Cardamine pratensis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 81 | Daisy (Bellis perennis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 216 | Daisy (Leucanthemum ircutianum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 514 | disc mayweed (Matricaria discoidea) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 575 | Downy birch (Betula pubescens) | edible/none/0/pfaf | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 307 | Dryad's Saddle (Cerioporus squamosus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 236 | European Larch (Larix decidua) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 326 | European Stonecrop (Petrosedum ochroleucum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 281 | European wood-sorrel (Oxalis acetosella) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 410 | Field Maple (Acer campestre) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 551 | Field thistle (Cirsium arvense) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 531 | fireweed (Chamaenerion angustifolium) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 103 | Fireweed (Epilobium angustifolium) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 299 | Five-seeded Hawthorn (Crataegus pentagyna) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 574 | Fuchsia (Fuchsia magellanica) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 223 | Giant Polypore (Meripilus giganteus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 278 | Goatsbeard (Aruncus dioicus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 382 | Great Marsh-bedstraw (Galium elongatum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 317 | greater burdock (Arctium lappa) | edible/none/1/auto | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 37 | Ground ivy (Glechoma hederacea) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 222 | Ground Ivy (Glechoma hirsuta) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 21 | hairy bittercress (Cardamine hirsuta) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 79 | Hawthorn (Crataegus monogyna) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 368 | Hazel (Corylus avellana) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 192 | He-balsam (Picea rubens) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 32 | Hedge Garlic (Alliaria petiolata) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 351 | honesty (Lunaria annua) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 104 | Hop Clover (Medicago lupulina) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 534 | Hop-hornbeam (Ostrya carpinifolia) | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 08 | 416 | Hornbeam (Carpinus betulus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 291 | horsemint (Mentha longifolia) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 257 | Horseradish (Armoracia rusticana) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 349 | Hylotelephium telephium | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 378 | Indian Balsam (Impatiens glandulifera) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 562 | Ivy-leaved toadflax (Cymbalaria muralis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 596 | Jewelweed (Impatiens noli-tangere) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 567 | Lady's Mantle (Alchemilla xanthochlora) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 345 | Lady's-mantle (Alchemilla vulgaris) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 276 | large bittercress (Cardamine amara) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 340 | lemon balm (Melissa officinalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 241 | Lemon verbena (Aloysia citrodora) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 253 | Lewis' mock orange (Philadelphus lewisii) | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 08 | 11 | ling (Calluna vulgaris) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 393 | Lucky-clover (Oxalis tetraphylla) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 28 | marsh thistle (Cirsium palustre) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 365 | Meadowsweet (Filipendula ulmaria) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 179 | Mint (Mentha aquatica) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 611 | Mountain Bluet (Centaurea montana) | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 10 | 53 | Nipplewort (Lapsana communis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 568 | Oregano (Origanum vulgare) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 333 | Perennial Honesty (Lunaria rediviva) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 323 | porcelain mushroom (Oudemansiella mucida) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 170 | Pot marjoram (Origanum onites) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 424 | Rose Mallow (Malva trimestris) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 78 | Silverweed (Argentina anserina) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 238 | Spearmint (Mentha spicata) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 86 | Sticky Mouse-ear (Cerastium glomeratum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 506 | Summer Bolete (Boletus reticulatus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 429 | Sweet Chestnut (Castanea sativa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 374 | Tall blue-lettuce (Cicerbita alpina) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 556 | Tall Cotton-Grass (Eriophorum angustifolium) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 564 | Trailing bellflower (Campanula poscharskyana) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 267 | trailing restharrow (Ononis arvensis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 55 | Turkey hornbeam (Carpinus orientalis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 282 | velvetweed (Oenothera curtiflora) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 77 | Wall pellitory (Parietaria judaica) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 618 | Water Avens (Geum rivale) | edible/none/0/pfaf | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 17 | Wavy Bittercress (Cardamine flexuosa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 49 | Whitebeam (Aria edulis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 205 | Wild Lettuce (Lactuca serriola) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 181 | Wild Strawberry (Fragaria vesca) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 33 | Wintercress (Barbarea vulgaris) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 92 | Wood Avens (Geum urbanum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 336 | Wood Hedgehog (Hydnum repandum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 10 | 595 | Wood pimpernel (Lysimachia nemorum) | inedible/none/0/pfaf | inedible/none/1/human | ✗ not edible → ✗ not edible | blocked |
| DEFAULT keep + verify | 11 | 243 | Wood-shamrock (Oxalis dillenii) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 09 | 198 | Woodruff (Galium odoratum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 08 | 202 | Yarrow (Achillea millefolium) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 11 | 172 | نعناع (Mentha × piperita) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |

Names in the Rows table are as they appeared in the chunk files (before the 4 renames).
Grid badge = `safety_decision()` label, else the grid's verdict badge (✓ edible / ✗ not edible).
