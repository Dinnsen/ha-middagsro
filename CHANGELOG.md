# Changelog

All notable changes to REMA 1000 for Home Assistant. The version is the one in `custom_components/rema1000/manifest.json`; a new version on `main` is released by itself with its section below as notes.

## [1.9.0] - 2026-10-21

### Changed
- **Steadier against REMA's and Tjek's hiccups.** A maintenance page instead of JSON, a busy server (429, 502-504) or a refused token right after it was renewed no longer end in tracebacks or a "log in again" prompt: busy answers are tried again after a moment, REMA's trouble is told apart from a wrong password, and only one token renewal runs at a time however many requests hit the wall together.
- **Sending can't double up.** Each item is marked sent the moment it is on the REMA list, so if REMA fails halfway the next send only sends the rest – and two sends can't run at once. The list is changed by one thing at a time (a send, a quick add, a clear).
- **Fewer requests to REMA**: the primary list's id is remembered for a while (and read again if the list is gone), Tjek's products of an offer are remembered for six hours, and the Tjek key isn't looked for again and again when the page can't be read.
- **Overvågning and other chains match better**: a watched text matches whole words (*ris* no longer fires on *Kg-pris*, *te* not on *tomater*), frozen is not fresh across chains, *Spar 30 %* is not a fat percentage, a 2 kg bag is not compared with a 500 g pack, *2 stk. / 175 g* is priced as two, *pr. 1/2 kg* is half a kilo, and a long description no longer spoils a match. A watched REMA product is also found in REMA's own next avis before REMA prices it. The matching runs off Home Assistant's event loop, so a long watch list no longer freezes anything.
- Comparing a plan's items with other chains counts from today, not the plan's first day, and skips what is bought.
- Food aviser called *Julemad* or *Haveavis* are no longer dropped as non-food.

### Fixed
- A damaged file of first-seen aviser no longer stops the offers; entries older than 90 days are forgotten.
- The dinner sensor and the calendar are no longer polled (they are told when plans change); the calendar's end date is exclusive, as Home Assistant expects.
- The account's stored plans and offers are deleted when the account is removed.
- Diagnostics no longer include the family's allergies and what they avoid (counts only), and include the chains and watch list state instead.
- A login the site itself fails (maintenance, a changed page) shows "cannot connect" instead of an unknown error with a traceback.

## [1.8.1] - 2026-10-21

### Fixed
- The plan check no longer calls these repeats: *pasta med kødsovs* and *pasta carbonara*, *tomatsuppe* and *græskarsuppe*, *kyllingegryde* and *oksegryde* – what is on the pasta is the dish, and only kinds that define a dish (pizza, lasagne, burger, frikadeller …) count as the same. *Laksefilet* is still *laks*.
- A fixed day passes its check when the dinner is what the day says (*rugbrød med æg* on *Rugbrødsdag*) or the AI marks it as the fixed day; before, the default rye-bread thursday failed every time and cost two needless AI rounds.
- When the AI is asked to put a plan right, it is shown its own previous plan and told to change only the days named, so the rest stays.
- The shopping list from the family's own recipes: an item two recipe days share is bought for both, a line one of them keeps is no longer dropped, and *løg* no longer takes the *hvidløg* line (nor *mælk* the *havremælk*).
- Recipe amounts like *1½ dl*, *1/2 l* and *2 x 400 g* are read right, and the recipe on the day is scaled to the household like the shopping list (with the servings it is for now).
- *Overrask os* is checked like any other plan (leftover days, time, dislikes).
- A milk allergy no longer prefers lactose-free dairy, which still has milk protein.

## [1.8.0] - 2026-10-21

