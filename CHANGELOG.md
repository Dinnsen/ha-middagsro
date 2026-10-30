# Changelog

All notable changes to REMA 1000 for Home Assistant. The version is the one in `custom_components/rema1000/manifest.json`; a new version on `main` is released by itself with its section below as notes.

## [2.12.0b3] - 2026-10-30

### Added
- **Find varer igen** under *Indkøb → Flere muligheder*: every item of the plan that isn't sent is read again from its words and matched with the rules as they are now – same dishes, one line per thing, and what isn't sure is looked for in Bilka. What you chose, kept, left out or moved to another shop stays as it is. So a plan made with an older version gets the newest fixes without making a new plan.

## [2.12.0b2] - 2026-10-30

Beta: fixes from a real week-45 plan made with 2.12.0b1.

### Added
- **Bilka for what REMA has no sure product for:** with Bilka among *Andre butikker*, a line Middagsro isn't sure of in REMA (galangarod, romainesalat …) is looked for in Bilka ToGo by the same rules. A sure match goes on Bilka's list under Indkøb at Bilka's price (and can be moved back); a line Bilka isn't sure of either stays among *Usikre varer*.

### Fixed
- **Behold, Udelad, Behold alle and Glem valget did nothing but show an error:** the panel's command for them was never registered in Home Assistant ("Unknown command").
- **Æg in the Thursday basket without being on offer:** a dish built on Thursday's skrabeæg offer, with the family's organic eggs chosen, put the eggs in the Thursday basket at the normal price. Only the offer's own product waits for its day; the rest is bought and priced on the shopping day.
- **A colour or sort the line names is kept:** "rød peberfrugt" is never GUL/ORANGE PEBER and "romainesalat" never icebergsalat or hjertesalat; a product that doesn't say it is the red one (ØKO. PEBER) is marked for a check.
- **An offer's product must be what the line is called:** "Mini-baguettes" searched as "brød" no longer gets the Schulstad offer's sødmælksbrød (baguettes and flutes are their own thing in the catalogue).
- **"8 pølser" of an avis pack** were 8 packs; they are counted by what a sausage weighs. "Rød peber" and "rød peberfrugt" are one line.
- **A recipe's instructions are not the name:** "Kaffirblade, fjern stilken i midten og striml bladene fint" is searched as kaffirblade.

## [2.12.0b1] - 2026-10-30

Beta: the matching of ingredients to REMA's products rebuilt. Please check the shopping list of a new plan closely and report what is wrong.

### Added
- **Usikre varer – a check before the list is sent:** when Middagsro is not sure a product is the right one for an ingredient, the line is marked *Tjek* or *Usikker* on the shopping list, with the other products it could be. A yellow box at the top lists them: keep the product, choose another, search for one, or leave the line out. The new setting **Indstillinger → Indkøb → Usikre varer** decides what a send does with lines nobody has looked at: wait for the check (default – an automatic send at 02:00 goes without them), send them as chosen, or leave them out.
- **Middagsro remembers your choices:** a product you keep, choose or put on a line yourself is the one that ingredient gets in the next plans (marked *Jeres valg*); a product you leave out is never taken for that ingredient again. *Glem valget* on the line undoes it.
- **An ingredient catalogue:** some 250 common ingredients with how they are searched, what one piece weighs (so "2 løg" from a kilo bag is one bag, not two, and "3 fed hvidløg" one bulb), whether they are fresh, canned or dried, and the words that make a product something else ("skalotteløg" is not løg, "stødt chili" is not fresh chili, "indbagt laks" is not laks).
- **REMA's own shelf decides what a product is:** department and category gate every search result, so cup noodles can never be nudler, a can of pepper strips never a fresh peberfrugt, grill skewers never food – and a line only gets a ready meal, a snack or a drink when it asks for one (a Friday frysepizza).
- **Allergies and avoided foods are checked:** every dish of a plan, every AI recipe and every item a recipe adds are checked against word lists for what the family can't eat; the AI is asked to put a dish or recipe right, and an extra item with a conflict is never added. (Gluten and lactose are left to the product choice, which prefers GLUTENFRI and LAKTOSEFRI products.)
- **Structured answers from the AI:** AI Task is given the shape of the plan, the recipe and the product choice, so the answer is valid JSON with the right keys. After the list is priced, one question to the AI picks among the products found for the uncertain lines.
- A corpus of REMA's real search results (164 lines, among them every error of a real week-45 plan) guards the matching in the tests.

