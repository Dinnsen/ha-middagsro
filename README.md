<p align="center">
  <img src="docs/images/hero.png" alt="Middagsro: meal plan, recipe and shopping list on a phone" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Dinnsen/ha-middagsro/releases"><img alt="Version" src="https://img.shields.io/github/v/release/Dinnsen/ha-middagsro?style=flat-square&label=version&color=0e2a8a"></a>
  <a href="https://github.com/Dinnsen/ha-middagsro/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/Dinnsen/ha-middagsro/total?style=flat-square&label=downloads&color=0e2a8a"></a>
  <a href="https://hacs.xyz"><img alt="HACS" src="https://img.shields.io/badge/HACS-custom-41BDF5?style=flat-square"></a>
  <img alt="Home Assistant 2026.1+" src="https://img.shields.io/badge/Home%20Assistant-2026.1%2B-18BCF2?style=flat-square&logo=homeassistant&logoColor=white">
  <img alt="Quality scale: Platinum" src="https://img.shields.io/badge/quality-platinum-7f8c99?style=flat-square">
  <a href="https://github.com/Dinnsen/ha-middagsro/actions/workflows/tests.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/Dinnsen/ha-middagsro/tests.yml?branch=main&style=flat-square&label=tests"></a>
  <a href="LICENSE"><img alt="Licence: MIT" src="https://img.shields.io/badge/licence-MIT-97ca00?style=flat-square"></a>
  <a href="https://buymeacoffee.com/dinnsen"><img alt="Buy Me a Coffee" src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-ffdd00?style=flat-square&logo=buymeacoffee&logoColor=black"></a>
</p>

# Middagsro – meal plans and REMA 1000 shopping in Home Assistant

🇩🇰 [Læs på dansk](README.da.md)

**Middagsro** (Danish for *dinner calm*) plans the week's dinners with AI from REMA 1000's weekly offers (*tilbudsavis*), brings the recipes up in the kitchen, keeps the family's recipe collection and sends the shopping list straight to the REMA 1000 app with one tap. The shopping list in the app also becomes a to-do list in Home Assistant, so you can add items by voice, from an automation or from a dashboard.

> [!NOTE]
> Unofficial integration, not made by or affiliated with REMA 1000 or the other chains it shows offers from. REMA 1000 has no public API, so the integration uses the same calls as rema1000.dk and the web shop. It may stop working if REMA changes its site. For personal use with your own REMA 1000 account in Denmark. The panel and the meal plans are in Danish.

