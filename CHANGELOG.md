# Changelog

All notable changes to REMA 1000 for Home Assistant. The version is the one in `custom_components/rema1000/manifest.json`; a new version on `main` is released by itself with its section below as notes.

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