### Changed
- **One line per thing:** the plan's "Løg", "Løg, i både" and "Stort løg" become one line with the amounts added up; the same for a web recipe's second onion.
- **Recipe text is not shopping:** a heading ("Dej:", "Fyld:"), the tin ("Tærteform"), water and remarks ("Server med ris", "Kan erstattes med skyr") never reach the list; "Evt. chili" is chili.
- **The usual size, not the cheapest package:** "2 dåser kokosmælk" is two normal cans, not mini cans of light coconut milk; a "vej selv" loose item is not chosen over a bag; "kokosmælk light" is only chosen when asked for. A percent asked for is kept ("creme fraiche 18%" is not the 38%). Frozen meat, poultry or fish only when clearly cheaper than fresh.
- **The avis offers shown to the AI** are food for dinner the family can eat: no household goods, sweets or drinks, nothing they avoid or are allergic to. Vegan and vegetarian households get the rule spelled out. The AI's checklist is only for the family's own rules – the other rules are checked by Middagsro – and the corrections from a previous try come last in the instructions, where the model weighs them most.
- A plan is checked against the rules before its list is priced (a worse try costs no searches), REMA's answers are kept for the rounds of one generation, and if the AI fails on a later round the best try so far is the plan. The budget feedback separates the fixed weekly items the AI can't change.
- A fixed day at a restaurant is no longer a leftovers day.

### Fixed
- Many wrong products from a real plan: cupnudler for "oksekød i strimler", pepper strips in a can for peberfrugt, soybeans for soja, bearnaise for fishsauce, ground chili for fresh chili, skalotteløg for løg, a date bar for peanuts, onions bought three times, 3 forårsløg as 3 bunches, a tart scaled by four, 1 kg chicken breast counted as 2 pieces, mini cans of light coconut milk.
- A recipe link's redirects are followed one hop at a time, each address checked, so a page can't lead to the home network.

## [2.11.0] - 2026-10-29

### Added
- **A meal plan across the shops:** under *Andre butikker*, *Byg madplanen på tilbud fra alle de valgte butikker* gives the AI every chosen chain's offers (Netto, Lidl, føtex …) next to REMA's, to pick the week's best across them. An item built on another shop's offer goes on that shop's own list under Indkøb at the offer's price (and can be moved back to REMA); the rest is bought at REMA as before. Off by default: then the other shops are for comparison, as until now.

### Changed
- **Det skal AI'en huske is followed:** the family's standing rules come first in the instructions for the plan and for every recipe, before everything else, and the AI must answer for each rule in the plan's checklist (shown under *Krav-tjekliste*).
- **A fixed day is made as the family describes it:** "Spaghetti og kødsovs: en pakke spaghetti, kød, pastasovs og ost" gives a recipe with just that – no extra herbs, bouillon or tomato purée, and nothing is added to the shopping list for it.
- **Recipe notes are not shopping:** "Lime, saften herfra" is lime, "Citronsaft (friskpresset)" is a lemon, "Rød chili, hakket (mængde efter smag)" is red chili, "2 stængler citrongræs" is citrongræs, "Purløg (tørret eller frisk)" is purløg – so they are matched to REMA's products instead of being added as free text.
- **Cupnudler are not nudler:** instant noodle cups are the last choice for a dish's noodles.

## [2.10.1] - 2026-10-29

