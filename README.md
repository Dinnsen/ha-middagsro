<p align="center">
  <img src="docs/images/hero.png" alt="REMA 1000 for Home Assistant: meal plan, recipe and shopping list on a phone" width="100%">
</p>

<p align="center">
  <a href="https://github.com/Dinnsen/ha-rema1000/releases"><img alt="Version" src="https://img.shields.io/github/v/release/Dinnsen/ha-rema1000?style=flat-square&label=version&color=0e2a8a"></a>
  <a href="https://hacs.xyz"><img alt="HACS" src="https://img.shields.io/badge/HACS-custom-41BDF5?style=flat-square"></a>
  <img alt="Home Assistant 2026.1+" src="https://img.shields.io/badge/Home%20Assistant-2026.1%2B-18BCF2?style=flat-square&logo=homeassistant&logoColor=white">
  <img alt="Quality scale: Platinum" src="https://img.shields.io/badge/quality-platinum-7f8c99?style=flat-square">
  <a href="https://github.com/Dinnsen/ha-rema1000/actions/workflows/tests.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/Dinnsen/ha-rema1000/tests.yml?branch=main&style=flat-square&label=tests"></a>
  <a href="LICENSE"><img alt="Licence: MIT" src="https://img.shields.io/badge/licence-MIT-97ca00?style=flat-square"></a>
  <a href="https://buymeacoffee.com/dinnsen"><img alt="Buy Me a Coffee" src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-ffdd00?style=flat-square&logo=buymeacoffee&logoColor=black"></a>
</p>

# REMA 1000 for Home Assistant

🇩🇰 [Læs på dansk](README.da.md)

Plan the week's dinners with AI from REMA 1000's weekly offers (*tilbudsavis*), bring the recipes up in the kitchen, and send the shopping list straight to the REMA 1000 app with one tap. The shopping list in the app also becomes a to-do list in Home Assistant, so you can add items by voice, from an automation or from a dashboard.

> [!NOTE]
> Unofficial integration, not made by or affiliated with REMA 1000. REMA 1000 has no public API, so the integration uses the same calls as rema1000.dk and the web shop. It may stop working if REMA changes its site. For personal use with your own REMA 1000 account in Denmark. The panel and the meal plans are in Danish.

