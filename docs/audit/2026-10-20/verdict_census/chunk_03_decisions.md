# Verdict census — chunk_03 decisions (Melvin, 21 Oct 2026)

Applied 21 Oct 2026. 45 species through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunk_03"; severity through `severity_for_verdict` with the requested severity. The status endpoint (AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_144853.sqlite` (quick_check ok; no commit). No job, scan or background process was running.
- Verdict history: `species_edibility_history` ids **658–837** (180 rows: edibility_status, edibility_verified, edibility_verified_by, toxicity_severity — 45 each). Read back by id: 0 mismatches.
- Curator text (species-page field path, changed_by='human', word for word; read back byte-identical, row and history): `culinary_info_history` ids **3347–3354**.
  - 761 *Angelica sylvestris* preparation_warnings replaced PFAF text ("All members of this genus contain furocoumarins…", kept as old_value in history 3347).
  - 495, 832, 829 preparation_warnings and all four look_alike_warnings were empty (old_value NULL).
- 644 *Blitum bonus-henricus* common name (species-page common-names editor, `PATCH /api/species/{name}/common-names`, human; history **3355**): preferred "Fat hen" → "Good King Henry"; EN names ["Fat hen", "Good King Henry", "Allgood"] → ["Good King Henry", "Allgood"] (Melvin: drop "Fat hen" — it is *Chenopodium album*'s name); DE names unchanged.
- 44 pending verdict drafts on these species (#3256–#3309, all `verdict_sweep`) rejected with reason "superseded by Melvin census verdict". 796 *Ampulloclitocybe clavipes* had none. Other drafts on these species unchanged (35 pending, 14 invalidated, 1 approved before and after).
- Caution warnings now served (`safety_decision`): 761, 495, 832, 829 → "⚠ caution" + their preparation_warnings text, so map, walk, species page, Lists, print, PDF and Export summary all show the reason.
- Culinary content newly shown: 26 species (none newly hidden; no approved recipes or taste notes on any). Edible-parts text now shows for 9: *Anaphalis margaritacea*, *Angelica sylvestris*, *Barbarea verna*, *Chenopodium album*, *Chenopodium pratericola*, *Chrysosplenium oppositifolium*, *Cichorium endivia*, *Cichorium intybus*, *Cirsium hookerianum*. The other 17 have no culinary text yet.

## Curator text (verbatim)

- 761 *Angelica sylvestris* — preparation_warnings: "Wear gloves — the sap is phototoxic and burns skin in sunlight."
- 761 *Angelica sylvestris* — look_alike_warnings: "Look-alikes: giant hogweed (its sap burns too) and deadly hemlock (purple-blotched stem, mousy smell). Only pick with certain identification."
- 495 *Apioperdon pyriforme* — preparation_warnings: "Cut through the middle — only the ones that are fully white are edible."
- 495 *Apioperdon pyriforme* — look_alike_warnings: "An Amanita 'egg' shows the outline of a cap and gills inside (deadly); earthballs are purple-black inside (toxic)."
- 832 *Armillaria cepistipes* — preparation_warnings: "Toxic when raw — ensure it's thoroughly cooked. Can cause a reaction in some people; try a small amount first."
- 832 *Armillaria cepistipes* — look_alike_warnings: "Deadly funeral bell (Galerina) grows in the same places — brown spore print, where honey fungus is white. Sulphur tuft (toxic) has greenish-yellow gills."
- 829 *Armillaria ostoyae* — preparation_warnings: "Toxic when raw — ensure it's thoroughly cooked. Can cause a reaction in some people; try a small amount first."
- 829 *Armillaria ostoyae* — look_alike_warnings: "Deadly funeral bell (Galerina) grows in the same places — brown spore print, where honey fungus is white. Sulphur tuft (toxic) has greenish-yellow gills."

## Rows

| group | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after | culinary |
|---|---|---|---|---|---|---|
| toxic/toxic | 483 | Aquilegia dumeticola | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 652 | Chaerophyllum villarsii | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 796 | Club Foot (Ampulloclitocybe clavipes) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 354 | crocus (Crocus) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 757 | Crownvetch (Coronilla varia) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| inedible/none | 656 | Alpine chickweed (Cerastium alpinum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 660 | Alpine Thistle (Carduus defloratus) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 650 | Anthriscus nitida | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 631 | Arceuthobium douglasii | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 770 | Bell heather (Erica cinerea) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 748 | broadleaf enchanter's nightshade (Circaea lutetiana) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 697 | Broadleaf helleborine (Epipactis helleborine) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 602 | Brown knapweed (Centaurea jacea) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 779 | Dwarf Thistle (Cirsium acaulon) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 642 | Meadow Thistle (Cirsium dissectum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 741 | Small teasel (Dipsacus pilosus) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 777 | Stinking aposeris (Aposeris foetida) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 623 | Thistle (Carduus personata) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 830 | Trooping Crumble Cap (Coprinellus disseminatus) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| edible/none | 827 | American Winter Cress (Barbarea verna) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 778 | Bearded bellflower (Campanula barbata) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 788 | chicory (Cichorium intybus) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 847 | Clinopodium nepeta | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 455 | common bistort (Bistorta officinalis) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 724 | Crepis micrantha | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 765 | Desert Goosefoot (Chenopodium pratericola) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 606 | Dianthus carthusianorum | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 738 | Endive (Cichorium endivia) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 644 | Good King Henry (Blitum bonus-henricus) — was "Fat hen" | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 613 | Golden hawk's beard (Crepis aurea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 731 | Hawk's beard (Crepis pulchra) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 727 | Lambs quarters (Chenopodium album) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 780 | Marsh hawk's beard (Crepis paludosa) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 663 | Mugwort (Artemisia verlotiorum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 733 | Opposite leaved Golden Saxifrage (Chrysosplenium oppositifolium) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 699 | Pearly Everlasting (Anaphalis margaritacea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 659 | Rock thyme (Clinopodium alpinum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 723 | smooth hawksbeard (Crepis capillaris) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 661 | Spiniest Thistle (Cirsium spinosissimum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 824 | white thistle (Cirsium hookerianum) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 687 | Willowherb (Epilobium montanum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| caution/none + text | 829 | Honey Mushroom (Armillaria ostoyae) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 832 | mullet honey fungus (Armillaria cepistipes) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 495 | Pear-shaped Puffball (Apioperdon pyriforme) | None/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 761 | Wild angelica (Angelica sylvestris) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |

Grid badge = `safety_decision()` label, else the grid's verdict badge (✓ edible / ✗ not edible).
