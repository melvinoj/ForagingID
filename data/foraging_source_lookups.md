# ForagingID — Edibility Source Lookup Tables
*Generated: 2026-06-29 — for use in multi-source edibility agreement model*
*Status: DRAFT — merge with Melvin's additional sources before building pipeline*

---

## How to use this file

Each source table maps scientific name (genus or full binomial) to:
- `url` — direct page URL (automatable if present)
- `edibility` — edible / caution / toxic / inedible / unknown
- `notes` — brief qualifier where relevant

The pipeline reads this file, matches by scientific_name (exact first, then genus fallback),
and uses agreement across sources as the approval signal.

**Confidence tiers:**
- 3+ sources agree → auto-approve (edible or inedible only — never caution)
- 2 sources agree → send to review with recommendation
- 1 source only → send to review, flag as single-source
- Conflict between sources → always send to review

---

## Source 1: eatweeds.co.uk
*Robin Harford — UK foraging reference. ~65 species. URL pattern: scientific name embedded in slug.*
*All species listed here are edible (this is a foraging guide — hemlock included as warning only).*
*Edibility verdict: edible unless noted.*

| common_name | scientific_name | url | edibility | notes |
|---|---|---|---|---|
| Alexanders | Smyrnium olusatrum | https://www.eatweeds.co.uk/alexanders-smyrnium-olusatrum | edible | |
| Amaranth | Amaranthus spp | https://www.eatweeds.co.uk/amaranth-amaranthus | edible | genus-level |
| Arrowhead | Sagittaria sagittifolia | https://www.eatweeds.co.uk/arrowhead-sagittaria-sagittifolia | edible | |
| Ash | Fraxinus excelsior | https://www.eatweeds.co.uk/ash-fraxinus-excelsior | edible | seeds/shoots/sap |
| Beech | Fagus sylvatica | https://www.eatweeds.co.uk/beech-fagus-sylvatica | edible | |
| Birch | Betula pendula | https://www.eatweeds.co.uk/silver-birch-betula-pendula | edible | |
| Black Horehound | Ballota nigra | https://www.eatweeds.co.uk/black-horehound-ballota-nigra | inedible | medicinal only |
| Black Mustard | Brassica nigra | https://www.eatweeds.co.uk/black-mustard-brassica-nigra | edible | |
| Bramble | Rubus fruticosus | https://www.eatweeds.co.uk/bramble-blackberry-rubus-fruticosus | edible | |
| Brooklime | Veronica beccabunga | https://www.eatweeds.co.uk/brooklime-veronica-beccabunga | edible | |
| Burdock | Arctium spp | https://www.eatweeds.co.uk/burdock-arctium | edible | genus-level |
| Chickweed | Stellaria media | https://www.eatweeds.co.uk/chickweed-stellaria-media | edible | |
| Cleavers | Galium aparine | https://www.eatweeds.co.uk/cleavers-galium-aparine | edible | |
| Cow Parsley | Anthriscus sylvestris | https://www.eatweeds.co.uk/cow-parsley-anthriscus-sylvestris | caution | Apiaceae — hemlock lookalike |
| Crab Apple | Malus sylvestris | https://www.eatweeds.co.uk/crab-apple-malus-sylvestris | edible | |
| Daisy | Bellis perennis | https://www.eatweeds.co.uk/daisy-bellis-perennis | edible | |
| Dandelion | Taraxacum officinale | https://www.eatweeds.co.uk/dandelion-taraxacum-officinale | edible | |
| Dock | Rumex obtusifolius | https://www.eatweeds.co.uk/dock-rumex-obtusifolius | edible | |
| Douglas Fir | Pseudotsuga menziesii | https://www.eatweeds.co.uk/douglas-fir-pseudotsuga-menziesii | edible | |
| Duke of Argyll's Teaplant | Lycium barbarum | https://www.eatweeds.co.uk/duke-argylls-teaplant-lycium-barbarum | edible | goji berries |
| Elder | Sambucus nigra | https://www.eatweeds.co.uk/elder-sambucus-nigra | edible | flowers/berries cooked |
| Elm | Ulmus glabra | https://www.eatweeds.co.uk/wych-elm-ulmus-glabra | edible | |
| Fat Hen | Chenopodium album | https://www.eatweeds.co.uk/fat-hen-chenopodium-album | edible | |
| Field Bindweed | Convolvulus arvensis | https://www.eatweeds.co.uk/field-bindweed-convolvulus-arvensis | caution | historical use only |
| Flowering Currant | Ribes sanguineum | https://www.eatweeds.co.uk/flowering-currant-ribes-sanguineum | edible | |
| Garlic Mustard | Alliaria petiolata | https://www.eatweeds.co.uk/garlic-mustard-alliaria-petiolata | edible | |
| Gorse | Ulex europaeus | https://www.eatweeds.co.uk/gorse-ulex-europaeus | edible | flowers |
| Ground Elder | Aegopodium podagraria | https://www.eatweeds.co.uk/ground-elder-aegopodium-podagraria | edible | |
| Ground Ivy | Glechoma hederacea | https://www.eatweeds.co.uk/ground-ivy-glechoma-hederacea | edible | |
| Guelder Rose | Viburnum opulus | https://www.eatweeds.co.uk/guelder-rose-viburnum-opulus | caution | berries toxic raw, ok cooked |
| Hawthorn | Crataegus monogyna | https://www.eatweeds.co.uk/hawthorn-crataegus-monogyna | edible | |
| Hazel | Corylus avellana | https://www.eatweeds.co.uk/hazel-corylus-avellana | edible | |
| Hemlock | Conium maculatum | https://www.eatweeds.co.uk/hemlock-conium-maculatum | toxic | deadly |
| Himalayan Balsam | Impatiens glandulifera | https://www.eatweeds.co.uk/himalayan-balsam | edible | seeds |
| Hogweed | Heracleum sphondylium | https://www.eatweeds.co.uk/hogweed-heracleum-sphondylium | edible | not giant hogweed |
| Horseradish | Armoracia rusticana | https://www.eatweeds.co.uk/horseradish-armoracia-rusticana | edible | |
| Japanese Pagoda Tree | Styphnolobium japonicum | https://www.eatweeds.co.uk/japanese-pagoda-tree-styphnolobium-japonicum | edible | |
| Judas Tree | Cercis siliquastrum | https://www.eatweeds.co.uk/judas-tree-cercis-siliquastrum | edible | |
| Lady's-smock | Cardamine pratensis | https://www.eatweeds.co.uk/ladys-smock-cuckooflower-cardamine-pratensis | edible | |
| Laver | Porphyra spp | https://www.eatweeds.co.uk/laver-porphyra | edible | seaweed |
| Lesser Celandine | Ficaria verna | https://www.eatweeds.co.uk/lesser-celandine-ficaria-verna | caution | toxic raw; tubers edible cooked only |
| Lime/Linden | Tilia spp | https://www.eatweeds.co.uk/lime-linden-tilia | edible | genus-level |
| Mallow | Malva sylvestris | https://www.eatweeds.co.uk/mallow-malva-sylvestris | edible | |
| Marshmallow | Althaea officinalis | https://www.eatweeds.co.uk/marshmallow-althaea-officinalis | edible | |
| Meadowsweet | Filipendula ulmaria | https://www.eatweeds.co.uk/meadowsweet-filipendula-ulmaria | edible | |
| Mugwort | Artemisia vulgaris | https://www.eatweeds.co.uk/mugwort-artemisia-vulgaris | edible | caution in pregnancy |
| Navelwort | Umbilicus rupestris | https://www.eatweeds.co.uk/navelwort-umbilicus-rupestris | edible | |
| Oak | Quercus robur | https://www.eatweeds.co.uk/oak-quercus-robur | edible | acorns processed |
| Oxeye Daisy | Leucanthemum vulgare | https://www.eatweeds.co.uk/oxeye-daisy-leucanthemum-vulgare | edible | |
| Peach-leaved Bellflower | Campanula persicifolia | https://www.eatweeds.co.uk/peach-leaved-bellflower | edible | |
| Plantain | Plantago spp | https://www.eatweeds.co.uk/ribwort-and-greater-plantain-plantago-spp | edible | genus-level |
| Primrose | Primula vulgaris | https://www.eatweeds.co.uk/primrose-primula-vulgaris | edible | |
| Purple Loosestrife | Lythrum salicaria | https://www.eatweeds.co.uk/purple-loosestrife-lythrum-salicaria | edible | young shoots |
| Red Campion | Silene dioica | https://www.eatweeds.co.uk/red-campion-silene-dioica | edible | |
| Rock Samphire | Crithmum maritimum | https://www.eatweeds.co.uk/rock-samphire-crithmum-maritimum | edible | |
| Rosebay Willowherb | Epilobium angustifolium | https://www.eatweeds.co.uk/rosebay-willowherb-epilobium-angustifolium | edible | |
| Rosehip / Dog Rose | Rosa canina | https://www.eatweeds.co.uk/rosehip-rosa-canina | edible | |
| Rowan | Sorbus aucuparia | https://www.eatweeds.co.uk/rowan-sorbus-aucuparia | edible | cooked only |
| Salad Burnet | Sanguisorba minor | https://www.eatweeds.co.uk/salad-burnet-sanguisorba-minor | edible | |
| Scots Pine | Pinus sylvestris | https://www.eatweeds.co.uk/scots-pine-pinus-sylvestris | edible | needles/resin |
| Sea Aster | Aster tripolium | https://www.eatweeds.co.uk/sea-aster-aster-tripolium | edible | |
| Sea Beet | Beta vulgaris subsp. maritima | https://www.eatweeds.co.uk/sea-beet-beta-vulgaris-maritima | edible | |
| Sea Buckthorn | Hippophae rhamnoides | https://www.eatweeds.co.uk/sea-buckthorn-elaeagnus-rhamnoides | edible | note: slug uses old name Elaeagnus |
| Sea Purslane | Atriplex portulacoides | https://www.eatweeds.co.uk/sea-purslane-atriplex-portulacoides | edible | |
| Selfheal | Prunella vulgaris | https://www.eatweeds.co.uk/selfheal-prunella-vulgaris | edible | |
| Sloe | Prunus spinosa | https://www.eatweeds.co.uk/sloe-prunus-spinosa | edible | |
| Sorrel | Rumex acetosa | https://www.eatweeds.co.uk/sorrel-rumex-acetosa | edible | |
| Sowthistle | Sonchus spp | https://www.eatweeds.co.uk/sowthistle-sonchus-spp | edible | genus-level |
| Staghorn Sumac | Rhus typhina | https://www.eatweeds.co.uk/staghorn-sumac-rhus-typhina | edible | |
| Stinging Nettle | Urtica dioica | https://www.eatweeds.co.uk/stinging-nettle-urtica-dioica | edible | |
| Sweet Chestnut | Castanea sativa | https://www.eatweeds.co.uk/sweet-chestnut-castanea-sativa | edible | |
| Sweet Flag | Acorus calamus | https://www.eatweeds.co.uk/sweet-flag-acorus-calamus | caution | toxic in large amounts; some regulators restrict |
| Sweet Violet | Viola odorata | https://www.eatweeds.co.uk/sweet-violet-viola-odorata | edible | |
| Three-cornered Leek | Allium triquetrum | https://www.eatweeds.co.uk/three-cornered-leek-allium-triquetrum | edible | |
| Water Pepper | Persicaria hydropiper | https://www.eatweeds.co.uk/water-pepper-persicaria-hydropiper | edible | |
| White Dead-Nettle | Lamium album | https://www.eatweeds.co.uk/white-dead-nettle-lamium-album | edible | |
| Wild Angelica | Angelica sylvestris | https://www.eatweeds.co.uk/wild-angelica-angelica-sylvestris | edible | |
| Wild Garlic | Allium ursinum | https://www.eatweeds.co.uk/wild-garlic-allium-ursinum | edible | |
| Wild Service Tree | Sorbus torminalis | https://www.eatweeds.co.uk/wild-service-chequers-tree-sorbus-torminalis | edible | |
| Wood Avens | Geum urbanum | https://www.eatweeds.co.uk/wood-avens-geum-urbanum | edible | |
| Yarrow | Achillea millefolium | https://www.eatweeds.co.uk/yarrow-achillea-millefolium | edible | |
| Goat's Beard | Tragopogon pratensis | https://www.eatweeds.co.uk/the-wild-root-chefs-dont-know | edible | note: non-standard slug |