### Fixed
- **A REMA 1000 account without a shopping list** (a new account, or one whose list was never made in the app) could not be set up: "The account has no shopping lists", and Home Assistant kept retrying (#62). Middagsro now starts with an empty list and finds the list as soon as one is made in the REMA 1000 app; sending to the list until then says so in Danish.

## [2.10.0] - 2026-10-29

### Added
- **Opdater madplan:** when a setting the plan is made from changes after the plan was made (days, leftover days, fixed days, household, budget, what to avoid …), the plan shows *Opdater madplan*. It starts from the plan you have – same first day and skipped days – keeps as many dishes as possible on their days and changes only what the new settings need; the updated plan takes the old one's place. Not once the shopping list has been sent (then a new plan is the way). After saving such a setting, the panel says so.

### Changed
- **A fixed leftovers day counts as a leftover day:** with 2 leftover days and *Rester* fixed on Thursdays, the plan has Thursday and one more leftover day – not three. The AI is told so, and the plan's check counts it the same way (so a plan with Thursday as its only leftover day no longer fails "0 restedage"). A fixed leftovers day may also be on a day otherwise kept free of leftovers.
- **Ny madplan takes less room:** *Tilpas dagene* (skip a day or choose its dish) is folded away until you open it – it stays open while days are tailored – and *Månedens frysermad* is its own folded card below.

## [2.9.0] - 2026-10-29

Built on the work of @nagels in #59 – thank you.

### Added
- **BilkaToGo's cart:** log in to Bilka with the Salling Group account from the BilkaToGo app and choose a Bilka store; assortment and prices follow that store, and the meal plan's groceries are sent to the same cart as in the app (ordering and pickup time stay in BilkaToGo). Products without a sure match are not sent but listed apart, with *Søg manglende varer igen*. Transfers keep receipts, so a repeated tap or a retry after a timeout never adds an item twice. The cart is read once for a whole send, instead of several times for each item. **The login is optional:** with empty fields Bilka works as before (prices on every item, the list in Home Assistant).
- **The store in the BilkaToGo app:** Middagsro makes the chosen store the active pickup store in the app when Home Assistant starts and before it changes the cart, and the setup says so.
- **Portions:** normal, 25 % more, 50 % more or double under *Familie og portioner*, for new weekly plans.
- **Månedens frysermad:** a separate freezer plan with four or five dishes for one cooking day, with its own wishes (*Ønsker til fryserretterne*), portions chosen per dish and one combined shopping list. It doesn't change the week's plan.

### Changed
- **Tilbud og priser is first on the front page**, above the meal plan.
- **Settings regrouped:** *AI til madplanen* has its own section (right after *Ugens madplan*), the pantry items are under *Indkøb og basisvarer*, portions under *Familie og portioner*, and clearer names for several fields. *Gem ændringer* is only active when something has changed.
- **Ingredients become the right products:** chopped and peeled tomatoes ("hakkede/flåede tomater", "tomater, hakket") are always canned, never fresh; home preparation is left out of searches ("finthakket løg" → løg, "presset hvidløg" → hvidløg); fresh or dried herbs as the recipe says; stock is bought as bouillon cubes (and bouillon is no longer in the default pantry); karrypulver, svinemørbrad and oksekød til gryderet find the right product. Recipe water is not on the shopping list.
- A recipe is scaled to at most 4 times its servings (more only with bigger portions), so a misread serving count can't multiply the shopping.
- The panel's files get a new cache revision when they change, so a browser never keeps an old panel.

### Fixed
- A freezer plan that can't be made is logged, and the panel says why in Danish.

## [2.8.1] - 2026-10-28

### Fixed
- **An AI service's error in plain Danish:** when the AI can't answer, the panel showed the service's raw error (e.g. Google's "402 … prepayment credits are depleted"). It now says what is wrong and what to do: the account has run out of credit, the service is too busy right now, or it refused the key – for the meal plan, recipes, other dishes and scanning. The log gets a short warning instead of a traceback.

## [2.8.0] - 2026-10-25

### Added
- **Bilka's prices on every item, not only its offers.** With Bilka among *Indstillinger → Andre butikker*, the shopping list says when an item is cheaper in Bilka at its everyday price, and *Tilbud og priser* shows Bilka's products next to REMA's. The prices are Bilka ToGo's (the webshop's, close to a Bilka shop's).
- **Bilka as the shop with prices:** chosen in the setup (or under Reconfigure), every item is matched to a Bilka ToGo product with its price, like with REMA 1000 – the plan's total, the budget and product search work; the list is kept in Home Assistant.
- Bilka ToGo's search key is read from its webshop when it is needed (and again if it changes). Unofficial, like REMA's: it may stop working if Bilka changes the webshop.

## [2.7.1] - 2026-10-25

### Fixed
- **The right item also when the AI writes it as a list:** an item must have the thing a line is about (*grønne bønner* are beans, never *grønne druer*). Written the other way round – "tomater, hakkede", "løg rødt", "oksekød hakket 8-12%", "mælk let" – the describing word came last and was taken for the thing, so "løg rødt" could become anything red. Describing words after the thing are now skipped, for every item.

## [2.7.0] - 2026-10-25