**Contents:** [Features](#features) · [Requirements](#requirements) · [Installation](#installation) · [Setup](#setup) · [Settings](#settings-in-the-panel) · [Entities](#entities) · [Actions](#actions) · [Examples](#examples) · [How it works](#how-it-works) · [Limitations](#known-limitations) · [Troubleshooting](#troubleshooting) · [Removal](#removing-the-integration) · [Privacy](#privacy)

## Features

The integration adds a **REMA 1000 panel** to the sidebar. It follows your Home Assistant theme, light and dark mode, and works on a computer, tablet and phone, where the tabs sit at the bottom and you can swipe between them.

### The week's meal plan, made with AI

<img src="docs/images/plan.png" alt="A week's meal plan with price, budget and the dinners" width="100%">

- The AI you have set up in Home Assistant (an **AI Task**, e.g. Google Gemini, OpenAI or Anthropic) plans dinner for 1–14 days and builds the dishes around the week's offers.
- The plan follows your rules: budget, organic, requirements for eggs and milk, things to avoid, allergies, number of vegetarian dishes, leftover days, fixed days (e.g. a rye-bread day), maximum time on weekdays and your favourite dishes.
- **Skip days** when you are not eating at home, and choose the first day yourself.
- **Wishes for the plan:** write, for example, what in the fridge must be used before a given day, or which dish you want on a given day. The wishes are used in the next plan only – also when it is made automatically – and then removed.
- While next week's plan is ready, the plan page shows **tonight and the rest of this week** from the plan that is running now. The recipes tab always opens on tonight's dish.
- If the shopping list goes **over budget**, the integration asks the AI once for a cheaper plan and keeps the cheapest.
- A **requirements checklist** shows whether the plan keeps your rules.
- Turn on **automation** to make next week's plan when the new offers come out – and optionally send it straight to the REMA list.
- **Swap a dish:** tap a dish in the plan and get three other suggestions. Pick one, and the shopping list and recipe are made again.
- Buttons that use AI are marked with ✦.

### Recipes for the kitchen

<img src="docs/images/recipe.png" alt="A recipe with ticked ingredients and a timer counting down" width="100%">

Ingredients and steps in large type. Tick them off as you go, start a **timer** on each step (it beeps and vibrates when time is up), and tap **Hold skærmen tændt** (keep the screen on) while you cook. Leftover days point to the day the food was made. Not happy with a recipe? Make it again.

### The cheapest shopping list – straight into the REMA app

<img src="docs/images/shopping.png" alt="Shopping list with REMA products, offers, organic labels and prices" width="100%">

- For each ingredient, **the cheapest REMA product** that meets your rules is found. Products from the offers, organic products and weekly fixed items are labelled.
- Price per product, number of packs and the total against the budget.
- **Send til REMA-listen** puts everything on your primary list in the REMA 1000 app. Items without a safe match are added as text.
- **Search and add** other REMA products to the shopping list – also to the list for later in the week.
- **Basic items in the plan** (*Basisvarer i madplanen*) shows the basic items (salt, oil, butter …) the recipes use. Out of one? Tap **Tilføj til indkøb**, and the product is found by your settings.
- Below the list you see what is on the REMA list right now, and it can be emptied once you have shopped.

<img src="docs/images/rema-list.png" alt="What is on the REMA list right now" width="100%">

### Your favourite products on offer

<img src="docs/images/favorites.png" alt="Favourite products from the REMA app that are on offer" width="100%">

The products you have given a heart in the REMA 1000 app. Choose **Denne uge** (this week) or **Næste uge** (next week) to see which are on offer, with before and now price, and put them on the list with one tap. This week shows REMA's own prices, as in the app. Next week shows the avis's prices and text as soon as it is out, since REMA only has them from Sunday 02:00. Offers that only start on Thursday are shown with a blue *fra tor* badge until they start. Until next week's offers are out, this week's are shown. All favourites can be filtered.

### History

<img src="docs/images/history.png" alt="Earlier meal plans with price and dishes" width="100%">

Earlier meal plans with price, status and dishes. Open an old plan and send it to the REMA list again, or delete it.

### The family's favourite dishes and dishes you don't like

<img src="docs/images/family-favorites.png" alt="The family's favourite dishes with how often" width="100%">

Describe the dishes the family loves and how often they should be on the plan (every week, every 2 weeks, every month, only when the ingredients are on offer, or just for inspiration). Dishes you don't like never go on the plan.

### Light and dark mode

<img src="docs/images/plan-dark.png" alt="The meal plan in dark mode" width="100%">

### App on the home screen

Open `https://<your-home-assistant>/rema1000_app/app.html` in Safari or Chrome, log in and choose **Share → Add to Home Screen**. REMA 1000 then opens full screen with the REMA icon and your Home Assistant theme – also behind the notch and home bar. Pull down to refresh. The link is also under **Indstillinger** (settings) in the panel.

## Requirements

- Home Assistant **2026.1** or newer.
- A REMA 1000 account (the same login as on rema1000.dk and in the REMA 1000 app).
- For the meal plan: an **AI Task** in Home Assistant, e.g. from Google Generative AI, OpenAI or Anthropic (**Settings → Devices & services → Add integration**). The shopping list, search, offers and favourites work without AI.

## Installation

### With HACS (recommended)

[![Open your Home Assistant and add the repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dinnsen&repository=ha-rema1000&category=integration)

1. Tap the button above, or go to **HACS → ⋮ → Custom repositories** and add `https://github.com/Dinnsen/ha-rema1000` as an **Integration**.
2. Search for **REMA 1000** in HACS and tap **Download**.
3. Restart Home Assistant.

### Manually

1. Download the source code of the latest version under [Releases](https://github.com/Dinnsen/ha-rema1000/releases).
2. Copy the folder `custom_components/rema1000` to `config/custom_components/` in Home Assistant.
3. Restart Home Assistant.

## Setup

[![Open your Home Assistant and add REMA 1000.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rema1000)

1. Go to **Settings → Devices & services → Add integration** and choose **REMA 1000**.
2. Log in:

   | Field | Description |
   |---|---|
   | **E-mail** | The e-mail you log in to rema1000.dk and the REMA 1000 app with. |
   | **Password** | Your REMA 1000 password. It is stored in Home Assistant and only sent to REMA 1000. |

3. Open **REMA 1000** in the sidebar, go to **Indstillinger** (settings) and choose the family's rules. Then tap **Lav madplan** (make meal plan).

The integration logs in again by itself when the session expires. If you change your password, Home Assistant asks you for the new one (**Settings → Devices & services → REMA 1000**). To change the e-mail or password yourself, choose **⋮ → Reconfigure** on the integration. You can add several REMA 1000 accounts. Each gets its own entities, and the actions can target a given account; the panel shows the one added first.

## Settings in the panel

<img src="docs/images/settings.png" alt="Settings for AI, budget, organic, product requirements, things to avoid and allergies" width="100%">

The settings apply every time a meal plan is made and are stored per REMA 1000 account. The panel is in Danish; the Danish name of each setting is in brackets.

| Setting | What it does | Default |
|---|---|---|
| **AI Task entity** (*AI-opgave-entitet*) | Which AI Task makes the plan. *Home Assistants standard* uses the one chosen in the AI settings. | Default |
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
| **Fixed weekly items** (*Faste varer hver uge*) | Search REMA's range and pick a product (or write free text) that always goes on the list. | – |
| **We also shop late in the week** (*Vi handler også sidst på ugen*) | Some offers only start on Thursday. Off, the meal plan only uses offers that run on the shopping day. On, it may use them in dishes from that day; the shopping list is split into the shopping day and Thursday, each sent on its own. | Off |
| **Automation** (*Automatik*) | Make next week's plan when the new offers come out, and optionally send it to the REMA list. It is sent at 02:00 on the shopping day (Thursday's items at 02:00 on Thursday), when REMA has the week's products and prices. | Off |
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
| **Meal plan** | `calendar` | Each day's dinner as an event with time and ingredients. |
| **Make meal plan** | `button` | Makes a new plan with the settings from the panel. |
| **Send meal plan to shopping list** | `button` | Sends the newest plan to the REMA list. |

## Actions

| Action | Description | Fields |
|---|---|---|
| `rema1000.search_products` | Search REMA 1000's range with price, offers and organic. Returns a response. | `query` (required), `limit` (1–100, default 10), `config_entry_id` |
| `rema1000.get_offers` | All offers in the current or next catalogue. Returns a response. | `catalog` (`current` or `upcoming`), `config_entry_id` |
| `rema1000.add_items` | Add products (REMA product number or free text) to the REMA list. | `items` (required, list with `product_id` or `name` and optionally `amount`), `config_entry_id` |
| `rema1000.generate_meal_plan` | Make a meal plan in the background. | `start_date`, `send` (send the list when the plan is ready), `config_entry_id` |
| `rema1000.send_meal_plan` | Send a meal plan's shopping list to the REMA list. | `plan_id` (empty = newest), `part` (`main` = the shopping day, `late` = the Thursday items, `all`; default `main`), `config_entry_id` |

`config_entry_id` is only needed if you have several REMA 1000 accounts.

## Examples

**Add products from an automation:**

```yaml
action: rema1000.add_items
data:
  items:
    - product_id: 20494
      amount: 2
    - name: Opvasketabs
```

**Search for a product and use the response:**

```yaml
action: rema1000.search_products
data:
  query: letmælk
  limit: 5
response_variable: result
```

**Get a notification when next week's offers are out:**

```yaml
triggers:
  - trigger: state
    entity_id: sensor.rema_1000_next_offer_catalogue  # your id for Next offer catalogue
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
  - action: rema1000.generate_meal_plan
    data:
      send: true
```

**By voice:** Say *"Add milk to the shopping list"* to Assist (or Siri via the Home Assistant app) if **Shopping list** is exposed to Assist. The item is matched with a REMA product and shows in the REMA 1000 app.

**On a dashboard:** Show **Dinner today** in a tile card, **Shopping list** in a to-do list card and the **Meal plan** calendar in a calendar card.

The entity IDs depend on the account's name and your language; find them under **Settings → Devices & services → REMA 1000**.

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

Feel free to open an [issue](https://github.com/Dinnsen/ha-rema1000/issues) with the diagnostics file and a description. Please report security issues privately, see [SECURITY.md](SECURITY.md).

## Removing the integration

1. Go to **Settings → Devices & services → REMA 1000** and choose **⋮ → Delete** for each account. The panel disappears when the last account is deleted. Your list in the REMA 1000 app is not touched.
2. Installed with HACS: open **REMA 1000** in HACS and choose **⋮ → Remove**. Manually: delete the folder `config/custom_components/rema1000`.
3. Restart Home Assistant.

## Privacy

Your REMA 1000 login is stored in Home Assistant and only sent to REMA 1000. For the meal plan, the integration sends your settings, the week's offers, your favourite dishes, your wishes for the plan and the dishes of the last weeks (so they are not repeated) to the AI service you have chosen in Home Assistant – never your login or your e-mail.

## Support

If you like REMA 1000 for Home Assistant, you can [buy me a coffee](https://buymeacoffee.com/dinnsen).

## Licence

[MIT](LICENSE). The home-screen app includes [home-assistant-js-websocket](https://github.com/home-assistant/home-assistant-js-websocket) under the Apache-2.0 licence. REMA 1000 is a trademark of its owner; this project is not affiliated with REMA 1000.