---

## Source 2: botanical.com (Mrs Grieve's Modern Herbal)
*Public domain, ~800 species, UK/European focus, written 1931.*
*URL pattern: common-name-based slugs with numeric suffix — NOT scientific name automatable.*
*Use: Code should scrape all 26 index pages once to build a common_name → url → edibility map.*
*Poison index (44 species) available at: https://botanical.com/botanical/mgmh/poison.html*

**Confirmed toxic species from poison index:**
Aconite (Aconitum), Baneberry (Actaea), Bloodroot (Sanguinaria), Black Bryony (Tamus communis),
White Bryony (Bryonia dioica), Cherry Laurel (Prunus laurocerasus), Clematis spp,
Foxglove (Digitalis), Hellebore spp, Hemlock (Conium maculatum), Water Hemlock (Cicuta),
Laburnum (Laburnum anagyroides), Deadly Nightshade (Atropa belladonna),
Black Nightshade (Solanum nigrum), Meadow Saffron (Colchicum), Yew (Taxus baccata),
Thornapple (Datura stramonium), Spurges (Euphorbia spp)

*Note: 1931 publication — some caution verdicts now considered edible with modern preparation knowledge (e.g. Elder berries). Use as supporting signal only, not primary.*

**Build task for Code:** scrape `/botanical/mgmh/comindx{a-z}.html`, extract all common_name → url pairs,
then for each page check for "POISONOUS" or "poison" in body to infer toxic status.