### Added
- **Choose the shop – also without REMA 1000.** The setup starts with a shop: REMA 1000 (log in, as before) or Netto, føtex, Lidl, Bilka, 365discount, MENY, SuperBrugsen, Kvickly, Brugsen, SPAR, Løvbjerg, Min Købmand or ABC Lavpris – no login. With another shop the meal plan is built on its offer catalogue (from Tjek), an item on offer gets the avis's price and the rest are free text, and the shopping list is kept in Home Assistant (the to-do entity as before). The setup lists what only works with REMA 1000.
- **Change the shop under Reconfigure:** meal plans, recipes, budget and settings are kept, and so are the entities and their ids.
- **Also on your own to-do list** (another shop): *Indstillinger → Butik → Send også til* puts what is sent on another to-do list too, e.g. Bring!, Google Keep or Home Assistant's shopping list.
- **Indstillinger → Butik** tells which shop is used and how to change it.
- A **one-time note** in the panel tells REMA families about the choice. Nothing changes for them.

### Changed
- With another shop: REMA's recipes, product search, nutrition, favourites and price comparisons are left out of the panel; the plan's total is the offers', the AI is told the budget is a guess (no "over budget" rounds), and the budget's forecast is only what the family books. Something typed on the shopping list is added as free text.

## [2.6.4] - 2026-10-25

### Fixed
- **DK-kogebogen found nothing:** its sitemaps only have its categories. Its recipes are read from the dinner categories (*hovedretter* and *suppe*), with their real names; at most 150 category pages a day.

## [2.6.3] - 2026-10-25

### Fixed
- **Madsider found too few recipes:** only the first part of each sitemap (and of a recipe page) was read. They are read whole now, so Louises madblog, Madens Verden, DK-kogebogen and Arla find all their recipes.
- **Real titles in the results:** some sites leave æ, ø and å out of their addresses ("Aben lasagne med salsiccia"); the hits shown get the title from their page.
- A sitemap that could not be read is tried again after half an hour instead of the next day, and a site that is down keeps the recipes it had.

## [2.6.2] - 2026-10-25

### Fixed
- A recipe read from microdata (Valdemarsro) was named after the site; it takes the page's heading now.

## [2.6.1] - 2026-10-25

### Fixed
- **Arla's recipes could not be read:** the site sends a header longer than Home Assistant's web client takes. Recipe pages (also links pasted in the collection) are read with room for it.
- **Recipes without JSON-LD:** a page with the recipe as microdata (*itemprop*) is read too, and a JSON-LD block with line breaks inside its texts. A recipe opened from *Madsider* on a page with no recipe data at all is read by the AI, like a pasted link.

## [2.6.0] - 2026-10-25

### Added
- **Recipes from known Danish recipe sites:** choose the family's sites in *Indstillinger → Opskrifter og madsider* – Valdemarsro, Madens Verden, Louises madblog, DK-kogebogen and Arla. *Opskrifter → Madsider* searches them; a recipe opens to be looked over and saved in the collection, with a link back to the site. *Vælg ret* in a new plan has a *Madsider* tab too.
- **Plans from the sites:** with *Brug madsidernes opskrifter, når madplanen laves* on, the AI is offered recipes from the sites for the week's main offers (chicken, salmon, minced beef …). A recipe it chooses is saved in the collection, and its ingredients go on the shopping list.
- The sites are searched by their sitemaps (read once a day, robots.txt respected), and a recipe is only read when it is opened or offered to the AI.

## [2.5.0] - 2026-10-25

### Added
- **Scan a recipe from a cookbook:** *Scan fra kogebog* under *Opskrifter → Opskriftsamling* takes a photo of the page (or several, when the recipe fills more than one) – or picks one from the phone's photos. The AI reads it, and the recipe opens to be checked and corrected before it is saved in the collection. The photos are made smaller in the browser and only kept while the AI reads them. Needs an AI Task that can read images (Google Gemini, OpenAI, Anthropic …); a conversation agent can't.

## [2.4.1] - 2026-10-25

### Fixed
- **Errors in the panel are in Danish** (Home Assistant words its errors in English, whatever the language).
- **Moving a dish in a plan the AI made a little wrong:** a dish on wednesday with an item from thursday's offers stopped every move in the plan. Only what a move itself breaks stops it now.
- **Minced beef is beef:** an avis offer on "hakket oksekød, grise- og kalvekød eller kyllingekød" put pork and veal on the list for a line that asked for beef (the hakkebøffer). The product must be the thing the line is about, also from an offer.

## [2.4.0] - 2026-10-25

