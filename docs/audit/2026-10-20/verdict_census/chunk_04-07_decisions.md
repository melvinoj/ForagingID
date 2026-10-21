# Verdict census — chunks 04–07 decisions (Melvin, 21 Oct 2026)

Applied 21 Oct 2026. 138 chunk rows = 135 written + 467 *Amanita rubescens* (done earlier) + *Collybia nuda* and *Conyza canadensis* (no species card) skipped. Every verdict through `edibility._write_verdict`, verified by human, note "Melvin 21 Oct census chunks 04–07"; severity through `severity_for_verdict` with the requested severity (the Review severity path; 840 deadly). Confirm-as-is rows kept their verdict and severity. The status endpoint (AI drafting) was not called.

- Snapshot before writing: `snapshots/db_20261021_145347.sqlite` (quick_check ok; no commit). No job, scan or background process was running.
- Verdict history: `species_edibility_history` ids **838–1357** (520 rows: edibility_status 135, edibility_verified 129, edibility_verified_by 131, toxicity_severity 125). Read back by id: 0 mismatches.
- Curator text (species-page field path, changed_by='human', word for word; byte-identical in row and history): `culinary_info_history` ids **3356–3365**. Replaced existing PFAF text in 743 edible_parts, 806 preparation_warnings, 783 preparation_warnings (old text kept as old_value); the rest were empty.
- 118 pending verdict drafts on these species (#3310–#3448, all `verdict_sweep`) rejected with reason "superseded by Melvin census verdict". Other drafts unchanged (111 pending, 114 invalidated, 33 approved before and after).
- **494 family not changed** (Melvin: deferred). It holds family Caprifoliaceae and genus Dipsacus; no route edits family/genus. Added to batch 11b scope (v) with the genus/family audit. Merges for 704→457, 758↔757, 708↔412 and the *Collybia nuda* / *Conyza canadensis* relinks are also at the top of batch 11b scope — nothing merged.
- Caution warnings served now: 494, 806, 783 show their preparation text everywhere. **816, 821, 820 (*Macrolepiota*) and 711 (*Marasmius oreades*) have a curator look-alike only**, so their served caution warning is empty — the walk card shows "⚠ caution" with no reason until batch 6 (a).
- Confirm-as-is cautions — curator-authored warning check: 106 Keck (*Anthriscus sylvestris*): look-alike curator; preparation **not** (its human history row is the marker string "(human-authored preparation_warnings)", not the text — E-14, batch 6). 590 *Pimpinella major*: look-alike curator; preparation **not** (pfaf_reparse). 603 *Pimpinella saxifraga*: look-alike curator; preparation **not** (no history). None written. All three therefore serve "⚠ caution" with no warning text.
- **Culinary content newly hidden (5):** 230 Columbine (*Aquilegia vulgaris*, edible → toxic): edible parts, taste notes and approved recipe #63 "Aquilegia Vulgaris Salad with Whipped Labneh, Cucumber Water, and Toasted Dukkah" (ai_generated); 280 marsh marigold (*Caltha palustris*, edible → toxic): edible parts and approved recipe #66 "Marsh Marigold — Pickled Buds with Slow-Cooked Greens, Brown Butter, and Toasted Hazelnuts" (ai_generated); 492 cutleaf waterparsnip (*Berula erecta*, caution → toxic): edible parts; 124 Blackish Columbine (*Aquilegia nigricans*) and 503 False Death-cap (*Amanita citrina*) (caution → toxic): no culinary text.
- **Culinary content newly shown (50):** edible-parts text now shows for 21 (*Oxalis triangularis*, *Solidago virgaurea*, *Malva verticillata*, *Tragopogon pratensis*, *Tragopogon dubius*, *Medicago sativa*, *Verbena officinalis*, *Lathyrus linifolius*, *Nymphoides peltata*, *Mycelis muralis*, *Potentilla nepalensis*, *Oxalis stricta*, *Melilotus officinalis*, *Vaccinium uliginosum*, *Larix lyallii*, *Vaccinium vitis-idaea*, *Pinus cembra*, *Juniperus communis*, *Rumex alpinus*, *Oenothera biennis*, *Filipendula vulgaris*); the other 29 have no culinary text yet. No taste notes or approved recipes on any newly shown species.

## Curator text (verbatim)

- 743 Bitter Vetch (Lathyrus linifolius) — edible_parts: "Tubers only; not the seeds."
- 494 common puffball (Lycoperdon perlatum) — preparation_warnings: "Cut through the middle — only the ones that are fully white are edible."
- 494 common puffball (Lycoperdon perlatum) — look_alike_warnings: "An Amanita 'egg' shows the outline of a cap and gills inside (deadly); earthballs are purple-black inside (toxic)."
- 806 Common juniper (Juniperus communis) — preparation_warnings: "Ripe blue-black berries as a spice, a few at a time — not in pregnancy."
- 806 Common juniper (Juniperus communis) — look_alike_warnings: "Savin juniper (toxic) has soft scale-like leaves and smells unpleasant when crushed; common juniper has sharp needles in threes."
- 816 Frayed Parasol (Macrolepiota excoriata) — look_alike_warnings: "Deadly small Lepiotas look similar — be certain of the movable ring and cap size; if in doubt, leave it."
- 821 Macrolepiota mastoidea — look_alike_warnings: "Deadly small Lepiotas look similar — be certain of the movable ring and cap size; if in doubt, leave it."
- 820 Macrolepiota rhodosperma — look_alike_warnings: "Deadly small Lepiotas look similar — be certain of the movable ring and cap size; if in doubt, leave it."
- 711 Marasmius oreades — look_alike_warnings: "Deadly look-alike: fool's funnel grows in the same rings — white, crowded gills running down the stem. Fairy ring champignon has widely spaced gills and a tough, bendy stem."
- 783 Sweetclover (Melilotus officinalis) — preparation_warnings: "Use fresh or well dried; mouldy or fermented sweet clover is toxic (thins the blood)."

## Rows

| group | chunk | id | Common name (Latin) | before (status/severity/verified/by) | after | grid badge before → after | culinary |
|---|---|---|---|---|---|---|---|
| toxic/deadly | 05 | 840 | Paxillus involutus | None/unknown/0/None | toxic/deadly/1/human | ⚠ toxicity unknown → ☠ deadly | blocked |
| toxic/toxic | 06 | 801 | Alpenrose (Rhododendron ferrugineum) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 597 | Balkan Spurge (Euphorbia stricta) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 06 | 124 | Blackish Columbine (Aquilegia nigricans) | caution/none/0/unlocked_for_review | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 06 | 230 | Columbine (Aquilegia vulgaris) | edible/none/0/None | toxic/toxic/1/human | ✓ edible → ☠ toxic | **newly hidden** |
| toxic/toxic | 06 | 758 | Crownvetch (Securigera varia) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 06 | 492 | cutleaf waterparsnip (Berula erecta) | caution/none/0/None | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 05 | 805 | Dwarf buckthorn (Rhamnus pumila) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 06 | 503 | False Death-cap (Amanita citrina) | caution/none/1/multi-source-tier-a | toxic/toxic/1/human | ⚠ caution → ☠ toxic | **newly hidden** |
| toxic/toxic | 04 | 843 | flowering spurge (Euphorbia corollata) | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 767 | Hoary Ragwort (Jacobaea erucifolia) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 643 | Honeysuckle (Lonicera xylosteum) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 541 | Lactarius torminosus | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 798 | Large flowered Hemp-nettle (Galeopsis speciosa) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 06 | 280 | marsh marigold (Caltha palustris) | edible/none/0/None | toxic/toxic/1/human | ✓ edible → ☠ toxic | **newly hidden** |
| toxic/toxic | 05 | 624 | Red rattle (Pedicularis palustris) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 05 | 686 | Rhododendron albiflorum | None/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 05 | 722 | Small Cow wheat (Melampyrum sylvaticum) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 04 | 818 | White Dapperling (Leucocoprinus leucothites) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 05 | 720 | Whorled Solomon's seal (Polygonatum verticillatum) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| toxic/toxic | 05 | 787 | Wood Cow wheat (Melampyrum nemorosum) | unknown/unknown/0/None | toxic/toxic/1/human | ⚠ toxicity unknown → ☠ toxic | blocked |
| inedible/none | 04 | 657 | Alpine balsam (Erinus alpinus) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 811 | Alpine Eyebright (Euphrasia alpina) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 814 | Alpine Snowbell (Soldanella alpina) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 849 | artist's bracket (Ganoderma applanatum) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 714 | Atlas Poppy (Papaver atlanticum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 769 | Bank Haircap Moss (Polytrichum formosum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 846 | Barclay's willow (Salix barclayi) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 635 | Bedstraw (Galium intermedium) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 511 | Brittle Cinder (Kretzschmaria deusta) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 718 | Butter and-eggs (Linaria vulgaris) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 742 | Carolina poplar (Populus × canadensis) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 828 | conical brittlestem (Parasola conopilea) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 809 | Conifer Mazegill (Gloeophyllum sepiarium) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 678 | dark-leaved willow (Salix myrsinifolia) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 547 | Dutch elm (Ulmus × hollandica) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 795 | Eared willow (Salix aurita) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 850 | Gentiana brachyphylla | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 519 | Golden Pholiota (Pholiota aurivella) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 781 | Grass of Parnassus (Parnassia palustris) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 680 | Great wood rush (Luzula sylvatica) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 698 | Greater butterfly orchid (Platanthera chlorantha) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 834 | Gypsywort (Lycopus europaeus) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 703 | Heath cudweed (Omalotheca sylvatica) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 671 | Helianthus silphioides | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 626 | Hieracium lachenalii | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 771 | Horn Calcareous Moss (Mnium hornum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 669 | Jasione montana | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 708 | lemon-scented fern (Oreopteris limbosperma) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 668 | Leucanthemum adustum | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 540 | Lichenomphalia umbellifera | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 577 | London Plane (Platanus × hispanica) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 500 | membraneous felt lichen (Peltigera membranacea) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 616 | Nettle leaf speedwell (Veronica urticifolia) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 728 | Nettle leaved Mullein (Verbascum chaixii) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 734 | Oreomecon crocea | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 705 | Parmotrema perlatum | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 831 | Pleuroflammula tuberculosa | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 496 | Plums-and-Custard (Tricholomopsis rutilans) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 498 | Pompon Mustard-rosette (Pyxine albovirens) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 837 | princess tree (Paulownia tomentosa) | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 292 | Psilocybe semilanceata | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 813 | Purple Coltsfoot (Homogyne alpina) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 725 | Purple loosestrife (Lythrum virgatum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 563 | Purple Toadflax (Linaria purpurea) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 621 | Ragged robin (Silene flos-cuculi) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 05 | 841 | Ramaria stricta | None/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 614 | Round leaf saxifrage (Saxifraga rotundifolia) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 675 | Round leaved bedstraw (Galium rotundifolium) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 726 | Scentless Mayweed (Tripleurospermum inodorum) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 655 | Sheepsbit (Jasione laevis) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 789 | Spring gentian (Gentiana verna) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 586 | Tall fleabane (Erigeron sumatrensis) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 06 | 535 | Thyme speedwell (Veronica serpyllifolia) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| inedible/none | 04 | 712 | Wood scabious (Knautia dipsacifolia) | unknown/unknown/0/None | inedible/none/1/human | ⚠ toxicity unknown → ✗ not edible | blocked |
| edible/none | 05 | 736 | Alfalfa (Medicago sativa) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 743 | Bitter Vetch (Lathyrus linifolius) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 790 | Bog bilberry (Vaccinium uliginosum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 674 | Bramble (Rubus pruinosus) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 604 | Brambles (Rubus canescens) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 664 | Catmint (Nepeta racemosa) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 717 | Cluster mallow (Malva verticillata) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 735 | common salsify (Tragopogon dubius) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 737 | Common vervain (Verbena officinalis) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 799 | Cowberry (Vaccinium vitis-idaea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 557 | Devony Oak (Quercus × rosacea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 848 | dropwort (Filipendula vulgaris) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 694 | Eltrot (Heracleum sibiricum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 823 | Evening primrose (Oenothera biennis) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 692 | Evening primrose (Oenothera parviflora) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 658 | Globe headed Rampion (Phyteuma hemisphaericum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 732 | Goat's beard (Tragopogon pratensis) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 713 | Goldenrod (Solidago virgaurea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 546 | grassy tarweed (Madia gracilis) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 768 | Herb Robert (Geranium robertianum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 681 | mock strawberry (Potentilla indica) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 812 | Monk's rhubarb (Rumex alpinus) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 800 | Mountain pansy (Viola lutea) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 756 | Nepalese cinquefoil (Potentilla nepalensis) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 747 | Nymphoides peltata | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 746 | Oenothera × fallax | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 707 | Oxalis triangularis | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 632 | Picea obovata | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 704 | Polyporus versicolor | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 819 | Rock dandelion (Taraxacum erythrospermum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 739 | Sand Lucerne (Medicago × varia) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 836 | Shaggy soldier (Galinsoga quadriradiata) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 822 | smooth cat's ear (Hypochaeris glabra) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 839 | Spotted dead nettle (Lamium maculatum) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 786 | Stag's horn Sumac (Rhus typhina) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 804 | Sticky Bolete (Suillus viscidus) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 04 | 791 | Subalpine larch (Larix lyallii) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 706 | Suillus grevillei | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 802 | Swiss pine (Pinus cembra) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 845 | Taraxacum campylodes | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 749 | wall lettuce (Mycelis muralis) | None/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 06 | 640 | Yellow Fieldcress (Rorippa sylvestris) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| edible/none | 05 | 759 | Yellow wood sorrel (Oxalis stricta) | unknown/unknown/0/None | edible/none/1/human | ⚠ toxicity unknown → ✓ edible | newly shown |
| caution/none + text | 04 | 806 | Common juniper (Juniperus communis) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 04 | 494 | common puffball (Lycoperdon perlatum) | None/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 04 | 816 | Frayed Parasol (Macrolepiota excoriata) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 04 | 821 | Macrolepiota mastoidea | None/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 04 | 820 | Macrolepiota rhodosperma | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 05 | 711 | Marasmius oreades | None/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| caution/none + text | 05 | 783 | Sweetclover (Melilotus officinalis) | unknown/unknown/0/None | caution/none/1/human | ⚠ toxicity unknown → ⚠ caution | newly shown |
| confirm as-is | 06 | 75 | European Parsley (Helosciadium nodiflorum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 06 | 178 | Goutweed (Aegopodium podagraria) | edible/none/1/human | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 07 | 590 | Greater Burnet saxifrage (Pimpinella major) | caution/none/1/human | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| confirm as-is | 06 | 144 | Hogweed (Heracleum sphondylium) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 06 | 106 | Keck (Anthriscus sylvestris) | caution/none/1/human | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| confirm as-is | 06 | 87 | Pignut (Conopodium majus) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 07 | 603 | Pimpinella (Pimpinella saxifraga) | caution/none/1/multi-source-tier-a | caution/none/1/human | ⚠ caution → ⚠ caution | shown |
| confirm as-is | 06 | 373 | Spignel (Meum athamanticum) | edible/none/0/None | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 07 | 521 | sweet cicely (Myrrhis odorata) | edible/none/0/unlocked_for_review | edible/none/1/human | ✓ edible → ✓ edible | shown |
| confirm as-is | 06 | 9 | Wild Carrot (Daucus carota) | edible/none/1/human | edible/none/1/human | ✓ edible → ✓ edible | shown |

Skipped: 467 *Amanita rubescens* (done 21 Oct morning); *Collybia nuda*, *Conyza canadensis* (no species card — batch 11b relink).

Grid badge = `safety_decision()` label, else the grid's verdict badge (✓ edible / ✗ not edible).