---

## Source 3: wildfooduk.com
*Mark Williams — UK foraging guide. Explicit edible/inedible/toxic categorisation.*
*URL pattern: https://www.wildfooduk.com/hedgerow-guide/{common-name-slug}/*
*Reachability: 403 on some pages — robots.txt may restrict. Needs testing per species.*
*Species count: ~80-100 UK species.*

**Build task for Code:** fetch https://www.wildfooduk.com/wild-plant-guide/ to extract species list
and slugs, then test reachability. If blocked, use as manual lookup only.

---

## Source 4: wildfoodpeople.co.uk
*Richard Prideaux — UK/Wales foraging. Categorised directory: edible plants / edible trees / edible fungi / toxic.*
*URL pattern: JS-rendered WordPress — individual species pages not directly linkable from static HTML.*
*Edibility verdict derivable from which section species appears in (edible plants = edible, toxic section = toxic).*

**Build task for Code:** use requests-html or playwright to render
https://wildfoodpeople.co.uk/species-directory/ and extract species + section labels.
Alternatively: manual extraction of the ~60-80 species list into a JSON file.

---

## Source 5: PFAF (pfaf.org)
*Already integrated. Edibility rating 0-5. Scientific name in URL. Most reliable automated source.*
*Backfill run complete 2026-06-29: 61 species updated.*
*See app/integrations/pfaf.py for live integration.*

