# REMA 1000 til Home Assistant

Uofficiel integration til REMA 1000 Danmark. Din indkøbsliste i REMA 1000-appen bliver en to-do-liste i Home Assistant, og du kan søge i sortimentet, se ugens tilbudsavis og tilføje varer fra automatiseringer og AI.

> **Bemærk:** REMA 1000 har ikke et offentligt API. Integrationen bruger de samme kald som rema1000.dk og webshoppen og kan derfor holde op med at virke, hvis REMA ændrer deres side. Kun til personlig brug med din egen konto.

## Funktioner

- **Indkøbsliste** (`todo`): Din primære REMA-liste, den der vises i appen. Tilføj, kryds af, ret antal og slet – ændringer vises i appen og omvendt. Skriv `3 x mælk` for at tilføje 3 stk.
- **Indkøbsliste i alt** (sensor): Anslået pris for det, der mangler at blive købt.
- **Aktuel og næste tilbudsavis** (sensorer): Hvornår avisen gælder fra/til, og hvornår integrationen første gang så næste uges avis.
- **Handlinger:**
  - `rema1000.search_products` – søg i sortimentet med pris, tilbud og økologi-mærker
  - `rema1000.add_items` – tilføj varer (produkt-ID eller fritekst) til listen
  - `rema1000.get_offers` – hent alle tilbud i aktuel eller næste tilbudsavis

Madplan med AI og et panel med opskrifter kommer i senere versioner.

## Installation

1. HACS → ⋮ → **Brugerdefinerede repositories** → tilføj `https://github.com/Dinnsen/ha-rema1000` som *Integration*.
2. Installer **REMA 1000** og genstart Home Assistant.
3. **Indstillinger → Enheder og tjenester → Tilføj integration → REMA 1000**, og log ind med samme e-mail og adgangskode som på rema1000.dk.

Integrationen logger selv ind igen, når sessionen udløber. Skifter du adgangskode, beder Home Assistant dig om den nye.

## Eksempler

Tilføj varer:

```yaml
action: rema1000.add_items
data:
  items:
    - product_id: 20494
      amount: 2
    - name: Opvasketabs
```

Søg efter varer:

```yaml
action: rema1000.search_products
data:
  query: letmælk
  limit: 5
response_variable: result
```

## Fejlfinding

Slå debug-log til under integrationen og se loggen. Adgangskoden logges aldrig.
