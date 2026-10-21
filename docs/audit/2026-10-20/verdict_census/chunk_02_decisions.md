# Verdict census — chunk_02 decisions (Melvin, 21 Oct 2026)

Applied 21 Oct 2026. 45 species through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunk_02"; severity through `severity_for_verdict` with the requested severity (the Review severity path). The status endpoint (AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_143122.sqlite` (quick_check ok; no commit). No job, scan or background process was running.
- Verdict history: `species_edibility_history` ids **504–657** (154 rows): edibility_status 45, edibility_verified 41, edibility_verified_by 42, toxicity_severity 26. Read back by id: 0 mismatches.
- Curator text (species-page field path, changed_by='human', word for word; read back byte-identical): `culinary_info_history` ids **3344–3346**.
  - 793 *Abies nordmanniana* edible_parts (was PFAF "None known"): "Young spring tips raw, in syrup or vinegar; needles as tea."
  - 793 *Abies nordmanniana* look_alike_warnings (was empty): "Don't confuse with yew (deadly): yew needles are plain pale green underneath with no white stripes, and it has red berries."
  - 817 *Agaricus campestris* look_alike_warnings (was empty): "Gills pink, then chocolate-brown — never white like the deadly Amanitas. Yellow stainer: bruises chrome yellow at the stem base and smells of ink; it makes people ill."
- 817 is caution with **no** preparation_warnings (Melvin's decision): its served caution warning is empty. The look-alike text shows on the map pop-up (cut at 120 chars until batch 6) and the species page, not on the walk stop card — added to batch 6 scope in REPORT.md section 9.
- Verdict drafts #3240–#3251 and #3253 rejected through the verdict-draft reject path with reason "superseded by Melvin census verdict" (new optional reason, stored in generation_context_json as rejected_reason / rejected_at). #3252 (*Amaranthus hybridus*, not in chunk_02) left pending.
- #1685 (*Clitocybe nebularis*, rejected in chunk_01) back-filled with reason "Melvin 21 Oct census chunk_01: confirmed toxic" (same helper, status unchanged).
- Culinary content newly shown (8, none newly hidden; no approved recipes on any): Sneezewort, Agrimony and Common Amaranth (PFAF edible parts); Caucasian fir (the curator edible_parts above); Fragrant Agrimony, *Alchemilla subcrenata*, Orange peel fungus and Meadow Mushroom (no culinary text yet).

| group | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after | culinary |
|---|---|---|---|---|---|---|
| A toxic as-is | 304 | bird's-foot trefoil (Lotus corniculatus) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 12 | common bracken (Pteridium aquilinum) | toxic/toxic/1/safety_constant | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 310 | Dwarf Elder (Sambucus ebulus) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 123 | fig buttercup (Ranunculus ficaria) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 185 | Garden Lupin (Lupinus polyphyllus) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 246 | Holly (Ilex aquifolium) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 662 | Large White Buttercup (Ranunculus platanifolius) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 620 | Meadow rue (Thalictrum aquilegiifolium) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 676 | Ranunculus gouanii | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 397 | Rhododendron (Rhododendron ponticum) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 629 | Rough Comfrey (Symphytum asperum) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 509 | Sulphur Tuft (Hypholoma fasciculare) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 581 | White Corsage (Rhododendron formosanum) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 610 | White Crowfoot (Ranunculus aconitifolius) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 719 | Wood Ragwort (Senecio ovatus) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| A toxic as-is | 389 | Yellow Flag (Iris pseudacorus) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| B → toxic/deadly | 782 | Aconite (Aconitum plicatum) | unknown/unknown/0/None | toxic/deadly/1/human | ⚠ toxicity unknown → ☠ deadly | blocked |
| B → toxic/deadly | 773 | Desert rose (Adenium obesum) | unknown/unknown/0/None | toxic/deadly/1/human | ⚠ toxicity unknown → ☠ deadly | blocked |
| B → toxic/deadly | 750 | Manchurian monkshood (Aconitum variegatum) | unknown/unknown/0/None | toxic/deadly/1/human | ⚠ toxicity unknown → ☠ deadly | blocked |
| B → toxic/toxic | 24 | European yellowrattle (Rhinanthus alectorolophus) | inedible/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| B → toxic/toxic | 418 | Hyacinthoides (Hyacinthoides × massartiana) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| B → toxic/toxic | 484 | jewelled amanita (Amanita junquillea) | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| B → toxic/toxic | 490 | Yellow Rattle (Rhinanthus minor) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic | blocked |
| B → inedible/none | 331 | common bonnet (Mycena galericulata) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 51 | False Ivy-leaf Speedwell (Veronica sublobata) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 478 | felt lichen (Peltigera praetextata) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 797 | Green alder (Alnus alnobetula) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| B → inedible/none | 316 | hairy curtain crust (Stereum hirsutum) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 401 | Lyell's Bristle-moss (Pulvigera lyellii) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 412 | Mountain fern (Thelypteris limbosperma) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 139 | New York aster (Symphyotrichum novi-belgii) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 458 | Peppery Milkcap (Lactifluus piperatus) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 332 | Physarum cinereum | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 507 | Pluteus romellii | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 321 | red edge brittlestem (Psathyrella corrugis) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 481 | Spanish moss (Tillandsia usneoides) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → inedible/none | 493 | Tubaria furfuracea | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible | blocked |
| B → edible/none | 715 | Agrimony (Agrimonia eupatoria) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 592 | Alchemilla subcrenata | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 793 | Caucasian fir (Abies nordmanniana) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 844 | Common Amaranth (Amaranthus retroflexus) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 716 | Fragant Agrimony (Agrimonia procera) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 842 | Orange peel fungus (Aleuria aurantia) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → edible/none | 730 | Sneezewort (Achillea ptarmica) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| B → caution/none | 817 | Meadow Mushroom (Agaricus campestris) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |

Grid badge = `safety_decision()` label, else the grid's verdict badge (✓ edible / ✗ not edible).