---

## Source 6: wildfooduk.com (FULL — replaces partial scrape)
*Mark Williams — UK foraging guide. ~140 species. Edible/Poisonous/Inedible classification per species.*
*JS-paginated site — full table manually extracted by Melvin (2 pages, 2026-06-30).*

| common_name | scientific_name | edibility | notes |
|---|---|---|---|
| Yarrow | Achillea millefolium | edible | |
| Monks Hood | Aconitum napellus | toxic | |
| Ground Elder | Aegopodium podagraria | edible | |
| Fool's Parsley | Aethusa cynapium | toxic | |
| Hedge Garlic | Alliaria petiolata | edible | |
| Few-Flowered Garlic | Allium paradoxum | edible | |
| Rosy Garlic | Allium roseum | edible | |
| Three-Cornered Leek | Allium triquetrum | edible | |
| Wild Garlic | Allium ursinum | edible | |
| Crow Garlic | Allium vineale | edible | |
| Wild Chervil | Anthriscus sylvestris | edible | |
| Columbine | Aquilegia | caution | edible-with-caution |
| Burdock | Arctium minus | edible | multi-species entry |
| Mugwort | Artemisia vulgaris | edible | |
| Lords and Ladies | Arum maculatum | toxic | |
| Asparagus | Asparagus officinalis | edible | |
| Deadly Nightshade | Atropa belladonna | toxic | |
| Purple Rock Cress | Aubrieta deltoidea | edible | |
| Wintercress | Barbarea vulgaris | edible | |
| Daisy | Bellis perennis | edible | |
| Barberry | Berberis thunbergii atropurpurea | edible | |
| Sea Beet | Beta vulgaris maritima | edible | |
| Silver Birch | Betula pendula | edible | |
| Bistort | Bistorta officinalis | edible | |
| Good King Henry | Blitum bonus-henricus | edible | |
| Borage | Borago officinalis | edible | |
| White Bryony | Bryonia dioica | toxic | |
| Trailing Bellflower | Campanula poscharskyana | edible | |
| Harebells | Campanula rotundifolia | edible | |
| Shepherd's Purse | Capsella bursa-pastoris | edible | |
| Hairy Bittercress | Cardamine hirsuta | edible | |
| Lady's Smock | Cardamine pratensis | edible | |
| Sea fig | Carpobrotus sp | edible | |
| Sweet Chestnut | Castanea sativa | edible | |
| Mouse-eared Chickweed | Cerastium sp | edible | |
| Rough chervil | Chaerophyllum temulum | toxic | |
| Rosebay Willowherb | Chamerion angustifolium | edible | |
| Fat Hen | Chenopodium album | edible | |
| Miner's lettuce | Claytonia perfoliata | edible | |
| Pink Purslane | Claytonia sibirica | edible | |
| Scurvy Grass | Cochlearia officinalis | edible | |
| Hemlock | Conium maculatum | toxic | |
| Pignut | Conopodium majus | edible | |
| Lily of the Valley | Convallaria majalis | toxic | |
| Meadow Bindweed | Convolvulus arvensis | toxic | |
| Lesser Swine Cress | Coronopus didymus | edible | |
| Hazel Nut | Corylus spp. | edible | genus-level |
| Hawthorn | Crataegus monogyna | edible | |
| Smooth Hawkbeard | Crepis capillaris | edible | |
| Rock Samphire | Crithmum maritimum | edible | |
| Thornapple/Jimson Weed | Datura stramonium | toxic | |
| Wild Carrot | Daucus carota | edible | |
| Foxglove | Digitalis sp | toxic | genus-level |
| Black Bryony | Dioscorea communis | toxic | |
| Crowberry | Empetrum nigrum | edible | |
| Winter Aconite | Eranthis hyemalis | toxic | |
| Beech Tree | Fagus sylvatica | edible | |
| Lesser Celandine | Ficaria verna | edible | |
| Meadowsweet | Filipendula ulmaria | edible | |
| Forsythia | Forsythia x intermedia | edible | |
| Wild Strawberry | Fragaria vesca | edible | |
| Cleavers | Galium aparine | edible | |
| Hedge Bedstraw | Galium mollugo | edible | |
| Wood Avens | Geum urbanum | edible | |
| Stinking Hellebore | Helleborus foetidus | toxic | |
| Fool's Watercress | Helosciadium nodiflorum | edible | |
| Giant Hogweed | Heracleum mantegazzianum | toxic | |
| Hogweed | Heracleum sphondylium | edible | |
| Lady's Rocket | Hesperis matronalis | edible | |
| Henbane | Hyoscyamus niger | toxic | |
| Himalayan Balsam | Impatiens glandulifera | edible | |
| Ragwort | Jacobaea vulgaris | toxic | |
| Walnut | Juglans regia | edible | |
| Laburnum | Laburnum sp. | toxic | genus-level |
| Prickly Wild Lettuce | Lactuca serriola | edible | |
| Dead Nettles | Lamium sp | edible | genus-level |
| Rough Hawkbit | Leontodon hispidus | edible | |
| Pheasant Berry | Leycesteria formosa | edible | |
| Honesty | Lunaria annua | edible | |
| Pimpernel species | Lysimachia sp | toxic | genus-level |
| Magnolia | Magnolia spp. | edible | genus-level |
| Oregon Grape | Mahonia aquifolium | edible | |
| Crab Apple | Malus sylvestris | edible | |
| Mallow | Malva sylvestris | edible | |
| Pineapple Weed | Matricaria discoidea | edible | |
| Water Mint | Mentha aquatica | edible | |
| Dog's Mercury | Mercurialis perennis | toxic | |
| Sweet Cicely | Myrrhis odorata | edible | |
| Watercress | Nasturtium officinale | edible | |
| Hemlock Water Dropwort | Oenanthe crocata | toxic | |
| Wood Sorrel | Oxalis acetosella | edible | |
| Pink Sorrel | Oxalis articulata | edible | |
| Green Alkanet | Pentaglottis sempervirens | toxic | |
| Water Pepper | Persicaria hydropiper | edible | |
| Winter Heliotrope | Petasites fragrans | toxic | |
| Stagshorn Plantain | Plantago coronopus | edible | |
| Ribwort Plantain | Plantago lanceolata | edible | |
| Greater Plantain | Plantago major | edible | |
| Cowslip | Primula veris | edible | |
| Primrose | Primula vulgaris | edible | |
| Damson | Prunus domestica | edible | |
| Cherry | Prunus avium | edible | |
| Blackthorn/Sloe | Prunus spinosa | edible | |
| Douglas Fir | Pseudotsuga menziesii | edible | |
| Buttercups | Ranunculus sp | toxic | genus-level |
| Sea Radish | Raphanus maritimus | edible | |
| Redcurrant | Ribes rubrum | edible | |
| Wild Gooseberry | Ribes uva-crispa | edible | |
| Dewberry | Rubus caesius | edible | |
| Bramble | Rubus fruticosus | edible | |
| Wild Raspberry | Rubus idaeus | edible | |
| Common Sorrel | Rumex acetosa | edible | |
| Sheep's Sorrel | Rumex acetosella | edible | |
| Elder tree | Sambucus nigra | edible | |
| Crown Vetch | Securigera varia | toxic | |
| White Campion | Silene latifolia | inedible | |
| Wild Mustard | Sinapis arvensis | edible | |
| Alexanders | Smyrnium olusatrum | edible | |
| Woody Nightshade | Solanum dulcamara | toxic | |
| Black nightshade | Solanum nigrum | toxic | |
| Perennial Sow-thistle | Sonchus arvensis | edible | |
| Prickly Sowthistle | Sonchus asper | edible | |
| Common Sow Thistle | Sonchus oleraceus | edible | |
| Rowan/Mountain Ash | Sorbus aucuparia | edible | |
| Service Tree | Sorbus torminalis | edible | |
| Greater Stitchwort | Stellaria holostea | edible | |
| Common Chickweed | Stellaria media | edible | |
| Comfrey | Symphytum officinale | edible | |
| Dandelion | Taraxacum officinale | edible | |
| Yew Tree | Taxus baccata | toxic | |
| Wild Thyme | Thymus polytrichus | edible | |
| Lime Tree | Tilia sp | edible | genus-level |
| Salsify/Goatsbeard | Tragopogon sp | edible | genus-level |
| Clovers | Trifolium sp | edible | genus-level |
| Coltsfoot | Tussilago farfara | edible | |
| Gorse | Ulex sp. | caution | site lists both edible+poisonous tags |
| Pennywort | Umbilicus rupestris | edible | |
| Nettle | Urtica dioica | edible | |
| Bilberry | Vaccinium myrtillus | edible | |
| Lamb's Lettuce | Valerianella locusta | edible | |
| Vetch | Vicia spp. | edible | genus-level |
| Violet | Viola odorata | edible | |

