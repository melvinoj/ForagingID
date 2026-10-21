# Verdict census — chunk_01 decisions (Melvin, 21 Oct 2026)

Applied 21 Oct 2026. 45 species, each through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunk_01". Severity via `severity_for_verdict` with the requested severity — the same path the Review severity select uses (`POST /api/edibility/verdict-drafts/{id}/approve` → `_write_verdict(..., severity_req, note)`). The status endpoint (which starts AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_141729.sqlite` (quick_check ok; no commit).
- History: `species_edibility_history` ids **382–503** (122 rows): edibility_status 45, edibility_verified 30, edibility_verified_by 30, toxicity_severity 17. Read back by id: 0 mismatches.
- Verdict draft #1685 (*Clitocybe nebularis*, old fungi lookup draft, status=unknown) **rejected** via the AI-draft reject path (`POST /api/species/{name}/drafts/edibility_status/reject`); the batch-3b verdict-draft reject path refuses it (not a 3b draft).
- 137 *Astrantia major* was toxic/toxic, not inedible; relaxed to inedible/none on Melvin's explicit confirmation (21 Oct).
- Culinary content: no species gained or lost culinary content — every row was blocked before and is blocked after (toxic/deadly, or inedible under the 21 Oct rule).

| group | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after |
|---|---|---|---|---|---|
| A deadly as-is | 522 | Aconite (Aconitum napellus) | toxic/deadly/0/unlocked_for_review | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 356 | common yew (Taxus baccata) | toxic/deadly/0/unlocked_for_review | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 763 | Deadly Nightshade (Atropa bella-donna) | toxic/deadly/1/human | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 131 | Dungwort (Helleborus foetidus) | toxic/deadly/0/unlocked_for_review | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 130 | poison hemlock (Conium maculatum) | toxic/deadly/0/unlocked_for_review | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 609 | White hellebore (Veratrum album) | toxic/deadly/0/None | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A deadly as-is | 630 | Wolfsbane (Aconitum lycoctonum) | toxic/deadly/1/human | toxic/deadly/1/human | ☠ deadly → ☠ deadly |
| A toxic as-is | 628 | Alder Buckthorn (Frangula alnus) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 690 | Blue devil (Echium vulgare) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 408 | Bluebell (Hyacinthoides non-scripta) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 136 | Bryonia syriaca | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 636 | Bugbane (Actaea spicata) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 499 | Cloudy Clitocybe (Clitocybe nebularis) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 745 | Common Ivy (Hedera helix) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 155 | Fly agaric (Amanita muscaria) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 191 | Golden Chervil (Chaerophyllum aureum) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 57 | Hairy chervil (Chaerophyllum hirsutum) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 215 | Hemp-nettle (Galeopsis tetrahit) | toxic/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 688 | Hogweed (Heracleum mantegazzianum) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 58 | Male fern (Dryopteris filix-mas) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 524 | Mountain arnica (Arnica montana) | toxic/toxic/0/None | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| A toxic as-is | 2 | rough chervil (Chaerophyllum temulum) | toxic/toxic/1/human | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/deadly | 376 | Foxglove (Digitalis purpurea) | toxic/toxic/1/human | toxic/deadly/1/human | ☠ toxic → ☠ deadly |
| B → toxic/toxic | 362 | Adenostyles (Adenostyles alliariae) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/toxic | 67 | Cypress spurge (Euphorbia cyparissias) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/toxic | 206 | Petty spurge (Euphorbia peplus) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/toxic | 386 | Pyrenean columbine (Aquilegia pyrenaica) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/toxic | 430 | Scaly male fern (Dryopteris affinis) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → toxic/toxic | 127 | wood anemone (Anemonoides nemorosa) | inedible/toxic/0/unlocked_for_review | toxic/toxic/1/human | ☠ toxic → ☠ toxic |
| B → inedible/none | 234 | Black alder (Alnus glutinosa) | inedible/toxic/1/human | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 138 | bur chervil (Anthriscus caucalis) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 200 | Ciulin (Cirsium ferox) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 320 | Common spotted orchid (Dactylorhiza fuchsii) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 589 | Dyer's Chamomile (Cota tinctoria) | inedible/toxic/1/human | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 137 | great masterwort (Astrantia major) | toxic/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 338 | hare's foot inkcap (Coprinopsis lagopus) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 453 | Jelly Spot Fungus (Dacrymyces stillatus) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 330 | Jelly-antler (Calocera viscosa) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 576 | Lawson Cypress (Chamaecyparis lawsoniana) | inedible/toxic/1/human | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 533 | Orange-ball-tree (Buddleja globosa) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 224 | Purple Jellydisc (Ascocoryne sarcoides) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 14 | spotted hawkweed (Hieracium maculatum) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 204 | Teasel (Dipsacus fullonum) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 220 | Tyrol knapweed (Centaurea nigrescens) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |
| B → inedible/none | 122 | Western Marsh-orchid (Dactylorhiza majalis) | inedible/toxic/0/unlocked_for_review | inedible/none/1/human | ☠ toxic → ✗ not edible |

Grid badge = `safety_decision()` label; '✗ not edible' is the grid's verdict badge for an inedible species with no safety label.
