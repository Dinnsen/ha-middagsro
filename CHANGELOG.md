# Changelog

All notable changes to REMA 1000 for Home Assistant. The version is the one in `custom_components/rema1000/manifest.json`; a new version on `main` is released by itself with its section below as notes.

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