---

## Source 7: easyscape.com (Berlin native edibles)
*Gardening/landscaping tool filtered to edible natives of Berlin/Germany. All entries = edible.*
*Cloudflare-blocked on direct fetch (2026-06-30). 35 species confirmed from prior manual session.*

| scientific_name | edibility | notes |
|---|---|---|
| Sambucus nigra | edible | |
| Ajuga reptans | edible | |
| Salvia nemorosa | edible | |
| Matteuccia struthiopteris | edible | |
| Fagus sylvatica | edible | |
| Quercus robur | edible | |
| Tilia cordata | edible | |
| Thymus praecox | edible | |
| Sedum telephium | edible | |
| Galium odoratum | edible | |
| Sambucus racemosa | edible | |
| Allium schoenoprasum | edible | |
| Fragaria vesca | edible | |
| Thymus serpyllum | edible | |
| Sedum acre | edible | |
| Campanula persicifolia | edible | |
| Viola odorata | edible | |
| Calluna vulgaris | edible | |
| Origanum vulgare | edible | |
| Bellis perennis | edible | |
| Papaver rhoeas | edible | |
| Polygonatum odoratum | edible | caution raw — toxic raw, edible cooked |
| Viola tricolor | edible | |
| Muscari botryoides | edible | |
| Achillea millefolium | edible | |
| Armeria maritima | edible | |
| Juniperus communis | edible | |
| Corylus avellana | edible | |
| Athyrium filix-femina | edible | |
| Pinus sylvestris | edible | |
| Cornus mas | edible | |
| Aruncus dioicus | edible | |
| Pyrus communis | edible | |
| Sorbus aucuparia | edible | cooked only |
| Scabiosa columbaria | edible | |