### Added
- **Move a dish up or down:** arrows under 👍 and 👎 on each day of the plan swap the dinner with the day before or after. Leftovers follow the dinner they are from and never come before the day it is made; a dish built on an offer that starts later (thursday) isn't moved before it; days that have passed stay. The place under ❤️ is kept free.
- **Choose the dish for a day yourself** when making a new plan: *Vælg ret* next to each day opens the family's recipe collection, REMA 1000's recipes and (with Mealie) Mealie's recipes. The AI plans the rest of the week around it, and the chosen recipe is put on the day with its items on the list.
- **No leftovers on chosen weekdays** (*Indstillinger → Retter, favoritter og ønsker → Ingen rester disse dage*): the AI is told, and a plan with leftovers on one of those days is sent back.
- **The shop at the top of the shopping list**, and a **REMA button on every item** that puts just that item on the REMA list in the app right away (it leaves the basket like a sent item; the rest is sent as before).

### Changed
- **Recipes with taste.** The plan takes the items that give a dish its taste (onion, garlic, spices, herbs, stock, tomato purée …), and a recipe may add cheap flavourings, which then go on the shopping list. Dishes are made of the meat they traditionally are (hakkebøffer of beef), also when another meat is on offer. A recipe with "krydderier" as one ingredient, too few steps or meatballs formed of fried mince is sent back to the AI once.
- **A dish asked for on a day is kept:** "frikadeller på onsdag" in the wishes for the plan is checked like a fixed day, and the AI is told again if it puts something else there.

### Fixed
- A shopping item is only a product whose name has the thing it is about: *grønne bønner* became *STENFRI GRØNNE DRUER* because "grønne" fitted. Now it is beans or free text.

## [2.3.0] - 2026-10-24

