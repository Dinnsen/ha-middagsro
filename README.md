# REMA 1000 til Home Assistant

Uofficiel integration til REMA 1000 Danmark. Lav ugens madplan med AI ud fra tilbudsavisen, og send indkøbslisten direkte til REMA 1000-appen. Din indkøbsliste i appen bliver samtidig en to-do-liste i Home Assistant.

> **Bemærk:** REMA 1000 har ikke et offentligt API. Integrationen bruger de samme kald som rema1000.dk og webshoppen og kan derfor holde op med at virke, hvis REMA ændrer deres side. Kun til personlig brug med din egen konto.

## Madplan

Et **REMA 1000-panel** i sidebaren samler det hele:

- **Madplan:** Ugens aftensmad lavet af den AI, du har sat op i Home Assistant (AI Task – fx Google, OpenAI eller Anthropic). Retterne bygges op om ugens tilbud.
- **Opskrifter:** Ingredienser og trin i stor skrift, afkrydsning, timere og en knap, der holder skærmen tændt, mens du laver mad.
- **Indkøb:** Den billigste REMA-vare til hver ingrediens efter dine økologi-regler, med pris, tilbud og samlet budget. Send listen til REMA 1000-appen med ét tryk, og tøm REMA-listen, når I har handlet.
- **Favoritter:** Dine favoritvarer fra REMA-appen – dem på tilbud nu og i næste avis vises øverst og kan tilføjes til listen med ét tryk.
- **Historik:** Tidligere madplaner.
- **Indstillinger:** Startdag, budget, økologi (udelukkende / foretrækkes hvis højst x % dyrere / ligeglad), krav til æg (skrabe-, frilands- eller økologiske), økologisk mælk og økologisk frugt og grønt, ting der skal undgås, allergier, familiens medlemmer, vegetar- og restedage, faste dage (fx rugbrødsdag), maks. tid på hverdage, basisvarer, faste ugevarer og familiens favoritretter med hyppighed.

**App på hjemmeskærmen:** Åbn `https://<din-home-assistant>/rema1000_app/index.html` i Safari eller Chrome, log ind og vælg *Del → Føj til hjemmeskærm*. Så åbner panelet i fuld skærm med REMA-ikon og dit Home Assistant-tema. Linket står også under Indstillinger i panelet.

Slå **automatik** til, så laves næste uges madplan, når den nye tilbudsavis udkommer – og sendes evt. direkte til REMA-listen.

Hvis indkøbslisten bliver over budget, beder integrationen AI'en om en billigere plan én gang og beholder den billigste.

## Funktioner

- **Madplan** (sensor), **Madplan** (kalender) og knapperne **Lav madplan** og **Send madplan til indkøbsliste**.
- **Indkøbsliste** (`todo`): Din primære REMA-liste, den der vises i appen. Tilføj, kryds af, ret antal og slet – ændringer vises i appen og omvendt. Det du tilføjer (også via Assist) matches automatisk med en REMA-vare; findes der ingen sikker match, tilføjes det som tekst. Skriv `3 x mælk` for at tilføje 3 stk.
- **Tilføj vare** (`text`): Skriv fx `letmælk`, `2 x rugbrød` eller `tre poser chips` – varen matches med REMA's sortiment og lægges på listen, ellers tilføjes den som tekst. Feltet tømmes bagefter, og attributterne viser hvad der blev tilføjet.
- **Dagens ret** (sensor): Dagens aftensmad fra madplanen med ingredienser, tid og morgendagens ret som attributter.
- **Indkøbsliste i alt** (sensor): Anslået pris for det, der mangler at blive købt.
- **Aktuel og næste tilbudsavis** (sensorer): Hvornår avisen gælder fra/til, og hvornår integrationen første gang så næste uges avis.
- **Handlinger:**
  - `rema1000.search_products` – søg i sortimentet med pris, tilbud og økologi-mærker
  - `rema1000.add_items` – tilføj varer (produkt-ID eller fritekst) til listen
  - `rema1000.get_offers` – hent alle tilbud i aktuel eller næste tilbudsavis
  - `rema1000.generate_meal_plan` – lav en madplan (evt. med `send: true`)
  - `rema1000.send_meal_plan` – send madplanens indkøbsliste til REMA-listen

Madplanen kræver en AI Task-entitet i Home Assistant (Indstillinger → Enheder og tjenester → fx Google Generative AI, OpenAI eller Anthropic).

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