---

## Source 8: TRAFFIC/WWF Central Europe (PDF)
*EU-funded ethnobotany project. 11 Central European species. Edible/medicinal.*
*Static — add manually. All 11 are edible.*

| scientific_name | common_name | edibility | notes |
|---|---|---|---|
| Vaccinium myrtillus | Bilberry | edible | fruit/leaves |
| Sambucus nigra | Black Elder | edible | flowers/berries cooked |
| Carum carvi | Caraway | edible | seeds as spice |
| Juniperus communis | Common Juniper | edible | berries as flavouring |
| Urtica dioica | Common Nettle | edible | young leaves |
| Centaurium erythraea | European Centaury | edible | medicinal primarily |
| Althaea officinalis | Marshmallow | edible | |
| Mentha x piperita | Peppermint | edible | |
| Rosa canina | Rosehip | edible | |
| Betula pendula | Silver Birch | edible | |
| Juglans regia | Walnut | edible | |

---

## Source 9: gone71.com (Edible Wild Plants Northern Europe)
*Scandinavia/Northern Europe foraging poster. ~80 species, all edible. No toxic coverage.*
*No individual URLs — list only. Good for bulk edible confirmation of Northern European species.*

| scientific_name | common_name | edibility |
|---|---|---|
| Primula veris | Cowslip | edible |
| Lathyrus pratensis | Meadow Vetchling | edible |
| Lotus corniculatus | Bird's-foot Trefoil | edible |
| Medicago falcata | Sickle Alfalfa | edible |
| Trifolium pratense | Red Clover | edible |
| Malva sylvestris | Common Mallow | edible |
| Papaver rhoeas | Common Poppy | edible |
| Verbascum phlomoides | Orange Mullein | edible |
| Potentilla reptans | Creeping Cinquefoil | edible |
| Agrimonia eupatoria | Common Agrimony | edible |
| Barbarea vulgaris | Wintercress | edible |
| Galium verum | Lady's Bedstraw | edible |
| Oxyria digyna | Mountain Sorrel | edible |
| Rumex acetosa | Sorrel | edible |
| Pulmonaria officinalis | Lungwort | edible |
| Sanguisorba officinalis | Great Burnet | edible |
| Stachys sylvatica | Hedge Woundwort | edible |
| Lamium maculatum | Spotted Dead-nettle | edible |
| Tragopogon pratensis | Goat's-beard | edible |
| Hieracium pilosella | Mouse-ear Hawkweed | edible |
| Sonchus oleraceus | Sow Thistle | edible |
| Scorzonera hispanica | Black Salsify | edible |
| Lysimachia vulgaris | Yellow Loosestrife | edible |
| Lamium galeobdolon | Yellow Archangel | edible |
| Ajuga pyramidalis | Pyramidal Bugle | edible |
| Veronica chamaedrys | Germander Speedwell | edible |
| Campanula rotundifolia | Harebell | edible |
| Campanula rapunculoides | Creeping Bellflower | edible |
| Geranium pratense | Meadow Crane's-bill | edible |
| Salvia pratensis | Meadow Clary | edible |
| Taraxacum sect. Ruderalia | Common Dandelion | edible |
| Tussilago farfara | Coltsfoot | edible |
| Scorzoneroides autumnalis | Autumn Hawkbit | edible |
| Viola biflora | Alpine Yellow Violet | edible |
| Glechoma hederacea | Ground Ivy | edible |
| Geranium sylvaticum | Wood Crane's-bill | edible |
| Vicia sativa | Common Vetch | edible |
| Vicia sepium | Bush Vetch | edible |
| Allium schoenoprasum | Chives | edible |
| Viola riviniana | Common Dog-violet | edible |
| Viola tricolor | Wild Pansy | edible |
| Bunias orientalis | Warty-cabbage | edible |
| Sisymbrium officinale | Hedge Mustard | edible |
| Matricaria chamomilla | Wild Chamomile | edible |
| Bellis perennis | Daisy | edible |
| Cardamine pratensis | Cuckoo Flower | edible |
| Cardamine bulbifera | Coral Root | edible |
| Achillea millefolium | Yarrow | edible |
| Euphrasia rostkoviana | Eyebright | edible |
| Malva neglecta | Common Mallow | edible |
| Althaea officinalis | Marsh Mallow | edible |
| Tripolium pannonicum | Sea Aster | edible |
| Allium ursinum | Wild Garlic | edible |