**Contents:** [Features](#features) · [Food budget](#food-budget-økonomi) · [Dashboard cards](#cards-for-your-own-dashboards) · [Requirements](#requirements) · [Installation](#installation) · [Setup](#setup) · [Settings](#settings-in-the-panel) · [Entities](#entities) · [Actions](#actions) · [Examples](#examples) · [How it works](#how-it-works) · [Limitations](#known-limitations) · [Troubleshooting](#troubleshooting) · [Removal](#removing-the-integration) · [Privacy](#privacy)

## Features

The integration adds a **Middagsro panel** to the sidebar. It follows your Home Assistant theme, light and dark mode, and works on a computer, tablet and phone, where the tabs sit at the bottom and you can swipe between them.

### The week's meal plan, made with AI

<img src="docs/images/plan.png" alt="A week's meal plan with price, budget and the dinners" width="100%">

- The AI you have set up in Home Assistant (an **AI Task**, e.g. Google Gemini, OpenAI or Anthropic) plans dinner for 1–14 days and builds the dishes around the week's offers.
- The plan follows your rules: budget, organic, requirements for eggs and milk, things to avoid, allergies, number of vegetarian dishes, leftover days, fixed days (e.g. a rye-bread day), maximum time on weekdays and your favourite dishes.
- **Skip days** when you are not eating at home, and choose the first day yourself.
- **Wishes for the plan:** write, for example, what in the fridge must be used before a given day, or which dish you want on a given day. The wishes are used in the next plan only – also when it is made automatically – and then removed.
- **One plan for the week:** the plan page shows the whole week, from the family's first weekday to the last planned day, as one plan – also when it was made in several goes (a new plan from Wednesday replaces the old one from Wednesday on). When next week's plan is ready, it follows under its own week heading. Days that have passed are dimmed. The calendar and the *dinner today* sensor follow the same rule. The recipes tab always opens on tonight's dish.
- **The plan is checked, not just asked for.** The AI is not trusted to keep the rules: every plan is checked afterwards – no dish from the last weeks again (the main dish counts: salmon is salmon, whatever the side), nothing the family dislikes, the right number of leftover days from a double portion, the vegetarian count, fixed days, the weekday time limit and the budget. What is wrong is sent back to the AI, up to twice, and the best try is kept. Anything it still couldn't fix is shown on the plan.
- **Your own recipes are used as they are.** When a dinner is one of your favourite dishes and the recipe collection has your recipe for it (a ❤️, or the favourite's own), the plan uses that recipe – its ingredients go on the shopping list in amounts for your household, with the REMA products it names – instead of the AI's own version.
- A **requirements checklist** shows whether the plan keeps your rules.
- Turn on **automation** to make next week's plan when the new offers come out – and optionally send it straight to the REMA list.
- **Swap, delete or skip:** tap a dish in the plan to get three other suggestions, delete it or skip the day. The shopping list and recipe follow along.
- **Move a dish** a day up or down with the arrows under 👍 and 👎 – leftovers follow, and never come before the day the food is made.
- **Choose a dish yourself** for a day of the next plan (*Vælg ret*): from the recipe collection, REMA's recipes or Mealie. The AI plans the rest around it. A dish asked for in the wishes ("frikadeller på onsdag") is kept on that day too.
- **No leftovers on chosen weekdays**, e.g. the weekend.
- **Det skal AI'en huske** (what the AI must remember): standing points for every plan, e.g. “always fresh broccoli with salmon” – typed or dictated.
- **Nutrition targets** per dinner (kcal and the split of protein, carbs and fat), and the **Sundhed** (health) tab with nutrition, the dietary advice and labels like the Keyhole.
- Buttons that use AI are marked with ✦.

<img src="docs/images/plan-tools.png" alt="A dish's menu, three other dishes to swap to, and the points the AI must remember" width="100%">

*Tap a dish: see the recipe, swap it for one of three new suggestions or a REMA recipe, delete it or skip the day. Right: the standing points for every plan.*

### Recipes for the kitchen

<img src="docs/images/recipe.png" alt="A recipe with ticked ingredients and a timer counting down" width="100%">

Ingredients and steps in large type. Tick them off as you go, start a **timer** on each step (it beeps and vibrates when time is up, whatever tab is open, and a chip at the top counts down – tap it to get back to the recipe), and tap **Hold skærmen tændt** (keep the screen on) while you cook. Leftover days point to the day the food was made. Not happy with a recipe? Make it again.

### The cheapest shopping list – straight into the REMA app

<img src="docs/images/shopping.png" alt="Shopping list with REMA products, offers, organic labels and prices" width="100%">

- For each ingredient, **the cheapest REMA product** that meets your rules is found. Products from the offers, organic products and weekly fixed items are labelled.
- Price per product, number of packs and the total against the budget. With a [food budget](#food-budget-økonomi), sending a list that costs more than the week has left asks first.
- **Send til REMA-listen** puts everything on your primary list in the REMA 1000 app. Items without a safe match are added as text. Sent items leave Middagsro's basket, so the next send only has what was added since – nothing ends up twice in the app. **Genskab seneste kurv** puts the last sent items back if something went wrong. The REMA logo next to an item puts just that item on the REMA list right away.
- Search the basket for any REMA product – also the offers in REMA's avis, including *partivarer* that are only sold in the shops.
- **Search and add** other REMA products to the shopping list – also to the list for later in the week – or put one **straight on the REMA list** in the app with *+ REMA-listen*, past the meal plan. Tap an item to change how many, swap it or delete it.
- **Basic items in the plan** (*Basisvarer i madplanen*) shows the basic items (salt, oil, butter …) the recipes use. Out of one? Tap **Tilføj til indkøb**, and the product is found by your settings.
- Below the list you see what is on the REMA list right now, and it can be emptied once you have shopped.

<img src="docs/images/rema-list.png" alt="What is on the REMA list right now" width="100%">

### Your favourite products on offer

<img src="docs/images/favorites.png" alt="Favourite products from the REMA app that are on offer" width="100%">

The products you have given a heart in the REMA 1000 app. Choose **Denne uge** (this week) or **Næste uge** (next week) to see which are on offer, with before and now price, and put them on the list with one tap. This week shows REMA's own prices, as in the app. Next week shows the avis's prices and text as soon as it is out, since REMA only has them from Sunday 02:00. Offers that only start on Thursday are shown with a blue *fra tor* badge until they start. Until next week's offers are out, this week's are shown. All favourites can be filtered.

Search REMA's products at the bottom of *Favoritter* to add favourites of your own, next to the hearts from the app.

<img src="docs/images/watch.png" alt="The watch list: where watched items are on offer, in REMA and other chains" width="100%">

**Watch list (Overvågning).** Tap the 🔔 on a favourite or any product to watch it – or type something REMA doesn't sell and watch it as text. At the top of *Favoritter* you see where the watched items are on offer: in REMA (now or from next week's avis) and in the chains you have chosen, with the price and a button that puts the item in the basket or on that chain's shopping list. In **Indstillinger → Overvågning og beskeder** you can get a notification on your phone or in Home Assistant when something on the watch list comes on offer – and only then. The list is checked every 3 hours, and each offer is told once.

### Food budget (*Økonomi*)

<img src="docs/images/budget.png" alt="The week's food budget on the front page, the month as a chart with a forecast, and the last 12 weeks" width="100%">

The household's fixed amount for food a month, with every purchase booked against it – so you see what is left of the week while you shop, and the meal plan stays within it.

- **The front page** shows what is left of the week and per day for the rest of it, a bar with a mark for an even pace, and what the week's lists still to be bought are estimated at. **Book a purchase** below it: the amount on the receipt, the shop (REMA 1000, your other chains or *Andet*) and the day. The list you sent today can be booked with one tap.
- **The amount is spread over the month's days** (5.000 kr. in October is 161 kr. a day, 1.129 kr. a week). What a week doesn't use carries on to the next weeks of the same month, and what it overspends is taken from them; a new month starts afresh on the 1st. Everything you book counts, nappies too.
- **The *Økonomi* page** (under *Mere*): the month as a chart – spent, an even pace and a **forecast** from your own pace over the last eight weeks – the **last 12 weeks** against their budget, the **year** month by month, and the purchases of the last two months (delete one with ✕).
- **The averages that matter:** per shopping day (*Snit søndag*, *Snit torsdag*), extra trips, per adult per day (children count for less), per shop, saved on offers and what was bought outside the meal plan.
- **The meal plan keeps to it:** a new plan may cost what is left of its week (lists still to be bought before it are taken off, and never below 40 % of the week's budget), and the AI is told to stay a bit below.
- **Told at 80 %:** optionally a notification when 80 % of the week is used – once a week, to the same place as the watch list's.
- Three sensors – *left this week*, *spent this month*, *forecast for the month* – for dashboards and automations.

<img src="docs/images/budget-year.png" alt="Averages per shopping day, the year month by month and the latest purchases" width="100%">

**Booking by itself with Apple Pay (iPhone).** REMA's *Scan & Betal* has no receipts you can reach, but a card payment can book itself. In the *Shortcuts* app, make a personal automation **Transaction** (*Transaktion*) for your Wallet card – choose the shops (REMA 1000, Netto …), or leave them open if the card is only for food – and *Run immediately*. Add Home Assistant's action **Perform action** (*Udfør handling*), choose *Register a purchase*, and write in its data field:

```json
{"amount": "Amount", "store": "Merchant"}
```

where *Amount* and *Merchant* are not typed but inserted as the shortcut's variables (*Shortcut Input → Amount* and *→ Merchant*), so they show as blue bubbles. The amount may come as the payment shows it (*600,00 kr.*). A Siri shortcut that asks for the amount works the same way, and the action answers with what is left of the week.

### History

<img src="docs/images/history.png" alt="Earlier meal plans with price and dishes" width="100%">

Earlier meal plans with price, status and dishes. Open an old plan and send it to the REMA list again, or delete it.

### The family's favourite dishes and dishes you don't like

<img src="docs/images/family-favorites.png" alt="The family's favourite dishes with how often" width="100%">

Describe the dishes the family loves and how often they should be on the plan (every week, every 2 weeks, every month, only when the ingredients are on offer, or just for inspiration). Dishes you don't like never go on the plan.

### Recipe collection – 👍, 👎 and ❤️

<img src="docs/images/collection.png" alt="The recipe collection with search, sorting and thumbs up, down and heart" width="100%">

The **Opskrifter** (recipes) tab has three pages: **Ugens opskrifter** (the week's recipes) as before, **Opskriftsamling** (the recipe collection) and **REMA-opskrifter** (REMA 1000's own recipes).

- **👍, 👎 and ❤️** on every dinner in the plan and on the recipe. 👍 saves the dish in the collection as one you like, 👎 as one you don't like (it is never put on a plan again), and ❤️ as a favourite (it also gets 👍, and the heart turns red). Tap again to take it back; 👍 after 👎 changes it.
- **Search, sort and filter** the collection (name, newest, most used, quickest; all, favourites, liked, disliked).
- **Add a recipe from a link:** paste the link to a recipe page and tap **Hent opskrift**. The recipe is read from the page (most recipe sites have it as data; otherwise the AI reads the page), and you can correct it before it is saved. The link itself is not kept. Or write a recipe yourself – type an ingredient and pick one of REMA's products for it, so the shopping list gets the very item.
- **Scan a recipe from a cookbook:** *Scan fra kogebog* takes a photo of the page (or several pages); the AI reads it, and you check and correct it before it is saved. Needs an AI Task that can read images.
- **Recipes from recipe sites:** search Valdemarsro, Madens Verden, Louises madblog, DK-kogebogen and Arla under *Opskrifter → Madsider*, save a recipe in the collection, or let the AI build the plan from the sites' recipes (*Indstillinger → Opskrifter og madsider*).
- **Open a recipe** to edit the name, times, ingredients and steps, rate it, or **put it on the meal plan** on a day you choose – its items go on the shopping list.
- New plans and swap suggestions use the family's favourites and liked dishes when they fit the week's offers, and never the disliked ones.
- **REMA 1000's recipes:** search or browse REMA's own recipes – popular, newest, *Avisopskrifter* (built on this week's offers), *Aftensmad*, *Mad for børn*, *Kødfri* and more. Each card shows the time, a rough price and how many of its items are on offer. Every ingredient is linked to one of REMA's products, so the shopping list gets the very item. Save a recipe in the collection (with its photo), or put it straight on a day of the plan. In the plan, tap a dish and **Vælg en REMA-opskrift** to swap it for one of REMA's.

<img src="docs/images/rema-recipes.png" alt="REMA 1000's own recipes with time, price and how many items are on offer" width="100%">

### Overrask os (surprise us)

<img src="docs/images/new-plan.png" alt="A new meal plan: first day, wishes, days to skip, Lav ny madplan and Overrask os" width="40%" align="right">

Next to **Lav ny madplan** on the front page: a plan with dishes the family has never had – from other cuisines, with exciting flavours and surprising combinations, but still within your budget, allergies, rules and weekday time.

Above the buttons you choose the first day, write **wishes for this plan** and tick the days you are not eating at home. The plan is made for the week of the newest avis – never for a week whose prices aren't out yet.

<br clear="right">

### Offers from other shops

<img src="docs/images/chains.png" alt="Round logos of other chains on the front page and items that are cheaper elsewhere in the shopping list" width="100%">

Middagsro is still about REMA 1000, but under **Indstillinger → Andre butikker** you can choose other chains you also shop in (Netto, Lidl, føtex, Bilka, 365discount, MENY, SuperBrugsen, Kvickly, Brugsen, SPAR, Løvbjerg, Min Købmand, ABC Lavpris).

- REMA 1000's logo comes first: its page shows all the offers in REMA's avis.

<img src="docs/images/search.png" alt="Searching every shop for milk: REMA's prices and the other chains' offers, the cheapest per litre marked" width="100%">

- **Search every shop** under the logos: a product's price at REMA and in the other shops' offers, per kilo, litre or piece, with the cheapest marked – and put it on the meal plan's shopping list (*+ Indkøb*), **straight on the REMA list in the app** (*+ REMA-listen*) or on the cheaper shop's list.
- Their **logos are shown in circles on the front page**; tap one to see that chain's food offers, search them and put one on that shop's list.
- In the **shopping list**, a small logo shows when an item is cheaper in one of them this week, and how much you save. **Tap the logo** to buy it there: the item moves to a separate list for that shop under the REMA list, and is not sent to the REMA app. Each shop's list can be ticked off, amounts changed, items deleted or moved back to REMA, and **Ryd kurven** (empty the basket) removes what has been bought – the list disappears when it is empty.
- In **Favoritter**, the same logo shows which of your favourite products are cheaper elsewhere that week.
- The offers come from the chains' own weekly aviser on Tjek (eTilbudsavis), the same source as REMA's avis. An item only counts as cheaper when it is the same kind of item (same words, fat percentage and organic or not), compared per kilo, litre or piece.

### Health (*Sundhed*)

<img src="docs/images/health.png" alt="Nutrition per dinner: kcal, protein, carbs, fat and fibre, per day" width="100%">

How the week's dinners add up for an adult portion: kcal, protein, carbohydrate, fat and fibre on average and per day, against the targets you set under **Indstillinger → Næring** (the AI is asked to hit them when it plans).

<img src="docs/images/health-advice.png" alt="The official Danish dietary advice: fruit and vegetables, fish, red meat and pulses from the shopping list" width="100%">

From the shopping list: fruit and vegetables, fish (and oily fish), red meat and pulses per person against the official Danish dietary advice – children count for less – and the share of the basket with the Keyhole, organic and ASC/MSC labels.

### Settings in sub-pages

The settings are split into pages – meal plan and week, food budget, the family, dishes, shopping, what the AI must remember, nutrition, other shops, watch list and notifications, Mealie and the app – each with a short summary of what is chosen.

### Made for the kitchen and the sofa

- **Your typing is safe:** the field you are typing in keeps its focus and keyboard when the page updates – while a plan is being made, or the partner ticks something off.
- **Up to date when you come back:** returning to the app after a while reloads the plan and the list, so an automatic plan and the other phone's ticks show up without a tap.
- **No tap is lost:** taps while something is in flight wait their turn.
- Swipe between tabs on a phone; the *older plan* banner warns before an old list is sent.

### Mealie

If [Mealie](https://mealie.io) is set up in Home Assistant (the official Mealie integration), the plan can work with it – switch it on under **Indstillinger → Mealie**:

- **Start from your own recipes:** the AI uses the family's recipes in Mealie when they fit the week's offers and your rules, and makes up its own dishes when none fit. A dish from Mealie keeps Mealie's ingredients and steps, and the shopping list follows them. Swapping a dish suggests your own recipes too.
- **Save a recipe in Mealie:** *Gem i Mealie* on a recipe from the plan saves it in Mealie with ingredients, steps and times.
- **Mealie's calendar:** the plan's dinners go into Mealie's meal planner (as the recipe when it is in Mealie, otherwise as a note), and are updated when a dish is swapped, deleted or a day is skipped.

The integration uses the Mealie integration's address and API token, so nothing has to be entered twice.

### Cards for your own dashboards

<img src="docs/images/cards.png" alt="Middagsro's dashboard cards on a phone, light and dark: Bubble buttons for tonight, the shopping and the budget, the week, tonight, the basket and the food budget" width="100%">

Middagsro brings six cards for your own dashboards. They come with the integration – there is no resource to add and nothing to install in HACS – and are under **Add card** (search for *Middagsro*), with a visual editor. They follow Middagsro live: a new plan, a sent list or a booked purchase shows at once.

| Card | | Size |
| --- | --- | --- |
| **Week** `custom:middagsro-week-card` | The week's dinners on one line, with tonight marked and in view. | Full width |
| **Tonight** `custom:middagsro-tonight-card` | Tonight's dish with its time, servings and type, and tomorrow's. | Half width |
| **Tonight, large** `custom:middagsro-tonight-large-card` | Tonight's recipe as on the *Opskrifter* page: ingredients and steps to tick off, and the timers. | Full width |
| **Shopping** `custom:middagsro-shopping-card` | The basket (items and price), what has been sent, what is on the REMA list now, and **Send til REMA**. | Half width |
| **Budget** `custom:middagsro-budget-card` | The week's food budget: what is left, per day, the bar with the even pace, and the month. | Half width |
| **Bubble** `custom:middagsro-bubble-card` | Tonight, the shopping or the budget as one [Bubble Card](https://github.com/Clooos/Bubble-Card) button (`show: tonight`, `shopping` or `budget`): the budget fills it like a slider with the pace marked, the shopping has a *Send* button. | One row |

**Tapping a card** opens a pop-up with that page of the panel – the day's recipe, the basket or *Økonomi* – and **Åbn i Middagsro** goes to the panel. The pop-up is Home Assistant's own dialog, so it opens above everything (also from a Bubble Card pop-up) and closes with the back button or by pulling it down on a phone. `tap_action: panel` opens the panel instead, `none` does nothing.

```yaml
type: custom:middagsro-bubble-card
show: shopping          # tonight (default), shopping or budget
name: Indkøb            # optional
tap_action: popup       # popup (default), panel or none
```

The panel's pages have addresses of their own: `/middagsro/plan`, `/middagsro/recipes/<date>`, `/middagsro/shopping`, `/middagsro/budget` and so on.

**Themes.** The cards and the pop-up follow your theme without card-mod: Home Assistant's card and dialog variables; Bubble Card's `--bubble-*` variables for the Bubble card and the pop-up (so it matches your Bubble pop-ups); and [Theme Studio](https://github.com/Dinnsen/theme-studio)'s glass blur (`--theme-studio-card-backdrop-filter`, also on the panel's own cards), raised surface (`--theme-studio-soft-background-color`), chip radius (`--theme-studio-chip-radius`) and pop-up border and shadow.

<img src="docs/images/cards-theme-studio.png" alt="The Bubble cards and the week in a Theme Studio theme, light and dark" width="100%">

### Light and dark mode

<img src="docs/images/plan-dark.png" alt="The meal plan in dark mode" width="100%">

### App on the home screen

Open `https://<your-home-assistant>/middagsro_app/app.html` in Safari or Chrome, log in and choose **Share → Add to Home Screen**. Middagsro then opens full screen with its icon and your Home Assistant theme – also behind the notch and home bar. Pull down to refresh. The link is also under **Indstillinger** (settings) in the panel.

## Requirements

- Home Assistant **2026.1** or newer.
- A REMA 1000 account (the same login as on rema1000.dk and in the REMA 1000 app).
- For the meal plan: an **AI Task** in Home Assistant, e.g. from Google Generative AI, OpenAI or Anthropic (**Settings → Devices & services → Add integration**). An AI that only offers a **conversation agent** – such as [LiteLLM](https://www.home-assistant.io/integrations/litellm) – works too: choose it under the panel's settings. The shopping list, search, offers and favourites work without AI.

## Installation

### With HACS (recommended)

[![Open your Home Assistant and add the repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dinnsen&repository=ha-middagsro&category=integration)

1. Tap the button above, or go to **HACS → ⋮ → Custom repositories** and add `https://github.com/Dinnsen/ha-middagsro` as an **Integration**.
2. Search for **Middagsro** in HACS and tap **Download**.
3. Restart Home Assistant.

### Manually

1. Download the source code of the latest version under [Releases](https://github.com/Dinnsen/ha-middagsro/releases).
2. Copy the folder `custom_components/middagsro` to `config/custom_components/` in Home Assistant.
3. Restart Home Assistant.

### Updating from the REMA 1000 integration (before 1.1.0)

From 1.1.0 the integration's id and folder are `middagsro` (before: `rema1000`). After updating in HACS and restarting Home Assistant:

1. Go to **Settings → Devices & services → Add integration** and choose **Middagsro**.
2. It finds your REMA 1000 setup – tap **Submit**. The meal plans, settings, recipe collection, device and entities are moved over; the entities keep their IDs, and you don't log in again.
3. Delete the old folder `config/custom_components/rema1000` if HACS hasn't, and restart once more.

Actions are now called `middagsro.…` (before `rema1000.…`); change them in your automations and scripts. The home-screen app's old address still works.

## Setup

[![Open your Home Assistant and add Middagsro.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=middagsro)

1. Go to **Settings → Devices & services → Add integration** and choose **Middagsro**.
2. Choose the shop. With **REMA 1000** you log in (below) and get prices on every item, REMA's recipes and the shopping list in the REMA app. With **another shop** (Netto, føtex, Lidl, Bilka, 365discount, MENY, SuperBrugsen, Kvickly, SPAR …) there is no login: the meal plan is built on the shop's offer catalogue, only the offers have a price (in Bilka every item has its Bilka ToGo price), and the shopping list is kept in Home Assistant (and can also go to another to-do list, e.g. Bring!). The setup lists what only works with REMA 1000. The shop can be changed later under **Reconfigure** – meal plans, recipes and settings are kept.
3. With REMA 1000: log in:

   | Field | Description |
   |---|---|
   | **E-mail** | The e-mail you log in to rema1000.dk and the REMA 1000 app with. |
   | **Password** | Your REMA 1000 password. It is stored in Home Assistant and only sent to REMA 1000. |

4. Open **Middagsro** in the sidebar, go to **Indstillinger** (settings) and choose the family's rules. Then tap **Lav madplan** (make meal plan).

The integration logs in again by itself when the session expires. If you change your password, Home Assistant asks you for the new one (**Settings → Devices & services → Middagsro**). To change the e-mail or password yourself, choose **⋮ → Reconfigure** on the integration. You can add several REMA 1000 accounts. Each gets its own entities, and the actions can target a given account; the panel shows the one added first.

## Settings in the panel

<img src="docs/images/settings.png" alt="The settings, split into pages each with a short summary" width="100%">

The settings apply every time a meal plan is made and are stored per REMA 1000 account. The panel is in Danish; the Danish name of each setting is in brackets.

| Setting | What it does | Default |
|---|---|---|
| **AI for the meal plan** (*AI til madplanen*) | Which AI Task makes the plan – or a conversation agent, for an AI without AI Tasks (LiteLLM); it is asked to answer in JSON. *Home Assistants standard* uses the AI Task chosen in the AI settings. | Default |
| **Plan starts / shopping day** (*Madplanen starter / der handles ind*) | The weekday the plan starts. The offers run from Sunday. | Sunday |
| **Number of days** (*Antal dage*) | 1–14 days. | 7 |
| **Budget** | The whole shopping list in DKK. Over budget, the AI tries once more. | 500 |
| **Organic** (*Økologi*) | *Only organic*, *Prefer organic* (if at most x % dearer than the cheapest) or *Don't mind*. | Prefer, 20 % |
| **Eggs** (*Æg*) | Cage eggs, at least free-range or organic only. | Cage eggs |
| **Milk / fruit and vegetables must be organic** | Requirements that apply whatever the price. | Off |
| **Avoid** (*Undgå*) | Meat, pork, beef, fish, shellfish, animal products (vegan), spicy food – and free text. | – |
| **Allergies** (*Allergier*) | The 14 allergens on the EU list (gluten, lactose, milk protein, egg, nuts, peanuts, soy, sesame, celery, mustard, fish, crustaceans, molluscs, lupin, sulphites) – and free text. | – |
| **Family** (*Familien*) | Adults and children with age and sex, so the amounts fit. | 2 adults, 2 children |
| **Vegetarian dishes** (*Vegetarretter*) | Minimum and maximum per plan. | 0–1 |
| **Leftover days** (*Restedage*) | Days with leftovers from the day before. | 2 |
| **Max. minutes on weekdays** | The most time a dish may take Monday–Friday. | 30 |
| **No repeats** (*Ingen gentagelse*) | Number of weeks before a dish may come back. | 3 |
| **Fixed days** (*Faste dage*) | E.g. a rye-bread day on Wednesdays. | Thursday: rye bread |
| **Wishes for the food** (*Ønsker til maden*) | Free text for the AI. | Healthy and child-friendly |
| **Pantry** (*Basisvarer*) | What you always have and don't buy (salt, oil, flour …). | Salt, pepper, oil etc. |
| **Fixed weekly items** (*Faste varer hver uge*) | Search REMA's range and pick a product (or write free text) that always goes on the list. Optionally, a fixed item that is already on the REMA list (not bought) is not sent again. | – |
| **We also shop late in the week** (*Vi handler også sidst på ugen*) | Some offers only start on Thursday. Off, the meal plan only uses offers that run on the shopping day. On, it may use them in dishes from that day; the shopping list is split into the shopping day and Thursday, each sent on its own. | Off |
| **Automation** (*Automatik*) | Make next week's plan when the new offers come out, and optionally send it to the REMA list. It is sent at 02:00 on the shopping day (Thursday's items at 02:00 on Thursday), when REMA has the week's products and prices. | Off |
| **What the AI must remember** (*Det skal AI'en huske*) | Standing points for every plan, e.g. "always fresh broccoli with salmon". Also on the front page, typed or dictated. | – |
| **Nutrition** (*Næring*) | Targets per dinner for an adult: kcal and the split of protein, carbs and fat. | Off |
| **Other shops** (*Andre butikker*) | The chains you also shop in, for their offers, prices and shopping lists. | – |
| **Watch list and notifications** (*Overvågning og beskeder*) | Where to tell when something watched comes on offer: a phone (Companion app) or Home Assistant. The food budget's 80 % notice goes there too. | Off |
| **Mealie** | Use the family's Mealie recipes, save recipes there and fill Mealie's meal planner. | Off |
| **Food budget** (*Madbudget*) | The monthly amount for food (0 = off). With it, a plan's budget is what is left of its week, and *Budget* above isn't used. Optionally a notification at 80 % of the week. | Off |
| **The family's favourites** (*Familiens favoritter*) | Dishes with how often. | – |
| **Dishes the family doesn't like** | Never go on the plan. | – |

## Entities

Each REMA 1000 account becomes a service with these entities:

| Entity | Type | Description |
|---|---|---|
| **Shopping list** | `todo` | Your primary REMA list – the one shown in the app. Add, tick off, change amounts and delete; changes show in the app and the other way round. What you add (also via Assist) is matched with a REMA product; write `3 x mælk` for 3 pieces. If there is no safe match, it is added as text. |
| **Add to shopping list** | `text` | Write e.g. `letmælk`, `2 x rugbrød` or `tre poser chips`. The product is matched and put on the list, and the field is emptied afterwards. The attributes show what was added. |
| **Meal plan** | `sensor` | Status of the meal plan (*No plan*, *Generating*, *Ready*, *Sent to shopping list*, *Error*). Attributes: title, start and end date, price, budget, over budget and the dinner per day. |
| **Dinner today** | `sensor` | Today's dinner. Attributes: type, leftovers, servings, time, ingredients, number of steps, tip and tomorrow's dish. |
| **Shopping list total** | `sensor` (DKK) | Estimated price of what is still to be bought. Attributes: number of items and items without a price. |
| **Current offer catalogue** / **Next offer catalogue** | `sensor` (timestamp) | When the offers run until / from. Attributes: the catalogue's name, number of offers and when the integration first saw next week's catalogue. |
| **Food budget left this week** / **spent this month** / **forecast for the month** | `sensor` (DKK) | The food budget's numbers (unavailable without a monthly budget). The week's sensor has the week's start, end, available, spent, carry, planned and per day as attributes. |
| **Meal plan** | `calendar` | Each day's dinner as an event with time and ingredients. |
| **Make meal plan** | `button` | Makes a new plan with the settings from the panel. |
| **Send meal plan to shopping list** | `button` | Sends the newest plan to the REMA list. |

## Actions

| Action | Description | Fields |
|---|---|---|
| `middagsro.search_products` | Search REMA 1000's range with price, offers and organic. Returns a response. | `query` (required), `limit` (1–100, default 10), `config_entry_id` |
| `middagsro.get_offers` | All offers in the current or next catalogue. Returns a response. | `catalog` (`current` or `upcoming`), `config_entry_id` |
| `middagsro.add_items` | Add products (REMA product number or free text) to the REMA list. | `items` (required, list with `product_id` or `name` and optionally `amount`), `config_entry_id` |
| `middagsro.generate_meal_plan` | Make a meal plan in the background. | `start_date`, `send` (send the list when the plan is ready), `config_entry_id` |
| `middagsro.send_meal_plan` | Send a meal plan's shopping list to the REMA list. | `plan_id` (empty = newest), `part` (`main` = the shopping day, `late` = the Thursday items, `all`; default `main`), `config_entry_id` |
| `middagsro.register_purchase` | Book a purchase against the food budget. Returns what is left of the week and the month's forecast. | `amount` (required), `store` (a name like *REMA 1000 Valby* or *Netto*; default REMA 1000), `date` (default today), `note`, `config_entry_id` |

`config_entry_id` is only needed if you have several REMA 1000 accounts.

## Examples

**Add products from an automation:**

```yaml
action: middagsro.add_items
data:
  items:
    - product_id: 20494
      amount: 2
    - name: Opvasketabs
```

**Search for a product and use the response:**

```yaml
action: middagsro.search_products
data:
  query: letmælk
  limit: 5
response_variable: result
```

**Get a notification when next week's offers are out:**

```yaml
triggers:
  - trigger: state
    entity_id: sensor.middagsro_next_offer_catalogue  # your id for Next offer catalogue
    from: unknown
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: "Next week's REMA offers are out – time for a new meal plan."
```

**Make and send the meal plan on Saturday morning:**

```yaml
triggers:
  - trigger: time
    at: "08:00:00"
conditions:
  - condition: time
    weekday: sat
actions:
  - action: middagsro.generate_meal_plan
    data:
      send: true
```

**By voice:** Say *"Add milk to the shopping list"* to Assist (or Siri via the Home Assistant app) if **Shopping list** is exposed to Assist. The item is matched with a REMA product and shows in the REMA 1000 app.

**On a dashboard:** Show **Dinner today** in a tile card, **Shopping list** in a to-do list card and the **Meal plan** calendar in a calendar card.

The entity IDs depend on the account's name and your language; find them under **Settings → Devices & services → Middagsro**. Installations from before 1.0.0 keep their `rema_1000_…` entity IDs; new ones get `middagsro_…`.

## How it works

- The **shopping list** is fetched from REMA 1000 every **2 minutes**, so changes in the app show up quickly in Home Assistant. Changes from Home Assistant are sent at once.
- The **offer catalogues** (current and next week) are fetched every **3 hours** from Tjek, which REMA 1000 uses for its offers.
- Prices for the meal plan are those of the plan's first day, so a plan for next week uses next week's prices and offers. REMA's prices for a week end before the avis does; until the week turns on Sunday, the week's prices still count.
- The **meal plan** is only made when you ask for it (or automatically when next week's offers are out, if turned on). It usually takes 1–2 minutes: the AI plans, the integration finds and prices the products by your rules, and finally the recipes are written.
- Plans, settings and favourite dishes are stored in Home Assistant and included in backups.
- If the integration loses its connection to REMA 1000, the entities become unavailable and come back by themselves. If the login is no longer valid, Home Assistant asks you to log in again.

## Known limitations

- Only REMA 1000 **Denmark** and only your **primary** shopping list (the one the app shows).
- The panel, meal plans and recipes are in Danish.
- Prices are REMA's web prices and can differ from the shop. Offers outside the catalogue (e.g. local in-store offers) are not known.
- Some ingredients have no safe REMA product (e.g. fresh herbs). They go on the list as text and are not counted in the price.
- The AI can make mistakes. Check recipes and allergens before you cook.
- The integration uses non-public calls and may stop working if REMA 1000 changes its site.

## Troubleshooting

- **"Madplanen kunne ikke laves"** (the meal plan could not be made): check that there is an AI Task in Home Assistant and that it is chosen (or that a default is chosen) under the panel's **Indstillinger**. If it is missing, there is also a message under **Settings → Repairs**. If the AI answers too long or not in the right format, try again – or choose another model.
- **Login does not work:** try logging in on rema1000.dk with the same e-mail and password. Use **Reconfigure** on the integration if you changed your password.
- **The list doesn't update in the app:** pull down in the REMA 1000 app to refresh. Home Assistant fetches the list every 2 minutes.
- **The panel shows an old version after an update:** reload the page (on a phone: close and open the app).
- **Debug log:** go to the integration and choose **Enable debug logging**. Repeat the error, then turn it off again to download the log. The password is never logged.
- **Diagnostics:** choose **⋮ → Download diagnostics** on the integration. E-mail, password, tokens and other personal data are removed before the file is saved.

Feel free to open an [issue](https://github.com/Dinnsen/ha-middagsro/issues) with the diagnostics file and a description. Please report security issues privately, see [SECURITY.md](SECURITY.md).

## Removing the integration

1. Go to **Settings → Devices & services → Middagsro** and choose **⋮ → Delete** for each account. The panel disappears when the last account is deleted. Your list in the REMA 1000 app is not touched.
2. Installed with HACS: open **Middagsro** in HACS and choose **⋮ → Remove**. Manually: delete the folder `config/custom_components/middagsro`.
3. Restart Home Assistant.

## Privacy

Your REMA 1000 login is stored in Home Assistant and only sent to REMA 1000. For the meal plan, the integration sends your settings, the week's offers, your favourite dishes, your wishes for the plan and the dishes of the last weeks (so they are not repeated) to the AI service you have chosen in Home Assistant – never your login or your e-mail.

## Support

If you like Middagsro, you can [buy me a coffee](https://buymeacoffee.com/dinnsen).

## Licence

[MIT](LICENSE). The home-screen app includes [home-assistant-js-websocket](https://github.com/home-assistant/home-assistant-js-websocket) under the Apache-2.0 licence. REMA 1000 is a trademark of its owner; this project is not affiliated with REMA 1000 or the other chains. The other chains' names and logos are only used to show their offers.