### Changed
- **The plan is checked, not just asked for.** The AI often broke the rules (salmon three weeks running, a favourite remade its own way, pita bread with a kebab pizza). Now every plan is checked after the AI answers: no dish from the last weeks again (by its main dish – *laks med pasta* is *laks med ris*), nothing the family dislikes, no dish twice in a week, the right number of leftover days from a double portion, the vegetarian count, fixed days (*torsdag: rester* must be leftovers), the weekday time limit and the budget. What is wrong goes back to the AI, up to twice, and the best try is kept. What it still couldn't fix is shown on the plan, under the price.
- **The last weeks** are what the family actually had: for every date the plan that was sent (or the newest), not every draft that was ever made – and the favourites and recipes they just had are not offered as inspiration.
- **Your own recipes are used as they are.** A dinner that is one of your favourite dishes, or a ❤️ recipe in the collection, uses that recipe – its ingredients go on the shopping list in amounts for your household (children count for less), with the REMA products it names – instead of the AI's own version of the dish. The AI is told so for every favourite that has a recipe, and the plan is tied to it even when the AI forgets.
- **Products:** a dish made of the ingredient is not the ingredient (a kebab pizza is no kebab, a chicken wrap no chicken), fruit and vegetables are fresh unless the line says frozen (*frisk broccoli* was frozen broccoli), and frozen is not fresh the other way round.
- The AI is told how many adult portions the household eats, so amounts fit (a one-year-old is not an adult).
- Swapping a dish also keeps away from the last weeks' dishes, and a dish from the collection uses the family's recipe.

## [1.7.0] - 2026-10-20

### Added
- **Faste varer only once on the REMA list** (*Indstillinger → Indkøb og varer → Faste varer hver uge*): with *Send ikke faste varer, der allerede står på REMA-listen* on, a must-have that is on the list in the REMA app and not bought is not sent again, so its amount isn't added on top. The note after sending says how many were already there. Off by default ([#28](https://github.com/Dinnsen/ha-middagsro/issues/28)).

## [1.6.0] - 2026-10-20