*(Items 54+ are image-only on the poster — not in page HTML. ~80 total per poster description.)*

---

## Source 10: Nordic Food Lab (chef species list)
*Research article — ~40 species used by Nordic chefs. All edible. No toxic coverage.*
*Lower priority — narrow scope, Scandinavian focus.*

| scientific_name | common_name | edibility |
|---|---|---|
| Urtica dioica | Stinging Nettle | edible |
| Rumex acetosa | Sorrel | edible |
| Oxalis acetosella | Wood Sorrel | edible |
| Angelica archangelica | Angelica | edible |
| Betula spp | Birch | edible |
| Allium scorodoprasum | Wild Onion | edible |
| Achillea millefolium | Yarrow | edible |
| Artemisia vulgaris | Mugwort | edible |
| Calluna vulgaris | Heather | edible |
| Fagus sylvatica | Beech | edible |
| Foeniculum vulgare | Fennel | edible |
| Fragaria vesca | Wild Strawberry | edible |
| Geum urbanum | Wood Avens | edible |
| Juniperus communis | Common Juniper | edible |
| Melissa officinalis | Lemon Balm | edible |
| Origanum vulgare | Wild Marjoram | edible |
| Picea abies | Norway Spruce | edible |
| Prunus avium | Wild Cherry | edible |
| Prunus spinosa | Blackthorn/Sloe | edible |
| Quercus spp | Oak | edible |
| Rubus fruticosus | Blackberry | edible |
| Rubus idaeus | Raspberry | edible |
| Sambucus nigra | Elder | edible |
| Vaccinium myrtillus | Bilberry | edible |
| Aegopodium podagraria | Ground Elder | edible |
| Alliaria petiolata | Garlic Mustard | edible |
| Allium ursinum | Wild Garlic | edible |
| Angelica sylvestris | Wild Angelica | edible |
| Anthriscus sylvestris | Cow Parsley | caution | Apiaceae |
| Aster tripolium | Sea Aster | edible |

