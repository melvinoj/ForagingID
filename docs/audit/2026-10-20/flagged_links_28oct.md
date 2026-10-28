# Flagged culinary source links — 28 Oct 2026

Rule: `app/services/source_links.py` — a link is flagged when neither its title nor its URL names the species (scientific name, display common name, synonyms; word-start match, case/accent/apostrophe-blind). Read-only pass over `culinary_info.culinary_links_json` on the live DB, 28 Oct 2026. Nothing deleted: flagged links are hidden from guests and print, shown to the curator on the species page with ⚑.

Counts: 190 species with links, 455 links, **345 flagged** on 132 species (129 are Wildman Steve Brill generic curriculum / day-camp / scout pages).

Known false positives (page IS the species, under a non-display common name — e.g. Ground elder on *Aegopodium* 'Goutweed', Garlic Mustard on *Alliaria* 'Hedge Garlic', Cow parsley on *Anthriscus* 'Keck'): matching every stored common name would unflag 15 links but also let wrong-species pages through (pineapple weed on *Matricaria chamomilla*, lesser celandine on *Cardamine hirsuta*), so the rule stays as decided. A curator fix is to set the preferred common name.

| species id | species | display name | source | title | url |
|---|---|---|---|---|---|
| 359 | *Abies alba* | Silver Fir | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 359 | *Abies alba* | Silver Fir | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 359 | *Abies alba* | Silver Fir | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 343 | *Abies grandis* | Grand Fir | Wildman Steve Brill | Foraging with KidsA guide to wild edible plants for parents, grandparents, and teachers, to use with children | https://www.wildmanstevebrill.com/Store_Books |
| 410 | *Acer campestre* | Field Maple | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 410 | *Acer campestre* | Field Maple | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 410 | *Acer campestre* | Field Maple | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 202 | *Achillea millefolium* | Yarrow | Galloway Wild Foods | A common, easily recognisable and rather wonderful little “weed”, with a delicious aroma of pineapple and cham | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 202 | *Achillea millefolium* | Yarrow | Galloway Wild Foods | By opening our eyes and imaginations to the full extent of our wild larder, its perfectly possible to make any | https://gallowaywildfoods.com/wild-spices-of-the-uk/ |
| 202 | *Achillea millefolium* | Yarrow | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 202 | *Achillea millefolium* | Yarrow | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 202 | *Achillea millefolium* | Yarrow | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 773 | *Adenium obesum* | Desert rose | Eatweeds | Rosehip Soup Recipe With Roasted Chilli & Smoked Tofu | https://www.eatweeds.co.uk/rosehip-soup-recipe |
| 773 | *Adenium obesum* | Desert rose | Eatweeds | Rosehip syrup | https://www.eatweeds.co.uk/rosehip-syrup-recipe |
| 178 | *Aegopodium podagraria* | Goutweed | Galloway Wild Foods | Ground elder – Identification, distribution, edibility. | https://gallowaywildfoods.com/ground-elder-identification-distribution-edibility/ |
| 178 | *Aegopodium podagraria* | Goutweed | Galloway Wild Foods | Elder Tree, Elderflower and Elderberry Identification, Edibility and Distribution | https://gallowaywildfoods.com/elder-identification-edibility-and-distribution/ |
| 178 | *Aegopodium podagraria* | Goutweed | Galloway Wild Foods | Elderflower Champagne and other Wild Floral Champagnes Recipe | https://gallowaywildfoods.com/elderflower-champagne-recipe/ |
| 817 | *Agaricus campestris* | Meadow Mushroom | Wildman Steve Brill | Wild Mushrooms | https://www.wildmanstevebrill.com/mushrooms |
| 817 | *Agaricus campestris* | Meadow Mushroom | Wildman Steve Brill | Mushroom Recipes | https://www.wildmanstevebrill.com/mushroom-recipes |
| 176 | *Alchemilla mollis* | Lady's-mantle | Wildman Steve Brill | Garden Club Program | https://www.wildmanstevebrill.com/garden-club |
| 32 | *Alliaria petiolata* | Hedge Garlic | Galloway Wild Foods | Garlic Mustard – Edibility, Identification, distribution | https://gallowaywildfoods.com/garlic-mustard-edibility-identification-distribution/ |
| 32 | *Alliaria petiolata* | Hedge Garlic | Galloway Wild Foods | An Introduction to the Mustard/Cabbage/Brassica Family for Foragers | https://gallowaywildfoods.com/an-introduction-to-the-mustardcabbagebrassica-family-for-foragers/ |
| 32 | *Alliaria petiolata* | Hedge Garlic | Galloway Wild Foods | Wild Garlic Pesto Recipe – With Goat’s Cheese & Hazelnuts | https://gallowaywildfoods.com/wild-garlic-pesto-with-goats-cheese-hazelnuts/ |
| 797 | *Alnus alnobetula* | Green alder | Wildman Steve Brill | Green Links | https://www.wildmanstevebrill.com/green-links |
| 503 | *Amanita citrina* | False Death-cap | Galloway Wild Foods | Poisonous fungi – Death Cap and Destroying Angel v False Deathcap | https://gallowaywildfoods.com/poisonous-fungi-death-cap/ |
| 785 | *Amaranthus hybridus* | Green amaranth | Eatweeds | The Traditional and Modern Uses of Common Amaranth | https://www.eatweeds.co.uk/amaranthus-retroflexus |
| 785 | *Amaranthus hybridus* | Green amaranth | Wildman Steve Brill | Green Links | https://www.wildmanstevebrill.com/green-links |
| 796 | *Ampulloclitocybe clavipes* | Club Foot | Galloway Wild Foods | There are some strange things growing out in the woods – check these out… The elegant and ephemeral hare’s foo | https://gallowaywildfoods.com/weird-and-wonderful/ |
| 796 | *Ampulloclitocybe clavipes* | Club Foot | Wildman Steve Brill | Garden Club Program | https://www.wildmanstevebrill.com/garden-club |
| 761 | *Angelica sylvestris* | Wild angelica | Galloway Wild Foods | How To Pickle Wild Mushrooms | https://gallowaywildfoods.com/how-to-pickle-wild-mushrooms/ |
| 761 | *Angelica sylvestris* | Wild angelica | Galloway Wild Foods | Wild Spices of the UK | https://gallowaywildfoods.com/wild-spices-of-the-uk/ |
| 761 | *Angelica sylvestris* | Wild angelica | Galloway Wild Foods | Wild Resources Stock-Taking | https://gallowaywildfoods.com/wild-resources-stock-taking/ |
| 761 | *Angelica sylvestris* | Wild angelica | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 761 | *Angelica sylvestris* | Wild angelica | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 761 | *Angelica sylvestris* | Wild angelica | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 106 | *Anthriscus sylvestris* | Keck | Galloway Wild Foods | Cow parsley – identification, edibility, distribution, comparison with Hemlock | https://gallowaywildfoods.com/cow-parsley-identification-edibility-and-distribution/ |
| 106 | *Anthriscus sylvestris* | Keck | Galloway Wild Foods | There are over 1500 members of the carrot/parsley – or more correctly – apiaceae – family worldwide, and aroun | https://gallowaywildfoods.com/know-your-carrots/ |
| 274 | *Anthyllis vulneraria* | Common Kidney-Vetch | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 274 | *Anthyllis vulneraria* | Common Kidney-Vetch | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 274 | *Anthyllis vulneraria* | Common Kidney-Vetch | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 495 | *Apioperdon pyriforme* | Pear-shaped Puffball | Galloway Wild Foods | Puffballs – Identification, Distribution, Edibility | https://gallowaywildfoods.com/giant-puffball-identification-distribution-edibility/ |
| 317 | *Arctium lappa* | Greater burdock | Eatweeds | The Traditional and Modern Uses of Lesser Burdock | https://www.eatweeds.co.uk/burdock-arctium-minus |
| 317 | *Arctium lappa* | Greater burdock | Eatweeds | Burdock Root Chips | https://www.eatweeds.co.uk/burdock-root-recipe |
| 317 | *Arctium lappa* | Greater burdock | Eatweeds | Burdock Root Stir Fry | https://www.eatweeds.co.uk/edible-burdock-root-recipe |
| 49 | *Aria edulis* | Whitebeam | Galloway Wild Foods | Whether you call it cep, penny bun, porcini, or king bolete, there is no doubt that Boletus edulis is the king | https://gallowaywildfoods.com/cep-identification-distribution-edibility/ |
| 502 | *Armillaria mellea* | Honey Mushroom | Galloway Wild Foods | How To Pickle Wild Mushrooms | https://gallowaywildfoods.com/how-to-pickle-wild-mushrooms/ |
| 502 | *Armillaria mellea* | Honey Mushroom | Galloway Wild Foods | Wild Mushroom Paté Recipe | https://gallowaywildfoods.com/wild-mushroom-pate-recipe/ |
| 502 | *Armillaria mellea* | Honey Mushroom | Galloway Wild Foods | Honey Fungus – Identification, Edibility, Distribution, Ecological Role | https://gallowaywildfoods.com/honey-fungus-identification-edibility-distribution-ecological-role/ |
| 502 | *Armillaria mellea* | Honey Mushroom | Wildman Steve Brill | Wild Mushrooms | https://www.wildmanstevebrill.com/mushrooms |
| 502 | *Armillaria mellea* | Honey Mushroom | Wildman Steve Brill | Mushroom Recipes | https://www.wildmanstevebrill.com/mushroom-recipes |
| 829 | *Armillaria ostoyae* | Honey Mushroom | Galloway Wild Foods | How To Pickle Wild Mushrooms | https://gallowaywildfoods.com/how-to-pickle-wild-mushrooms/ |
| 829 | *Armillaria ostoyae* | Honey Mushroom | Galloway Wild Foods | Wild Mushroom Paté Recipe | https://gallowaywildfoods.com/wild-mushroom-pate-recipe/ |
| 829 | *Armillaria ostoyae* | Honey Mushroom | Galloway Wild Foods | Honey Fungus – Identification, Edibility, Distribution, Ecological Role | https://gallowaywildfoods.com/honey-fungus-identification-edibility-distribution-ecological-role/ |
| 829 | *Armillaria ostoyae* | Honey Mushroom | Wildman Steve Brill | Wild Mushrooms | https://www.wildmanstevebrill.com/mushrooms |
| 829 | *Armillaria ostoyae* | Honey Mushroom | Wildman Steve Brill | Mushroom Recipes | https://www.wildmanstevebrill.com/mushroom-recipes |
| 701 | *Atriplex patula* | Common Orache | Galloway Wild Foods | Orache – Identification, Edibility, Distribution | https://gallowaywildfoods.com/orache-identification-edibility-distribution/ |
| 701 | *Atriplex patula* | Common Orache | Galloway Wild Foods | Common scurvygrass – Edibility, Identification, Distribution | https://gallowaywildfoods.com/common-scurvygrass-edibility-identification-distribution/ |
| 701 | *Atriplex patula* | Common Orache | Galloway Wild Foods | By opening our eyes and imaginations to the full extent of our wild larder, its perfectly possible to make any | https://gallowaywildfoods.com/wild-spices-of-the-uk/ |
| 701 | *Atriplex patula* | Common Orache | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 701 | *Atriplex patula* | Common Orache | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 701 | *Atriplex patula* | Common Orache | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 763 | *Atropa bella-donna* | Deadly Nightshade | Galloway Wild Foods | The Day I Ate A Deadly Plant: The Spectrum of Edibility | https://gallowaywildfoods.com/the-day-i-ate-a-deadly-plant-the-spectrum-of-edibility/ |
| 420 | *Betula pendula* | Common Birch | Galloway Wild Foods | Orange Birch Bolete and Brown Birch Bolete – Identification, Edibility, Distribution | https://gallowaywildfoods.com/orange-birch-bolete-and-brown-birch-bolete-identification-edibility-distribution/ |
| 420 | *Betula pendula* | Common Birch | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 420 | *Betula pendula* | Common Birch | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 420 | *Betula pendula* | Common Birch | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 455 | *Bistorta officinalis* | Common bistort | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 455 | *Bistorta officinalis* | Common bistort | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 455 | *Bistorta officinalis* | Common bistort | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 392 | *Brassica oleracea* | Kale | Galloway Wild Foods | An Introduction to the Mustard/Cabbage/Brassica Family for Foragers | https://gallowaywildfoods.com/an-introduction-to-the-mustardcabbagebrassica-family-for-foragers/ |
| 380 | *Briza media* | Totter grass | Wildman Steve Brill | Media | https://wildmanstevebrill.com/media |
| 276 | *Cardamine amara* | Large bittercress | Eatweeds | Hairy Bittercress, Dandelion & Papaya Salad | https://www.eatweeds.co.uk/hairy-bittercress-dandelion-papaya-salad |
| 276 | *Cardamine amara* | Large bittercress | Galloway Wild Foods | Hairy Bittercress – Identification, Edibility and Distribution | https://gallowaywildfoods.com/hairy-bittercress-identification-edibility-and-distribution/ |
| 17 | *Cardamine flexuosa* | Wavy Bittercress | Galloway Wild Foods | Hairy Bittercress – Identification, Edibility and Distribution | https://gallowaywildfoods.com/hairy-bittercress-identification-edibility-and-distribution/ |
| 21 | *Cardamine hirsuta* | Hairy bittercress | Galloway Wild Foods | Prior to flowering, lesser celandine is one of the milder spring leaves, so good for bulking out salads of mor | https://gallowaywildfoods.com/lesser-celandine-edibility-distribution-identification/ |
| 135 | *Cardamine pratensis* | Cuckoo flower | Galloway Wild Foods | One of the very best ways to taste the vibrant shoots, leaves, and flowers of spring is in wild sushi. Many of | https://gallowaywildfoods.com/wild-sushi-rolls/ |
| 551 | *Cirsium arvense* | Field thistle | Eatweeds | The Traditional and Modern Uses of Smooth Sowthistle | https://www.eatweeds.co.uk/sowthistle-sonchus-spp |
| 551 | *Cirsium arvense* | Field thistle | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 551 | *Cirsium arvense* | Field thistle | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 551 | *Cirsium arvense* | Field thistle | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 634 | *Cirsium oleraceum* | Water Thistle | Eatweeds | Sowthistle Tempeh Salad | https://www.eatweeds.co.uk/sowthistle-tempeh-salad |
| 28 | *Cirsium palustre* | Marsh thistle | Eatweeds | How to Identify Milk Thistle | https://www.eatweeds.co.uk/how-to-identify-milk-thistle |
| 375 | *Cirsium vulgare* | Bull Thistle | Eatweeds | What Persian Cooks, Cajun Cooks, and Native American Foragers All Knew About the Spear Thistle | https://www.eatweeds.co.uk/spearthistle |
| 857 | *Clinopodium vulgare* | Wild basil | Eatweeds | Getting Wild In Laos With Three Cornered Leek | https://www.eatweeds.co.uk/wild-lahp-recipe |
| 857 | *Clinopodium vulgare* | Wild basil | Galloway Wild Foods | Wild Sushi Rolls | https://gallowaywildfoods.com/wild-sushi-rolls/ |
| 857 | *Clinopodium vulgare* | Wild basil | Galloway Wild Foods | Foraging Perspectives: Foraging in 1950’s Russia | https://gallowaywildfoods.com/foraging-in-1950s-russia/ |
| 857 | *Clinopodium vulgare* | Wild basil | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 857 | *Clinopodium vulgare* | Wild basil | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 857 | *Clinopodium vulgare* | Wild basil | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 130 | *Conium maculatum* | Poison hemlock | Galloway Wild Foods | Poisonous plants – hemlock | https://gallowaywildfoods.com/587-2/ |
| 130 | *Conium maculatum* | Poison hemlock | Galloway Wild Foods | Poisonous plants – hemlock water-dropwort | https://gallowaywildfoods.com/poisonous-plants-hemlock-water-dropwort/ |
| 130 | *Conium maculatum* | Poison hemlock | Galloway Wild Foods | Cow parsley – identification, edibility, distribution, comparison with Hemlock | https://gallowaywildfoods.com/cow-parsley-identification-edibility-and-distribution/ |
| 130 | *Conium maculatum* | Poison hemlock | Botanical.com | Poisons Index | https://botanical.com/botanical/mgmh/poison.html |
| 130 | *Conium maculatum* | Poison hemlock | Botanical.com | Shorter Medical Dictionary, 1942 - Poisons & Antidotes | https://botanical.com/botanical/steapois/poisonix.html |
| 639 | *Cornus sanguinea* | Dogwood | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 639 | *Cornus sanguinea* | Dogwood | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 639 | *Cornus sanguinea* | Dogwood | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 368 | *Corylus avellana* | Hazel | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 368 | *Corylus avellana* | Hazel | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 368 | *Corylus avellana* | Hazel | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 860 | *Cystoderma aureum* | Golden Cap | Galloway Wild Foods | Both species are large brown to golden brown seaweeds up to 3m long, with flat, finger-like fronds extending f | https://gallowaywildfoods.com/forest-kelp-and-oarweed-edibility-identification-distribution/ |
| 320 | *Dactylorhiza fuchsii* | Common spotted orchid | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 320 | *Dactylorhiza fuchsii* | Common spotted orchid | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 320 | *Dactylorhiza fuchsii* | Common spotted orchid | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 9 | *Daucus carota* | Wild Carrot | Eatweeds | Forty wild edible plants in the carrot family | https://www.eatweeds.co.uk/40-wild-edible-plants-in-the-carrot-family |
| 9 | *Daucus carota* | Wild Carrot | Eatweeds | The Carrot Family (Apiaceae) | https://www.eatweeds.co.uk/apiaceae |
| 9 | *Daucus carota* | Wild Carrot | Galloway Wild Foods | Online Wild Food Mentoring | https://gallowaywildfoods.com/wild-food-mentor/ |
| 9 | *Daucus carota* | Wild Carrot | Galloway Wild Foods | Wild Spices of the UK | https://gallowaywildfoods.com/wild-spices-of-the-uk/ |
| 9 | *Daucus carota* | Wild Carrot | Galloway Wild Foods | An Introduction to the Carrot/Apiaceae Family for Foragers | https://gallowaywildfoods.com/know-your-carrots/ |
| 9 | *Daucus carota* | Wild Carrot | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 9 | *Daucus carota* | Wild Carrot | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 9 | *Daucus carota* | Wild Carrot | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 204 | *Dipsacus fullonum* | Teasel | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 204 | *Dipsacus fullonum* | Teasel | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 204 | *Dipsacus fullonum* | Teasel | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 58 | *Dryopteris filix-mas* | Male fern | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 58 | *Dryopteris filix-mas* | Male fern | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 58 | *Dryopteris filix-mas* | Male fern | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 527 | *Equisetum arvense* | Field horsetail | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 527 | *Equisetum arvense* | Field horsetail | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 527 | *Equisetum arvense* | Field horsetail | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 556 | *Eriophorum angustifolium* | Tall Cotton-Grass | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 556 | *Eriophorum angustifolium* | Tall Cotton-Grass | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 556 | *Eriophorum angustifolium* | Tall Cotton-Grass | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 181 | *Fragaria vesca* | Wild Strawberry | Galloway Wild Foods | Pineapple Weed – Identification, Edibility, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 181 | *Fragaria vesca* | Wild Strawberry | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 181 | *Fragaria vesca* | Wild Strawberry | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 181 | *Fragaria vesca* | Wild Strawberry | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 774 | *Furcraea selloana* | Wild Sisal | Galloway Wild Foods | https://gallowaywildfoods.com/?feed=rss2 | https://gallowaywildfoods.com/?feed=rss2 |
| 774 | *Furcraea selloana* | Wild Sisal | Galloway Wild Foods | https://gallowaywildfoods.com/contact-me | https://gallowaywildfoods.com/contact-me |
| 774 | *Furcraea selloana* | Wild Sisal | Galloway Wild Foods | Galloway Wild Foods | https://gallowaywildfoods.com/ |
| 774 | *Furcraea selloana* | Wild Sisal | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 774 | *Furcraea selloana* | Wild Sisal | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 774 | *Furcraea selloana* | Wild Sisal | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 198 | *Galium odoratum* | Woodruff | Galloway Wild Foods | A common, easily recognisable and rather wonderful little “weed”, with a delicious aroma of pineapple and cham | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 768 | *Geranium robertianum* | Herb Robert | Eatweeds | The Traditional and Modern Uses of Wood Avens (Herb Bennet) | https://www.eatweeds.co.uk/wood-avens-geum-urbanum |
| 768 | *Geranium robertianum* | Herb Robert | Botanical.com | A Modern Herbal | https://botanical.com/botanical/mgmh/mgmh.html |
| 768 | *Geranium robertianum* | Herb Robert | Botanical.com | Plant & Herb Index | https://botanical.com/botanical/mgmh/comindx.html |
| 618 | *Geum rivale* | Water Avens | Galloway Wild Foods | Wood Avens – Edibility, Identification, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/wood-avens-edibility-identification-distribution/ |
| 873 | *Gymnopilus penetrans* | Common Rustgill | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 873 | *Gymnopilus penetrans* | Common Rustgill | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 873 | *Gymnopilus penetrans* | Common Rustgill | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 745 | *Hedera helix* | Common Ivy | Galloway Wild Foods | This is a super-common plant of wood edges and hedgerows, with a long history of medicinal use. The leaves can | https://gallowaywildfoods.com/wood-avens-edibility-identification-distribution/ |
| 745 | *Hedera helix* | Common Ivy | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 745 | *Hedera helix* | Common Ivy | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 745 | *Hedera helix* | Common Ivy | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 694 | *Heracleum sibiricum* | Eltrot | Eatweeds | The Traditional and Modern Uses of Hogweed | https://www.eatweeds.co.uk/hogweed-heracleum-sphondylium |
| 694 | *Heracleum sibiricum* | Eltrot | Eatweeds | Hogweed Seed Spice, Cashew and Date Sweets | https://www.eatweeds.co.uk/hogweed-seed-spiced-sweets |
| 694 | *Heracleum sibiricum* | Eltrot | Eatweeds | Quick Braised Hogweed Shoots | https://www.eatweeds.co.uk/braised-hogweed-shoots-recipe |
| 694 | *Heracleum sibiricum* | Eltrot | Galloway Wild Foods | Hogweed Seed Parkin Cake Recipe | https://gallowaywildfoods.com/hogweed-seed-parkin-cake-recipe/ |
| 694 | *Heracleum sibiricum* | Eltrot | Galloway Wild Foods | Common Hogweed – Identification, Edibility, Distribution | https://gallowaywildfoods.com/hogweed/ |
| 336 | *Hydnum repandum* | Wood Hedgehog | Galloway Wild Foods | Foraging Perspectives: A Meeting in the Woods | https://gallowaywildfoods.com/a-meeting-in-the-woods/ |
| 336 | *Hydnum repandum* | Wood Hedgehog | Galloway Wild Foods | Hedgehog mushroom – Edibility, Identification, Distribution, Ecology | https://gallowaywildfoods.com/october-hedgehog-mushroom/ |
| 875 | *Hygrophoropsis aurantiaca* | False Chanterelle | Galloway Wild Foods | Chanterelle – Identification, Distribution, Edibility, Ecology, Sustainable Harvesting, Cooking, Processing, R | https://gallowaywildfoods.com/chanterelle-identification-distribution-edibility/ |
| 229 | *Hypericum perforatum* | St John's wort | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 229 | *Hypericum perforatum* | St John's wort | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 229 | *Hypericum perforatum* | St John's wort | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 806 | *Juniperus communis* | Common juniper | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 806 | *Juniperus communis* | Common juniper | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 806 | *Juniperus communis* | Common juniper | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 355 | *Laetiporus sulphureus* | Chicken of the woods | Galloway Wild Foods | Hen of the Woods – Identification, Edibility, Distribution, Medicinal Uses, Ecology, Sustainable Harvesting | https://gallowaywildfoods.com/hen-of-the-woods-identification-edibility-distribution-ecology/ |
| 743 | *Lathyrus linifolius* | Bitter Vetch | Galloway Wild Foods | A few thoughts on how to combine pungent, bitter, sour, mild and aromatic spring and summer plants into a sati | https://gallowaywildfoods.com/spring-weed-salad/ |
| 379 | *Lathyrus oleraceus* | केराइ | Wildman Steve Brill | Garden Club Program | https://www.wildmanstevebrill.com/garden-club |
| 563 | *Linaria purpurea* | Purple Toadflax | Galloway Wild Foods | Even if it wasn’t edible sea kale would still be my favourite plant. Its alien-looking purple shoots, sculptur | https://gallowaywildfoods.com/sea-kale-identification-edibility-and-distribution/ |
| 82 | *Lophiolepis ferox* | Thistle | Eatweeds | Sowthistle and White Bean Soup | https://www.eatweeds.co.uk/simple-bean-and-sowthistle-soup |
| 351 | *Lunaria annua* | Honesty | Galloway Wild Foods | Lie, lies, lies!What does “local” really mean on a menu? And are those “Wild mushrooms” really wild?A rant on  | https://gallowaywildfoods.com/local-meat-and-wild-mushrooms-26711/ |
| 185 | *Lupinus polyphyllus* | Garden Lupin | Wildman Steve Brill | Garden Club Program | https://www.wildmanstevebrill.com/garden-club |
| 680 | *Luzula sylvatica* | Great wood rush | Galloway Wild Foods | Hen of the Woods – Identification, Edibility, Distribution, Medicinal Uses, Ecology, Sustainable Harvesting | https://gallowaywildfoods.com/hen-of-the-woods-identification-edibility-distribution-ecology/ |
| 494 | *Lycoperdon perlatum* | Common puffball | Galloway Wild Foods | Puffballs – Identification, Distribution, Edibility | https://gallowaywildfoods.com/giant-puffball-identification-distribution-edibility/ |
| 494 | *Lycoperdon perlatum* | Common puffball | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 494 | *Lycoperdon perlatum* | Common puffball | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 494 | *Lycoperdon perlatum* | Common puffball | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 591 | *Lysimachia vulgaris* | Loosestrife | Wildman Steve Brill | Garden Club Program | https://www.wildmanstevebrill.com/garden-club |
| 161 | *Malus domestica* | Apple | Galloway Wild Foods | Pickled Chanterelles with Pineapple Weed Recipe | https://gallowaywildfoods.com/pickled-chanterelles-with-pineapple-weed-recipe/ |
| 161 | *Malus domestica* | Apple | Galloway Wild Foods | Pineapple Weed – Identification, Edibility, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 228 | *Matricaria chamomilla* | Mayweed | Galloway Wild Foods | A common, easily recognisable and rather wonderful little “weed”, with a delicious aroma of pineapple and cham | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 762 | *Melampyrum pratense* | Common Cow wheat | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 762 | *Melampyrum pratense* | Common Cow wheat | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 762 | *Melampyrum pratense* | Common Cow wheat | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 179 | *Mentha aquatica* | Mint | Eatweeds | Cold water infusions versus hot water infusions – which is better? | https://www.eatweeds.co.uk/cold-water-infusions-versus-hot-water-infusions |
| 179 | *Mentha aquatica* | Mint | Galloway Wild Foods | Watercress – edibility, distribution and identification | https://gallowaywildfoods.com/watercress-edibility-distribution-and-identification/ |
| 8 | *Mentha arvensis* | Corn mint | Eatweeds | Getting Wild In Laos With Three Cornered Leek | https://www.eatweeds.co.uk/wild-lahp-recipe |
| 291 | *Mentha longifolia* | Horsemint | Eatweeds | The Traditional and Modern Uses of Horseradish | https://www.eatweeds.co.uk/horseradish-armoracia-rusticana |
| 331 | *Mycena galericulata* | Common bonnet | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 331 | *Mycena galericulata* | Common bonnet | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 331 | *Mycena galericulata* | Common bonnet | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 180 | *Nasturtium officinale* | Water-cress | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 180 | *Nasturtium officinale* | Water-cress | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 180 | *Nasturtium officinale* | Water-cress | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 323 | *Oudemansiella mucida* | Porcelain mushroom | Wildman Steve Brill | Wild Mushrooms | https://www.wildmanstevebrill.com/mushrooms |
| 323 | *Oudemansiella mucida* | Porcelain mushroom | Wildman Steve Brill | Mushroom Recipes | https://www.wildmanstevebrill.com/mushroom-recipes |
| 243 | *Oxalis dillenii* | Wood-shamrock | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 243 | *Oxalis dillenii* | Wood-shamrock | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 243 | *Oxalis dillenii* | Wood-shamrock | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 456 | *Papaver rhoeas* | Common poppy | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 456 | *Papaver rhoeas* | Common poppy | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 456 | *Papaver rhoeas* | Common poppy | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 899 | *Paris quadrifolia* | Herb Paris | Galloway Wild Foods | Cow parsley – identification, edibility, distribution, comparison with Hemlock | https://gallowaywildfoods.com/cow-parsley-identification-edibility-and-distribution/ |
| 899 | *Paris quadrifolia* | Herb Paris | Botanical.com | A Modern Herbal | https://botanical.com/botanical/mgmh/mgmh.html |
| 899 | *Paris quadrifolia* | Herb Paris | Botanical.com | Plant & Herb Index | https://botanical.com/botanical/mgmh/comindx.html |
| 334 | *Petasites hybridus* | Common Butterbur | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 334 | *Petasites hybridus* | Common Butterbur | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 334 | *Petasites hybridus* | Common Butterbur | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 438 | *Pinus nigra* | Black pine | Eatweeds | Black mustard with millet | https://www.eatweeds.co.uk/black-mustard-with-millet |
| 289 | *Pinus pinea* | Stone Pine | Eatweeds | The Traditional and Modern Uses of Orpine | https://www.eatweeds.co.uk/orpine-sedum-telephium |
| 95 | *Plantago major* | Plantain | Galloway Wild Foods | A common, easily recognisable and rather wonderful little “weed”, with a delicious aroma of pineapple and cham | https://gallowaywildfoods.com/pineapple-weed-identification-edibility-distribution-ecology-recipes/ |
| 95 | *Plantago major* | Plantain | Galloway Wild Foods | By opening our eyes and imaginations to the full extent of our wild larder, its perfectly possible to make any | https://gallowaywildfoods.com/wild-spices-of-the-uk/ |
| 95 | *Plantago major* | Plantain | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 95 | *Plantago major* | Plantain | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 95 | *Plantago major* | Plantain | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 560 | *Pleurotus pulmonarius* | Pale oyster | Galloway Wild Foods | Oyster mushroom – Edibility, Identification, Distribution | https://gallowaywildfoods.com/oyster-mushroom-edibility-identification-distribution/ |
| 560 | *Pleurotus pulmonarius* | Pale oyster | Galloway Wild Foods | There are some strange things growing out in the woods – check these out… The elegant and ephemeral hare’s foo | https://gallowaywildfoods.com/weird-and-wonderful/ |
| 7 | *Prunus avium* | Wild Cherry | Galloway Wild Foods | https://gallowaywildfoods.com/?feed=rss2 | https://gallowaywildfoods.com/?feed=rss2 |
| 7 | *Prunus avium* | Wild Cherry | Galloway Wild Foods | https://gallowaywildfoods.com/contact-me | https://gallowaywildfoods.com/contact-me |
| 7 | *Prunus avium* | Wild Cherry | Galloway Wild Foods | Galloway Wild Foods | https://gallowaywildfoods.com/ |
| 7 | *Prunus avium* | Wild Cherry | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 7 | *Prunus avium* | Wild Cherry | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 7 | *Prunus avium* | Wild Cherry | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 212 | *Prunus cerasus* | Sour cherry | Eatweeds | The Traditional and Modern Uses of Japanese Cherry | https://www.eatweeds.co.uk/japanese-cherry-prunus-serrulata |
| 212 | *Prunus cerasus* | Sour cherry | Eatweeds | Cherry plum | https://www.eatweeds.co.uk/cherry-plum-prunus-cerasifera |
| 212 | *Prunus cerasus* | Sour cherry | Galloway Wild Foods | Wild Resources Stock-Taking | https://gallowaywildfoods.com/wild-resources-stock-taking/ |
| 385 | *Pyrola minor* | Mountain pyrola | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 385 | *Pyrola minor* | Mountain pyrola | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 385 | *Pyrola minor* | Mountain pyrola | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 433 | *Pyrus communis* | Pear | Eatweeds | EP60: Connecting Children and Families to the Wild – with Chris Holland | https://www.eatweeds.co.uk/ep60 |
| 433 | *Pyrus communis* | Pear | Eatweeds | What Persian Cooks, Cajun Cooks, and Native American Foragers All Knew About the Spear Thistle | https://www.eatweeds.co.uk/spearthistle |
| 433 | *Pyrus communis* | Pear | Eatweeds | Wild Marshmallow Vegan Recipe | https://www.eatweeds.co.uk/wild-marshmallow-vegan-recipe |
| 433 | *Pyrus communis* | Pear | Galloway Wild Foods | How To Pickle Wild Mushrooms | https://gallowaywildfoods.com/how-to-pickle-wild-mushrooms/ |
| 433 | *Pyrus communis* | Pear | Galloway Wild Foods | Accrediting Foraging & Wild Food in the UK | https://gallowaywildfoods.com/accrediting-foraging-and-wild-food-in-the-uk/ |
| 433 | *Pyrus communis* | Pear | Galloway Wild Foods | Foraging Perspectives – Wild Creeping Time | https://gallowaywildfoods.com/foraging-perspectives-wild-creeping-time/ |
| 433 | *Pyrus communis* | Pear | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 433 | *Pyrus communis* | Pear | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 433 | *Pyrus communis* | Pear | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 64 | *Quercus robur* | Common Oak | Galloway Wild Foods | One of the UK’s most common mushrooms, honey fungus suffers from a bad reputation because it is a virulent par | https://gallowaywildfoods.com/honey-fungus-identification-edibility-distribution-ecological-role/ |
| 64 | *Quercus robur* | Common Oak | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 64 | *Quercus robur* | Common Oak | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 64 | *Quercus robur* | Common Oak | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 123 | *Ranunculus ficaria* | Fig buttercup | Eatweeds | The Traditional and Modern Uses of Lesser Celandine | https://www.eatweeds.co.uk/lesser-celandine-ficaria-verna |
| 419 | *Reynoutria japonica* | Mexican-bamboo | Galloway Wild Foods | Japanese knotweed – Identification, distribution, edibility | https://gallowaywildfoods.com/japanese-knotweed-identification-distribution-edibility/ |
| 391 | *Ribes nigrum* | Blackcurrant | Eatweeds | The Traditional and Modern Uses of Flowering Currant | https://www.eatweeds.co.uk/flowering-currant-ribes-sanguineum |
| 391 | *Ribes nigrum* | Blackcurrant | Galloway Wild Foods | Flowering Currant – Identification, Distribution, Edibility, Recipes | https://gallowaywildfoods.com/flowering-currant-identification-distribution-edibility-recipes/ |
| 297 | *Rosa arvensis* | Field Rose | Eatweeds | The Traditional and Modern Uses of Rosebay Willowherb (Fireweed) | https://www.eatweeds.co.uk/rosebay-willowherb-epilobium-angustifolium |
| 297 | *Rosa arvensis* | Field Rose | Eatweeds | The Traditional and Modern Uses of Primrose | https://www.eatweeds.co.uk/primrose-primula-vulgaris |
| 297 | *Rosa arvensis* | Field Rose | Eatweeds | Everything you need to know about rosehips | https://www.eatweeds.co.uk/rosehip-faq |
| 297 | *Rosa arvensis* | Field Rose | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 297 | *Rosa arvensis* | Field Rose | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 297 | *Rosa arvensis* | Field Rose | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 100 | *Rosa canina* | Dog Rose | Galloway Wild Foods | Sea beet is an aristocrat in the world of wild greens. Like many true aristocrats, it has an unkempt appearanc | https://gallowaywildfoods.com/sea-beet-identification-distribution-edibility/ |
| 298 | *Rosa spinosissima* | Burnet Rose | Eatweeds | Everything you need to know about rosehips | https://www.eatweeds.co.uk/rosehip-faq |
| 520 | *Rumex acetosa* | Common Sorrel | Galloway Wild Foods | Common Hogweed – Identification, Edibility, Distribution | https://gallowaywildfoods.com/hogweed/ |
| 520 | *Rumex acetosa* | Common Sorrel | Galloway Wild Foods | Wood Sorrel – Identification, Edibility, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/december-wood-sorrel/ |
| 520 | *Rumex acetosa* | Common Sorrel | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 520 | *Rumex acetosa* | Common Sorrel | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 520 | *Rumex acetosa* | Common Sorrel | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 166 | *Rumex acetosella* | Red sorrel | Galloway Wild Foods | A very common, easy to identify, delicious succulent coastal plant that grows just above the high tide line on | https://gallowaywildfoods.com/sea-sandwort-identification-edibility-distribution-ecology-sustainable-harvesting-recipes/ |
| 166 | *Rumex acetosella* | Red sorrel | Galloway Wild Foods | One of the great pleasures of foraging is discovering exciting flavours in the common and innocuous-looking pl | https://gallowaywildfoods.com/sea-arrowgrass-identification-distribution-edibility/ |
| 166 | *Rumex acetosella* | Red sorrel | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 166 | *Rumex acetosella* | Red sorrel | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 166 | *Rumex acetosella* | Red sorrel | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 73 | *Rumex conglomeratus* | Green dock | Eatweeds | A history of dock pudding: A centuries-old springtime delicacy from Yorkshire | https://www.eatweeds.co.uk/a-history-of-dock-pudding |
| 73 | *Rumex conglomeratus* | Green dock | Eatweeds | The Traditional and Modern Uses of Broad-leaved dock | https://www.eatweeds.co.uk/dock-rumex-obtusifolius |
| 73 | *Rumex conglomeratus* | Green dock | Eatweeds | The Traditional and Modern Uses of Lesser Burdock | https://www.eatweeds.co.uk/burdock-arctium-minus |
| 73 | *Rumex conglomeratus* | Green dock | Galloway Wild Foods | Dock, Dandelion and Nettle Spring Puddings | https://gallowaywildfoods.com/dock-dandelion-and-nettle-spring-puddings/ |
| 73 | *Rumex conglomeratus* | Green dock | Wildman Steve Brill | Green Links | https://www.wildmanstevebrill.com/green-links |
| 258 | *Rumex crispus* | Curled dock | Eatweeds | Frank Cook on dock | https://www.eatweeds.co.uk/learn-about-dock-rumex |
| 258 | *Rumex crispus* | Curled dock | Galloway Wild Foods | Dock, Dandelion and Nettle Spring Puddings | https://gallowaywildfoods.com/dock-dandelion-and-nettle-spring-puddings/ |
| 305 | *Rumex obtusifolius* | Broad-leaved dock | Eatweeds | Frank Cook on dock | https://www.eatweeds.co.uk/learn-about-dock-rumex |
| 305 | *Rumex obtusifolius* | Broad-leaved dock | Galloway Wild Foods | Dock, Dandelion and Nettle Spring Puddings | https://gallowaywildfoods.com/dock-dandelion-and-nettle-spring-puddings/ |
| 348 | *Rumex sanguineus* | Wood Dock | Eatweeds | The Traditional and Modern Uses of Lesser Burdock | https://www.eatweeds.co.uk/burdock-arctium-minus |
| 348 | *Rumex sanguineus* | Wood Dock | Galloway Wild Foods | Dock, Dandelion and Nettle Spring Puddings | https://gallowaywildfoods.com/dock-dandelion-and-nettle-spring-puddings/ |
| 894 | *Rumex scutatus* | French sorrel | Eatweeds | Sorrel, watercress and roasted fennel soup | https://www.eatweeds.co.uk/sorrel-watercress-and-fennel-soup |
| 432 | *Salix alba* | White willow | Eatweeds | The Traditional and Modern Uses of Rosebay Willowherb (Fireweed) | https://www.eatweeds.co.uk/rosebay-willowherb-epilobium-angustifolium |
| 432 | *Salix alba* | White willow | Galloway Wild Foods | Rosebay Willowherb/Fireweed – Edibility, Identification, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/rosebay-willowherbfireweed-edibility-identification-recipes/ |
| 795 | *Salix aurita* | Eared willow | Eatweeds | The Traditional and Modern Uses of Rosebay Willowherb (Fireweed) | https://www.eatweeds.co.uk/rosebay-willowherb-epilobium-angustifolium |
| 174 | *Salvia officinalis* | Sage | Galloway Wild Foods | Laver Seaweed – Edibility, Identification, Distribution, Preparation, Usage and Laverbread Recipe | https://gallowaywildfoods.com/laver-seaweed-edibility-identification-distribution/ |
| 174 | *Salvia officinalis* | Sage | Galloway Wild Foods | Winter Chanterelle – Edibility, Identification, Similar species, Distribution, Ecology, Harvesting, Usage | https://gallowaywildfoods.com/winter-chanterelle-edibility-identification-distribution/ |
| 107 | *Sambucus nigra* | Elderberry | Galloway Wild Foods | Ground elder – Identification, distribution, edibility. | https://gallowaywildfoods.com/ground-elder-identification-distribution-edibility/ |
| 107 | *Sambucus nigra* | Elderberry | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 107 | *Sambucus nigra* | Elderberry | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 107 | *Sambucus nigra* | Elderberry | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 617 | *Sanguisorba officinalis* | Great Burnet | Eatweeds | The Traditional and Modern Uses of Salad Burnet | https://www.eatweeds.co.uk/salad-burnet-sanguisorba-minor |
| 617 | *Sanguisorba officinalis* | Great Burnet | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 617 | *Sanguisorba officinalis* | Great Burnet | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 617 | *Sanguisorba officinalis* | Great Burnet | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 856 | *Scrophularia nodosa* | Common figwort | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 856 | *Scrophularia nodosa* | Common figwort | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 856 | *Scrophularia nodosa* | Common figwort | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 90 | *Silene dioica* | Red Campion | Galloway Wild Foods | Sea campion – Edibility, Identification, Distribution | https://gallowaywildfoods.com/sea-campion-edibility-identification-distribution/ |
| 301 | *Silene latifolia* | White campion | Eatweeds | The Traditional and Modern Uses of Red Campion | https://www.eatweeds.co.uk/red-campion-silene-dioica |
| 347 | *Sisymbrium officinale* | Hedge Mustard | Eatweeds | Black mustard soup | https://www.eatweeds.co.uk/black-mustard-soup |
| 347 | *Sisymbrium officinale* | Hedge Mustard | Eatweeds | The Traditional and Modern Uses of Garlic Mustard | https://www.eatweeds.co.uk/garlic-mustard-alliaria-petiolata |
| 347 | *Sisymbrium officinale* | Hedge Mustard | Galloway Wild Foods | An Introduction to the Mustard/Cabbage/Brassica Family for Foragers | https://gallowaywildfoods.com/an-introduction-to-the-mustardcabbagebrassica-family-for-foragers/ |
| 347 | *Sisymbrium officinale* | Hedge Mustard | Galloway Wild Foods | Garlic Mustard – Edibility, Identification, distribution | https://gallowaywildfoods.com/garlic-mustard-edibility-identification-distribution/ |
| 207 | *Sonchus arvensis* | Sowthistle | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 207 | *Sonchus arvensis* | Sowthistle | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 207 | *Sonchus arvensis* | Sowthistle | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 327 | *Sonchus asper* | Spiny sowthistle | Eatweeds | Buttered Prickly Sowthistle Tips | https://www.eatweeds.co.uk/sowthistle-recipe |
| 350 | *Sonchus oleraceus* | Common sowthistle | Eatweeds | The Traditional and Modern Uses of Smooth Sowthistle | https://www.eatweeds.co.uk/sowthistle-sonchus-spp |
| 350 | *Sonchus oleraceus* | Common sowthistle | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 350 | *Sonchus oleraceus* | Common sowthistle | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 350 | *Sonchus oleraceus* | Common sowthistle | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 16 | *Stellaria media* | Common chickweed | Galloway Wild Foods | Chickweed – Identification, Edibility, Distribution | https://gallowaywildfoods.com/chickweed-identification-edibility-distribution/ |
| 16 | *Stellaria media* | Common chickweed | Galloway Wild Foods | A very common, easy to identify, delicious succulent coastal plant that grows just above the high tide line on | https://gallowaywildfoods.com/sea-sandwort-identification-edibility-distribution-ecology-sustainable-harvesting-recipes/ |
| 16 | *Stellaria media* | Common chickweed | Wildman Steve Brill | Media | https://wildmanstevebrill.com/media |
| 139 | *Symphyotrichum novi-belgii* | New York aster | Eatweeds | The Traditional and Modern Uses of Sea Aster | https://www.eatweeds.co.uk/sea-aster-aster-tripolium |
| 68 | *Syringa vulgaris* | Lilac | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 68 | *Syringa vulgaris* | Lilac | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 68 | *Syringa vulgaris* | Lilac | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 194 | *Tanacetum vulgare* | Tansy | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 194 | *Tanacetum vulgare* | Tansy | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 194 | *Tanacetum vulgare* | Tansy | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 819 | *Taraxacum erythrospermum* | Rock dandelion | Eatweeds | EP17: Busted by the cops for picking a dandelion | https://www.eatweeds.co.uk/ep17 |
| 356 | *Taxus baccata* | Common yew | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 356 | *Taxus baccata* | Common yew | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 356 | *Taxus baccata* | Common yew | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 383 | *Teucrium scorodonia* | Wood Sage | Galloway Wild Foods | Hen of the Woods – Identification, Edibility, Distribution, Medicinal Uses, Ecology, Sustainable Harvesting | https://gallowaywildfoods.com/hen-of-the-woods-identification-edibility-distribution-ecology/ |
| 383 | *Teucrium scorodonia* | Wood Sage | Galloway Wild Foods | Wood Avens – Edibility, Identification, Distribution, Ecology, Recipes | https://gallowaywildfoods.com/wood-avens-edibility-identification-distribution/ |
| 383 | *Teucrium scorodonia* | Wood Sage | Galloway Wild Foods | Winter Chanterelle – Edibility, Identification, Similar species, Distribution, Ecology, Harvesting, Usage | https://gallowaywildfoods.com/winter-chanterelle-edibility-identification-distribution/ |
| 513 | *Thlaspi arvense* | Field penny-cress | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 513 | *Thlaspi arvense* | Field penny-cress | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 513 | *Thlaspi arvense* | Field penny-cress | Wildman Steve Brill | Birthday PartiesThis hands-on environmental birthday party consists of a field walk in a local park focusing o | https://www.wildmanstevebrill.com/birthday-party |
| 142 | *Thymus polytrichus* | English Wild Thyme | Galloway Wild Foods | Wild Galloway Banquet | https://gallowaywildfoods.com/wild-galloway-banquet/ |
| 142 | *Thymus polytrichus* | English Wild Thyme | Galloway Wild Foods | Wild Resources Stock-Taking | https://gallowaywildfoods.com/wild-resources-stock-taking/ |
| 142 | *Thymus polytrichus* | English Wild Thyme | Galloway Wild Foods | Elderberry Vinegar Recipe | https://gallowaywildfoods.com/elderberry-vinegar-recipe/ |
| 142 | *Thymus polytrichus* | English Wild Thyme | Wildman Steve Brill | Home | https://wildmanstevebrill.com/ |
| 142 | *Thymus polytrichus* | English Wild Thyme | Wildman Steve Brill | Contact | https://wildmanstevebrill.com/contact |
| 142 | *Thymus polytrichus* | English Wild Thyme | Wildman Steve Brill | Events | https://wildmanstevebrill.com/events |
| 740 | *Ulmus laciniata* | Japanese elm | Eatweeds | The Traditional and Modern Uses of Japanese Pagoda Tree | https://www.eatweeds.co.uk/japanese-pagoda-tree-styphnolobium-japonicum |
| 93 | *Urtica dioica* | Stinging nettle | Galloway Wild Foods | Super Simple Nettle Soup, with some even wilder suggestions | https://gallowaywildfoods.com/super-simple-nettle-soup-with-some-even-wilder-suggestions/ |
| 93 | *Urtica dioica* | Stinging nettle | Galloway Wild Foods | Dock, Dandelion and Nettle Spring Puddings | https://gallowaywildfoods.com/dock-dandelion-and-nettle-spring-puddings/ |
| 737 | *Verbena officinalis* | Common vervain | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 737 | *Verbena officinalis* | Common vervain | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 737 | *Verbena officinalis* | Common vervain | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 372 | *Vicia cracca* | Cow Vetch | Galloway Wild Foods | Bush and Tufted Vetch – Identification, Edibility, Distribution | https://gallowaywildfoods.com/bush-vetch-identification-edibility-distribution/ |
| 101 | *Vicia sativa* | Tare | Galloway Wild Foods | Bush and Tufted Vetch – Identification, Edibility, Distribution | https://gallowaywildfoods.com/bush-vetch-identification-edibility-distribution/ |
| 101 | *Vicia sativa* | Tare | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 101 | *Vicia sativa* | Tare | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 101 | *Vicia sativa* | Tare | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 645 | *Vicia sylvatica* | Wood Vetch | Galloway Wild Foods | Bush and Tufted Vetch – Identification, Edibility, Distribution | https://gallowaywildfoods.com/bush-vetch-identification-edibility-distribution/ |
| 48 | *Vinca minor* | Myrtle | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 48 | *Vinca minor* | Myrtle | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 48 | *Vinca minor* | Myrtle | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
| 121 | *Viola riviniana* | Common dog-violet | Wildman Steve Brill | SchoolsThis hands-on environmental program focuses on common wild plants, putting children in touch with their | https://www.wildmanstevebrill.com/curriculum |
| 121 | *Viola riviniana* | Common dog-violet | Wildman Steve Brill | Day CampsThis hands-on environmental program consists of field walks in local parks focusing on common wild pl | https://www.wildmanstevebrill.com/day-camp |
| 121 | *Viola riviniana* | Common dog-violet | Wildman Steve Brill | ScoutsThis hands-on environmental program consists of field walks in local parks focusing on common wild plant | https://www.wildmanstevebrill.com/scout |