### Added
- **A conversation agent can make the plans** ([#43](https://github.com/Dinnsen/ha-middagsro/issues/43)). AI services that only offer a conversation agent and no AI Task – such as **LiteLLM** – can now be chosen under *Indstillinger → Madplan og uge → AI til madplanen*, below the AI Tasks. The plan, the recipes, the swap suggestions and recipes read from a link are asked of the agent, which is told to answer in JSON. Home Assistant's own agent (*Home Assistant*) is not offered: it can't write a plan.

## [2.2.0] - 2026-10-23

### Added
- **Cards for your own dashboards**, included in the integration – no resource to add, nothing to install in HACS. Under *Add card* (search *Middagsro*), with a visual editor:
  - **Week:** the week's dinners on one line, tonight marked and in view.
  - **Tonight:** tonight's dish with time, servings and type, and tomorrow's.
  - **Tonight, large:** tonight's recipe as on the *Opskrifter* page, with ingredients and steps to tick off and the timers.
  - **Shopping:** the basket, what is sent, what is on the REMA list now, and *Send til REMA* (it asks first when the list costs more than the week's budget has left, as in the panel).
  - **Budget:** what is left of the week's food budget, per day, the bar with the even pace, and the month.
  - **Bubble:** tonight, the shopping or the budget as one Bubble Card button, with Bubble Card's measures and `--bubble-*` variables.
  The cards follow Middagsro live through the new `middagsro/subscribe` (the plans, the budget, the REMA list and midnight), and all cards on a page share one connection.
- **A pop-up from every card** with that page of the panel (the day's recipe, the basket, *Økonomi*). It is Home Assistant's own dialog, so it opens above everything, also inside a Bubble Card pop-up, and closes with the back button or by pulling it down. `tap_action: panel` opens the panel instead.
- **Addresses for the panel's pages:** `/middagsro/plan`, `/middagsro/recipes/<date>`, `/middagsro/shopping`, `/middagsro/budget` and so on. The address follows what is shown, so a reload or a link opens the same page.
- **+ REMA-listen in the searches:** a product found under *Søg i alle butikker* or in the basket's search can go **straight onto the REMA list in the app**, past the meal plan's list, also when there is a plan. *+ Indkøb* still puts it in the meal plan's basket.

### Changed
- **The theme reaches further:** the panel's cards take Theme Studio's glass blur (`--theme-studio-card-backdrop-filter`), and its dialogs Home Assistant's dialog scrim (and its blur) and corners. The cards and the pop-up use Theme Studio's raised surface, chip radius and pop-up border and shadow, and Bubble Card's pop-up background.

## [2.1.2] - 2026-10-22

### Fixed
- *Økonomi*: *Sparet på tilbud* and *Ud over madplanen* only count the lists sent since the budget began, and the latter isn't shown (as a negative amount) while less is booked than the lists cost.

## [2.1.1] - 2026-10-22

### Fixed
- `middagsro.register_purchase` takes the amount as a card payment shows it, as text from an iPhone shortcut: *600,00 kr.*, *kr. 1.234,50* or *DKK 1,234.50*.

## [2.1.0] - 2026-10-22

### Added
- **Food budget (*Økonomi*).** Enter the household's monthly amount for food (*Indstillinger › Madbudget*). It is spread over the month's days (5.000 kr. in October is 161 kr. a day, 1.129 kr. a week). What a week doesn't use carries on to the next weeks of the same month (and what it overspends is taken from them); a new month starts afresh on the 1st. Everything you book counts, also the nappies.
- **Book a purchase on the front page:** the amount from the receipt, the shop (REMA 1000, your other chains or *Andet*) and the day. The card shows what is left of the week, the amount per day for the rest of it, a bar with a mark for an even pace, and what the week's lists still to be bought are estimated at. The list you sent today can be booked with one tap.
- **The *Økonomi* page** (under *Mere*): the month as a chart (spent, an even pace and a forecast from your own pace over the last eight weeks or the week's lists), the last 12 weeks against their budget, the year month by month, and the averages that matter: per shopping day, extra trips, per adult per day, per shop, saved on offers and what was bought outside the meal plan. The purchases of the last two months can be deleted.
- **The meal plan keeps to the budget:** with a monthly budget, a new plan may cost what is left of its week (lists still to be bought before it are taken off; never below 40 % of the week's budget), and the AI is told to stay a bit below. Sending a list that costs more than the week has left asks first.
- **Told at 80 %:** optionally a notification (to the same place as the offer watch) when 80 % of the week's budget is used, once a week.
- **The action `middagsro.register_purchase`** books a purchase (amount, shop, day, note) and answers with what is left of the week and the month's forecast – for an iPhone *Transaction* automation with Apple Pay, a Siri shortcut or anything else.
- Sensors *Food budget left this week*, *Food budget spent this month* and *Food budget forecast for the month* (DKK; unavailable without a budget).

## [2.0.2] - 2026-10-21

### Fixed
- A favourite with a one-word name (*SMOOTHIE*, *SMØR*) is only "cheaper in Netto" when the offer names its brand or variety (Lovemade, Lurpak, quinoa & æble) – not just any smoothie or any butter.
- The badge on a favourite shows the price you pay in the other chain; the popup opens with that very offer at the top, with what it comes to for REMA's size, and a button that puts it on that chain's list.

## [2.0.1] - 2026-10-21

### Fixed
- **The list buys what the recipes use.** The overview's amounts are the AI's first guess; the recipes come after, for the household, and two dishes may share a line (the lasagne's and the hakkebøffer's minced meat). Now a line's packages grow to what the dishes need – never more than fourfold, never fewer – also after a dish is swapped or a recipe rewritten. The recipe writer is also told what is actually bought ("2 × 400 g").
- *Cæsardressing* finds REMA's *CÆSAR DRESSING*: a compound search word is also tried as two words, and matches a two-word name.

## [2.0.0] - 2026-10-21

### Changed
- **The panel stays out of your way.** The field you are typing in keeps its focus, caret and keyboard when the page is redrawn (while a plan is being made, after a toast), and the page is only redrawn when something actually changed. A toast no longer redraws the page at all.
- **No tap is lost.** Actions run one after the other: a tap while something else is in flight waits its turn instead of being ignored.
- **Timers ring wherever you are**: a cooking timer sounds and vibrates once, whatever tab is open, with a toast – and a chip in the toolbar counts down the next one (tap it to get to the recipe).
- **Back to the app, up to date**: coming back after a while (or while a plan is being made) reloads the plan and the list, so the partner's ticks and an automatic plan show up without a tap.
- The *older plan* banner now also shows on the shopping list and the week's recipes, so an old list isn't sent by mistake.
- The plan tab starts with tonight's dinner; the other chains' offers and prices follow below.
- Big lists (favourites, a chain's offers, the recipe collection) are redrawn a moment after the last keystroke, not on every one.
- A swipe inside a popup no longer changes the tab underneath, and leaving a chain's offers page lands on the plan again.
- *Sundhed* is only recalculated when the plan changed (or *Regn igen* is tapped).
- A problem drawing one page shows "Prøv igen" instead of a blank panel; the toast sits above popups and is announced to screen readers.

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