---

## Pending — sources Melvin is researching
*(Add results here before building pipeline)*

---

## Cross-reference: species in ForagingID with unknown/empty edibility
*As of 2026-06-29 post-PFAF-backfill: 148 species still unknown (down from 209)*
*Priority matches to find in lookup tables above:*
*(Run Code diagnostic after Melvin adds additional sources)*

---

## Implementation notes

1. Store this file at `data/source_lookups/edibility_sources.md` in repo
2. Parse into JSON at server start or on-demand: `data/source_lookups/edibility_sources.json`
3. Pipeline match order: exact scientific_name → genus match → no match
4. For genus-level entries (Amaranthus spp, Plantago spp etc): apply to all species of that genus
   unless overridden by a species-level entry
5. Agreement model: PFAF rating + 1 lookup table match = 2 sources.
   Add eatweeds match = 3 sources → auto-approve threshold met for edible/inedible.
6. Caution verdicts: NEVER auto-approve regardless of source count. Always review.
7. Toxic verdicts: NEVER overwrite existing toxic. If lookup says toxic and DB says unknown → 
   flag for human review, do not auto-write toxic.


---

## Source 11: edibleplantdb.org
*27,918 species worldwide — largest edible plant database found. All entries = edible by definition.*
*URL pattern confirmed: /plants/{numeric-id}/{scientific-name-slug} e.g. /plants/10551/urtica-dioica*
*Bot-blocked on direct fetch — needs Code to test slug-only URL or search endpoint.*
*Coverage: global, includes European species. High value for unknown species resolution.*

**Code task:** Test `/plants/0/{scientific-name-slug}` or search endpoint. If slug works, highest-coverage automated source. Store as `data/source_lookups/edibleplantdb.json`.

---

## Source 12: eattheweeds.com (Green Deane)
*~1,000 species, US-focused but covers many European/cosmopolitan weeds. Blog format.*
*No structured scientific-name index. Not automatable. Lower priority.*

---

## Source 13: wildforager.org
*Germany-focused, curated edible plants with look-alike warnings. App-based, not automatable.*
*Useful as manual reference for German species only.*

---

## SKIP LIST (taxonomy/distribution/regulatory — no edibility data)
FloraWeb (robots.txt), GBIF, iNaturalist, PlantNet, Kew POWO, Euro+Med, World Flora, eFloras,
BSBI, NBN Atlas, Natura 2000, EEA, USDA GRIN, NABU, NatureSpot, WikiSpecies,
foragerchef.com (US blog), foragingcoursecompany.co.uk (small catalogue)

---

## TOXIC SIGNAL SOURCES (negative lookup — flag for review, never auto-write toxic)
- RHS harmful plants: https://www.rhs.org.uk/prevention-protection/potentially-harmful-garden-plants
- Woodland Trust poisonous plants: https://www.woodlandtrust.org.uk/blog/2020/07/uk-poisonous-plants/
- BfR poisonous plants: https://www.bfr.bund.de/en/service/frequently-asked-questions/topic/poisonous-plants
- Die Giftpflanzen Deutschlands 1910 PDF (commons.wikimedia.org)
- botanical.com poison index: 44 species already in Source 2 above

**Code task:** Scrape RHS + Woodland Trust toxic lists for scientific names → `data/source_lookups/toxic_signals.json`

---

## Summary: Code scrape tasks in priority order

1. **wildfooduk.com** — static HTML table, edible/poisonous, ~100 UK species
2. **easyscape.com** — 2 pages, 186 German native edibles
3. **edibleplantdb.org** — test slug-only URL first; if works, 27k species coverage
4. **RHS + Woodland Trust** — toxic_signals.json veto layer
5. **botanical.com** — 26 alpha index pages, flag poison-index entries

**Agreement threshold:** 3+ independent sources = edible → auto-approve (edible/inedible only)
**Caution:** never auto-approve regardless of count
**Toxic signals:** never auto-write toxic — always human review
