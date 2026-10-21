# Verdict census — chunks 12–16 decisions (Melvin, 21 Oct 2026) — final round

Applied 21 Oct 2026. 180 chunk rows = 123 verdicts written (chunks 12–14 DEFAULT rows included) + 56 chunk 15–16 rows already human-verified (left untouched; read back unchanged) + 457 *Trametes versicolor* skipped (done). Every verdict through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunks 12–16". The status endpoint (AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_155418.sqlite` (quick_check ok; no commit). No job, scan or background process was running.
- Verdict history: `species_edibility_history` ids **1887–2228** (342 rows: edibility_status 123, edibility_verified 102, edibility_verified_by 111, toxicity_severity 6). Read back by id: 0 mismatches.
- Curator text (species-page field path, human, word for word; byte-identical in row and history): `culinary_info_history` **3384–3385**. Both replaced PFAF text (kept as old_value): 402 *Sambucus racemosa* preparation_warnings; 25 *Symphytum officinale* preparation_warnings — 25's previous text was **not** curator-authored (PFAF, no history row), so no STOP.
- Common names (species-page common-names editor, human; history **3386–3387**): 391 *Ribes nigrum* preferred "Инек-караа" → **"Blackcurrant"**, names [Blackcurrant, Black Currant, European black currant, Инек-караа]; 217 *Silene pendula* "Ragged Robin" → **"Nodding catchfly"**, names [Nodding catchfly, Drooping catchfly] ("Ragged Robin" dropped — it stays on 621 *Silene flos-cuculi*, unchanged).
- 794 *Sparassis crispa*: draft **#3063** rejected — it is an old fungi-lookup draft (model `fao_fungi+mushroom_observer`), so the verdict-draft path refuses it; rejected through the AI-draft reject path (`POST /api/species/{name}/drafts/edibility_status/reject`) and its reason stored with `record_rejection_reason`: "superseded by Melvin's human verdict (edible)". Card and verdict unchanged (edible / none / human).
- No pending verdict drafts on the 123 verdict rows — none to reject. Draft counts otherwise unchanged.
- **277 *Rosa dumalis*: now edible / none / human-verified.** The walk 4 build gate (`export.py --walk-id 4 --overrides overrides/walk4.json --default --plan-only`, writes nothing): before this round it failed on 277 ("edible but not human-verified"); after, it first failed on a **batch 5 regression** — `app_styles.py` read the walk ☠ badge colours and shape from `_culinaryGateBadge()` in index.html, which since batch 5 calls `SafetyGate.badge()`. Both anchors now read `static/js/safety-gate.js` (same values: #dc2626 / #fff, 0.68rem, 1px 6px, 4px). **The gate now passes (exit 0)**: 62 species shown, 277 as edible; 1 AI-agreed-only species flagged for review (193 *Stellaria graminea*, not a blocker). `dist/` untouched; nothing republished.

## Culinary content
- **Newly shown: none.**
- **Newly hidden: 16** (caution/edible → toxic or inedible):
  - 22 David's-harp (*Polygonatum multiflorum*): edible parts + approved recipe #37 "Solomon's Seal Shoots with Spring Alliums and Brown Butter"
  - 97 Aspen (*Populus tremula*): edible parts + approved recipe #48 "Aspen Inner Bark Flatbread with Rendered Bone Fat and Wild Garlic"
  - edible parts only: 221 *Polygala vulgaris*, 385 *Pyrola minor*, 409 *Salix caprea*, 432 *Salix alba*, 504 *Populus tremuloides*, 585 *Genista tinctoria*, 633 *Populus nigra*, 670 *Polygonatum odoratum*, 679 *Polystichum aculeatum*, 689 *Spiraea salicifolia*, 696 *Polygala alpestris*
  - no culinary text: 48 *Vinca minor*, 188 *Genista sagittalis*, 318 *Symphytum caucasicum*

## Census summary (all 633 census species, after all rounds)

| verdict / severity | species |
|---|---|
| edible/none | 355 |
| inedible/none | 143 |
| toxic/toxic | 81 |
| caution/none | 40 |
| toxic/deadly | 12 |
| NULL/NULL | 2 |

- By verdict: edible 355, inedible 143, toxic 93 (81 toxic + 12 deadly), caution 40, no card 2.
- **Not human-verified: 3** — *Collybia nuda* and *Conyza canadensis* (no species card; batch 11b relink) and 479 *Phyllospadix scouleri* (observation 10176 sent back to Review; species row still edible/none, unverified; no longer on the species page, which now lists 632).
- **Grid badge mismatches: 0 among species with a card.** The only 2 rows without a verdict badge match are the two no-card names, which fail closed to "⚠ toxicity unknown" (no verdict exists to match). No species shows no badge.

## Curator text (verbatim)

- 402 red-berried elder (Sambucus racemosa) — preparation_warnings: "Cook the berries and strain out the seeds — raw berries and seeds are toxic."
- 25 boneset (Symphytum officinale) — preparation_warnings: "Good medicine as tea or tincture, but not for prolonged use — it can harm the liver."

## Rows

| group | chunk | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after | culinary |
|---|---|---|---|---|---|---|---|
| toxic/toxic | 16 | 318 | Caucasian Comfrey (Symphytum caucasicum) | caution/none/1/human | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 15 | 762 | Common Cow wheat (Melampyrum pratense) | inedible/none/1/human | toxic/toxic/1/human | ✗ not edible → ☠ toxic | blocked |
| toxic/toxic | 12 | 22 | David’s-harp (Polygonatum multiflorum) | edible/none/0/None | toxic/toxic/1/human | ✓ edible → ☠ toxic | **newly hidden** |
| toxic/toxic | 14 | 48 | Myrtle (Vinca minor) | caution/none/0/unlocked_for_review | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 15 | 670 | Polygonatum odoratum | caution/none/1/human | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 12 | 542 | Rhamnus cathartica | inedible/none/0/pfaf | toxic/toxic/1/human | ✗ not edible → ☠ toxic | blocked |
| inedible/none | 12 | 696 | Alpen Kreuzblume (Polygala alpestris) | edible/none/0/None | inedible/none/1/human | ✓ edible → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 97 | Aspen (Populus tremula) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 13 | 689 | Bridewort (Spiraea salicifolia) | caution/none/1/multi-source-tier-a | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 15 | 585 | Genista tinctoria | caution/none/1/human | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 13 | 409 | Goat willow (Salix caprea) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 679 | hard shield fern (Polystichum aculeatum) | caution/none/1/multi-source-tier-a | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 221 | Milkwort (Polygala vulgaris) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 385 | Mountain pyrola (Pyrola minor) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 633 | Populus nigra | caution/none/1/multi-source-tier-a | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 12 | 504 | quaking aspen (Populus tremuloides) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 13 | 432 | white willow (Salix alba) | caution/none/0/None | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| inedible/none | 15 | 188 | Winged Broom (Genista sagittalis) | caution/none/1/human | inedible/none/1/human | ⚠ caution → ✗ not edible | **newly hidden** |
| caution → edible/none | 15 | 273 | annual fleabane (Erigeron annuus) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 69 | Birdseye Speedwell (Veronica chamaedrys) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 599 | Bramble Vetch (Vicia tenuifolia) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 102 | Bush Vetch (Vicia sepium) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 15 | 27 | Calycine Hawthorn (Crataegus rhipidophylla) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 372 | Cow Vetch (Vicia cracca) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 15 | 159 | Druce's Crane's-bill (Geranium × oxonianum) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 12 | 473 | Durand Oak (Quercus sinuata) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 617 | Great Burnet (Sanguisorba officinalis) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 73 | Green dock (Rumex conglomeratus) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 15 | 190 | Hairy lady's mantle (Alchemilla monticola) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 347 | Hedge Mustard (Sisymbrium officinale) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 15 | 168 | Hedgerow Geranium (Geranium pyrenaicum) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 68 | Lilac (Syringa vulgaris) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 12 | 508 | Monterey pine (Pinus radiata) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 666 | Mountain Dock (Rumex arifolius) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 15 | 212 | Sour cherry (Prunus cerasus) | caution/none/1/human | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 384 | Speedwell (Veronica officinalis) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 12 | 622 | Tormentil (Potentilla erecta) | caution/none/1/multi-source-tier-a | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 14 | 262 | Tower Mustard (Turritis glabra) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 406 | white stonecrop (Sedum album) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution → edible/none | 13 | 383 | Wood Sage (Teucrium scorodonia) | caution/none/0/None | edible/none/1/human | ⚠ caution → ✓ edible | shown |
| caution/none + text | 16 | 25 | boneset (Symphytum officinale) | caution/none/1/human | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| caution/none + text | 13 | 402 | red-berried elder (Sambucus racemosa) | edible/none/0/None | caution/none/1/human | ✓ edible → ⚠ caution | shown |
| DEFAULT keep + verify | 12 | 641 | Alpine currant (Ribes alpinum) | edible/none/0/pfaf | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 476 | Armenian Blackberry (Rubus armeniacus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 573 | Basswood (Tilia americana) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 625 | Betony (Stachys officinalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 62 | Bicolor oak (Quercus bicolor) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 315 | bilberry (Vaccinium myrtillus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 437 | bird cherry (Prunus padus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 388 | Black oak (Quercus velutina) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 26 | black raspberry (Rubus occidentalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 305 | broad-leaved dock (Rumex obtusifolius) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 298 | Burnet Rose (Rosa spinosissima) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 353 | Canada goldenrod (Solidago canadensis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 169 | Catchfly (Silene × hampeana) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 16 | common chickweed (Stellaria media) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 530 | common dandelions (Taraxacum sect. Taraxacum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 121 | common dog-violet (Viola riviniana) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 520 | Common Sorrel (Rumex acetosa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 350 | common sowthistle (Sonchus oleraceus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 213 | Creeping thyme (Thymus praecox) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 258 | curled dock (Rumex crispus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 294 | dark mullein (Verbascum nigrum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 552 | David’s elm (Ulmus davidiana) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 100 | Dog Rose (Rosa canina) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 99 | Eglantine (Rosa rubiginosa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 10 | European plum (Prunus domestica) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 395 | Feverfew (Tanacetum parthenium) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 513 | field penny-cress (Thlaspi arvense) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 297 | Field Rose (Rosa arvensis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 277 | Glaucous Dog Rose (Rosa dumalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 319 | Grateful Bramble (Rubus gratus) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 18 | great yellowcress (Rorippa amphibia) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 407 | greater stitchwort (Rabelera holostea) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 300 | Hairy tare (Vicia hirsuta) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 371 | Heal-all (Prunella vulgaris) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 296 | hedge woundwort (Stachys sylvatica) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 528 | hop trefoil (Trifolium campestre) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 203 | Horned Dandelion (Taraxacum ceratophorum) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 475 | Kievan nettle (Urtica kioviensis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 63 | Lamb's lettuce (Valeriana locusta) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 237 | Marmot plum (Prunus cerasifera) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 239 | Mediterranean Creeping Thyme (Thymus longicaulis) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 419 | Mexican-bamboo (Reynoutria japonica) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 128 | Orange Mullein (Verbascum phlomoides) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 20 | oxlip (Primula elatior) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 95 | Plantain (Plantago major) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 539 | Pleurotus ostreatus | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 61 | Plymouth pear (Pyrus cordata) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 545 | Prunus syriaca | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 209 | Purple Lettuce (Prenanthes purpurea) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 217 | Ragged Robin (Silene pendula) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 536 | Rambler rose (Rosa multiflora) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 90 | Red Campion (Silene dioica) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 226 | Red Clover (Trifolium medium) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 175 | Red clover (Trifolium pratense) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 166 | red sorrel (Rumex acetosella) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 324 | Red-cracking Bolete (Xerocomellus chrysenteron) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 96 | Ribwort (Plantago lanceolata) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 549 | Roseus Sorrel (Rumex thyrsoides) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 325 | Rowan (Sorbus aucuparia) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 328 | Rubus scaber | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 171 | Rugosa rose (Rosa rugosa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 174 | Sage (Salvia officinalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 199 | Salad Burnet (Sanguisorba minor) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 242 | Silver Plantain (Plantago argentea) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 532 | Small-leaved Lime (Tilia cordata) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 396 | Smallflower sweetbrier (Rosa micrantha) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 550 | Snowball (Viburnum trilobum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 207 | Sowthistle (Sonchus arvensis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 59 | Spade Vine (Stellaria apetala) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 327 | spiny sowthistle (Sonchus asper) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 289 | Stone Pine (Pinus pinea) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 163 | Taraxacum clemens | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 101 | Tare (Vicia sativa) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 60 | Valerian (Valeriana officinalis) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 301 | white campion (Silene latifolia) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 487 | White Clover (Trifolium repens) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 165 | wild thyme (Thymus serpyllum) | edible/none/1/auto | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 13 | 348 | Wood Dock (Rumex sanguineus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 645 | Wood Vetch (Vicia sylvatica) | edible/none/0/pfaf | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 14 | 23 | Wych Elm (Ulmus glabra) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| DEFAULT keep + verify | 12 | 391 | Инек-караа (Ribes nigrum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |

Names in the Rows table are as they appeared in the chunk files (before the 2 renames).
Grid badge = `safety_decision()` label, else the grid's verdict badge (✓ edible / ✗ not edible).