### Added
- **Overvågning (watch list)** at the top of *Favoritter*. Tap the 🔔 on a favourite, a product card or a search result to watch it. The list shows where each watched item is on offer – in REMA (now, or from next week's avis) and in the chains chosen in the settings – with the price and a button that puts it in the basket (REMA) or on that chain's shopping list.
- Watch something REMA doesn't sell, or any brand: type it and choose *Overvåg "…" som tekst*. A text is on offer wherever an avis offer has all its words, REMA's own avis included.
- **Add favourites yourself**: a search field in *Favoritter* finds REMA's products; *+ Favorit* adds one next to the products with a heart in the REMA app (*Fjern* takes it off again).
- **Notifications only for the watch list** (*Indstillinger → Overvågning og beskeder*): choose the phone (Companion app) or a notification in Home Assistant. The list is checked every 3 hours, and each new offer is told once, with 🔔 in the title, 🛒 for REMA and 🏷️ for other chains, the product photo, and a tap opens Middagsro. *Tjek nu og send besked* checks right away.
- A **Ryd** button next to every search field.

## [1.5.0] - 2026-10-20

### Changed
- **Send empties the basket.** The items sent to the REMA app leave the list under *Indkøb*, and the next send only has what was added since – nothing ends up twice in the app. A note says how many items were sent and when, and **Genskab seneste kurv** puts the last sent items back (e.g. if the REMA list was lost). The plan's total still counts everything.
- The send buttons say how many items will be sent, and are greyed out when everything is sent.

### Fixed
- An offer from REMA's avis that the webshop doesn't sell (a *partivare*, e.g. a glue gun) can be put on the list: it gets the avis's name and price, and becomes REMA's product if REMA has it when the list is sent. Before, it failed with "REMA 1000 doesn't have that product".
- Searching in the basket also shows matching offers from REMA's avis, so partivarer can be found there.

## [1.4.4] - 2026-10-20

### Added
- Writing a recipe yourself (or editing one): type an ingredient and REMA's products for it show up under the field. Tap one to link the ingredient to that product – the shopping list then gets the very item when the recipe is put on the plan. *Fjern* takes the link off again.

## [1.4.3] - 2026-10-19

### Changed
- Each release has a `middagsro.zip` that HACS installs from, so GitHub counts the downloads – shown as a badge at the top of the README. Nothing changes in Home Assistant.

## [1.4.2] - 2026-10-19

### Changed
- The recipe pop-up is at most 80 % of the screen, with a ✕ at the top and the buttons at the bottom kept in place while you scroll. On a phone the fields sit two by two and the buttons are smaller.

## [1.4.1] - 2026-10-19

### Added
- Search in REMA 1000's recipes (*Opskrifter → REMA-opskrifter*), like on REMA's own site. Empty the field to go back to the popular ones.

## [1.4.0] - 2026-10-19

### Added
- **REMA 1000's recipes** under *Opskrifter → REMA-opskrifter*: popular, newest, *Avisopskrifter* and REMA's categories (*Aftensmad*, *Nem hverdagsmad*, *Mad for børn*, *Kødfri* …). Each card shows the time, a rough price and how many of its items are on offer now.
- A REMA recipe can be saved in the collection – with its photo and every ingredient linked to REMA's product – or put straight on a day of the plan. Saving it again updates the same recipe and keeps its rating.
- In the plan: tap a dish and **Vælg en REMA-opskrift** to swap it for one of REMA's. The shopping list gets the products the recipe is made for; basic items only when the family doesn't have them.

## [1.3.1] - 2026-10-19

### Fixed
- Days skipped at the start of a plan ("vi har mad søndag til tirsdag") belong to that plan, so an older plan's dishes no longer fill them in the week, the calendar or the *dinner today* sensor.

## [1.3.0] - 2026-10-19

### Changed
- One plan for the week. The plan page no longer splits the week into *Resten af denne uge* and the newest plan: it shows every day from the family's first weekday to the last planned day as one plan, *Madplan uge 43*. Each day comes from the newest plan that covers it, so a plan made from Wednesday replaces the old one from Wednesday on, also on the days it skips. Next week's plan follows under its own week heading, and days that have passed are dimmed. When days come from an older plan, the price says which days the shopping list covers.
- The week's recipes, *Sæt på madplanen* from the collection, the calendar and the *dinner today* sensor use the same rule, so they always show the same dinner for a day.

## [1.2.5] - 2026-10-19

### Fixed
- Deleting a meal plan updates the meal plan sensor and calendar right away; before, they showed the deleted plan until the next change.

## [1.2.4] - 2026-10-19

### Fixed
- A meal plan can no longer be made for a week whose avis isn't out yet. Before, it was made with the running week's prices, which end before the plan starts. Until the new avis is out, *Første dag* is today (the rest of this week), the date picker stops at the last day of the avis, and the plan ends that day. Once the new avis is out, the family's usual first day is back.

## [1.2.3] - 2026-10-19

### Changed
- The price comparison from favourites is smaller: at most 80 % of the screen, with a ✕ at the top and *Luk* at the bottom that stay in place while you scroll. Each result is two lines on a phone, with the button under the price.
- The help under the meal plan ("Tryk på en ret …") is behind a small ?.

### Fixed
- *Billigst* in a search is only the very kind asked for: REMA's search also finds near misses such as grisekød for oksekød, and those are left out. Items with other words that make them another product (oksekød 35 % grønt) or another fat % are still shown, but cannot be the cheapest.

## [1.2.2] - 2026-10-19

### Fixed
- The shops' logos fill their circle on phones too – in the search on the front page, the shopping list and favourites they were drawn at the size of a product photo, so only a corner showed.
- Tapping a shop on the front page opens its page at the top; before, the page's start was hidden under the bar at the top, so it looked as if it jumped down to the search field.

## [1.2.1] - 2026-10-19

### Fixed
- The results of a search on the front page go away again: empty the field (or tap its ✕), tap *Ryd*, tap *Madplan* again or go to another tab.

## [1.2.0] - 2026-10-19

### Added
- **REMA 1000 among the shops on the front page:** its logo comes first, and its page shows all the offers in REMA's avis; *+ Indkøb* puts one on the shopping list (as REMA's product, or the avis's text for an item only sold in the shops).
- **Search every shop** under the logos: a product's prices at REMA and in the other shops' offers, compared per kilo, litre or piece, with the cheapest marked. Put it on the REMA shopping list or on the cheaper shop's list.
- **Favourites:** every favourite has *Sammenlign priser*, which opens the same comparison; when another shop is cheaper, its logo and price are shown and can be tapped.

### Fixed
- Favourites cheaper in another shop were missed when the other shop's name for it was a compound word or had more words ("mælk" in "Arla Letmælk"); the chains' logos are now always read.

## [1.1.0] - 2026-10-19

### Changed
- **The integration's id and folder are now `middagsro`** (before `rema1000`), and the repository is `Dinnsen/ha-middagsro`. Add **Middagsro** under *Add integration* after updating: it finds the old REMA 1000 setup and moves the meal plans, settings, recipe collection, device and entities over – the entities keep their IDs, and there is no new login. Actions are now `middagsro.…`. The home-screen app's old address (`/rema1000_app/app.html`) still works.

## [1.0.0] - 2026-10-19

The integration is now called **Middagsro**. It is still about REMA 1000 and its shopping list; the new name and icon are its own.

### Changed
- **New name, icon and logo:** Middagsro, with an AI spark over a bowl between a knife and fork. The panel, the sidebar, the home-screen app, HACS and the device are renamed. The technical id stays `rema1000`, so installations, automations and entity IDs are unchanged (new installations get `middagsro_…` entity IDs). The repository is now `Dinnsen/ha-middagsro`; GitHub forwards the old address.
- **Settings in sub-pages:** meal plan and week, the family, dishes, shopping, what the AI must remember, nutrition, other shops, Mealie and the app – each with a summary of what is chosen.

### Added
- **Recipe collection** (*Opskrifter → Opskriftsamling*): search, sort and filter the family's recipes; open one in a popup to edit its name, times, ingredients and steps, or put it on the meal plan on a chosen day (its items go on the shopping list).
- **👍, 👎 and ❤️** on every dinner in the plan, in the rest of this week and on the recipe – and in the collection. ❤️ is a favourite (with 👍, and a red heart). Tap again to take it back; 👍 after 👎 changes it. The rated dish is saved in the collection with its recipe. New plans and swap suggestions use favourites and liked dishes when they fit the offers, and never disliked ones.
- **Add a recipe from a link:** the recipe is read from the page's recipe data (or by the AI from its text) and shown to be checked before it is saved. The link is not kept. Pages on the home network can't be read.
- **Overrask os** (surprise us): a meal plan with dishes the family has never had, still within budget, allergies and rules.
- **Offers from other shops** (*Indstillinger → Andre butikker*): Netto, Lidl, føtex, Bilka, 365discount, MENY, SuperBrugsen, Kvickly, Brugsen, SPAR, Løvbjerg, Min Købmand and ABC Lavpris, from their own aviser on Tjek. Their round logos on the front page open a page with their food offers. The shopping list and the favourites show when an item is cheaper in one of them that week (the same kind of item, compared per kilo, litre or piece). Tapping the logo moves the item to a list for that shop under the REMA list (not sent to the REMA app), where it can be ticked off, changed, deleted or moved back; *Ryd kurven* removes what was bought.

## [0.10.0] - 2026-10-18

### Added
- **Mealie** (when the official Mealie integration is set up in Home Assistant; switch it on under *Indstillinger → Mealie*):
  - **Start from the family's own recipes:** the AI is shown the recipes in Mealie and uses one when it fits the week's offers and the rules, else it makes up its own dish. A dish from Mealie keeps Mealie's ingredients and steps, and its shopping items follow the recipe. Swapping a dish suggests the family's recipes too.
  - **Gem i Mealie:** save one of the plan's recipes in Mealie, with ingredients, steps, servings and times.
  - **Mealie's calendar:** the plan's dinners are put in Mealie's meal planner – as the recipe when it is in Mealie, else as a note – and kept up to date when a dish is swapped or deleted or a day is skipped. *Sæt ugen i Mealie-kalenderen* does it by hand.

## [0.9.0] - 2026-10-18

### Added
- **Delete or skip a day:** tap a dish – also in *Resten af denne uge* – to delete it (the day is empty, and a new dish can be found with *Find en ret*) or skip the day. The dish's own items leave the shopping list, and its leftovers go with it.
- **Change shopping items:** tap an item in the shopping list to change how many, put another REMA product on it (search as in the shopping list) or delete it. An item changed by hand keeps its product when offers are matched again at 02:00. REMA's nutrition per 100 g is shown for the product.
- **Det skal AI'en huske:** standing points for every plan, recipe and suggestion – e.g. *Vi vil altid have frisk broccoli og fettuccine med spinat til laksefilet* – on the plan page and in the settings, written or dictated with the microphone (the browser's speech recognition, or Home Assistant's own speech-to-text in the app). Each point can be edited and deleted. The wishes for the next plan can be dictated too.
- **Nutrition targets** per adult's dinner: kcal from–to and protein/carbohydrate/fat in percent, aimed for as closely as possible. Recipes now come with the AI's estimate of the nutrition per portion.
- **Sundhed (health)** tab: nutrition per dinner and on average against the targets – the AI's estimate and as REMA's own product data adds up (nutrition per 100 g of the products bought) – the official Danish dietary advice for what the dinners hold (vegetables, fish and fatty fish, red meat, legumes) and the share of the basket with the Keyhole label, organic and ASC/MSC.

### Fixed
- **No zooming** in the panel and the home-screen app (pinch, double-tap and the zoom on text fields on iPhone).
- A new plan with skipped days no longer shows the running plan's dinners for those days under *Resten af denne uge*: the new plan's whole period replaces it.

## [0.8.1] - 2026-10-18

### Fixed
- **Offer items are matched again at 02:00 on the shopping day** (Thursday's at 02:00 on Thursday), when REMA has the offers' products and prices – also when the plan isn't sent automatically. A plan is made from the avis days before, when a new offer product isn't in REMA yet: week 43's salmon offer got 3 × 225 g salmon at the normal price, while REMA's *HEL LAKSEFILET* 600 g for 89 kr only appeared on Sunday. Sending the list also looks at the offers again first.
- A new button, *Opdatér tilbudsvarer*, in the shopping list does it by hand (for plans made before this version).

## [0.8.0] - 2026-10-17

### Added
- **Swap a dish:** tap a dish in the meal plan to see its recipe or get three other suggestions from the AI (following the family's rules and using the week's offers). The chosen dish gets its own shopping items – the old dish's items leave the list, items shared with other dishes stay – and a new recipe; leftovers of it follow along.
- **Basic items in the plan** (*Basisvarer i madplanen*): a window in the shopping list with the basic items from the settings (salt, oil, butter …) that the recipes use, with how much. *Tilføj til indkøb* puts one on the list as the REMA product that fits the family's rules (the recipe's own word is searched for, e.g. *hvedemel*).
- **Search and add products** to the plan's shopping list, both the shopping day's and the one for later in the week. Added items can be removed again.

## [0.7.0] - 2026-10-17

### Changed
- **Avis items REMA doesn't have yet.** Some offers are for products that aren't in REMA's webshop before the offer starts, or at all (a *partivare*, e.g. *REMA 1000 Laksefilet 600 g* for 89 kr in week 43). A meal plan item built on such an offer now gets the avis's name and price (*Avispris*) instead of another product at its normal price (3 × 225 g salmon for 132 kr). When the list is sent, the item is looked up again: REMA's product if it has it by then, otherwise free text with the avis's name, as the webshop does.
- **Automatic sending waits for REMA:** a plan made when the new avis is out is sent at 02:00 on the shopping day (the Thursday items at 02:00 on Thursday), when REMA has the week's products and prices. A waiting send survives a restart.
- **Recipes use the dish's own items.** The AI now says which items on the shopping list each dish uses, and the recipe gets only those (with what is bought), so the lasagne no longer uses the fresh tomatoes meant for the snack vegetables. Both prompts ask for the everyday ingredients a Danish family uses, such as chopped tomatoes in a can for meat sauce and lasagne.

### Fixed
- **Offers with products Tjek lists without REMA's id** (*Arla Skyr Airy* in the Karolines Køkken/Cheasy/Arla offer) are found by Tjek's name or the avis's text; before, only the products with an id could get the offer.
- An **insert** (*Uge 42 Indstik*), which is out on Wednesday before it starts, is no longer taken for next week's avis. Its offers are in the week's avis already, so it isn't read.

## [0.6.2] - 2026-10-17

### Fixed
- **Meal plans:** a product found through an offer must still be what the item is (no meatballs for kebab when the AI picks the wrong offer), and when several products cost the same, the biggest package is chosen.

## [0.6.1] - 2026-10-17

### Fixed
- **Meal plans:** when the AI searches more broadly than the item is called (*laks* for *Laksefilet*), products that are what the item is called are preferred, so salmon fillet isn't swapped for a cheaper salmon pastry.

## [0.6.0] - 2026-10-17

### Changed
- **Avis offers are matched to REMA's products by id.** Tjek, which publishes the avis, knows which of REMA's products each offer covers (the webshop shows them when you open an offer). Favourites and meal plans now use those product ids, so the right products get the avis price – also when the names differ (*Lækkert & Nemt Grøntsagsblanding*, *grise- og kalvekød*). An offer whose products aren't in the webshop (a *partivare*) gives no avis price. The strict text match from 0.5.6 is only used when an offer can't be looked up.
- A meal plan item built on an offer gets one of that offer's own products, fetched directly from REMA.
- *Gravad laks* is no longer chosen for salmon fillet.

## [0.5.9] - 2026-10-17

### Fixed
- **Meal plans**, found with a test plan on the real avis for week 43:
  - An item REMA already has at an offer price still gets the avis's lower price next week (minced chicken 25 kr in the avis, not this week's 29 kr).
  - When the AI's search word only finds something else (*laks*: smoked salmon), the item's own name is searched too (*Laksefilet*), and smoked (*varmrøget*, *koldrøget*) products count as different products.
  - *Ved køb af flere end 6 stk.* in the avis text is a limit, not a size.

## [0.5.8] - 2026-10-17

### Fixed
- **Avis sizes** are compared per kind (grams, litres, pieces), so a piece count in the avis text no longer hides the weight or volume: a 6-pack of 1.98 l Pepsi Max is not the 1.5 l offer, and *Kærgården* 200 g is found again. Purchase limits (*Max. 6 stk.*) are not read as sizes.

## [0.5.7] - 2026-10-17

### Fixed
- **Avis offers**, found by checking 0.5.6 against the real avis: a brand in front of an offer is for all of it (*Lotus Premium Toiletpapir eller køkkenruller* is not REMA's kitchen roll), a heading of one word only covers every variety when the size is of the same kind (*Kærgården* 200 g, but *Æbler* is not apple juice), and pieces count as a size (8 eggs are not the offer on 10).

## [0.5.6] - 2026-10-17

### Fixed
- **Avis offers are matched strictly** to REMA's products, in meal plans and in the favourites. A product only gets an offer's price when the offer is for that very product: every word of its name is in the offer, the brand fits (REMA's own cream doesn't get the price of Karolines Køkken's), the size is in the offer's range, the fat percentage is the same (8-12%, not 15-18%) and organic matches organic. Before, a loose match put wrong products and prices on the list, e.g. smoked salmon for a salmon fillet offer, an egg stand for eggs, and many wrong favourites next week. A favourite or item that doesn't fit an offer is better shown at its normal price than at someone else's.
- **Meal plans:** an item built on an offer gets the product that offer is for (also searching for the offer's own name), and otherwise the best normal match. Weighed items are matched to products sold by weight, so 3 kg potatoes are no longer one sweet potato. Short words only match the end of a compound word (*æg* is *skrabeæg*, not *æggestand*).

## [0.5.5] - 2026-10-17

### Changed
- **Favourites this week** use REMA's own prices, as in the app. On Saturday, when REMA has no price, the last known one is used until REMA's new prices start on Sunday at 02:00. Offers in the avis that start Thursday are shown before that with the avis price and a blue *fra tor* badge; from Thursday 02:00 REMA's price is used.
- **Favourites next week** use the avis's prices as soon as the avis is out (REMA only has them from Sunday 02:00), with the avis text, so you see what the offer covers. Thursday offers get the blue badge.
- **Meal plans** use the avis price for items built on an avis offer while REMA doesn't show the offer yet, marked *Avispris*. Only for the product that is on offer (an organic product doesn't get the price of a non-organic offer).
- **Two baskets** with *Vi handler også sidst på ugen*: the shopping list is split into the shopping day and Thursday, each with its own send button. *Send til REMA-listen* and automatic sending send only the shopping day; the Thursday items are sent on their own. The action `rema1000.send_meal_plan` has a new field `part` (`main`, `late` or `all`, default `main`).
- Before-prices: during an offer REMA often has no normal price; the normal price after (or before) the offer is shown.

## [0.5.4] - 2026-10-17

### Added
- **Offers from Thursday:** a new setting, *Vi handler også sidst på ugen* (we also shop late in the week). Off (the default), the meal plan only uses offers that run on the shopping day, so no dish is built on an offer you can't get yet. On, the AI may use offers that start Thursday in dishes from that day, and those items are marked *Købes tor* (buy Thursday) and priced on that day.
- **Favourites:** offers that only start Thursday are found too and marked *fra tor* until they start – this week and next week.

## [0.5.3] - 2026-10-17

### Fixed
- **Saturdays:** REMA's prices for the week end before the avis does, so on Saturdays many products had no price and the week's offers were missing – in the favourites and in meal plans made that day. A price that ended now lasts until the week turns at Sunday 00:00 (unless a new price replaced it), like in the shop.
- **Favourites next week** are checked in the middle of the coming avis week. The check ran an hour after the avis starts, before REMA's prices for that week begin, and found no offers.
- **Meal plans for next week** are priced on the plan's first day, so prices, offers and the total match the week you shop in and the avis the dishes are built on. Something typed for the list is still priced now.

## [0.5.2] - 2026-10-17

### Fixed
- When tonight is skipped in the running plan, the rest of its week is still shown on the plan page and in the recipes.

### Security
- The home-screen app no longer loads its Home Assistant connection library from a CDN; it is bundled with the integration (home-assistant-js-websocket 9.4.0, Apache-2.0).

### Docs
- README in English, with the Danish README in `README.da.md`.
- `SECURITY.md` for private vulnerability reports, and issue forms for bugs and ideas.

## [0.5.1] - 2026-10-17

### Changed
- The knife and fork sit in the centre of the round badge on the icon (panel, HACS and the home-screen app).

## [0.5.0] - 2026-10-17

### Added
- **Ønsker til madplanen:** a button on the plan page opens a small popup for free text, e.g. what in the fridge must be used before a date, or a dish on a given day. The wishes are used in the next plan only (also when it is made automatically) and then removed.
- **Tonight and the rest of this week:** while next week's plan is ready, the plan page shows the remaining dinners of the plan that is running now, and the recipes open on tonight's dish.
- **Favourites this week and next week:** a switch between *Denne uge* and *Næste uge*. Favourites that look like something in the avis are checked with REMA 1000 at a time that avis runs. Until next week's avis is out, *Næste uge* shows this week's offers.
- Every button that uses AI is marked with an AI icon, and so is the *Make meal plan* button entity.

### Fixed
- Favourites on offer this week are checked against the avis too, not only by the single price in REMA's favourites list, which could leave the list empty.
- The plan's name ("Madplan uge 43") is set from the plan's dates instead of by the AI, which could copy the example week.
- Avis dates in the panel are shown as local days (an avis starting 22:00 UTC the day before showed one day early).

## [0.4.0] - 2026-10-13

The first release ready for HACS, on the Platinum level of Home Assistant's quality scale.

### Added
- **Change login** (*Reconfigure*) for e-mail and password.
- **Diagnostics** with e-mail, password, tokens and personal data removed.
- **Repairs:** a message when no AI task is set up for the meal plan.
- Translated error messages (Danish and English) everywhere.

### Fixed
- In the panel on a computer, the *Tilbud* and *Øko* badges stay next to the product name instead of filling the row.
- On a phone the plan's price lines up with the rest of the card.

### Quality
- Full test suite with at least 95 % coverage, strict typing, Ruff, hassfest and HACS validation on every change.

### Docs
- New README with screenshots of every feature, installation, set-up, every setting, entities, actions, examples, troubleshooting and removal.
