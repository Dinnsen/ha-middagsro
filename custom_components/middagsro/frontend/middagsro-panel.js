/* Middagsro – madplan og indkøb til REMA 1000 i Home Assistant. Ingen build-trin, ingen afhængigheder. */

const WEEKDAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"];
const AVOID_LABELS = {
  meat: "Kød",
  pork: "Svinekød",
  beef: "Oksekød",
  fish: "Fisk",
  shellfish: "Skaldyr",
  animal_products: "Animalske produkter (vegansk)",
  spicy: "Stærk mad",
};
const ALLERGY_LABELS = {
  gluten: "Gluten",
  lactose: "Laktose",
  milk: "Mælkeprotein",
  egg: "Æg",
  nuts: "Nødder",
  peanuts: "Jordnødder",
  soy: "Soja",
  sesame: "Sesam",
  celery: "Selleri",
  mustard: "Sennep",
  fish: "Fisk",
  shellfish: "Krebsdyr",
  molluscs: "Bløddyr",
  lupin: "Lupin",
  sulphites: "Sulfitter",
};
const FREQ_LABELS = {
  weekly: "Hver uge",
  biweekly: "Hver 2. uge",
  monthly: "Hver måned",
  on_offer: "Kun når på tilbud",
  inspiration: "Til inspiration",
};
const TYPE_LABELS = { normal: "", vegetar: "Vegetar", rester: "Rester", fast: "Fast dag", tom: "Ingen ret", egen: "Skrevet selv" };
const EGG_LABELS = {
  caged: "Skrabeæg (alle æg)",
  free_range: "Mindst frilandsæg",
  organic: "Kun økologiske æg",
};
const GENERATING_MESSAGE = "Madplanen er ved at blive lavet – det tager typisk 1-2 minutter.";
const onOffer = (p) =>
  Boolean(p.is_advertised || p.is_campaign || (p.normal_price && p.price && p.price < p.normal_price - 0.01));
const validTo = (iso) => (iso && !iso.startsWith("2099") ? shortDate(iso.slice(0, 10)) : "");
const STATUS_LABELS = { draft: "Klar", sent: "Sendt", generating: "Laves", error: "Fejl" };
// Line icons for the tab bar (shown when it sits at the bottom on a phone).
const TAB_ICONS = {
  home: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5h-5v5H5a1 1 0 0 1-1-1Z"/></svg>',
  plan: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4M7.5 14h3M13.5 14h3M7.5 17h3"/></svg>',
  recipes: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7.5c-1.6-1.6-4.3-2.3-8-2.2v12.5c3.7-.1 6.4.6 8 2.2 1.6-1.6 4.3-2.3 8-2.2V5.3c-3.7-.1-6.4.6-8 2.2zM12 7.5V20"/></svg>',
  shopping: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2.2l2.3 10.3a1 1 0 0 0 1 .7h8.9a1 1 0 0 0 1-.8L20 8H6.3"/><circle cx="9.5" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/></svg>',
  favorites: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z"/></svg>',
  inventory: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h16v12H4zM3 4h18v4H3zM9 12h6"/></svg>',
  health: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2-5 4 10 2-5h6"/></svg>',
  history: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg>',
  budget: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5h14.5a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18V6.5A1.5 1.5 0 0 1 5.5 5H17"/><path d="M16 12.5h4v3h-4a1.5 1.5 0 0 1 0-3z"/></svg>',
};
const NAV_STORAGE = "middagsro.navigation.v1";
const PHONE_TABS = ["home", "plan", "shopping", "budget"];
const OLD_PHONE_TABS = ["plan", "recipes", "shopping", "favorites"];
const MORE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>';
const CLOSE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
// Shown on every button that asks the AI for something.
const AI_ICON = '<svg class="ai" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 3.5l1.6 4.6 4.6 1.6-4.6 1.6L10 15.9l-1.6-4.6L3.8 9.7l4.6-1.6z"/><path d="M17.5 13.5l.9 2.4 2.4.9-2.4.9-.9 2.4-.9-2.4-2.4-.9 2.4-.9z"/></svg>';
const aiLabel = (label) => `${AI_ICON}${label}`;
const RATE_ICONS = {
  like: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10.5V20H4.2a.7.7 0 0 1-.7-.7v-8.1a.7.7 0 0 1 .7-.7H7zm0 0 3.6-6.2c.4-.7 1.3-.9 2-.5.6.4.9 1.1.7 1.8L12.6 9h5.6a2 2 0 0 1 2 2.4l-1.3 6.9a2 2 0 0 1-2 1.7H7"/></svg>',
  dislike: '<svg viewBox="0 0 24 24" aria-hidden="true" style="transform:rotate(180deg)"><path d="M7 10.5V20H4.2a.7.7 0 0 1-.7-.7v-8.1a.7.7 0 0 1 .7-.7H7zm0 0 3.6-6.2c.4-.7 1.3-.9 2-.5.6.4.9 1.1.7 1.8L12.6 9h5.6a2 2 0 0 1 2 2.4l-1.3 6.9a2 2 0 0 1-2 1.7H7"/></svg>',
  favorite: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z"/></svg>',
};
const CAMERA_ICON =
  '<svg viewBox="0 0 24 24" aria-hidden="true" class="ico"><path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.5-2h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/><circle cx="12" cy="13" r="3.5"/></svg>';

// A photo as a JPEG data URL at most `max` pixels on its longest side (the AI reads it fine,
// and the websocket message stays small).
const shrinkPhoto = (file, max) =>
  new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.naturalWidth, img.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.naturalWidth * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.8));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Billedet kunne ikke åbnes"));
    };
    img.src = url;
  });

const MOVE_ICONS = {
  up: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
  down: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M6 13l6 6 6-6"/></svg>',
};
// A name's genitive in Danish: "Nettos", but "føtex'" (and "REMA's", as the app always said).
const genitive = (name) => (name === "REMA 1000" ? "REMA's" : /[sxz]$/i.test(name) ? `${name}'` : `${name}s`);
const REMA_ID = "11deC"; // REMA 1000 on Tjek: its avis is shown first among the shops
const RATE_LABELS = { like: "Synes om", dislike: "Synes ikke om", favorite: "Favorit" };
const SURPRISE_ICON = '<svg class="ai" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 11h16v9H4zM12 11v9M3 7.5h18V11H3zM12 7.5C10 3 6 4 7.5 6.5 8.4 8 12 7.5 12 7.5zm0 0c2-4.5 6-3.5 4.5-1C15.6 8 12 7.5 12 7.5z"/></svg>';
const RECIPE_SORTS = { name: "Navn", newest: "Senest tilføjet", most_used: "Mest brugt", quickest: "Hurtigst" };
// What a day can be: in Tilpas dagene (this week) and under Faste dage (every week).
const DAY_KIND_LABELS = { ai: "AI vælger", pick: "Vælg selv ret", skip: "Spring over", rest: "Restedag", rye: "Rugbrødsdag", veg: "Vegetardag", fixed: "Fast ret" };
const FIXED_KINDS = ["rest", "rye", "veg", "skip", "fixed"];
const fixedKindOf = (f) =>
  FIXED_KINDS.includes(f?.kind) ? f.kind : /\brest/i.test(f?.text || "") ? "rest" : /\brugbrød/i.test(f?.text || "") ? "rye" : "fixed";
const RECIPE_FILTERS = { all: "Alle", favorite: "Favoritter", like: "Synes om", dislike: "Synes ikke om", unlinked: "Mangler varer" };
// 👍, 👎 and ❤️: pressing the same again takes it back, the other one replaces it (as the server does).
const applyRating = (recipe, action) => {
  const r = { ...recipe };
  if (action === "like") Object.assign(r, r.rating === "like" ? { rating: null, favorite: false } : { rating: "like" });
  if (action === "dislike") Object.assign(r, r.rating === "dislike" ? { rating: null } : { rating: "dislike", favorite: false });
  if (action === "favorite") Object.assign(r, r.favorite ? { favorite: false } : { favorite: true, rating: "like" });
  return r;
};
const rateToast = (recipe) =>
  recipe.favorite
    ? `${recipe.name} er en favorit – gemt i opskriftsamlingen.`
    : recipe.rating === "like"
      ? `I synes om ${recipe.name} – gemt i opskriftsamlingen.`
      : recipe.rating === "dislike"
        ? `${recipe.name} kommer ikke på madplanen igen.`
        : `Bedømmelsen af ${recipe.name} er fjernet.`;
const normName = (name) => String(name || "").toLowerCase().split(/\s+/).filter(Boolean).join(" ");
const CREDIT = `<p class="credit">Udviklet af Christian Dinnsen <a class="gh-link" href="https://github.com/Dinnsen" target="_blank" rel="noopener noreferrer" aria-label="Christian Dinnsen på GitHub" title="Christian Dinnsen på GitHub"><svg class="gh" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg></a></p>`;
const TABS = [
  ["home", "Forside"],
  ["plan", "Madplan"],
  ["recipes", "Opskrifter"],
  ["shopping", "Indkøb"],
  ["favorites", "Favoritter"],
  ["budget", "Økonomi"],
  ["health", "Sundhed"],
  ["inventory", "Spisekammer"],
  ["history", "Historik"],
  ["settings", "Indstillinger"],
];

// The look, chosen per person (Home Assistant keeps it with the user): Theme Studio (the theme), Frisk, Hverdag.
const LOOK_NAMES = { studio: "Theme Studio", frisk: "Frisk", hverdag: "Hverdag" };
// The message centre's kinds: [key, name, when, icon, colour, title, example, time].
const MSG_KINDS = [
  ["watch", "Tilbud på overvågningslisten", "Når noget kommer på tilbud", "mdi:tag-heart", "#E4568C", "🔔 Merrild kaffe er på tilbud", "🛒 REMA 1000: Merrild kaffe – 35,00 kr.", "08:05"],
  ["budget", "Madbudget", "Når 80 % af ugen er brugt", "mdi:wallet-outline", "#0FA3A3", "💰 312 kr. tilbage af ugens madbudget", "Brugt 1.288 kr. af 1.600 kr.", "17:40"],
];
const MSG_ICONS = ["mdi:tag-heart", "mdi:sale", "mdi:bell", "mdi:wallet-outline", "mdi:cash", "mdi:cart", "mdi:silverware-fork-knife", "mdi:food-apple"];
const BELL_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.6 1.9H4.4z"/><path d="M10 20.6a2.1 2.1 0 0 0 4 0"/></svg>';
// "Ryd" next to a search field: clears it and its results.
const clearBtn = (arg) => `<button class="btn small" data-action="clear-field" data-arg="${arg}" aria-label="Ryd søgefeltet">Ryd</button>`;

const SETTING_ICONS = {
  ai: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 3.5l1.9 5.1 5.1 1.9-5.1 1.9L11 17.5l-1.9-5.1L4 10.5l5.1-1.9z"/><path d="M18 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/></svg>',
  plan: TAB_ICONS.plan,
  family: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="8.5" cy="8" r="2.8"/><circle cx="16.5" cy="9.5" r="2.2"/><path d="M3.5 19c.4-3.3 2.4-5.3 5-5.3s4.6 2 5 5.3M13.8 15.2c.8-.9 1.7-1.3 2.7-1.3 2 0 3.5 1.6 3.9 4.6"/></svg>',
  dishes: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="6.5"/><circle cx="12" cy="13" r="3"/><path d="M4 4v5M2.8 4v3M5.2 4v3M4 9v11M20 4c-1.6 1.3-2 3.5-2 6h2v10"/></svg>',
  shopping: TAB_ICONS.shopping,
  rules: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/></svg>',
  nutrition: TAB_ICONS.health,
  mealie: TAB_ICONS.recipes,
  sites: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5s1.1-6.1 3.4-8.5z"/></svg>',
  watch: BELL_ICON,
  messages: BELL_ICON,
  look: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18c1.2 0 1.8-.8 1.8-1.7 0-1.1-.9-1.5-.9-2.6 0-1 .8-1.7 1.8-1.7H17a4 4 0 0 0 4-4C21 6.5 17 3 12 3z"/><circle cx="7.5" cy="11" r="1.2"/><circle cx="10" cy="7" r="1.2"/><circle cx="15" cy="7" r="1.2"/></svg>',
  budget: TAB_ICONS.budget,
  shop: TAB_ICONS.shopping,
  chains: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5 5.5 4h13L20 9.5M4 9.5h16M4 9.5c0 1.7 1.3 2.5 2.7 2.5S9.3 11.2 9.3 9.5c0 1.7 1.3 2.5 2.7 2.5s2.7-.8 2.7-2.5c0 1.7 1.3 2.5 2.7 2.5S20 11.2 20 9.5M5.5 12v8h13v-8M10 20v-4.5h4V20"/></svg>',
  app: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/></svg>',
};

// The settings' sub-pages, with a one-line summary of what is chosen.
const SETTINGS_SECTIONS = (panel) => {
  const f = panel._form;
  const state = panel._state;
  const organic = { only: "Kun økologi", prefer: "Foretræk økologi", none: "Billigst" }[f.organic] || "";
  const allergies = f.allergies.length + (f.allergies_other.trim() ? 1 : 0);
  const dislikes = (state.settings.disliked_dishes || []).length;
  const shop = state.shop || { name: "REMA 1000", rema: true };
  return [
    { key: "shop", title: "Butik", form: !shop.rema,
      summary: shop.rema ? "REMA 1000 · priser på alle varer og REMA-appens liste" : shop.bilka_cart ? (shop.cart_name === "Nemlig.com" ? "Nemlig.com · priser på alle varer og kurven på nemlig.com" : `BilkaToGo · ${shop.pickup_name} · kurv i appen`) : `${shop.name} · tilbudsavis og liste i Home Assistant` },
    { key: "plan", title: "Ugens madplan", form: true,
      summary: `${f.days} dage fra ${WEEKDAYS[f.start_weekday].toLowerCase()} · ${f.monthly_budget ? "budget efter madbudgettet" : `budget ${f.budget} kr.`}${f.auto_generate ? " · laves automatisk" : ""}` },
    { key: "ai", title: "AI til madplanen", form: true,
      summary: state.ai_entities?.find(x => x.entity_id === f.ai_task_entity)?.name || "Home Assistants standard" },
    { key: "budget", title: "Madbudget", form: true,
      summary: f.monthly_budget ? `${f.budget_period === "week" ? `${kr0(f.weekly_budget)} om ugen` : `${kr0(f.monthly_budget)} om måneden`}${f.budget_notify ? " · besked ved 80 %" : ""}` : "Ikke sat op" },
    { key: "family", title: "Familie og portioner", form: true,
      summary: `${f.household.length} personer${f.portion_percent > 100 ? ` · +${f.portion_percent - 100} % mad` : ""}${allergies ? ` · ${allergies} allergi${allergies === 1 ? "" : "er"}` : ""}${f.avoid.length ? ` · undgår ${f.avoid.length}` : ""}` },
    { key: "dishes", title: "Retter og vaner", form: true,
      summary: `${f.leftover_days} restedage · ${(f.fixed_days || []).length} faste dage · ${f.min_vegetarian}-${f.max_vegetarian} vegetarretter` },
    { key: "shopping", title: "Indkøb og basisvarer", form: true,
      summary: `${organic}${f.must_haves.length ? ` · ${f.must_haves.length} faste varer` : ""}` },
    { key: "rules", title: "Det skal AI'en huske", form: false,
      summary: `${(state.settings.rules || []).length} punkter` },
    { key: "nutrition", title: "Næring", form: true,
      summary: f.nutrition_enabled ? `${f.kcal_min}–${f.kcal_max} kcal · ${f.protein_pct}/${f.carb_pct}/${f.fat_pct} %` : "Slået fra" },
    { key: "chains", title: "Andre butikker", form: true,
      summary: (f.chains || []).filter((id) => id !== panel._storeId()).length ? `${f.chains.filter((id) => id !== panel._storeId()).map((id) => panel._chainName(id)).join(", ")}${f.plan_all_chains ? " · madplan på tværs" : " · sammenligning"}` : `Kun ${panel._shopName()}` },
    { key: "messages", title: "Beskeder", form: true,
      summary: [f.watch_notify ? "Tilbud" : "", f.budget_notify ? "Madbudget" : "", f.quiet?.on ? `stille ${f.quiet.from}–${f.quiet.to}` : ""].filter(Boolean).join(" · ") || "Ingen beskeder" },
    { key: "look", title: "Udseende", form: false, summary: LOOK_NAMES[panel._look()] },
    { key: "watch", title: "Overvågning og beskeder", form: true,
      summary: `${(state.watch || []).length} overvåget${f.watch_notify ? " · besked ved tilbud" : " · ingen beskeder"}` },
    { key: "sites", title: "Opskrifter og madsider", form: true,
      summary: (f.recipe_sites || []).length
        ? `${(state.recipe_sites || []).filter((x) => f.recipe_sites.includes(x.id)).map((x) => x.name).join(", ")}${f.recipe_sites_in_plan ? " · i madplanen" : ""}`
        : "Ingen valgt" },
    { key: "mealie", title: "Mealie", form: true,
      summary: state.mealie?.available ? (f.mealie_recipes || f.mealie_calendar ? "Slået til" : "Slået fra") : "Ikke sat op" },
    { key: "app", title: "App på hjemmeskærmen", form: false, summary: "Åbn Middagsro som en app på telefonen" },
  ].map((sec) => ({ ...sec, icon: SETTING_ICONS[sec.key] }));
};

/** Today's date as YYYY-MM-DD in the phone's own time zone. */
function localToday() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// Whole kroner, for budgets: "1.127 kr."
const kr0 = (value) =>
  value == null || Number.isNaN(Number(value)) ? "–" : `${Math.round(Number(value)).toLocaleString("da-DK")} kr.`;
const MONTHS_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
const kr = (value) =>
  value == null || Number.isNaN(Number(value))
    ? "–"
    : `${Number(value).toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.`;
const MUST_GROUPS = { "": "Faste varer", morgenmad: "Morgenmad", madpakker: "Madpakker", husholdning: "Husholdning" };
const dateLabel = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return `${WEEKDAYS[(d.getDay() + 6) % 7]} ${d.getDate()}/${d.getMonth() + 1}`;
};
// "13. nov. 2026" from an ISO date or datetime.
const longDate = (iso) => {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getDate()}. ${MONTHS_SHORT[d.getMonth()]}. ${d.getFullYear()}`;
};
// "15.21.13" – the clock time of a receipt.
const clockTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, "0")).join(".");
};
// A price or price range for a bought item, e.g. "4,95 kr." or "3,95–5,95 kr."
const priceRange = (min, max) => {
  if (min == null && max == null) return "";
  if (min == null || max == null || min === max) return kr(min == null ? max : min);
  const fmt = (v) => Number(v).toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${fmt(min)}–${fmt(max)} kr.`;
};
// "torsdag" for a date.
const dayName = (iso) => {
  const d = new Date(`${localDay(iso)}T12:00:00`);
  return WEEKDAYS[(d.getDay() + 6) % 7].toLowerCase();
};
// "tor 15/10": short weekday and date, for offers that start later in the week.
const dayShort = (iso) => {
  if (!iso) return "";
  const day = localDay(iso);
  const d = new Date(`${day}T12:00:00`);
  return `${WEEKDAYS[(d.getDay() + 6) % 7].slice(0, 3).toLowerCase()} ${shortDate(day)}`;
};
const shortDate = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return `${d.getDate()}/${d.getMonth() + 1}`;
};
// When the list was sent: "i dag kl. 19.15", "i går kl. 8.05" or "18/10 kl. 9.30".
const sentWhen = (iso) => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  const time = `kl. ${d.getHours()}.${pad(d.getMinutes())}`;
  const day = localDay(iso);
  const today = localToday();
  const y = new Date(`${today}T12:00:00`);
  y.setDate(y.getDate() - 1);
  const yesterday = localDay(y.toISOString());
  return day === today ? `i dag ${time}` : day === yesterday ? `i går ${time}` : `${shortDate(day)} ${time}`;
};
// A timestamp from the avis (often UTC, e.g. 22:00 the day before) as a local day.
const localDay = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const clone = (obj) => JSON.parse(JSON.stringify(obj));

class Rema1000Panel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "home";
    this._navigation = this._readNavigation();
    this._state = null;
    this._plan = null; // the plan being viewed (latest unless chosen in history)
    this._viewingLatest = true;
    this._day = 0;
    this._dayKey = null; // plan + date the recipe day was chosen for
    this._form = null;
    this._dirty = false;
    this._busy = false;
    this._toast = null;
    this._error = null;
    this._search = { query: "", results: [], loading: false };
    this._editFav = null;
    this._settingsSection = null; // the open sub-page of the settings
    this._recipesSub = "collection"; // "week" (the plan's recipes) or "collection"
    this._rc = { query: "", sort: "newest", filter: "all", link: "", importing: false, scanning: false };
    // REMA 1000's own recipes: the chosen category, the pages read, and a day to put one on.
    this._rr = { key: "popular", query: "", page: 0, last: 1, total: 0, recipes: [], tags: [], loading: false, error: null };
    this._remaPick = null;
    this._chains = null; // the chains that can be chosen, with logos
    this._chain = null; // the chain whose offers page is open
    this._chainOffers = {}; // dealer id -> {offers, loading, error}
    this._chainQuery = "";
    this._compare = null; // {key, lines, chains, loading}: plan items cheaper elsewhere
    this._favCompare = {}; // week -> {product id: cheaper offer}
    this._everywhere = { query: "", loading: false, data: null, error: null }; // one search, every shop
    this._newFav = { text: "", frequency: "weekly" };
    this._newDislike = "";
    this._startDate = null;
    this._skip = new Set(); // ISO dates in the next plan that get no dinner
    this._noteOpen = false; // the "wishes for the plan" popup
    this._noteDraft = "";
    // Other popups: a day of the plan (recipe or swap the dish), the basic items.
    this._modal = null;
    this._newRule = "";
    this._editRule = null; // {index, text}
    this._dictating = null; // the field being dictated into
    this._health = null; // {planId, data, loading, error}
    this._shopSearch = { main: { query: "", results: [], loading: false }, late: { query: "", results: [], loading: false } };
    this._moreOpen = false; // the "Mere" sheet on a phone
    this._checked = {}; // ingredient/step ticks per plan+day
    this._timers = {};
    this._favWeek = "current"; // favourites on offer this week or next week
    this._favCache = {}; // week -> {products, on_offer, catalog, fallback}
    this._favsLoading = false;
    this._favsError = null;
    this._favFilter = "";
    // The watch list's offers, and the search for products to add to the favourites.
    this._watch = { items: null, loading: false, error: null };
    this._favSearch = { query: "", results: [], loading: false };
    // The food budget: the purchase being booked, and the economy page's month/year view.
    this._book = { amount: "", store: null, date: "", monthly: "" }; // store: null is the family's shop
    // Dishes chosen for a day of the next plan: {date: {dish, source, recipe_id | slug}}.
    this._picks = {};
    this._dayKinds = {}; // ISO date -> {kind, text}: what a day of the next plan is this week
    this._sites = { query: "", results: [], loading: false, error: null, searched: false, opening: null };
    this._budgetSpan = "month";
    this._spendSpan = "month"; // the REMA-spend overview: "week" / "month" / "year"
    this._rl = { email: "", password: "", label: "" }; // add-an-extra-receipt-login form
    // The Historik page: which sub-tab, and the receipt opened in the detail view.
    this._histSub = "indkob"; // "indkob" (receipts), "plans" (meal plans), "varer" (items)
    this._receiptId = null; // the receipt being opened / shown (null = the list)
    this._receipt = null; // its full contents, once fetched
    this._receiptLoading = false;
    this._itemFilter = "";
    this._wake = null;
    this._wakeWanted = false;
    this._onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      if (this._wakeWanted && !this._wake) this._requestWake();
      // Back from the background: the list and the plan may have moved on (the partner's phone,
      // an automatic plan), and a plan being made keeps being watched.
      const generating = this._state?.status?.state === "generating";
      if (this._state && this._hass && (generating || Date.now() - (this._loadedAt || 0) > 60000)) this._load(true);
    };
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && (this._noteOpen || this._modal)) {
        this._noteOpen = false;
        if (this._modal?.kind === "notice") this._ws("middagsro/notice_seen", { notice: this._modal.notice }).catch(() => {});
        if (!this._modal?.busy) this._modal = null;
        this._renderModal();
      }
    });
    this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onInput(ev));
    // Folded sections stay as the family left them when the panel redraws.
    this.shadowRoot.addEventListener("toggle", (ev) => {
      const key = ev.target?.dataset?.fold;
      if (!key) return;
      this._folds ||= new Set();
      if (ev.target.open) this._folds.add(key);
      else this._folds.delete(key);
    }, true);
    this.shadowRoot.addEventListener("touchstart", (ev) => this._onTouchStart(ev), { passive: true });
    this.shadowRoot.addEventListener("touchend", (ev) => this._onTouchEnd(ev), { passive: true });
  }

  // The look, per person: Theme Studio (the default, as before), Frisk or Hverdag.
  _looks() {
    return ["studio", "frisk", "hverdag"];
  }

  _look() {
    return this._looks().includes(this._lookChoice) ? this._lookChoice : "studio";
  }

  _applyLook() {
    if (this._lookAsked === undefined && this._hass?.callWS) {
      this._lookAsked = true;
      this._hass.callWS({ type: "frontend/get_user_data", key: "middagsro_look" }).then((answer) => { this._lookChoice = answer?.value || null; this._applyLook(); }).catch(() => {});
    }
    this.setAttribute("look", this._look());
    this.toggleAttribute("dark", Boolean(this._hass?.themes?.darkMode));
  }

  _setLook(look) {
    if (!this._looks().includes(look)) return;
    this._lookChoice = look;
    this._applyLook();
    this._hass?.callWS?.({ type: "frontend/set_user_data", key: "middagsro_look", value: look }).catch(() => {});
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    this._applyLook();
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first) {
      this._load();
      // A page asked for before Home Assistant was there (its data loads with hass).
      if (this._pendingPath !== undefined) {
        const path = this._pendingPath;
        this._pendingPath = undefined;
        this._applyPath(path);
      }
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  /* Home Assistant's address below /middagsro: /plan, /recipes, /recipes/<date>, /shopping, ... */
  set route(route) {
    const path = route?.path || "";
    if (this._embed || path === this._routePath) return;
    this._routePath = path;
    this._applyPath(path);
  }

  /* Shown inside a dashboard card's pop-up or card: one page, no toolbar or tabs. */
  set embed(embed) {
    this._embed = embed || null;
    this.toggleAttribute("embed", !!embed);
    if (embed?.view) this._applyPath(embed.view);
  }

  get embed() {
    return this._embed;
  }

  // "recipes/2026-10-23" -> the recipes tab on that day; an unknown page is the meal plan.
  _applyPath(path) {
    if (!this._hass) {
      this._pendingPath = path;
      return;
    }
    const [tab, date] = String(path || "").replace(/^\/+/, "").split("/");
    const key = TABS.some(([k]) => k === tab) ? tab : tab ? "plan" : "home";
    if (key === "recipes") {
      this._recipesSub = "week";
      this._wantDate = /^\d{4}-\d{2}-\d{2}$/.test(date || "") ? date : localToday();
    }
    if (key !== this._tab) this._goTab(key);
    else if (this._state) this._render();
  }

  // The page's own address, so a reload or a link opens the same page (not inside a card).
  get _path() {
    if (this._tab !== "recipes") return this._tab;
    const day = this._recipeDays()[this._day]?.day;
    return day ? `recipes/${day.date}` : "recipes";
  }

  _syncPath() {
    if (this._embed) return;
    const base = "/middagsro";
    if (!location.pathname.startsWith(base)) return;
    const next = `${base}/${this._path}`;
    if (location.pathname !== next) history.replaceState(history.state, "", next + location.search);
    this._routePath = `/${this._path}`;
  }

  get _static() {
    return this._panel?.config?.static_url || "/middagsro_static";
  }

  /* Images are cached for a long time: the version in the address makes a new version load new images */
  _img(name) {
    const v = this._panel?.config?.version;
    return `${this._static}/${name}${v ? `?v=${encodeURIComponent(v)}` : ""}`;
  }

  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisibility);
    // No zooming: pinch (Safari's gesture events) and two-finger touches -
    // except back out of a zoom the phone made itself (turning it, say).
    const zoomed = () => (window.visualViewport?.scale || 1) > 1.01;
    this._noZoom = (ev) => {
      if (!zoomed()) ev.preventDefault();
    };
    this._noPinch = (ev) => {
      if (ev.touches?.length > 1 && !zoomed()) ev.preventDefault();
    };
    // Turned sideways and back, iOS may leave the page zoomed in with larger text:
    // the viewport is reset to its normal scale.
    this._unzoom = () => {
      setTimeout(() => {
        if (!zoomed()) return;
        const meta = document.querySelector('meta[name="viewport"]');
        if (!meta) return;
        const content = meta.getAttribute("content") || "width=device-width, initial-scale=1";
        meta.setAttribute("content", `${content.replace(/,?\s*maximum-scale=[^,]*/g, "")}, maximum-scale=1`);
        setTimeout(() => meta.setAttribute("content", content), 400);
      }, 350);
    };
    // Not inside a dashboard card: the dashboard decides about zooming there.
    if (!this._embed) {
      document.addEventListener("gesturestart", this._noZoom, { passive: false });
      document.addEventListener("touchmove", this._noPinch, { passive: false });
      window.addEventListener("orientationchange", this._unzoom);
      window.visualViewport?.addEventListener("resize", this._unzoom);
      // Landscape must not enlarge the text (iOS text autosizing).
      document.documentElement.style.setProperty("-webkit-text-size-adjust", "100%");
      document.documentElement.style.setProperty("text-size-adjust", "100%");
    }
    this._tick = setInterval(() => this._tickTimers(), 1000);
    if (this._hass && !this._state) this._load();
    else if (this._hass && this._state?.status?.state === "generating") this._load(true);
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisibility);
    document.removeEventListener("gesturestart", this._noZoom);
    document.removeEventListener("touchmove", this._noPinch);
    if (this._unzoom) {
      window.removeEventListener("orientationchange", this._unzoom);
      window.visualViewport?.removeEventListener("resize", this._unzoom);
    }
    this._stopDictation?.();
    clearInterval(this._tick);
    clearTimeout(this._poll);
    this._releaseWake();
  }

  // ------------------------------------------------------------------ data

  async _ws(type, data = {}) {
    const entry = type !== "middagsro/state" && this._state?.entry_id ? { entry_id: this._state.entry_id } : {};
    return this._hass.callWS({ type, ...entry, ...data });
  }

  async _load(silent = false, refresh = false) {
    const before = this._signature();
    try {
      const state = await this._ws("middagsro/state", refresh ? { refresh: true } : {});
      if (this._state && state.entry_id !== this._state.entry_id) {
        location.reload(); // discard account-specific caches before showing another shop
        return;
      }
      const first = !this._state;
      this._state = state;
      if (first && state.start_new_plan) { this._viewingLatest = false; this._plan = null; }
      else if (first && state.switched_plan?.kind === "freezer") { this._viewingLatest = false; this._plan = state.switched_plan; }
      this._error = null;
      this._loadedAt = Date.now();
      if (!this._startDate || !this._startDateTouched) this._startDate = state.default_start;
      // The plan looked at from the history is the newest now (a newer one was deleted),
      // or is gone itself: show the newest, without the "older plan" banner.
      if (!this._viewingLatest && this._plan?.kind !== "freezer") {
        const id = this._plan?.id;
        if (!id || id === state.latest_plan?.id || !(state.plans || []).some((p) => p.id === id)) this._viewingLatest = true;
      }
      if (this._viewingLatest) this._plan = state.latest_plan;
      else if (this._plan?.kind === "freezer") this._plan = await this._ws("middagsro/plan", { plan_id: this._plan.id });
      if (!this._form || !this._dirty) this._form = clone(state.settings);
      if (!this._chains) this._loadChains();
      // A one-time note after an update (not in the dashboard cards).
      const notice = (state.notices || [])[0];
      if (notice && !this._modal && !this._noticeShown && !this.hasAttribute("embed")) {
        this._noticeShown = true;
        this._modal = { kind: "notice", notice };
        setTimeout(() => this._renderModal(), 0);
      }
    } catch (err) {
      this._error = err?.message || String(err);
    }
    clearTimeout(this._poll);
    if (this._state?.status?.state === "generating") {
      this._poll = setTimeout(() => this._load(true), 3000);
    }
    // Polling: don't redraw the page under the user's fingers unless something changed
    // (the settings form never, while polling).
    if (silent && (this._tab === "settings" || before === this._signature())) {
      this._renderStatus();
      return;
    }
    this._render();
  }

  // What the page is built from: when it is the same, there is nothing to redraw.
  _signature() {
    const s = this._state;
    if (!s) return "";
    return JSON.stringify([
      s.status, s.latest_plan?.id, s.latest_plan?.total, s.plans?.length, s.note, s.freezer_plans,
      s.timeline?.length, s.recipes?.length, s.favorites?.length, s.rema_list?.items?.length,
      s.watch?.length, s.own_favorites?.length,
    ]);
  }

  // The to-do list the quick "+ list" buttons put things on, when the family chose one.
  _quickTodo() {
    const id = this._state?.settings?.quick_todo_entity;
    const state = id ? this._hass?.states?.[id] : null;
    return state ? { id, name: state.attributes?.friendly_name || id } : null;
  }

  _quickLabel() {
    const todo = this._quickTodo();
    return todo ? `+ ${todo.name}` : "+ REMA-listen";
  }

  // One product on the REMA list in the app (or the to-do list chosen for the quick
  // button); the meal plan's list is left as it is.
  _addToRemaList(productId, name) {
    const todo = this._quickTodo();
    if (todo) return this._addToTodo(todo, name);
    this._run(() => this._ws("middagsro/list/add", { product_id: Number(productId), amount: 1 }), `${name} er sat på ${this._listName()}.`);
  }

  _addToTodo(todo, name) {
    this._run(() => this._hass.callService("todo", "add_item", { item: name }, { entity_id: todo.id }), `${name} er sat på ${todo.name}.`);
  }

  // A toast is its own little render: it never redraws the page under the user's fingers.
  _say(message) {
    this._toast = message;
    this._toastAction = null;
    this._renderToast();
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = null;
      this._renderToast();
    }, 3500);
  }

  // Changing a purchase booked wrong: amount, day, shop and note, or deleting it.
  _purchaseModal(m) {
    const chains = [this._storeId(), ...(this._state.settings.chains || []).filter((id) => id !== this._storeId()), "other"];
    if (m.store && !chains.includes(m.store)) chains.splice(1, 0, m.store);
    const chip = (id) => `<button class="chip ${m.store === id ? "active" : ""}" data-action="pedit-store" data-arg="${esc(id)}">${id === "other" ? "Andet" : esc(this._chainName(id))}</button>`;
    return `<div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="pedit-title">
        <div class="dialog-top"><h2 id="pedit-title">Ret købet</h2>
          <button class="icon-btn close" data-action="modal-close" aria-label="Luk">${CLOSE_ICON}</button></div>
        <div class="book">
          <input type="text" inputmode="decimal" data-bind="pedit" data-field="amount" value="${esc(m.amount)}" placeholder="Beløb" aria-label="Beløb">
          <input type="date" data-bind="pedit" data-field="date" value="${esc(m.date)}" max="${localToday()}" aria-label="Dato">
        </div>
        <div class="book-stores">${chains.map(chip).join("")}</div>
        <label class="field">Note <input type="text" data-bind="pedit" data-field="note" value="${esc(m.note)}" maxlength="120" placeholder="${m.store === "other" ? "Fx Bager Jensen" : "Valgfri"}"></label>
        <div class="row wrap dialog-actions">
          <button class="btn primary" data-action="pedit-save">Gem</button>
          <button class="btn danger" data-action="purchase-delete" data-arg="${esc(m.id)}">Slet købet</button>
          <span class="spacer"></span>
          <button class="btn" data-action="modal-close">Annullér</button>
        </div>
      </div>`;
  }

  _renderToast() {
    const node = this.shadowRoot.querySelector("#toast");
    const a = this._toast ? this._toastAction : null;
    if (node) node.innerHTML = this._toast ? `<div class="toast">${esc(this._toast)}${a ? ` <button class="toast-btn" data-action="${esc(a.action)}" data-arg="${esc(a.arg)}">${esc(a.label)}</button>` : ""}</div>` : "";
  }

  _renderBusy() {
    const node = this.shadowRoot.querySelector("#busy");
    if (node) node.innerHTML = this._busy ? '<span class="spinner small"></span>' : "";
  }

  // Actions run one after the other: a tap while something else is in flight is
  // not dropped, it waits its turn.
  _run(fn, okMessage) {
    const job = () => this._runNow(fn, okMessage);
    this._queue = (this._queue || Promise.resolve()).then(job, job);
    return this._queue;
  }

  async _runNow(fn, okMessage) {
    this._toastAction = null;
    this._busy = true;
    this._renderBusy();
    let ok = false;
    try {
      await fn();
      ok = true;
      if (okMessage && typeof okMessage !== "function") this._toast = okMessage;
    } catch (err) {
      this._toast = `Fejl: ${err?.message || err}`;
    } finally {
      this._busy = false;
      await this._load();
      // A message that depends on the state after the change.
      if (ok && typeof okMessage === "function") {
        this._toast = okMessage();
        this._renderToast();
      }
      if (!ok) this._toastAction = null;
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        this._toast = null;
        this._toastAction = null;
        this._renderToast();
      }, this._toastAction ? 8000 : 3500);
    }
  }

  // ------------------------------------------------------------------ events

  // Saved right away like the favourites, without saving other unsaved settings.
  _saveDislikes(list, okMessage) {
    this._run(async () => {
      const saved = await this._ws("middagsro/settings", {
        settings: { ...this._state.settings, disliked_dishes: list },
      });
      if (this._form) this._form.disliked_dishes = saved.disliked_dishes;
    }, okMessage);
  }

  // To the top of the page. Scrolling <main> into view would tuck its start under the sticky toolbar.
  _toTop() {
    const top = this.shadowRoot.querySelector("#top");
    if (top?.scrollIntoView) top.scrollIntoView({ block: "start" });
    else this.scrollTo?.(0, 0);
  }

  _goTab(key, direction = 0) {
    if (!key || key === this._tab) return;
    this._moreOpen = false;
    this._chain = null; // a chain's offers belong to the plan tab
    this._everywhere = { query: "", loading: false, data: null, error: null };
    this._tab = key;
    if (key !== "recipes") this._releaseWake();
    if (key === "favorites" && !this._favCache[this._favWeek] && !this._favsLoading) this._loadFavs();
    if (key === "favorites" && !this._watch.items && !this._watch.loading) this._loadWatch();
    if (key === "health") this._loadHealth();
    this._render();
    this._syncPath();
    this._toTop(); // a page always opens from the top
    const content = this.shadowRoot.querySelector("#content");
    if (content && direction) {
      content.classList.remove("from-left", "from-right");
      void content.offsetWidth; // restart the animation
      content.classList.add(direction > 0 ? "from-right" : "from-left");
    }
  }

  // Swipe left/right on the page to go to the next/previous tab.
  _onTouchStart(ev) {
    this._swipe = null;
    if (this._embed || ev.touches.length !== 1 || this._modal || this._noteOpen || this._moreOpen) return;
    const t = ev.touches[0];
    // Leave the screen edges to the system (back gesture, HA's menu).
    if (t.clientX < 24 || t.clientX > innerWidth - 24) return;
    for (const el of ev.composedPath()) {
      if (el === this) break;
      if (!(el instanceof HTMLElement)) continue;
      if (el.matches("input, textarea, select, .tabs, .chips")) return;
      const overflow = getComputedStyle(el).overflowX;
      if ((overflow === "auto" || overflow === "scroll") && el.scrollWidth > el.clientWidth) return;
    }
    this._swipe = { x: t.clientX, y: t.clientY, time: Date.now() };
  }

  _onTouchEnd(ev) {
    const start = this._swipe;
    this._swipe = null;
    if (!start || !ev.changedTouches.length) return;
    const t = ev.changedTouches[0];
    const dx = t.clientX - start.x;
    const dy = t.clientY - start.y;
    if (Math.abs(dx) < 70 || Math.abs(dx) < Math.abs(dy) * 2 || Date.now() - start.time > 700) return;
    if (getSelection()?.toString()) return;
    const primary = this._navigation[matchMedia("(max-width: 700px)").matches ? "mobile" : "desktop"];
    const keys = [...primary, ...TABS.map(([key]) => key).filter(key => !primary.includes(key))];
    const next = keys[keys.indexOf(this._tab) + (dx < 0 ? 1 : -1)];
    this._goTab(next, dx < 0 ? 1 : -1);
  }

  _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    // The profile menu closes on a tap anywhere else.
    const profMenu = this.shadowRoot.querySelector(".prof-menu");
    if (profMenu && !profMenu.hidden && !ev.target.closest(".prof-wrap")) profMenu.hidden = true;
    if (!el) return;
    const { action, arg } = el.dataset;
    if (this._v3Click(action, arg, el)) return;
    const actions = {
      "store-switch-copy": () => this._performStoreSwitch(this._modal.target, "copy", this._modal.remember),
      "store-switch-new": () => this._performStoreSwitch(this._modal.target, "new", this._modal.remember),
      "store-switch-ask": () => this._run(() => this._ws("middagsro/store/ask"), "Du bliver spurgt ved næste butiksskift."),
      tab: () => {
        this._moreOpen = false;
        this._chain = null;
        if (arg === "settings") this._settingsSection = null;
        if (arg === this._tab) {
          this._everywhere = { query: "", loading: false, data: null, error: null };
          this._render();
        }
        else this._goTab(arg);
      },
      more: () => {
        this._moreOpen = !this._moreOpen;
        this._render();
      },
      "nav-open": () => {
        this._moreOpen = false;
        this._modal = { kind: "navigation", screen: matchMedia("(max-width: 700px)").matches ? "mobile" : "desktop", draft: { desktop: [...this._navigation.desktop], mobile: [...this._navigation.mobile] } };
        this._render();
        this._renderModal();
      },
      "nav-screen": () => { if (this._modal?.kind === "navigation") { this._modal.screen = arg; this._renderModal(); } },
      "nav-move": () => {
        const [screen, key, step] = String(arg).split("|");
        const list = this._modal?.draft?.[screen];
        if (!list) return;
        const at = list.indexOf(key), to = at + Number(step);
        if (at >= 0 && to >= 0 && to < list.length) [list[at], list[to]] = [list[to], list[at]];
        this._renderModal();
      },
      "nav-reset": () => { this._modal.draft = this._defaultNavigation(); this._renderModal(); },
      "nav-save": () => this._saveNavigation(),
      "inventory-save": () => this._run(async () => {
        const d = this._inventoryDraft || {};
        await this._ws("middagsro/inventory/edit", { item_id: d.id || null, name: d.name || "", amount: Number(String(d.amount || "").replace(",", ".")), unit: d.unit || "g", place: d.place || "", best_before: d.best_before || null });
        this._inventoryDraft = {};
      }, "Spisekammeret er gemt."),
      "inventory-edit": () => { this._inventoryDraft = { ...(this._state.freezer_inventory || []).find(i => i.id === arg) }; this._render(); },
      "inventory-cancel": () => { this._inventoryDraft = {}; this._render(); },
      "surplus-stock": () => this._run(async () => {
        const plan = this._plan;
        if (!plan) return;
        const { items } = await this._ws("middagsro/inventory/surplus", { plan_id: plan.id });
        if (!items.length) throw new Error("Pakkerne holder ikke mere, end retterne bruger – der er intet overskud at gemme.");
        const list = items.map((i) => `• ${i.name}: ${String(i.amount).replace(".", ",")} ${i.unit}`).join("\n");
        if (!confirm(`Læg dette i spisekammeret, når I har handlet?\n\n${list}\n\nNye madplaner bruger det først. Du kan rette mængderne under Spisekammer.`)) return;
        await this._ws("middagsro/inventory/surplus", { plan_id: plan.id, apply: true });
        this._surplusDone = true;
        if (!this._viewingLatest) this._plan = await this._ws("middagsro/plan", { plan_id: plan.id });
      }, () => {
        const done = this._surplusDone;
        this._surplusDone = false;
        return done ? "Overskuddet er lagt i spisekammeret." : null;
      }),
      "inventory-delete": () => this._run(async () => { await this._ws("middagsro/inventory/delete", { item_id: arg }); if (this._inventoryDraft?.id === arg) this._inventoryDraft = {}; }, "Råvaren er fjernet."),
      "inventory-consume-open": () => {
        const [planId, groupId] = String(arg || "").split("|");
        const plan = this._planOf(planId) || this._plan;
        const group = (plan?.freezer_groups || []).find(g => g.id === groupId);
        this._modal = { kind: "inventory-consume", plan, group, selected: new Set((group?.items || plan?.freezer_used || []).map(i => i.id)) };
        this._renderModal();
      },
      "inventory-consume": () => this._run(async () => {
        const m = this._modal;
        if (!m || m.kind !== "inventory-consume") return;
        await this._ws("middagsro/inventory/consume", { plan_id: m.plan.id, ...(m.group ? { group_id: m.group.id, item_ids: [...m.selected] } : {}) });
        this._modal = null; this._renderModal();
      }, "Forbruget er registreret."),
      "fav-refresh": () => this._loadFavs(true),
      "fav-week": () => {
        if (arg === this._favWeek) return;
        this._favWeek = arg;
        if (this._favCache[arg]) this._render();
        else this._loadFavs();
      },
      "note-open": () => {
        this._noteDraft = this._state?.note || "";
        this._noteOpen = true;
        this._renderModal();
        this.shadowRoot.querySelector("#note-text")?.focus();
      },
      "note-close": () => {
        this._noteOpen = false;
        this._renderModal();
      },
      "note-clear": () => {
        this._noteDraft = "";
        this._saveNote();
      },
      "note-save": () => this._saveNote(),
      "note-generate": () => this._saveNote(true),
      "clear-field": () => {
        const [bind, part] = String(arg).split("|");
        const m = this._modal;
        if (bind === "linesearch" && m) Object.assign(m, { query: "", results: [], error: null });
        if (bind === "chainquery") this._chainQuery = "";
        if (bind === "rc") this._rc.query = "";
        if (bind === "shopsearch") this._shopSearch[part] = { query: "", results: [], offers: [], loading: false };
        if (bind === "favfilter") this._favFilter = "";
        if (bind === "itemfilter") this._itemFilter = "";
        if (bind === "search") this._search = { query: "", results: [], loading: false };
        if (bind === "favsearch") this._favSearch = { query: "", results: [], loading: false };
        if (bind === "rrquery") return this._rrSearch("");
        if (bind === "everywhere") {
          this._everywhere = { query: "", loading: false, data: null, error: null };
          if (m?.kind === "where") return this._renderModal();
        }
        if (bind === "linesearch") return this._renderModal();
        this._render();
      },
      "fav-search": () => this._favSearchRun(),
      "watch-refresh": () => this._loadWatch(),
      "watch-toggle": () => this._watchToggle(this._productById(arg) || { product_id: Number(arg) }),
      "watch-key": () => {
        const item = (this._state.watch || []).find((w) => w.key === arg);
        if (item) this._watchToggle(item);
      },
      "watch-text": () => {
        const text = this._favSearch.query.trim();
        if (!text) return this._say("Skriv først, hvad der skal overvåges.");
        this._favSearch = { query: "", results: [], loading: false };
        this._watchToggle({ text });
      },
      "watch-add": () => this._watchAdd(arg),
      "watch-check": () =>
        this._run(async () => {
          const res = await this._ws("middagsro/watch/check");
          this._toast = res.told ? `Der er sendt besked om ${res.told} ${res.told === 1 ? "vare" : "varer"}.` : "Intet nyt på tilbud – der er ikke sendt besked.";
        }),
      "fav-own-add": () => {
        const p = this._favSearch.results.find((x) => String(x.id) === arg);
        if (!p) return;
        this._run(async () => {
          this._state.own_favorites = await this._ws("middagsro/favorites/own", { product: p, add: true });
          this._favCache = {};
          await this._loadFavs();
        }, `${p.name} er tilføjet til favoritterne.`);
      },
      "fav-own-remove": () => {
        const p = this._productById(arg);
        if (!p) return;
        this._run(async () => {
          this._state.own_favorites = await this._ws("middagsro/favorites/own", { product: p, add: false });
          this._favCache = {};
          await this._loadFavs();
        }, `${p.name} er fjernet fra favoritterne.`);
      },
      "fav-add": () =>
        this._run(
          () => this._ws("middagsro/list/add", { product_id: Number(arg), amount: 1 }),
          `Tilføjet til ${this._listName()}.`
        ),
      "clear-list": () => {
        const bought = (this._state?.rema_list?.items || []).filter((i) => i.bought).length;
        const name = this._listName();
        if (!bought) return this._say(`Der er ingen afkrydsede varer på ${name}.`);
        if (!confirm(`Fjern de ${bought} købte varer fra ${name}? Resten bliver stående.`)) return;
        this._run(() => this._ws("middagsro/list/clear", { bought_only: true }), `${bought} købte ${bought === 1 ? "vare er" : "varer er"} fjernet fra ${name}.`);
      },
      generate: () => this._run(() => this._generate(), GENERATING_MESSAGE),
      "freezer-generate": () => this._run(
        () => this._ws("middagsro/freezer/generate", {
          count: Number(arg),
          note: (this._freezerNote ?? this._state?.freezer_note ?? "").slice(0, 2000),
          use_freezer: this._useFreezerBatch !== false,
        }),
        "Fryserplanen laves. Åbn den nedenfor, når den er klar."
      ),
      "freezer-open": () => this._run(async () => {
        this._plan = await this._ws("middagsro/plan", { plan_id: arg });
        this._viewingLatest = false;
        this._tab = "plan";
      }),
      "rematch-missing": () => this._editPlan(
        () => this._ws("middagsro/plan/refresh", { plan_id: this._plan.id, unmatched: true }),
        "De manglende varer er søgt igen. Varer med et sikkert match er nu klar til at blive sendt."
      ),
      send: () => {
        // With a food budget: say so before a list that takes the week over.
        const week = this._state?.budget?.week;
        const part = arg === "late" ? "late" : "main";
        const cost = (this._plan?.shopping || [])
          .filter((l) => !l.sent && !l.buy_at && Boolean(l.buy_from) === (part === "late"))
          .reduce((sum, l) => sum + (Number(l.cost) || 0), 0);
        if (week && cost > week.remaining && !confirm(`Listen er anslået til ${kr0(cost)}, men der er kun ${kr0(week.remaining)} tilbage af ugens madbudget. Send den alligevel?`)) return;
        this._run(
          () => this._ws("middagsro/send", { plan_id: this._plan?.id, part }),
          this._isRema()
            ? part === "late" ? `Varerne til ${this._lateDayName()} er sendt til REMA 1000-appen.` : "Indkøbslisten er sendt til REMA 1000-appen."
            : this._state?.shop?.bilka_cart ? `De fundne varer er sendt til ${this._listName()}. Eventuelle manglende varer vises under Indkøb.` : part === "late" ? `Varerne til ${this._lateDayName()} er sat på indkøbslisten.` : "Varerne er sat på indkøbslisten."
        );
      },
      "budget-store": () => {
        this._book.store = arg;
        this._renderBudgetForms();
      },
      "budget-book": () => {
        const amount = Number(String(this._book.amount || "").replace(",", "."));
        if (!(amount > 0)) return this._say("Skriv beløbet fra kvitteringen.");
        const data = { amount, store: this._book.store || this._storeId(), date: this._book.date || localToday() };
        let booked = null;
        this._run(async () => {
          booked = (await this._ws("middagsro/purchases/add", data))?.booked || null;
          this._book = { amount: "", store: this._book.store, date: "" };
        }, () => {
          if (booked) this._toastAction = { label: "Fortryd", action: "purchase-undo", arg: booked };
          return `${kr0(amount)} er konteret.`;
        });
      },
      "budget-suggest": () => {
        this._book.amount = String(Math.round(Number(arg) || 0));
        this._renderBudgetForms();
      },
      "purchase-undo": () => {
        this._toastAction = null;
        this._run(() => this._ws("middagsro/purchases/delete", { purchase_id: arg }), "Købet er fortrudt.");
      },
      "purchase-edit": () => {
        const p = (this._state?.budget?.purchases || []).find((x) => x.id === arg);
        if (!p) return;
        this._modal = { kind: "purchase", id: p.id, amount: String(p.amount).replace(".", ","), date: p.date, store: p.store, note: p.note || "" };
        this._renderModal();
      },
      "pedit-store": () => {
        if (this._modal?.kind !== "purchase") return;
        this._modal.store = arg;
        this._renderModal();
      },
      "pedit-save": () => {
        const m = this._modal;
        if (m?.kind !== "purchase") return;
        const amount = Number(String(m.amount || "").replace(",", "."));
        if (!(amount > 0)) return this._say("Skriv beløbet fra kvitteringen.");
        this._modal = null;
        this._renderModal();
        this._run(
          () => this._ws("middagsro/purchases/edit", { purchase_id: m.id, amount, date: m.date || localToday(), store: m.store, note: m.note.trim() }),
          "Købet er rettet."
        );
      },
      "purchase-delete": () => {
        const p = (this._state?.budget?.purchases || []).find((x) => x.id === arg);
        if (!p || !confirm(`Slet købet på ${kr0(p.amount)} fra ${dateLabel(p.date).toLowerCase()}?`)) return;
        if (this._modal?.kind === "purchase") {
          this._modal = null;
          this._renderModal();
        }
        this._run(() => this._ws("middagsro/purchases/delete", { purchase_id: arg }), "Købet er slettet.");
      },
      "budget-period": () => {
        this._book.period = arg;
        this._render();
      },
      "budget-setup": () => {
        const week = this._book.period === "week";
        const value = Math.round(Number(String(this._book.monthly || "").replace(",", ".")));
        if (!(value > 0)) return this._say(`Skriv jeres madbudget pr. ${week ? "uge" : "måned"}.`);
        const amount = week ? { budget_period: "week", weekly_budget: value } : { budget_period: "month", monthly_budget: value };
        this._run(async () => {
          const saved = await this._ws("middagsro/settings", { settings: { ...this._state.settings, ...amount } });
          if (this._form && !this._dirty) this._form = clone(saved);
        }, `Madbudgettet er sat til ${kr0(value)} om ${week ? "ugen" : "måneden"}.`);
      },
      "budget-purchases": () => {
        this._budgetSpan = "purchases";
        this._tab = "budget";
        this._render();
      },
      "budget-view": () => {
        this._budgetSpan = arg;
        this._render();
      },
      "spend-span": () => {
        this._spendSpan = arg;
        this._render();
      },
      "rl-add": () =>
        this._run(async () => {
          await this._ws("middagsro/receipt_login/add", {
            email: this._rl.email.trim(),
            password: this._rl.password,
            label: this._rl.label.trim(),
          });
          this._rl = { email: "", password: "", label: "" };
        }, "Kontoen er tilføjet – kvitteringerne hentes nu."),
      "rl-remove": () => {
        if (!confirm("Fjern denne konto og dens kvitteringer fra Økonomi?")) return;
        this._run(
          () => this._ws("middagsro/receipt_login/remove", { login_id: arg }),
          "Kontoen og dens kvitteringer er fjernet."
        );
      },
      "hist-sub": () => {
        this._histSub = arg;
        this._receiptId = null;
        this._receipt = null;
        this._receiptLoading = false;
        this._render();
      },
      "view-receipt": () => {
        this._receiptId = arg;
        this._receipt = null;
        this._receiptLoading = true;
        this._render();
        this._ws("middagsro/receipt", { receipt_id: arg })
          .then((receipt) => {
            if (this._receiptId !== arg) return; // moved on meanwhile
            this._receipt = receipt;
            this._receiptLoading = false;
            this._render();
          })
          .catch((err) => {
            if (this._receiptId !== arg) return;
            this._receiptLoading = false;
            this._render();
            this._say(err?.message || "Kunne ikke hente kvitteringen.");
          });
      },
      "receipt-back": () => {
        this._receiptId = null;
        this._receipt = null;
        this._receiptLoading = false;
        this._render();
      },
      "open-day": () => {
        this._day = this._recipeIndex(arg);
        this._dayKey = this._recipeKey();
        this._tab = "recipes";
        this._recipesSub = "week";
        this._render();
        this._syncPath();
      },
      day: () => {
        this._day = Number(arg);
        this._dayKey = this._recipeKey();
        this._render();
        this._syncPath();
      },
      tick: () => {
        this._checked[arg] = !this._checked[arg];
        this._render();
      },
      timer: () => {
        const sep = arg.lastIndexOf("|"); // the key itself contains "|"
        const key = arg.slice(0, sep);
        const minutes = arg.slice(sep + 1);
        if (this._timers[key]) delete this._timers[key];
        else this._timers[key] = Date.now() + Number(minutes) * 60000;
        this._fired?.delete(key);
        this._audio ||= (() => { try { return new (window.AudioContext || window.webkitAudioContext)(); } catch (err) { return null; } })(); // from a tap, so iOS allows sound later
        this._render();
      },
      wake: () => (this._wakeWanted ? this._releaseWake(true) : this._requestWake()),
      "view-plan": () =>
        this._run(async () => {
          this._plan = await this._ws("middagsro/plan", { plan_id: arg });
          this._viewingLatest = this._plan?.id === this._state?.latest_plan?.id;
          this._tab = "plan";
        }),
      "view-latest": () => {
        this._viewingLatest = true;
        this._plan = this._state?.latest_plan;
        this._render();
      },
      "delete-plan": () => {
        const freezer = this._plan?.id === arg && this._plan.kind === "freezer"
          || (this._state?.freezer_plans || []).some(p => p.id === arg);
        if (!confirm(freezer ? "Slet denne fryserplan? Varer i kurven og Spisekammerets beholdning ændres ikke." : "Slet denne madplan fra historikken?")) return;
        this._run(async () => {
          await this._ws("middagsro/plan/delete", { plan_id: arg });
          if (this._plan?.id === arg) {
            this._viewingLatest = true;
          }
        }, freezer ? "Fryserplanen er slettet." : "Madplanen er slettet.");
      },
      "send-line": () => {
        const line = (this._plan?.shopping || []).find((l) => l.id === arg);
        this._run(
          () => this._ws("middagsro/send", { plan_id: this._plan?.id, line_id: arg }),
          `${line?.product?.name || line?.name || "Varen"} er lagt på ${this._listName()}.`
        );
      },
      "site-search": () => this._siteSearch(this._sites.query),
      "site-open": () => {
        this._sites.opening = arg;
        this._render();
        this._ws("middagsro/sites/recipe", { url: arg })
          .then((recipe) => {
            this._modal = { kind: "recipe", recipe: { ...recipe, id: null }, imported: true };
            this._renderModal();
          })
          .catch((err) => this._say(`Fejl: ${err?.message || err}`))
          .finally(() => {
            this._sites.opening = null;
            this._render();
          });
      },
      "pick-open": () => {
        this._modal = { kind: "pick", date: arg, tab: "collection", query: "", rema: null, mealie: null };
        this._renderModal();
      },
      "pick-tab": () => {
        const m = this._modal;
        if (m?.kind !== "pick") return;
        m.tab = arg;
        this._renderModal();
        if (arg === "rema" && !m.rema) this._pickLoad("rema");
        if (arg === "mealie" && !m.mealie) this._pickLoad("mealie");
      },
      "pick-search": () => {
        const m = this._modal;
        if (m?.kind !== "pick") return;
        if (m.tab === "rema") this._pickLoad("rema");
        if (m.tab === "sites") this._siteSearch(m.query, (m.sites ||= {}));
      },
      "pick-choose": () => {
        const m = this._modal;
        if (m?.kind !== "pick") return;
        const [source, id] = String(arg).split("|");
        let pick = null;
        if (source === "collection") {
          const r = (this._state.recipes || []).find((x) => x.id === id);
          if (r) pick = { dish: r.name, source, recipe_id: r.id, type: r.type };
        } else if (source === "rema") {
          const r = (m.rema?.recipes || []).find((x) => x.slug === id);
          if (r) pick = { dish: r.title, source, slug: r.slug, type: r.vegetarian ? "vegetar" : "normal" };
        } else if (source === "web") {
          const r = (m.sites?.results || []).find((x) => x.url === id);
          if (r) pick = { dish: r.title, source, url: r.url };
        } else {
          const r = (m.mealie?.recipes || []).find((x) => x.slug === id);
          if (r) pick = { dish: r.name, source, slug: r.slug };
        }
        if (!pick) return;
        if (m.target) return this._pickForDay(m, pick);
        this._picks[m.date] = pick;
        this._dayKinds[m.date] = { kind: "pick", text: "" };
        this._skip.delete(m.date);
        this._modal = null;
        this._renderModal();
        this._render();
      },
      "pick-remove": () => {
        delete this._picks[arg];
        this._dayKinds[arg] = { kind: "ai", text: "" };
        this._render();
      },
      "move-day": () => {
        const [planId, date, direction] = String(arg).split("|");
        this._run(() => this._ws("middagsro/day/move", { plan_id: planId, date, direction }));
      },
      "rate-day": () => {
        const [planId, date, rate] = String(arg).split("|");
        this._run(async () => {
          this._toast = rateToast(await this._ws("middagsro/recipes/rate_day", { plan_id: planId, date, action: rate }));
        });
      },
      "rate-recipe": () => {
        const [id, rate] = String(arg).split("|");
        const m = this._modal;
        if (m?.kind === "recipe" && !m.recipe.id) {
          // Not saved yet: the rating is saved with it.
          m.recipe = applyRating(m.recipe, rate);
          return this._renderModal();
        }
        this._run(async () => {
          const recipe = await this._ws("middagsro/recipes/rate", { recipe_id: id, action: rate });
          this._toast = rateToast(recipe);
          if (m?.kind === "recipe" && m.recipe.id === id) {
            m.recipe = { ...m.recipe, rating: recipe.rating, favorite: recipe.favorite };
            this._renderModal();
          }
        });
      },
      "recipes-sub": () => {
        this._recipesSub = arg;
        if (arg !== "rema") this._remaPick = null;
        this._render();
        if (arg === "rema" && !this._rr.page) this._rrLoad();
        if (arg === "offers" && !this._cand?.data && !this._cand?.loading) this._candLoad();
      },
      "cand-sort": () => {
        this._cand = { ...(this._cand || {}), sort: arg, data: null };
        this._candLoad();
      },
      "rr-tag": () => {
        if (this._rr.loading) return;
        this._rrQuery = "";
        this._rr = { ...this._rr, key: arg, query: "", page: 0, last: 1, recipes: [], loading: false, error: null };
        this._rrLoad();
      },
      "rr-more": () => this._rrLoad(),
      "rr-search": () => this._rrSearch(this._rrQuery || ""),
      "rr-open": () => this._rrOpen(arg),
      "rr-pick": () => this._rrPick(arg),
      "rr-pick-cancel": () => {
        this._remaPick = null;
        this._render();
      },
      "day-rema": () => {
        const m = this._modal;
        if (m?.kind !== "day") return;
        this._remaPick = { planId: m.planId, date: m.date, dish: m.dish };
        this._modal = null;
        this._renderModal();
        this._goTab("recipes");
        this._recipesSub = "rema";
        this._render();
        this._toTop();
        if (!this._rr.page) this._rrLoad();
      },
      "rc-filter": () => {
        this._rc.filter = arg;
        this._render();
      },
      "rc-import": () => this._recipeImport(),
      "rc-scan": () => {
        const input = this.shadowRoot.querySelector("#scan-input");
        if (!input) return;
        input.value = "";
        input.onchange = () => this._recipeScan([...(input.files || [])]);
        input.click();
      },
      "rc-new": () => {
        this._modal = { kind: "recipe", recipe: { id: null, name: "", type: "normal", servings: 4, active_minutes: 0, total_minutes: 0,
          ingredients: [{ amount: "", name: "" }], steps: [{ text: "", minutes: 0 }], tip: "", rating: null, favorite: false, source: "manual" } };
        this._renderModal();
      },
      "rc-open": () => this._recipeOpen(arg),
      "rc-row": () => {
        const m = this._modal;
        if (m?.kind !== "recipe") return;
        const [list, op, idx] = String(arg).split("|");
        const rows = m.recipe[list];
        if (op === "add") rows.push(list === "ingredients" ? { amount: "", name: "" } : { text: "", minutes: 0 });
        else rows.splice(Number(idx), 1);
        if (list === "ingredients" && op !== "add") {
          m.found = {}; // the rows moved: the suggestions no longer fit them
          this._rcLinksSoon(m);
        }
        this._renderModal();
      },
      "rc-save": () => this._recipeSave(),
      "rc-rema-save": () => {
        const m = this._modal;
        if (m?.kind !== "recipe" || !m.recipe.rema_slug || m.busy) return;
        const slug = m.recipe.rema_slug;
        this._run(async () => {
          const res = await this._ws("middagsro/rema_recipes/save_links", { slug, ingredients: m.recipe.ingredients });
          const card = (this._rr?.recipes || []).find((r) => r.slug === slug);
          if (card) card.ready = !!res.ready;
          if (this._cand) this._cand.data = null; // priced again with the new products
          this._modal = null;
          this._renderModal();
        }, "Varerne er gemt på REMA-opskriften.");
      },
      "rc-ing-pick": () => {
        const m = this._modal;
        const [idx, id] = String(arg).split("|");
        const ing = m?.kind === "recipe" ? m.recipe.ingredients[Number(idx)] : null;
        const product = (m?.sugg?.items || []).find((p) => String(p.id) === id);
        if (!ing || !product) return;
        ing.product = { id: product.id, name: product.name, underline: product.underline || "" };
        if (!String(ing.name || "").trim()) ing.name = product.name.toLowerCase();
        m.sugg = null;
        this._renderModal();
      },
      "rc-ing-unlink": () => {
        const ing = this._modal?.kind === "recipe" ? this._modal.recipe.ingredients[Number(arg)] : null;
        if (!ing) return;
        delete ing.product;
        delete ing.basic;
        delete ing.exact;
        this._renderModal();
      },
      "rc-ing-use": () => {
        const m = this._modal;
        const [idx, id] = String(arg).split("|");
        const ing = m?.kind === "recipe" ? m.recipe.ingredients[Number(idx)] : null;
        const found = m?.found?.[idx];
        const product = found && [found.product, ...(found.alternatives || [])].find((p) => p && String(p.id) === id);
        if (!ing || !product) return;
        ing.product = { id: product.id, name: product.name, underline: product.underline || "" };
        delete m.found[idx];
        this._renderModal();
      },
      "rc-ing-basic": () => {
        const ing = this._modal?.kind === "recipe" ? this._modal.recipe.ingredients[Number(arg)] : null;
        if (!ing) return;
        ing.basic = true;
        this._renderModal();
      },
      "rc-ing-exact": () => {
        const ing = this._modal?.kind === "recipe" ? this._modal.recipe.ingredients[Number(arg)] : null;
        if (!ing) return;
        if (ing.exact) delete ing.exact;
        else ing.exact = true;
        this._renderModal();
      },
      "rc-links-find": () => {
        if (this._modal?.kind === "recipe") this._rcLinks(this._modal, true);
      },
      "rc-links-useall": () => {
        const m = this._modal;
        if (m?.kind !== "recipe") return;
        for (const [idx, f] of Object.entries(m.found || {})) {
          const ing = m.recipe.ingredients[Number(idx)];
          if (ing && !ing.product && !ing.basic && f.product && f.confidence === "high") {
            ing.product = { id: f.product.id, name: f.product.name, underline: f.product.underline || "" };
            delete m.found[idx];
          }
        }
        this._renderModal();
      },
      "rc-delete": () => {
        const m = this._modal;
        if (!m?.recipe?.id || !confirm(`Slet "${m.recipe.name}" fra opskriftsamlingen?`)) return;
        this._modal = null;
        this._renderModal();
        this._run(() => this._ws("middagsro/recipes/delete", { recipe_id: m.recipe.id }), "Opskriften er slettet.");
      },
      "rc-plan": () => {
        const m = this._modal;
        if (!m) return;
        m.picking = !m.picking;
        this._renderModal();
      },
      "rc-plan-day": () => this._recipeToPlan(arg),
      surprise: () => {
        if (!confirm("Overrask jer? Middagsro laver en ny madplan med retter, I aldrig har fået – fra andre køkkener og med overraskende smage.")) return;
        this._run(() => this._generate(true), "Madplanen med nye, overraskende retter er ved at blive lavet – det tager typisk 1-2 minutter.");
      },
      everywhere: () => this._everywhereRun(),
      "everywhere-clear": () => {
        this._everywhere = { query: "", loading: false, data: null, error: null };
        if (this._modal?.kind === "where") {
          this._modal = null;
          this._renderModal();
        }
        this._render();
      },
      "ev-rema": () => {
        const product = this._everywhere.data?.products.find((p) => String(p.id) === arg);
        const plan = this._state?.latest_plan;
        if (!product || !plan) return;
        this._editPlan(
          () => this._ws("middagsro/plan/add", { plan_id: plan.id, product_id: product.id, part: "main" }),
          `${product.name} er sat på indkøbslisten.`
        );
      },
      // Straight onto the REMA list in the app, past the meal plan's list.
      "ev-rema-list": () => {
        const product = this._everywhere.data?.products.find((p) => String(p.id) === arg);
        if (product) this._addToRemaList(product.id, product.name);
      },
      "ev-chain": () => {
        const offer = this._everywhere.data?.offers.find((o) => o.id === arg);
        const plan = this._state?.latest_plan;
        if (!offer || !plan) return;
        this._editPlan(
          () => this._ws("middagsro/chains/add", { plan_id: plan.id, offer }),
          `${offer.heading} er sat på ${this._chainName(offer.dealer_id)}-listen under Indkøb.`
        );
      },
      "fav-where": () => {
        const p = (this._favCache[this._favWeek]?.products || []).find((x) => String(x.id) === arg)
          || (this._favCache[this._favWeek]?.on_offer || []).find((x) => String(x.id) === arg);
        if (!p) return;
        const match = this._favCompare[this._favWeek]?.[String(p.id)] || null;
        this._modal = { kind: "where", title: p.name, product: p, match };
        this._renderModal();
        this._everywhereRun(p.name);
      },
      "match-chain": () => {
        const offer = this._modal?.match;
        const plan = this._state?.latest_plan;
        if (!offer || !plan) return;
        this._editPlan(
          () => this._ws("middagsro/chains/add", { plan_id: plan.id, offer }),
          `${offer.heading} er sat på ${this._chainName(offer.dealer_id)}-listen under Indkøb.`
        );
      },
      "plan-help": () => {
        this._planHelp = !this._planHelp;
        this._render();
      },
      "chain-open": () => {
        this._chain = arg;
        this._chainQuery = "";
        this._render();
        this._toTop();
        if (!this._chainOffers[arg]?.offers) this._loadChainOffers(arg);
      },
      "chain-close": () => {
        this._chain = null;
        this._render();
      },
      "chain-refresh": () => this._loadChainOffers(this._chain, true),
      "chain-add": () => {
        const offer = (this._chainOffers[this._chain]?.offers || []).find((o) => o.id === arg);
        const plan = this._state?.latest_plan;
        if (offer && offer.dealer_id === this._storeId()) {
          return this._editPlan(async () => {
            const res = await this._ws("middagsro/chains/rema_add", { offer, plan_id: plan?.id || null });
            this._toast = res.added_to === "plan" ? `${res.name} er sat på indkøbslisten.` : `${res.name} er sat på ${this._listName()}.`;
          });
        }
        if (!offer || !plan) return this._say("Lav en madplan først – så kan tilbuddet komme på indkøbslisten.");
        this._editPlan(
          () => this._ws("middagsro/chains/add", { plan_id: plan.id, offer }),
          `${offer.heading} er sat på ${this._chainName(offer.dealer_id)}-listen under Indkøb.`
        );
      },
      "chain-move": () => {
        const [lineId, dealer] = String(arg).split("|");
        const found = this._compare?.lines?.[lineId];
        this._compare = null;
        this._editPlan(
          () => this._ws("middagsro/chains/move", { plan_id: this._plan.id, line_id: lineId, dealer_id: dealer || null,
            price: dealer && found ? found.per_package : null, heading: dealer && found ? found.heading : null }),
          dealer ? `Flyttet til ${this._chainName(dealer)}-listen.` : `Flyttet tilbage til ${this._listName()}.`
        );
      },
      "chain-move-all": () => {
        const unsent = new Set((this._plan?.shopping || []).filter((l) => !l.sent).map((l) => l.id));
        const lines = Object.entries(this._compare?.lines || {}).filter(([id, f]) => f.dealer_id === arg && unsent.has(id));
        this._compare = null;
        this._editPlan(async () => {
          for (const [lineId, f] of lines) {
            await this._ws("middagsro/chains/move", { plan_id: this._plan.id, line_id: lineId, dealer_id: arg, price: f.per_package, heading: f.heading });
          }
        }, `${lines.length} varer er flyttet til ${this._chainName(arg)}-listen.`);
      },
      "chain-tick": () => {
        const line = this._plan?.shopping.find((l) => l.id === arg);
        if (!line) return;
        this._editPlan(() => this._ws("middagsro/chains/line", { plan_id: this._plan.id, line_id: arg, bought: !line.bought }));
      },
      "chain-count": () => {
        const [lineId, delta] = String(arg).split("|");
        const line = this._plan?.shopping.find((l) => l.id === lineId);
        if (!line) return;
        const packages = Math.max(1, Math.min(99, (line.packages || 1) + Number(delta)));
        this._editPlan(() => this._ws("middagsro/chains/line", { plan_id: this._plan.id, line_id: lineId, packages }));
      },
      "chain-delete": () =>
        this._editPlan(() => this._ws("middagsro/chains/line", { plan_id: this._plan.id, line_id: arg, delete: true }), "Varen er slettet."),
      "chain-clear": () => {
        const bought = this._plan.shopping.filter((l) => l.buy_at === arg && l.bought).length;
        if (!bought) return this._say("Sæt flueben ved det, I har købt – så ryddes det fra listen.");
        this._editPlan(() => this._ws("middagsro/chains/clear", { plan_id: this._plan.id, dealer_id: arg }), `Kurven er ryddet – ${bought} varer er købt.`);
      },
      prof: () => {
        const menu = this.shadowRoot.querySelector(".prof-menu");
        menu.hidden = !menu.hidden;
        this.shadowRoot.querySelector(".prof").setAttribute("aria-expanded", String(!menu.hidden));
      },
      look: () => this._setLook(arg),
      "settings-open": () => {
        const menu = this.shadowRoot.querySelector(".prof-menu");
        if (menu) menu.hidden = true;
        this._goTab("settings");
        this._settingsSection = arg || null;
        this._render();
        this._toTop();
      },
      "settings-section": () => {
        if (arg === "chains" && !this._chains) this._loadChains();
        this._settingsSection = arg || null;
        this._render();
        this._toTop();
      },
      "save-settings": () =>
        this._run(async () => {
          await this._ws("middagsro/settings", { settings: this._form });
          this._dirty = false;
        }, () => this._canUpdatePlan(this._state?.latest_plan) === "update"
          ? "Indstillingerne er gemt. Tryk på Opdater madplan under Madplan for at rette ugens plan til."
          : "Indstillingerne er gemt."),
      "plan-update": () => this._run(
        () => this._ws("middagsro/plan/update", { plan_id: arg || this._state?.latest_plan?.id }),
        "Madplanen opdateres til de nye indstillinger …"
      ),
      "add-dislike": () => {
        const text = this._newDislike.trim();
        if (!text) return this._say("Skriv en ret først.");
        this._saveDislikes([...(this._state.settings.disliked_dishes || []), text], "Retten er tilføjet.");
        this._newDislike = "";
      },
      "delete-dislike": () => {
        const list = [...(this._state.settings.disliked_dishes || [])];
        list.splice(Number(arg), 1);
        this._saveDislikes(list, "Retten er fjernet.");
      },
      "reset-settings": () => {
        this._form = clone(this._state.settings);
        this._dirty = false;
        this._render();
      },
      "add-row": () => {
        const rows = {
          household: { role: "adult", age: 40, sex: "female" },
          fixed_days: { weekday: 3, kind: "rest", text: "Rester" },
          must_haves: { name: "", amount: 1, product_id: null, group: "", mode: "packs", use: 0, unit: "stk" },
        };
        this._form[arg].push(clone(rows[arg]));
        this._dirty = true;
        this._render();
      },
      "remove-row": () => {
        const [list, idx] = arg.split("|");
        this._form[list].splice(Number(idx), 1);
        this._dirty = true;
        this._render();
      },
      search: () => this._doSearch(),
      "pick-product": () => {
        const product = this._search.results[Number(arg)];
        if (!product) return;
        const name = `${product.name}${product.underline ? ` (${product.underline.split("/")[0].trim()})` : ""}`;
        this._form.must_haves.push({ name, product_id: product.id, amount: 1, group: "", mode: "packs", use: 0, unit: "stk" });
        this._search = { query: "", results: [], loading: false };
        this._dirty = true;
        this._render();
      },
      "add-fav": () => {
        if (!this._newFav.text.trim()) return this._say("Skriv en ret først.");
        this._run(async () => {
          await this._ws("middagsro/favorite/save", { favorite: this._newFav });
          this._newFav = { text: "", frequency: "weekly" };
        }, "Favoritten er tilføjet.");
      },
      "edit-fav": () => {
        const fav = this._state.favorites.find((f) => f.id === arg);
        this._editFav = fav ? clone(fav) : null;
        this._render();
      },
      "save-fav": () =>
        this._run(async () => {
          await this._ws("middagsro/favorite/save", { favorite: this._editFav });
          this._editFav = null;
        }, "Favoritten er gemt."),
      "cancel-fav": () => {
        this._editFav = null;
        this._render();
      },
      "delete-fav": () => {
        if (!confirm("Slet denne favorit?")) return;
        this._run(() => this._ws("middagsro/favorite/delete", { favorite_id: arg }), "Favoritten er slettet.");
      },
      recipe: () =>
        this._run(async () => {
          const item = this._recipeDays()[this._day];
          if (!item) return;
          // The plans are read again afterwards, so the new recipe shows up.
          await this._ws("middagsro/recipe", { plan_id: item.plan.id, date: item.day.date });
          if (!this._viewingLatest) this._plan = await this._ws("middagsro/plan", { plan_id: this._plan.id });
        }, "Opskriften er lavet igen."),
      refresh: () => this._load(),
      // A day of the plan: see the recipe, or swap the dish for another.
      "day-menu": () => {
        const [planId, date] = String(arg).split("|");
        const plan = this._planOf(planId);
        const day = plan?.days.find((d) => d.date === date);
        if (!day) return;
        const written = day.type === "egen";
        const leftovers = !!day.uses_leftovers_from || day.type === "rester";
        const food = leftovers ? this._foodDay(plan, day) : null;
        const section = leftovers ? "rest" : written ? "text" : "dish";
        this._modal = {
          kind: "day", planId, date, dish: day.dish, written, newDish: !!day.new_dish, text: written ? day.dish : "",
          leftovers, food: food?.date || null, source: food?.date || null, section, mode: "day", vegetarian: day.type === "vegetar",
        };
        this._renderModal();
      },
      "day-menu-skipped": () => {
        const [planId, date] = String(arg).split("|");
        this._modal = { kind: "day", planId, date, dish: "", skipped: true, section: "skip", mode: "day", text: "", vegetarian: false };
        this._renderModal();
      },
      // The day's menu: what the day is (a dinner, leftovers, no cooking, skipped).
      "day-section": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        Object.assign(m, { section: arg, options: null, error: null, mode: "day" });
        if (arg === "rest" && !m.source) {
          const foods = this._foodDays(this._planOf(m.planId), m.date);
          m.source = foods.length ? foods[foods.length - 1].date : null;
        }
        // A skipped day is taken back first: then it can be anything.
        if (m.skipped && arg !== "skip") return this._dayBack(m, arg);
        this._renderModal();
      },
      "day-back": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        this._dayBack(m, null);
      },
      "day-veg": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        m.vegetarian = !m.vegetarian;
        this._renderModal();
      },
      "day-chip": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        m.text = arg;
        this._renderModal();
      },
      "day-source-swap": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        m.mode = "source";
        this._swapOptions();
      },
      "day-pick": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        this._modal = { kind: "pick", date: m.date, tab: "collection", query: "", rema: null, mealie: null, target: { planId: m.planId, date: m.date } };
        this._renderModal();
      },
      "day-leftovers": () => {
        const m = this._modal;
        if (m?.kind !== "day" || m.busy) return;
        const plan = this._planOf(m.planId);
        const foods = this._foodDays(plan, m.date);
        if (!m.source && foods.length) m.source = foods[foods.length - 1].date;
        const food = plan?.days.find((d) => d.date === m.source);
        if (!food) {
          m.error = "Vælg den dag, resterne er fra.";
          return this._renderModal();
        }
        if (m.dish && !m.leftovers && !m.written && !confirm(`Gør ${dateLabel(m.date).toLowerCase()} til rester af ${food.dish}? ${m.dish} og dens egne varer fjernes.`)) return;
        m.busy = "rest";
        this._renderModal();
        this._ws("middagsro/day/leftovers", { plan_id: m.planId, date: m.date, source: m.source })
          .then(async (plan) => {
            if (!this._viewingLatest && this._plan?.id === plan.id) this._plan = plan;
            this._modal = null;
            this._renderModal();
            await this._load();
            this._say(`${dateLabel(m.date)} er rester af ${food.dish} – den laves i dobbelt portion, og indkøbslisten er rettet.`);
          })
          .catch((err) => {
            m.busy = null;
            m.error = err?.message || String(err);
            this._renderModal();
          });
      },
      "day-text": () => {
        const m = this._modal;
        if (!m || m.busy) return;
        const text = String(m.text || "").trim();
        if (!text) return this._say("Skriv fx Spiser ude eller Skolefest.");
        if (m.dish && !m.written && !confirm(`Skriv "${text}" i stedet for ${m.dish}? Rettens egne varer fjernes fra indkøbslisten.`)) return;
        this._modal = null;
        this._renderModal();
        this._editPlan(() => this._ws("middagsro/day/text", { plan_id: m.planId, date: m.date, text }), "Dagen er skrevet ind.");
      },
      "day-approve": () => {
        const m = this._modal;
        if (!m || m.busy) return;
        this._modal = null;
        this._renderModal();
        this._editPlan(() => this._ws("middagsro/day/approve", { plan_id: m.planId, date: m.date }), `${m.dish} er godkendt og gemt i opskriftsamlingen.`);
      },
      "day-restore": () => {
        const [planId, date] = String(arg).split("|");
        this._editPlan(() => this._ws("middagsro/day/restore", { plan_id: planId, date }), `${dateLabel(date)} er tilbage i madplanen.`);
      },
      "notice-close": () => {
        const notice = this._modal?.notice;
        this._modal = null;
        this._renderModal();
        if (notice) this._ws("middagsro/notice_seen", { notice }).catch(() => {});
        if (arg === "shop") {
          this._goTab("settings");
          this._settingsSection = "shop";
          this._render();
        }
      },
      "modal-close": () => {
        if (this._modal?.busy) return;
        if (this._modal?.kind === "where") this._everywhere = { query: "", loading: false, data: null, error: null };
        this._modal = null;
        this._renderModal();
      },
      "day-recipe": () => {
        const m = this._modal;
        this._modal = null;
        this._renderModal();
        this._day = this._recipeIndex(`${m.planId}|${m.date}`);
        this._dayKey = this._recipeKey();
        this._tab = "recipes";
        this._recipesSub = "week";
        this._render();
      },
      "swap-options": () => this._swapOptions(),
      "day-clear": () => {
        const m = this._modal;
        if (!m || m.busy) return;
        const skip = arg === "skip";
        const what = skip ? "Spring dagen over? Der laves ingen aftensmad den dag." : "Slet retten? Du kan vælge en ny bagefter.";
        if (!confirm(`${what} Rettens egne varer fjernes fra indkøbslisten.`)) return;
        this._modal = null;
        this._renderModal();
        this._editPlan(
          () => this._ws("middagsro/day/clear", { plan_id: m.planId, date: m.date, skip }),
          skip ? "Dagen springes over." : "Retten er slettet."
        );
      },
      "line-menu": () => this._openLine(arg),
      "review-keep": () => this._reviewAction(arg, "keep", null, "Varen beholdes – og huskes til næste gang."),
      "review-skip": () => this._reviewAction(arg, "skip", null, "Varen er udeladt, og den vælges ikke til ingrediensen igen."),
      "review-have": () => this._reviewAction(arg, "have", null, "Varen er taget af listen denne gang. Næste gang kommer den med igen."),
      "review-unskip": () => this._reviewAction(arg, "unskip", null, "Varen er med på listen igen."),
      "review-forget": () => this._reviewAction(arg, "forget", null, "Valget er glemt – varen findes på ny næste gang."),
      "review-choose": () => {
        const [lineId, productId] = arg.split("|");
        const line = this._plan?.shopping.find((l) => l.id === lineId);
        const alt = line?.alternatives?.find((a) => String(a.id) === productId);
        this._reviewAction(lineId, "choose", Number(productId), `${alt?.name || "Varen"} er sat på listen i stedet – og huskes til næste gang.`);
      },
      "review-keep-all": () => this._run(async () => {
        const planId = this._plan?.id;
        const unsure = (this._plan?.shopping || []).filter((l) => this._needsReview(l) && l.product);
        for (const line of unsure) {
          await this._ws("middagsro/plan/review", { plan_id: planId, line_id: line.id, action: "keep", product_id: null });
        }
        if (!this._viewingLatest && this._plan) this._plan = await this._ws("middagsro/plan", { plan_id: planId });
      }, "Varerne beholdes – og huskes til næste gang."),
      "line-count": () => {
        const m = this._modal;
        if (!m) return;
        m.packages = Math.max(1, Math.min(99, m.packages + Number(arg)));
        this._renderModal();
      },
      "line-save-count": () => this._lineAction({ packages: this._modal.packages }, "Antallet er rettet."),
      "line-delete": () => this._lineAction({ delete: true }, "Varen er slettet fra indkøbslisten."),
      "line-save-left": () => {
        const m = this._modal;
        const left = Number(String(m?.left ?? "").replace(",", "."));
        if (!m || !Number.isFinite(left) || left < 0) return this._say("Skriv hvor meget I har tilbage, fx 1,5.");
        this._lineAction({ left }, left ? "Kun resten købes." : "Hele forbruget købes.", "middagsro/line/left");
      },
      "line-search": () => this._lineSearch(),
      "line-pick": () => {
        const product = this._modal?.results[Number(arg)];
        if (product) this._lineAction({ product_id: product.id }, `${product.name} er sat på listen i stedet.`);
      },
      "add-rule": () => {
        const text = this._newRule.trim();
        if (!text) return this._say("Skriv noget først – eller diktér det.");
        this._newRule = "";
        this._saveRules([...(this._state.settings.rules || []), text], "Gemt – AI'en husker det fra næste madplan.");
      },
      "edit-rule": () => {
        this._editRule = { index: Number(arg), text: (this._state.settings.rules || [])[Number(arg)] || "" };
        this._render();
      },
      "cancel-rule": () => {
        this._editRule = null;
        this._render();
      },
      "save-rule": () => {
        const list = [...(this._state.settings.rules || [])];
        const text = this._editRule?.text.trim();
        if (text) list[this._editRule.index] = text;
        else list.splice(this._editRule.index, 1);
        this._editRule = null;
        this._saveRules(list, "Rettet.");
      },
      "delete-rule": () => {
        const list = [...(this._state.settings.rules || [])];
        list.splice(Number(arg), 1);
        this._saveRules(list, "Slettet.");
      },
      dictate: () => this._dictate(arg),
      "health-refresh": () => this._loadHealth(true),
      "mealie-save": () => {
        const [planId, date] = String(arg).split("|");
        if (this._modal) {
          this._modal = null;
          this._renderModal();
        }
        this._editPlan(() => this._ws("middagsro/mealie/save", { plan_id: planId, date }), "Opskriften er gemt i Mealie.");
      },
      "mealie-sync": () =>
        this._run(() => this._ws("middagsro/mealie/sync", { plan_id: this._plan.id }), "Ugen er sat i Mealie-kalenderen."),
      "swap-pick": () => this._swapPick(Number(arg)),
      "day-own-dish": () => {
        const m = this._modal;
        const dish = String(m?.text || "").trim();
        if (!m || m.busy) return;
        if (!dish) return this._say("Skriv navnet på retten, fx Tacos.");
        this._swapPick(-1, { dish });
      },
      "pantry-open": () => this._pantryOpen(),
      "plan-rematch": () =>
        this._editPlan(
          () => this._ws("middagsro/plan/rematch", { plan_id: this._plan.id }),
          "Varerne er fundet igen. Jeres egne valg er beholdt, og usikre varer står øverst."
        ),
      "plan-record": () =>
        this._run(async () => {
          const record = await this._ws("middagsro/plan/record", { plan_id: this._plan.id });
          if (!record.cases.length) throw new Error("Ingen varer er beholdt eller valgt i denne madplan endnu");
          const blob = new Blob([JSON.stringify(record, null, 1)], { type: "application/json" });
          const link = document.createElement("a");
          link.href = URL.createObjectURL(blob);
          link.download = `middagsro-testsag-${record.plan || record.recorded}.json`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          setTimeout(() => URL.revokeObjectURL(link.href), 1000);
        }, "Testsagen er gemt som fil."),
      "links-share": () => {
        // Opened at once (a window opened after waiting is stopped by the browser).
        const win = window.open("", "_blank");
        this._run(async () => {
          const share = await this._ws("middagsro/links/share");
          if (!share.url) {
            win?.close();
            throw new Error("Der er ingen nye valg at dele endnu");
          }
          if (win) win.location.href = share.url;
          else window.location.href = share.url;
        }, "GitHub er åbnet med jeres valg. Tryk “Submit new issue” for at dele dem.");
      },
      "plan-refresh": () =>
        this._editPlan(
          () => this._ws("middagsro/plan/refresh", { plan_id: this._plan.id }),
          this._isRema() ? "Tilbudsvarerne er fundet igen med REMA's varer og priser lige nu." : "Tilbudsvarerne er opdateret."
        ),
      "pantry-add": () => this._pantryAdd(arg),
      "shop-search": () => this._shopSearchRun(arg),
      "shop-offer-add": () => {
        const offer = this._shopSearch.main?.offers?.[Number(arg)];
        if (!offer || !this._plan) return;
        this._shopSearch.main = { query: "", results: [], offers: [], loading: false };
        this._editPlan(
          () => this._ws("middagsro/chains/rema_add", { offer, plan_id: this._plan.id }),
          `${offer.heading} er tilføjet til indkøbslisten.`
        );
      },
      "shop-offer-add-list": () => {
        const offer = this._shopSearch.main?.offers?.[Number(arg)];
        if (!offer) return;
        this._shopSearch.main = { query: "", results: [], offers: [], loading: false };
        const todo = this._quickTodo();
        if (todo) return this._addToTodo(todo, offer.heading);
        this._run(() => this._ws("middagsro/chains/rema_add", { offer, plan_id: null }), `${offer.heading} er sat på REMA-listen.`);
      },
      "shop-add-list": () => {
        const [part, idx] = String(arg).split("|");
        const product = this._shopSearch[part]?.results[Number(idx)];
        if (!product) return;
        this._shopSearch[part] = { query: "", results: [], loading: false };
        this._addToRemaList(product.id, product.name);
      },
      "send-restore": () =>
        this._editPlan(
          () => this._ws("middagsro/send/restore", { plan_id: this._plan?.id }),
          "Den seneste kurv er lagt tilbage – send den igen, når du er klar."
        ),
      "shop-add-text": () => {
        const search = this._shopSearch[arg];
        const name = search?.query.trim();
        if (!name || !this._plan) return;
        this._shopSearch[arg] = { query: "", results: [], offers: [], loading: false };
        this._editPlan(
          () => this._ws("middagsro/plan/add", { plan_id: this._plan.id, name, part: arg }),
          `${name} er tilføjet til indkøbslisten.`
        );
      },
      "shop-add": () => {
        const [part, idx] = String(arg).split("|");
        const product = this._shopSearch[part]?.results[Number(idx)];
        if (!product || !this._plan) return;
        this._shopSearch[part] = { query: "", results: [], loading: false };
        this._editPlan(
          () => this._ws("middagsro/plan/add", { plan_id: this._plan.id, product_id: product.id, part }),
          `${product.name} er tilføjet til indkøbslisten.`
        );
      },
      "line-remove": () =>
        this._editPlan(() => this._ws("middagsro/plan/remove", { plan_id: this._plan.id, line_id: arg }), "Varen er fjernet."),
    };
    actions[action]?.();
  }

  _onInput(ev) {
    const el = ev.target;
    const ds = el.dataset;
    if (this._v3Input(el, ev)) return;
    if (ds.bind === "store-choice") {
      if (ev.type !== "change") return;
      const target = el.value;
      el.value = this._state.entry_id;
      this._openStoreSwitch(target);
      return;
    }
    if (ds.bind === "remember-store-switch") {
      if (this._modal?.kind === "store-switch") this._modal.remember = el.checked;
      return;
    }
    if (ds.bind === "navigation") {
      if (ev.type !== "change") return;
      const list = this._modal?.draft?.[ds.screen];
      if (!list) return;
      const at = list.indexOf(ds.key);
      if (el.checked && at < 0 && (ds.screen !== "mobile" || list.length < 4)) list.push(ds.key);
      else if (!el.checked && at >= 0) list.splice(at, 1);
      this._renderModal();
      return;
    }
    if (ds.bind === "inventory-used") {
      const selected = this._modal?.selected;
      if (selected) { if (el.checked) selected.add(ds.id); else selected.delete(ds.id); }
      return;
    }
    if (ds.bind === "use-freezer-batch") { this._useFreezerBatch = el.checked; return; }
    if (ds.bind === "use-freezer") { this._useFreezer = el.checked; return; }
    if (ds.bind === "inventory-field") {
      this._inventoryDraft = { ...this._inventoryDraft, [ds.field]: el.value };
      return;
    }
    if (ds.bind === "freezer-note") {
      this._freezerNote = el.value;
      return;
    }
    if (ds.bind === "freezer-portions") {
      if (ev.type === "change") this._run(async () => {
        this._plan = await this._ws("middagsro/freezer/portions", {
          plan_id: this._plan.id, date: ds.date, portions: Number(el.value),
        });
      }, "Portioner og indkøb er opdateret.");
      return;
    }
    if (ds.bind === "start") {
      this._startDate = el.value;
      this._startDateTouched = true;
      if (ev.type === "change") this._render(); // the skip boxes follow the dates
      return;
    }
    if (ds.bind === "daykind") {
      if (ev.type !== "change") return;
      const iso = ds.field;
      const kind = el.value;
      const before = this._kindOf(iso);
      this._dayKinds[iso] = { kind, text: kind === "fixed" ? before.text || "" : "" };
      if (kind !== "pick") delete this._picks[iso];
      if (kind === "skip") this._skip.add(iso);
      else this._skip.delete(iso);
      this._render();
      if (kind === "pick" && !this._picks[iso]) {
        this._modal = { kind: "pick", date: iso, tab: "collection", query: "", rema: null, mealie: null };
        this._renderModal();
      }
      return;
    }
    if (ds.bind === "daykindtext") {
      this._dayKinds[ds.field] = { kind: "fixed", text: el.value };
      return;
    }
    if (ds.bind === "skip") {
      if (el.checked) this._skip.add(el.value);
      else this._skip.delete(el.value);
      return;
    }
    if (ds.bind === "note") {
      this._noteDraft = el.value;
      return;
    }
    if (ds.bind === "sitequery") {
      this._sites.query = el.value;
      if (ev.type === "change") this._siteSearch(el.value);
      return;
    }
    if (ds.bind === "pickq") {
      const m = this._modal;
      if (m?.kind !== "pick") return;
      m.query = el.value;
      if (m.tab === "rema") {
        if (ev.type === "change") this._pickLoad("rema");
        return;
      }
      if (m.tab === "sites") {
        if (ev.type === "change") this._siteSearch(m.query, (m.sites ||= {}));
        return;
      }
      this._soon("pickq", () => this._renderModal());
      return;
    }
    if (ds.bind === "daysource") {
      if (this._modal?.kind === "day") this._modal.source = el.value;
      return;
    }
    if (ds.bind === "daytext") {
      if (this._modal?.kind === "day") this._modal.text = el.value;
      return;
    }
    if (ds.bind === "pedit") {
      if (this._modal?.kind === "purchase") this._modal[ds.field] = el.value;
      return;
    }
    if (ds.bind === "book") {
      this._book[ds.field] = el.value;
      return;
    }
    if (ds.bind === "favfilter") {
      this._favFilter = el.value;
      this._soon("favfilter", () => {
        const list = this.shadowRoot.querySelector("#fav-all");
        if (list) list.innerHTML = this._favRows();
      });
      return;
    }
    if (ds.bind === "itemfilter") {
      this._itemFilter = el.value;
      this._soon("itemfilter", () => this._render());
      return;
    }
    if (ds.bind === "rl") {
      this._rl[ds.field] = el.value;
      return;
    }
    if (ds.bind === "rrquery") {
      this._rrQuery = el.value;
      if (!el.value.trim() && this._rr.key === "search") this._rrSearch("");
      else if (ev.type === "change" && el.value.trim()) this._rrSearch(el.value);
      return;
    }
    if (ds.bind === "everywhere") {
      this._everywhere.query = el.value;
      if (!el.value.trim()) {
        // Emptied (also with the field's own ✕): the results go away.
        this._everywhere = { query: "", loading: false, data: null, error: null };
        this.shadowRoot.querySelectorAll(".ev-out").forEach((n) => (n.innerHTML = ""));
        return;
      }
      if (ev.type === "change") this._everywhereRun();
      return;
    }
    if (ds.bind === "chainquery") {
      this._chainQuery = el.value;
      this._soon("chainquery", () => {
        const list = this.shadowRoot.querySelector("#chain-offers");
        if (list) list.innerHTML = this._chainOfferRows();
      });
      return;
    }
    if (ds.bind === "rc") {
      this._rc[ds.field] = el.value;
      if (ds.field === "link") return;
      if (ds.field === "sort" && ev.type === "input") return; // change follows
      if (ds.field === "sort" || ev.type === "input") {
        this._soon("rc", () => {
          const list = this.shadowRoot.querySelector("#rc-list");
          if (list && ds.field === "query") list.innerHTML = this._collectionRows();
          else this._render();
        });
      }
      return;
    }
    if (ds.bind === "rcp") {
      const m = this._modal;
      if (m?.kind !== "recipe") return;
      const number = ["servings", "active_minutes", "total_minutes", "minutes"].includes(ds.field);
      const value = number ? Number(el.value) || 0 : el.value;
      if (ds.list) m.recipe[ds.list][Number(ds.idx)][ds.field] = value;
      else m.recipe[ds.field] = value;
      // Typing an ingredient searches REMA, so it can be linked to the very product.
      if (ds.list === "ingredients" && ds.field === "name" && ev.type === "input" && this._hasPrices()) this._ingSearchSoon(Number(ds.idx), el.value);
      if (ds.list === "ingredients" && ds.field === "name" && ev.type === "change") this._rcLinksSoon(m);
      return;
    }
    if (ds.bind === "newrule") {
      this._newRule = el.value;
      return;
    }
    if (ds.bind === "editrule") {
      if (this._editRule) this._editRule.text = el.value;
      return;
    }
    if (ds.bind === "favsearch") {
      this._favSearch.query = el.value;
      if (ev.type === "change" && el.value.trim() && this._isRema()) this._favSearchRun();
      return;
    }
    if (ds.bind === "line-left") {
      if (this._modal) this._modal.left = el.value;
      return;
    }
    if (ds.bind === "linesearch") {
      if (this._modal) this._modal.query = el.value;
      if (ev.type === "change") this._lineSearch();
      return;
    }
    if (ds.bind === "shopsearch") {
      this._shopSearch[ds.part].query = el.value;
      if (ev.type === "change") this._shopSearchRun(ds.part);
      return;
    }
    if (ds.bind === "search") {
      this._search.query = el.value;
      if (ev.type === "change") this._doSearch();
      return;
    }
    if (ds.bind === "newdislike") {
      this._newDislike = el.value;
      return;
    }
    if (ds.bind === "newfav") {
      this._newFav[ds.field] = el.value;
      return;
    }
    if (ds.bind === "editfav") {
      this._editFav[ds.field] = el.value;
      return;
    }
    if (ds.list && this._form) {
      const list = (this._form[ds.list] ||= []);
      const idx = list.indexOf(el.value);
      if (el.checked && idx < 0) list.push(el.value);
      if (!el.checked && idx >= 0) list.splice(idx, 1);
      this._dirty = true;
      this._updateSettingsSavebar();
      return;
    }
    if (ds.path && this._form) {
      let value = el.type === "checkbox" ? el.checked : el.value;
      if (ds.type === "number") value = value === "" ? 0 : Number(value);
      if (ds.type === "nullable") value = value || null;
      const keys = ds.path.split(".");
      let target = this._form;
      while (keys.length > 1) target = target[keys.shift()];
      target[keys[0]] = value;
      // A fixed day's own text only for a fixed dish.
      const fixedKind = /^fixed_days\.(\d+)\.kind$/.exec(ds.path);
      if (fixedKind && ev.type === "change") {
        const row = this._form.fixed_days[Number(fixedKind[1])];
        if (row) row.text = value === "fixed" ? "" : DAY_KIND_LABELS[value];
      }
      // The same budget in the other period, so switching doesn't turn it off.
      if (ds.path === "budget_period" && ev.type === "change") {
        const f = this._form;
        if (value === "week" && !f.weekly_budget && f.monthly_budget) f.weekly_budget = Math.round((f.monthly_budget * 12 * 7) / 365);
        if (value === "month" && f.weekly_budget) f.monthly_budget = Math.round((f.weekly_budget * 365) / 12 / 7);
      }
      this._dirty = true;
      this._updateSettingsSavebar();
      if (ev.type === "change" && (el.type === "radio" || el.tagName === "SELECT" || /_pct$/.test(ds.path) || ds.path === "lunch_count")) this._render();
    }
  }

  _updateSettingsSavebar() {
    const status = this.shadowRoot.querySelector("[data-settings-status]");
    const message = this._dirty ? "Ændringer er ikke gemt" : "Alt er gemt";
    if (status && status.textContent !== message) status.textContent = message;
    this.shadowRoot.querySelectorAll('.savebar [data-action="save-settings"], .savebar [data-action="reset-settings"]')
      .forEach(button => { button.disabled = this._busy || !this._dirty; });
  }

  async _loadFavs(force = false) {
    if (!this._isRema()) return; // no favourites in an app
    const week = this._favWeek;
    if (force) this._favCache = {};
    this._favsLoading = true;
    this._favsError = null;
    this._render();
    try {
      this._favCache[week] = await this._ws("middagsro/favorites", { force, week });
      this._loadFavCompare(week);
    } catch (err) {
      this._favsError = err?.message || String(err);
    }
    this._favsLoading = false;
    this._render();
  }

  // Favourites that are cheaper in one of the chosen chains that week.
  async _loadFavCompare(week) {
    const data = this._favCache[week];
    if (!data || !(this._state?.settings?.chains || []).length) return;
    const date = week === "next" && !data.fallback && data.catalog?.valid_from ? localDay(data.catalog.valid_from) : null;
    const products = (data.products || []).map((p) => ({ id: p.id, name: p.name, underline: p.underline, price: p.price, is_organic: p.is_organic }));
    try {
      this._favCompare[week] = (await this._ws("middagsro/chains/products", { products, date })).products;
      if (this._tab === "favorites") this._render();
    } catch (err) {
      this._favCompare[week] = {};
    }
  }

  _favCheaper(p) {
    const found = this._favCompare[this._favWeek]?.[String(p.id)];
    // The price you pay there; what that is for REMA's size is in the popup.
    return found
      ? `<button class="cheaper" data-action="fav-where" data-arg="${esc(p.id)}" title="Se priserne i butikkerne">${this._chainLogo(found.dealer_id, "tiny")}<span>${kr(found.price)} i ${esc(this._chainName(found.dealer_id))}</span></button>`
      : `<button class="cheaper plain" data-action="fav-where" data-arg="${esc(p.id)}">Sammenlign priser</button>`;
  }

  async _generate(surprise = false) {
    const dates = this._planDates();
    const kinds = Object.fromEntries(dates.map((iso) => [iso, this._kindOf(iso)]));
    await this._ws("middagsro/generate", {
      start_date: this._startDate || null,
      skip_dates: dates.filter((d) => kinds[d].kind === "skip"),
      surprise,
      days: Object.fromEntries(dates.map((d) => [d, { kind: kinds[d].kind === "pick" && !this._picks[d] ? "ai" : kinds[d].kind, text: kinds[d].text || "" }])),
      use_freezer: this._useFreezer !== false,
      picks: Object.fromEntries(Object.entries(this._picks).filter(([d]) => kinds[d]?.kind === "pick")),
    });
    this._skip.clear();
    this._picks = {};
    this._dayKinds = {};
    this._viewingLatest = true;
    this._tab = "plan";
  }

  // Save the wishes for the next plan, and make the plan right away if asked.
  _saveNote(generate = false) {
    const text = this._noteDraft.trim();
    this._noteOpen = false;
    this._renderModal();
    this._run(
      async () => {
        await this._ws("middagsro/note", { text });
        if (generate) await this._generate();
      },
      generate ? GENERATING_MESSAGE : text ? "Ønskerne bruges i næste madplan." : "Ønskerne er fjernet."
    );
  }

  // Every plan the panel has in full: the viewed one, the newest and those this week's days come from.
  _planOf(id) {
    const s = this._state || {};
    return [this._plan, s.latest_plan, s.current_plan, ...(s.timeline_plans || [])].find((p) => p && p.id === id) || null;
  }

  // This week and the coming days as one plan: each date from the newest plan that covers it.
  // Null when looking at an older plan, or when nothing is planned from today on.
  _timeline() {
    if (!this._viewingLatest) return null;
    const today = localToday();
    const list = (this._state?.timeline || [])
      .map((e) => {
        const plan = this._planOf(e.plan_id);
        return plan ? { ...e, plan, day: e.skipped ? null : plan.days.find((d) => d.date === e.date) || null } : null;
      })
      .filter(Boolean);
    return list.some((e) => e.date >= today) ? list : null;
  }

  // The dinners of the week (or of the plan being viewed), in order.
  _recipeDays() {
    const plan = this._plan;
    if (!plan) return [];
    const timeline = this._timeline();
    if (timeline) return timeline.filter((e) => e.day).map((e) => ({ plan: e.plan, day: e.day }));
    return plan.days.map((day) => ({ plan, day }));
  }

  // "planId|date" -> position in _recipeDays(); otherwise today, else the first day.
  _recipeIndex(arg) {
    const list = this._recipeDays();
    const [planId, date] = String(arg || "").split("|");
    let idx = list.findIndex((x) => x.plan.id === planId && x.day.date === date);
    if (idx < 0) idx = list.findIndex((x) => x.day.date === localToday());
    return Math.max(0, idx);
  }

  async _doSearch() {
    const query = this._search.query.trim();
    if (!query) return;
    this._search.loading = true;
    this._render();
    try {
      this._search.results = await this._ws("middagsro/search", { query });
    } catch (err) {
      this._say(`Søgningen fejlede: ${err?.message || err}`);
    }
    this._search.loading = false;
    this._render();
  }

  // A change to the plan being viewed: run it, then show the plan as it is now.
  _editPlan(fn, okMessage) {
    return this._run(async () => {
      await fn();
      if (!this._viewingLatest && this._plan) this._plan = await this._ws("middagsro/plan", { plan_id: this._plan.id });
    }, okMessage);
  }

  // Offers in REMA's avis whose text has every searched word (read once, then from memory).
  async _remaAvisMatches(query) {
    const words = query.toLowerCase().split(/\s+/).filter((w) => w.length > 1);
    if (!words.length) return [];
    try {
      const shop = this._storeId();
      if (!this._chainOffers[shop]?.offers) {
        const data = await this._ws("middagsro/chains/offers", { dealer_id: shop });
        this._chainOffers[shop] = { offers: data.offers, loading: false };
      }
    } catch (err) {
      return [];
    }
    return (this._chainOffers[this._storeId()].offers || [])
      .filter((o) => words.every((w) => `${o.heading} ${o.description || ""}`.toLowerCase().includes(w)))
      .slice(0, 5);
  }

  async _shopSearchRun(part) {
    const search = this._shopSearch[part];
    const query = search?.query.trim();
    if (!query) return;
    search.loading = true;
    search.searched = true;
    search.offers = [];
    this._render();
    // REMA's avis too: partivarer are only sold in the shops, so the product search misses them.
    const avis = part === "main" ? this._remaAvisMatches(query) : Promise.resolve([]);
    try {
      // Another shop has no products online: the avis, and the text as it is typed.
      search.results = this._hasPrices() ? await this._ws("middagsro/search", { query }) : [];
    } catch (err) {
      search.results = [];
      this._say(`Søgningen fejlede: ${err?.message || err}`);
    }
    search.offers = await avis;
    if (this._hasPrices() && !search.results.length && !search.offers.length) this._say(`Ingen varer fundet for "${query}".`);
    search.loading = false;
    this._render();
  }

  // Take a skipped day back into the plan; then open its menu at a section (or close).
  async _dayBack(m, section) {
    m.busy = "back";
    m.error = null;
    this._renderModal();
    try {
      const plan = await this._ws("middagsro/day/restore", { plan_id: m.planId, date: m.date });
      if (!this._viewingLatest && this._plan?.id === plan.id) this._plan = plan;
      await this._load();
      if (!section) {
        this._modal = null;
        this._renderModal();
        return this._say(`${dateLabel(m.date)} er tilbage i madplanen.`);
      }
      const day = this._planOf(m.planId)?.days.find((d) => d.date === m.date);
      const leftovers = !!day?.uses_leftovers_from || day?.type === "rester";
      const foods = this._foodDays(this._planOf(m.planId), m.date);
      Object.assign(m, {
        busy: null, skipped: false, section, dish: day?.dish || "", written: day?.type === "egen", leftovers,
        food: leftovers ? day.uses_leftovers_from : null,
        source: (leftovers && day.uses_leftovers_from) || (foods.length ? foods[foods.length - 1].date : null),
      });
    } catch (err) {
      m.busy = null;
      m.error = err?.message || String(err);
    }
    this._renderModal();
  }

  // The day whose dinner a leftovers day eats.
  _foodDay(plan, day) {
    const days = plan?.days || [];
    return (
      days.find((d) => d.date === day.uses_leftovers_from) ||
      [...days].reverse().find((d) => d.date < day.date && !d.uses_leftovers_from && !["rester", "tom", "egen"].includes(d.type) && d.dish) ||
      null
    );
  }

  // The days a day can eat the leftovers of: earlier days with a dinner.
  _foodDays(plan, date) {
    return (plan?.days || []).filter((d) => d.date < date && d.dish && !d.uses_leftovers_from && !["rester", "tom", "egen"].includes(d.type));
  }

  async _pickForDay(m, pick) {
    const { planId, date } = m.target;
    m.busy = true;
    m.error = null;
    this._renderModal();
    try {
      const plan =
        pick.source === "collection"
          ? await this._ws("middagsro/recipes/plan", { recipe_id: pick.recipe_id, plan_id: planId, date })
          : pick.source === "rema"
            ? await this._ws("middagsro/rema_recipes/plan", { slug: pick.slug, plan_id: planId, date })
            : await this._ws("middagsro/swap", { plan_id: planId, date, option: { dish: pick.dish, mealie: pick.slug } });
      if (!this._viewingLatest && this._plan?.id === plan.id) this._plan = plan;
      this._modal = null;
      this._renderModal();
      await this._load();
      this._say(`${pick.dish} er sat på ${dateLabel(date).toLowerCase()} – indkøbslisten og opskriften er lavet om.`);
    } catch (err) {
      m.busy = false;
      m.error = err?.message || String(err);
      this._renderModal();
    }
  }

  async _swapOptions() {
    const m = this._modal;
    if (!m || m.busy) return;
    m.busy = "options";
    m.error = null;
    this._renderModal();
    try {
      const result = await this._ws("middagsro/swap/options", {
        plan_id: m.planId, date: m.date, leftovers: m.mode || "day", vegetarian: !!m.vegetarian,
      });
      Object.assign(m, { options: result.options, optionsFor: result.dish, optionsDate: result.date });
    } catch (err) {
      m.error = err?.message || String(err);
    }
    m.busy = null;
    this._renderModal();
  }

  async _swapPick(idx, own = null) {
    const m = this._modal;
    const option = own || m?.options?.[idx];
    if (!option || m.busy) return;
    m.busy = own ? "own" : "swap";
    m.picked = idx;
    m.error = null;
    this._renderModal();
    try {
      const plan = await this._ws("middagsro/swap", { plan_id: m.planId, date: m.date, option, leftovers: m.mode || "day" });
      if (!this._viewingLatest && this._plan?.id === plan.id) this._plan = plan;
      this._modal = null;
      this._renderModal();
      await this._load();
      this._say(`${option.dish} er sat på madplanen – indkøbslisten og opskriften er lavet om.`);
    } catch (err) {
      m.busy = null;
      m.error = err?.message || String(err);
      this._renderModal();
    }
  }

  async _pantryOpen() {
    if (!this._plan) return;
    this._modal = { kind: "pantry", busy: "load", items: [] };
    this._renderModal();
    await this._pantryLoad();
  }

  async _pantryLoad() {
    const m = this._modal;
    if (!m) return;
    try {
      m.items = await this._ws("middagsro/pantry", { plan_id: this._plan.id });
      m.error = null;
    } catch (err) {
      m.error = err?.message || String(err);
    }
    m.busy = null;
    this._renderModal();
  }

  async _pantryAdd(name) {
    const m = this._modal;
    if (!m || m.busy) return;
    m.busy = name;
    this._renderModal();
    try {
      const line = await this._ws("middagsro/plan/add", { plan_id: this._plan.id, pantry: name });
      if (!this._viewingLatest) this._plan = await this._ws("middagsro/plan", { plan_id: this._plan.id });
      await this._load();
      this._say(line.product ? `${line.product.name} er tilføjet til indkøbslisten.` : `${line.name} er tilføjet som fritekst.`);
    } catch (err) {
      m.error = err?.message || String(err);
    }
    await this._pantryLoad();
  }

  // ------------------------------------------------------------------ rules ("Det skal AI'en huske")

  _saveRules(list, okMessage) {
    this._run(async () => {
      const saved = await this._ws("middagsro/settings", { settings: { ...this._state.settings, rules: list } });
      if (this._form) this._form.rules = saved.rules;
    }, okMessage);
  }

  _rulesHtml() {
    const rules = this._state.settings.rules || [];
    const items = rules
      .map((text, i) =>
        this._editRule?.index === i
          ? `<li class="fav edit"><textarea data-bind="editrule" rows="2">${esc(this._editRule.text)}</textarea>
              <div class="row wrap">
                <button class="btn primary small" data-action="save-rule" ${this._busy ? "disabled" : ""}>Gem</button>
                ${this._micButton("editrule")}
                <button class="btn small" data-action="cancel-rule">Annullér</button>
              </div></li>`
          : `<li class="fav"><div class="what" data-action="edit-rule" data-arg="${i}"><span>${esc(text)}</span></div>
              <button class="btn small" data-action="edit-rule" data-arg="${i}">Ret</button>
              <button class="btn small danger" data-action="delete-rule" data-arg="${i}">Slet</button></li>`
      )
      .join("");
    return `<textarea data-bind="newrule" rows="2" placeholder="Fx: Vi vil altid have frisk broccoli og fettuccine med spinat til laksefilet">${esc(this._newRule)}</textarea>
      <div class="row wrap">
        <button class="btn primary small" data-action="add-rule" ${this._busy ? "disabled" : ""}>Tilføj</button>
        ${this._micButton("newrule")}
      </div>
      <ul class="favs">${items || "<li class='muted'>Ingen endnu.</li>"}</ul>`;
  }

  // ------------------------------------------------------------------ dictation

  _micButton(target) {
    if (!this._canDictate()) return "";
    const on = this._dictating === target;
    return `<button class="btn small mic ${on ? "on" : ""}" data-action="dictate" data-arg="${target}">${on ? "■ Stop" : "🎤 Diktér"}</button>`;
  }

  _canDictate() {
    return Boolean(
      window.SpeechRecognition || window.webkitSpeechRecognition || (navigator.mediaDevices?.getUserMedia && this._hass?.connection)
    );
  }

  // Put dictated text into a field (and its state) without redrawing the page.
  _dictated(target, text) {
    text = String(text || "").trim();
    if (!text) return;
    const join = (old) => (old && !/\s$/.test(old) ? `${old} ${text}` : `${old || ""}${text}`);
    if (target === "newrule") this._newRule = join(this._newRule);
    else if (target === "editrule" && this._editRule) this._editRule.text = join(this._editRule.text);
    else if (target === "note") this._noteDraft = join(this._noteDraft);
    const field = this.shadowRoot.querySelector(`[data-bind="${target}"]`);
    if (field) field.value = target === "note" ? this._noteDraft : target === "newrule" ? this._newRule : this._editRule?.text || "";
  }

  _dictate(target) {
    if (this._dictating) {
      this._stopDictation?.();
      return;
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (Recognition) {
      const rec = new Recognition();
      rec.lang = "da-DK";
      rec.interimResults = false;
      rec.continuous = false;
      rec.onresult = (ev) => {
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          if (ev.results[i].isFinal) this._dictated(target, ev.results[i][0].transcript);
        }
      };
      rec.onerror = (ev) => {
        if (ev.error === "not-allowed") this._say("Giv adgang til mikrofonen for at diktere.");
        else if (ev.error !== "no-speech" && ev.error !== "aborted") this._dictateHA(target);
      };
      rec.onend = () => {
        if (this._dictating === target && this._stopDictation === stop) this._dictationDone();
      };
      const stop = () => rec.stop();
      this._stopDictation = stop;
      this._dictating = target;
      this._render();
      this._renderModal();
      try {
        rec.start();
      } catch (err) {
        this._dictateHA(target);
      }
      return;
    }
    this._dictateHA(target);
  }

  _dictationDone() {
    this._dictating = null;
    this._stopDictation = null;
    this._render();
    this._renderModal();
  }

  // Without the browser's own speech recognition (e.g. the Home Assistant app):
  // Home Assistant's own speech-to-text (Assist), as its voice dialog does.
  async _dictateHA(target) {
    const conn = this._hass?.connection;
    if (!navigator.mediaDevices?.getUserMedia || !conn) {
      this._say("Diktat virker ikke i denne browser.");
      return this._dictationDone();
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      this._say("Giv adgang til mikrofonen for at diktere.");
      return this._dictationDone();
    }
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const source = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    let handler = null;
    let stopped = false;
    let unsub = null;
    const waiting = [];
    const send = (pcm) => {
      const msg = new Uint8Array(1 + pcm.byteLength);
      msg[0] = handler;
      msg.set(new Uint8Array(pcm.buffer), 1);
      conn.socket.send(msg);
    };
    const finish = () => {
      if (stopped) return;
      stopped = true;
      proc.disconnect();
      source.disconnect();
      stream.getTracks().forEach((t) => t.stop());
      ctx.close();
      if (handler !== null) conn.socket.send(new Uint8Array([handler])); // end of audio
    };
    this._stopDictation = finish;
    this._dictating = target;
    this._render();
    this._renderModal();
    proc.onaudioprocess = (ev) => {
      if (stopped) return;
      const input = ev.inputBuffer.getChannelData(0);
      const pcm = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) pcm[i] = Math.max(-1, Math.min(1, input[i])) * 0x7fff;
      if (handler === null) waiting.push(pcm);
      else send(pcm);
    };
    source.connect(proc);
    proc.connect(ctx.destination);
    try {
      unsub = await conn.subscribeMessage(
        (ev) => {
          if (ev.type === "run-start") {
            handler = ev.data.runner_data.stt_binary_handler_id;
            waiting.splice(0).forEach(send);
          } else if (ev.type === "stt-vad-end") {
            finish();
          } else if (ev.type === "stt-end") {
            this._dictated(target, ev.data?.stt_output?.text);
          } else if (ev.type === "error") {
            finish();
            this._say(`Diktat fejlede: ${ev.data?.message || ev.data?.code || "ukendt fejl"}`);
          }
          if (ev.type === "run-end" || ev.type === "error") {
            unsub?.();
            this._dictationDone();
          }
        },
        { type: "assist_pipeline/run", start_stage: "stt", end_stage: "stt", input: { sample_rate: ctx.sampleRate } }
      );
    } catch (err) {
      finish();
      this._say(`Diktat virker ikke: ${err?.message || err}. Sæt tale-til-tekst op under Indstillinger › Stemmeassistenter.`);
      this._dictationDone();
    }
  }

  // ------------------------------------------------------------------ shopping line popup

  _openLine(lineId) {
    const plan = this._plan;
    const line = plan?.shopping.find((l) => l.id === lineId);
    if (!line) return;
    const m = { kind: "line", planId: plan.id, lineId, packages: line.packages || 1, query: "", results: [], loading: false };
    this._modal = m;
    this._renderModal();
    // REMA's nutrition per 100 g, as the app shows it.
    if (line.product?.id) {
      this._ws("middagsro/nutrition", { product_id: line.product.id })
        .then((n) => {
          m.nutrition = n;
          if (this._modal === m) this._renderModal();
        })
        .catch(() => {});
    }
  }

  async _lineAction(data, okMessage, command = "middagsro/plan/line") {
    const m = this._modal;
    if (!m || m.busy) return;
    m.busy = true;
    m.error = null;
    this._renderModal();
    try {
      const plan = await this._ws(command, { plan_id: m.planId, line_id: m.lineId, ...data });
      if (!this._viewingLatest && this._plan?.id === plan.id) this._plan = plan;
      this._modal = null;
      this._renderModal();
      await this._load();
      this._say(okMessage);
    } catch (err) {
      m.busy = false;
      m.error = err?.message || String(err);
      this._renderModal();
    }
  }

  async _lineSearch() {
    const m = this._modal;
    const query = m?.query.trim();
    if (!query) return;
    m.loading = true;
    this._renderModal();
    try {
      m.results = await this._ws("middagsro/search", { query });
      if (!m.results.length) m.error = `Ingen varer fundet for "${query}".`;
    } catch (err) {
      m.error = err?.message || String(err);
    }
    m.loading = false;
    this._renderModal();
    this.shadowRoot.querySelector('[data-bind="linesearch"]')?.focus();
  }

  _lineModal(m) {
    const line = this._plan?.shopping.find((l) => l.id === m.lineId);
    if (!line) return "";
    const p = line.product || line.avis_item;
    const busy = !!m.busy;
    const results = m.loading
      ? '<p class="muted"><span class="spinner small"></span> Søger …</p>'
      : m.results
          .map(
            (r, i) => `<button class="result" data-action="line-pick" data-arg="${i}" ${busy ? "disabled" : ""}>
              ${r.image ? `<img src="${esc(r.image)}" alt="">` : ""}
              <span><b>${esc(r.name)}</b><span class="muted">${esc(r.underline || "")} · ${kr(r.price)}</span></span>
              ${r.is_organic ? '<span class="badge eco">Øko</span>' : ""}<span class="add">Vælg</span></button>`
          )
          .join("");
    const price = p?.price != null ? p.price : null;
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="line-title">
        <div class="line-head">
          ${p?.image ? `<img src="${esc(p.image)}" alt="">` : '<span class="noimg">?</span>'}
          <div><h2 id="line-title">${esc(p ? p.name : line.name)}</h2>
          <p class="muted small">${esc(p?.underline || "Fritekst")}${line.amount && line.unit && line.unit !== "pk" ? ` · behov ${esc(`${line.amount} ${line.unit}`)}` : ""}</p></div>
        </div>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        <div class="row wrap stepper">
          <span>Antal</span>
          <button class="btn small" data-action="line-count" data-arg="-1" ${busy || m.packages <= 1 ? "disabled" : ""}>−</button>
          <b class="count">${m.packages}</b>
          <button class="btn small" data-action="line-count" data-arg="1" ${busy || m.packages >= 99 ? "disabled" : ""}>+</button>
          ${price != null ? `<span class="muted">${kr(price * m.packages)}</span>` : ""}
          <span class="spacer"></span>
          <button class="btn small primary" data-action="line-save-count" ${busy || m.packages === (line.packages || 1) ? "disabled" : ""}>Gem antal</button>
        </div>
        ${m.nutrition && m.nutrition.kcal != null
          ? `<details class="nutrition"><summary>Næringsindhold pr. 100 g</summary><table>
              ${[["kcal", "Energi", " kcal"], ["fat_g", "Fedt", " g"], ["carbs_g", "Kulhydrat", " g"], ["fiber_g", "Kostfibre", " g"], ["protein_g", "Protein", " g"], ["salt_g", "Salt", " g"]]
                .filter(([k]) => m.nutrition[k] != null)
                .map(([k, label, unit]) => `<tr><td>${label}</td><td>${String(m.nutrition[k]).replace(".", ",")}${unit}</td></tr>`)
                .join("")}</table></details>`
          : ""}
        ${line.use_mode && !line.sent ? `<div class="left-box">
          <p class="small">${esc(line.use_note || "")}${line.use_note ? ". " : ""}Hvor meget har I tilbage? Kun resten købes.</p>
          <div class="row wrap">
            <label class="field inline">Har tilbage <input type="number" inputmode="decimal" min="0" step="any" data-bind="line-left" value="${esc(m.left ?? line.left ?? "")}" placeholder="0"> ${esc(line.unit || "")}</label>
            <button class="btn small primary" data-action="line-save-left" ${busy ? "disabled" : ""}>Gem</button>
          </div></div>` : ""}
        ${line.skipped ? `<div class="banner info">${line.have ? "I har varen hjemme, så den er ikke på listen denne gang." : "Varen er udeladt som forkert vare."} <button class="btn small" data-action="review-unskip" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>Tag den med igen</button></div>` : ""}
        ${this._needsReview(line) ? `<div class="banner warn"><div>Middagsro er ikke sikker på, at det er den rigtige vare${line.note ? ` (${esc(line.note)})` : ""}.
          <div class="row wrap">${p ? `<button class="btn small primary" data-action="review-keep" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>✓ Behold varen</button>` : ""}
          <button class="btn small" data-action="review-skip" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""} title="Varen udelades og vælges ikke til ingrediensen igen">Forkert vare</button></div></div></div>` : ""}
        ${!line.skipped && !line.sent ? `<p class="muted small"><button class="btn small" data-action="review-have" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>Har det hjemme</button> Tager varen af listen denne gang. Middagsro lærer ikke noget af det.</p>` : ""}
        ${line.remembered ? `<p class="muted small">Den vare I valgte til ingrediensen sidst. <button class="btn small" data-action="review-forget" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>Glem valget</button></p>` : ""}
        ${(line.alternatives || []).filter((a) => !p || a.id !== p.id).length ? `<h2 class="small-h">Andre muligheder</h2>
        <div class="results">${(line.alternatives || [])
          .filter((a) => !p || a.id !== p.id)
          .map((a) => `<button class="result" data-action="review-choose" data-arg="${esc(line.id)}|${a.id}" ${busy ? "disabled" : ""}>
              ${a.image ? `<img src="${esc(a.image)}" alt="">` : ""}
              <span><b>${esc(a.name)}</b><span class="muted">${esc(a.underline || "")}${a.price != null ? ` · ${kr(a.price)}` : ""}</span></span>
              ${a.is_organic ? '<span class="badge eco">Øko</span>' : ""}<span class="add">Vælg</span></button>`)
          .join("")}</div>` : ""}
        ${this._hasPrices() ? `<h2 class="small-h">Skift til en anden vare</h2>
        <div class="row wrap">
          <input class="grow" type="search" data-bind="linesearch" value="${esc(m.query)}" placeholder="Søg i ${esc(this._shopName())}">
          <button class="btn small" data-action="line-search" ${busy ? "disabled" : ""}>Søg</button>
          ${clearBtn("linesearch")}
        </div>
        <div class="results">${results}</div>` : ""}
        <div class="row wrap dialog-actions">
          <button class="btn danger" data-action="line-delete" ${busy ? "disabled" : ""}>Slet varen</button>
          <span class="spacer"></span>
          <button class="btn" data-action="modal-close" ${busy ? "disabled" : ""}>Luk</button>
        </div>
      </div>`;
  }

  // ------------------------------------------------------------------ health

  _healthKey() {
    const plan = this._plan;
    return plan ? `${plan.id}|${plan.total}|${plan.shopping?.length || 0}|${plan.days?.map((d) => d.dish).join("|")}` : "";
  }

  async _loadHealth(force = false) {
    const planId = this._plan?.id;
    if (!planId) return;
    const key = this._healthKey();
    if (!force && this._health?.key === key && (this._health.data || this._health.loading)) return;
    this._health = { planId, key, loading: true, data: null, error: null };
    this._render();
    try {
      this._health.data = await this._ws("middagsro/health", { plan_id: planId });
    } catch (err) {
      this._health.error = err?.message || String(err);
    }
    this._health.loading = false;
    if (this._tab === "health") this._render();
  }

  _healthView() {
    return `${this._v3Plate()}${this._healthPlanView()}`;
  }

  _healthPlanView() {
    if (!this._plan) return `<div class="card">Der er ingen madplan endnu.</div>`;
    const h = this._health;
    if (!h || h.key !== this._healthKey()) {
      setTimeout(() => this._loadHealth(), 0);
      return `<div class="card center"><span class="spinner"></span> Regner på madplanen …</div>`;
    }
    if (h.loading) return `<div class="card center"><span class="spinner"></span> Regner på madplanen …</div>`;
    if (h.error) return `<div class="card"><div class="banner error">${esc(h.error)}</div></div>`;
    const d = h.data;
    const t = d.targets;
    const bar = (value, goal, kind) => {
      const pct = goal ? Math.min(100, Math.round((value / goal) * 100)) : 0;
      const ok = kind === "max" ? value <= goal : value >= goal;
      return `<div class="meter ${ok ? "ok" : kind === "max" ? "over" : "low"}"><span style="width:${pct}%"></span></div>`;
    };
    const macro = (pct) =>
      pct ? `${pct.protein} % protein · ${pct.carbs} % kulhydrat · ${pct.fat} % fedt` : "";
    const avg = d.average || d.rema_average;
    const fromRema = !d.average && !!d.rema_average;
    const rema = d.rema_average;
    const kcalOk = avg && t ? avg.kcal >= t.kcal_min && avg.kcal <= t.kcal_max : null;
    const dinners = d.dinners
      .map(
        (x) => `<li class="hrow"><div class="what"><b>${esc(dateLabel(x.date))}</b><span>${esc(x.dish)}${x.leftovers ? ' <span class="badge">Rester</span>' : ""}</span>
          <span class="muted small">${x.percent ? macro(x.percent) : ""}</span></div>
          <div class="cost">${x.nutrition || x.rema
            ? `<b>${Math.round((x.nutrition || x.rema).kcal)} kcal</b>${Math.round((x.nutrition || x.rema).protein_g || 0)} g protein${x.nutrition && x.rema ? `<br><span class="small">REMA: ${Math.round(x.rema.kcal)} kcal</span>` : ""}`
            : "–"}</div></li>`
      )
      .join("");
    const nutritionCard = avg
      ? `<div class="card">
          <h1>Næring pr. aftensmad</h1>
          <p class="muted small">Pr. voksenportion${fromRema ? ", regnet ud fra REMA's næringsindhold for varerne" : ", som AI'en vurderer det ud fra opskriften"}. Børnenes portioner er mindre.</p>
          <div class="kpis">
            <div class="kpi"><span class="big ${kcalOk === false ? "warn" : ""}">${Math.round(avg.kcal)}</span><span class="muted">kcal i snit${t ? ` · mål ${t.kcal_min}–${t.kcal_max}` : ""}</span></div>
            <div class="kpi"><span class="big">${Math.round(avg.protein_g || 0)} g</span><span class="muted">protein</span></div>
            <div class="kpi"><span class="big">${Math.round(avg.carbs_g || 0)} g</span><span class="muted">kulhydrat</span></div>
            <div class="kpi"><span class="big">${Math.round(avg.fat_g || 0)} g</span><span class="muted">fedt</span></div>
            ${avg.fiber_g ? `<div class="kpi"><span class="big">${Math.round(avg.fiber_g)} g</span><span class="muted">kostfibre</span></div>` : ""}
          </div>
          ${(d.average_percent || d.rema_average_percent) ? `<p>Fordeling: <b>${macro(d.average_percent || d.rema_average_percent)}</b>${t ? ` <span class="muted">· mål ${t.protein} / ${t.carbs} / ${t.fat} %</span>` : ""}</p>` : ""}
          ${rema && !fromRema
            ? `<p class="nutri">Efter REMA's varedata: <b>${Math.round(rema.kcal)} kcal</b> · ${Math.round(rema.protein_g)} g protein · ${Math.round(rema.carbs_g)} g kulhydrat · ${Math.round(rema.fat_g)} g fedt
                <br><span class="muted small">Regnet ud fra næringsindholdet pr. 100 g på de varer, retten bruger (som i REMA-appen). Frugt, grønt og basisvarer har ofte ingen næringsdata, så tallet er typisk lidt lavt.</span></p>`
            : ""}
          ${t ? "" : '<p class="muted small">Sæt mål for kalorier og fordeling under Indstillinger › Næring.</p>'}
          <ul class="lines">${dinners}</ul>
        </div>`
      : `<div class="card"><h1>Næring pr. aftensmad</h1>
          <p class="muted">Næringen regnes ud, når opskrifterne skrives. Madplaner lavet før version 0.9 har den ikke – lav en ny madplan, eller tryk "Lav opskriften igen" på en ret.</p></div>`;
    const advice = d.advice
      .map(
        (a) => `<li class="hrow"><div class="what"><b>${esc(a.label)}</b><span class="muted small">${esc(a.note)}</span>
            ${bar(a.value, a.goal, a.kind)}</div>
          <div class="cost"><b>${a.value} g</b>${a.kind === "max" ? "højst" : "mål"} ${a.goal} g<br><span class="small">${esc(a.unit)}</span></div></li>`
      )
      .join("");
    const l = d.labels;
    const share = (v) => (v == null ? "–" : `${v} %`);
    return `
      ${nutritionCard}
      <div class="card">
        <h1>Kostrådene</h1>
        <p class="muted small">Ud fra indkøbslisten til ${d.days} dage og ${String(d.people).replace(".", ",")} portioner (børn tæller mindre). Kun aftensmaden er med – morgenmad, frokost og frugt kommer oveni.</p>
        <ul class="lines">${advice}</ul>
        ${d.unknown.length ? `<p class="muted small">Uden mængde: ${d.unknown.map(esc).join(", ")}.</p>` : ""}
        <p class="muted small">Kilde: <a href="https://www.sundhed.dk/borger/sygdomme-a-aa/hormoner-og-stofskifte/sygdomme/kost/sund-kost/" target="_blank" rel="noopener">De officielle kostråd (sundhed.dk)</a>.</p>
      </div>
      <div class="card">
        <h1>Mærker i kurven</h1>
        <p class="muted small">Andel af indkøbslistens pris.</p>
        ${l.known
          ? `<div class="kpis">
              <div class="kpi"><span class="big">${share(l.keyhole)}</span><span class="muted">Nøglehulsmærket</span></div>
              <div class="kpi"><span class="big">${share(l.organic)}</span><span class="muted">Økologisk</span></div>
              <div class="kpi"><span class="big">${share(l.asc_msc)}</span><span class="muted">ASC/MSC (fisk)</span></div>
            </div>`
          : `<p class="muted">Mærkerne gemmes på varerne fra version 0.9. Tryk "Opdatér tilbudsvarer" i Indkøb eller lav en ny madplan.</p>
            <div class="kpis"><div class="kpi"><span class="big">${share(l.organic)}</span><span class="muted">Økologisk</span></div></div>`}
      </div>
      <div class="row wrap"><button class="btn" data-action="health-refresh">Regn igen</button></div>`;
  }

  // ------------------------------------------------------------------ wake lock

  async _requestWake() {
    this._wakeWanted = true;
    if (!("wakeLock" in navigator)) {
      this._wakeWanted = false;
      this._say("Denne browser kan ikke holde skærmen tændt.");
      return;
    }
    try {
      this._wake = await navigator.wakeLock.request("screen");
      this._wake.addEventListener("release", () => {
        this._wake = null;
        this._render();
      });
    } catch (err) {
      this._wakeWanted = false;
      this._say(`Skærmen kan ikke holdes tændt: ${err?.message || err}`);
    }
    this._render();
  }

  async _releaseWake(render = false) {
    this._wakeWanted = false;
    if (this._wake) {
      try {
        await this._wake.release();
      } catch (err) {
        /* already released */
      }
      this._wake = null;
    }
    if (render) this._render();
  }

  // ------------------------------------------------------------------ timers

  // The timers live in state, not on the page: they ring whatever tab is open, once.
  _tickTimers() {
    this._fired ||= new Set();
    const clock = (left) => `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
    let soonest = null;
    for (const [key, end] of Object.entries(this._timers)) {
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      if (left === 0 && !this._fired.has(key)) {
        this._fired.add(key);
        if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
        this._beep();
        if (this._tab !== "recipes") this._say("Timeren er færdig!");
      }
      if (left > 0 && (soonest === null || left < soonest)) soonest = left;
    }
    this.shadowRoot.querySelectorAll("[data-timer]").forEach((node) => {
      const end = this._timers[node.dataset.timer];
      if (!end) return;
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      node.textContent = left > 0 ? clock(left) : "Færdig!";
      if (left === 0) node.closest(".step")?.classList.add("alarm");
    });
    this._v3SceneTick();
    const chip = this.shadowRoot.querySelector("#timerchip");
    if (chip) {
      const text = soonest === null ? "" : `⏱ ${clock(soonest)}`;
      if (chip.textContent !== text) chip.textContent = text;
    }
  }

  _beep() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      this._audio ||= new Ctx();
      const ctx = this._audio;
      if (ctx.state === "suspended") ctx.resume();
      const osc = ctx.createOscillator();
      osc.frequency.value = 880;
      osc.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.6);
    } catch (err) {
      /* no audio */
    }
  }

  // ------------------------------------------------------------------ render

  // ------------------------------------------------------------------ other chains

  async _loadChains() {
    if (this._chainsLoading) return;
    this._chainsLoading = true;
    try {
      this._chains = (await this._ws("middagsro/chains")).chains;
    } catch (err) {
      this._chains = [];
    }
    this._chainsLoading = false;
    this._render();
  }

  _chainInfo(id) {
    const fallback = { id, name: id === REMA_ID ? "REMA 1000" : id, color: id === REMA_ID ? "#0B2D8B" : null, logo: null };
    return (this._chains || []).find((c) => c.id === id) || fallback;
  }

  _chainName(id) {
    return this._chainInfo(id).name;
  }

  // A chain's logo in a circle, so they stand out from REMA's own things.
  _chainLogo(id, cls = "") {
    const c = this._chainInfo(id);
    return `<span class="chain-logo ${cls}" style="--c:${esc(c.color || "#888")}">${c.logo
      ? `<img class="cl" src="${esc(c.logo)}" alt="${esc(c.name)}">`
      : `<span>${esc(c.name.slice(0, 2))}</span>`}</span>`;
  }

  async _loadChainOffers(id, force = false) {
    this._chainOffers[id] = { ...(this._chainOffers[id] || {}), loading: true, error: null };
    this._render();
    try {
      const data = await this._ws("middagsro/chains/offers", { dealer_id: id, force });
      this._chainOffers[id] = { offers: data.offers, loading: false };
    } catch (err) {
      this._chainOffers[id] = { offers: null, loading: false, error: err?.message || String(err) };
    }
    this._render();
  }

  _chainOfferRows() {
    const data = this._chainOffers[this._chain] || {};
    const words = normName(this._chainQuery).split(" ").filter(Boolean);
    const offers = (data.offers || []).filter((o) => {
      const text = normName(`${o.heading} ${o.description || ""}`);
      return words.every((w) => text.includes(w));
    });
    if (!offers.length) return `<p class="muted">${data.offers?.length ? "Ingen tilbud passer til søgningen." : "Ingen madtilbud lige nu."}</p>`;
    const plan = this._state?.latest_plan;
    return offers
      .slice(0, 300)
      .map(
        (o) => `<div class="prod">
          ${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
          <div class="prod-body">
            <b>${esc(o.heading)}</b>
            ${o.description ? `<span class="muted small clamp">${esc(o.description)}</span>` : ""}
            <span class="prod-price"><b class="sale">${o.price != null ? kr(o.price) : ""}</b>${o.pre_price ? ` <s class="muted">${kr(o.pre_price)}</s>` : ""}</span>
            <span class="muted small">${o.quantity ? `${esc(o.quantity)} · ` : ""}${o.valid_to ? `til ${esc(shortDate(localDay(o.valid_to)))}` : ""}</span>
          </div>
          ${plan ? `<button class="btn small" data-action="chain-add" data-arg="${esc(o.id)}" ${this._busy ? "disabled" : ""}>+ Indkøb</button>` : ""}
        </div>`
      )
      .join("");
  }

  _chainView() {
    const id = this._chain;
    const c = this._chainInfo(id);
    const data = this._chainOffers[id] || {};
    const count = data.offers?.length;
    return `
      <div class="settings-head">
        <button class="btn back" data-action="chain-close">‹ Tilbage</button>
        ${this._chainLogo(id, "big")}
        <h1>Tilbud i ${esc(c.name)}</h1>
      </div>
      <div class="card">
        <div class="row wrap">
          <input class="grow" type="search" data-bind="chainquery" value="${esc(this._chainQuery)}" placeholder="Søg i tilbuddene, fx kaffe">
          ${clearBtn("chainquery")}
          <button class="btn small" data-action="chain-refresh" ${data.loading ? "disabled" : ""}>${data.loading ? '<span class="spinner small"></span>' : "Opdatér"}</button>
        </div>
        <p class="muted small">${count != null ? `${count} madtilbud fra ${esc(c.name)}${c.name.endsWith("s") ? "'" : "s"} aviser. ` : ""}${id === this._storeId() ? `Med "+ Indkøb" kommer tilbuddet på indkøbslisten${this._isRema() ? " og sendes til REMA-appen med resten" : ""}.` : `Med "+ Indkøb" kommer et tilbud på ${esc(c.name)}-listen under Indkøb – ${this._listName()} er uændret.`}</p>
        ${data.error ? `<div class="banner error">${esc(data.error)}</div>` : ""}
        ${data.loading && !data.offers ? '<p class="muted"><span class="spinner small"></span> Henter tilbud …</p>' : `<div class="prod-grid" id="chain-offers">${this._chainOfferRows()}</div>`}
      </div>`;
  }

  // The chosen chains on the front page.
  _chainsCard() {
    const ids = [this._storeId(), ...(this._state.settings.chains || []).filter((id) => id !== this._storeId())];
    const e = this._everywhere;
    return `<div class="card chains-card">
      <h2 class="flush">Tilbud og priser</h2>
      <div class="chain-row">${ids
        .map((id) => `<button class="chain-btn" data-action="chain-open" data-arg="${esc(id)}">${this._chainLogo(id)}<span>${esc(this._chainName(id))}</span></button>`)
        .join("")}</div>
      <div class="row wrap everywhere">
        <input class="grow" type="search" data-bind="everywhere" value="${esc(e.query)}" placeholder="Søg på en vare – fx kaffe, smør eller laks" enterkeyhint="search">
        <button class="btn" data-action="everywhere" ${e.loading ? "disabled" : ""}>${e.loading ? '<span class="spinner small"></span>' : "Søg"}</button>
        <button class="btn" data-action="everywhere-clear">Ryd</button>
      </div>
      <div class="ev-out">${e.error ? `<div class="banner error">${esc(e.error)}</div>` : ""}${e.data ? this._everywhereHtml(e.data) : ""}</div>
    </div>`;
  }

  async _everywhereRun(query) {
    const q = String(query ?? this._everywhere.query).trim();
    if (!q) return this._say("Skriv en vare først.");
    this._everywhere = { query: q, loading: true, data: this._everywhere.data, error: null };
    this._render();
    try {
      this._everywhere = { query: q, loading: false, data: await this._ws("middagsro/search/everywhere", { query: q }), error: null };
    } catch (err) {
      this._everywhere = { query: q, loading: false, data: null, error: err?.message || String(err) };
    }
    this._render();
    this._renderModal();
  }

  // REMA's products and the other shops' offers for a search, cheapest marked.
  // The offer the favourite's "cheaper in Netto" badge is about: the same kind of item,
  // with what it costs there and what that is for REMA's size.
  _matchHtml(m) {
    const o = m?.match;
    const p = m?.product;
    if (!o || !p) return "";
    const plan = this._state?.latest_plan;
    const chain = this._chainName(o.dealer_id);
    const size = (p.underline || "").split("/")[0].trim();
    return `<div class="match">
      <h3>Samme slags hos ${esc(chain)}</h3>
      <ul class="evs"><li class="ev best">
        ${this._chainLogo(o.dealer_id, "tiny")}
        ${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
        <div class="what"><b>${esc(o.heading)}</b><span class="muted small">${esc([chain, o.description].filter(Boolean).join(" · "))}</span>
          <span class="small">≈ <b>${kr(o.per_package)}</b> for REMA's ${esc(size || "pakke")} (REMA: ${kr(p.price)})</span></div>
        <span class="ev-price sale">${o.price != null ? kr(o.price) : ""}</span>
        <button class="btn small" data-action="match-chain" ${this._busy || !plan ? "disabled" : ""} title="${plan ? "" : "Lav en madplan først"}">+ ${esc(chain)}</button>
      </li></ul>
    </div>`;
  }

  _everywhereHtml(data) {
    const unit = (u) => (u ? `${kr(u.price)}/${u.unit}` : "");
    const best = data.best;
    const isBest = (source, id) => best && best.source === source && String(best.id) === String(id);
    const plan = this._state?.latest_plan;
    const products = data.products
      .map(
        (p) => `<li class="ev ${isBest("rema", p.id) ? "best" : ""}">
          ${this._chainLogo(REMA_ID, "tiny")}
          ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
          <div class="what"><b>${esc(p.name)}</b><span class="muted small">${esc(p.underline || "")}${p.unit_price ? ` · ${unit(p.unit_price)}` : ""}</span>
            ${isBest("rema", p.id) ? '<span class="badge eco">Billigst</span>' : ""}</div>
          <span class="ev-price ${onOffer(p) ? "sale" : ""}">${kr(p.price)}</span>
          ${plan
            ? `<span class="ev-btns">
                <button class="btn small" data-action="ev-rema" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""} title="På madplanens indkøbsliste">+ Indkøb</button>
                <button class="btn small" data-action="ev-rema-list" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""} title="Direkte på ${esc(this._quickTodo()?.name || "REMA-listen i appen")}">${esc(this._quickLabel())}</button>
              </span>`
            : `<button class="btn small" data-action="ev-rema-list" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""}>${esc(this._quickLabel())}</button>`}
        </li>`
      )
      .join("");
    const offers = data.offers
      .map(
        (o) => `<li class="ev ${isBest("chain", o.id) ? "best" : ""}">
          ${this._chainLogo(o.dealer_id, "tiny")}
          ${o.image ? `<img src="${esc(o.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
          <div class="what"><b>${esc(o.heading)}</b><span class="muted small">${esc(this._chainName(o.dealer_id))}${o.full_price ? " · fast pris" : ""}${o.description ? ` · ${esc(o.description)}` : ""}${o.unit_price ? ` · ${unit(o.unit_price)}` : ""}</span>
            ${isBest("chain", o.id) ? '<span class="badge eco">Billigst</span>' : ""}</div>
          <span class="ev-price sale">${o.price != null ? kr(o.price) : ""}</span>
          <button class="btn small" data-action="ev-chain" data-arg="${esc(o.id)}" ${this._busy || !plan ? "disabled" : ""} title="${plan ? "" : "Lav en madplan først"}">+ ${esc(this._chainName(o.dealer_id))}</button>
        </li>`
      )
      .join("");
    const chains = (this._state.settings.chains || []).length;
    return `<div class="everywhere-results">
      ${best
        ? `<p class="best-line">Billigst: <b>${unit(best.unit_price)}</b> hos ${esc(best.source === "rema" ? "REMA 1000" : this._chainName((data.offers.find((o) => o.id === best.id) || {}).dealer_id))}</p>`
        : ""}
      ${this._isRema() ? `<h3>REMA 1000</h3>
      <ul class="evs">${products || '<li class="muted">Ingen varer fundet hos REMA.</li>'}</ul>` : ""}
      ${chains
        ? `<h3>${data.offers.some((o) => o.full_price) ? "Andre butikker" : "Tilbud i andre butikker"}</h3><ul class="evs">${offers || '<li class="muted">Ingen af de andre butikker har den på tilbud lige nu.</li>'}</ul>`
        : '<p class="muted small">Vælg andre butikker under Indstillinger › Andre butikker for at sammenligne med deres tilbud.</p>'}
    </div>`;
  }

  // Which of the plan's items are cheaper in the chosen chains (read once per change of the list).
  _ensureCompare() {
    const plan = this._plan;
    if (!plan || !(this._state.settings.chains || []).length) return null;
    const key = `${plan.id}|${plan.total}|${plan.shopping.length}|${(this._state.settings.chains || []).join(",")}`;
    if (this._compare?.key === key) return this._compare;
    this._compare = { key, loading: true, lines: {}, chains: {} };
    this._ws("middagsro/chains/compare", { plan_id: plan.id })
      .then((data) => {
        if (this._compare?.key === key) this._compare = { key, loading: false, ...data };
      })
      .catch(() => {
        if (this._compare?.key === key) this._compare = { key, loading: false, lines: {}, chains: {} };
      })
      .finally(() => this._tab === "shopping" && this._render());
    return this._compare;
  }

  _chainListsHtml(plan) {
    const byChain = {};
    plan.shopping.filter((l) => l.buy_at).forEach((l) => (byChain[l.buy_at] ||= []).push(l));
    return Object.entries(byChain)
      .map(([id, lines]) => {
        const total = lines.filter((l) => !l.bought).reduce((sum, l) => sum + (l.cost || 0), 0);
        const bought = lines.filter((l) => l.bought).length;
        const rows = lines
          .map(
            (l) => `<li class="cline ${l.bought ? "bought" : ""}">
              <button class="box" data-action="chain-tick" data-arg="${esc(l.id)}" aria-label="Købt" aria-pressed="${!!l.bought}">${l.bought ? "✓" : ""}</button>
              <div class="what"><b>${esc(l.chain_heading || l.product?.name || l.name)}</b>
                <span class="muted small">${l.chain_only ? esc(l.note || "") : l.chain_planned ? `Tilbud i madplanen${l.product?.name && l.product.name !== l.chain_heading ? ` · hos ${this._isRema() ? "REMA" : esc(this._shopName())}: ${esc(l.product.name)}` : ""}` : `I stedet for ${esc(l.product?.name || l.name)} hos ${this._isRema() ? "REMA" : esc(this._shopName())}`}</span></div>
              <span class="cost"><b>${kr(l.cost)}</b></span>
              <span class="ctrl">
                <span class="stepper">
                  <button class="icon-btn" data-action="chain-count" data-arg="${esc(l.id)}|-1" aria-label="Færre">−</button>
                  <b>${l.packages || 1}</b>
                  <button class="icon-btn" data-action="chain-count" data-arg="${esc(l.id)}|1" aria-label="Flere">+</button>
                </span>
                ${l.chain_only ? "" : `<button class="icon-btn" data-action="chain-move" data-arg="${esc(l.id)}|" title="Tilbage på ${this._listName()}" aria-label="Tilbage på REMA-listen">↩</button>`}
                <button class="icon-btn" data-action="chain-delete" data-arg="${esc(l.id)}" aria-label="Slet">${CLOSE_ICON}</button>
              </span>
            </li>`
          )
          .join("");
        return `<div class="card chain-list" style="--c:${esc(this._chainInfo(id).color || "#888")}">
          <div class="row between wrap">
            <div class="row">${this._chainLogo(id)}<h1 class="flush">Indkøb i ${esc(this._chainName(id))}</h1></div>
            <div class="price"><span class="big">${kr(total)}</span><span class="muted">${lines.length - bought} mangler</span></div>
          </div>
          <ul class="clines">${rows}</ul>
          <div class="row wrap actions">
            <button class="btn" data-action="chain-clear" data-arg="${esc(id)}" ${this._busy ? "disabled" : ""}>Ryd kurven${bought ? ` (${bought} købt)` : ""}</button>
            <button class="btn" data-action="chain-open" data-arg="${esc(id)}" ${this._busy ? "disabled" : ""}>Se tilbud i ${esc(this._chainName(id))}</button>
          </div>
        </div>`;
      })
      .join("");
  }

  // ------------------------------------------------------------------ recipe collection

  // The collection's recipe for a plan's dinner (leftovers: the dish they are from).
  _recipeForDay(plan, day) {
    let cooked = day;
    if (day.uses_leftovers_from) cooked = plan.days.find((d) => d.date === day.uses_leftovers_from) || day;
    const recipes = this._state?.recipes || [];
    return {
      cooked,
      recipe: recipes.find((r) => r.id === cooked.recipe_id) || recipes.find((r) => normName(r.name) === normName(cooked.dish)),
    };
  }

  _rateButtons(plan, day) {
    const { cooked, recipe } = this._recipeForDay(plan, day);
    if (!cooked?.dish || cooked.type === "tom" || cooked.type === "egen") return '<span class="rate"><span class="rate-gap"></span><span class="rate-gap"></span><span class="rate-gap"></span></span>';
    const on = { like: recipe?.rating === "like", dislike: recipe?.rating === "dislike", favorite: !!recipe?.favorite };
    return `<span class="rate">${["like", "dislike", "favorite"]
      .map(
        (a) => `<button class="rate-btn ${a} ${on[a] ? "on" : ""}" data-action="rate-day" data-arg="${esc(plan.id)}|${esc(day.date)}|${a}"
          title="${RATE_LABELS[a]}" aria-label="${RATE_LABELS[a]}: ${esc(cooked.dish)}" aria-pressed="${on[a]}" ${this._busy ? "disabled" : ""}>${RATE_ICONS[a]}</button>`
      )
      .join("")}</span>`;
  }

  // Move a dinner a day up or down: under 👍 and 👎; the place under ❤️ is kept free.
  // The shop the family shops in: REMA 1000 (with its login), or another chosen
  // when Middagsro was set up (its Tjek dealer id), without prices or app.
  _storeId() {
    const shop = this._state?.shop;
    return !shop || shop.rema ? REMA_ID : shop.id;
  }

  _isRema() {
    return this._storeId() === REMA_ID;
  }

  // Every item has a price and can be searched: REMA 1000, and Bilka (its webshop).
  _hasPrices() {
    return this._isRema() || !!this._state?.shop?.prices;
  }

  // "REMA-listen" (the list in the REMA app), or "indkøbslisten" with another shop.
  _listName() {
    return this._isRema() ? "REMA-listen" : this._state?.shop?.bilka_cart ? `${this._state.shop.cart_name || "BilkaToGo"}-kurven` : "indkøbslisten";
  }

  _shopName() {
    return this._state?.shop?.name || "REMA 1000";
  }

  // "Nettos", "føtex'", "REMA 1000s".
  _shopGen() {
    return genitive(this._shopName());
  }

  _moveButtons(plan, day, past) {
    const near = (step) => {
      const d = new Date(`${day.date}T12:00:00`);
      d.setDate(d.getDate() + step);
      const iso = localDay(d.toISOString());
      return (plan.days || []).find((x) => x.date === iso);
    };
    const button = (dir, other) => {
      const off = past || !other || other.date < localToday() || this._busy;
      return `<button class="rate-btn move" data-action="move-day" data-arg="${esc(plan.id)}|${esc(day.date)}|${dir}" ${off ? "disabled" : ""}
        title="${dir === "up" ? "Flyt en dag op" : "Flyt en dag ned"}" aria-label="${dir === "up" ? "Flyt en dag op" : "Flyt en dag ned"}: ${esc(day.dish || "")}">${MOVE_ICONS[dir]}</button>`;
    };
    return `<span class="rate move-row">${button("up", near(-1))}${button("down", near(1))}<span class="rate-gap"></span></span>`;
  }

  _recipeRateButtons(recipe) {
    return `<span class="rate">${["like", "dislike", "favorite"]
      .map((a) => {
        const on = a === "favorite" ? !!recipe.favorite : recipe.rating === a;
        return `<button class="rate-btn ${a} ${on ? "on" : ""}" data-action="rate-recipe" data-arg="${esc(recipe.id || "")}|${a}"
          title="${RATE_LABELS[a]}" aria-label="${RATE_LABELS[a]}" aria-pressed="${on}" ${this._busy ? "disabled" : ""}>${RATE_ICONS[a]}</button>`;
      })
      .join("")}</span>`;
  }

  _filteredRecipes() {
    const words = normName(this._rc.query).split(" ").filter(Boolean);
    const list = (this._state.recipes || []).filter((r) => {
      if (this._rc.filter === "favorite" && !r.favorite) return false;
      if (["like", "dislike"].includes(this._rc.filter) && r.rating !== this._rc.filter) return false;
      if (this._rc.filter === "unlinked" && !r.missing) return false;
      const text = normName(`${r.name} ${(r.ingredient_names || []).join(" ")}`);
      return words.every((w) => text.includes(w));
    });
    const by = {
      name: (a, b) => a.name.localeCompare(b.name, "da"),
      newest: (a, b) => String(b.created || "").localeCompare(String(a.created || "")),
      most_used: (a, b) => (b.times_planned || 0) - (a.times_planned || 0) || a.name.localeCompare(b.name, "da"),
      quickest: (a, b) => (a.total_minutes || 999) - (b.total_minutes || 999),
    }[this._rc.sort];
    return list.sort(by);
  }

  _collectionRows() {
    const list = this._filteredRecipes();
    if (!list.length) {
      return (this._state.recipes || []).length
        ? '<p class="muted">Ingen opskrifter passer til søgningen.</p>'
        : '<p class="muted">Opskriftsamlingen er tom. Giv en ret 👍 eller ♥ på madplanen, indsæt et link til en opskrift, eller skriv en ny.</p>';
    }
    return list
      .map(
        (r) => `<div class="rc-item">
          <button class="rc-open" data-action="rc-open" data-arg="${esc(r.id)}">
            <b>${esc(r.name)}</b>
            <span class="muted small">${[
              r.total_minutes ? `${r.total_minutes} min` : "",
              r.type === "vegetar" ? "Vegetar" : "",
              r.times_planned ? `brugt ${r.times_planned} ${r.times_planned === 1 ? "gang" : "gange"}` : "",
              r.source === "link" ? "fra link" : r.source === "web" ? `fra ${r.site || "madside"}` : r.source === "scan" ? "fra kogebog" : r.source === "manual" ? "egen opskrift" : "",
            ]
              .filter(Boolean)
              .join(" · ")}${this._hasPrices() ? (r.ready ? ' <span class="badge ready">Klar</span>' : r.missing ? ` <span class="badge doubt">Mangler ${r.missing} ${r.missing === 1 ? "vare" : "varer"}</span>` : "") : ""}</span>
          </button>
          ${this._recipeRateButtons(r)}
        </div>`
      )
      .join("");
  }

  _collectionView() {
    const filters = Object.entries(RECIPE_FILTERS)
      .map(([k, l]) => `<button class="chip ${this._rc.filter === k ? "active" : ""}" data-action="rc-filter" data-arg="${k}">${l}</button>`)
      .join("");
    return `
      <div class="card">
        <h2 class="flush">Tilføj en opskrift</h2>
        <div class="row wrap">
          <input class="grow" type="url" inputmode="url" data-bind="rc" data-field="link" value="${esc(this._rc.link)}" placeholder="Indsæt et link til en opskrift">
          <button class="btn primary" data-action="rc-import" ${this._rc.importing ? "disabled" : ""}>${this._rc.importing ? '<span class="spinner small"></span> Henter …' : "Hent opskrift"}</button>
          <button class="btn" data-action="rc-new">Skriv selv</button>
        </div>
        <div class="row wrap scan-row">
          <button class="btn scan-btn" data-action="rc-scan" ${this._rc.scanning ? "disabled" : ""}>${this._rc.scanning ? '<span class="spinner small"></span> Læser opskriften …' : `${CAMERA_ICON} Scan fra kogebog`}</button>
          <input type="file" id="scan-input" accept="image/*" multiple hidden>
          <span class="muted small">Tag et billede af siden – eller flere, hvis opskriften fylder mere end én.</span>
        </div>
        <p class="muted small">Opskriften hentes fra siden eller billedet, og du kan rette den, før den gemmes. Linket og billederne gemmes ikke.</p>
      </div>
      <div class="card">
        <div class="row wrap">
          <input class="grow" type="search" data-bind="rc" data-field="query" value="${esc(this._rc.query)}" placeholder="Søg i opskrifter og ingredienser">
          ${clearBtn("rc")}
          <label class="field inline">Sortér
            <select data-bind="rc" data-field="sort">${Object.entries(RECIPE_SORTS)
              .map(([k, l]) => `<option value="${k}" ${this._rc.sort === k ? "selected" : ""}>${l}</option>`)
              .join("")}</select></label>
        </div>
        <div class="chips">${filters}</div>
        <div id="rc-list" class="rc-list">${this._collectionRows()}</div>
      </div>`;
  }

  // Photos of a cookbook page: made smaller in the browser, read by the AI, then edited.
  async _recipeScan(files) {
    const images = files.filter((f) => f.type.startsWith("image/") || !f.type).slice(0, 4);
    if (!images.length) return;
    this._rc.scanning = true;
    this._render();
    try {
      const photos = [];
      for (const file of images) photos.push(await shrinkPhoto(file, images.length > 2 ? 1400 : 1700));
      const recipe = await this._ws("middagsro/recipes/scan", { photos });
      this._modal = { kind: "recipe", recipe: { ...recipe, id: null }, imported: true };
      this._renderModal();
    } catch (err) {
      this._say(`Fejl: ${err?.message || err}`);
    }
    this._rc.scanning = false;
    this._render();
  }

  async _recipeImport() {
    const url = this._rc.link.trim();
    if (!url) return this._say("Indsæt et link først.");
    this._rc.importing = true;
    this._render();
    try {
      const recipe = await this._ws("middagsro/recipes/import", { url });
      this._rc.link = "";
      this._modal = { kind: "recipe", recipe: { ...recipe, id: null }, imported: true };
      this._renderModal();
    } catch (err) {
      this._say(`Fejl: ${err?.message || err}`);
    }
    this._rc.importing = false;
    this._render();
  }

  async _recipeOpen(id) {
    this._modal = { kind: "recipe", loading: true, recipe: { id, name: "" } };
    this._renderModal();
    try {
      const recipe = await this._ws("middagsro/recipes/get", { recipe_id: id });
      if (this._modal?.kind === "recipe" && this._modal.recipe.id === id) {
        this._modal = { kind: "recipe", recipe: clone(recipe) };
        this._renderModal();
      }
    } catch (err) {
      this._modal = null;
      this._renderModal();
      this._say(`Fejl: ${err?.message || err}`);
    }
  }

  async _recipeSave() {
    const m = this._modal;
    if (m?.kind !== "recipe" || m.busy) return;
    const r = m.recipe;
    if (!String(r.name || "").trim()) return this._say("Giv opskriften et navn.");
    const recipe = {
      ...r,
      ingredients: r.ingredients.filter((i) => String(i.name || "").trim()),
      steps: r.steps.filter((st) => String(st.text || "").trim()),
    };
    if (!recipe.id) delete recipe.id;
    m.busy = true;
    this._renderModal();
    try {
      const saved = await this._ws("middagsro/recipes/save", { recipe });
      this._modal = null;
      this._renderModal();
      this._recipesSub = "collection";
      this._say(r.id ? "Opskriften er gemt." : `${saved.name} er gemt i opskriftsamlingen.`);
      await this._load(true);
    } catch (err) {
      m.busy = false;
      m.error = err?.message || String(err);
      this._renderModal();
    }
  }

  // The days a recipe can be put on: the newest plan's, from today.
  _planTargets() {
    const today = localToday();
    const timeline = this._timeline();
    if (timeline) return timeline.filter((e) => e.day && e.date >= today).map((e) => ({ plan: e.plan, day: e.day }));
    const plan = this._state?.latest_plan;
    return plan ? plan.days.filter((d) => d.date >= today).map((day) => ({ plan, day })) : [];
  }

  async _recipeToPlan(arg) {
    const m = this._modal;
    const [planId, date] = String(arg).split("|");
    if (m?.kind !== "recipe" || !(m.recipe.id || m.recipe.rema_slug) || m.busy) return;
    m.busy = "plan";
    m.error = null;
    this._renderModal();
    try {
      if (m.recipe.id) await this._ws("middagsro/recipes/plan", { recipe_id: m.recipe.id, plan_id: planId, date });
      else await this._ws("middagsro/rema_recipes/plan", { slug: m.recipe.rema_slug, plan_id: planId, date });
      this._modal = null;
      this._renderModal();
      await this._load();
      this._say(`${m.recipe.name} er sat på madplanen ${dateLabel(date).toLowerCase()} – indkøbslisten er lavet om.`);
    } catch (err) {
      m.busy = false;
      m.error = err?.message || String(err);
      this._renderModal();
    }
  }

  // A recipe's items and REMA's products: which are bought and linked, and (suggest)
  // products for those that have none. Nothing is saved until the recipe is.
  async _rcLinks(m, suggest = false) {
    if (!this._hasPrices()) return;
    const token = (m.linksToken = (m.linksToken || 0) + 1);
    if (suggest) m.suggesting = true;
    if (this._modal === m) this._renderModal();
    try {
      const res = await this._ws("middagsro/recipes/links", { recipe: { ingredients: m.recipe.ingredients }, suggest });
      if (token !== m.linksToken) return;
      m.links = res;
      if (suggest) m.found = Object.fromEntries((res.suggestions || []).map((x) => [String(x.index), x]));
    } catch (err) {
      if (token !== m.linksToken) return;
      if (m.links === null) m.links = { ingredients: [], missing: 0, ready: false, failed: true };
    }
    m.suggesting = false;
    if (this._modal === m) this._renderModal();
  }

  _rcLinksSoon(m) {
    clearTimeout(this._rcLinksTimer);
    this._rcLinksTimer = setTimeout(() => this._modal === m && this._rcLinks(m), 500);
  }

  // Under the ingredients' heading: ready, or how many items still need a product.
  _rcLinkStatus(m) {
    if (!this._hasPrices()) return "";
    if (m.suggesting) return '<div class="banner info small"><span class="spinner small"></span> Finder REMA-varer til ingredienserne …</div>';
    if (!m.links || m.links.failed) return m.links === null ? '<p class="muted small"><span class="spinner small"></span> Tjekker varerne …</p>' : "";
    const rows = m.links.ingredients || [];
    const ings = m.recipe.ingredients;
    const missing = ings.filter((ing, i) => rows[i]?.bought && !ing.product && !ing.basic).length;
    if (!ings.length) return "";
    if (!missing) return '<div class="banner info small"><span class="badge ready">Klar</span> Alle varer, der skal købes, er koblet til en REMA-vare.</div>';
    const found = Object.values(m.found || {});
    const sure = found.filter((f) => f.product && f.confidence === "high" && !ings[f.index]?.product && !ings[f.index]?.basic).length;
    return `<div class="banner warn small"><div>${missing === 1 ? "1 ingrediens mangler" : `${missing} ingredienser mangler`} en REMA-vare. Kobl dem én gang, så indkøbslisten får de rigtige varer – eller tryk <i>Har vi altid</i> ved det, I ikke køber.</div>
      <div class="row wrap">${m.found ? "" : '<button class="btn small" data-action="rc-links-find">Find varer</button>'}${sure ? `<button class="btn small primary" data-action="rc-links-useall">Brug de sikre forslag (${sure})</button>` : ""}</div></div>`;
  }

  // One ingredient's product: linked (exact or of its kind), always in the house, or missing with suggestions.
  _rcIngLink(m, ing, i) {
    const row = m.links?.ingredients?.[i];
    const kind = row?.kind ? `<span class="muted">slags: ${esc(row.kind)}</span>` : "";
    if (ing.product) {
      return `<p class="muted small rc-prod">REMA: ${esc(ing.product.name)}${ing.product.underline ? ` · ${esc(ing.product.underline)}` : ""}${ing.basic ? " · basisvare" : ""}
        <button class="link small" data-action="rc-ing-unlink" data-arg="${i}">Fjern</button>
        ${this._hasPrices() ? `<label class="check inline small" title="Ellers må en anden vare af samme slags bruges, når den er på tilbud"><input type="checkbox" data-action="rc-ing-exact" data-arg="${i}" ${ing.exact ? "checked" : ""}> Altid præcis denne</label>` : ""}</p>`;
    }
    if (ing.basic) return `<p class="muted small rc-prod">Har I altid – købes ikke <button class="link small" data-action="rc-ing-unlink" data-arg="${i}">Fortryd</button></p>`;
    if (!row?.bought || !this._hasPrices()) return "";
    const f = m.found?.[String(i)];
    const others = (f?.alternatives || []).filter((a) => a.id !== f?.product?.id).slice(0, 3);
    return `<div class="small rc-prod rc-missing"><span class="badge doubt">Mangler vare</span> ${kind}
      ${f?.product ? `<span>Forslag: <b>${esc(f.product.name)}</b>${f.product.underline ? ` <span class="muted">${esc(f.product.underline)}</span>` : ""}</span>
        <button class="btn small" data-action="rc-ing-use" data-arg="${i}|${esc(f.product.id)}">Brug</button>` : f ? '<span class="muted">Intet sikkert forslag – skriv navnet om, eller søg ved at skrive i feltet.</span>' : ""}
      ${others.map((a) => `<button class="chip" data-action="rc-ing-use" data-arg="${i}|${esc(a.id)}">${esc(a.name)}${a.underline ? ` · ${esc(a.underline)}` : ""}</button>`).join("")}
      <button class="link small" data-action="rc-ing-basic" data-arg="${i}">Har vi altid</button></div>`;
  }

  _recipeModal(m) {
    if (m.loading) {
      return `<div class="scrim" data-action="modal-close"></div>
        <div class="dialog wide" role="dialog" aria-modal="true"><p><span class="spinner small"></span> Henter opskriften …</p></div>`;
    }
    const r = m.recipe;
    const busy = !!m.busy;
    const field = (name, value, attrs = "") =>
      `<input data-bind="rcp" data-field="${name}" value="${esc(value ?? "")}" ${attrs}>`;
    const ingredients = r.ingredients
      .map(
        (ing, i) => `<div class="rc-ing">
          <input type="text" class="amount" data-bind="rcp" data-list="ingredients" data-idx="${i}" data-field="amount" value="${esc(ing.amount)}" placeholder="Mængde">
          <input type="text" class="grow" data-bind="rcp" data-list="ingredients" data-idx="${i}" data-field="name" value="${esc(ing.name)}" placeholder="Ingrediens">
          <button class="icon-btn" data-action="rc-row" data-arg="ingredients|del|${i}" aria-label="Fjern ingrediens">${CLOSE_ICON}</button>
        </div>${this._rcIngLink(m, ing, i)}<div class="rc-sugg" data-idx="${i}"></div>`
      )
      .join("");
    const steps = r.steps
      .map(
        (st, i) => `<div class="rc-step">
          <span class="num">${i + 1}</span>
          <textarea class="grow" rows="2" data-bind="rcp" data-list="steps" data-idx="${i}" data-field="text" placeholder="Trin">${esc(st.text)}</textarea>
          <button class="icon-btn" data-action="rc-row" data-arg="steps|del|${i}" aria-label="Fjern trin">${CLOSE_ICON}</button>
        </div>`
      )
      .join("");
    const targets = m.picking
      ? `<div class="rc-targets">${this._planTargets()
          .map(
            ({ plan, day }) => `<button class="option" data-action="rc-plan-day" data-arg="${esc(plan.id)}|${esc(day.date)}" ${busy ? "disabled" : ""}>
              <b>${esc(dateLabel(day.date))}</b><span class="muted small">${esc(day.dish || "Ingen ret")}</span></button>`
          )
          .join("") || '<p class="muted">Der er ingen dage at sætte den på – lav en madplan først.</p>'}
          ${m.busy === "plan" ? '<p class="muted small"><span class="spinner small"></span> Finder varer og sætter retten på …</p>' : ""}</div>`
      : "";
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog wide sheet rc-sheet" role="dialog" aria-modal="true" aria-label="Opskrift">
        <div class="dialog-top rc-head">
          <input type="text" class="rc-name" data-bind="rcp" data-field="name" value="${esc(r.name)}" placeholder="Rettens navn">
          ${this._recipeRateButtons(r)}
          <button class="icon-btn close" data-action="modal-close" aria-label="Luk" ${busy ? "disabled" : ""}>${CLOSE_ICON}</button>
        </div>
        ${r.image ? `<img class="rc-photo" src="${esc(r.image)}" alt="">` : ""}
        ${r.rema_slug
          ? `<p class="muted small">Fra REMA 1000's opskrifter. Ingredienserne er koblet til REMA's varer, så indkøbslisten får de rigtige varer.${r.id ? "" : " <b>Gem</b> beholder jeres valg af varer på REMA-opskriften; <b>Gem i samlingen</b> gemmer den også i jeres opskriftsamling."}</p>`
          : m.imported ? `<p class="muted small">${m.recipe.source === "scan" ? "Læst fra billedet af AI'en – tjek mængder og trin" : m.recipe.source === "web" ? `Fra ${esc(m.recipe.site || "madsiden")}` : "Hentet fra linket"}. Ret det, der skal rettes, og gem den i opskriftsamlingen.</p>` : ""}
        ${m.recipe.url ? `<p class="muted small"><a href="${esc(m.recipe.url)}" target="_blank" rel="noopener">Se opskriften på ${esc(m.recipe.site || "siden")} ↗</a></p>` : ""}
        ${this._remaPick && r.rema_slug
          ? `<div class="banner info">Vælg den til ${esc(dateLabel(this._remaPick.date).toLowerCase())}?
              <button class="btn primary small" data-action="rr-pick" data-arg="${esc(r.rema_slug)}" ${busy ? "disabled" : ""}>${m.busy === "pick" ? '<span class="spinner small"></span> Sætter på …' : "Sæt på madplanen"}</button></div>`
          : ""}
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        ${r.favorite ? `<label class="field rc-freq">Favorit – hvor tit skal den på madplanen?
          <select data-bind="rcp" data-field="frequency">${["weekly", "biweekly", "monthly", "on_offer", "inspiration"].map((q) => `<option value="${q}" ${(r.frequency || "inspiration") === q ? "selected" : ""}>${FREQ_LABELS[q]}</option>`).join("")}</select></label>` : ""}
        <div class="grid rc-meta">
          <label class="field">Personer ${field("servings", r.servings, 'type="number" min="1" max="50"')}</label>
          <label class="field">Min. aktiv ${field("active_minutes", r.active_minutes, 'type="number" min="0" max="600"')}</label>
          <label class="field">Min. i alt ${field("total_minutes", r.total_minutes, 'type="number" min="0" max="1440"')}</label>
          <label class="field">Type
            <select data-bind="rcp" data-field="type">
              <option value="normal" ${r.type !== "vegetar" ? "selected" : ""}>Med kød/fisk</option>
              <option value="vegetar" ${r.type === "vegetar" ? "selected" : ""}>Vegetar</option>
            </select></label>
        </div>
        <h3>Ingredienser</h3>
        ${this._rcLinkStatus(m)}
        ${ingredients}
        <button class="btn small" data-action="rc-row" data-arg="ingredients|add">+ Ingrediens</button>
        <h3>Sådan gør du</h3>
        ${steps}
        <button class="btn small" data-action="rc-row" data-arg="steps|add">+ Trin</button>
        <label class="field">Tip <textarea rows="2" data-bind="rcp" data-field="tip">${esc(r.tip || "")}</textarea></label>
        ${targets}
        <div class="dialog-bottom wrap">
          <button class="btn primary" data-action="rc-save" ${busy ? "disabled" : ""}>${r.id ? "Gem" : "Gem i samlingen"}</button>
          ${r.rema_slug && !r.id ? `<button class="btn" data-action="rc-rema-save" ${busy ? "disabled" : ""} title="Gem varerne på REMA-opskriften, uden at den kommer i samlingen">Gem</button>` : ""}
          ${r.id || r.rema_slug ? `<button class="btn" data-action="rc-plan" ${busy ? "disabled" : ""}>${aiLabel("Tilføj til madplan")}</button>` : ""}
          ${r.id ? `<button class="btn danger" data-action="rc-delete" ${busy ? "disabled" : ""}>Slet</button>` : ""}
          <span class="spacer"></span>
          <button class="btn" data-action="modal-close" ${busy ? "disabled" : ""}>Luk</button>
        </div>
      </div>`;
  }

  _renderStatus() {
    const node = this.shadowRoot.querySelector("#status");
    if (node) node.innerHTML = this._statusHtml();
  }

  _defaultNavigation() {
    return { desktop: TABS.map(([key]) => key), mobile: [...PHONE_TABS] };
  }

  _readNavigation() {
    const defaults = this._defaultNavigation();
    try {
      const saved = JSON.parse(localStorage.getItem(NAV_STORAGE) || "null");
      const clean = values => Array.isArray(values) ? [...new Set(values.filter(key => TABS.some(([id]) => id === key)))] : [];
      const desktop = clean(saved?.desktop), mobile = clean(saved?.mobile);
      // Forside (3.0) is new: it joins a saved menu, and the old phone default becomes the new one.
      if (desktop.length && !desktop.includes("home")) desktop.unshift("home");
      const oldPhone = mobile.length === 4 && mobile.every((key, i) => key === OLD_PHONE_TABS[i]);
      return { desktop: desktop.length ? desktop : defaults.desktop, mobile: mobile.length === 4 && !oldPhone ? mobile : defaults.mobile };
    } catch { return defaults; }
  }

  _renderNavigation() {
    const nav = this.shadowRoot.querySelector("nav.tabs");
    if (!nav) return;
    const signature = JSON.stringify(this._navigation);
    if (nav.dataset.signature === signature) return;
    const { desktop, mobile } = this._navigation;
    const classes = key => `${desktop.includes(key) ? " desktop-primary" : ""}${mobile.includes(key) ? " mobile-primary" : ""}`;
    const style = key => `--desktop-order:${desktop.indexOf(key)};--mobile-order:${mobile.indexOf(key)}`;
    nav.innerHTML = TABS.map(([key, label]) => `<button class="tab${classes(key)}" style="${style(key)}" data-action="tab" data-arg="${key}">${TAB_ICONS[key] || ""}<span>${label}</span></button>`).join("")
      + `<button class="tab more ${desktop.length === TABS.length ? "no-desktop-extra" : ""}" data-action="more" aria-expanded="false"></button><button class="tab customize" data-action="nav-open">Tilpas menu</button>`;
    this.shadowRoot.querySelector(".more-sheet").innerHTML = `<div class="ms-grab"></div><div class="ms-top"><h2>Mere</h2><button class="ms-x" data-action="more" aria-label="Luk">×</button></div><div class="more-grid">${TABS.map(([key, label]) => `<button class="more-item mg${classes(key)}" data-action="tab" data-arg="${key}"><span class="st-ic">${TAB_ICONS[key] || ""}</span><b>${label}</b></button>`).join("")}</div>`
      + '<button class="ms-custom" data-action="nav-open">Tilpas menu</button>';
    nav.dataset.signature = signature;
  }

  _navigationModal() {
    const m = this._modal;
    const section = (screen, title, help) => {
      const selected = m.draft[screen];
      const ordered = [...selected, ...TABS.map(([key]) => key).filter(key => !selected.includes(key))];
      return `<section><h3>${title}</h3><p class="muted small">${help}</p>${ordered.map(key => {
        const index = selected.indexOf(key), checked = index >= 0;
        const label = TABS.find(([id]) => id === key)[1];
        return `<div class="nav-option"><label class="check"><input type="checkbox" data-bind="navigation" data-screen="${screen}" data-key="${key}" ${checked ? "checked" : ""} ${screen === "mobile" && !checked && selected.length >= 4 ? "disabled" : ""}>${label}</label>${checked ? `<button class="btn small" data-action="nav-move" data-arg="${screen}|${key}|-1" aria-label="Flyt ${label} op på ${screen === "mobile" ? "telefon" : "computer"}" ${index === 0 ? "disabled" : ""}>↑</button><button class="btn small" data-action="nav-move" data-arg="${screen}|${key}|1" aria-label="Flyt ${label} ned på ${screen === "mobile" ? "telefon" : "computer"}" ${index === selected.length - 1 ? "disabled" : ""}>↓</button>` : ""}</div>`;
      }).join("")}</section>`;
    };
    return `<div class="scrim" data-action="modal-close"></div><div class="dialog wide" role="dialog" aria-modal="true" aria-label="Tilpas menu"><div class="dialog-top"><h2>Tilpas menu</h2><button class="btn" data-action="modal-close">Luk</button></div><p>Vælg genveje og rækkefølge. Alle andre sider kan stadig åbnes under “Mere”. Valgene gemmes i denne browser.</p>${`<div class="seg fit"><button data-action="nav-screen" data-arg="desktop" class="${m.screen === "desktop" ? "active" : ""}">Computer</button><button data-action="nav-screen" data-arg="mobile" class="${m.screen === "mobile" ? "active" : ""}">Telefon</button></div>`}${m.screen === "mobile" ? section("mobile", `Telefon · ${m.draft.mobile.length} af 4 valgt`, "Vælg præcis fire. Fjern et flueben for at vælge et andet punkt.") : section("desktop", "Computer", "Vælg mindst ét menupunkt.")}<div class="dialog-bottom wrap"><button class="btn primary" data-action="nav-save" ${m.draft.mobile.length !== 4 || !m.draft.desktop.length ? "disabled" : ""}>Gem menu</button><button class="btn" data-action="nav-reset">Gendan standard</button><button class="btn" data-action="modal-close">Annuller</button></div></div>`;
  }

  _saveNavigation() {
    const draft = this._modal?.draft;
    if (!draft || !draft.desktop.length || draft.mobile.length !== 4) return;
    this._navigation = { desktop: [...draft.desktop], mobile: [...draft.mobile] };
    let message = "Menuen er gemt i denne browser.";
    try { localStorage.setItem(NAV_STORAGE, JSON.stringify(this._navigation)); }
    catch { message = "Menuen er ændret, men browseren kunne ikke gemme den til næste besøg."; }
    this._modal = null;
    this._render();
    this._renderModal();
    this._say(message);
  }

  _storeChooser() {
    const stores = this._state?.stores || [];
    if (stores.length < 2) return "";
    const pref = this._state.store_switch_preference;
    return `<div class="store-chooser"><label class="field">Vi handler i
      <select data-bind="store-choice" aria-label="Vælg butik" ${this._busy ? "disabled" : ""}>
      ${stores.map(store => `<option value="${esc(store.entry_id)}" ${store.entry_id === this._state.entry_id ? "selected" : ""}>${esc(store.name)}${store.pickup ? ` · ${esc(store.pickup)}` : ""}</option>`).join("")}</select></label>
      <div class="muted small">Vælg mellem jeres tilføjede butikker. Kurven ændres først, når du sender varer.
      ${pref && pref !== "ask" ? `<br>${pref === "copy" ? "Madplanen følger med ved skift." : "Et butiksskift åbner en ny madplan."} <button class="link" data-action="store-switch-ask">Spørg mig igen</button>` : ""}</div></div>`;
  }

  _openStoreSwitch(target) {
    if (this._busy || target === this._state.entry_id) return;
    if (this._dirty) return this._say("Gem eller fortryd dine indstillingsændringer, før du skifter butik.");
    if (Object.values(this._timers || {}).some(end => end > Date.now())) return this._say("Afslut madlavningens timere, før du skifter butik.");
    const store = this._state.stores.find(store => store.entry_id === target);
    if (!store) return;
    const pref = this._state.store_switch_preference;
    if (pref === "new" || (pref === "copy" && this._plan)) return this._performStoreSwitch(target, pref, true);
    this._modal = { kind: "store-switch", target, name: store.name, remember: false, busy: false };
    this._renderModal();
  }

  _storeSwitchModal(modal) {
    return `<div class="scrim" ${modal.busy ? "" : 'data-action="modal-close"'}></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-label="Skift butik">
      <h2>Skift til ${esc(modal.name)}</h2>
      <p>Vil du tage madplanen med eller starte en ny til denne butik?</p>
      <div class="store-switch-actions">
        <button class="btn primary" data-action="store-switch-copy" ${modal.busy || !this._plan ? "disabled" : ""}>Tag madplanen med</button>
        <p class="muted small">Opskrifterne beholdes, og vi finder den nye butiks varer og priser. Allerede sendte varer sendes ikke igen.</p>
        <button class="btn" data-action="store-switch-new" ${modal.busy ? "disabled" : ""}>Start en ny madplan</button>
        <p class="muted small">Du vælger selv startdag og laver planen bagefter. Tidligere planer bliver i historikken.</p>
      </div>
      <p class="muted small">Familie, allergier, basisvarer og madønsker følger med. Øvrige butiksindstillinger beholdes. Skiftet gælder også Middagsros dashboardkort.</p>
      <label class="check"><input type="checkbox" data-bind="remember-store-switch" ${modal.remember ? "checked" : ""} ${modal.busy ? "disabled" : ""}> Husk valget ved fremtidige butiksskift</label>
      <p class="muted small">Du kan altid vælge “Spørg mig igen”.</p>
      <div class="dialog-bottom"><button class="btn" data-action="modal-close" ${modal.busy ? "disabled" : ""}>Annullér</button>${modal.busy ? '<span class="spinner small"></span><span>Skifter butik …</span>' : ""}</div></div>`;
  }

  async _performStoreSwitch(target, action, remember) {
    this._busy = true;
    if (this._modal) this._modal.busy = true;
    this._renderModal();
    this._renderBusy();
    try {
      await this._ws("middagsro/store/switch", { target_entry_id: target, action, remember: !!remember, plan_id: action === "copy" ? this._plan?.id || null : null });
      location.reload();
    } catch (err) {
      this._busy = false;
      if (this._modal) this._modal.busy = false;
      this._renderModal();
      this._renderBusy();
      this._say(`Butikken kunne ikke skiftes: ${err?.message || err}`);
    }
  }

  _statusHtml() {
    const status = this._state?.status;
    if (!status) return "";
    if (status.state === "generating") {
      return `<div class="banner info"><span class="spinner"></span>${esc(status.message || "Laver madplan …")}</div>`;
    }
    if (status.state === "error") {
      return `<div class="banner error"><b>Madplanen kunne ikke laves:</b> ${esc(status.message)}</div>`;
    }
    return "";
  }

  _render() {
    const state = this._state;
    let body;
    if (this._error && !state) {
      body = `<div class="card"><h2>Middagsro kunne ikke indlæses</h2><p>${esc(this._error)}</p>
        <button class="btn" data-action="refresh">Prøv igen</button></div>`;
    } else if (!state) {
      body = `<div class="card center"><span class="spinner"></span> Indlæser …</div>`;
    } else {
      try {
        body = {
          home: () => this._homeView(),
          plan: () => this._planView(),
          recipes: () => this._recipesView(),
          shopping: () => this._shoppingView(),
          favorites: () => this._favoritesView(),
          budget: () => this._budgetView(),
          inventory: () => `${this._v3PantryArt()}${this._inventoryCard(true)}`,
          health: () => this._healthView(),
          history: () => this._historyView(),
          settings: () => this._settingsView(),
        }[this._tab]();
        if ((this._tab === "plan" || this._tab === "shopping") && this._chain) body = this._chainView();
        if (this._tab === "plan") body += CREDIT;
      } catch (err) {
        // One odd field must not blank the whole panel.
        console.error("Middagsro: the page could not be drawn", err);
        body = `<div class="card"><h2>Siden kunne ikke vises</h2><p class="muted">${esc(err?.message || String(err))}</p>
          <div class="row wrap"><button class="btn" data-action="refresh">Prøv igen</button>
          <button class="btn" data-action="tab" data-arg="plan">Til madplanen</button></div></div>`;
      }
    }
    const root = this.shadowRoot;
    // The toolbar and tabs are built once, so their horizontal scroll survives.
    if (!root.querySelector("#content")) {
      root.innerHTML = `
        <style>${STYLE}</style>
        <div id="top"></div>
        <div class="v3 hdr-host"><header class="hdr small" id="hdr">
        <div class="scene-wrap" id="scene" aria-hidden="true"></div>
        <div class="toolbar">
          <ha-menu-button></ha-menu-button>
          <span class="brand" data-action="tab" data-arg="home" role="button" tabindex="0" aria-label="Forside"><img class="logo" src="${this._img("icon.svg")}" alt=""><span class="wordmark">Middagsro</span></span>
          <span class="spacer"></span>
          <span id="timerchip" class="timer-chip" data-action="tab" data-arg="recipes"></span>
          <span id="busy"></span>
          <span class="prof-wrap"><button class="prof" data-action="prof" aria-haspopup="menu" aria-expanded="false" aria-label="Profil og indstillinger"></button>
            <span class="prof-menu" role="menu" hidden>
              <button role="menuitem" data-action="settings-open" data-arg="">${TAB_ICONS.settings || ""}<span>Indstillinger</span></button>
              <button role="menuitem" data-action="settings-open" data-arg="messages">${BELL_ICON}<span>Beskeder</span></button>
              <button role="menuitem" data-action="settings-open" data-arg="look">${SETTING_ICONS.look}<span>Udseende</span></button>
            </span></span>
        </div>
        <div id="hdr-body"></div>
        <nav class="tabs" aria-label="Middagsro"></nav>
        </header></div>
        <div class="more-scrim" data-action="more" hidden></div>
        <div class="more-sheet" hidden></div>
        <main id="content"></main>
        <div id="modal"></div>
        <div id="toast" role="status" aria-live="polite"></div>`;
    }
    this._renderNavigation();
    const prof = root.querySelector(".prof");
    if (prof) prof.textContent = String(this._hass?.user?.name || "?").trim().charAt(0).toUpperCase();
    const menu = root.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    root.querySelectorAll(".tab, .more-item").forEach((tab) => tab.classList.toggle("active", tab.dataset.arg === this._tab));
    const more = root.querySelector(".tab.more");
    if (more) {
      more.classList.toggle("active", this._moreOpen || !this._navigation[matchMedia("(max-width: 700px)").matches ? "mobile" : "desktop"].includes(this._tab));
      more.setAttribute("aria-expanded", String(!!this._moreOpen));
      const phoneNav = matchMedia("(max-width: 700px)").matches;
      const inMore = !this._navigation[phoneNav ? "mobile" : "desktop"].includes(this._tab);
      more.innerHTML = this._moreOpen ? `${CLOSE_ICON}<span>Luk</span>` : `${MORE_ICON}<span>${inMore ? TABS.find(([k]) => k === this._tab)?.[1] || "Mere" : "Mere"}</span>`;
    }
    for (const sel of [".more-sheet", ".more-scrim"]) {
      const el = root.querySelector(sel);
      if (el) el.hidden = !this._moreOpen;
    }
    this._renderBusy();
    const oldChips = root.querySelector(".chips");
    const chipsLeft = oldChips ? oldChips.scrollLeft : 0;
    // The field being typed in keeps focus, caret and the phone's keyboard across the redraw.
    const focused = root.activeElement;
    const keep =
      focused && root.querySelector("#content")?.contains(focused) && focused.matches("input, textarea, select")
        ? { key: this._fieldKey(focused), start: focused.selectionStart, end: focused.selectionEnd, scroll: focused.scrollTop }
        : null;
    root.querySelector("#content").innerHTML = `<div id="status">${this._statusHtml()}</div>${body}`;
    this._renderToast();
    try { this._v3Header(); this._v3After(); } catch (err) { console.error("Middagsro: the header could not be drawn", err); }
    if (keep?.key) {
      const again = [...root.querySelectorAll("#content input, #content textarea, #content select")].find((el) => this._fieldKey(el) === keep.key);
      if (again) {
        again.focus({ preventScroll: true });
        try {
          if (keep.start !== null && keep.start !== undefined && again.setSelectionRange) again.setSelectionRange(keep.start, keep.end);
          again.scrollTop = keep.scroll;
        } catch (err) {
          /* a field without a caret */
        }
      }
    }
    const chips = root.querySelector(".chips");
    if (chips) chips.scrollLeft = chipsLeft;
    this._keepVisible(root.querySelector(".tabs"), root.querySelector(".tab.active"));
    this._keepVisible(chips, chips?.querySelector(".chip.active"));
    this._tickTimers();
  }

  // A list is redrawn a moment after the last keystroke, not on every one.
  _soon(key, fn, ms = 120) {
    this._soonTimers ||= {};
    clearTimeout(this._soonTimers[key]);
    this._soonTimers[key] = setTimeout(fn, ms);
  }

  // What makes a field the same field after a redraw.
  _fieldKey(el) {
    const ds = el.dataset;
    return [ds.bind, ds.path, ds.list, ds.field, ds.idx, ds.part, el.name, el.id].map((v) => v ?? "").join("|") || null;
  }

  // The popup lives outside #content, so polling while a plan is made doesn't
  // redraw it under the user's fingers.
  _renderModal() {
    const node = this.shadowRoot.querySelector("#modal");
    if (!node) return;
    if (this._modal?.kind === "navigation") { node.innerHTML = this._navigationModal(); return; }
    if (this._modal?.kind === "inventory-consume") {
      const m = this._modal;
      const items = m.group?.items || m.plan?.freezer_used || [];
      node.innerHTML = `<div class="scrim" data-action="modal-close"></div><div class="dialog" role="dialog" aria-modal="true" aria-label="Bekræft råvarer brugt"><h2>${m.group?.day_id ? "Er retten lavet?" : "Er råvarerne brugt?"}</h2>${m.group ? `<p><b>${esc(m.group.dish)}</b></p>` : ""}<p>Markér de råvarer fra lageret, du faktisk brugte. Fjern fluebenet, hvis du brugte noget andet. Kun de markerede mængder trækkes fra.</p>${items.map(i => `<label class="check"><input type="checkbox" data-bind="inventory-used" data-id="${esc(i.id)}" ${m.selected.has(i.id) ? "checked" : ""}>${esc(i.name)} · ${i.amount} ${esc(i.unit)}</label>`).join("")}<div class="row wrap"><button class="btn primary" data-action="inventory-consume" ${this._busy ? "disabled" : ""}>Bekræft forbrug</button><button class="btn" data-action="modal-close">Ikke nu</button></div></div>`;
      return;
    }
    if (this._modal?.kind === "store-switch") {
      node.innerHTML = this._storeSwitchModal(this._modal);
      return;
    }
    if (this._modal?.kind === "notice") {
      node.innerHTML = `<div class="scrim" data-action="notice-close"></div>
        <div class="dialog" role="dialog" aria-modal="true" aria-label="Nyt i Middagsro">
          <div class="dialog-top"><h2>Nyt: vælg selv butik</h2>
            <button class="icon-btn close" data-action="notice-close" aria-label="Luk">${CLOSE_ICON}</button></div>
          <p>Middagsro kan nu også bruges uden REMA 1000 – med Netto, føtex, Lidl, Bilka, 365discount, MENY, Coop og flere. Så bygges madplanen på den butiks tilbudsavis, og indkøbslisten ligger i Home Assistant.</p>
          <p><b>I handler i REMA 1000, og alt virker som før.</b> Der er intet, I skal gøre.</p>
          <p class="muted small">Vil I skifte: Indstillinger › Enheder og tjenester › Middagsro › ⋮ › Omkonfigurér. Madplaner, opskrifter og indstillinger beholdes.</p>
          <div class="row wrap dialog-actions">
            <button class="btn primary" data-action="notice-close">OK</button>
            <button class="btn" data-action="notice-close" data-arg="shop">Læs mere</button>
          </div>
        </div>`;
      return;
    }
    if (this._modal?.kind === "day") {
      node.innerHTML = this._dayModal(this._modal);
      return;
    }
    if (this._modal?.kind === "v3-bon") {
      node.innerHTML = this._v3BonModal(this._modal);
      return;
    }
    if (this._modal?.kind === "v3-xfer") {
      node.innerHTML = this._v3XferModal(this._modal);
      return;
    }
    if (this._modal?.kind === "pantry") {
      node.innerHTML = this._pantryModal(this._modal);
      return;
    }
    if (this._modal?.kind === "purchase") {
      node.innerHTML = this._purchaseModal(this._modal);
      return;
    }
    if (this._modal?.kind === "where") {
      const e = this._everywhere;
      node.innerHTML = `<div class="scrim" data-action="modal-close"></div>
        <div class="dialog wide sheet" role="dialog" aria-modal="true" aria-label="Priser">
          <div class="dialog-top"><h2>${esc(this._modal.title)}</h2>
            <button class="icon-btn close" data-action="modal-close" aria-label="Luk">${CLOSE_ICON}</button></div>
          <div class="row wrap everywhere">
            <input class="grow" type="search" data-bind="everywhere" value="${esc(e.query)}" placeholder="Søg på en vare">
            <button class="btn" data-action="everywhere" ${e.loading ? "disabled" : ""}>${e.loading ? '<span class="spinner small"></span>' : "Søg"}</button>
            ${clearBtn("everywhere")}
          </div>
          ${this._matchHtml(this._modal)}
          <div class="ev-out">${e.error ? `<div class="banner error">${esc(e.error)}</div>` : ""}
          ${e.loading && !e.data ? '<p class="muted"><span class="spinner small"></span> Finder priserne …</p>' : e.data ? this._everywhereHtml(e.data) : ""}</div>
          <div class="dialog-bottom"><button class="btn" data-action="modal-close">Luk</button></div>
        </div>`;
      return;
    }
    if (this._modal?.kind === "recipe") {
      const rm = this._modal;
      if (rm.links === undefined && !rm.loading && this._hasPrices()) {
        // Which items are linked; a recipe not in the collection yet gets suggestions.
        rm.links = null;
        queueMicrotask(() => this._rcLinks(rm, !rm.recipe.id));
      }
      // Keep the scroll position when rows are added or removed.
      const top = node.querySelector(".dialog")?.scrollTop || 0;
      node.innerHTML = this._recipeModal(this._modal);
      const dialog = node.querySelector(".dialog");
      if (dialog) dialog.scrollTop = top;
      return;
    }
    if (this._modal?.kind === "line") {
      node.innerHTML = this._lineModal(this._modal);
      return;
    }
    if (this._modal?.kind === "pick") {
      const keep = node.querySelector("input[data-bind=pickq]") === this.shadowRoot.activeElement;
      node.innerHTML = this._pickModal(this._modal);
      if (keep) node.querySelector("input[data-bind=pickq]")?.focus();
      return;
    }
    if (!this._noteOpen) {
      node.innerHTML = "";
      return;
    }
    const busy = this._busy || this._state?.status?.state === "generating";
    node.innerHTML = `
      <div class="scrim" data-action="note-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="note-title">
        <h2 id="note-title">Ønsker til madplanen</h2>
        <p class="muted small">Bruges kun i den næste madplan og fjernes derefter. Fx varer i køleskabet, der skal bruges inden en dato, eller en bestemt ret på en bestemt dag.</p>
        <textarea id="note-text" data-bind="note" rows="5" maxlength="1000"
          placeholder="Fx: Fløde og 500 g hakket kylling skal bruges inden tirsdag. Pizza fredag.">${esc(this._noteDraft)}</textarea>
        <div class="row wrap dialog-actions">
          <button class="btn primary" data-action="note-generate" ${busy ? "disabled" : ""}>${aiLabel("Gem og lav madplan")}</button>
          <button class="btn" data-action="note-save">Gem</button>
          ${this._micButton("note")}
          ${this._state?.note ? '<button class="btn danger" data-action="note-clear">Fjern</button>' : ""}
          <span class="spacer"></span>
          <button class="btn" data-action="note-close">Annullér</button>
        </div>
      </div>`;
  }

  // "Gem i Mealie" for the plan's own recipes, "Åbn i Mealie" for the family's.
  _mealieButton(planId, date) {
    const mealie = this._state?.mealie;
    if (!mealie?.available) return "";
    const plan = this._planOf(planId);
    let day = plan?.days.find((d) => d.date === date);
    if (day?.uses_leftovers_from) day = plan.days.find((d) => d.date === day.uses_leftovers_from) || day;
    if (!day?.dish) return "";
    if (day.mealie) {
      return mealie.url
        ? `<a class="btn" href="${esc(`${mealie.recipes || `${mealie.url}/g/home/r/`}${encodeURIComponent(day.mealie)}`)}" target="_blank" rel="noopener">Åbn i Mealie</a>`
        : "";
    }
    if (!day.steps?.length) return "";
    return `<button class="btn" data-action="mealie-save" data-arg="${esc(planId)}|${esc(day.date)}" ${this._busy ? "disabled" : ""}>Gem i Mealie</button>`;
  }

  _dayModal(m) {
    const busy = !!m.busy;
    const dis = busy ? "disabled" : "";
    const plan = this._planOf(m.planId);
    const food = m.food ? plan?.days.find((d) => d.date === m.food) : null;
    const foodName = food ? `${dateLabel(food.date).split(" ")[0].toLowerCase()}ens ${food.dish}` : "";
    const options = (m.options || [])
      .map(
        (o, i) => `<button class="option" data-action="swap-pick" data-arg="${i}" ${dis}>
          <span class="option-dish"><b>${esc(o.dish)}</b>${o.type === "vegetar" ? ' <span class="badge eco">Vegetar</span>' : ""}${o.mealie ? ' <span class="badge mealie">Mealie</span>' : ""}</span>
          ${o.why ? `<span class="muted small">${esc(o.why)}</span>` : ""}
          <span class="muted small">${o.active_minutes ? `${o.active_minutes} min aktiv` : ""}${o.total_minutes ? ` · ${o.total_minutes} min i alt` : ""}</span>
          ${m.busy === "swap" && m.picked === i ? '<span class="muted small"><span class="spinner small"></span> Finder varer og skriver opskriften …</span>' : ""}
        </button>`
      )
      .join("");
    if (m.options) {
      const forFood = m.mode === "source" && food;
      return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="day-title">
        <h2 id="day-title">${forFood ? `Ny ret ${esc(dateLabel(food.date).toLowerCase())}` : `Ret til ${esc(dateLabel(m.date).toLowerCase())}`}</h2>
        <p class="muted small">${forFood ? `Erstatter ${esc(food.dish)} – resterne ${esc(dateLabel(m.date).toLowerCase())} følger med.` : m.leftovers ? `Laves ${esc(dateLabel(m.date).toLowerCase())} i stedet for resterne.` : "Vælg en ret. Indkøbslisten og opskriften bliver lavet om."}</p>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        <div class="options">${options}</div>
        <div class="row wrap dialog-actions">
          <button class="btn" data-action="swap-options" ${dis}>
            ${m.busy === "options" ? '<span class="spinner small"></span> Finder andre retter …' : aiLabel("Tre nye forslag")}</button>
          <span class="spacer"></span>
          <button class="btn" data-action="day-section" data-arg="dish" ${dis}>Tilbage</button>
        </div>
      </div>`;
    }
    const sections = [["dish", "Ret"], ["rest", "Restedag"], ["text", "Ingen madlavning"], ["skip", "Spring over"]];
    const seg = `<div class="seg fit day-kinds" role="tablist" aria-label="Hvad er dagen">${sections
      .map(([k, l]) => `<button role="tab" class="${m.section === k ? "active" : ""}" aria-selected="${m.section === k}" data-action="day-section" data-arg="${k}" ${dis}>${l}</button>`)
      .join("")}</div>`;
    let body = "";
    if (m.section === "dish") {
      body = `${m.leftovers && food ? `<div class="banner info small"><div>Dagen er rester af ${esc(foodName)}. Vælger du en ret her, laves den ${esc(dateLabel(m.date).toLowerCase())}, og ${esc(food.dish)} laves i én portion.
          <div class="row wrap"><button class="btn small" data-action="day-source-swap" ${dis}>${m.busy === "options" && m.mode === "source" ? '<span class="spinner small"></span> Finder retter …' : `Skift ${esc(food.dish)} i stedet`}</button></div></div></div>` : ""}
        ${m.newDish ? `<div class="banner warn small"><div>En ny ret, der ikke var blandt ugens opskrifter. Godkend den, så kommer den i opskriftsamlingen, og listen kan sendes – eller skift den ud.
          <div class="row wrap"><button class="btn primary small" data-action="day-approve" ${dis}>Godkend retten</button></div></div></div>` : ""}
        <div class="row wrap">
          <button class="btn primary" data-action="swap-options" ${dis}>
            ${m.busy === "options" && m.mode !== "source" ? '<span class="spinner small"></span> Finder retter …' : aiLabel(m.dish && !m.leftovers && !m.written ? "Skift retten – tre forslag" : "Find en ret – tre forslag")}</button>
          <button class="btn" data-action="day-pick" ${dis}>Vælg i opskrifter</button>
        </div>
        <label class="check"><input type="checkbox" data-action="day-veg" ${m.vegetarian ? "checked" : ""} ${dis}> Kun vegetarretter</label>
        <label class="field">Skriv selv en ret
          <input type="text" data-bind="daytext" value="${esc(m.written ? "" : m.text || "")}" maxlength="120" placeholder="Fx Tacos" enterkeyhint="done"></label>
        <div class="row wrap">
          <button class="btn" data-action="day-own-dish" ${dis} title="AI'en skriver rettens varer på indkøbslisten og laver opskriften">${m.busy === "own" ? '<span class="spinner small"></span> Finder varer …' : aiLabel("Køb ind til retten")}</button>
        </div>
        ${this._v3MoveRow(m)}
        ${m.dish && !m.written && !m.leftovers ? `<div class="row wrap dialog-actions">
          <button class="btn" data-action="day-recipe" ${dis}>Se opskriften</button>
          ${this._mealieButton(m.planId, m.date)}
          <span class="spacer"></span>
          <button class="btn danger" data-action="day-clear" data-arg="delete" ${dis}>Slet retten</button></div>` : ""}`;
    } else if (m.section === "rest") {
      const foods = this._foodDays(plan, m.date);
      body = foods.length
        ? `<p class="muted small">Dagen spiser resten af en tidligere ret. Den ret laves i dobbelt portion – opskriften og indkøbslisten bliver rettet${m.dish && !m.leftovers && !m.written ? `, og ${esc(m.dish)} med dens egne varer fjernes` : ""}.</p>
          <label class="field">Rester af
            <select data-bind="daysource">${foods
              .map((d) => `<option value="${esc(d.date)}" ${d.date === (m.source || foods[foods.length - 1].date) ? "selected" : ""}>${esc(dateLabel(d.date))}: ${esc(d.dish)}</option>`)
              .join("")}</select></label>
          <div class="row wrap dialog-actions">
            ${m.leftovers ? `<button class="btn" data-action="day-recipe" ${dis}>Se opskriften</button>` : ""}
            <span class="spacer"></span>
            <button class="btn primary" data-action="day-leftovers" ${dis}>${m.busy === "rest" ? '<span class="spinner small"></span> Retter madplanen …' : m.leftovers ? "Gem" : "Gør til restedag"}</button>
          </div>`
        : '<p class="muted">Der er ingen ret før denne dag at spise rester af. Flyt dagen, eller vælg en ret til en tidligere dag først.</p>';
    } else if (m.section === "text") {
      const chips = ["Spiser ude", "Take-away", "Rugbrødsdag", "Skolefest"]
        .map((t) => `<button class="chip ${m.text === t ? "active" : ""}" data-action="day-chip" data-arg="${esc(t)}" ${dis}>${esc(t)}</button>`)
        .join("");
      body = `<p class="muted small">Der laves ingen aftensmad, og der købes ikke ind til dagen${m.dish && !m.written && !m.leftovers ? ` – ${esc(m.dish)} og dens egne varer fjernes` : ""}.</p>
        <div class="row wrap chips">${chips}</div>
        <label class="field">Hvad sker der
          <input type="text" data-bind="daytext" value="${esc(m.text || "")}" maxlength="120" placeholder="Fx Spiser ude" enterkeyhint="done"></label>
        <div class="row wrap dialog-actions">
          ${m.written ? `<button class="btn danger" data-action="day-clear" data-arg="delete" ${dis}>Fjern teksten</button>` : ""}
          <span class="spacer"></span>
          <button class="btn primary" data-action="day-text" ${dis}>${m.written ? "Gem teksten" : "Ingen madlavning"}</button>
        </div>`;
    } else if (m.skipped) {
      body = `<p class="muted small">Dagen springes over: ingen aftensmad, og der købes ikke ind til den. Vælg en af de andre muligheder ovenfor, eller tag dagen tilbage, som den var.</p>
        <div class="row wrap dialog-actions"><span class="spacer"></span>
          <button class="btn primary" data-action="day-back" ${dis}>${m.busy === "back" ? '<span class="spinner small"></span> Tager dagen tilbage …' : "Tag dagen tilbage"}</button></div>`;
    } else {
      body = `<p class="muted small">Dagen tages ud af madplanen: ingen aftensmad, og ${m.dish && !m.written && !m.leftovers ? `${esc(m.dish)}s egne varer fjernes fra indkøbslisten` : "der købes ikke ind til den"}. Du kan tage den tilbage under madplanen.</p>
        <div class="row wrap dialog-actions"><span class="spacer"></span>
          <button class="btn danger" data-action="day-clear" data-arg="skip" ${dis}>Spring dagen over</button></div>`;
    }
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="day-title">
        <div class="dialog-top day-hero">${V3.dishArt(m.skipped ? "" : m.dish, "dlg-art")}<div><h2 id="day-title">${esc(m.skipped ? "Springes over" : m.dish || "Ingen ret")}</h2>
          <p class="muted">${esc(dateLabel(m.date))}</p></div>
          <button class="icon-btn close" data-action="modal-close" aria-label="Luk" ${dis}>${CLOSE_ICON}</button></div>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        ${seg}
        ${m.busy === "back" && m.section !== "skip" ? '<p class="muted"><span class="spinner small"></span> Tager dagen tilbage …</p>' : body}
      </div>`;
  }

  // Choose the dish for a day of the next plan: the collection, REMA's recipes or Mealie.
  async _pickLoad(source) {
    const m = this._modal;
    if (m?.kind !== "pick") return;
    m[source] = { loading: true, recipes: m[source]?.recipes || [] };
    this._renderModal();
    try {
      const data =
        source === "rema"
          ? await this._ws("middagsro/rema_recipes/list", m.query.trim() ? { query: m.query.trim() } : {})
          : await this._ws("middagsro/mealie/recipes");
      if (this._modal === m) m[source] = { loading: false, recipes: data.recipes || [] };
    } catch (err) {
      if (this._modal === m) m[source] = { loading: false, recipes: [], error: err?.message || String(err) };
    }
    if (this._modal === m) this._renderModal();
  }

  _pickModal(m) {
    const query = m.query.trim().toLowerCase();
    const tabs = [["collection", '<span class="wide">Opskriftsamling</span><span class="narrow">Samling</span>']];
    if (this._isRema()) tabs.push(["rema", 'REMA<span class="wide">-opskrifter</span>']);
    if (this._state.mealie?.available) tabs.push(["mealie", "Mealie"]);
    if ((this._state.settings.recipe_sites || []).length && !m.target) tabs.push(["sites", "Madsider"]);
    const row = (source, id, name, meta) => `<li class="pick-row"><div class="what"><b>${esc(name)}</b>${meta ? `<span class="muted small">${esc(meta)}</span>` : ""}</div>
      <button class="btn small primary" data-action="pick-choose" data-arg="${source}|${esc(id)}">Vælg</button></li>`;
    let body = "";
    if (m.tab === "collection") {
      const list = (this._state.recipes || [])
        .filter((r) => r.rating !== "dislike" && (!query || r.name.toLowerCase().includes(query)))
        .sort((a, b) => Number(!!b.favorite) - Number(!!a.favorite) || a.name.localeCompare(b.name, "da"));
      body = list.length
        ? `<ul class="lines">${list.map((r) => row("collection", r.id, `${r.favorite ? "❤️ " : ""}${r.name}`, r.total_minutes ? `${r.total_minutes} min` : "")).join("")}</ul>`
        : '<p class="muted">Ingen opskrifter i samlingen passer. Gem retter med 👍 eller ❤️, så kommer de her.</p>';
    } else if (m.tab === "sites") {
      const data = m.sites || {};
      body = data.loading
        ? '<p class="muted"><span class="spinner small"></span> Søger på madsiderne …</p>'
        : data.error
          ? `<div class="banner error">${esc(data.error)}</div>`
          : (data.results || []).length
            ? `<ul class="lines">${data.results.map((r) => row("web", r.url, r.title, r.site_name)).join("")}</ul>`
            : `<p class="muted">${data.searched ? "Ingen opskrifter fundet." : "Søg efter en ret på jeres madsider."}</p>`;
    } else {
      const data = m[m.tab];
      const list = (data?.recipes || []).filter(
        (r) => m.tab === "rema" || !query || r.name.toLowerCase().includes(query)
      );
      body = data?.loading && !list.length
        ? '<p class="muted"><span class="spinner small"></span> Henter opskrifter …</p>'
        : data?.error
          ? `<div class="banner error">${esc(data.error)}</div>`
          : list.length
            ? `<ul class="lines">${list
                .map((r) =>
                  m.tab === "rema"
                    ? row("rema", r.slug, r.title, [r.total_minutes ? `${r.total_minutes} min` : "", r.on_offer ? `${r.on_offer} på tilbud` : ""].filter(Boolean).join(" · "))
                    : row("mealie", r.slug, r.name, "")
                )
                .join("")}</ul>`
            : '<p class="muted">Ingen opskrifter fundet.</p>';
    }
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog wide sheet" role="dialog" aria-modal="true" aria-label="Vælg ret">
        <div class="dialog-top"><h2>Ret til ${esc(dateLabel(m.date).toLowerCase())}</h2>
          <button class="icon-btn close" data-action="modal-close" aria-label="Luk">${CLOSE_ICON}</button></div>
        <div class="seg subnav fit">${tabs.map(([k, label]) => `<button class="${m.tab === k ? "active" : ""}" data-action="pick-tab" data-arg="${k}">${label}</button>`).join("")}</div>
        <div class="row wrap">
          <input class="grow" type="search" data-bind="pickq" value="${esc(m.query)}" placeholder="${m.tab === "rema" ? "Søg i REMA's opskrifter" : m.tab === "sites" ? "Søg på madsiderne" : "Søg"}">
          ${m.tab === "rema" || m.tab === "sites" ? `<button class="btn" data-action="pick-search">Søg</button>` : ""}
        </div>
        <p class="muted small">${m.target ? "Retten sættes på dagen, dens varer kommer på indkøbslisten, og opskriften følger med." : "Madplanen bygges omkring den valgte ret, og dens varer kommer på indkøbslisten."}</p>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        ${m.busy ? '<p class="muted"><span class="spinner small"></span> Sætter retten på og finder varerne …</p>' : body}
        <div class="dialog-bottom"><button class="btn" data-action="modal-close">Luk</button></div>
      </div>`;
  }

  _pantryModal(m) {
    const items = (m.items || [])
      .map((item) => {
        const uses = item.uses.map((u) => `${esc(u.dish)}${u.amount ? `: ${esc(u.amount)}` : ""}`).join(" · ");
        const need = item.amount ? ` · i alt ${item.amount} ${esc(item.unit)}` : "";
        const action = item.on_list
          ? '<span class="badge eco">På listen ✓</span>'
          : `<button class="btn small primary" data-action="pantry-add" data-arg="${esc(item.name)}" ${m.busy ? "disabled" : ""}>
               ${m.busy === item.name ? '<span class="spinner small"></span>' : "+ Tilføj til indkøb"}</button>`;
        return `<li class="pantry-item"><div class="what"><b>${esc(item.name.charAt(0).toUpperCase() + item.name.slice(1))}</b>
            <span class="muted small">${uses}${need}</span></div>${action}</li>`;
      })
      .join("");
    const empty =
      m.busy === "load"
        ? '<p class="muted"><span class="spinner small"></span> Kigger i opskrifterne …</p>'
        : '<p class="muted">Opskrifterne bruger ingen af jeres basisvarer – eller de er ikke skrevet endnu.</p>';
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="pantry-title">
        <h2 id="pantry-title">Basisvarer i madplanen</h2>
        <p class="muted small">Varer fra opskrifterne, som I har som basisvarer (Indstillinger) og derfor ikke står på indkøbslisten. Mangler I en, så tilføj den – varen vælges efter jeres indstillinger.</p>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        ${items ? `<ul class="lines">${items}</ul>` : empty}
        <div class="row wrap dialog-actions"><span class="spacer"></span>
          <button class="btn" data-action="modal-close" ${m.busy && m.busy !== "load" ? "disabled" : ""}>Luk</button></div>
      </div>`;
  }

  // Search REMA and add a product to the main list or the later one.
  _shopSearchHtml(part) {
    const search = this._shopSearch[part];
    const results = search.loading
      ? '<p class="muted"><span class="spinner small"></span> Søger …</p>'
      : search.results
          .map(
            (p, i) => `<div class="result-pair"><button class="result" data-action="shop-add" data-arg="${part}|${i}" ${this._busy ? "disabled" : ""}>
              ${p.image ? `<img src="${esc(p.image)}" alt="">` : ""}
              <span><b>${esc(p.name)}</b><span class="muted">${esc(p.underline || "")} · ${kr(p.price)}</span></span>
              ${p.is_organic ? '<span class="badge eco">Øko</span>' : ""}<span class="add">+ Tilføj</span></button>
              <button class="btn small to-rema" data-action="shop-add-list" data-arg="${part}|${i}" ${this._busy ? "disabled" : ""} title="Direkte til ${this._listName()}">+ ${this._listName()}</button></div>`
          )
          .join("");
    const text = search.query.trim();
    const typed = !this._hasPrices() && text && !search.loading && search.searched
      ? `<div class="result-pair"><button class="result" data-action="shop-add-text" data-arg="${part}" ${this._busy ? "disabled" : ""}>
          <span><b>${esc(text)}</b><span class="muted">Som fritekst</span></span><span class="add">+ Tilføj</span></button></div>`
      : "";
    const offers = !search.loading && search.offers?.length
      ? `<p class="muted small avis-head">I ${esc(this._shopGen())} avis</p>${search.offers
          .map(
            (o, i) => `<div class="result-pair"><button class="result" data-action="shop-offer-add" data-arg="${i}" ${this._busy ? "disabled" : ""}>
              ${o.image ? `<img src="${esc(o.image)}" alt="">` : ""}
              <span><b>${esc(o.heading)}</b><span class="muted">${esc([o.description, o.price != null ? kr(o.price) : ""].filter(Boolean).join(" · "))}</span></span>
              <span class="badge offer">Avis</span><span class="add">+ Tilføj</span></button>
              ${this._isRema() ? `<button class="btn small to-rema" data-action="shop-offer-add-list" data-arg="${i}" ${this._busy ? "disabled" : ""} title="Direkte på ${esc(this._quickTodo()?.name || "REMA-listen i appen")}, ikke på madplanens liste">${esc(this._quickLabel())}</button>` : ""}</div>`
          )
          .join("")}`
      : "";
    return `<div class="shop-search">
        <div class="row wrap">
          <input class="grow" type="search" data-bind="shopsearch" data-part="${part}" value="${esc(search.query)}"
            placeholder="${this._hasPrices() ? `Tilføj en vare – søg i ${esc(this._shopName())}, fx kaffe` : "Tilføj en vare, fx kaffe"}">
          <button class="btn small" data-action="shop-search" data-arg="${part}">Søg</button>
          ${clearBtn(`shopsearch|${part}`)}
        </div>
        <div class="results">${typed}${results}${offers}</div>
      </div>`;
  }

  _keepVisible(container, item) {
    // Scroll a horizontal strip just enough to show the active item.
    if (!container || !item) return;
    const left = item.offsetLeft - container.offsetLeft;
    const right = left + item.offsetWidth;
    if (left < container.scrollLeft) container.scrollLeft = left - 12;
    else if (right > container.scrollLeft + container.clientWidth) {
      container.scrollLeft = right - container.clientWidth + 12;
    }
  }

  // The dates the next plan covers, from the chosen first day.
  _planDates() {
    const start = this._startDate || this._state?.default_start;
    const count = this._state?.settings?.days || 7;
    if (!start) return [];
    const pad = (n) => String(n).padStart(2, "0");
    return Array.from({ length: count }, (_, i) => {
      const d = new Date(`${start}T12:00:00`);
      d.setDate(d.getDate() + i);
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    });
  }

  // The last day available for the first shopping day; dinners may go beyond it.
  _lastAvisDay() {
    const cat = this._state?.catalogs || {};
    return localDay(cat.upcoming?.valid_to || cat.current?.valid_to || "");
  }

  // A day of the next plan as the settings' Faste dage have it.
  _defaultKind(iso) {
    const weekday = (new Date(`${iso}T12:00:00`).getDay() + 6) % 7;
    const fixed = (this._state?.settings?.fixed_days || []).find((f) => Number(f.weekday) === weekday);
    return fixed ? { kind: fixedKindOf(fixed), text: fixed.text || "" } : { kind: "ai", text: "" };
  }

  // What a day of the next plan is this week: chosen here, or as the settings have it.
  _kindOf(iso) {
    if (this._dayKinds[iso]) return this._dayKinds[iso];
    if (this._picks[iso]) return { kind: "pick", text: "" };
    if (this._skip.has(iso)) return { kind: "skip", text: "" };
    return this._defaultKind(iso);
  }

  _generateControls(label = "Lav ny madplan") {
    const generating = this._state?.status?.state === "generating";
    const skip = this._planDates()
      .map((iso) => {
        const pick = this._picks[iso];
        const k = this._kindOf(iso);
        const options = Object.entries(DAY_KIND_LABELS)
          .map(([key, l]) => `<option value="${key}" ${k.kind === key ? "selected" : ""}>${l}</option>`)
          .join("");
        const extra =
          k.kind === "pick"
            ? pick
              ? `<span class="pick-chip"><button class="link" data-action="pick-open" data-arg="${iso}" title="Skift retten">${esc(pick.dish)}</button><button class="icon-btn" data-action="pick-remove" data-arg="${iso}" aria-label="Fjern ${esc(pick.dish)}">${CLOSE_ICON}</button></span>`
              : `<button class="btn small primary pick-btn" data-action="pick-open" data-arg="${iso}">Find ret i opskrifter</button>`
            : k.kind === "fixed"
              ? `<input type="text" class="grow" data-bind="daykindtext" data-field="${iso}" value="${esc(k.text || "")}" placeholder="Fx Pizza">`
              : "";
        return `<div class="pickday ${pick && k.kind === "pick" ? "picked" : ""} ${k.kind === "skip" ? "skipped" : ""}"><b>${esc(dateLabel(iso))}</b>
          <select data-bind="daykind" data-field="${iso}" aria-label="Hvad er ${esc(dateLabel(iso).toLowerCase())}">${options}</select>${extra}</div>`;
      })
      .join("");
    const note = this._state?.note;
    const cat = this._state?.catalogs || {};
    const last = this._lastAvisDay();
    return `<div class="row wrap">
      <label class="field inline">Første dag
        <input type="date" data-bind="start" value="${esc(this._startDate || "")}" ${last ? `max="${esc(last)}"` : ""}>
      </label>
    </div>
    ${cat.current && !cat.upcoming && last
      ? `<p class="muted small">Næste uges avis er ikke ude endnu. Hele den valgte periode planlægges med kendte priser og tilbud på indkøbsdagen.</p>`
      : ""}
    <div class="wishes">
      <button class="btn" data-action="note-open">${note ? "Ret ønsker til madplanen" : "Ønsker til madplanen"}</button>
      ${note ? `<p class="muted small note-preview">Bruges i næste madplan: ${esc(note)}</p>` : ""}
    </div>
    ${skip ? (() => {
      const dates = this._planDates();
      const tailored = dates.filter((iso) => {
        const k = this._kindOf(iso);
        const d = this._defaultKind(iso);
        return k.kind !== d.kind || (k.kind === "fixed" && k.text !== d.text) || (k.kind === "pick" && this._picks[iso]);
      }).length;
      const open = tailored || this._folds?.has("days");
      return `<details class="fold" data-fold="days" ${open ? "open" : ""}><summary>Tilpas dagene${tailored ? ` <span class="badge">${tailored} ${tailored === 1 ? "dag" : "dage"}</span>` : ""}</summary>
        <p class="muted small">Dagene er som under Faste dage i indstillingerne – ændr dem for netop denne uge. En rugbrødsdag laves der ikke mad, og der købes ikke noget til.</p><div class="skipdays">${skip}</div></details>`;
    })() : ""}
    ${(this._state?.freezer_inventory || []).length ? `<label class="check"><input type="checkbox" data-bind="use-freezer" ${this._useFreezer !== false ? "checked" : ""}> Brug råvarer fra spisekammeret i denne madplan</label><p class="muted small">Prioritér spisekammerets indhold. Kun manglende mængder købes; du bekræfter selv forbruget bagefter.</p>` : ""}
    <div class="row wrap skipgo">
      <button class="btn primary" data-action="generate" ${generating || this._busy ? "disabled" : ""}>
        ${generating ? "Laves …" : aiLabel(label)}
      </button>
      <button class="btn surprise" data-action="surprise" ${generating || this._busy ? "disabled" : ""}
        title="Retter I aldrig har fået – fra andre køkkener og med overraskende smage">${SURPRISE_ICON}Overrask os</button>
    </div>`;
  }

  _inventoryCard(open = false) {
    const items = this._state?.freezer_inventory || [];
    const d = this._inventoryDraft || {};
    return `<details class="card fold" data-fold="inventory" ${open || this._folds?.has("inventory") ? "open" : ""}>
      <summary><span class="fold-title">Råvarer på lager</span> <span class="badge">${items.length}</span></summary>
      <p class="muted small">Fælles lager for alle butikker. Skriv råvaren, fx hakket oksekød, og den samlede mængde. Råvarerne bruges automatisk til nye madplaner, medmindre du slår det fra – dem med <b>Brug senest</b> først og tidligt i ugen.</p>
      ${items.map(i => `<div class="row wrap"><span class="spacer">${esc(i.name)} · ${String(i.amount).replace(".", ",")} ${esc(i.unit)}${i.place ? ` <span class="muted small">· ${esc(i.place)}</span>` : ""}${this._bestBefore(i.best_before)}</span><button class="btn small" data-action="inventory-edit" data-arg="${esc(i.id)}">Ret</button><button class="btn small" data-action="inventory-delete" data-arg="${esc(i.id)}" ${this._busy ? "disabled" : ""}>Fjern</button></div>`).join("") || '<p class="muted">Spisekammeret er tomt.</p>'}
      <div class="row wrap inventory-fields">
        <label class="field">Råvare <input data-bind="inventory-field" data-field="name" maxlength="120" value="${esc(d.name || "")}" placeholder="Fx hakket oksekød"></label>
        <label class="field">Mængde <input data-bind="inventory-field" data-field="amount" type="number" min="0.001" max="100000" step="any" value="${esc(d.amount ?? "")}" placeholder="800"></label>
        <label class="field">Enhed <select data-bind="inventory-field" data-field="unit">${["g", "kg", "ml", "l", "stk"].map(u => `<option ${u === (d.unit || "g") ? "selected" : ""}>${u}</option>`).join("")}</select></label>
        <label class="field">Hvor <select data-bind="inventory-field" data-field="place"><option value="">–</option>${["køleskab", "fryser", "skab"].map(p => `<option value="${p}" ${p === d.place ? "selected" : ""}>${p[0].toUpperCase()}${p.slice(1)}</option>`).join("")}</select></label>
        <label class="field">Brug senest <input data-bind="inventory-field" data-field="best_before" type="date" value="${esc(d.best_before || "")}"></label>
      </div><div class="row wrap"><button class="btn" data-action="inventory-save" ${this._busy ? "disabled" : ""}>${d.id ? "Gem mængde" : "Tilføj råvare"}</button>${d.id ? '<button class="btn" data-action="inventory-cancel">Annuller</button>' : ""}</div>
      <p class="muted small">Lageret reserveres ikke af en madplan. Tryk “Retten er lavet” ved den enkelte ret for at bekræfte forbruget. Ret lageret her, hvis du bruger noget til andet. Nye lagerændringer gælder nye madplaner.</p>
    </details>`;
  }

  // "brug senest 10/11", red when it is today or past, amber within two days.
  _bestBefore(iso) {
    if (!iso) return "";
    const days = Math.round((new Date(`${iso}T12:00:00`) - new Date(`${localToday()}T12:00:00`)) / 86400000);
    const cls = days <= 0 ? "badge over" : days <= 2 ? "badge doubt" : "muted small";
    const text = days < 0 ? `overskredet ${shortDate(iso)}` : days === 0 ? "brug i dag" : `brug senest ${shortDate(iso)}`;
    return ` <span class="${cls}">${text}</span>`;
  }

  _inventoryUsage(plan, day = null, shopping = false) {
    const used = plan?.freezer_used || [];
    if (!used.length) return "";
    const groups = (plan.freezer_groups || []).filter(g => !day || g.day_id === day.inventory_id);
    const consumed = (this._state?.freezer_consumed || []).includes(plan.id);
    const confirmed = this._state?.freezer_confirmed || {};
    const list = items => `<ul>${items.map(i => `<li>${esc(i.name)}: ${i.amount} ${esc(i.unit)}</li>`).join("")}</ul>`;
    if (!groups.length && day) return "";
    return `<div class="banner"><b>${shopping ? "Ikke på indkøbslisten – fra spisekammeret" : "Fra spisekammeret"}</b>
      <p class="small">${shopping ? "Disse mængder har I allerede. Hvis lageret kun dækker en del, købes resten." : "Disse mængder er ikke lagt på indkøbslisten. Opskriften viser den fulde mængde."}</p>
      ${groups.length ? groups.map(g => `<div><b>${esc(g.dish)}</b>${list(g.items)}${consumed || confirmed[g.id] ? `<p class="small">${consumed || confirmed[g.id]?.items?.length ? "Forbruget er registreret ✓" : "Bekræftet: råvarerne blev ikke brugt fra lageret."}</p>` : shopping ? "" : `<button class="btn small" data-action="inventory-consume-open" data-arg="${esc(plan.id)}|${esc(g.id)}" ${this._busy ? "disabled" : ""}>${g.day_id ? "Retten er lavet" : "Registrér forbrug"}</button>`}</div>`).join("") : `${list(used)}${consumed ? "Forbruget er registreret ✓" : shopping ? "" : `<button class="btn" data-action="inventory-consume-open" data-arg="${esc(plan.id)}" ${this._busy ? "disabled" : ""}>Registrér forbrug</button>`}`}
      ${!shopping && !consumed ? '<p class="muted small">Lageret ændres først, når du bekræfter forbruget.</p>' : ""}</div>`;
  }

  // Månedens frysermad, folded away under the weekly plan.
  _freezerCard() {
    const count = (this._state?.freezer_plans || []).length;
    return `<details class="card fold freezer-card" data-fold="freezer" ${this._folds?.has("freezer") ? "open" : ""}>
      <summary><span class="fold-title">Månedens frysermad</span>${count ? ` <span class="badge">${count} ${count === 1 ? "plan" : "planer"}</span>` : ""}</summary>
      ${this._freezerControls(false)}
    </details>`;
  }

  _freezerControls(heading = true) {
    const busy = this._busy || this._state?.status?.state === "generating";
    const plans = this._state?.freezer_plans || [];
    return `<section class="freezer-section ${heading ? "" : "flat"}">
      ${heading ? "<h2>Månedens frysermad</h2>" : ""}
      <p class="muted">Én maddag, flere aftener med nem mad. Lav en separat plan, og vælg bagefter portioner for hver ret.</p>
      <label class="field">Ønsker til fryserretterne <textarea data-bind="freezer-note" rows="2" maxlength="2000" placeholder="Fx gryderetter med kylling, ingen svampe">${esc(this._freezerNote ?? this._state?.freezer_note ?? "")}</textarea></label>
      <p class="muted small">Bruges kun til fryserplanen – ugens madplan har sine egne ønsker.</p>
      ${(this._state?.freezer_inventory || []).length ? `<label class="check"><input type="checkbox" data-bind="use-freezer-batch" ${this._useFreezerBatch !== false ? "checked" : ""}> Brug råvarer fra spisekammeret til fryserretterne</label>` : ""}
      <div class="row wrap">${[4, 5].map(n => `<button class="btn" data-action="freezer-generate" data-arg="${n}" ${busy ? "disabled" : ""}>${aiLabel(`Lav en plan med ${n} retter`)}</button>`).join("")}</div>
      ${plans.length ? `<h3>Dine fryserplaner</h3><div class="batch-plans">${plans.map(p => `<div class="batch-plan-row"><button class="setting-row" data-action="freezer-open" data-arg="${esc(p.id)}"><span class="setting-text"><b>${esc(p.title)}</b><span class="muted small">${p.dishes?.length || ""} retter · ${kr(p.total)}</span></span><span class="chev" aria-hidden="true">›</span></button><button class="btn small danger" data-action="delete-plan" data-arg="${esc(p.id)}" aria-label="Slet fryserplan: ${esc(p.title)}" ${busy ? "disabled" : ""}>Slet</button></div>`).join("")}</div>` : '<p class="muted small">Når planen er klar, kan du åbne den her. Den ændrer ikke ugens madplan.</p>'}
    </section>`;
  }

  _freezerView(plan) {
    const consumed = (this._state?.freezer_consumed || []).includes(plan.id) || (plan.freezer_groups || []).some(g => Object.hasOwn(this._state?.freezer_confirmed || {}, g.id));
    const locked = plan.portions_locked || plan.sent_at || plan.shopping.some(l => l.sent) || consumed || plan.days.some(d => Object.hasOwn(this._state?.freezer_confirmed || {}, d.inventory_group_id));
    const portions = day => {
      const values = [...new Set([4, 8, 12, 16, 20, 24, 32, 40, day.servings])].sort((a, b) => a - b);
      return `<label class="field batch-portions">Antal portioner <select data-bind="freezer-portions" data-date="${day.date}" aria-label="Portioner til ${esc(day.dish)}" ${locked || this._busy ? "disabled" : ""}>${values.map(n => `<option value="${n}" ${n === day.servings ? "selected" : ""}>${n} portioner</option>`).join("")}</select></label>`;
    };
    return `<div class="card">
      <h1>${esc(plan.title)}</h1>
      <ol class="batch-steps" aria-label="Sådan bruger du fryserplanen"><li>Retterne er valgt</li><li ${!locked ? 'aria-current="step"' : ""}>Vælg portioner</li><li ${locked ? 'aria-current="step"' : ""}>Gennemgå indkøb</li></ol>
      <p>Hvor meget vil I lave af hver ret? Vælg fx 16 portioner. Opskrift og indkøbsliste opdateres automatisk.</p>
      <p class="muted small">Familiens portionsprocent bruges ikke her. Ris og pasta til spisedagen købes separat.</p>
      ${locked ? '<div class="banner info">Portionsvalget er låst, fordi overførsel er startet eller lagerforbrug er bekræftet.</div>' : ""}
      ${this._inventoryUsage(plan)}
      <div class="batch-dishes">${plan.days.map((day, i) => `<article class="batch-dish"><div class="batch-dish-name"><span class="batch-number" aria-hidden="true">${i + 1}</span><h2>${esc(day.dish)}</h2></div>${portions(day)}
        ${day.tip ? `<p class="muted">${esc(day.tip)}</p>` : ""}
        <button class="btn small" data-action="open-day" data-arg="${esc(plan.id)}|${day.date}" aria-label="Se opskrift på ${esc(day.dish)}">Se opskrift</button></article>`).join("")}</div>
      <details><summary>Fordeling i fryseposer</summary><p class="muted small">Fordel den færdige ret i fx 400 g poser. Antallet afhænger af rettens færdige vægt og beregnes ikke automatisk.</p></details>
      <div class="batch-footer"><div><span class="muted small">Anslået indkøb i alt</span><strong>${kr(plan.total)}</strong></div><button class="btn primary" data-action="tab" data-arg="shopping">Se indkøbsliste →</button></div>
      <div class="row between wrap"><button class="link" data-action="view-latest">‹ Til ugens madplan</button><button class="btn small danger" data-action="delete-plan" data-arg="${esc(plan.id)}" ${this._busy ? "disabled" : ""}>Slet fryserplan</button></div>
    </div>${this._freezerControls()}`;
  }

  // The week's packed lunches: how many, the days off, and the AI's ideas.
  _lunchHtml(plan) {
    const lunch = plan.lunch;
    if (!lunch) return "";
    const off = (lunch.off || []).map((d) => dateLabel(d)).join(", ");
    const ideas = plan.lunch_ideas || [];
    return `<details class="plan-checks" ${ideas.length ? "open" : ""}><summary>Madpakker: ${lunch.lunches ? `${lunch.lunches} i perioden` : "ingen i perioden"}</summary>
      <p class="muted small">${lunch.count} om dagen · ${(lunch.days || []).length} skoledage${off ? ` · fri ${esc(off)}` : ""}. Madpakkevarerne står på indkøbslisten.</p>
      ${ideas.length ? `<ul class="lunch-ideas">${ideas.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}
    </details>`;
  }

  _planView() {
    const plan = this._plan;
    if (plan?.kind === "freezer") return this._freezerView(plan);
    const cat = this._state.catalogs;
    const catLine = [
      cat.current ? `Aktuel avis: ${esc(cat.current.label || "")} (til ${shortDate(localDay(cat.current.valid_to))})` : "",
      cat.upcoming
        ? `Næste avis: ${esc(cat.upcoming.label || "")} fra ${shortDate(localDay(cat.upcoming.valid_from))}`
        : "Næste uges avis er ikke udkommet endnu",
    ]
      .filter(Boolean)
      .join(" · ");
    if (!plan) {
      return `<div class="card hero">
        <img src="${this._img("icon.png")}" class="hero-icon" alt="">
        <h1>Ingen madplan endnu</h1>
        <p>Madplanen laves med AI ud fra ugens tilbud og jeres indstillinger. Tjek indstillingerne først, og tryk så på knappen.</p>
        ${this._generateControls("Lav madplan")}
        <p class="muted">${catLine}</p>
      </div>${this._freezerCard()}`;
    }
    const over = plan.budget && plan.total > plan.budget;
    const today = localToday();
    const dayRow = (owner, day) => {
      const type = TYPE_LABELS[day.type] ?? day.type;
      const past = day.date < today;
      return `<div class="day-row ${past ? "past" : ""}"><button class="day art ${day.date === today ? "today" : ""}" data-action="day-menu" data-arg="${esc(owner.id)}|${day.date}">
          ${V3.dishArt(day.dish || "", "d-art")}<span class="date">${day.date === today ? `I aften · ${esc(dateLabel(day.date))}` : esc(dateLabel(day.date))}</span>
          <span class="dish ${day.dish ? "" : "muted"}">${esc(day.dish || "Ingen ret – tryk for at vælge en")}</span>
          <span class="meta">${day.total_minutes ? `${day.total_minutes} min` : ""}${type ? ` <span class="badge">${esc(type)}</span>` : ""}${day.mealie ? ' <span class="badge mealie">Mealie</span>' : ""}${day.new_dish ? ' <span class="badge doubt">Ny ret – godkend</span>' : ""}${owner.surprise ? ' <span class="badge surprise">Overraskelse</span>' : ""}</span>
        </button><span class="day-tools">${this._rateButtons(owner, day)}${this._moveButtons(owner, day, past)}</span></div>`;
    };
    // A skipped day stays in the list, grey: tap it to take it back or make it something else.
    const skippedRow = (planId, date) => `<div class="day-row skipped-day ${date < today ? "past" : ""}"><button class="day art" data-action="day-menu-skipped" data-arg="${esc(planId)}|${date}">
          ${V3.dishArt("", "d-art")}<span class="date">${esc(dateLabel(date))}</span>
          <span class="dish muted">Springes over – tryk for at ændre</span>
          <span class="meta"><span class="badge">Springes over</span></span>
        </button><span class="day-tools"></span></div>`;
    // The newest plan decides each date; this week and the coming days show as one plan.
    const timeline = this._timeline();
    let title = plan.title;
    let period = `${dateLabel(plan.start_date)} – ${dateLabel(plan.end_date)}`;
    let skipped = (plan.skipped || []).map((date) => ({ planId: plan.id, date }));
    let avis = plan.catalog ? ` · ${plan.catalog.label || ""}` : "";
    let shopFrom = "";
    let days;
    if (timeline) {
      const weeks = [...new Set(timeline.map((e) => e.week))];
      title = weeks.length > 1 ? `Madplan uge ${weeks[0]}–${weeks[weeks.length - 1]}` : `Madplan uge ${weeks[0]}`;
      const shown = timeline.filter((e) => e.day || e.skipped);
      period = shown.length ? `${dateLabel(shown[0].date)} – ${dateLabel(shown[shown.length - 1].date)}` : period;
      skipped = timeline.filter((e) => e.skipped && e.date >= today).map((e) => ({ planId: e.plan.id, date: e.date }));
      avis = "";
      // Days from older plans: the price and the list are the newest plan's.
      if (timeline.some((e) => e.plan.id !== plan.id)) shopFrom = `indkøb fra ${dateLabel(plan.start_date)}`;
      let week = null;
      days = shown
        .map((e) => {
          const head = weeks.length > 1 && e.week !== week ? `<h3 class="week-head">Uge ${esc(e.week)}</h3>` : "";
          week = e.week;
          return head + (e.day ? dayRow(e.plan, e.day) : skippedRow(e.plan.id, e.date));
        })
        .join("");
    } else {
      days = [
        ...plan.days.map((day) => ({ date: day.date, html: dayRow(plan, day) })),
        ...(plan.skipped || []).map((date) => ({ date, html: skippedRow(plan.id, date) })),
      ]
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((d) => d.html)
        .join("");
    }
    const checklist = (plan.checklist || [])
      .map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.requirement)}</li>`)
      .join("");
    return `
      ${this._olderBanner()}
      ${this._updateBanner(plan)}
      <div class="card">
        <div class="row between wrap">
          <div>
            <h1 class="plan-title">${esc(title)} <button class="help-q" data-action="plan-help" aria-expanded="${this._planHelp ? "true" : "false"}" aria-label="Hjælp" title="Hjælp">?</button></h1>
            <p class="muted">${esc(period)}${esc(avis)}</p>
          </div>
          <div class="price ${over ? "over" : ""}">
            <span class="big">${kr(plan.total)}</span>
            <span class="muted">${[shopFrom, plan.budget ? `budget ${kr(plan.budget)}` : ""].filter(Boolean).map(esc).join(" · ")}</span>
          </div>
        </div>
        ${plan.summary ? `<p>${esc(plan.summary)}</p>` : ""}
        ${over ? `<div class="banner warn">Planen er over budget. Prøv at lave en ny, eller ret budgettet i indstillingerne.</div>` : ""}
        ${(() => {
          const broken = (plan.checklist || []).filter((c) => !c.ok);
          return broken.length
            ? `<div class="banner warn">AI'en kunne ikke overholde ${broken.length === 1 ? "ét krav" : `${broken.length} krav`}, selv efter at have prøvet igen:<ul class="checklist">${broken.map((c) => `<li class="bad">✗ ${esc(c.requirement)}</li>`).join("")}</ul>Tryk på retten for at skifte den ud, eller lav en ny madplan.</div>`
            : "";
        })()}
        ${(() => {
          const waiting = (plan.days || []).filter((d) => d.new_dish);
          return waiting.length
            ? `<div class="banner warn">${waiting.length === 1 ? "1 ny ret venter" : `${waiting.length} nye retter venter`} på godkendelse: ${waiting.map((d) => esc(d.dish)).join(", ")}. Listen sendes først, når de er godkendt eller skiftet ud – tryk på retten.</div>`
            : "";
        })()}
        ${this._planHelp ? '<p class="muted small help-text">Tryk på en ret for at se opskriften eller skifte den ud. 👍, 👎 og ♥ gemmer retten i opskriftsamlingen – tryk igen for at fortryde.</p>' : ""}
        ${this._inventoryUsage(plan)}
        <div class="days">${days}</div>
        ${this._lunchHtml(plan)}
        ${checklist || plan.deviations ? `<details class="plan-checks"><summary>Krav-tjekliste</summary><ul class="checklist">${checklist}</ul>${plan.deviations ? `<p class="muted">${esc(plan.deviations)}</p>` : ""}</details>` : ""}
        <div class="plan-actions">
          ${(() => {
            const left = plan.shopping.filter((line) => !line.buy_from && !line.buy_at && !line.sent).length;
            return `<button class="btn primary send-main" data-action="send" ${this._busy || !left ? "disabled" : ""}>
              ${left ? (plan.status === "sent" ? `Send ${left} nye varer til ${this._listName()}` : `Send til ${this._listName()}`) : "Sendt ✓"}</button>`;
          })()}
          ${plan.shopping.some((line) => line.buy_from)
            ? `<p class="muted small later">+ ${plan.shopping.filter((line) => line.buy_from).length} varer købes senere – se Indkøb</p>`
            : ""}
          <div class="plan-more">
            <button class="btn" data-action="tab" data-arg="shopping">Se indkøbsliste</button>
            <button class="btn" data-action="open-day" data-arg="">Start madlavning</button>
            ${this._state.mealie?.available ? `<button class="btn" data-action="mealie-sync" ${this._busy ? "disabled" : ""}>Sæt ugen i Mealie-kalenderen</button>` : ""}
          </div>
        </div>
      </div>
      <div class="card">
        <h2>Ny madplan</h2>
        ${this._generateControls()}
        <p class="muted">${catLine}</p>
      </div>${this._freezerCard()}`;
  }

  // Which plan and date the chosen recipe day belongs to; a new plan or a new
  // day starts again on today's dish.
  _recipeKey() {
    return `${this._plan?.id}|${localToday()}`;
  }

  // A short pause after typing an ingredient, then REMA's products for it.
  _ingSearchSoon(idx, text) {
    clearTimeout(this._ingTimer);
    const query = String(text || "").trim();
    const m = this._modal;
    if (query.length < 3) {
      if (m) m.sugg = null;
      this._ingSuggHtml(idx, "");
      return;
    }
    this._ingTimer = setTimeout(() => this._ingSearch(idx, query), 350);
  }

  async _ingSearch(idx, query) {
    const m = this._modal;
    if (m?.kind !== "recipe") return;
    const token = (this._ingToken = (this._ingToken || 0) + 1);
    this._ingSuggHtml(idx, '<p class="muted small"><span class="spinner small"></span> Søger hos REMA …</p>');
    let items = [];
    try {
      items = (await this._ws("middagsro/search", { query })).slice(0, 6);
    } catch (err) {
      items = [];
    }
    if (token !== this._ingToken || this._modal !== m) return;
    m.sugg = { idx, items };
    this._ingSuggHtml(
      idx,
      items.length
        ? `<div class="rc-sugg-list">${items
            .map(
              (p) => `<button class="rc-sugg-item" data-action="rc-ing-pick" data-arg="${idx}|${esc(p.id)}">
                ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
                <span class="what"><b>${esc(p.name)}</b><span class="muted small">${esc(p.underline || "")}</span></span>
                <span class="price ${onOffer(p) ? "sale" : ""}">${kr(p.price)}</span></button>`
            )
            .join("")}</div>`
        : `<p class="muted small">Ingen REMA-varer fundet for "${esc(query)}".</p>`
    );
  }

  _ingSuggHtml(idx, html) {
    const node = this.shadowRoot.querySelector(`#modal .rc-sugg[data-idx="${idx}"]`);
    if (node) node.innerHTML = html;
  }

  // REMA 1000's own recipes: categories, cards and "Vis flere".
  // The family's recipe sites: search them, open a recipe, save it in the collection.
  _sitesView() {
    const chosen = this._state.settings.recipe_sites || [];
    const names = (this._state.recipe_sites || []).filter((x) => chosen.includes(x.id)).map((x) => x.name);
    const s = this._sites;
    if (!chosen.length) {
      return `<div class="card"><h2 class="flush">Madsider</h2>
        <p>Søg i opskrifter fra kendte madsider – Valdemarsro, Madens Verden, Louises madblog, DK-kogebogen og Arla – og gem dem i opskriftsamlingen. Madplanen kan også tage udgangspunkt i dem.</p>
        <button class="btn primary" data-action="settings-open" data-arg="sites">Vælg madsider</button></div>`;
    }
    const rows = (s.results || [])
      .map(
        (r) => `<li class="pick-row"><div class="what"><b>${esc(r.title)}</b><span class="muted small">${esc(r.site_name)}</span></div>
          <button class="btn small" data-action="site-open" data-arg="${esc(r.url)}" ${s.opening ? "disabled" : ""}>${s.opening === r.url ? '<span class="spinner small"></span>' : "Se opskrift"}</button></li>`
      )
      .join("");
    return `<div class="card">
      <h2 class="flush">Madsider</h2>
      <p class="muted small">Søger i ${esc(names.join(", "))}. <button class="link" data-action="settings-open" data-arg="sites">Ret</button></p>
      <div class="row wrap">
        <input class="grow" type="search" data-bind="sitequery" value="${esc(s.query)}" placeholder="Søg fx frikadeller, lasagne eller laks" enterkeyhint="search">
        <button class="btn" data-action="site-search" ${s.loading ? "disabled" : ""}>Søg</button>
      </div>
      ${s.loading ? '<p class="muted"><span class="spinner small"></span> Søger … (første gang tager det lidt længere)</p>' : ""}
      ${s.error ? `<div class="banner error">${esc(s.error)}</div>` : ""}
      ${rows ? `<ul class="lines">${rows}</ul>` : s.searched && !s.loading ? '<p class="muted">Ingen opskrifter fundet. Prøv et andet ord.</p>' : ""}
    </div>`;
  }

  async _siteSearch(query, into) {
    const target = into || this._sites;
    if (!query.trim()) return;
    Object.assign(target, { loading: true, error: null, searched: true });
    into ? this._renderModal() : this._render();
    try {
      target.results = (await this._ws("middagsro/sites/search", { query })).results || [];
    } catch (err) {
      target.error = err?.message || String(err);
    }
    target.loading = false;
    into ? this._renderModal() : this._render();
  }

  // The week's dinners from the avis: ready recipes priced with its offers.
  async _candLoad() {
    const c = (this._cand = { sort: "cheapest", ...(this._cand || {}), loading: true, error: null });
    this._render();
    try {
      const data = await this._ws("middagsro/candidates", { start: this._state?.default_start || null, sort: c.sort });
      if (this._cand !== c) return;
      c.data = data;
    } catch (err) {
      c.error = err?.message || String(err);
    }
    c.loading = false;
    if (this._tab === "recipes") this._render();
  }

  _candView() {
    const c = this._cand || { sort: "cheapest" };
    const d = c.data;
    const chip = (key, label) => `<button class="chip ${c.sort === key ? "active" : ""}" data-action="cand-sort" data-arg="${key}" ${c.loading ? "disabled" : ""}>${label}</button>`;
    const cards = (d?.candidates || [])
      .map((r) => {
        const open = r.source === "collection" ? `data-action="rc-open" data-arg="${esc(r.id)}"` : `data-action="rr-open" data-arg="${esc(r.slug)}"`;
        const swaps = (r.swaps || []).map((x) => `<li>${esc(x.item)} → <b>${esc(x.offer)}</b> ${kr(x.price)}</li>`).join("");
        return `<div class="rr-card">
          <button class="rr-img" ${open} aria-label="Se ${esc(r.name)}">${r.image ? `<img src="${esc(r.image)}" alt="" loading="lazy">` : ""}</button>
          <b class="rr-title">${esc(r.name)}</b>
          <span class="muted small">ca. ${kr(r.per_person)} pr. person${r.saving >= 1 ? ` · sparer ca. ${kr0(r.saving)}` : ""}${r.total_minutes ? ` · ${r.total_minutes} min` : ""}</span>
          <span class="rr-badges"><span class="badge offer">${r.on_offer.length} på tilbud</span>${r.source === "collection" ? '<span class="badge">Jeres</span>' : '<span class="badge">REMA</span>'}${r.vegetarian ? '<span class="badge eco">Vegetar</span>' : ""}${r.favorite ? '<span class="badge">♥</span>' : ""}</span>
          ${swaps ? `<ul class="cand-swaps small muted">${swaps}</ul>` : ""}
          <button class="btn small" ${open}>Se opskrift</button>
        </div>`;
      })
      .join("");
    const lo = d?.left_out || {};
    const out = [
      lo.recent ? `${lo.recent} lavet for nylig` : "",
      lo.disliked ? `${lo.disliked} I ikke kan lide` : "",
      lo.rules ? `${lo.rules} med noget, I undgår` : "",
      lo.not_ready ? `${lo.not_ready} mangler varer` : "",
    ].filter(Boolean);
    return `<div class="card">
      <h2 class="flush">Ugens billigste retter ud fra avisen</h2>
      <p class="muted small">${d ? `${d.avis ? `${esc(d.avis)}: ` : ""}${d.total} klare opskrifter bruger noget fra avisen.` : ""} Prisen er anslået med én pakke af hver vare. En vare, der ikke er markeret <i>Altid præcis denne</i>, kan erstattes af en tilbudsvare af samme slags.</p>
      <div class="chips">${chip("cheapest", "Billigst pr. person")}${chip("offers", "Mest sparet")}</div>
      ${c.error ? `<div class="banner error">${esc(c.error)}</div>` : ""}
      ${c.loading ? '<p class="muted"><span class="spinner small"></span> Regner ugens priser ud …</p>' : ""}
      ${d && !c.loading && !cards ? `<p class="muted">Ingen klare opskrifter bruger noget fra avisen.${d.catalog && !d.catalog.swept ? " REMA's opskrifter er ikke hentet endnu." : ""}</p>` : ""}
      <div class="rr-grid">${cards}</div>
      ${out.length && d ? `<p class="muted small">Ikke med: ${out.join(", ")}.</p>` : ""}
    </div>`;
  }

  _remaView() {
    const rr = this._rr;
    const pick = this._remaPick;
    const chip = (key, label) =>
      `<button class="chip ${rr.key === key ? "active" : ""}" data-action="rr-tag" data-arg="${esc(key)}" ${rr.loading ? "disabled" : ""}>${esc(label)}</button>`;
    const chips = [chip("popular", "Populære"), chip("newest", "Nyeste"), ...rr.tags.map((t) => chip(t.id, t.title))].join("");
    const searching = rr.key === "search";
    const cards = rr.recipes
      .map(
        (r) => `<div class="rr-card">
          <button class="rr-img" data-action="rr-open" data-arg="${esc(r.slug)}" aria-label="Se ${esc(r.title)}">${r.image ? `<img src="${esc(r.image)}" alt="" loading="lazy">` : ""}</button>
          <b class="rr-title">${esc(r.title)}</b>
          <span class="muted small">${[r.total_minutes ? `${r.total_minutes} min` : "", r.servings ? `${r.servings} pers.` : "", r.cost ? `ca. ${kr(r.cost)}` : ""].filter(Boolean).join(" · ")}</span>
          <span class="rr-badges">${r.ready ? '<span class="badge ready" title="Alle varer er koblet til REMA – klar til madplanen">Klar</span>' : ""}${r.on_offer ? `<span class="badge offer">${r.on_offer} på tilbud</span>` : ""}${r.vegetarian ? '<span class="badge eco">Vegetar</span>' : ""}</span>
          ${pick
            ? `<button class="btn primary small" data-action="rr-pick" data-arg="${esc(r.slug)}" ${this._busy ? "disabled" : ""}>Vælg</button>`
            : `<button class="btn small" data-action="rr-open" data-arg="${esc(r.slug)}">Se opskrift</button>`}
        </div>`
      )
      .join("");
    return `<div class="card">
      ${pick
        ? `<div class="banner info">Vælg en ret til ${esc(dateLabel(pick.date).toLowerCase())}${pick.dish ? ` i stedet for ${esc(pick.dish)}` : ""}.
            <span class="spacer"></span><button class="btn small" data-action="rr-pick-cancel">Annullér</button></div>`
        : ""}
      <h2 class="flush">REMA 1000's opskrifter</h2>
      <p class="muted small">${rr.total ? `${rr.total} ${searching ? `opskrifter med "${esc(rr.query)}"` : "opskrifter"}. ` : ""}Ingredienserne er koblet til REMA's varer, så indkøbslisten får de rigtige varer – også dem på tilbud.</p>
      ${this._rrCatalogLine()}
      <div class="row wrap rr-search">
        <input class="grow" type="search" data-bind="rrquery" value="${esc(this._rrQuery ?? rr.query)}" placeholder="Søg fx frikadeller, laks eller spinatpandekager" enterkeyhint="search">
        <button class="btn" data-action="rr-search" ${rr.loading ? "disabled" : ""}>Søg</button>
        ${clearBtn("rrquery")}
      </div>
      <div class="chips">${chips}</div>
      ${rr.error ? `<div class="banner error">${esc(rr.error)}</div>` : ""}
      <div class="rr-grid">${cards}</div>
      ${rr.loading ? '<p class="muted"><span class="spinner small"></span> Henter opskrifter …</p>' : ""}
      ${!rr.loading && rr.page && rr.page < rr.last ? '<button class="btn" data-action="rr-more">Vis flere</button>' : ""}
      ${!rr.loading && rr.page && !rr.recipes.length ? `<p class="muted">${searching ? `Ingen af REMA's opskrifter passer til "${esc(rr.query)}".` : "Ingen opskrifter her."}</p>` : ""}
    </div>`;
  }

  // How far Home Assistant has got reading all of REMA's dinner recipes.
  _rrCatalogLine() {
    const c = this._rrCatalog;
    if (!c) return "";
    if (c.running)
      return `<p class="muted small"><span class="spinner small"></span> Henter alle REMA's aftensretter til Home Assistant – én side i minuttet, så REMA ikke belastes${c.pages ? ` (${c.pages} sider indtil videre)` : ""} …</p>`;
    if (c.swept && c.count)
      return `<p class="muted small">Alle ${c.count} aftensretter er hentet til Home Assistant – ${c.ready} er klar til madplanen (alle varer koblet). Opdateret ${esc(sentWhen(c.swept))}.</p>`;
    return "";
  }

  async _rrLoad() {
    const rr = this._rr;
    if (rr.loading || (rr.page && rr.page >= rr.last)) return;
    rr.loading = true;
    rr.error = null;
    this._render();
    const sorted = rr.key === "popular" || rr.key === "newest";
    try {
      const data = await this._ws("middagsro/rema_recipes/list", {
        query: rr.key === "search" ? rr.query : null,
        tag: sorted || rr.key === "search" ? null : rr.key,
        sort: rr.key === "newest" ? "newest" : "popular",
        page: rr.page + 1,
      });
      if (this._rr !== rr) return; // another category was chosen meanwhile
      const seen = new Set(rr.recipes.map((r) => r.slug));
      rr.recipes.push(...data.recipes.filter((r) => !seen.has(r.slug)));
      Object.assign(rr, { page: data.page, last: data.last_page, total: data.total, tags: data.tags || rr.tags });
      if (data.catalog) this._rrCatalog = data.catalog;
    } catch (err) {
      rr.error = err?.message || String(err);
    }
    rr.loading = false;
    if (this._tab === "recipes") this._render();
  }

  // Search REMA's recipes; an empty search goes back to the popular ones.
  _rrSearch(text) {
    const query = String(text || "").trim();
    if (!query) {
      this._rrQuery = "";
      this._rr = { ...this._rr, key: "popular", query: "", page: 0, last: 1, recipes: [], loading: false, error: null };
    } else this._rr = { ...this._rr, key: "search", query, page: 0, last: 1, recipes: [], loading: false, error: null };
    this._rrLoad();
  }

  async _rrOpen(slug) {
    this._modal = { kind: "recipe", loading: true, recipe: { id: null, name: "" } };
    this._renderModal();
    try {
      const recipe = await this._ws("middagsro/rema_recipes/get", { slug });
      if (this._modal?.kind !== "recipe" || !this._modal.loading) return;
      this._modal = { kind: "recipe", recipe: clone(recipe) };
      this._renderModal();
    } catch (err) {
      this._modal = null;
      this._renderModal();
      this._say(`Fejl: ${err?.message || err}`);
    }
  }

  // Put a REMA recipe on the day chosen in the plan (it is saved in the collection too).
  async _rrPick(slug) {
    const pick = this._remaPick;
    if (!pick || this._busy) return;
    const m = this._modal;
    if (m?.kind === "recipe") {
      m.busy = "pick";
      this._renderModal();
    }
    this._busy = true;
    this._say("Sætter retten på og finder varerne …");
    try {
      await this._ws("middagsro/rema_recipes/plan", { slug, plan_id: pick.planId, date: pick.date });
      this._remaPick = null;
      this._modal = null;
      this._renderModal();
      this._busy = false;
      this._goTab("plan");
      await this._load();
      this._say(`Retten er sat på ${dateLabel(pick.date).toLowerCase()} og gemt i opskriftsamlingen – indkøbslisten er lavet om.`);
    } catch (err) {
      this._busy = false;
      if (m?.kind === "recipe" && this._modal === m) {
        m.busy = false;
        m.error = err?.message || String(err);
        this._renderModal();
      } else this._say(`Fejl: ${err?.message || err}`);
      this._render();
    }
  }

  // Can the plan be updated to settings changed after it was made?
  // "update", "sent" (too late: its list is sent) or "" (nothing changed).
  _canUpdatePlan(plan) {
    const changed = this._state?.settings_changed;
    if (!changed || !plan?.created || plan.kind === "freezer") return "";
    if (new Date(changed) <= new Date(plan.created) || plan.end_date < localToday()) return "";
    return plan.sent_at || (plan.shopping || []).some((line) => line.sent) ? "sent" : "update";
  }

  _updateBanner(plan) {
    const can = this._viewingLatest ? this._canUpdatePlan(plan) : "";
    if (!can) return "";
    if (can === "sent") return `<div class="banner info">Indstillingerne er ændret, efter madplanen blev lavet. Indkøbslisten er sendt, så lav en ny madplan for at bruge ændringerne.</div>`;
    const busy = this._busy || this._state?.status?.state === "generating";
    return `<div class="banner info update-banner"><span>Indstillingerne er ændret, efter madplanen blev lavet. Opdatér den, så beholdes så mange retter som muligt, og kun det nødvendige ændres.</span>
      <button class="btn primary small" data-action="plan-update" data-arg="${esc(plan.id)}" ${busy ? "disabled" : ""}>${aiLabel("Opdater madplan")}</button></div>`;
  }

  _olderBanner() {
    if (this._viewingLatest || !this._plan) return "";
    if (this._plan.kind === "freezer") return `<div class="banner info">${esc(this._plan.title)} <button class="link" data-action="tab" data-arg="plan">Vælg portioner pr. ret</button></div>`;
    return `<div class="banner info">Du ser en ældre madplan (${esc(this._plan.title || "")}). <button class="link" data-action="view-latest">Vis nyeste</button></div>`;
  }

  _recipesView() {
    const seg = `<div class="seg subnav scroll">
        <button class="${this._recipesSub === "week" ? "active" : ""}" data-action="recipes-sub" data-arg="week">Ugens<span class="wide"> opskrifter</span></button>
        <button class="${this._recipesSub === "collection" ? "active" : ""}" data-action="recipes-sub" data-arg="collection"><span class="wide">Opskriftsamling</span><span class="narrow">Samling</span>${this._state.recipes?.length ? ` (${this._state.recipes.length})` : ""}</button>
        ${this._hasPrices() ? `<button class="${this._recipesSub === "offers" ? "active" : ""}" data-action="recipes-sub" data-arg="offers">Tilbud<span class="wide">sretter</span></button>` : ""}
        ${this._isRema() ? `<button class="${this._recipesSub === "rema" ? "active" : ""}" data-action="recipes-sub" data-arg="rema">REMA<span class="wide">-opskrifter</span></button>` : ""}
        <button class="${this._recipesSub === "sites" ? "active" : ""}" data-action="recipes-sub" data-arg="sites">Madsider</button>
      </div>`;
    const view = { collection: () => this._collectionView(), offers: this._hasPrices() ? () => this._candView() : null, rema: this._isRema() ? () => this._remaView() : null, sites: () => this._sitesView() }[this._recipesSub];
    return (view ? "" : this._olderBanner()) + seg + (view ? view() : this._weekRecipesView());
  }

  _weekRecipesView() {
    const list = this._recipeDays();
    if (!list.length) return `<div class="card">Der er ingen madplan endnu.</div>`;
    if (this._wantDate) {
      // A day asked for by the address or a dashboard card.
      const at = list.findIndex((x) => x.day.date === this._wantDate);
      this._day = at >= 0 ? at : this._recipeIndex("");
      this._dayKey = this._recipeKey();
      this._wantDate = null;
    } else if (this._dayKey !== this._recipeKey()) {
      // Today, or the first day if no plan has a dinner today.
      this._day = this._recipeIndex("");
      this._dayKey = this._recipeKey();
    }
    const idx = Math.min(this._day, list.length - 1);
    const { plan, day } = list[idx];
    const key = `${plan.id}|${day.date}`;
    const today = localToday();
    const chips = list
      .map(
        ({ day: d }, i) =>
          `<button class="chip ${i === idx ? "active" : ""}" data-action="day" data-arg="${i}">${plan.kind === "freezer" ? esc(d.dish) : d.date === today ? "I aften" : esc(dateLabel(d.date))}</button>`
      )
      .join("");
    const ingredients = day.ingredients
      .map((ing, i) => {
        const id = `${key}|i${i}`;
        return `<li class="${this._checked[id] ? "done" : ""}" data-action="tick" data-arg="${esc(id)}">
          <span class="box">${this._checked[id] ? "✓" : ""}</span>
          <span class="amount">${esc(ing.amount)}</span> ${esc(ing.name)}</li>`;
      })
      .join("");
    const steps = day.steps
      .map((step, i) => {
        const id = `${key}|s${i}`;
        const timer = step.minutes
          ? this._timers[id]
            ? `<button class="timer running" data-action="timer" data-arg="${esc(id)}|${step.minutes}"><span data-timer="${esc(id)}">${step.minutes}:00</span> ✕</button>`
            : `<button class="timer" data-action="timer" data-arg="${esc(id)}|${step.minutes}">⏱ ${step.minutes} min</button>`
          : "";
        return `<li class="step ${this._checked[id] ? "done" : ""}">
          <div class="step-text" data-action="tick" data-arg="${esc(id)}"><span class="num">${i + 1}</span>${esc(step.text)}</div>
          ${timer}</li>`;
      })
      .join("");
    const type = TYPE_LABELS[day.type] ?? day.type;
    const leftovers = day.uses_leftovers_from
      ? `<div class="banner info">Rester fra ${esc(dateLabel(day.uses_leftovers_from))} – varm op og server.</div>`
      : day.makes_leftovers
        ? `<div class="banner info">Lav dobbelt portion – resten bruges i morgen.</div>`
        : "";
    return `
      <div class="chips">${chips}</div>
      <div class="card recipe">
        <div class="row between wrap">
          <h1>${esc(day.dish || "Ingen ret")}</h1>
          ${this._rateButtons(plan, day)}
        </div>
        <button class="v3-wake${this._wake ? " on" : ""}" data-action="wake" aria-pressed="${this._wake ? "true" : "false"}"><span class="wk-sun">☀</span><span><b>${this._wake ? "Skærmen holdes tændt" : "Hold skærmen tændt"}</b><small>${this._wake ? "Tryk for at slippe den igen" : "Så telefonen ikke går i dvale, mens I laver mad"}</small></span><span class="wk-sw"><i></i></span></button>
        <p class="muted">${plan.kind === "freezer" ? "Fryserret" : esc(dateLabel(day.date))}${day.servings ? ` · ${day.servings} ${plan.kind === "freezer" ? "portioner" : "personer"}` : ""}${day.active_minutes ? ` · ${day.active_minutes} min aktiv` : ""}${day.total_minutes ? ` · ${day.total_minutes} min i alt` : ""}${type ? ` · ${esc(type)}` : ""}</p>
        ${leftovers}
        ${this._inventoryUsage(plan, day)}
        ${day.nutrition
          ? `<p class="nutri">Pr. voksenportion: <b>${Math.round(day.nutrition.kcal)} kcal</b>${["protein_g", "carbs_g", "fat_g"]
              .filter((k) => day.nutrition[k] != null)
              .map((k) => ` · ${Math.round(day.nutrition[k])} g ${{ protein_g: "protein", carbs_g: "kulhydrat", fat_g: "fedt" }[k]}`)
              .join("")}</p>`
          : ""}
        ${day.recipe_error || (!day.steps.length && !day.uses_leftovers_from && day.type !== "rester" && day.type !== "tom" && day.type !== "egen")
          ? `<div class="banner warn">Opskriften kunne ikke laves${day.recipe_error ? `: ${esc(day.recipe_error)}` : ""}
             <button class="btn small" data-action="recipe" ${this._busy ? "disabled" : ""}>${aiLabel("Prøv igen")}</button></div>`
          : ""}
        <div class="recipe-grid">
          <section>
            <h2>Ingredienser</h2>
            <ul class="ingredients">${ingredients || "<li>Ingen</li>"}</ul>
          </section>
          <section>
            <h2>Sådan gør du</h2>
            <ol class="steps">${steps || "<li>Ingen trin</li>"}</ol>
            ${day.tip ? `<p class="tip">💡 ${esc(day.tip)}</p>` : ""}
            <p class="row wrap">${day.mealie ? "" : `<button class="btn small" data-action="recipe" ${this._busy ? "disabled" : ""}>${aiLabel("Lav opskriften igen")}</button>`}
              ${this._mealieButton(plan.id, day.date)}</p>
            ${day.mealie ? '<p class="muted small">Opskriften er jeres egen fra Mealie.</p>' : ""}
          </section>
        </div>
      </div>`;
  }

  _needsReview(line) {
    return ["medium", "low"].includes(line.confidence) && !line.reviewed && !line.must_have && !line.added && !line.sent && !line.skipped;
  }

  // The lines Middagsro is not sure about: what was chosen, what else it could be, and
  // the family's answer (keep, choose another, leave it out).
  _reviewHtml(plan, lines) {
    const unsure = lines.filter((line) => this._needsReview(line));
    if (!unsure.length) return "";
    const mode = this._state?.settings?.uncertain_items || "review";
    const busy = this._busy ? "disabled" : "";
    const items = unsure
      .map((line) => {
        const p = line.product;
        const need = line.amount && line.unit && line.unit !== "pk" ? ` (${esc(`${line.amount} ${line.unit}`)})` : "";
        const alternatives = (line.alternatives || [])
          .filter((a) => !p || a.id !== p.id)
          .slice(0, 4)
          .map(
            (a) => `<button class="alt" data-action="review-choose" data-arg="${esc(line.id)}|${a.id}" ${busy} title="${esc(a.underline || "")}">
              ${a.image ? `<img src="${esc(a.image)}" alt="" loading="lazy">` : ""}<span><b>${esc(a.name)}</b><span class="muted">${esc((a.underline || "").split("/")[0].trim())}${a.price != null ? ` · ${kr(a.price)}` : ""}</span></span></button>`
          )
          .join("");
        return `<li class="review-line">
          <div class="review-what"><b>${esc(line.name)}</b>${need}
            <span class="muted">→ ${p ? `${esc(p.name)}${p.underline ? ` (${esc(p.underline.split("/")[0].trim())})` : ""}${line.packages > 1 ? ` × ${line.packages}` : ""}` : "ingen sikker vare fundet"}</span></div>
          ${alternatives ? `<div class="alts">${alternatives}</div>` : ""}
          <div class="row wrap review-actions">
            ${p ? `<button class="btn small primary" data-action="review-keep" data-arg="${esc(line.id)}" ${busy}>✓ Behold</button>` : ""}
            <button class="btn small" data-action="line-menu" data-arg="${esc(line.id)}" ${busy}>Søg anden vare</button>
            <button class="btn small" data-action="review-have" data-arg="${esc(line.id)}" ${busy} title="Tag varen af listen denne gang – I har den">Har det</button>
            <button class="btn small" data-action="review-skip" data-arg="${esc(line.id)}" ${busy} title="Udelad varen og vælg den ikke til ingrediensen igen">Forkert vare</button>
          </div>
        </li>`;
      })
      .join("");
    return `<div class="banner warn review-banner"><div>
      <b>${unsure.length} ${unsure.length === 1 ? "vare bør tjekkes" : "varer bør tjekkes"}</b> – Middagsro er ikke sikker på, at det er den rigtige vare til ingrediensen.
      ${mode === "review" ? "Listen sendes, når de er tjekket." : mode === "skip" ? "De sendes ikke med, medmindre I beholder eller vælger en vare." : "De sendes som valgt, hvis I ikke retter dem."}
      Jeres valg huskes til næste madplan.
      <ul class="review">${items}</ul>
      ${unsure.length > 1 && unsure.some((l) => l.product) ? `<button class="btn small" data-action="review-keep-all" ${busy}>Behold alle som valgt</button>` : ""}
    </div></div>`;
  }

  _reviewAction(lineId, action, productId, okMessage) {
    const planId = this._plan?.id;
    if (!planId) return;
    return this._editPlan(
      () => this._ws("middagsro/plan/review", { plan_id: planId, line_id: lineId, action, product_id: productId ?? null }),
      okMessage
    );
  }

  _shoppingView() {
    const plan = this._plan;
    const rema = this._state.rema_list;
    let planHtml = `<div class="card">Der er ingen madplan endnu.</div>`;
    if (plan) {
      const groups = {};
      const compare = this._ensureCompare();
      // Sent lines are in the REMA app: the basket here only has what isn't sent yet.
      const lateLines = plan.shopping.filter((line) => line.buy_from && !line.buy_at && !line.sent);
      const mainLines = plan.shopping.filter((line) => !line.buy_from && !line.buy_at && !line.sent);
      mainLines.forEach((line) => (groups[line.category || "Andet"] ||= []).push(line));
      const basketTotal = mainLines.reduce((sum, line) => sum + (line.skipped ? 0 : line.cost || 0), 0);
      const sentCount = plan.shopping.filter((line) => line.sent).length;
      const missingProducts = (plan.missing_products || []).filter((item) =>
        plan.shopping.some((line) => line.id === item.id && !line.sent && !line.product && !line.buy_at));
      // Cheaper elsewhere: only for what is still in the basket.
      const basketSavings = {};
      for (const line of mainLines) {
        const found = compare?.lines?.[line.id];
        if (!found) continue;
        const t = (basketSavings[found.dealer_id] ||= { count: 0, saving: 0 });
        t.count += 1;
        t.saving = Math.round((t.saving + (found.saving || 0)) * 100) / 100;
      }
      const row = (line) => {
              // An offer only sold in the shops (partivare) has the avis's name and price.
              const p = line.product || line.avis_item;
              const badges = [
                p?.is_advertised || p?.is_campaign ? '<span class="badge offer">Tilbud</span>' : "",
                p?.is_organic ? '<span class="badge eco">Øko</span>' : "",
                line.skipped ? `<span class="badge skipped">${line.have ? "Har det" : "Udeladt"}</span>` : this._needsReview(line) ? `<span class="badge doubt">${line.confidence === "low" ? "Tjek" : "Usikker"}</span>` : "",
                line.remembered ? '<span class="badge remembered" title="Den vare I valgte til ingrediensen sidst">Jeres valg</span>' : "",
                line.must_have ? `<span class="badge">${line.use_mode === "lunch" ? "Madpakker" : "Fast vare"}</span>` : "",
                line.buy_from ? `<span class="badge from">Købes ${esc(dayShort(line.buy_from))}</span>` : "",
                line.price_source === "avis" ? '<span class="badge">Avispris</span>' : "",
              ].join("");
              const need = line.amount && line.unit && line.unit !== "pk" ? `${line.amount} ${line.unit}` : "";
              return `<li class="line tappable ${this._isRema() && line.id ? "has-send" : ""} ${line.skipped ? "is-skipped" : ""}" data-action="line-menu" data-arg="${esc(line.id || "")}">
                <span class="limg">${V3.pic(p?.image, V3.groupOf(line.name))}</span>
                <div class="what">
                  <span class="title"><b>${esc(line.must_have || line.added || !line.name ? (p ? V3.clean(p.name) : line.name) : line.name)}</b> ${badges}</span>
                  <span class="muted">${need ? `${esc(need)} · ` : ""}${esc(p ? `${V3.clean(p.name)}${p.underline ? ` · ${p.underline.toLowerCase()}` : ""}` : this._state?.shop?.bilka_cart ? "Vælg en vare" : "Tilføjes som fritekst")}</span>
                  ${line.offer_name ? `<span class="muted">Avisvare: ${esc(line.offer_name)}${line.swapped_from ? ` – i stedet for ${esc(line.swapped_from)}` : ""}</span>` : ""}
                  ${line.note ? `<span class="note">${esc(line.note)}</span>` : ""}
                  ${line.use_note ? `<span class="muted">${esc(line.use_note)}${!line.use_mode ? "" : line.left ? ` – har ${esc(String(line.left).replace(".", ","))} ${esc(line.unit)} tilbage` : line.sent ? "" : " – tryk for at skrive, hvad I har tilbage"}</span>` : ""}
                  ${compare?.lines?.[line.id]
                    ? `<button class="cheaper" data-action="chain-move" data-arg="${esc(line.id)}|${esc(compare.lines[line.id].dealer_id)}"
                        title="Flyt til ${esc(this._chainName(compare.lines[line.id].dealer_id))}-listen">${this._chainLogo(compare.lines[line.id].dealer_id, "tiny")}
                        <span>${esc(compare.lines[line.id].heading)}: spar ${kr(compare.lines[line.id].saving)}</span></button>`
                    : ""}
                </div>
                <div class="cost">${p && p.price != null ? `${line.packages > 1 ? `${line.packages} × ${kr(p.price)}` : ""}<b>${kr(line.cost)}</b>` : line.packages > 1 ? `${line.packages} stk.` : "–"}</div>
                ${this._isRema() && line.id
                  ? `<button class="icon-btn to-rema-line" data-action="send-line" data-arg="${esc(line.id)}" ${this._busy ? "disabled" : ""}
                      title="Læg varen på REMA-listen i appen nu" aria-label="Læg ${esc(p ? p.name : line.name)} på REMA-listen nu">${this._chainLogo(REMA_ID, "tiny")}<span class="plus">+</span></button>`
                  : ""}
              </li>`;
      };
      const sections = Object.entries(groups)
        .map(([category, lines]) => `<h2>${esc(category)}</h2><ul class="lines">${lines.map(row).join("")}</ul>`)
        .join("");
      const lateDay = lateLines[0]?.buy_from;
      const lateTotal = lateLines.reduce((sum, line) => sum + (line.cost || 0), 0);
      const lateHtml = lateLines.length
        ? `<div class="card">
            <div class="row between wrap">
              <div><h1>Indkøb ${esc(lateDay ? dayShort(lateDay) : "senere")}</h1>
              <p class="muted">Tilbud, der først gælder fra ${esc(lateDay ? dayShort(lateDay) : "senere på ugen")}. Send dem til ${this._listName()}, når I skal handle.</p></div>
              <div class="price"><span class="big">${kr(lateTotal)}</span></div>
            </div>
            <ul class="lines">${lateLines.map(row).join("")}</ul>
            ${this._shopSearchHtml("late")}
            <div class="row wrap actions">
              <button class="btn primary" data-action="send" data-arg="late" ${this._busy ? "disabled" : ""}>
                Send ${esc(lateDay ? dayName(lateDay) : "")}svarer til ${this._listName()}</button>
            </div>
          </div>`
        : "";
      const onList = plan.shopping.filter((l) => l.sent && l.on_list).length;
      planHtml = `<div class="card shop-card">
        <div class="row between wrap">
          <div><div class="kicker">${lateLines.length ? "Indkøb på indkøbsdagen" : "Indkøbsliste"} · ${esc(plan.title)}</div><h1>${mainLines.length} ${mainLines.length === 1 ? "vare" : "varer"}</h1>${lateLines.length ? `<p class="muted">plus ${lateLines.length} varer ${esc(dayShort(lateDay))}</p>` : ""}</div>
          <div class="row shop-head">
            ${this._hasPrices()
              ? `<div class="price ${plan.budget && plan.total > plan.budget ? "over" : ""}"><span class="big">${kr(sentCount ? basketTotal : plan.total)}</span>
            <span class="muted">${sentCount ? `hele planen ${kr(plan.total)}` : plan.budget ? `budget ${kr(plan.budget)}` : ""}</span></div>`
              : `<div class="price"><span class="big">${kr(sentCount ? basketTotal : plan.total)}</span>
            <span class="muted" title="${esc(this._shopName())} har kun priser på tilbudsvarerne">tilbudsvarerne</span></div>`}
            <span class="store-badge" title="Butik: ${esc(this._chainName(this._storeId()))}">${this._chainLogo(this._storeId(), "big")}</span>
          </div>
        </div>
        ${sentCount
          ? `<div class="banner info sent-banner"><span>✓ ${sentCount} ${sentCount === 1 ? "vare er sendt" : "varer er sendt"} til ${this._isRema() ? "REMA-appen" : this._state?.shop?.bilka_cart ? this._listName() : "indkøbslisten"}${plan.last_sent?.at ? ` ${esc(sentWhen(plan.last_sent.at))}` : ""} – kurven her har kun det, der ikke er sendt endnu.${onList ? ` ${onList} ${onList === 1 ? "fast vare stod" : "faste varer stod"} der allerede og blev ikke sendt igen.` : ""}</span>
              ${plan.last_sent ? `<button class="btn small" data-action="send-restore" ${this._busy ? "disabled" : ""}>Genskab seneste kurv</button>` : ""}</div>`
          : ""}
        ${missingProducts.length ? `<div class="banner warn"><div><b>${missingProducts.length} ${missingProducts.length === 1 ? "vare mangler" : "varer mangler"} et match</b>
          <ul>${missingProducts.map((item) => `<li>${esc(item.name)}${item.amount && item.unit ? ` (${esc(item.amount)} ${esc(item.unit)})` : ""}</li>`).join("")}</ul>
          <p>Disse varer er ikke sendt. Vælg selv et produkt til dem, der mangler, eller prøv søgningen igen.</p><button class="btn small" data-action="rematch-missing" ${this._busy ? "disabled" : ""}>Søg manglende varer igen</button></div></div>` : ""}
        ${this._reviewHtml(plan, mainLines)}
        ${mainLines.length ? '<p class="muted small">Tryk på en vare for at rette antal, skifte den ud eller slette den.</p>' : '<p class="muted">Kurven er tom. Søg en vare frem nedenfor for at tilføje den.</p>'}
        ${Object.entries(basketSavings)
          .map(
            ([id, t]) => `<div class="banner info chain-save">${this._chainLogo(id)}
              <span><b>${t.count} ${t.count === 1 ? "vare er" : "varer er"} billigere i ${esc(this._chainName(id))}</b> – spar ${kr(t.saving)} Tryk på logoet ved en vare for at købe den der.</span>
              <button class="btn small" data-action="chain-move-all" data-arg="${esc(id)}" ${this._busy ? "disabled" : ""}>Lav ${esc(this._chainName(id))}-liste</button></div>`
          )
          .join("")}
        ${compare?.loading ? '<p class="muted small"><span class="spinner small"></span> Sammenligner med de andre butikkers tilbud …</p>' : ""}
        ${sections}
        ${this._shopSearchHtml("main")}
        <div class="row wrap actions">
          <button class="btn primary" data-action="send" ${this._busy || !mainLines.length ? "disabled" : ""}>
            ${mainLines.length ? `Send ${mainLines.length} ${mainLines.length === 1 ? "vare" : "varer"} til ${this._listName()}` : "Alt er sendt ✓"}</button>
        </div>
        <details class="shopping-tools"><summary>Flere muligheder</summary><div class="row wrap">
          <button class="btn small" data-action="pantry-open">Basisvarer i madplanen</button>
          ${this._hasPrices() ? `<button class="btn small" data-action="plan-rematch" ${this._busy ? "disabled" : ""}
            title="Alle varer, der ikke er sendt, findes igen med de nyeste regler. Retterne og jeres egne valg bliver.">Find varer igen</button>
          <button class="btn small" data-action="plan-record" ${this._busy ? "disabled" : ""}
            title="Gemmer de varer, I har beholdt eller valgt, som en testsag, så varesøgningen kan testes mod dem. Kun ingredienser og varenumre.">Gem som testsag</button>
          <button class="btn small" data-action="links-share" ${this._busy ? "disabled" : ""}
            title="Åbner GitHub med jeres valgte varer (kun ingrediens og varenummer), så alle kan få gavn af dem i den fælles tabel.">Del jeres valg</button>` : ""}
          <button class="btn small" data-action="plan-refresh" ${this._busy ? "disabled" : ""}>Opdatér tilbudspriser</button>
          <button class="btn small" data-action="surplus-stock" ${this._busy || plan.pantry_stocked ? "disabled" : ""}
            title="Det, pakkerne indeholder ud over retternes behov (fx 520 g ris af en 1 kg pose), lægges i spisekammeret efter indkøbet.">${plan.pantry_stocked ? "Overskud er lagt i spisekammeret ✓" : "Læg overskud i spisekammeret"}</button>
          ${!missingProducts.length && this._hasPrices() && plan.shopping.some(line => !line.product && !line.sent && !line.product_id && !line.added && !line.buy_at) ? `<button class="btn small" data-action="rematch-missing" ${this._busy ? "disabled" : ""}>Søg manglende varer igen</button>` : ""}
        </div></details>
      </div>${lateHtml}${this._chainListsHtml(plan)}`;
    }
    const remaItems = rema?.items?.length
      ? rema.items
          .map((i) => `<li class="${i.bought ? "bought" : ""}"><span class="limg">${V3.art(V3.groupOf(i.name), "")}</span><span class="lname"><b>${esc(V3.clean(i.name))}</b><small>${i.amount} stk.${i.bought ? " · købt" : ""}</small></span></li>`)
          .join("")
      : "<li class='muted'>Listen er tom.</li>";
    return `${this._chainsCard()}<div class="shopv">${this._olderBanner()}${this._inventoryUsage(plan, null, true)}${planHtml}</div><div class="v3">${this._v3Compare()}</div><div class="shopv">
      <div class="card">
        <div class="row between wrap">
          <div><div class="kicker">${this._isRema() ? "REMA-appens liste" : "Indkøbslisten"}${rema && this._isRema() ? ` · ${esc(rema.name)}` : ""}</div><h2>${(rema?.items || []).filter((i) => !i.bought).length} på ${this._listName()} lige nu</h2></div>
          <button class="btn small" data-action="clear-list" ${this._busy || !rema?.items?.some((i) => i.bought) ? "disabled" : ""}>Fjern købte varer</button>
        </div>
        <ul class="rema">${remaItems}</ul>
        ${rema && this._isRema() ? `<p class="muted">Anslået pris for det, der mangler: ${kr(rema.total)}</p>` : ""}
        ${!this._isRema() && this._state.settings.ha_todo_entity ? `<p class="muted small">Det, der sendes, kommer også på ${esc(this._hass?.states?.[this._state.settings.ha_todo_entity]?.attributes?.friendly_name || this._state.settings.ha_todo_entity)}.</p>` : ""}
      </div></div>`;
  }

  _productCard(p) {
    const sale = onOffer(p);
    const until = validTo(p.price_valid_to);
    return `<div class="prod">
      ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
      <div class="prod-body">
        <b>${esc(p.name)}</b>
        <span class="muted small">${esc(p.underline || "")}</span>
        <span class="prod-price">
          <b class="${sale ? "sale" : ""}">${kr(p.price)}</b>
          ${sale && p.normal_price && p.normal_price > p.price ? `<s class="muted">${kr(p.normal_price)}</s>` : ""}
        </span>
        <span>${p.is_advertised ? '<span class="badge offer">Avisvare</span>' : sale ? '<span class="badge offer">Tilbud</span>' : ""}
          ${p.is_organic ? '<span class="badge eco">Øko</span>' : ""}
          ${p.offer_from
            ? `<span class="badge from">fra ${esc(dayShort(p.offer_from))}</span>`
            : sale && until ? `<span class="muted small">til ${esc(until)}</span>` : ""}</span>
        ${p.avis ? `<span class="muted small avis">Avis: ${esc(p.avis)}${p.avis_quantity ? ` · ${esc(p.avis_quantity)}` : ""}</span>` : ""}
        ${this._favCheaper(p)}
      </div>
      ${this._bell(p)}
      <button class="btn small primary" data-action="fav-add" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""}>+ Tilføj</button>
    </div>`;
  }

  // A favourite or search result by its product id (for the bell and "Fjern").
  _productById(id) {
    const all = [
      ...Object.values(this._favCache).flatMap((d) => [...(d?.products || []), ...(d?.on_offer || [])]),
      ...this._favSearch.results,
    ];
    return all.find((p) => String(p.id) === String(id)) || null;
  }

  _isWatched(p) {
    return (this._state?.watch || []).some((w) => w.key === `p${p.id}`);
  }

  _bell(p) {
    const on = this._isWatched(p);
    return `<button class="bell ${on ? "on" : ""}" data-action="watch-toggle" data-arg="${esc(p.id)}" aria-pressed="${on}"
      title="${on ? "Overvåges – tryk for at stoppe" : "Overvåg: få besked, når den er på tilbud"}" aria-label="Overvåg ${esc(p.name)}">${BELL_ICON}</button>`;
  }

  async _loadWatch() {
    this._watch = { ...this._watch, loading: true, error: null };
    if (this._tab === "favorites") this._render();
    try {
      const data = await this._ws("middagsro/watch");
      this._watch = { items: data.items, loading: false, error: null };
    } catch (err) {
      this._watch = { items: this._watch.items, loading: false, error: err?.message || String(err) };
    }
    if (this._tab === "favorites") this._render();
  }

  async _watchToggle(item) {
    const body = item.key
      ? item
      : { product_id: item.product_id ?? item.id, text: item.text ?? item.name, underline: item.underline, image: item.image, is_organic: item.is_organic };
    try {
      const res = await this._ws("middagsro/watch/toggle", { item: body });
      this._state.watch = res.watch;
      this._say(res.watched ? `${body.text || body.name} overvåges nu.` : `${body.text || body.name} overvåges ikke længere.`);
      this._render();
      this._loadWatch();
    } catch (err) {
      this._say(`Fejl: ${err?.message || err}`);
    }
  }

  // An offer on the watch list in the basket: REMA's on REMA's list, another chain's on its own list.
  _watchAdd(arg) {
    const [key, idx] = String(arg).split("|");
    const item = (this._watch.items || []).find((w) => w.key === key);
    const deal = item?.deals?.[Number(idx)];
    const plan = this._state?.latest_plan;
    if (!deal) return;
    if (deal.source === "rema") {
      return this._editPlan(
        () => (plan
          ? this._ws("middagsro/plan/add", { plan_id: plan.id, product_id: deal.product_id, part: "main" })
          : this._ws("middagsro/list/add", { product_id: deal.product_id, amount: 1 })),
        `${deal.heading} er lagt i kurven.`
      );
    }
    if (deal.source === "rema_avis") {
      return this._editPlan(() => this._ws("middagsro/chains/rema_add", { offer: deal.offer, plan_id: plan?.id || null }), `${deal.heading} er lagt i kurven.`);
    }
    if (!plan) return this._say("Lav en madplan først – så får hver butik sin egen indkøbsliste.");
    return this._editPlan(
      () => this._ws("middagsro/chains/add", { plan_id: plan.id, offer: deal.offer }),
      `${deal.heading} er sat på ${this._chainName(deal.dealer_id)}-listen under Indkøb.`
    );
  }

  async _favSearchRun() {
    const query = this._favSearch.query.trim();
    if (!query) return;
    this._favSearch = { query, results: [], loading: true };
    this._render();
    try {
      this._favSearch = { query, results: await this._ws("middagsro/search", { query }), loading: false };
    } catch (err) {
      this._favSearch = { query, results: [], loading: false };
      this._say(`Søgningen fejlede: ${err?.message || err}`);
    }
    this._render();
  }

  _watchHtml() {
    const w = this._watch;
    const notify = this._state?.settings?.watch_notify;
    const items = w.items || [];
    const onOffer = items.filter((i) => i.deals.length);
    const quiet = items.filter((i) => !i.deals.length);
    const when = (d) => {
      const from = d.valid_from && localDay(d.valid_from) > localToday() ? `fra ${dayShort(d.valid_from)}` : "";
      return from || (d.valid_to ? `til ${shortDate(localDay(d.valid_to))}` : "");
    };
    const deals = onOffer
      .map(
        (item) => `<div class="watch-item">
          <div class="watch-head"><b>${esc(item.text)}</b>${item.product_id ? "" : ' <span class="badge">Tekst</span>'}
            <button class="bell on" data-action="watch-key" data-arg="${esc(item.key)}" aria-pressed="true" title="Stop overvågning">${BELL_ICON}</button></div>
          <ul class="watch-deals">${item.deals
            .map(
              (d, i) => `<li class="ev">
                ${this._chainLogo(d.dealer_id, "tiny")}
                ${d.image ? `<img src="${esc(d.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
                <div class="what"><b>${esc(d.heading || "")}</b><span class="muted small">${esc([this._chainName(d.dealer_id), d.underline, when(d)].filter(Boolean).join(" · "))}</span></div>
                <span class="ev-price sale">${d.price != null ? kr(d.price) : ""}${d.normal_price && d.price != null && d.normal_price > d.price ? `<s class="muted small">${kr(d.normal_price)}</s>` : ""}</span>
                <button class="btn small" data-action="watch-add" data-arg="${esc(item.key)}|${i}" ${this._busy ? "disabled" : ""}>+ ${d.dealer_id === this._storeId() ? "Kurv" : esc(this._chainName(d.dealer_id))}</button>
              </li>`
            )
            .join("")}</ul>
        </div>`
      )
      .join("");
    return `<div class="card watch-card">
      <div class="row between wrap">
        <h1 class="flush watch-title">${BELL_ICON}Overvågning</h1>
        <button class="btn small" data-action="watch-refresh" ${w.loading ? "disabled" : ""}>${w.loading ? '<span class="spinner small"></span>' : "Opdatér"}</button>
      </div>
      <p class="muted small">Tilbud på det, I overvåger – hos ${esc(this._shopName())} og ${esc((this._state.settings.chains || []).filter((id) => id !== this._storeId()).map((id) => this._chainName(id)).join(", ") || "ingen andre butikker endnu")}.
        ${notify ? "I får besked, når noget nyt kommer på tilbud." : '<button class="link" data-action="settings-open" data-arg="watch">Slå besked til</button>, når noget kommer på tilbud.'}</p>
      ${w.error ? `<div class="banner error">${esc(w.error)}</div>` : ""}
      ${!items.length && !w.loading
        ? `<p class="muted">Intet overvåges endnu. Tryk på ${BELL_ICON.replace("<svg", '<svg class="inline-icon"')} ved en favorit, eller søg nedenfor – også efter ting, REMA ikke har.</p>`
        : ""}
      ${w.loading && !w.items ? '<p class="muted"><span class="spinner small"></span> Leder efter tilbud …</p>' : ""}
      ${deals ? `<div class="watch-list">${deals}</div>` : items.length && !w.loading ? '<p class="muted">Intet af det, I overvåger, er på tilbud lige nu.</p>' : ""}
      ${quiet.length
        ? `<p class="muted small watch-quiet">Ikke på tilbud lige nu: ${quiet
            .map((i) => `<button class="chip" data-action="watch-key" data-arg="${esc(i.key)}" title="Tryk for at stoppe overvågning">${esc(i.text)} ✕</button>`)
            .join(" ")}</p>`
        : ""}
    </div>`;
  }

  _favSearchHtml() {
    const s = this._favSearch;
    const rows = s.loading
      ? '<p class="muted"><span class="spinner small"></span> Søger …</p>'
      : s.results
          .map((p) => {
            const fav = (this._favCache[this._favWeek]?.products || []).some((x) => x.id === p.id);
            return `<li class="fav-row">
              ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
              <div class="what"><b>${esc(p.name)}</b><span class="muted small">${esc(p.underline || "")}</span></div>
              <span class="${onOffer(p) ? "sale" : ""}">${kr(p.price)}</span>
              ${this._bell(p)}
              <button class="btn small" data-action="fav-own-add" data-arg="${esc(p.id)}" ${fav || this._busy ? "disabled" : ""}>${fav ? "Favorit ✓" : "+ Favorit"}</button>
            </li>`;
          })
          .join("");
    return `<div class="card">
      <h2 class="flush">Tilføj en favorit eller noget at overvåge</h2>
      <div class="row wrap">
        <input class="grow" type="search" data-bind="favsearch" value="${esc(s.query)}" placeholder="Søg i REMA 1000, fx kaffe" enterkeyhint="search">
        <button class="btn small" data-action="fav-search">Søg</button>
        ${clearBtn("favsearch")}
      </div>
      ${s.query.trim() ? `<p class="muted small">Har REMA den ikke? <button class="link" data-action="watch-text">Overvåg "${esc(s.query.trim())}" som tekst</button> – så leder Middagsro efter den i alle butikkernes aviser.</p>` : ""}
      ${rows ? `<ul class="favlist">${rows}</ul>` : ""}
    </div>`;
  }

  _favRows() {
    const filter = this._favFilter.trim().toLowerCase();
    const rows = (this._favCache[this._favWeek]?.products || [])
      .filter((p) => !filter || `${p.name} ${p.underline || ""}`.toLowerCase().includes(filter))
      .map(
        (p) => `<li class="fav-row">
          <div class="what"><b>${esc(p.name)}</b><span class="muted small">${esc(p.underline || "")}</span>${this._favCheaper(p)}</div>
          <span class="${onOffer(p) ? "sale" : ""}">${kr(p.price)}</span>
          ${this._bell(p)}
          ${p.own ? `<button class="btn small" data-action="fav-own-remove" data-arg="${esc(p.id)}" title="Fjern fra favoritterne">Fjern</button>` : ""}
          <button class="btn small" data-action="fav-add" data-arg="${esc(p.id)}">+ Tilføj</button>
        </li>`
      )
      .join("");
    return rows || "<li class='muted'>Ingen favoritter matcher.</li>";
  }

  // ------------------------------------------------------------------ the food budget

  _lateDayName() {
    const late = (this._plan?.shopping || []).find((l) => l.buy_from)?.buy_from;
    return late ? dayName(late) : "senere på ugen";
  }

  // The week's budget: what is left, the pace, and booking a purchase (also on the plan tab).
  _budgetCard(compact = false) {
    const b = this._state?.budget;
    if (!b) return "";
    const w = b.week;
    const used = w.available > 0 ? Math.min(100, Math.max(0, (w.spent / w.available) * 100)) : 100;
    const pace = w.available > 0 ? Math.min(100, Math.max(0, (w.pace / w.available) * 100)) : 0;
    const over = w.remaining < 0;
    const ahead = !over && w.spent > w.pace * 1.1;
    const next = (b.purchases || []).length ? "" : '<p class="muted small">Kontér det, I handler for, så holder Middagsro øje med ugen og måneden.</p>';
    const plannedNote = w.planned > 0
      ? `<div class="banner ${w.after_planned < 0 ? "warn" : "info"} small">Resten af ugens lister er anslået til ${kr0(w.planned)}. ${w.after_planned < 0 ? `Det er ${kr0(-w.after_planned)} mere, end der er tilbage.` : `Så er der ${kr0(w.after_planned)} til resten.`}</div>`
      : "";
    return `<div class="card budget-card">
      <div class="muted small">Ugens madbudget · uge ${w.week} · ${esc(shortDate(w.start))}–${esc(shortDate(w.end))}</div>
      <div class="budget-left"><span class="big ${over ? "over" : ""}">${kr0(Math.abs(w.remaining))}</span>
        <span class="muted">${over ? "over budgettet" : `tilbage · ${kr0(Math.max(0, w.per_day))} om dagen`}</span></div>
      <div class="budget-bar ${over ? "over" : ahead ? "ahead" : ""}" role="img" aria-label="Brugt ${kr0(w.spent)} af ${kr0(w.available)}">
        <span style="width:${used.toFixed(1)}%"></span><i style="left:${pace.toFixed(1)}%" title="Jævnt forbrug til og med i dag"></i></div>
      <div class="row between muted small"><span>Brugt ${kr0(w.spent)} af ${kr0(w.available)}</span><span>${over ? "" : ahead ? "Foran tempoet" : "I tempo"}</span></div>
      ${Math.abs(w.carry) >= 1 ? `<div class="muted small">${w.carry > 0 ? `Heraf ${kr0(w.carry)} sparet i tidligere uger` : `${kr0(-w.carry)} trukket fra – brugt for meget tidligere`} i ${MONTHS_SHORT[Number(w.start.slice(5, 7)) - 1]}.</div>` : ""}
      ${plannedNote}
      <div id="budget-book">${this._bookForm()}</div>
      ${next}
      ${compact ? `<div class="row"><button class="link" data-action="tab" data-arg="budget">Se økonomien</button>${(b.purchases || []).length ? '<button class="link" data-action="budget-purchases">Ret eller slet et køb</button>' : ""}</div>` : ""}
    </div>`;
  }

  _bookForm() {
    const chains = [this._storeId(), ...(this._state.settings.chains || []).filter((id) => id !== this._storeId()), "other"];
    const chip = (id) => `<button class="chip ${(this._book.store || this._storeId()) === id ? "active" : ""}" data-action="budget-store" data-arg="${esc(id)}">${id === "other" ? "Andet" : esc(this._chainName(id))}</button>`;
    // The list just sent is what was bought: offer its price.
    const sent = (this._plan?.shopping || []).filter((l) => l.sent && String(l.sent).slice(0, 10) === localToday());
    const suggestion = sent.reduce((sum, l) => sum + (Number(l.cost) || 0), 0);
    return `<div class="book">
        <label class="field">Beløb (kr.)<input type="text" inputmode="decimal" data-bind="book" data-field="amount" value="${esc(this._book.amount)}" placeholder="Fx 450" aria-label="Beløb"></label>
        <label class="field">Dato<input type="date" data-bind="book" data-field="date" value="${esc(this._book.date || localToday())}" max="${localToday()}" aria-label="Dato"></label>
        <button class="btn primary" data-action="budget-book">Kontér</button>
      </div>
      <div class="book-stores">${chains.map(chip).join("")}</div>
      ${suggestion > 0 && !this._book.amount ? `<button class="link small" data-action="budget-suggest" data-arg="${suggestion}">Brug dagens sendte liste: ${kr0(suggestion)}</button>` : ""}`;
  }

  _renderBudgetForms() {
    this.shadowRoot.querySelectorAll("#budget-book").forEach((n) => (n.innerHTML = this._bookForm()));
  }

  _budgetView() {
    const b = this._state.budget;
    if (!b) {
      return `<div class="card"><h2 class="flush">Madbudget</h2>
        <p>Skriv jeres faste beløb til indkøb pr. måned eller pr. uge. Så kan I kontere hvert køb, se hvad der er tilbage af ugen, og madplanen holder sig inden for det.</p>
        <div class="seg fit"><button class="${this._book.period !== "week" ? "active" : ""}" data-action="budget-period" data-arg="month">Pr. måned</button>
          <button class="${this._book.period === "week" ? "active" : ""}" data-action="budget-period" data-arg="week">Pr. uge</button></div>
        <div class="row wrap"><input class="grow" type="text" inputmode="numeric" data-bind="book" data-field="monthly" value="${esc(this._book.monthly)}" placeholder="${this._book.period === "week" ? "Fx 1200" : "Fx 5000"}">
          <button class="btn primary" data-action="budget-setup">Start madbudget</button></div></div>
        <div class="v3">${this._v3Rhythm()}${this._v3SpendCard()}${this._v3Story()}</div>`;
    }
    const m = b.month;
    const span = this._budgetSpan;
    const seg = `<div class="seg subnav">
      <button class="${span === "month" ? "active" : ""}" data-action="budget-view" data-arg="month">Måned</button>
      <button class="${span === "weeks" ? "active" : ""}" data-action="budget-view" data-arg="weeks">Uger</button>
      <button class="${span === "year" ? "active" : ""}" data-action="budget-view" data-arg="year">År</button>
      <button class="${span === "purchases" ? "active" : ""}" data-action="budget-view" data-arg="purchases">Køb</button></div>`;
    const body = { month: () => this._budgetMonth(b), weeks: () => this._budgetWeeks(b), year: () => this._budgetYear(b), purchases: () => this._budgetPurchases(b) }[span]?.() || "";
    const forecastDiff = m.forecast - m.budget;
    return `<div class="v3">${this._v3BudgetCard()}${this._v3Rhythm()}${this._v3SpendCard()}${this._v3Story()}</div>
      <h2 class="v3-section">Måned, uger og år</h2>
      <div class="stats">
        <div class="stat"><span class="muted small">Brugt i ${MONTHS_SHORT[Number(m.first.slice(5, 7)) - 1]}.</span><b>${kr0(m.spent)}</b><span class="muted small">af ${kr0(m.budget)}</span></div>
        <div class="stat"><span class="muted small">Prognose</span><b class="${forecastDiff > 0 ? "over" : "ok"}">${kr0(m.forecast)}</b><span class="muted small">${forecastDiff > 0 ? `${kr0(forecastDiff)} over` : `${kr0(-forecastDiff)} under`}</span></div>
      </div>
      ${seg}${body}`;
  }

  _receiptLoginsSettings() {
    const r = this._state.receipts || {};
    const logins = r.logins || [];
    const max = r.max_logins || 4;
    const d = this._rl;
    const full = logins.length >= max;
    const rows = logins
      .map(
        (l) => `<div class="row between wrap rowitem">
          <div><b>${esc(l.label || l.email)}</b><span class="muted small"> · ${esc(l.email)}${l.count ? ` · ${l.count} kvitteringer` : ""}</span></div>
          <button class="btn small danger" data-action="rl-remove" data-arg="${esc(l.id)}" ${this._busy ? "disabled" : ""}>Fjern</button>
        </div>`
      )
      .join("");
    return `<h3>Flere REMA-konti til kvitteringer</h3>
      <p class="muted small">Tilføj husstandens andre REMA 1000-logins (op til ${max} ekstra). Deres kvitteringer hentes også og konteres i Økonomi, så alle jeres REMA-køb tæller med. Bruges kun til kvitteringer – ikke indkøbslister, favoritter eller madplaner.</p>
      ${rows ? `<div class="rl-list">${rows}</div>` : ""}
      ${
        full
          ? `<p class="muted small">Grænsen på ${max} ekstra konti er nået.</p>`
          : `<div class="row wrap rl-form">
          <input class="grow" type="email" autocomplete="off" data-bind="rl" data-field="email" value="${esc(d.email)}" placeholder="E-mail">
          <input class="grow" type="password" autocomplete="new-password" data-bind="rl" data-field="password" value="${esc(d.password)}" placeholder="Adgangskode">
          <input class="grow" type="text" data-bind="rl" data-field="label" value="${esc(d.label)}" placeholder="Navn (fx Katrine)">
          <button class="btn primary" data-action="rl-add" ${this._busy ? "disabled" : ""}>${this._busy ? '<span class="spinner small"></span>' : "Tilføj konto"}</button>
        </div>`
      }`;
  }

  _spendLabel(span, key) {
    if (span === "week") return `u.${Number(key.slice(6))}`;
    if (span === "year") return key;
    return `${MONTHS_SHORT[Number(key.slice(5, 7)) - 1]} ${key.slice(2, 4)}`;
  }

  _spendOverview() {
    const ov = this._state.receipts && this._state.receipts.overview;
    if (!ov || !this._isRema()) return "";
    const span = ["week", "month", "year"].includes(this._spendSpan) ? this._spendSpan : "month";
    const g = ov[span];
    const seg = `<div class="seg subnav">${[["week", "Uge"], ["month", "Måned"], ["year", "År"]]
      .map(([k, l]) => `<button class="${span === k ? "active" : ""}" data-action="spend-span" data-arg="${k}">${l}</button>`)
      .join("")}</div>`;
    if (!g || !g.buckets.length) {
      return `<div class="card spend-card"><h2 class="flush">REMA-forbrug</h2>
        ${seg}
        <p class="muted">Når der er kvitteringer, vises dit REMA 1000-forbrug her pr. uge, måned og år – med højeste, laveste, gennemsnit og hvor meget du har sparet på tilbud.</p></div>`;
    }
    const buckets = g.buckets;
    const n = buckets.length;
    const max = Math.max(...buckets.map((x) => x.spent), 1);
    const W = 324, H = 148, L = 6, Rt = 318, T = 10, B = 120;
    const step = (Rt - L) / n;
    const bw = Math.max(5, step * 0.62);
    const everyLabel = n <= 13 ? 1 : Math.ceil(n / 8);
    const per = span === "week" ? "uge" : span === "month" ? "måned" : "år";
    const bars = buckets
      .map((bk, i) => {
        const h = ((B - T) * bk.spent) / max;
        const x = L + step * i + (step - bw) / 2;
        const y = B - h;
        const lab = this._spendLabel(span, bk.key);
        const text = i % everyLabel === 0 || i === n - 1
          ? `<text x="${(x + bw / 2).toFixed(1)}" y="${H - 5}" class="axis" text-anchor="middle">${esc(lab)}</text>`
          : "";
        return `<g class="spend-bar" style="--d:${(i * 0.03).toFixed(2)}s">
          <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" rx="3"><title>${esc(lab)}: ${kr0(bk.spent)}${bk.saved ? ` · sparet ${kr0(bk.saved)}` : ""} · ${bk.count} ${bk.count === 1 ? "køb" : "køb"}</title></rect>
          ${text}</g>`;
      })
      .join("");
    const stat = (label, value, sub) => `<div class="stat"><span class="muted small">${label}</span><b>${value}</b><span class="muted small">${sub}</span></div>`;
    return `<div class="card spend-card">
      <h2 class="flush">REMA-forbrug</h2>
      ${seg}
      <div class="stats spend-stats">
        ${stat("Højeste", g.high ? kr0(g.high.spent) : "–", g.high ? esc(this._spendLabel(span, g.high.key)) : "")}
        ${stat("Laveste", g.low ? kr0(g.low.spent) : "–", g.low ? esc(this._spendLabel(span, g.low.key)) : "")}
        ${stat("Gennemsnit", kr0(g.avg), `pr. ${per}`)}
        ${`<div class="stat save-stat"><span class="muted small">Sparet på tilbud</span><b>${kr0(g.saved_total)}</b><span class="muted small">i alt</span></div>`}
      </div>
      <svg class="spend-chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="REMA-forbrug pr. ${per}">${bars}</svg>
      <p class="muted small">Kun REMA 1000-kvitteringer. Viser de seneste ${n} ${per === "år" ? "år" : per + "er"}.</p>
    </div>`;
  }

  _budgetMonth(b) {
    const m = b.month;
    const W = 320, H = 150, L = 8, R = 312, T = 10, B = 128;
    const max = Math.max(m.budget, m.forecast, m.series.at(-1) || 0) * 1.05 || 1;
    const x = (day) => L + ((R - L) * (day - 1)) / Math.max(1, m.days - 1);
    const y = (v) => B - ((B - T) * v) / max;
    const points = m.series.map((v, i) => `${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
    const today = m.series.length;
    const last = m.series.at(-1) || 0;
    const s = b.stats;
    const stat = (label, value, note = "") => `<div class="stat"><span class="muted small">${label}</span><b>${value}</b>${note ? `<span class="muted small">${note}</span>` : ""}</div>`;
    const trips = (s.trips || []).map((t) => stat(`Snit ${t.weekday}`, kr0(t.average), `${t.count} ture`)).join("");
    const stores = (s.stores || []).map((st) => `<li><span>${st.store === "other" ? "Andet" : esc(this._chainName(st.store))}</span><b>${kr0(st.amount)}</b></li>`).join("");
    return `<div class="card">
      <svg class="budget-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Månedens forbrug mod budgettet">
        <line x1="${L}" y1="${y(m.budget)}" x2="${R}" y2="${y(m.budget)}" class="budget-top"/>
        <text x="${L}" y="${y(m.budget) - 4}" class="axis">${kr0(m.budget)}</text>
        <line x1="${L}" y1="${y(0)}" x2="${R}" y2="${y(m.budget)}" class="budget-line"/>
        <polyline points="${points}" class="spent-line"/>
        <line x1="${x(today)}" y1="${y(last)}" x2="${R}" y2="${y(m.forecast)}" class="forecast-line"/>
        <circle cx="${x(today)}" cy="${y(last)}" r="4" class="spent-dot"/>
        <text x="${L}" y="${H - 4}" class="axis">1.</text><text x="${R}" y="${H - 4}" class="axis" text-anchor="end">${m.days}.</text>
        <text x="${x(today)}" y="${H - 4}" class="axis" text-anchor="middle">i dag</text>
      </svg>
      <p class="muted small legend"><span class="key spent"></span>Brugt <span class="key budget"></span>Jævnt forbrug <span class="key forecast"></span>Prognose${m.planned ? ` – heraf ${kr0(m.planned)} på madplanernes lister` : ""}</p></div>
      <div class="stats">
        ${trips}
        ${s.extra_trips != null ? stat("Ekstra ture (90 dage)", String(s.extra_trips), s.extra_average ? `snit ${kr0(s.extra_average)}` : "") : ""}
        ${s.per_portion_day != null ? stat("Pr. voksen pr. dag", kr0(s.per_portion_day), "børn tæller mindre") : ""}
        ${s.saved_on_offers > 0 ? stat("Sparet på tilbud", kr0(s.saved_on_offers), "på månedens sendte lister") : ""}
        ${s.outside_lists != null ? stat("Ud over madplanen", kr0(s.outside_lists), "konteret minus sendte lister") : ""}
      </div>
      ${stores ? `<div class="card"><h3 class="flush">Butikker (90 dage)</h3><ul class="kv">${stores}</ul></div>` : ""}`;
  }

  _budgetWeeks(b) {
    const weeks = b.weeks || [];
    if (!weeks.length) return '<div class="card muted">Ingen uger endnu.</div>';
    const max = Math.max(...weeks.map((w) => Math.max(w.spent, w.budget))) * 1.1 || 1;
    const W = 320, H = 150, B = 128, gap = 6;
    const bw = (W - gap * (weeks.length + 1)) / weeks.length;
    const bars = weeks.map((w, i) => {
      const h = (B - 10) * (w.spent / max);
      const x = gap + i * (bw + gap);
      const cls = w.spent > w.budget ? "over" : w.current ? "current" : "ok";
      return `<rect x="${x.toFixed(1)}" y="${(B - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" rx="3" class="bar ${cls}"><title>Uge ${w.week}: ${kr0(w.spent)} af ${kr0(w.budget)}</title></rect>
        <text x="${(x + bw / 2).toFixed(1)}" y="${H - 6}" class="axis" text-anchor="middle">${w.week}</text>`;
    }).join("");
    const budgetY = B - (B - 10) * ((weeks.at(-1)?.budget || 0) / max);
    const done = weeks.filter((w) => !w.current);
    const avg = done.length ? done.reduce((s, w) => s + w.spent, 0) / done.length : null;
    const overCount = done.filter((w) => w.spent > w.budget).length;
    return `<div class="card">
      <svg class="budget-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Forbrug pr. uge mod ugebudgettet">
        <line x1="0" y1="${budgetY.toFixed(1)}" x2="${W}" y2="${budgetY.toFixed(1)}" class="budget-line"/>${bars}
      </svg>
      <p class="muted small legend"><span class="key spent"></span>Under budget <span class="key over"></span>Over <span class="key budget"></span>Ugebudget</p></div>
      <div class="stats">
        ${avg != null ? `<div class="stat"><span class="muted small">Snit pr. uge</span><b>${kr0(avg)}</b></div>` : ""}
        <div class="stat"><span class="muted small">Uger over budget</span><b>${overCount} af ${done.length}</b></div>
      </div>`;
  }

  _budgetYear(b) {
    const y = b.year;
    const months = y.months;
    const current = Number(b.month.first.slice(5, 7));
    const max = Math.max(...months.map((m) => Math.max(m.spent || 0, m.budget || 0))) * 1.1 || 1;
    const W = 320, H = 150, B = 128, gap = 4;
    const bw = (W - gap * 13) / 12;
    const bars = months.map((m, i) => {
      const x = gap + i * (bw + gap);
      const h = m.spent != null ? (B - 10) * (m.spent / max) : 0;
      const bh = m.budget != null ? (B - 10) * (m.budget / max) : 0;
      const cls = m.spent != null && m.budget != null && m.spent > m.budget ? "over" : m.month === current ? "current" : "ok";
      return `${m.budget != null ? `<rect x="${x.toFixed(1)}" y="${(B - bh).toFixed(1)}" width="${bw.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" class="bar ghost"/>` : ""}
        ${m.spent != null ? `<rect x="${x.toFixed(1)}" y="${(B - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" class="bar ${cls}"><title>${MONTHS_SHORT[i]}: ${kr0(m.spent)}</title></rect>` : ""}
        <text x="${(x + bw / 2).toFixed(1)}" y="${H - 6}" class="axis" text-anchor="middle">${MONTHS_SHORT[i][0].toUpperCase()}</text>`;
    }).join("");
    const done = months.filter((m) => m.spent != null && m.month < current);
    const best = done.length > 1 ? done.reduce((a, c) => (c.spent < a.spent ? c : a)) : null;
    return `<div class="card">
      <svg class="budget-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Forbrug pr. måned i ${y.year}">${bars}</svg>
      <p class="muted small legend"><span class="key spent"></span>Brugt <span class="key ghost"></span>Budget</p></div>
      <div class="stats">
        <div class="stat"><span class="muted small">${y.year} indtil nu</span><b>${kr0(y.spent)}</b><span class="muted small">af ${kr0(y.budget)} for året</span></div>
        ${y.average != null ? `<div class="stat"><span class="muted small">Snit pr. måned</span><b>${kr0(y.average)}</b></div>` : ""}
        ${best ? `<div class="stat"><span class="muted small">Billigste måned</span><b>${MONTHS_SHORT[best.month - 1]}.</b><span class="muted small">${kr0(best.spent)}</span></div>` : ""}
      </div>`;
  }

  _budgetPurchases(b) {
    const rows = (b.purchases || []).map(
      (p) => `<li class="purchase">
        ${this._chainLogo(p.store === "other" ? "?" : p.store, "tiny")}
        <button class="what plain" data-action="purchase-edit" data-arg="${esc(p.id)}" aria-label="Ret købet på ${esc(kr0(p.amount))}"><b>${kr0(p.amount)}</b><span class="muted small">${esc(dateLabel(p.date))} · ${esc(p.store === "other" ? p.note || "Andet" : this._chainName(p.store))}${p.note && p.store !== "other" ? ` · ${esc(p.note)}` : ""}${p.source === "action" ? " · automatisk" : ""}</span></button>
        <button class="icon-btn" data-action="purchase-delete" data-arg="${esc(p.id)}" aria-label="Slet købet">${CLOSE_ICON}</button></li>`
    ).join("");
    return `<div class="card"><h3 class="flush">De seneste to måneder</h3><p class="muted small">Tryk på et køb for at rette eller slette det.</p>${rows ? `<ul class="purchases">${rows}</ul>` : '<p class="muted">Ingen køb konteret endnu.</p>'}</div>`;
  }

  _favoritesView() {
    // Another shop has no favourites in an app: the watch list, and something to watch.
    if (!this._isRema()) {
      const q = this._favSearch.query;
      return `<div class="v3 favv">${this._watchHtml()}
        <div class="card">
          <h2 class="flush">Overvåg en vare</h2>
          <p class="muted small">Skriv, hvad I gerne vil have besked om, når det kommer på tilbud – fx kaffe eller laks. Middagsro leder i ${esc(this._shopGen())} og jeres andre butikkers aviser.</p>
          <div class="row wrap">
            <input class="grow" type="search" data-bind="favsearch" value="${esc(q)}" placeholder="Fx kaffe" enterkeyhint="done">
            <button class="btn small primary" data-action="watch-text">Overvåg</button>
          </div>
        </div></div>`;
    }
    const week = this._favWeek;
    const data = this._favCache[week];
    const seg = `<div class="seg" role="tablist">${[["current", "Denne uge"], ["next", "Næste uge"]]
      .map(([key, label]) => `<button role="tab" aria-selected="${key === week}" class="${key === week ? "active" : ""}" data-action="fav-week" data-arg="${key}">${label}</button>`)
      .join("")}</div>`;
    let body;
    if (this._favsLoading && !data) {
      body = `<p class="center muted"><span class="spinner"></span> Tjekker dine favoritter mod tilbudsavisen …</p>`;
    } else if (this._favsError && !data) {
      body = `<h2>Favoritterne kunne ikke hentes</h2><p>${esc(this._favsError)}</p>
        <button class="btn" data-action="fav-refresh">Prøv igen</button>`;
    } else {
      const offers = data?.on_offer || [];
      const cat = data?.catalog;
      const next = week === "next" && !data?.fallback;
      const from = next && cat?.valid_from ? ` fra ${esc(shortDate(localDay(cat.valid_from)))}` : "";
      body = `
        ${data?.fallback ? '<div class="banner info">Næste uges avis er ikke udkommet endnu – her er denne uges tilbud indtil da.</div>' : ""}
        <h2>${next ? `På tilbud${from}` : "På tilbud nu"} (${offers.length})</h2>
        ${offers.length
          ? `<div class="pgrid">${offers.map((p) => this._productCard(p)).join("")}</div>`
          : `<p class="muted">Ingen af dine favoritter er på tilbud ${next ? "i næste uge" : "lige nu"}.</p>`}`;
    }
    const count = data?.products?.length;
    return `<div class="v3 favv">${this._watchHtml()}
      <div class="card">
        <div class="row between wrap">
          <div><div class="kicker">Dine favoritter</div><h1>${data?.on_offer && count != null ? `${data.on_offer.length} af jeres ${count} favoritter er på tilbud` : "Dine favoritter"}</h1>
          <p class="muted">Varer med hjerte i REMA 1000-appen og dem, I har tilføjet her${count != null ? ` – ${count} i alt` : ""}. Tryk på klokken for at overvåge en vare.</p></div>
          <button class="btn small" data-action="fav-refresh" ${this._favsLoading ? "disabled" : ""}>
            ${this._favsLoading ? '<span class="spinner small"></span>' : "Opdatér"}</button>
        </div>
        ${seg}
        ${body}
      </div>
      <div class="card">
        <details>
          <summary>Alle favoritter (${count ?? 0})</summary>
          <div class="row wrap"><input class="grow filter" type="search" data-bind="favfilter" value="${esc(this._favFilter)}" placeholder="Filtrér, fx mælk">${clearBtn("favfilter")}</div>
          <ul class="favlist" id="fav-all">${this._favRows()}</ul>
        </details>
      </div>
      ${this._favSearchHtml()}</div>`;
  }

  _historyView() {
    // Receipts and the item list are a REMA 1000 extra; other shops only have
    // the meal-plan history, so there are no tabs for them.
    if (!this._isRema()) return this._plansHistoryView();
    const sub = ["indkob", "plans", "varer"].includes(this._histSub) ? this._histSub : "indkob";
    const seg = `<div class="seg subnav">
        <button class="${sub === "indkob" ? "active" : ""}" data-action="hist-sub" data-arg="indkob">Indkøb</button>
        <button class="${sub === "plans" ? "active" : ""}" data-action="hist-sub" data-arg="plans">Madplaner</button>
        <button class="${sub === "varer" ? "active" : ""}" data-action="hist-sub" data-arg="varer">Varer</button>
      </div>`;
    const body = { indkob: () => this._receiptsView(), plans: () => this._plansHistoryView(), varer: () => this._itemsView() }[sub]();
    return seg + body;
  }

  _plansHistoryView() {
    const plans = this._state.plans;
    if (!plans.length) return `<div class="card">Der er ingen tidligere madplaner.</div>`;
    const rows = plans
      .map(
        (p) => `<li class="hist">
          <div class="what" data-action="view-plan" data-arg="${esc(p.id)}">
            <b>${esc(p.title)}</b>
            <span class="muted">${esc(dateLabel(p.start_date))} – ${esc(dateLabel(p.end_date))} · ${kr(p.total)}</span>
            <span class="muted small">${esc(p.dishes.join(" · "))}</span>
          </div>
          <span class="badge ${p.status}">${esc(STATUS_LABELS[p.status] || p.status)}</span>
          <button class="btn small" data-action="view-plan" data-arg="${esc(p.id)}">Vis</button>
          <button class="btn small danger" data-action="delete-plan" data-arg="${esc(p.id)}">Slet</button>
        </li>`
      )
      .join("");
    return `<div class="card"><h1>Historik</h1><ul class="history">${rows}</ul></div>`;
  }

  _receiptsView() {
    if (this._receiptId) return this._receiptDetailView();
    const data = this._state.receipts;
    const list = (data && data.list) || [];
    if (!list.length) {
      return `<div class="card"><h1>Indkøb</h1>
        <p class="muted">Der er ingen kvitteringer endnu. De hentes fra REMA 1000-appens “Scan Selv”, og de nyeste dukker op her af sig selv.</p></div>`;
    }
    const rows = list
      .map(
        (r) => this._v3ReceiptRow(r)
      )
      .join("");
    return `<div class="v3"><div class="card"><div class="kicker">Indkøb</div><h2>${list.length} kvitteringer fra REMA 1000</h2>
      <p class="sub">Tryk på en kvittering for at se bonen.</p>
      <div class="hlist">${rows}</div></div></div>`;
  }

  _receiptDetailView() {
    const back = `<div class="row"><button class="link" data-action="receipt-back">‹ Alle kvitteringer</button></div>`;
    if (this._receiptLoading && !this._receipt) {
      return `${back}<div class="card center"><span class="spinner"></span> Henter kvittering …</div>`;
    }
    const r = this._receipt;
    if (!r) {
      return `${back}<div class="card"><p class="muted">Kvitteringen kunne ikke hentes.</p></div>`;
    }
    const s = r.store || {};
    const line2 = [s.address2].filter(Boolean);
    const addr = [s.address, [s.zip, s.city].filter(Boolean).join(" ")].filter(Boolean);
    const right = [
      longDate(r.date),
      clockTime(r.date),
      s.phone ? `TLF: ${esc(s.phone)}` : "",
      s.cvr ? `CVR: ${esc(s.cvr)}` : "",
    ].filter(Boolean);
    const itemRows = (r.items || [])
      .map((it) => {
        const qty = it.quantity && it.quantity > 1;
        // REMA's line price is one piece's: the line costs the price times how many.
        const unit = qty && it.price != null ? it.price : null;
        const lineTotal = it.price != null ? it.price * (it.quantity || 1) : null;
        return `<div class="rc-line">
          <div class="rc-name">${esc(it.name)}${qty ? ` <span class="rc-qty">${it.quantity} á ${unit != null ? unit.toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "?"}</span>` : ""}</div>
          <div class="rc-price">${lineTotal != null ? lineTotal.toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ""}</div>
          ${it.discount ? `<div class="rc-disc">Rabat per stk. <span>${Number(it.discount).toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>` : ""}
        </div>`;
      })
      .join("");
    const num = (v) => (v == null ? "" : Number(v).toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    const pay = r.card_type || "BETALT";
    return `${back}
      <div class="card receipt-paper">
        <div class="rc-head">REMA 1000</div>
        <div class="rc-store">
          <div class="rc-store-left">
            <b>${esc(s.name || "REMA 1000")}</b>
            ${line2.map((l) => `<div>${esc(l)}</div>`).join("")}
            ${addr.map((l) => `<div>${esc(l)}</div>`).join("")}
          </div>
          <div class="rc-store-right">${right.map((l) => `<div>${l}</div>`).join("")}</div>
        </div>
        <div class="rc-items">${itemRows}</div>
        <div class="rc-total"><span>Total</span><span>${num(r.total)}</span></div>
        ${r.total_vat != null ? `<div class="rc-sub muted"><span>Heraf moms</span><span>${num(r.total_vat)}</span></div>` : ""}
        <div class="rc-foot">
          <div class="rc-sub"><span>${esc(pay)}</span><span>${num(r.total)}</span></div>
          ${r.gross != null ? `<div class="rc-sub"><span>BRUTTOSUBTOTAL</span><span>${num(r.gross)}</span></div>` : ""}
          ${r.total_discount ? `<div class="rc-sub rc-save"><span>RABAT TOTAL</span><span>-${num(r.total_discount)}</span></div>` : ""}
        </div>
        <div class="rc-bon muted small">Bon ID:<br>${esc(r.id)}</div>
      </div>`;
  }

  _itemsView() {
    const data = this._state.receipts;
    const items = (data && data.items) || [];
    if (!items.length) {
      return `<div class="card"><h1>Varer</h1>
        <p class="muted">Når der er kvitteringer, vises alle købte varer her – med antal købt, laveste og højeste pris.</p></div>`;
    }
    const totalBought = items.reduce((sum, i) => sum + (i.count || 0), 0);
    const most = items[0];
    const filter = this._itemFilter.trim().toLowerCase();
    const shown = (filter ? items.filter((i) => i.name.toLowerCase().includes(filter)) : items).slice(0, 500);
    const rows = shown
      .map(
        (i) => `<li class="hist item-row${i.frequent ? " frequent" : ""}">
          <div class="what">
            <b>${i.frequent ? '<span class="star" title="Købt mere end 5 gange">★</span> ' : ""}${esc(i.name)}</b>
            <span class="muted small">${i.times} køb${i.last_date ? ` · sidst ${esc(longDate(i.last_date))}` : ""}${i.last_price != null ? ` · ${kr(i.last_price)}` : ""}</span>
          </div>
          <div class="item-stats">
            <span class="count">${i.count}×</span>
            <span class="muted small">${priceRange(i.min_price, i.max_price)}</span>
          </div>
        </li>`
      )
      .join("");
    return `${this._v3TopItems()}<div class="card"><h1>Alle varer</h1>
      <div class="stats">
        <div class="stat"><span class="muted small">Forskellige varer</span><b>${items.length}</b></div>
        <div class="stat"><span class="muted small">Købt i alt</span><b>${totalBought}</b></div>
        <div class="stat"><span class="muted small">Mest købt</span><b class="ell">${esc(most.name)}</b><span class="muted small">${most.count}×</span></div>
      </div>
      <div class="row wrap"><input class="grow filter" type="search" data-bind="itemfilter" value="${esc(this._itemFilter)}" placeholder="Filtrér, fx mælk">${clearBtn("itemfilter")}</div>
      <ul class="history items-list">${rows}</ul>
      ${shown.length >= 500 ? `<p class="muted small">Viser de 500 mest købte.</p>` : ""}
    </div>`;
  }

  _settingsView() {
    const f = this._form;
    const opts = this._state.options;
    const check = (list, key, labels) =>
      `<label class="check"><input type="checkbox" data-list="${list}" value="${key}" ${(f[list] || []).includes(key) ? "checked" : ""}> ${esc(labels[key] || key)}</label>`;
    const weekdaySelect = (path, value) =>
      `<select data-path="${path}" data-type="number">${WEEKDAYS.map((d, i) => `<option value="${i}" ${Number(value) === i ? "selected" : ""}>${d}</option>`).join("")}</select>`;
    const num = (path, value, min = 0, max = 999) =>
      `<input type="number" data-path="${path}" data-type="number" min="${min}" max="${max}" value="${esc(value)}">`;
    // AI Tasks first; conversation agents (LiteLLM and others without an AI Task) after.
    const aiOption = (e) => `<option value="${esc(e.entity_id)}" ${f.ai_task_entity === e.entity_id ? "selected" : ""}>${esc(e.name)}</option>`;
    const aiGroup = (kind, label) => {
      const list = (this._state.ai_entities || []).filter((e) => (e.kind || "ai_task") === kind);
      return list.length ? `<optgroup label="${label}">${list.map(aiOption).join("")}</optgroup>` : "";
    };
    const ai = aiGroup("ai_task", "AI-opgaver") + aiGroup("agent", "Samtaleagenter");
    const household = f.household
      .map(
        (m, i) => `<div class="row wrap rowitem">
          <select data-path="household.${i}.role">
            <option value="adult" ${m.role === "adult" ? "selected" : ""}>Voksen</option>
            <option value="child" ${m.role === "child" ? "selected" : ""}>Barn</option>
          </select>
          <label class="field inline">Alder ${num(`household.${i}.age`, m.age, 0, 120)}</label>
          <select data-path="household.${i}.sex">
            <option value="female" ${m.sex === "female" ? "selected" : ""}>Pige/kvinde</option>
            <option value="male" ${m.sex === "male" ? "selected" : ""}>Dreng/mand</option>
            <option value="other" ${m.sex === "other" ? "selected" : ""}>Andet</option>
          </select>
          <button class="btn small danger" data-action="remove-row" data-arg="household|${i}">Fjern</button>
        </div>`
      )
      .join("");
    const fixed = f.fixed_days
      .map(
        (d, i) => {
          const kind = fixedKindOf(d);
          return `<div class="row wrap rowitem">
          ${weekdaySelect(`fixed_days.${i}.weekday`, d.weekday)}
          <select data-path="fixed_days.${i}.kind">${FIXED_KINDS.map((k) => `<option value="${k}" ${kind === k ? "selected" : ""}>${DAY_KIND_LABELS[k]}</option>`).join("")}</select>
          ${kind === "fixed" ? `<input class="grow" type="text" data-path="fixed_days.${i}.text" value="${esc(d.text)}" placeholder="Fx Pizza">` : ""}
          <button class="btn small danger" data-action="remove-row" data-arg="fixed_days|${i}">Fjern</button>
        </div>`;
        }
      )
      .join("");
    const lunchOn = Number(f.lunch_count) > 0;
    const mustRow = (m, i) => {
      const mode = m.mode || "packs";
      const modes = { packs: "Antal pakker pr. uge", week: "Forbrug pr. uge", ...(lunchOn || mode === "lunch" ? { lunch: "Pr. madpakke" } : {}) };
      return `<div class="row wrap rowitem">
          <input class="grow" type="text" data-path="must_haves.${i}.name" value="${esc(m.name)}" placeholder="Vare">
          <select data-path="must_haves.${i}.mode" aria-label="Hvor meget">${Object.entries(modes).map(([v, l]) => `<option value="${v}" ${mode === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          ${mode === "packs"
            ? num(`must_haves.${i}.amount`, m.amount, 1, 99)
            : `<input type="number" data-path="must_haves.${i}.use" data-type="number" min="0" step="any" value="${esc(m.use || "")}" placeholder="${mode === "lunch" ? "0,25" : "5,5"}" aria-label="Mængde">
              <select data-path="must_haves.${i}.unit" aria-label="Enhed">${["g", "kg", "ml", "l", "stk", "pk"].map((u) => `<option ${u === (m.unit || "stk") ? "selected" : ""}>${u}</option>`).join("")}</select>`}
          <select data-path="must_haves.${i}.group" aria-label="Gruppe">${Object.entries(MUST_GROUPS).map(([v, l]) => `<option value="${v}" ${(m.group || "") === v ? "selected" : ""}>${l}</option>`).join("")}</select>
          ${m.product_id ? '<span class="badge">REMA-vare</span>' : ""}
          <button class="btn small danger" data-action="remove-row" data-arg="must_haves|${i}">Fjern</button>
        </div>`;
    };
    // Grouped as they are shown on the shopping list.
    const musts = Object.keys(MUST_GROUPS)
      .map((group) => {
        const rows = f.must_haves.map((m, i) => ((m.group || "") === group ? mustRow(m, i) : "")).join("");
        return rows ? `${group ? `<h3 class="small-h">${MUST_GROUPS[group]}</h3>` : ""}${rows}` : "";
      })
      .join("");
    const calendars = Object.keys(this._hass?.states || {}).filter((id) => id.startsWith("calendar.")).sort();
    const lunchHtml = `<h2>Madpakker</h2>
        <p class="muted small">Madpakkevarer følger ugens madpakker: ingen i ferien, færre i en kort skoleuge. Vælg <b>Pr. madpakke</b> ved en fast vare – fx rugbrød 0,25 pk eller pålæg 20 g – eller gruppen <b>Madpakker</b>.</p>
        <div class="grid">
          <label class="field">Madpakker om dagen ${num("lunch_count", f.lunch_count, 0, 20)}</label>
          <label class="field">Fridage fra kalender
            <select data-path="lunch_calendar"><option value="">Ingen</option>
              ${calendars.map((id) => `<option value="${esc(id)}" ${f.lunch_calendar === id ? "selected" : ""}>${esc(this._hass.states[id].attributes?.friendly_name || id)}</option>`).join("")}
            </select></label>
        </div>
        ${lunchOn ? `<p class="small">Skoledage</p><div class="checks">${WEEKDAYS.map((d, i) => check("lunch_weekdays", String(i), { [String(i)]: d })).join("")}</div>
        <p class="muted small">Heldagsbegivenheder i kalenderen – fx efterårsferie eller en skolefri dag – giver ingen madpakker den dag.</p>
        <label class="check"><input type="checkbox" data-path="lunch_ideas" ${f.lunch_ideas ? "checked" : ""}> AI'en foreslår madpakker ud fra ugens tilbud og aftensmadens rester</label>` : ""}`;
    const results = this._search.loading
      ? '<p class="muted"><span class="spinner small"></span> Søger …</p>'
      : this._search.results
          .map(
            (p, i) => `<button class="result" data-action="pick-product" data-arg="${i}">
              ${p.image ? `<img src="${esc(p.image)}" alt="">` : ""}
              <span><b>${esc(p.name)}</b><span class="muted">${esc(p.underline || "")} · ${kr(p.price)}</span></span>
              ${p.is_organic ? '<span class="badge eco">Øko</span>' : ""}</button>`
          )
          .join("");
    const dislikes = (this._state.settings.disliked_dishes || [])
      .map(
        (text, i) => `<li class="fav"><div class="what"><span>${esc(text)}</span></div>
          <button class="btn small danger" data-action="delete-dislike" data-arg="${i}">Slet</button></li>`
      )
      .join("");
    const favs = this._state.favorites
      .map((fav) =>
        this._editFav?.id === fav.id
          ? `<li class="fav edit">
              <textarea data-bind="editfav" data-field="text" rows="2">${esc(this._editFav.text)}</textarea>
              <div class="row wrap">
                <select data-bind="editfav" data-field="frequency">${opts.frequencies.map((q) => `<option value="${q}" ${this._editFav.frequency === q ? "selected" : ""}>${FREQ_LABELS[q]}</option>`).join("")}</select>
                <button class="btn small primary" data-action="save-fav">Gem</button>
                <button class="btn small" data-action="cancel-fav">Annullér</button>
              </div></li>`
          : `<li class="fav"><div class="what"><span>${esc(fav.text)}</span>
              <span class="muted small">${esc(FREQ_LABELS[fav.frequency] || fav.frequency)}${fav.last_used ? ` · sidst ${esc(shortDate(fav.last_used))}` : ""}</span></div>
              <button class="btn small" data-action="edit-fav" data-arg="${esc(fav.id)}">Ret</button>
              <button class="btn small danger" data-action="delete-fav" data-arg="${esc(fav.id)}">Slet</button></li>`
      )
      .join("");

    const card = (html) => `<div class="card">${html}</div>`;
    const sections = SETTINGS_SECTIONS(this);
    const open = sections.find((sec) => sec.key === this._settingsSection);
    const savebar = `<div class="savebar">
        <span class="muted small" data-settings-status role="status" aria-live="polite">${this._dirty ? "Ændringer er ikke gemt" : "Alt er gemt"}</span>
        <button class="btn primary" data-action="save-settings" ${this._busy || !this._dirty ? "disabled" : ""}>Gem ændringer</button>
        <button class="btn" data-action="reset-settings" ${this._busy || !this._dirty ? "disabled" : ""}>Fortryd</button>
      </div>`;
    const html = {
      ai: () => card(`        <h2 class="flush">Vælg AI</h2>
        <label class="field">AI til madplanen
          <select data-path="ai_task_entity" data-type="nullable">
            <option value="">Home Assistants standard-AI-opgave</option>${ai}
          </select></label>
        <p class="muted small">Brug Home Assistants standard, eller vælg en AI her. En samtaleagent kan også bruges.</p>
        `),
      plan: () => card(`        <h2 class="flush">Uge og budget</h2>
        <div class="grid">
          <label class="field">Første dag og indkøbsdag ${weekdaySelect("start_weekday", f.start_weekday)}</label>
          <label class="field">Antal dage ${num("days", f.days, 1, 14)}</label>
          <label class="field">Budget pr. madplan (kr.) ${num("budget", f.budget, 0, 100000)}</label>
          ${f.monthly_budget ? '<p class="muted small">I har et madbudget: en ny plan må koste det, der er tilbage af ugen, og dette tal bruges ikke.</p>' : ""}
        </div>
        <label class="check"><input type="checkbox" data-path="recipe_planner" ${f.recipe_planner ? "checked" : ""}> Byg madplanen på opskrifter</label>
        <p class="muted small">AI'en vælger ugens retter blandt de klare opskrifter (jeres og REMA's), der bruger avisens tilbud, og indkøbslisten regnes ud fra opskrifternes varer. Højst to nye retter om ugen – de skal godkendes, før listen sendes. Slået fra: AI'en finder på retterne og listen som før.</p>
        <label class="check"><input type="checkbox" data-path="shop_late_week" ${f.shop_late_week ? "checked" : ""}> Vi handler også sidst på ugen</label>
        <p class="muted small">Så må madplanen bruge tilbud, der først gælder fra torsdag, i retterne fra den dag. Varerne mærkes med, hvornår de skal købes. Ellers bruges kun tilbud, der gælder på indkøbsdagen.</p>
        `) + card(`        <h2 class="flush">Automatik</h2>
        <label class="check"><input type="checkbox" data-path="auto_generate" ${f.auto_generate ? "checked" : ""}> Lav næste uges madplan automatisk, når den nye tilbudsavis udkommer</label>
        <label class="check"><input type="checkbox" data-path="auto_send" ${f.auto_send ? "checked" : ""}> Send den automatisk til ${this._listName()}</label>
        `),
      family: () => card(`        <h2 class="flush">Familien</h2>
        ${household}
        <button class="btn small" data-action="add-row" data-arg="household">+ Tilføj person</button>
        <label class="field">Hvor meget spiser I? <select data-path="portion_percent">
          ${[[100, "Normale portioner"], [125, "25 % mere mad"], [150, "50 % mere mad"], [200, "Dobbelt så meget mad"]].map(([value, label]) => `<option value="${value}" ${Number(f.portion_percent || 100) === value ? "selected" : ""}>${label}</option>`).join("")}
        </select></label>
        <p class="muted small">Gælder nye ugeplaner, også retter til restedage. Faste ugevarer ændres ikke. Fryserretter har deres eget portionsvalg.</p>
        `) + card(`        <h2 class="flush">Undgå</h2>
        <div class="checks">${opts.avoid.map((k) => check("avoid", k, AVOID_LABELS)).join("")}</div>
        <label class="field">Andet at undgå <input type="text" data-path="avoid_other" value="${esc(f.avoid_other)}" placeholder="Fx svampe, oliven"></label>
        `) + card(`        <h2 class="flush">Allergier</h2>
        <div class="checks">${opts.allergies.map((k) => check("allergies", k, ALLERGY_LABELS)).join("")}</div>
        <label class="field">Andre allergier <input type="text" data-path="allergies_other" value="${esc(f.allergies_other)}"></label>
        `),
      dishes: () => card(`        <h2 class="flush">Retter</h2>
        <div class="grid">
          <label class="field">Mindst antal vegetarretter ${num("min_vegetarian", f.min_vegetarian, 0, 14)}</label>
          <label class="field">Højst antal vegetarretter ${num("max_vegetarian", f.max_vegetarian, 0, 14)}</label>
          <label class="field">Dage med rester ${num("leftover_days", f.leftover_days, 0, 7)}</label>
          <label class="field">Tid til madlavning på hverdage (min.) ${num("max_cook_minutes_weekday", f.max_cook_minutes_weekday, 5, 300)}</label>
          <label class="field">Vent med at gentage retter (uger) ${num("no_repeat_weeks", f.no_repeat_weeks, 0, 52)}</label>
        </div>
        <p class="muted small">Til en restedag laves der ekstra mad dagen før. En fast dag med rester (fx torsdag under Faste dage) tæller med i antallet. Det er adskilt fra månedens fryserretter.</p>
        <h3>Ingen rester disse dage</h3>
        <div class="checks">${WEEKDAYS.map((d, i) => check("no_leftover_weekdays", String(i), { [String(i)]: d })).join("")}</div>
        <h3>Faste dage</h3>
        <p class="muted small">Gælder hver uge og kan ændres for en enkelt uge under Tilpas dagene. Restedag: resten af en ret fra dagen før. Rugbrødsdag: der laves ikke mad, og der købes ikke noget til. Vegetardag: en vegetarret. Fast ret: AI'en laver den ret, I skriver.</p>
        ${fixed}
        <button class="btn small" data-action="add-row" data-arg="fixed_days">+ Tilføj fast dag</button>
        <label class="field">Ønsker til maden <textarea data-path="wishes" rows="2">${esc(f.wishes)}</textarea></label>
        <p class="muted small">Favoritretter og retter, I ikke kan lide, styres under Opskrifter: ♥ gør en ret til favorit (og under den vælger I, hvor tit den skal på madplanen), 👎 betyder, at den aldrig kommer på.</p>
        `),
      shopping: () => card(`<h2 class="flush">Det har I allerede hjemme</h2>
        <p class="muted small">Disse basisvarer kommer ikke på indkøbslisten. Adskil varerne med komma.</p>
        <label class="field">Basisvarer <textarea data-path="pantry" rows="2">${esc(f.pantry)}</textarea></label>
        `) + card(`        <h2 class="flush">Økologi</h2>
        <div class="row wrap">
          ${[["only", "Kun økologi"], ["prefer", "Gerne økologi"], ["none", "Vælg efter pris"]]
            .map(([v, l]) => `<label class="check"><input type="radio" name="organic" data-path="organic" value="${v}" ${f.organic === v ? "checked" : ""}> ${l}</label>`)
            .join("")}
        </div>
        ${f.organic === "prefer" ? `<label class="field inline">Højst så mange % dyrere end den billigste ${num("organic_max_extra_pct", f.organic_max_extra_pct, 0, 500)}</label>` : ""}
        `) + card(`        <h2 class="flush">Usikre varer</h2>
        <p class="muted small">Når Middagsro ikke er sikker på, at en vare er den rigtige til en ingrediens (fx "oksekød i strimler"), markeres den med <span class="badge doubt">Tjek</span> på indkøbslisten med andre muligheder at vælge imellem. Jeres valg huskes til næste madplan.</p>
        <div class="row wrap">
          ${[["review", "Vis dem til tjek, før listen sendes"], ["send", "Send dem som valgt"], ["skip", "Udelad dem fra listen"]]
            .map(([v, l]) => `<label class="check"><input type="radio" name="uncertain_items" data-path="uncertain_items" value="${v}" ${(f.uncertain_items || "review") === v ? "checked" : ""}> ${l}</label>`)
            .join("")}
        </div>

        <h2>Krav til varer</h2>
        <p class="muted small">Gælder uanset pris. Findes der ingen vare, der opfylder kravet, vælges den billigste med en note.</p>
        <div class="grid">
          <label class="field">Æg
            <select data-path="egg_min">${Object.entries(EGG_LABELS)
              .map(([v, l]) => `<option value="${v}" ${f.egg_min === v ? "selected" : ""}>${l}</option>`)
              .join("")}</select></label>
        </div>
        <label class="check"><input type="checkbox" data-path="milk_organic" ${f.milk_organic ? "checked" : ""}> Mælk skal være økologisk</label>
        <label class="check"><input type="checkbox" data-path="produce_organic" ${f.produce_organic ? "checked" : ""}> Frugt og grønt skal være økologisk</label>
        `) + card(`        <h2 class="flush">Faste varer hver uge</h2>
        <p class="muted small">Et fast antal pakker, et forbrug pr. uge (fx mælk 5,5 l – på indkøbslisten skriver I, hvad der er tilbage) eller en mængde pr. madpakke. Grupperne bliver overskrifter på indkøbslisten.</p>
        ${musts}
        <label class="check"><input type="checkbox" data-path="must_haves_once" ${f.must_haves_once ? "checked" : ""}> Send ikke faste varer, der allerede står på ${this._listName()}</label>
        <p class="muted small">Når madplanen sendes, springes en fast vare over, hvis den står på ${this._isRema() ? "listen i REMA-appen" : "indkøbslisten"} og ikke er købt – så bliver antallet ikke lagt oven i.</p>
        <div class="row wrap">
          ${this._hasPrices() ? `<input class="grow" type="search" data-bind="search" value="${esc(this._search.query)}" placeholder="Søg i ${esc(this._shopName())}, fx letmælk">
          <button class="btn small" data-action="search">Søg</button>
          ${clearBtn("search")}` : ""}
          <button class="btn small" data-action="add-row" data-arg="must_haves">+ ${this._hasPrices() ? "Fritekst" : "Tilføj vare"}</button>
        </div>
        <div class="results">${results}</div>
        ${lunchHtml}
        `),
      rules: () => card(`        <h2 class="flush">Det skal AI'en huske</h2>
        <p class="muted small">Hvert punkt gemmes med det samme.</p>
        <p class="muted">Faste ønsker, der bruges i alle madplaner, opskrifter og forslag – fx “Vi vil altid have frisk broccoli og fettuccine med spinat til laksefilet”. Skriv eller diktér; hvert punkt kan rettes og slettes.</p>
        ${this._rulesHtml()}
        `),
      nutrition: () => card(`        <h2 class="flush">Næring pr. aftensmad</h2>
        <p class="muted">Mål for en voksens portion. AI'en rammer det så tæt som muligt, og under Sundhed kan du se, hvordan madplanen ligger.</p>
        <label class="check"><input type="checkbox" data-path="nutrition_enabled" ${f.nutrition_enabled ? "checked" : ""}> Brug målene, når madplanen laves</label>
        <div class="grid">
          <label class="field inline">Protein ${num("protein_pct", f.protein_pct, 0, 100)} %</label>
          <label class="field inline">Kulhydrat ${num("carb_pct", f.carb_pct, 0, 100)} %</label>
          <label class="field inline">Fedt ${num("fat_pct", f.fat_pct, 0, 100)} %</label>
        </div>
        ${Number(f.protein_pct) + Number(f.carb_pct) + Number(f.fat_pct) !== 100
          ? `<p class="note">Procenterne giver ${Number(f.protein_pct) + Number(f.carb_pct) + Number(f.fat_pct)} % – de bør give 100 %.</p>`
          : ""}
        <div class="grid">
          <label class="field inline">Fra ${num("kcal_min", f.kcal_min, 100, 3000)} kcal</label>
          <label class="field inline">til ${num("kcal_max", f.kcal_max, 100, 3000)} kcal</label>
        </div>
        <p class="muted small">Fx 40 % protein, 35 % kulhydrat og 25 % fedt og 800–900 kcal. De officielle anbefalinger for voksne er ca. 10–20 % protein, 45–60 % kulhydrat og 25–40 % fedt af energien.</p>
        `),
      chains: () => card(`<h2 class="flush">Andre butikker</h2>
        <div class="banner info">I handler i ${esc(this._shopName())} – selve butikken vælges under Butik. Her vælger I de andre kæder, I også handler i.</div>
        <p class="muted">Deres madtilbud vises på forsiden, og i indkøbslisten og favoritterne står der, når en vare er billigere hos dem denne uge.</p>
        ${this._storeId() !== "93f13" ? '<p class="muted small">Bilka sammenlignes på <b>alle varer</b>, ikke kun tilbud – med priserne fra Bilka ToGo (webshoppens priser, tæt på butikkens).</p>' : ""}
        ${this._chains
          ? `<div class="chain-pick">${this._chains
              .filter((c) => this._isRema() || c.id !== this._storeId())
              .map((c) => `<label class="chain-choice"><input type="checkbox" data-list="chains" value="${esc(c.id)}" ${f.chains.includes(c.id) ? "checked" : ""}>${this._chainLogo(c.id)}<span>${esc(c.name)}</span></label>`)
              .join("")}</div>`
          : '<p class="muted"><span class="spinner small"></span> Henter kæderne …</p>'}
        <p class="muted small">Tilbuddene kommer fra kædernes tilbudsaviser (Tjek/eTilbudsavis). En vare tæller kun som billigere, når det er den samme slags vare i samme størrelse.</p>
        <h3>Madplan på tværs af butikkerne</h3>
        <label class="check"><input type="checkbox" data-path="plan_all_chains" ${f.plan_all_chains ? "checked" : ""}> Byg madplanen på tilbud fra alle de valgte butikker</label>
        <p class="muted small">AI'en får tilbuddene fra alle de valgte kæder og vælger ugens bedste på tværs af dem. Varer fra en anden butik kommer på den butiks egen liste under Indkøb (ikke på ${esc(this._listName())}). Slået fra: madplanen bygges kun på ${esc(this._shopName())}${this._isRema() ? "'s" : "s"} tilbud, og de andre butikker bruges til sammenligning.</p>`),
      budget: () => card(`<h2 class="flush">Madbudget</h2>
        <p class="muted">Jeres faste beløb til indkøb – pr. måned eller pr. uge, som I tænker i det. Et månedsbeløb fordeles på månedens dage (5.000 kr. i oktober er 161 kr. om dagen, 1.129 kr. om ugen); et ugebeløb er det samme hver uge (1.400 kr. om ugen er 200 kr. om dagen). Det, en uge ikke bruger, går videre til de næste uger i samme måned; en ny måned starter forfra den 1.</p>
        <label class="field">Angiv budgettet
          <select data-path="budget_period">
            <option value="month" ${f.budget_period !== "week" ? "selected" : ""}>Pr. måned</option>
            <option value="week" ${f.budget_period === "week" ? "selected" : ""}>Pr. uge</option>
          </select></label>
        ${f.budget_period === "week"
          ? `<label class="field">Madbudget pr. uge (kr., 0 = slået fra) ${num("weekly_budget", f.weekly_budget, 0, 250000)}</label>
             ${f.weekly_budget ? `<p class="muted small">Det er ca. ${kr0((f.weekly_budget * 365) / 12 / 7)} om måneden.</p>` : ""}`
          : `<label class="field">Madbudget pr. måned (kr., 0 = slået fra) ${num("monthly_budget", f.monthly_budget, 0, 1000000)}</label>`}
        <p class="muted small">Med et madbudget må en ny madplan koste det, der er tilbage af ugen – i stedet for det faste budget under Madplan og uge. Alt, der konteres, tæller med (også bleer og opvask).</p>
        <label class="check"><input type="checkbox" data-path="budget_notify" ${f.budget_notify ? "checked" : ""}> Giv besked, når 80 % af ugens budget er brugt</label>
        <p class="muted small">Beskeden går samme sted hen som overvågningens (Overvågning og beskeder${f.watch_notify ? "" : " – vælg en modtager dér"}).</p>
        <h3>Kontér automatisk</h3>
        ${this._isRema() ? `<label class="check"><input type="checkbox" data-path="book_receipts" ${f.book_receipts ? "checked" : ""}> Kontér mine REMA 1000-kvitteringer automatisk</label>
        <p class="muted small">Hver digital kvittering fra REMA 1000 bogføres som et køb i Økonomi – også hele din hidtidige historik – så du kan droppe Apple Pay-genvejen (den er der stadig til køb uden for REMA). ${f.book_receipts && f.book_receipts_since ? `Konterer fra ${esc(longDate(f.book_receipts_since))}.` : "Dækker hele historikken."}${f.monthly_budget ? "" : " <b>Sæt et madbudget ovenfor først.</b>"}</p>` : ""}
        ${this._isRema() ? this._receiptLoginsSettings() : ""}
        <p class="muted small">Handlingen <b>middagsro.register_purchase</b> konterer et køb (beløb og butik) og svarer med, hvad der er tilbage af ugen. Betaler I med Apple Pay, kan en automatisering i Genveje-appen (Personlig › Transaktion › Wallet, butikker: REMA 1000, Netto …) kalde den med <i>Beløb</i> og <i>Forhandler</i> via Home Assistant-appens "Udfør handling" – så konteres købet af sig selv, når I betaler. Med Siri kan en genvej spørge om beløbet og kalde den samme handling.</p>`),
      messages: () => {
        f.messages ||= {};
        for (const [k] of MSG_KINDS) f.messages[k] ||= {};
        f.quiet ||= { on: false, from: "22:00", to: "07:00", after: "digest" };
        const q = f.quiet, toMin = (t) => { const [h, m] = String(t || "0:0").split(":").map(Number); return (h || 0) * 60 + (m || 0); };
        const quiet = (t) => q.on && (toMin(q.from) <= toMin(q.to) ? toMin(t) >= toMin(q.from) && toMin(t) < toMin(q.to) : toMin(t) >= toMin(q.from) || toMin(t) < toMin(q.to));
        const isOn = (k) => (k === "budget" ? f.budget_notify : f.messages.watch.on !== false) && Boolean(f.watch_notify);
        const look = (k, i) => ({ color: f.messages[k].color || MSG_KINDS[i][4], icon: f.messages[k].icon || MSG_KINDS[i][3] });
        const notes = MSG_KINDS.map((d, i) => ({ d, l: look(d[0], i), held: quiet(d[7]) && !f.messages[d[0]].through })).filter(({ d }) => isOn(d[0]));
        const note = (title, body, time, color, held = false) => `<div class="mc-note${held ? " held" : ""}" style="--c:${color}"><span class="mc-ic">${BELL_ICON}</span><span class="mc-t"><b>${esc(title)}</b><i>${time}</i></span><span class="mc-m">${esc(body)}</span></div>`;
        const digest = q.after !== "drop", held = notes.filter((n) => n.held);
        const phone = `<div class="mc-phone"><div class="mc-clock">${esc(q.on ? q.to : "18:00")}</div>
          ${notes.length ? "" : `<p class="mc-empty">Ingen beskeder er slået til.</p>`}
          ${notes.filter((n) => !(n.held && digest)).map(({ d, l, held: h }) => note(d[5], d[6], d[7], l.color, h)).join("")}
          ${held.length && digest ? `<span class="mc-when">Efter stille timer</span>${note("Mens du sov", held.map(({ d }) => `${d[5]}: ${d[6]}`).join(" · "), q.to, "#5B5BD6")}` : ""}</div>`;
        const kcard = (d, i) => {
          const [k, name, when] = d, l = look(k, i), on = isOn(k);
          return `<article class="mc-card${on ? "" : " off"}" style="--c:${l.color}">
            <div class="mc-top"><span class="mc-ic">${BELL_ICON}</span><div><b>${esc(name)}</b><small>${esc(when)}</small></div>
              <label class="check"><input type="checkbox" data-path="${k === "budget" ? "budget_notify" : "messages.watch.on"}" ${on ? "checked" : ""} ${f.watch_notify ? "" : "disabled"}> Til</label></div>
            <div class="mc-bubble"><b>${esc(d[5])}</b><span>${esc(d[6])}</span></div>
            <label class="check"><input type="checkbox" data-path="messages.${k}.through" ${f.messages[k].through ? "checked" : ""}> Går igennem stille timer</label>
            <div class="row wrap"><label class="field">Ikon <select data-path="messages.${k}.icon">${MSG_ICONS.map((x) => `<option value="${x}" ${l.icon === x ? "selected" : ""}>${x.slice(4)}</option>`).join("")}</select></label>
              <label class="field">Farve <input type="color" data-path="messages.${k}.color" value="${esc(l.color)}"></label></div></article>`;
        };
        return card(`<h2 class="flush">Beskeder</h2>
          <div class="mc-strip">
            <label class="field">Send til <select data-path="watch_notify"><option value="" ${!f.watch_notify ? "selected" : ""}>Ingen beskeder</option>${(this._state.notify_targets || []).map((t) => `<option value="${esc(t.id)}" ${f.watch_notify === t.id ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</select></label>
            <label class="check"><input type="checkbox" data-path="quiet.on" ${q.on ? "checked" : ""}> Stille timer</label>
            ${q.on ? `<input type="time" class="mc-time" data-path="quiet.from" value="${esc(q.from)}" aria-label="Fra">–<input type="time" class="mc-time" data-path="quiet.to" value="${esc(q.to)}" aria-label="Til">
              <label class="field">Bagefter <select data-path="quiet.after"><option value="digest" ${digest ? "selected" : ""}>Én samlet besked</option><option value="drop" ${digest ? "" : "selected"}>Ingenting</option></select></label>` : ""}
          </div>
          <div class="mc-main"><div>${phone}</div><div class="mc-cards">${MSG_KINDS.map(kcard).join("")}</div></div>`);
      },
      look: () => card(`<h2 class="flush">Udseende</h2>
        <p class="muted small">Gemmes for dig. Theme Studio følger jeres Home Assistant-theme.</p>
        <div class="row wrap">${this._looks().map((k) => `<button class="btn${this._look() === k ? " primary" : ""}" data-action="look" data-arg="${k}" aria-pressed="${this._look() === k}">${LOOK_NAMES[k]}</button>`).join("")}</div>`),
      watch: () => card(`<h2 class="flush">Besked om tilbud</h2>
        <p class="muted">Få besked, når noget fra overvågningslisten under Favoritter kommer på tilbud hos ${esc(this._shopName())} eller en af jeres andre butikker – kun da, og kun én gang pr. tilbud.</p>
        <label class="field">Send besked til
          <select data-path="watch_notify">
            <option value="" ${!f.watch_notify ? "selected" : ""}>Ingen beskeder</option>
            ${(this._state.notify_targets || [])
              .map((t) => `<option value="${esc(t.id)}" ${f.watch_notify === t.id ? "selected" : ""}>${esc(t.name)}</option>`)
              .join("")}
          </select></label>
        <p class="muted small">Beskeden har en klokke i titlen, 🛒 ved ${esc(this._shopGen())} tilbud og 🏷️ ved de andre butikkers, varens billede, og den åbner Middagsro, når du trykker på den. Der tjekkes hver tredje time.</p>
        <div class="row wrap"><button class="btn small" data-action="watch-check" ${this._busy ? "disabled" : ""}>Tjek nu og send besked</button></div>
        <p class="muted small">${(this._state.watch || []).length} ting overvåges. Tilføj flere med klokken under Favoritter.</p>`),
      shop: () => {
        const shop = this._state.shop || { name: "REMA 1000", rema: true, rema_only: [] };
        const how = `Vælg mellem tilføjede butikker i <b>Vi handler i</b> øverst. Login og Bilka-varehus ændres under <b>Indstillinger › Enheder og tjenester › Middagsro › ⋮ › Omkonfigurér</b>.`;
        const todos = Object.keys(this._hass?.states || {})
          .filter((id) => id.startsWith("todo.") && !id.includes("middagsro"))
          .sort();
        if (shop.rema) {
          return card(`        <h2 class="flush">I handler i REMA 1000</h2>
        <p>Middagsro er logget ind på jeres REMA 1000-konto: alle varer har en pris, REMA's opskrifter kan bruges, og indkøbslisten sendes til REMA-appen.</p>
        <label class="field">Knappen + REMA-listen ved tilbud og priser lægger varen på
          <select data-path="quick_todo_entity">
            <option value="" ${f.quick_todo_entity ? "" : "selected"}>REMA-listen i appen</option>
            ${todos.map((id) => `<option value="${esc(id)}" ${f.quick_todo_entity === id ? "selected" : ""}>${esc(this._hass.states[id].attributes?.friendly_name || id)}</option>`).join("")}
          </select></label>
        <p class="muted small">Madplanens indkøbsliste sendes stadig til REMA-appen.</p>
        <p class="muted">Handler I et andet sted – Netto, føtex, Lidl, Bilka, 365discount, MENY, Coop eller andre – kan I vælge den butik i stedet. Så bygges madplanen på dens tilbudsavis, og indkøbslisten ligger i Home Assistant.</p>
        <p class="muted small">${how}</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Åbn Middagsro under Enheder og tjenester</a>`);
        }
        if (shop.bilka_cart && shop.cart_name === "Nemlig.com") {
          return card(`<h2 class="flush">I handler med Nemlig.com</h2>
        <p>Middagsro er logget ind på jeres Nemlig.com-konto: madplanen bygges på Nemligs tilbud, og alle varer har jeres Nemlig-pris.</p>
        <p>Madplanens varer sendes til kurven på nemlig.com og i Nemlig-appen. Du gennemgår selv kurven, vælger leveringstid og bestiller på nemlig.com.</p>
        <p>Fundne varer sendes til kurven. Ingredienser uden match vises særskilt og bliver i Middagsro, så du kan vælge en vare eller tilføje dem selv.</p>
        <p class="muted small">${how}</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Ret login</a>`);
        }
        if (shop.bilka_cart) {
          return card(`<h2 class="flush">I handler med BilkaToGo</h2>
        <p>Varehus: <b>${esc(shop.pickup_name)}</b>. Sortiment og priser følger dette varehus.</p>
        <p>Madplanens varer sendes til kurven i BilkaToGo-appen og på hjemmesiden. Du gennemgår selv kurven, vælger afhentningstid og bestiller i BilkaToGo.</p>
        <p>Fundne varer sendes til kurven. Ingredienser uden match vises særskilt og bliver i Middagsro, så du kan vælge en vare eller tilføje dem selv. Kurven kan ikke afkrydses som en indkøbsliste.</p>
        <p class="muted small">${how} Vælg Bilka igen for at ændre varehus eller login.</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Ret login eller varehus</a>`);
        }
        return card(`        <h2 class="flush">I handler i ${esc(shop.name)}</h2>
        <p>${shop.prices
          ? `Madplanen bygges på ${esc(genitive(shop.name))} tilbudsavis, og alle varer har deres pris fra ${esc(shop.name)} ToGo – webshoppens priser, som ligger tæt på butikkens.`
          : `Madplanen bygges på ${esc(genitive(shop.name))} tilbudsavis, og tilbudsvarerne har deres pris. Andre varer står på listen uden pris, så madbudgettet følger det, I selv konterer.`}</p>
        <h2>Indkøbsliste</h2>
        <p class="muted small">Det, der sendes, kommer på Middagsros indkøbsliste (også som to-do-liste i Home Assistant). Vælg en liste her, hvis det også skal på jeres egen – fx Bring!, Google Keep eller Home Assistants indkøbsliste.</p>
        <label class="field">Send også til
          <select data-path="ha_todo_entity">
            <option value="" ${f.ha_todo_entity ? "" : "selected"}>Ingen anden liste</option>
            ${todos.map((id) => `<option value="${esc(id)}" ${f.ha_todo_entity === id ? "selected" : ""}>${esc(this._hass.states[id].attributes?.friendly_name || id)}</option>`).join("")}
          </select></label>
        <h2>Kun med REMA 1000</h2>
        <ul class="plain">${(shop.rema_only || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p class="muted small">${how}</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Åbn Middagsro under Enheder og tjenester</a>`);
      },
      sites: () => card(`        <h2 class="flush">Madsider</h2>
        <p class="muted">Søg i opskrifterne på kendte madsider under Opskrifter › Madsider, og gem dem i opskriftsamlingen – eller vælg en til en dag i næste madplan.</p>
        <div class="checks">${(this._state.recipe_sites || []).map((x) => check("recipe_sites", x.id, { [x.id]: x.name })).join("")}</div>
        <label class="check"><input type="checkbox" data-path="recipe_sites_in_plan" ${f.recipe_sites_in_plan ? "checked" : ""}> Brug madsidernes opskrifter, når madplanen laves – AI'en vælger blandt opskrifter, der passer til ugens tilbud</label>
        <p class="muted small">Opskriften, AI'en vælger, gemmes i opskriftsamlingen med et link til siden, og dens ingredienser kommer på indkøbslisten.</p>
        `),
      mealie: () => card(`        <h2 class="flush">Mealie</h2>
        ${this._state.mealie?.available
          ? `<p class="muted">Bruger Mealie-integrationen i Home Assistant${this._state.mealie.url ? ` (${esc(this._state.mealie.url)})` : ""}.</p>
            <label class="check"><input type="checkbox" data-path="mealie_recipes" ${f.mealie_recipes ? "checked" : ""}> Tag udgangspunkt i vores opskrifter i Mealie – AI'en finder selv på, når ingen passer</label>
            <label class="check"><input type="checkbox" data-path="mealie_calendar" ${f.mealie_calendar ? "checked" : ""}> Sæt madplanen i Mealie-kalenderen (og ret den, når madplanen ændres)</label>
            <p class="muted small">Madplanens egne opskrifter kan gemmes i Mealie med "Gem i Mealie" på retten.</p>`
          : `<p class="muted">Har I jeres opskrifter i <a href="https://mealie.io" target="_blank" rel="noopener">Mealie</a>, så sæt Mealie-integrationen op i Home Assistant (Indstillinger › Enheder og tjenester). Så kan madplanen tage udgangspunkt i jeres opskrifter, gemme sine egne i Mealie og fylde Mealie-kalenderen.</p>`}
        `),
      app: () => card(`        <h2 class="flush">App på hjemmeskærmen</h2>
        <p class="muted">Åbn linket i Safari (eller Chrome), log ind og vælg Del › Føj til hjemmeskærm. Så åbner Middagsro i fuld skærm i dit tema.</p>
        <p><a href="${esc(`${location.origin}/middagsro_app/app.html`)}" target="_blank" rel="noopener">${esc(`${location.origin}/middagsro_app/app.html`)}</a></p>
        `),
    };
    if (open) {
      return `
        <div class="settings-head">
          <button class="btn back" data-action="settings-section" data-arg="">‹ Indstillinger</button>
          <div><h1>${esc(open.title)}</h1><p class="muted small">${esc(open.summary)}</p></div>
        </div>
        ${html[open.key]()}
        ${open.key === "shop" ? this._storeChooser() || '<p class="muted small">Tilføj Nemlig.com eller Bilka ToGo som butik under Enheder og tjenester › Middagsro › Tilføj post – så kan I skifte her og sammenligne kurven under Indkøb.</p>' : ""}
        ${open.form || this._dirty ? savebar : ""}`;
    }
    const row = (sec) => `<button class="setting-row" data-action="settings-section" data-arg="${sec.key}">
          <span class="setting-icon">${sec.icon}</span>
          <span class="setting-text"><b>${esc(sec.title)}</b><span class="muted small">${esc(sec.summary)}</span></span>
          <span class="chev" aria-hidden="true">›</span>
        </button>`;
    const groups = [
      { title: "Jeres hverdag", help: "Personer, portioner og ugens mad.", keys: ["family", "plan", "dishes", "rules"] },
      { title: "Indkøb og økonomi", help: "Hvor I handler, hvad I køber og jeres budget.", keys: ["shop", "shopping", "budget", "chains"] },
      { title: "Opskrifter og sundhed", help: "Opskriftskilder og ønsker til næring.", keys: ["sites", "nutrition", "mealie"] },
      { title: "Opsætning og beskeder", help: "AI, tilbudsbeskeder og adgang på telefonen.", keys: ["ai", "watch", "app"] },
    ];
    const order = ["shop", "plan", "ai", "budget", "family", "dishes", "rules", "shopping", "nutrition", "chains", "watch", "messages", "look", "sites", "mealie", "app"];
    const keys = [...order.filter((k) => sections.some((sec) => sec.key === k)), ...groups.flatMap((g) => g.keys).filter((k) => !order.includes(k) && sections.some((sec) => sec.key === k))];
    void row;
    return `<div class="v3"><div class="sgrid">${keys.map((key) => { const sec = sections.find((x) => x.key === key); return `<button class="stile" data-action="settings-section" data-arg="${sec.key}"><span class="st-ic">${sec.icon}</span><span><b>${esc(sec.title)}</b><small>${esc(sec.summary)}</small></span></button>`; }).join("")}</div></div>
      ${this._dirty ? savebar : ""}`;
  }
}

const STYLE_BASE = `
  /* No double-tap zoom; 16 px inputs so a phone doesn't zoom in on them. */
  :host, button, input, select, textarea, .day, .line { touch-action: manipulation; }
  :host { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }
  /* Inside a dashboard card or its pop-up: the page only, on the card's own surface. */
  :host([embed]) { min-height: 0; background: none; }
  :host([embed]) .toolbar, :host([embed]) .tabs, :host([embed]) .more-scrim, :host([embed]) .more-sheet, :host([embed]) .credit { display: none !important; }
  :host([embed]) .subnav { display: none; }
  :host([embed]) main { padding: 4px 12px calc(24px + var(--rema-safe-bottom, 0px)); }
  :host { display: block; min-height: 100vh; overflow-x: clip; background: var(--primary-background-color); color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, Roboto, sans-serif);
    /* Everything follows the Home Assistant theme; only the logo keeps REMA's colours. */
    --rema-accent: var(--primary-color);
    --rema-on-accent: var(--text-primary-color, #fff);
    --rema-sale: var(--error-color, #db4437);
    --rema-on-sale: var(--text-primary-color, #fff);
    --rema-ok: var(--success-color, #43a047);
    --rema-warn: var(--warning-color, #ffa600);
    --rema-card: var(--ha-card-background, var(--card-background-color));
    --rema-subtle: var(--secondary-background-color);
    --rema-tint: color-mix(in srgb, var(--rema-accent) 12%, transparent);
    /* Bars that stay on screen while content scrolls under them: the card colour on the
       page background, so see-through (glass) themes don't show text behind them. */
    --rema-solid-card: linear-gradient(var(--card-background-color), var(--card-background-color)) var(--primary-background-color); }

  /* The looks: Theme Studio is Home Assistant's theme (as before); Frisk and Hverdag are EV Planner's and Hverdagsro's. */
  :host([look="frisk"]) { --primary-background-color: #F2F4F7; --card-background-color: #FFFFFF; --ha-card-background: #FFFFFF; --secondary-background-color: #EEF1F4;
    --primary-text-color: #111827; --secondary-text-color: #6B7280; --divider-color: #E5E7EB; --primary-color: #00A884; --text-primary-color: #fff;
    --app-header-background-color: #FFFFFF; --app-header-text-color: #111827; --ha-card-border-radius: 16px; --ha-card-box-shadow: 0 1px 2px rgba(0,0,0,.05);
    --ha-font-family-body: Inter, "Segoe UI", system-ui, sans-serif; --theme-studio-card-backdrop-filter: none; }
  :host([look="frisk"][dark]) { --primary-background-color: #0E1116; --card-background-color: #161A21; --ha-card-background: #161A21; --secondary-background-color: #1C212A;
    --primary-text-color: #EEF1F5; --secondary-text-color: #9AA3B2; --divider-color: #262C36; --primary-color: #2DD4A7; --app-header-background-color: #161A21; --app-header-text-color: #EEF1F5; }
  :host([look="hverdag"]) { --primary-background-color: #F2F4F6; --card-background-color: #FFFFFF; --ha-card-background: #FFFFFF; --secondary-background-color: #F1EEFB;
    --primary-text-color: #1B1530; --secondary-text-color: #6B6880; --divider-color: #E4E2EE; --primary-color: #6E4AFF; --text-primary-color: #fff;
    --app-header-background-color: #FFFFFF; --app-header-text-color: #1B1530; --ha-card-border-radius: 18px; --ha-card-box-shadow: 0 1px 2px rgba(27,21,48,.06), 0 8px 24px rgba(27,21,48,.07);
    --ha-font-family-body: Figtree, "Segoe UI", system-ui, sans-serif; --theme-studio-card-backdrop-filter: none; }
  :host([look="hverdag"][dark]) { --primary-background-color: #0F0E19; --card-background-color: #191726; --ha-card-background: #191726; --secondary-background-color: #221F33;
    --primary-text-color: #F1EFFA; --secondary-text-color: #A7A3BD; --divider-color: #2D2A42; --primary-color: #9B83FF; --app-header-background-color: #191726; --app-header-text-color: #F1EFFA; }
  :host([look="frisk"]) .card, :host([look="hverdag"]) .card { border: 0; }
  :host([look="hverdag"]) .card { border: 0; }
  /* The profile button and its menu (Indstillinger, Beskeder, Udseende), as in EV Planner. */
  .prof-wrap { position: relative; }
  .prof { width: 34px; height: 34px; border-radius: 50%; border: 0; background: var(--rema-accent); color: var(--rema-on-accent); font-weight: 700; cursor: pointer; }
  .prof-menu { position: absolute; right: 0; top: 42px; z-index: 6; display: grid; min-width: 210px; padding: 6px; border-radius: 14px; background: var(--card-background-color); box-shadow: 0 12px 32px rgba(0,0,0,.18); border: 1px solid var(--divider-color); }
  .prof-menu[hidden] { display: none; }
  .prof-menu button { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 0; border-radius: 10px; background: none; color: var(--primary-text-color); font: inherit; text-align: left; cursor: pointer; }
  .prof-menu button:hover { background: var(--rema-tint); }
  .prof-menu svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; }
  /* The message centre (Indstillinger › Beskeder). */
  .mc-strip { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; padding: 10px 12px; border-radius: 14px; background: var(--rema-subtle); margin: 8px 0 14px; }
  .mc-strip .field { margin: 0; }
  .mc-time { padding: 4px 8px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
  .mc-main { display: grid; grid-template-columns: minmax(230px, 290px) minmax(0, 1fr); gap: 16px; align-items: start; }
  @media (max-width: 700px) { .mc-main { grid-template-columns: 1fr; } }
  .mc-phone { background: #0F1218; color: #F3F5F8; border-radius: 28px; border: 6px solid #2A2F38; padding: 14px 9px; display: grid; gap: 7px; align-content: start; min-height: 300px; }
  .mc-clock { text-align: center; font-size: 34px; font-weight: 700; margin: 4px 0; }
  .mc-when { color: #A7AFBC; font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; padding: 4px 6px 0; }
  .mc-empty { color: #A7AFBC; text-align: center; font-size: 13px; }
  .mc-note { display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: 2px 9px; padding: 9px 11px; border-radius: 16px; background: rgba(255,255,255,.12); }
  .mc-note.held { opacity: .42; }
  .mc-note .mc-ic { grid-row: span 2; }
  .mc-t { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; min-width: 0; }
  .mc-t b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mc-t i { font-style: normal; color: #A7AFBC; }
  .mc-m { font-size: 12.5px; color: #DDE2EA; }
  .mc-ic { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--c); color: #fff; flex: none; }
  .mc-ic svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 2; }
  .mc-cards { display: grid; gap: 10px; }
  .mc-card { border-radius: 14px; padding: 12px; background: var(--rema-subtle); display: grid; gap: 8px; }
  .mc-card.off { opacity: .65; }
  .mc-top { display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 10px; align-items: center; }
  .mc-top .mc-ic { width: 32px; height: 32px; }
  .mc-top small { display: block; color: var(--secondary-text-color); font-size: 12.5px; }
  .mc-bubble { background: var(--card-background-color); border-radius: 12px; padding: 8px 11px; font-size: 13px; display: grid; gap: 1px; }
  * { box-sizing: border-box; }
  a { color: var(--rema-accent); overflow-wrap: anywhere; }
  .skiphead { margin: 14px 0 6px; }
  .skipdays { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
  .skipgo { margin-top: 12px; }
  #content.from-right { animation: rema-from-right .2s ease-out; }
  #content.from-left { animation: rema-from-left .2s ease-out; }
  @keyframes rema-from-right { from { transform: translateX(32px); opacity: .4; } }
  @keyframes rema-from-left { from { transform: translateX(-32px); opacity: .4; } }
  @media (prefers-reduced-motion: reduce) { #content.from-right, #content.from-left { animation: none; } }
  /* --rema-safe-top/-bottom are only set by the home-screen app (behind the status bar and home bar). */
  .toolbar { display: flex; align-items: center; gap: 8px; height: calc(var(--header-height, 56px) + var(--rema-safe-top, 0px));
    padding: var(--rema-safe-top, 0px) 12px 0;
    background: var(--app-header-background-color, var(--card-background-color)); color: var(--app-header-text-color, inherit);
    border-bottom: 1px solid var(--divider-color); position: sticky; top: 0; z-index: 3; }
  .brand { display: inline-flex; align-items: center; gap: 10px; }
  .logo { height: min(36px, calc(var(--header-height, 56px) - 16px)); border-radius: 9px; }
  .wordmark { font-family: "Inter Display", Inter, var(--ha-font-family-body, system-ui), sans-serif; font-weight: 650; font-size: 22px;
    letter-spacing: -.025em; color: var(--app-header-text-color, var(--primary-text-color)); }
  .spacer { flex: 1; }
  .tabs { display: flex; gap: 4px; overflow-x: auto; padding: 8px 12px 0; background: var(--rema-solid-card);
    border-bottom: 1px solid var(--divider-color); position: sticky; top: calc(var(--header-height, 56px) + var(--rema-safe-top, 0px)); z-index: 2; }
  .tab { border: none; background: none; color: var(--secondary-text-color); padding: 10px 14px; font-size: 15px; cursor: pointer;
    border-bottom: 3px solid transparent; white-space: nowrap; font-weight: 500; }
  .tab.active { color: var(--rema-accent); border-color: var(--rema-accent); }
  .tab { order: var(--desktop-order, 20); }
  .tab:not(.desktop-primary):not(.more):not(.customize) { display: none; }
  .tab.more { display: flex; order: 21; }
  .tab.more.no-desktop-extra { display: none; }
  .tab.customize { order: 22; margin-left: auto; font-size: 13px; }
  .more-scrim, .more-sheet { display: none; }
  .more-scrim:not([hidden]) { display: block; position: fixed; inset: 0; z-index: 4; }
  .more-sheet:not([hidden]) { display: flex; flex-direction: column; position: fixed; right: 12px; top: calc(var(--header-height, 56px) + 50px); max-height: calc(100dvh - 140px); overflow-y: auto; z-index: 6; min-width: 210px; padding: 6px; border-radius: 16px; background: var(--rema-solid-card); border: 1px solid var(--divider-color); box-shadow: 0 8px 28px rgba(0,0,0,.22); }
  .more-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: none; border-radius: 10px; background: none; color: var(--primary-text-color); font-size: 15px; text-align: left; cursor: pointer; }
  .more-item.desktop-primary { display: none; }
  .more-item svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; }
  .more-item.active { color: var(--rema-accent); background: var(--rema-tint); }
  .nav-option { display: flex; gap: 8px; align-items: center; min-height: 44px; }
  .nav-option .check { flex: 1; min-width: 0; }
  .nav-option .btn { padding: 4px 10px; }
  .nav-option + .nav-option { border-top: 1px solid var(--divider-color); }
  .credit { margin: 24px 0 0; text-align: center; font-size: 13px; color: var(--secondary-text-color); }
  .credit .gh-link { display: inline-flex; vertical-align: -3px; margin-left: 4px; padding: 2px; color: inherit; border-radius: 999px; }
  .credit .gh { width: 16px; height: 16px; display: block; }
  .tab svg { display: none; width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8;
    stroke-linecap: round; stroke-linejoin: round; }
  main { max-width: 1100px; margin: 0 auto; padding: 16px 12px calc(96px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); }
  /* Theme Studio's glass blur is opt-in per card: the panel's cards take it. */
  .card { background: var(--rema-card); border-radius: var(--ha-card-border-radius, 12px);
    -webkit-backdrop-filter: var(--theme-studio-card-backdrop-filter, none); backdrop-filter: var(--theme-studio-card-backdrop-filter, none);
    box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.12)); border: 1px solid var(--divider-color);
    padding: 16px 18px; margin-bottom: 16px; }
  .center { text-align: center; }
  h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 22px 0 8px; } h3 { font-size: 15px; margin: 14px 0 6px; }
  p { line-height: 1.5; }
  .muted { color: var(--secondary-text-color); } .small { font-size: 13px; }
  .row { display: flex; align-items: center; gap: 10px; } .wrap { flex-wrap: wrap; } .between { justify-content: space-between; }
  .grow { flex: 1; min-width: 160px; }
  .actions { margin-top: 16px; }
  .btn { border: 1px solid var(--divider-color); background: var(--rema-card); color: var(--primary-text-color);
    border-radius: 999px; padding: 9px 16px; font-size: 14px; font-weight: 500; cursor: pointer; }
  .btn.primary { background: var(--rema-accent); color: var(--rema-on-accent); border-color: var(--rema-accent); }
  .btn.danger { color: var(--rema-sale); }
  .btn.small { padding: 5px 12px; font-size: 13px; }
  .btn:disabled { opacity: .5; cursor: default; }
  .ai { width: 1.1em; height: 1.1em; fill: currentColor; vertical-align: -.2em; margin-right: 6px; }
  .day-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; align-items: center; }
  .rate { display: inline-flex; gap: 2px; }
  .scan-row { margin-top: 8px; align-items: center; gap: 10px; }
  .scan-btn { display: inline-flex; align-items: center; gap: 6px; }
  .scan-btn .ico { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.7; }
  .pickday { display: flex; align-items: flex-start; flex-direction: column; gap: 4px; padding: 8px 10px; border: 1px solid var(--divider-color); border-radius: 10px; }
  .pickday .pick-btn { padding: 6px 12px; font-size: 14px; }
  .pick-chip { display: inline-flex; align-items: center; gap: 2px; background: var(--rema-tint); border-radius: 999px; padding: 0 2px 0 10px; font-size: 13px; }
  .pick-chip .icon-btn { width: 24px; height: 24px; }
  .pick-chip .icon-btn svg { width: 14px; height: 14px; }
  .pick-row { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
  .pick-row .what { flex: 1; display: flex; flex-direction: column; }
  .shop-head { gap: 12px; align-items: flex-start; }
  .store-badge .chain-logo { width: 40px; height: 40px; }
  .line.has-send { grid-template-columns: 48px 1fr auto auto; }
  .lines .line .to-rema-line { position: relative; flex: none; align-self: center; padding: 0; background: none; border: none; cursor: pointer; }
  .to-rema-line .plus { position: absolute; right: -4px; bottom: -4px; width: 16px; height: 16px; border-radius: 50%; background: var(--rema-accent); color: #fff; font-size: 13px; line-height: 16px; text-align: center; font-weight: 700; }
  .to-rema-line:disabled { opacity: .4; }
  .day-tools { display: flex; flex-direction: column; align-items: flex-end; gap: 0; }
  .move-row .rate-btn { height: 26px; color: var(--secondary-text-color); }
  .move-row .rate-btn:disabled { opacity: .25; cursor: default; background: none; }
  .rate-gap { width: 34px; }
  .rate-btn { width: 34px; height: 34px; border-radius: 50%; border: none; background: none; cursor: pointer; display: grid; place-items: center;
    color: var(--secondary-text-color); padding: 0; }
  .rate-btn:hover { background: var(--rema-tint); }
  .rate-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; stroke-linecap: round; }
  .rate-btn.on svg { fill: currentColor; }
  .rate-btn.like.on { color: var(--rema-accent); }
  .rate-btn.dislike.on { color: var(--secondary-text-color); }
  .rate-btn.favorite.on { color: #e5484d; }
  .rate-btn:focus-visible, .setting-row:focus-visible, .rc-open:focus-visible { outline: 2px solid var(--rema-accent); outline-offset: 2px; }
  .subnav { margin: 0 0 12px; }
  .btn.surprise { border-style: dashed; }
  .badge.surprise { background: color-mix(in srgb, #e5484d 15%, transparent); color: var(--primary-text-color); }
  .rc-list { display: grid; margin-top: 4px; }
  .rc-item { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; border-top: 1px solid var(--divider-color); }
  .rc-item:first-child { border-top: none; }
  .rc-open { display: grid; gap: 2px; text-align: left; background: none; border: none; color: var(--primary-text-color); font-size: 15px;
    padding: 12px 4px; cursor: pointer; min-width: 0; }
  .rc-open b { overflow-wrap: anywhere; }
  .dialog.wide { width: min(680px, calc(100vw - 24px)); }
  .rc-head { display: flex; gap: 8px; align-items: center; }
  .rc-name { flex: 1; min-width: 0; font-size: 20px !important; font-weight: 600; }
  .rc-meta { grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }
  .rc-meta input[type=number] { width: 100%; }
  .rc-step textarea { min-height: 44px; }
  .rc-ing, .rc-step { display: flex; gap: 6px; align-items: center; margin-bottom: 6px; }
  .rc-ing .amount { width: 110px; flex: none; }
  .rc-prod { margin: -4px 0 8px 116px; }
  .rc-prod .link { margin-left: 6px; font-size: .8rem; }
  .rc-sugg:empty { display: none; }
  .rc-sugg { margin: -2px 0 10px 116px; }
  .rc-sugg-list { display: grid; gap: 4px; border: 1px solid var(--divider-color); border-radius: 10px; padding: 4px; background: var(--card-background-color); }
  .rc-sugg-item { display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: 8px; align-items: center; text-align: left; padding: 4px 6px;
    border: none; border-radius: 8px; background: none; cursor: pointer; color: var(--primary-text-color); font: inherit; }
  .rc-sugg-item:hover { background: var(--secondary-background-color); }
  .rc-sugg-item img, .rc-sugg-item .noimg { width: 36px; height: 36px; object-fit: contain; border-radius: 6px; background: #fff; }
  .rc-sugg-item .what { display: grid; min-width: 0; }
  .rc-sugg-item .what b { font-size: .9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rc-sugg-item .price { font-weight: 700; white-space: nowrap; } .rc-sugg-item .price.sale { color: var(--rema-sale); }
  @media (max-width: 600px) { .rc-prod, .rc-sugg { margin-left: 0; } }
  .cand-swaps { margin: 0; padding-left: 16px; }
  .rr-search { margin-bottom: 12px; }
  .rc-missing { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: -2px; margin-bottom: 10px; }
  .rc-prod .check.inline { display: inline-flex; gap: 4px; margin-left: 8px; }
  .rc-photo { width: 100%; max-height: 260px; object-fit: cover; border-radius: 12px; margin: 4px 0 10px; }
  .rr-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin: 12px 0; }
  .rr-card { display: grid; gap: 4px; align-content: start; padding: 8px; border: 1px solid var(--divider-color); border-radius: 12px; background: var(--secondary-background-color); }
  .rr-card .btn { justify-self: start; margin-top: 4px; }
  .rr-img { padding: 0; border: none; background: var(--card-background-color); border-radius: 8px; overflow: hidden; aspect-ratio: 4 / 3; cursor: pointer; }
  .rr-img img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .rr-title { font-size: .95rem; line-height: 1.25; overflow-wrap: anywhere; }
  .rr-badges { display: flex; flex-wrap: wrap; gap: 4px; }
  .rr-badges:empty { display: none; }
  @media (max-width: 600px) { .rr-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } }
  .rc-step .num { flex: none; width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: 13px;
    background: var(--rema-tint); color: var(--rema-accent); font-weight: 600; }
  .icon-btn { flex: none; width: 32px; height: 32px; border-radius: 50%; border: none; background: none; cursor: pointer;
    color: var(--secondary-text-color); display: grid; place-items: center; }
  .icon-btn svg { width: 16px; height: 16px; stroke: currentColor; stroke-width: 2; fill: none; }
  .rc-targets { display: grid; gap: 6px; margin-top: 12px; }
  .chain-logo { --c: #888; flex: none; width: 52px; height: 52px; border-radius: 50%; background: #fff; display: grid; place-items: center;
    overflow: hidden; box-shadow: 0 0 0 3px var(--c), 0 2px 8px rgba(0, 0, 0, .12); }
  /* Beats the product-photo rules (.ev img, .prod img, .line img) the logo sits inside. */
  .chain-logo > img.cl { width: 78%; height: 78%; max-width: none; margin: 0; padding: 0; border: 0; border-radius: 0;
    background: none; object-fit: contain; display: block; }
  .chain-logo span { font-weight: 700; color: var(--c); text-transform: uppercase; }
  .chain-logo.big { width: 44px; height: 44px; }
  .chain-logo.tiny { width: 34px; height: 34px; font-size: 12px; }
  .chain-logo.tiny { width: 28px; height: 28px; box-shadow: 0 0 0 2px var(--c); }
  .chain-list .chain-logo, .chain-save .chain-logo { width: 36px; height: 36px; box-shadow: 0 0 0 2px var(--c); }
  .chain-row { display: flex; gap: 14px; overflow-x: auto; padding: 8px 4px 4px; }
  .chain-btn { display: grid; justify-items: center; gap: 8px; background: none; border: none; cursor: pointer; color: var(--primary-text-color);
    font-size: 13px; min-width: 64px; padding: 4px; }
  .chain-btn:focus-visible, .cheaper:focus-visible { outline: 2px solid var(--rema-accent); outline-offset: 2px; border-radius: 12px; }
  .cheaper { display: inline-flex; align-items: center; gap: 6px; margin-top: 4px; border: 1px solid var(--divider-color); background: var(--rema-card);
    color: var(--primary-text-color); border-radius: 999px; padding: 3px 10px 3px 4px; font-size: 12px; cursor: pointer; max-width: 100%; }
  .cheaper.static { cursor: default; }
  ul.plain { margin: 4px 0 10px; padding-left: 20px; }
  ul.plain li { margin: 2px 0; }
  .cheaper.plain { padding: 3px 10px; color: var(--secondary-text-color); }
  .everywhere { margin-top: 12px; }
  .everywhere-results h3 { margin: 14px 0 4px; }
  .best-line { margin: 12px 0 0; padding: 8px 12px; border-radius: 10px; background: color-mix(in srgb, var(--rema-ok) 14%, transparent); }
  .evs { list-style: none; padding: 0; margin: 0; }
  .ev { display: grid; grid-template-columns: auto 44px minmax(0, 1fr) auto auto; gap: 10px; align-items: center; padding: 8px 4px;
    border-top: 1px solid var(--divider-color); }
  .ev:first-child { border-top: none; }
  .ev.best { background: color-mix(in srgb, var(--rema-ok) 9%, transparent); border-radius: 10px; }
  .ev img, .ev .noimg { width: 44px; height: 44px; object-fit: contain; border-radius: 8px; background: #fff; }
  .ev .what { display: grid; min-width: 0; } .ev .what b { overflow-wrap: anywhere; }
  .ev .badge { justify-self: start; margin-top: 2px; }
  .ev-price { font-weight: 700; white-space: nowrap; } .ev-price.sale { color: var(--rema-sale); }
  .ev .what .muted { display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
  /* On a phone the button sits under the price, so a row is two lines, not four. */
  @media (max-width: 600px) {
    .ev { grid-template-columns: auto 40px minmax(0, 1fr) auto; row-gap: 4px; padding: 8px 2px; }
    .ev > .chain-logo, .ev > img, .ev > .noimg, .ev > .what { grid-row: 1 / 3; }
    .ev > .ev-price { grid-column: 4; grid-row: 1; justify-self: end; align-self: end; }
    .ev > .btn { grid-column: 4; grid-row: 2; justify-self: end; align-self: start; padding: 4px 10px; min-height: 0; font-size: .85rem; }
    .ev > .ev-btns { grid-column: 3 / 5; grid-row: 3; justify-self: end; }
    .ev > .ev-btns .btn { padding: 4px 10px; min-height: 0; font-size: .85rem; }
    .ev img, .ev .noimg { width: 40px; height: 40px; }
  }
  .day-row.past { opacity: .55; }
  .week-head { margin: 14px 0 4px; font-size: .95rem; color: var(--secondary-text-color); }
  .bell { flex: none; width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--divider-color); background: none; cursor: pointer;
    color: var(--secondary-text-color); display: inline-grid; place-items: center; padding: 0; }
  .bell svg { width: 17px; height: 17px; stroke: currentColor; stroke-width: 1.8; fill: none; stroke-linejoin: round; }
  .bell.on { color: var(--rema-accent); border-color: var(--rema-accent); background: color-mix(in srgb, var(--rema-accent) 12%, transparent); }
  .bell.on svg { fill: currentColor; }
  .prod { position: relative; }
  /* The bell in the corner of the product's photo. */
  .prod > .bell { position: absolute; top: 8px; right: 8px; width: 30px; height: 30px; background: var(--card-background-color); box-shadow: 0 1px 4px rgba(0, 0, 0, .15); }
  .prod > .bell.on { background: color-mix(in srgb, var(--rema-accent) 18%, var(--card-background-color)); }
  .watch-title { display: flex; align-items: center; gap: 8px; }
  .watch-title svg, .inline-icon { width: 22px; height: 22px; stroke: var(--rema-accent); stroke-width: 1.8; fill: none; vertical-align: middle; }
  .inline-icon { width: 16px; height: 16px; }
  .watch-list { display: grid; gap: 12px; margin-top: 8px; }
  .watch-item { border: 1px solid var(--divider-color); border-radius: 12px; padding: 8px 10px; }
  .watch-head { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
  .watch-deals { list-style: none; margin: 4px 0 0; padding: 0; }
  .watch-deals .ev-price s { display: block; font-weight: 400; }
  .watch-quiet .chip { margin: 2px; }
  .fav-row img, .fav-row .noimg { width: 36px; height: 36px; object-fit: contain; border-radius: 6px; background: #fff; flex: none; }
  .plan-title { display: flex; align-items: center; gap: 8px; }
  .plan-title .help-q { font-size: 13px; }
  .plan-checks { margin: 8px 0 4px; }
  .plan-actions { display: grid; gap: 8px; margin-top: 12px; }
  .plan-actions .send-main { width: 100%; justify-content: center; }
  .plan-actions .later { margin: 0; }
  .plan-more { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
  .plan-more .btn { justify-content: center; }
  .help-row { display: flex; align-items: flex-start; justify-content: flex-end; gap: 8px; margin: 6px 0; }
  .help-row .help-text { flex: 1; margin: 2px 0; }
  .help-q { flex: none; width: 24px; height: 24px; border-radius: 50%; border: 1px solid var(--divider-color); background: none; cursor: pointer;
    color: var(--secondary-text-color); font-weight: 700; font-size: .8rem; line-height: 1; display: grid; place-items: center; padding: 0; }
  .help-q[aria-expanded="true"] { background: var(--secondary-background-color); color: var(--primary-text-color); }
  /* A tall dialog: at most 80 % of the screen, with its top (✕) and bottom (buttons) kept in place. */
  .dialog.sheet { padding-top: 0; padding-bottom: 0; max-height: min(80vh, 760px); max-height: min(80dvh, 760px); }
  .dialog-bottom.wrap { flex-wrap: wrap; justify-content: flex-start; }
  .dialog-bottom .spacer { flex: 1; }
  @media (max-width: 600px) {
    .dialog-bottom { gap: 6px; padding: 8px 0 12px; }
    .dialog-bottom .btn { padding: 6px 12px; min-height: 0; font-size: .9rem; }
    .dialog-top .close { width: 32px; height: 32px; }
    /* The ✕ at the top closes it; the buttons stay on one line. */
    .rc-sheet .dialog-bottom [data-action="modal-close"] { display: none; }
    .rc-sheet .rc-meta { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  }
  .dialog-top, .dialog-bottom { position: sticky; z-index: 1; background: var(--rema-solid-card); display: flex; align-items: center; gap: 8px; }
  .dialog-top { top: 0; padding: 14px 0 8px; margin-bottom: 4px; }
  .dialog-top h2 { margin: 0; flex: 1; font-size: 1.15rem; overflow-wrap: anywhere; }
  .dialog-top > div { flex: 1; min-width: 0; }
  .day-row.skipped-day .day { opacity: 0.6; background: var(--rema-subtle); }
  .dialog-top > div p { margin: 2px 0 0; }
  /* What a day is: four equal choices, two by two on a phone, labels never on top of each other. */
  .dialog .seg.fit.day-kinds { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px;
    width: 100%; max-width: 100%; box-sizing: border-box; margin: 4px 0 12px; border-radius: 16px; }
  .dialog .seg.fit.day-kinds button { min-width: 0; white-space: normal; overflow-wrap: anywhere; line-height: 1.2;
    padding: 9px 6px; border-radius: 12px; }
  @media (max-width: 600px) {
    .dialog .seg.fit.day-kinds { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  .dialog-top .close { width: 36px; height: 36px; background: var(--secondary-background-color); }
  .dialog-bottom { bottom: 0; justify-content: flex-end; padding: 10px 0 14px; margin-top: 8px; border-top: 1px solid var(--divider-color); }
  .cheaper { justify-self: start; width: fit-content; }
  .cheaper > span:not(.chain-logo) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chain-save { align-items: center; }
  .chain-save > span:not(.chain-logo) { flex: 1; min-width: 200px; }
  .chain-list { border-top: 4px solid var(--c); }
  .chain-list .row { gap: 12px; align-items: center; }
  .clines { list-style: none; padding: 0; margin: 8px 0 0; }
  .cline { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; grid-template-areas: "box what cost ctrl"; gap: 8px;
    align-items: center; padding: 10px 0; border-top: 1px solid var(--divider-color); }
  .cline .box { grid-area: box; } .cline .what { grid-area: what; } .cline .cost { grid-area: cost; }
  .cline .ctrl { grid-area: ctrl; display: inline-flex; align-items: center; gap: 4px; }
  .cline .what { display: grid; min-width: 0; } .cline .what b { overflow-wrap: anywhere; }
  .cline.bought .what b { text-decoration: line-through; opacity: .6; }
  .cline .box { width: 28px; height: 28px; border-radius: 8px; border: 2px solid var(--c, var(--rema-accent)); background: none; cursor: pointer;
    color: var(--rema-on-accent); font-weight: 700; }
  .cline.bought .box { background: var(--c, var(--rema-accent)); color: #fff; }
  .stepper { display: inline-flex; align-items: center; gap: 2px; }
  .stepper .icon-btn { font-size: 18px; }
  .chain-pick { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; margin: 12px 0; }
  .chain-choice { display: flex; align-items: center; gap: 10px; padding: 8px; border-radius: 12px; border: 1px solid var(--divider-color); cursor: pointer; }
  .chain-choice .chain-logo { width: 36px; height: 36px; box-shadow: 0 0 0 2px var(--c); }
  .clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  @media (max-width: 600px) { .cline { grid-template-columns: auto minmax(0, 1fr) auto; grid-template-areas: "box what cost" ". ctrl ctrl"; row-gap: 2px; } }
  .setting-rows { display: grid; margin-top: 8px; }
  .setting-row { display: grid; grid-template-columns: 40px 1fr auto; gap: 12px; align-items: center; width: 100%; text-align: left;
    background: none; border: none; border-top: 1px solid var(--divider-color); padding: 14px 4px; color: var(--primary-text-color);
    font-size: 15px; cursor: pointer; }
  .setting-row:first-child { border-top: none; }
  .setting-row:hover { background: var(--rema-tint); }
  .setting-icon { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center;
    background: var(--rema-tint); color: var(--rema-accent); }
  .setting-icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .setting-text { display: grid; gap: 2px; min-width: 0; }
  .setting-text .small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chev { font-size: 22px; color: var(--secondary-text-color); }
  .settings-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .settings-head h1 { margin: 0; }
  .inventory-fields .field { flex: 1; min-width: 100px; }
  @media (max-width: 600px) { .inventory-fields .field:first-child { flex-basis: 100%; } }
  .inventory-fields input, .inventory-fields select { box-sizing: border-box; width: 100%; min-width: 0; }
  .store-chooser { display: flex; align-items: center; flex-wrap: wrap; gap: 12px 20px; padding: 12px 16px; margin-bottom: 16px; border: 1px solid var(--divider-color); border-radius: 12px; background: var(--rema-card); }
  .store-chooser .field { margin: 0; min-width: 200px; }
  .store-chooser > .small { flex: 1; min-width: 180px; }
  .store-switch-actions { display: grid; gap: 8px; margin: 20px 0; }
  .store-switch-actions p { margin: 0 0 12px; }
  .freezer-section { border-top: 1px solid var(--divider-color); margin-top: 24px; padding-top: 8px; text-align: left; }
  .freezer-section.flat { border-top: 0; margin-top: 4px; padding-top: 0; }
  details.fold > summary { cursor: pointer; font-weight: 600; padding: 6px 0; list-style-position: inside; }
  details.fold[open] > summary { margin-bottom: 6px; }
  .freezer-card > summary .fold-title { font-size: 18px; font-weight: 700; }
  .pickday.skipped { opacity: .6; }
  .update-banner { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
  .batch-plan-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; align-items: center; border-top: 1px solid var(--divider-color); }
  .batch-plan-row .setting-text { overflow-wrap: anywhere; }
  .batch-plans .setting-row { grid-template-columns: 1fr auto; padding: 14px 8px; }
  .batch-steps { display: flex; flex-wrap: wrap; gap: 12px 28px; padding: 12px 12px 12px 32px; background: var(--rema-subtle); border-radius: 12px; color: var(--secondary-text-color); }
  .batch-steps [aria-current] { color: var(--rema-accent); font-weight: 700; }
  .batch-dishes { display: grid; gap: 12px; margin: 20px 0; }
  .batch-dish { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 20px; padding: 18px; border: 1px solid var(--divider-color); border-radius: 14px; }
  .batch-dish-name { display: flex; gap: 10px; align-items: center; min-width: 0; }
  .batch-dish h2 { margin: 0; font-size: 18px; overflow-wrap: anywhere; }
  .batch-number { display: grid; place-items: center; width: 28px; height: 28px; flex-shrink: 0; border-radius: 50%; background: var(--rema-tint); color: var(--rema-accent); font-weight: 700; }
  .batch-portions { margin: 0; }
  .batch-dish p { grid-column: 1 / -1; margin: 2px 0; }
  .batch-dish > .btn { justify-self: start; }
  .batch-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; padding: 20px 0; margin-top: 12px; border-top: 1px solid var(--divider-color); }
  .batch-footer strong { display: block; font-size: 24px; color: var(--rema-accent); }
  .shopping-tools .row { margin-top: 12px; }
  @media (max-width: 520px) { .batch-dish { grid-template-columns: 1fr; } .batch-portions { max-width: 220px; } .batch-footer > .btn { width: 100%; } }
  .settings-head p { margin: 6px 0 0; }
  .settings-intro { margin: 0 0 20px; }
  .settings-intro h1 { margin-bottom: 8px; }
  .settings-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
  .settings-groups .card { margin: 0; min-width: 0; }
  .setting-text .small { white-space: normal; overflow-wrap: anywhere; }
  .savebar [data-settings-status] { margin-right: auto; }
  @media (max-width: 760px) { .settings-groups { grid-template-columns: 1fr; } }
  .btn.back { padding: 6px 12px; }
  .wishes { margin-top: 12px; } .hero .wishes { text-align: center; }
  .note-preview { margin: 6px 0 0; white-space: pre-line; overflow-wrap: anywhere; }
  h2.flush { margin-top: 0; }
  .day.today { box-shadow: inset 3px 0 0 var(--rema-accent); }
  .seg { display: inline-flex; gap: 2px; padding: 3px; margin-top: 12px; border-radius: 999px; background: var(--rema-subtle); }
  .seg button { border: none; background: none; color: var(--secondary-text-color); padding: 7px 16px; border-radius: 999px;
    font-size: 14px; font-weight: 500; cursor: pointer; }
  .seg button.active { background: var(--rema-accent); color: var(--rema-on-accent); }
  .seg .narrow { display: none; }
  .seg.scroll { display: flex; max-width: 100%; overflow-x: auto; gap: 4px; scrollbar-width: none; }
  .seg.scroll::-webkit-scrollbar { display: none; }
  .seg.scroll button { flex: none; white-space: nowrap; padding: 7px 14px; }
  @media (max-width: 600px) {
    .seg.fit { display: flex; max-width: 100%; }
    .seg.fit button { flex: 1 1 0; min-width: 0; padding: 7px 6px; white-space: nowrap; }
    .seg.fit .wide { display: none; }
    .seg.fit .narrow { display: inline; }
  }
  /* Like Home Assistant's dialogs, so a theme's scrim (Theme Studio's blur) reaches these too. */
  .scrim { position: fixed; inset: 0; z-index: 20; background: var(--mdc-dialog-scrim-color, rgba(0, 0, 0, .45));
    -webkit-backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none); backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none); }
  .dialog { position: fixed; z-index: 21; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(520px, calc(100vw - 32px));
    max-height: calc(100vh - 32px); overflow: auto; padding: 18px; border-radius: var(--ha-dialog-border-radius, var(--ha-card-border-radius, 16px));
    background: var(--rema-solid-card); border: 1px solid var(--divider-color); box-shadow: 0 12px 40px rgba(0, 0, 0, .3); }
  .dialog h2 { margin-top: 0; } .dialog-actions { margin-top: 12px; }
  .link { background: none; border: none; color: var(--primary-color); cursor: pointer; text-decoration: underline; font-size: inherit; }
  .banner { border-radius: 10px; padding: 10px 14px; margin-bottom: 12px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .banner.info { background: var(--rema-tint); }
  .banner.warn { background: color-mix(in srgb, var(--rema-warn) 18%, transparent); }
  .banner.error { background: color-mix(in srgb, var(--rema-sale) 15%, transparent); }
  .spinner { width: 18px; height: 18px; border: 3px solid var(--rema-tint); border-top-color: var(--rema-accent); border-radius: 50%;
    display: inline-block; animation: spin 1s linear infinite; vertical-align: middle; }
  .spinner.small { width: 14px; height: 14px; border-width: 2px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hero { text-align: center; padding: 32px 18px; } .hero .row { justify-content: center; }
  .hero-icon { width: 72px; height: 72px; margin-bottom: 8px; }
  .price { text-align: right; display: flex; flex-direction: column; } .price .big { font-size: 22px; font-weight: 700; color: var(--rema-accent); }
  .price.over .big { color: var(--rema-sale); }
  .days { display: grid; gap: 8px; margin-top: 12px; }
  .day { display: grid; grid-template-columns: 130px 1fr auto; gap: 12px; align-items: center; text-align: left; width: 100%;
    background: var(--rema-subtle); border: none; border-radius: 10px; padding: 12px 14px;
    color: var(--primary-text-color); font-size: 15px; cursor: pointer; }
  .day .date { font-weight: 600; color: var(--rema-accent); } .day .meta { color: var(--secondary-text-color); font-size: 13px; white-space: nowrap; }
  .badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 999px;
    background: var(--rema-subtle); color: var(--secondary-text-color); vertical-align: middle; }
  .badge.offer { background: var(--rema-sale); color: var(--rema-on-sale); }
  .badge.eco, .badge.sent, .badge.ready { background: var(--rema-ok); color: var(--rema-on-accent); }
  .badge.from { background: var(--info-color, #039be5); color: #fff; }
  .badge.doubt { background: var(--rema-warn); color: #000; }
  .badge.skipped { background: var(--secondary-text-color); color: var(--rema-on-accent); }
  .badge.over { background: var(--error-color, #db4437); color: #fff; }
  .left-box { background: var(--rema-subtle); border-radius: 10px; padding: 8px 12px; margin: 10px 0; }
  .left-box p { margin: 0 0 6px; }
  .left-box input { width: 90px; }
  .lunch-ideas { margin: 6px 0 0; padding-left: 20px; }
  .badge.remembered { background: var(--rema-accent); color: var(--rema-on-accent); }
  .line.is-skipped .what, .line.is-skipped .cost { opacity: 0.55; text-decoration: line-through; }
  .review { list-style: none; padding: 0; margin: 10px 0 0; display: grid; gap: 10px; }
  .review-line { background: var(--card-background-color, #fff); border-radius: 10px; padding: 10px 12px; }
  .review-what { display: flex; flex-direction: column; gap: 2px; }
  .alts { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
  .alt { display: flex; gap: 8px; align-items: center; text-align: left; background: var(--rema-subtle); border: 1px solid transparent;
    border-radius: 10px; padding: 6px 10px; cursor: pointer; color: var(--primary-text-color); font-size: 13px; max-width: 100%; }
  .alt:hover { border-color: var(--rema-accent); }
  .alt img { width: 32px; height: 32px; object-fit: contain; border-radius: 6px; background: #fff; }
  .alt span { display: flex; flex-direction: column; min-width: 0; } .alt b { font-size: 13px; }
  .review-actions { margin-top: 4px; }
  .prod .avis { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .badge.draft { background: var(--rema-accent); color: var(--rema-on-accent); }
  details { margin-top: 14px; } summary { cursor: pointer; color: var(--secondary-text-color); }
  .checklist { list-style: none; padding: 0; } .checklist li { padding: 3px 0; } .checklist .bad { color: var(--rema-sale); }
  .chips { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 8px; margin-bottom: 8px; }
  .chip { border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color);
    border-radius: 999px; padding: 8px 14px; white-space: nowrap; cursor: pointer; font-size: 14px; }
  .chip.active { background: var(--rema-accent); color: var(--rema-on-accent); border-color: var(--rema-accent); }
  .recipe h1 { font-size: 26px; }
  .recipe-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 24px; }
  .recipe-grid section { min-width: 0; overflow-wrap: anywhere; }
  .ingredients { list-style: none; padding: 0; margin: 0; }
  .ingredients li { display: flex; gap: 10px; align-items: center; padding: 9px 0; border-bottom: 1px solid var(--divider-color);
    font-size: 17px; cursor: pointer; }
  .ingredients .amount { font-weight: 600; min-width: 70px; }
  .box { width: 22px; height: 22px; border: 2px solid var(--rema-accent); border-radius: 6px; display: inline-flex;
    align-items: center; justify-content: center; color: var(--rema-on-accent); flex: none; font-size: 14px; }
  li.done .box { background: var(--rema-accent); } li.done { opacity: .5; text-decoration: line-through; }
  .steps { list-style: none; padding: 0; margin: 0; }
  .step { padding: 12px 0; border-bottom: 1px solid var(--divider-color); display: flex; gap: 10px; align-items: flex-start;
    justify-content: space-between; flex-wrap: wrap; }
  .step-text { font-size: 19px; line-height: 1.5; cursor: pointer; flex: 1; min-width: 200px; display: flex; gap: 12px; }
  .num { flex: none; width: 30px; height: 30px; border-radius: 50%; background: var(--rema-accent); color: var(--rema-on-accent); font-weight: 700;
    display: inline-flex; align-items: center; justify-content: center; font-size: 15px; }
  .step.done .step-text { opacity: .45; text-decoration: line-through; } .step.done .num { background: var(--rema-ok); }
  .step.alarm { background: color-mix(in srgb, var(--rema-sale) 15%, transparent); border-radius: 10px; }
  .timer { border: 1px solid var(--rema-accent); color: var(--rema-accent); background: none; border-radius: 999px; padding: 6px 12px;
    font-size: 14px; cursor: pointer; font-variant-numeric: tabular-nums; }
  .timer.running { background: var(--rema-accent); color: var(--rema-on-accent); }
  .tip { background: var(--rema-subtle); padding: 10px 14px; border-radius: 10px; }
  .lines, .history, .favs, .rema { list-style: none; padding: 0; margin: 0; }
  .line { display: grid; grid-template-columns: 48px 1fr auto; gap: 12px; align-items: center; padding: 10px 0;
    border-bottom: 1px solid var(--divider-color); }
  .line img, .noimg { width: 48px; height: 48px; object-fit: contain; border-radius: 8px; background: #fff; }
  .noimg { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); background: var(--secondary-background-color); }
  .what { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .what .title { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; }
  .note { color: var(--rema-warn); font-size: 13px; }
  .cost { text-align: right; display: flex; flex-direction: column; font-size: 13px; color: var(--secondary-text-color); white-space: nowrap; }
  .cost b { color: var(--primary-text-color); font-size: 15px; }
  .rema li { padding: 6px 0; border-bottom: 1px solid var(--divider-color); } .rema .bought { opacity: .45; text-decoration: line-through; }
  .hist, .fav { display: flex; gap: 10px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--divider-color); }
  .hist .what, .fav .what { flex: 1; cursor: pointer; } .fav.edit { flex-direction: column; align-items: stretch; }
  .stat b.ell { font-size: 15px; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* Indkøb – the receipt list */
  .receipt-row { cursor: pointer; }
  .receipt-row .receipt-amt { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; }
  .receipt-row .save { color: var(--rema-accent); }
  .save { color: var(--rema-accent); }
  .receipt-row .chev { color: var(--secondary-text-color); font-size: 22px; line-height: 1; margin-left: 2px; }
  /* A digital receipt, styled like the REMA 1000 app */
  .receipt-paper { max-width: 420px; margin-inline: auto; background: #fff; color: #0a1f44; border-radius: 10px; }
  :host([dark]) .receipt-paper { background: #f6f8ff; }
  .receipt-paper .muted { color: #5b6b8c; }
  .rc-head { text-align: center; font-weight: 800; font-size: 30px; letter-spacing: 1px; color: #1664ff; padding: 6px 0 12px; }
  .rc-store { display: flex; justify-content: space-between; gap: 12px; border-top: 1px solid #d9e0f0; border-bottom: 1px solid #d9e0f0; padding: 12px 0; font-size: 14px; }
  .rc-store-right { text-align: right; white-space: nowrap; }
  .rc-store b { font-size: 15px; }
  .rc-items { padding: 6px 0; }
  .rc-line { display: grid; grid-template-columns: 1fr auto; column-gap: 10px; padding: 7px 0; align-items: baseline; }
  .rc-name { font-weight: 600; }
  .rc-qty { color: #1664ff; font-weight: 600; }
  .rc-price { font-weight: 700; text-align: right; }
  .rc-disc { grid-column: 1 / -1; color: #5b6b8c; font-size: 13px; }
  .rc-disc span { color: #e8930c; font-weight: 700; }
  .rc-total { display: flex; justify-content: space-between; font-weight: 800; font-size: 26px; border-top: 1px solid #d9e0f0; padding: 12px 0 2px; }
  .rc-sub { display: flex; justify-content: space-between; font-size: 14px; padding: 3px 0; }
  .rc-foot { border-top: 1px solid #d9e0f0; margin-top: 10px; padding-top: 10px; }
  .rc-save span:last-child, .rc-save { color: #e8930c; font-weight: 700; }
  .rc-bon { text-align: center; margin-top: 14px; word-break: break-all; }
  /* Økonomi – the REMA spend overview */
  .spend-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .spend-stats .save-stat b { color: var(--rema-accent); }
  .spend-chart { width: 100%; height: auto; margin-top: 8px; overflow: visible; }
  .spend-bar rect { fill: var(--rema-accent); transform-box: fill-box; transform-origin: bottom; animation: spendGrow .5s cubic-bezier(.2,.75,.25,1) both; animation-delay: var(--d, 0s); cursor: pointer; transition: fill .15s; }
  .spend-bar:hover rect { fill: color-mix(in srgb, var(--rema-accent) 72%, #000); }
  .spend-chart .axis { fill: var(--secondary-text-color); font-size: 9px; }
  @keyframes spendGrow { from { transform: scaleY(0); } to { transform: scaleY(1); } }
  @media (max-width: 560px) { .spend-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .rl-list { display: flex; flex-direction: column; gap: 4px; margin: 6px 0; }
  .rl-list .rowitem { padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
  .rl-form { margin-top: 6px; }
  /* Varer – the bought-items list */
  .item-row .item-stats { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; }
  .item-row .count { font-weight: 700; }
  .item-row.frequent .star { color: #e8930c; }
  .field { display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: var(--secondary-text-color); margin: 8px 0; }
  .field.inline { flex-direction: row; align-items: center; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 4px 16px; }
  input[type=text], input[type=number], input[type=date], input[type=search], input[type=url], input:not([type]), select, textarea {
    font: inherit; font-size: 16px; color: var(--primary-text-color); background: var(--secondary-background-color, transparent);
    border: 1px solid var(--divider-color); border-radius: 8px; padding: 8px 10px; }
  input[type=number] { width: 90px; } textarea { width: 100%; resize: vertical; }
  .checks { display: flex; flex-wrap: wrap; gap: 6px 18px; }
  .check { display: flex; align-items: center; gap: 6px; font-size: 15px; padding: 4px 0; }
  .rowitem { padding: 6px 0; border-bottom: 1px dashed var(--divider-color); }
  .results { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; margin-top: 8px; }
  .shop-search { margin-top: 14px; }
  .line.tappable { cursor: pointer; } .line.tappable:hover { background: var(--rema-subtle); }
  .line-head { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
  .line-head img, .line-head .noimg { width: 56px; height: 56px; object-fit: contain; border-radius: 8px; background: #fff; flex: 0 0 auto; }
  .line-head h2 { margin: 0; }
  .stepper { align-items: center; gap: 8px; margin: 10px 0; } .stepper .count { min-width: 28px; text-align: center; font-size: 18px; }
  .small-h { font-size: 16px; margin: 14px 0 6px; }
  .badge.mealie { background: #e58325; color: #fff; }
  a.btn { text-decoration: none; display: inline-flex; align-items: center; }
  .mic.on { background: var(--rema-sale); color: var(--rema-on-sale); border-color: transparent; }
  details.nutrition table { width: 100%; border-collapse: collapse; margin-top: 6px; }
  details.nutrition td { padding: 6px 4px; border-bottom: 1px solid var(--divider-color); } details.nutrition td:last-child { text-align: right; font-weight: 600; }
  .nutri { background: var(--rema-subtle); padding: 8px 12px; border-radius: 10px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; margin: 10px 0; }
  .kpi { display: flex; flex-direction: column; background: var(--rema-subtle); border-radius: 12px; padding: 10px 12px; }
  .kpi .big { font-size: 22px; font-weight: 700; color: var(--rema-accent); } .kpi .big.warn { color: var(--rema-warn); }
  .hrow { display: flex; gap: 12px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--divider-color); }
  .hrow .what { flex: 1; }
  .meter { height: 8px; border-radius: 999px; background: var(--rema-subtle); overflow: hidden; margin-top: 6px; }
  .meter span { display: block; height: 100%; border-radius: 999px; background: var(--rema-accent); }
  .meter.low span { background: var(--rema-warn); } .meter.over span { background: var(--rema-sale); }
  .result .add { color: var(--rema-accent); font-weight: 600; white-space: nowrap; }
  .result-pair { display: flex; gap: 6px; align-items: stretch; min-width: 0; }
  .result-pair > .result { flex: 1; min-width: 0; }
  .result-pair > .to-rema { flex: 0 0 auto; white-space: nowrap; align-self: center; }
  /* A phone: the REMA button under the row, at its right end. */
  @media (max-width: 600px) {
    .result-pair { flex-wrap: wrap; gap: 4px; }
    .result-pair > .result { flex-basis: 100%; }
    .result-pair > .to-rema { margin-left: auto; padding: 4px 10px; min-height: 0; font-size: .85rem; }
  }
  .ev-btns { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .result .badge, .result .add { display: inline-block; flex: 0 0 auto; }
  .options { display: grid; gap: 8px; }
  .option { display: flex; flex-direction: column; gap: 3px; text-align: left; width: 100%; background: var(--rema-subtle);
    border: 1px solid transparent; border-radius: 10px; padding: 12px 14px; color: var(--primary-text-color); font-size: 15px; cursor: pointer; }
  .option:hover:not([disabled]) { border-color: var(--rema-accent); }
  .option[disabled] { cursor: default; opacity: .75; }
  .pantry-item { display: flex; gap: 10px; align-items: center; justify-content: space-between; padding: 10px 0;
    border-bottom: 1px solid var(--divider-color); }
  .pantry-item .what { flex: 1; } .pantry-item .btn, .pantry-item .badge { white-space: nowrap; flex: 0 0 auto; }
  .link.small { font-size: 12px; padding: 2px 0; }
  .result { display: flex; gap: 10px; align-items: center; text-align: left; background: var(--rema-subtle);
    border: none; border-radius: 10px; padding: 8px 10px; cursor: pointer; color: var(--primary-text-color); }
  .result img { width: 40px; height: 40px; object-fit: contain; background: #fff; border-radius: 6px; }
  .result span { display: flex; flex-direction: column; flex: 1; }
  .prod-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
  .prod { display: flex; flex-direction: column; gap: 6px; padding: 8px; border: 1px solid var(--divider-color);
    border-radius: 12px; background: var(--rema-subtle); min-width: 0; font-size: 14px; }
  .prod img, .prod .noimg { width: 100%; height: 90px; object-fit: contain; border-radius: 8px; }
  .prod img { background: #fff; } /* product photos are shot on white */
  .prod-body { display: flex; flex-direction: column; gap: 3px; flex: 1; min-width: 0; overflow-wrap: break-word; hyphens: auto; }
  .prod-body > b { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .prod-price { display: flex; flex-wrap: wrap; gap: 0 6px; align-items: baseline; font-size: 16px; }
  .prod .btn { width: 100%; }
  .sale { color: var(--rema-sale); font-weight: 700; }
  .favlist { list-style: none; padding: 0; margin: 8px 0 0; }
  .fav-row { display: flex; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--divider-color); }
  .fav-row .what { flex: 1; }
  .filter { width: 100%; margin-top: 10px; }
  .sticky { position: sticky; bottom: 0; background: var(--rema-solid-card); padding: 12px 0 calc(12px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px)));
    border-top: 1px solid var(--divider-color); }
  /* Last in the settings view, so it stays at the bottom of the screen all the way down. */
  .savebar { position: sticky; bottom: calc(8px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); z-index: 2; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    margin-top: 16px; padding: 12px 16px; background: var(--rema-solid-card); border: 1px solid var(--divider-color);
    border-radius: var(--ha-card-border-radius, 12px); box-shadow: 0 -2px 12px rgba(0, 0, 0, .12); }
  .toast { position: fixed; left: 50%; bottom: calc(24px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); transform: translateX(-50%); background: var(--primary-text-color); color: var(--primary-background-color);
    padding: 12px 20px; border-radius: 10px; z-index: 40; max-width: 90vw; box-shadow: 0 4px 12px rgba(0,0,0,.3); }
  .budget-card .budget-left { display: flex; align-items: baseline; gap: 8px; margin: 4px 0 8px; flex-wrap: wrap; }
  .budget-card .big { font-size: 28px; font-weight: 600; }
  .budget-card .big.over, .stat b.over { color: var(--rema-sale, #d33); }
  .stat b.ok { color: var(--success-color, #2e7d32); }
  .budget-bar { position: relative; height: 10px; border-radius: 5px; background: var(--divider-color, rgba(127,127,127,.2)); margin: 6px 0; }
  .budget-bar > span { position: absolute; inset: 0 auto 0 0; border-radius: 5px; background: var(--success-color, #2e7d32); }
  .budget-bar.ahead > span { background: var(--warning-color, #f0a500); }
  .budget-bar.over > span { background: var(--rema-sale, #d33); }
  .budget-bar > i { position: absolute; top: -4px; bottom: -4px; width: 2px; background: var(--primary-text-color); }
  .budget-card .banner.small { font-size: 13px; margin: 8px 0; }
  #budget-book { container-type: inline-size; }
  .book { margin-top: 12px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; align-items: end; }
  .book .field { margin: 0; min-width: 0; }
  .book input { display: block; min-width: 0; min-inline-size: 0; max-width: 100%; width: 100%; height: 46px; box-sizing: border-box; font-size: 16px; }
  .book input[type="date"] { appearance: none; -webkit-appearance: none; }
  .book input::-webkit-date-and-time-value { text-align: left; }
  .book > .btn { grid-column: 1 / -1; min-height: 46px; }
  @container (max-width: 340px) { .book { grid-template-columns: minmax(0, 1fr); } }
  @container (min-width: 480px) { .book { grid-template-columns: repeat(2, minmax(0, 1fr)) auto; } .book > .btn { grid-column: auto; } }
  .book-stores { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
  .book-stores .chip { padding: 4px 10px; font-size: 13px; }
  .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0 0 12px; }
  .stat { background: var(--card-background-color, #fff); border-radius: 12px; padding: 10px 12px; display: flex; flex-direction: column; gap: 2px; box-shadow: var(--ha-card-box-shadow, none); border: 1px solid var(--divider-color, rgba(127,127,127,.15)); }
  .stat b { font-size: 20px; }
  .budget-chart { width: 100%; height: auto; display: block; }
  .budget-chart .axis { font-size: 11px; fill: var(--secondary-text-color); }
  .budget-chart .budget-line { stroke: var(--secondary-text-color); stroke-width: 1; stroke-dasharray: 4 4; }
  .budget-chart .spent-line { fill: none; stroke: var(--success-color, #2e7d32); stroke-width: 2.5; }
  .budget-chart .budget-top { stroke: var(--divider-color, rgba(127,127,127,.35)); stroke-width: 1; }
  .budget-chart .forecast-line { stroke: var(--rema-accent); stroke-width: 2.5; stroke-dasharray: 1 5; stroke-linecap: round; }
  .budget-chart .spent-dot { fill: var(--success-color, #2e7d32); }
  .budget-chart .bar.ok { fill: var(--success-color, #2e7d32); }
  .budget-chart .bar.current { fill: var(--success-color, #2e7d32); opacity: .55; }
  .budget-chart .bar.over { fill: var(--rema-sale, #d33); }
  .budget-chart .bar.ghost { fill: var(--divider-color, rgba(127,127,127,.25)); }
  .legend .key { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 4px 0 10px; vertical-align: -1px; }
  .legend .key:first-child { margin-left: 0; }
  .legend .key.spent { background: var(--success-color, #2e7d32); }
  .legend .key.over { background: var(--rema-sale, #d33); }
  .legend .key.budget { background: transparent; border-top: 2px dashed var(--secondary-text-color); height: 0; }
  .legend .key.forecast { background: transparent; border-top: 3px dotted var(--rema-accent); height: 0; }
  .legend .key.ghost { background: var(--divider-color, rgba(127,127,127,.25)); }
  ul.kv, ul.purchases { list-style: none; padding: 0; margin: 0; }
  ul.kv li { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--divider-color, rgba(127,127,127,.15)); }
  ul.purchases li { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--divider-color, rgba(127,127,127,.15)); }
  ul.purchases .what { flex: 1; display: flex; flex-direction: column; }
  button.what.plain { background: none; border: 0; padding: 0; text-align: left; color: inherit; font: inherit; cursor: pointer; }
  .toast-btn { margin-left: 12px; background: none; border: 0; color: inherit; font: inherit; font-weight: 600; text-decoration: underline; cursor: pointer; padding: 4px; }
  .timer-chip { font-variant-numeric: tabular-nums; font-size: 14px; padding: 2px 8px; border-radius: 12px; cursor: pointer; }
  .timer-chip:not(:empty) { background: var(--rema-sale, #d33); color: #fff; margin-right: 6px; }
  @media (max-width: 700px) {
    .recipe-grid { grid-template-columns: 1fr; }
    .day { grid-template-columns: 1fr; gap: 4px; }
    .price { text-align: left; }
    .step-text { font-size: 18px; }
    .line { grid-template-columns: 40px 1fr; } .line .cost { grid-column: 2; text-align: left; flex-direction: row; gap: 8px; }
    .line.has-send { grid-template-columns: 40px 1fr auto; } .line.has-send .to-rema-line { grid-column: 3; grid-row: 1 / span 2; }
    .shop-card { position: relative; } .shop-card .store-badge { position: absolute; top: 14px; right: 14px; } .shop-card h1, .shop-card .shop-head { padding-right: 52px; }
    .prod-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
    .prod { padding: 6px; gap: 4px; font-size: 12px; border-radius: 10px; }
    .prod img, .prod .noimg { height: 64px; }
    .prod-price { font-size: 14px; }
    .prod .badge { font-size: 10px; padding: 1px 5px; }
    .prod .btn { padding: 6px 4px; font-size: 12px; }
    /* Phone: the tabs become a low bar at the very bottom, see-through like the CRM's menu. */
    :host { --rema-tabbar: calc(56px + max(2px, var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px)) - 16px)); }
    .tabs { position: fixed; top: auto; bottom: 0; left: 0; right: 0; z-index: 5; display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0; overflow: visible;
      /* side padding keeps the outer icons clear of the screen's rounded corners */
      padding: 5px 22px max(2px, calc(var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px)) - 16px));
      border-bottom: none; border-top: 1px solid var(--divider-color);
      background: color-mix(in srgb, var(--primary-background-color) 60%, transparent);
      -webkit-backdrop-filter: blur(2px) saturate(1.4); backdrop-filter: blur(2px) saturate(1.4); }
    .tab { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 0 4px; min-width: 0;
      font-size: 10.5px; font-weight: 600; border-bottom: none; }
    .tab span { max-width: 100%; overflow: hidden; text-overflow: ellipsis; }
    .tabs { grid-template-columns: repeat(5, minmax(0, 1fr)); }
    .tabs .tab { order: var(--mobile-order, 20); }
    .tabs .tab:not(.mobile-primary):not(.more) { display: none; }
    .tabs .tab.mobile-primary { display: flex; }
    .tabs .tab.more { display: flex; order: 21; }
    .more-scrim:not([hidden]) { display: block; position: fixed; inset: 0; z-index: 4; }
    .more-sheet:not([hidden]) { display: flex; flex-direction: column; position: fixed; right: 8px; z-index: 6;
      top: auto; bottom: calc(var(--rema-tabbar) + 8px); min-width: 200px; padding: 6px; border-radius: 16px;
      background: var(--rema-solid-card); border: 1px solid var(--divider-color); box-shadow: 0 8px 28px rgba(0, 0, 0, .22); }
    .more-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: none; border-radius: 10px;
      background: none; color: var(--primary-text-color); font-size: 16px; font-weight: 500; text-align: left; cursor: pointer; }
    .more-item.desktop-primary { display: flex; }
    .more-item.mobile-primary { display: none; }
    .more-item svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .more-item.active { color: var(--rema-accent); background: var(--rema-tint); }
    .tab svg { display: block; }
    main { padding-bottom: calc(96px + var(--rema-tabbar)); }
    .savebar { bottom: calc(8px + var(--rema-tabbar)); }
    .sticky { bottom: var(--rema-tabbar); padding-bottom: 12px; }
    .toast { bottom: calc(16px + var(--rema-tabbar)); }
  }
  /* Tabs as in EV Planner on a wide screen: an icon, and the chosen one as a soft pill. Settings is in the profile menu. */
  @media (min-width: 701px) {
    .tab { align-items: center; gap: 6px; border-bottom: 0; border-radius: 12px; margin-bottom: 8px; padding: 8px 12px; }
    .tab.desktop-primary, .tab.more { display: inline-flex; }
    .tab svg { display: inline-block; width: 18px; height: 18px; }
    .tab.active { background: var(--rema-tint); }
    .tab[data-arg="settings"], .more-item[data-arg="settings"] { display: none !important; }
  }
`;

/* ======================================================================================
   Middagsro 3: the street in the header, the front page, the clocks in Økonomi and the
   plates in Sundhed. Drawn here, on top of the panel above; nothing of it needs a build.
   ====================================================================================== */
const V3 = (() => {
  const NBSP = " ";
  const fmt = (v, d = 0) => Number(v || 0).toLocaleString("da-DK", { minimumFractionDigits: d, maximumFractionDigits: d });
  const krd = (v, d = 0) => `${fmt(v, d)}${NBSP}kr.`;
  const DAYS = ["SØN", "MAN", "TIR", "ONS", "TOR", "FRE", "LØR"];
  const DAYS_LONG = ["søndag", "mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag"];
  const MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const MONTHS_LONG = ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december"];
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
  const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const addDays = (iso, n) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() + n); return d; };
  const daysBetween = (a, b) => Math.round((new Date(`${b}T12:00:00`) - new Date(`${a}T12:00:00`)) / 864e5);
  const isoWeek = (d) => { const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); const day = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - day); const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return Math.ceil(((t - y0) / 864e5 + 1) / 7); };
  // A Middagsro week starts on Sunday: its number is the ISO week of the Monday after.
  const weekNo = (start) => isoWeek(addDays(start, 1));
  const sundayOf = (iso) => { const d = new Date(`${iso}T12:00:00`); d.setDate(d.getDate() - d.getDay()); return ymd(d); };
  const span = (start) => { const a = addDays(start, 0), b = addDays(start, 6); return a.getMonth() === b.getMonth() ? `${a.getDate()}.–${b.getDate()}. ${MONTHS_LONG[b.getMonth()]}` : `${a.getDate()}. ${MONTHS[a.getMonth()]}–${b.getDate()}. ${MONTHS[b.getMonth()]}`; };
  const greet = (h) => (h < 5 ? "God nat" : h < 10 ? "God morgen" : h < 12 ? "God formiddag" : h < 18 ? "God eftermiddag" : "God aften");

  /* Geometry: angles in degrees, clockwise from the top, as on a clock. */
  const P = (cx, cy, r, a) => { const t = (a * Math.PI) / 180; return [cx + r * Math.sin(t), cy - r * Math.cos(t)]; };
  const pt = (p) => `${p[0].toFixed(2)} ${p[1].toFixed(2)}`;
  const sector = (cx, cy, r0, r1, a0, a1) => {
    if (a1 - a0 >= 359.99) a1 = a0 + 359.99;
    const L = a1 - a0 > 180 ? 1 : 0;
    return `M${pt(P(cx, cy, r1, a0))}A${r1} ${r1} 0 ${L} 1 ${pt(P(cx, cy, r1, a1))}L${pt(P(cx, cy, r0, a1))}A${r0} ${r0} 0 ${L} 0 ${pt(P(cx, cy, r0, a0))}Z`;
  };
  const arc = (cx, cy, r, a0, a1) => {
    if (a1 - a0 >= 359.99) a1 = a0 + 359.99;
    const L = a1 - a0 > 180 ? 1 : 0;
    return `M${pt(P(cx, cy, r, a0))}A${r} ${r} 0 ${L} 1 ${pt(P(cx, cy, r, a1))}`;
  };
  const countUp = (el, to, dur = 900, render = (v) => krd(v)) => {
    if (!el) return;
    const from = Number(el.dataset.v || 0);
    el.dataset.v = to;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = render(to); return; }
    const t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = render(from + (to - from) * e); if (k < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  };

  /* Varegrupperne: eight, in a fixed order, each with its colour and its little drawing. */
  const GROUPS = [
    { k: "mejeri", name: "Mejeri & æg" }, { k: "kolonial", name: "Kolonial & færdigt" }, { k: "drikke", name: "Drikke & kaffe" },
    { k: "brod", name: "Brød & morgenmad" }, { k: "snacks", name: "Snacks & slik" }, { k: "frugt", name: "Frugt & grønt" },
    { k: "hjem", name: "Hjem, baby & andet" }, { k: "kod", name: "Kød & fisk" },
  ];
  const GNAME = Object.fromEntries(GROUPS.map((g) => [g.k, g.name]));
  GNAME.none = "Andre køb";
  const ORDER = [...GROUPS.map((g) => g.k), "none"];
  const c = (g) => `var(--g-${g})`;
  const tint = (g, p) => `color-mix(in srgb, var(--g-${g}) ${p}%, var(--card-background-color))`;
  const shade = (g, p) => `color-mix(in srgb, var(--g-${g}) ${100 - p}%, #000)`;
  const ART = {
    mejeri: (g = "mejeri") => `<ellipse cx="32" cy="57" rx="20" ry="3" fill="${shade(g, 40)}" opacity=".12"/><path d="M18 22 L24 12 H38 L44 22 V54 H18 Z" fill="${tint(g, 22)}"/><path d="M24 12 H38 L44 22 H18 Z" fill="${tint(g, 55)}"/><path d="M18 22 H44 V54 H18 Z" fill="none" stroke="${c(g)}" stroke-width="2.4" stroke-linejoin="round"/><path d="M24 12 L18 22 M38 12 L44 22 M24 12 H38" stroke="${c(g)}" stroke-width="2.4" stroke-linecap="round"/><rect x="22" y="30" width="18" height="12" rx="3" fill="${c(g)}"/><path d="M26 38 q5 -6 10 0" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/><ellipse cx="49" cy="47" rx="7" ry="9" fill="#FFF7EA" stroke="${shade(g, 30)}" stroke-opacity=".35" stroke-width="1.4"/><ellipse cx="47" cy="44" rx="2" ry="3" fill="#fff"/>`,
    kolonial: (g = "kolonial") => `<ellipse cx="32" cy="57" rx="20" ry="3" fill="#000" opacity=".1"/><rect x="17" y="18" width="22" height="36" rx="6" fill="${tint(g, 18)}" stroke="${c(g)}" stroke-width="2.4"/><rect x="15" y="12" width="26" height="8" rx="3" fill="${c(g)}"/><path d="M21 30 h14 M21 36 h14 M21 42 h14 M21 48 h14" stroke="${tint(g, 70)}" stroke-width="3" stroke-linecap="round"/><path d="M22 28 l3 22 M28 28 l1 22 M33 28 l-2 22" stroke="#F2C66D" stroke-width="2.4" stroke-linecap="round"/><rect x="40" y="34" width="14" height="20" rx="3" fill="${c(g)}"/><rect x="40" y="40" width="14" height="8" fill="${tint(g, 40)}"/><ellipse cx="47" cy="34" rx="7" ry="2.4" fill="${shade(g, 25)}"/>`,
    drikke: (g = "drikke") => `<ellipse cx="32" cy="57" rx="20" ry="3" fill="#000" opacity=".1"/><path d="M22 8 h8 v8 q6 4 6 12 v24 q0 3 -3 3 h-14 q-3 0 -3 -3 v-24 q0 -8 6 -12 Z" fill="${tint(g, 22)}" stroke="${c(g)}" stroke-width="2.4" stroke-linejoin="round"/><rect x="22" y="5" width="8" height="5" rx="1.5" fill="${c(g)}"/><rect x="16" y="32" width="20" height="12" fill="${c(g)}"/><circle cx="26" cy="38" r="3" fill="#fff" opacity=".85"/><path d="M40 30 h14 l-2 22 q0 3 -3 3 h-4 q-3 0 -3 -3 Z" fill="${tint(g, 45)}" stroke="${c(g)}" stroke-width="2" stroke-linejoin="round"/><path d="M41 38 h12" stroke="${c(g)}" stroke-width="2"/><circle cx="46" cy="44" r="1.6" fill="#fff"/><circle cx="49" cy="48" r="1.2" fill="#fff"/>`,
    brod: (g = "brod") => `<ellipse cx="32" cy="56" rx="24" ry="3" fill="#000" opacity=".1"/><path d="M8 40 q0 -18 24 -18 q24 0 24 18 v8 q0 6 -6 6 h-36 q-6 0 -6 -6 Z" fill="${tint(g, 55)}" stroke="${shade(g, 22)}" stroke-width="2.2"/><path d="M8 40 q0 -18 24 -18 q24 0 24 18" fill="${c(g)}" opacity=".85"/><path d="M18 34 l6 -6 M28 32 l6 -7 M38 33 l6 -6" stroke="${tint(g, 15)}" stroke-width="3" stroke-linecap="round"/><circle cx="16" cy="46" r="1" fill="${shade(g, 30)}"/><circle cx="24" cy="49" r="1" fill="${shade(g, 30)}"/><circle cx="44" cy="47" r="1" fill="${shade(g, 30)}"/>`,
    snacks: (g = "snacks") => `<ellipse cx="32" cy="57" rx="20" ry="3" fill="#000" opacity=".1"/><path d="M14 30 l-8 -6 v16 Z M50 30 l8 -6 v16 Z" fill="${tint(g, 55)}" stroke="${c(g)}" stroke-width="2" stroke-linejoin="round"/><rect x="14" y="22" width="36" height="16" rx="8" fill="${c(g)}"/><path d="M22 22 l-4 16 M30 22 l-4 16 M38 22 l-4 16 M46 22 l-4 16" stroke="${tint(g, 35)}" stroke-width="2.4"/><path d="M44 42 v14" stroke="${shade(g, 40)}" stroke-width="2.4" stroke-linecap="round"/><circle cx="44" cy="42" r="8" fill="${tint(g, 30)}" stroke="${c(g)}" stroke-width="2"/><path d="M44 42 m-4 0 a4 4 0 1 1 4 4" stroke="${c(g)}" stroke-width="2" fill="none" stroke-linecap="round"/><circle cx="20" cy="49" r="5" fill="#F3B34C"/><circle cx="20" cy="49" r="2" fill="#fff" opacity=".6"/>`,
    frugt: (g = "frugt") => `<ellipse cx="32" cy="57" rx="22" ry="3" fill="#000" opacity=".1"/><path d="M26 22 q-14 -4 -16 12 q-1 14 10 20 q4 2 6 0 q2 2 6 0 q11 -6 10 -20 q-2 -16 -16 -12 Z" fill="#E5483C"/><path d="M16 34 q0 -8 6 -9" stroke="#fff" stroke-width="2.6" stroke-linecap="round" fill="none" opacity=".55"/><path d="M26 22 q0 -8 4 -12" stroke="#6B4A2A" stroke-width="2.4" stroke-linecap="round" fill="none"/><path d="M30 14 q8 -6 14 0 q-8 5 -14 0 Z" fill="${c(g)}"/><path d="M44 30 l10 22 q1 3 -2 3 l-3 0 Z" fill="#F08A24"/><path d="M47 36 h3 M48 41 h3 M50 46 h2" stroke="#C0631A" stroke-width="1.6" stroke-linecap="round"/><path d="M44 30 q-4 -8 -2 -12 M45 30 q2 -9 6 -10 M45 30 q6 -4 10 -2" stroke="${c(g)}" stroke-width="2.6" stroke-linecap="round" fill="none"/>`,
    hjem: (g = "hjem") => `<ellipse cx="32" cy="57" rx="22" ry="3" fill="#000" opacity=".1"/><path d="M10 30 L32 12 L54 30 V54 H10 Z" fill="${tint(g, 18)}" stroke="${c(g)}" stroke-width="2.4" stroke-linejoin="round"/><path d="M6 32 L32 10 L58 32" stroke="${c(g)}" stroke-width="3.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M32 46 c-8 -5 -10 -9 -7 -12 c2 -2 5 -1 7 2 c2 -3 5 -4 7 -2 c3 3 1 7 -7 12 Z" fill="${c(g)}"/><circle cx="48" cy="50" r="7" fill="#fff" stroke="${tint(g, 60)}" stroke-width="2"/><circle cx="48" cy="50" r="2.4" fill="${tint(g, 60)}"/>`,
    kod: (g = "kod") => `<ellipse cx="32" cy="57" rx="22" ry="3" fill="#000" opacity=".1"/><path d="M10 34 q2 -14 18 -14 q16 0 20 10 q2 8 -6 12 q-6 4 -18 4 q-14 0 -14 -12 Z" fill="${c(g)}"/><path d="M16 34 q2 -8 12 -8 q10 0 12 6" stroke="${tint(g, 55)}" stroke-width="3" fill="none" stroke-linecap="round"/><path d="M42 42 q-4 4 -14 4" stroke="#fff" stroke-width="3.2" fill="none" stroke-linecap="round" opacity=".9"/><path d="M34 48 q8 -8 18 -2 l6 -5 v12 l-6 -5 q-10 6 -18 0 Z" fill="#7FB3D9" stroke="#4C86B5" stroke-width="1.6" stroke-linejoin="round"/><circle cx="40" cy="48" r="1.4" fill="#173A57"/>`,
    none: () => `<circle cx="32" cy="32" r="18" fill="var(--g-none)" opacity=".7"/>`,
  };
  const art = (g, cls = "art") => `<svg class="${cls}" viewBox="0 0 64 64" aria-hidden="true">${(ART[g] || ART.none)(g)}</svg>`;
  const dot = (g) => (g === "none" ? `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="var(--g-none)"/></svg>` : art(g, ""));

  /* What a line is, by its name (as the server does for receipts). */
  const GROUP_WORDS = [
    ["hjem", "bleer|pants|bleposer|vådserviet|nan pro|svømmeble|toiletpapir|køkkenrull|skumvask|opvask|vaskemiddel|flydende vask|afspænding|pletfjern|håndsæbe|shampoo|hairspray|batteri|affaldspose|lynlås|genluk|tandpasta|ansigtscreme|håndcreme|sollotion|lommeletter|servietter|sprinklervæske|vejsalt|rodalon|hygiejnebind|gavepapir|sløjfe|amaryllis|playset|politibil|pocket money"],
    ["kolonial", "pizza|lovemade|dinner kit|pommes|fritter|pomm's|dej|suppe|melboller|lasagne|nuggets|ret nemt|karbonader|panerede|tærte|quiche"],
    ["drikke", "pepsi|faxe|fanta|cola|juice|smoothie|iskaffe|blanc|freixenet|chateau|château|grand cru|prosecco|asti|barbera|reserva|mocktail|shots|kaffe|crema|espresso|qualita|x-mas|chardonnay|rosé|ipa"],
    ["snacks", "slik|snack|chips|popcorn|haribo| mix|bars |chokolade|knas|marshmallow|toffifee|kiks|kager|gummies|lakrids|ferrero|kinder|julekalender|isvaffel|sandwich is|ostepops|spiraler|bugles|nødde|rosin|dipmix|grinebidder|halloween|snitter|kanelstang|trøfler|kammerjunker|dippers|fruit stars|sour cream"],
    ["kod", "laks|kylling|okse|kalv|gris|hamburgerryg|postej|spegepølse|pølse|bacon|skinke|frikadelle|fisk|makrel|tun |tun i|tunsalat|rejer|ørred|mørbrad|medister|flæskesteg|ribbens|culotte|ribeye|kebab|döner|salami|rullepølse|burgerboost|pulled pork|andebryst|steak|kalkun|hapser|sandwichsk|koteletter|carpaccio"],
    ["brod", "rugbrød|brød|boller|mysli|havregryn|guldkorn|coco pops|baguette|skagenslapper|cafesandwich|pølsehorn|brioche|burgerb|rugfras|klemmer|tortilla|rug go|kohberg|pandekager|æbleskiver|solsikke |focaccia|marmelade|gær"],
    ["mejeri", "mælk|yoghurt|fraiche|ost|mozzarella|smørbar|lurpak|kærgården|æg|fløde|cremefine|koldskål|actimel|puck|havarti|parmigiano|grana|cheasy|vaniljesauce|45\\+|30\\+|burrata|gouda|kakao|skiver ml"],
    ["frugt", "agurk|banan|avocado|blåbær|jordbær|druer|salat|broccoli|gulerød|tomat|citron|lime|appelsin|clementin|kiwi|æble|vandmelon|kartof|kart\\.|majs|ærter|sugar snaps|løg|porre|squash|champignon|blomkål|hokkaido|ingefær|purløg|land/kl|danmark kl|spanien kl|holland kl"],
    ["kolonial", "pasta|nudler|fusilli|fettuccine|ris |ris$|pesto|salsa|remoulade|dressing|mayo|sauce|croutoner|bulgur|olie|mel |mel$|rasp|peanut|tex mex|hummus|vaniljestæng"],
  ].map(([g, w]) => [g, new RegExp(w)]);
  const groupOf = (name) => { const n = ` ${String(name || "").toLowerCase()} `; for (const [g, re] of GROUP_WORDS) if (re.test(n)) return g; return "hjem"; };
  // "LETMÆLK 1,5% ARLA, ØKOLOGISK" -> "Letmælk 1,5% arla, økologisk"
  const clean = (n) => { let s = String(n || "").replace(/\s*LAND\/KL\.: SE VAREN/i, "").replace(/\s*REMA 1000/i, "").replace(/\s+,/g, ",").trim().toLowerCase(); return cap(s); };
  // A product picture, with the group's drawing if it is missing or will not load.
  const pic = (url, g) => (url ? `<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" data-fb="${esc(g || "hjem")}">` : art(g || "hjem", ""));

  /* Retterne, tegnet: a plate from above with what the dish's name says is on it. */
  const dishKind = (n) => {
    n = String(n || "").toLowerCase();
    if (!n) return "tom";
    if (/spiser ude|takeaway|take-away|ude$/.test(n)) return "ude";
    if (/rugbrød/.test(n)) return "rugbrod";
    if (/rester|fryser/.test(n) && !/laks|chili|frikadel|pølse|pita|risotto/.test(n)) return "rester";
    if (/laks|fisk|torsk|rødspætte|sej|tun/.test(n)) return "laks";
    if (/chili|gryde|bolognese|kødsovs/.test(n)) return "chili";
    if (/frikadel|krebinet|karbonade|bøf|burger/.test(n)) return "frikadeller";
    if (/cæsar|salat/.test(n)) return "salat";
    if (/pita|tortilla|baguette|kebab|taco|wrap|burrito/.test(n)) return "pita";
    if (/risotto|ris |stegte ris|ris$|karry/.test(n)) return "ris";
    if (/pølse/.test(n)) return "polse";
    if (/lasagne|spaghetti|pasta|nudel|pizza/.test(n)) return "pasta";
    if (/suppe/.test(n)) return "suppe";
    if (/kylling|mørbrad|oksekød|wok|svin|flæsk|kotelet/.test(n)) return "kylling";
    if (/kage|omelet|æggekage|tærte|pandekage/.test(n)) return "aeg";
    return "andet";
  };
  const DISH = {
    laks: `<path d="M30 46 q14 -16 40 -6 q6 10 0 18 q-26 10 -40 -4Z" fill="#F08A5D"/><path d="M40 42 l4 14 M50 40 l4 16 M60 40 l3 16" stroke="#FBD1B8" stroke-width="2.4" stroke-linecap="round"/><g fill="#2E9E5B"><circle cx="34" cy="68" r="6"/><circle cx="42" cy="72" r="6"/><circle cx="38" cy="64" r="5"/></g><path d="M56 66 q10 -4 16 4 q-8 8 -16 4Z" fill="#7DBE5A"/><path d="M58 70 q6 -2 10 2" stroke="#4E8C35" stroke-width="1.4" fill="none"/><circle cx="68" cy="34" r="6" fill="#F7E36B" stroke="#D9C24A" stroke-width="1.4"/>`,
    chili: `<circle cx="50" cy="50" r="22" fill="#B5371F"/><g fill="#5A1F12"><ellipse cx="42" cy="44" rx="4" ry="2.6"/><ellipse cx="56" cy="52" rx="4" ry="2.6"/><ellipse cx="47" cy="58" rx="4" ry="2.6"/><ellipse cx="58" cy="41" rx="4" ry="2.6"/></g><g fill="#F3B34C"><circle cx="50" cy="46" r="2"/><circle cx="40" cy="54" r="2"/><circle cx="60" cy="58" r="2"/></g><path d="M38 40 q10 -6 22 2" stroke="#fff" stroke-width="2.4" fill="none" opacity=".75" stroke-linecap="round"/>`,
    frikadeller: `<g fill="#8A4B2A"><ellipse cx="38" cy="44" rx="10" ry="8"/><ellipse cx="56" cy="40" rx="10" ry="8"/><ellipse cx="48" cy="56" rx="10" ry="8"/></g><g fill="#B26A3E" opacity=".6"><ellipse cx="36" cy="41" rx="4" ry="2"/><ellipse cx="54" cy="37" rx="4" ry="2"/><ellipse cx="46" cy="53" rx="4" ry="2"/></g><g fill="#F2C66D" stroke="#D9A441" stroke-width="1.4"><path d="M62 54 l10 2 l-4 9 l-9 -3Z"/><path d="M66 46 l9 -1 l1 9 l-9 1Z"/></g><g fill="#2E9E5B"><circle cx="32" cy="64" r="4"/><circle cx="38" cy="68" r="4"/></g>`,
    salat: `<g fill="#6DBA4F"><path d="M30 50 q8 -22 20 -20 q-2 14 -20 20Z"/><path d="M50 30 q20 0 22 18 q-14 -2 -22 -18Z"/><path d="M70 52 q-2 20 -20 22 q2 -14 20 -22Z"/><path d="M48 72 q-20 0 -20 -16 q14 2 20 16Z"/></g><g fill="#F3DFA6" stroke="#D9B865" stroke-width="1.2"><rect x="40" y="44" width="7" height="7" rx="1.5"/><rect x="54" y="52" width="7" height="7" rx="1.5"/><rect x="46" y="58" width="6" height="6" rx="1.5"/></g><g fill="#E7B172"><path d="M52 40 q8 -2 10 4 q-6 4 -10 -4Z"/></g>`,
    pita: `<path d="M26 58 q4 -26 30 -26 q24 2 22 20 q-4 18 -26 20 q-24 2 -26 -14Z" fill="#E9C389"/><path d="M34 54 q20 -10 40 -4" stroke="#C99A5C" stroke-width="2" fill="none"/><g fill="#6DBA4F"><circle cx="44" cy="44" r="5"/><circle cx="56" cy="42" r="4"/></g><g fill="#E5483C"><circle cx="50" cy="48" r="3.4"/><circle cx="62" cy="46" r="3"/></g><path d="M38 50 q12 -6 26 -2" stroke="#F4E9D8" stroke-width="3" fill="none" stroke-linecap="round"/>`,
    ris: `<circle cx="50" cy="50" r="22" fill="#F3EEDD"/><g fill="#E4DCC2">${Array.from({ length: 14 }, (_, i) => `<ellipse cx="${36 + ((i * 7) % 28)}" cy="${38 + ((i * 11) % 26)}" rx="2.6" ry="1.2" transform="rotate(${i * 25} ${36 + ((i * 7) % 28)} ${38 + ((i * 11) % 26)})"/>`).join("")}</g><g fill="#2E9E5B"><circle cx="58" cy="44" r="4"/><circle cx="44" cy="58" r="3.4"/></g><path d="M64 64 q8 -10 14 -2 q-6 8 -14 2Z" fill="#E7B172"/>`,
    polse: `<g stroke-linecap="round"><path d="M30 42 q20 -8 40 0" stroke="#A7472A" stroke-width="9"/><path d="M30 56 q20 -8 40 0" stroke="#B85433" stroke-width="9"/></g><path d="M34 41 q16 -6 32 0 M34 55 q16 -6 32 0" stroke="#E08D6A" stroke-width="2" fill="none"/><g fill="#F2C66D"><circle cx="40" cy="68" r="4"/><circle cx="50" cy="70" r="4"/><circle cx="60" cy="68" r="4"/></g>`,
    pasta: `<g fill="none" stroke="#F2D27A" stroke-width="3" stroke-linecap="round"><path d="M32 50 q8 -14 18 0 q10 14 18 0"/><path d="M30 58 q10 -12 20 0 q10 12 20 0"/><path d="M34 42 q8 -10 16 0 q8 10 16 0"/></g><circle cx="50" cy="50" r="10" fill="#C2412B" opacity=".9"/><g fill="#7DBE5A"><circle cx="46" cy="47" r="2"/><circle cx="54" cy="52" r="2"/></g>`,
    suppe: `<circle cx="50" cy="50" r="24" fill="#E8B04B"/><circle cx="50" cy="50" r="24" fill="none" stroke="#fff" stroke-width="3" opacity=".6"/><g fill="#7DBE5A"><circle cx="42" cy="46" r="3"/><circle cx="58" cy="54" r="3"/></g><g fill="#B5371F"><rect x="52" y="40" width="6" height="5" rx="1"/><rect x="40" y="56" width="6" height="5" rx="1"/></g>`,
    kylling: `<path d="M30 52 q2 -16 22 -16 q18 2 18 14 q0 14 -20 16 q-20 0 -20 -14Z" fill="#E7B172"/><path d="M36 48 q12 -6 28 0 M38 56 q12 -5 24 0" stroke="#C98C4E" stroke-width="2.4" fill="none"/><g fill="#2E9E5B"><circle cx="66" cy="66" r="5"/><circle cx="72" cy="60" r="4"/></g><g fill="#F2C66D"><circle cx="34" cy="68" r="4"/><circle cx="42" cy="72" r="4"/></g>`,
    aeg: `<circle cx="50" cy="50" r="22" fill="#F7D774"/><g fill="#F2C66D" stroke="#D9A441" stroke-width="1"><path d="M38 44 l8 -2 l1 7 l-8 1Z"/><path d="M54 56 l8 -1 l0 7 l-8 0Z"/></g><g fill="#2E9E5B"><circle cx="58" cy="44" r="3"/><circle cx="44" cy="58" r="3"/></g><g fill="#B85433"><rect x="48" y="46" width="6" height="4" rx="1"/></g>`,
    rester: `<rect x="28" y="34" width="44" height="34" rx="7" fill="#DCE7F2" stroke="#9FB3C8" stroke-width="2"/><rect x="26" y="30" width="48" height="9" rx="4" fill="#7FA6CF"/><path d="M36 52 q14 -8 28 0" stroke="#B5371F" stroke-width="7" stroke-linecap="round" opacity=".7"/><circle cx="66" cy="62" r="7" fill="#fff" stroke="#9FB3C8" stroke-width="1.5"/><path d="M66 58 v4 l3 2" stroke="#7FA6CF" stroke-width="1.6" fill="none" stroke-linecap="round"/>`,
    rugbrod: `<rect x="30" y="34" width="40" height="30" rx="5" fill="#6B4A36"/><g fill="#8A6A52"><circle cx="38" cy="42" r="1.6"/><circle cx="50" cy="40" r="1.6"/><circle cx="62" cy="44" r="1.6"/><circle cx="44" cy="54" r="1.6"/><circle cx="58" cy="56" r="1.6"/></g><path d="M32 36 q18 -8 36 0" stroke="#E9C389" stroke-width="4" fill="none" stroke-linecap="round"/><g fill="#6DBA4F"><circle cx="40" cy="36" r="4"/></g><g fill="#F08A5D"><ellipse cx="56" cy="36" rx="6" ry="3"/></g>`,
    ude: `<path d="M38 30 v16 q0 6 6 6 v20" stroke="#8A93A6" stroke-width="3.4" fill="none" stroke-linecap="round"/><path d="M34 30 v10 M42 30 v10" stroke="#8A93A6" stroke-width="3" stroke-linecap="round"/><path d="M62 30 q-8 8 -2 22 v20" stroke="#8A93A6" stroke-width="3.4" fill="none" stroke-linecap="round"/><circle cx="50" cy="50" r="8" fill="none" stroke="#C5CBD6" stroke-width="2" stroke-dasharray="3 3"/>`,
    tom: `<circle cx="50" cy="50" r="10" fill="none" stroke="#C5CBD6" stroke-width="2" stroke-dasharray="3 3"/>`,
    andet: `<g fill="#2E9E5B"><circle cx="40" cy="44" r="7"/><circle cx="46" cy="38" r="6"/></g><path d="M50 52 q12 -10 22 0 q-10 12 -22 0Z" fill="#E7B172"/><g fill="#F2C66D"><circle cx="40" cy="62" r="5"/><circle cx="50" cy="66" r="5"/></g>`,
  };
  const dishArt = (name, cls = "dish-art") => {
    const k = dishKind(name);
    const plate = k === "ude" || k === "tom"
      ? `<circle cx="50" cy="50" r="40" fill="var(--rema-subtle)" stroke="var(--divider-color)" stroke-width="2" stroke-dasharray="4 5"/>`
      : k === "rester"
        ? `<circle cx="50" cy="50" r="40" fill="var(--rema-subtle)"/>`
        : `<circle cx="50" cy="52" r="42" fill="#000" opacity=".08"/><circle cx="50" cy="50" r="42" fill="#FFFFFF"/><circle cx="50" cy="50" r="34" fill="#F6F4EF" stroke="#E9E5DC" stroke-width="1.5"/>`;
    return `<svg class="${cls}" viewBox="0 0 100 100" aria-hidden="true">${plate}${DISH[k]}</svg>`;
  };

  /* The street with your shop and your kitchen, as it looks now. The sky follows the clock. */
  const LOGO = `<path d="M0 0h512v512H0z" fill="none"/><rect width="512" height="512" rx="116" fill="url(#lg-cg2)"/><path d="M256 92C265 166 288 190 362 200C288 210 265 234 256 308C247 234 224 210 150 200C224 190 247 166 256 92Z" fill="#fff"/><path d="M352 104C355 122 361 128 379 131C361 134 355 140 352 158C349 140 343 134 325 131C343 128 349 122 352 104Z" fill="#fff" opacity=".75"/><path d="M144 326H368C368 384 324 420 256 420S144 384 144 326Z" fill="#1B1530"/><g fill="#1B1530"><path d="M80 236v52a20 20 0 0 0 14 19v113a10 10 0 0 0 20 0V307a20 20 0 0 0 14-19v-52a5 5 0 0 0-10 0v44a4 4 0 0 1-8 0v-44a5 5 0 0 0-10 0v44a4 4 0 0 1-8 0v-44a5 5 0 0 0-10 0z"/><path d="M422 236c-26 14-34 54-32 96h22v88a10 10 0 0 0 20 0V244c0-7-5-11-10-8z"/></g>`;
  const skyAt = (h) => {
    if (h < 5 || h >= 21.5) return { top: "#0B1330", low: "#26336A", stars: 1, lit: 1, name: "nat", ground: "#1A2238", haze: "#3A4680" };
    if (h < 8) return { top: "#3A3F7A", low: "#F4A77A", stars: 0.3, lit: 1, name: "morgen", ground: "#3B3F5C", haze: "#C98C8C" };
    if (h < 11) return { top: "#6FB1E8", low: "#FDE3C0", stars: 0, lit: 0, name: "formiddag", ground: "#5E6B7E", haze: "#E8D9C6" };
    if (h < 16) return { top: "#4C9BE0", low: "#BFE2FB", stars: 0, lit: 0, name: "dag", ground: "#5A6B80", haze: "#CFE3F2" };
    if (h < 18) return { top: "#5F86C9", low: "#F7C08A", stars: 0, lit: 0.6, name: "eftermiddag", ground: "#545C74", haze: "#E9BFA0" };
    return { top: "#2E2D6B", low: "#D9718A", stars: 0.6, lit: 1, name: "aften", ground: "#2C2F4F", haze: "#8E5E8C" };
  };
  const shopFront = (k, kind, h) => {
    const open = h >= 7 && h < 22;
    return `<rect x="0" y="0" width="340" height="190" rx="8" fill="color-mix(in srgb, #EEF0F4 86%, ${k.ground})"/>
    <rect x="0" y="0" width="340" height="28" rx="8" fill="color-mix(in srgb, var(--rema-accent) 80%, #000)"/>
    <text x="170" y="19" text-anchor="middle" style="font:800 15px var(--v3-display);fill:#fff;letter-spacing:.2em">DAGLIGVARER</text>
    <path d="M-10 28 h360 l-10 30 h-340Z" fill="var(--rema-accent)"/>
    ${Array.from({ length: 12 }, (_, i) => `<path d="M${4 + i * 28} 28 l-3 30 h14 l3 -30Z" fill="#fff" opacity=".85"/>`).join("")}
    <rect x="22" y="78" width="104" height="92" rx="5" fill="#1F2B44"/><rect x="22" y="78" width="104" height="92" rx="5" fill="url(#win-${kind})" style="opacity:${(open ? Math.max(0.35, k.lit) : 0.1).toFixed(2)}"/>
    <rect x="214" y="78" width="104" height="92" rx="5" fill="#1F2B44"/><rect x="214" y="78" width="104" height="92" rx="5" fill="url(#win-${kind})" style="opacity:${(open ? Math.max(0.35, k.lit) : 0.1).toFixed(2)}"/>
    <g opacity=".75">${[0, 1, 2].map((r) => `<rect x="30" y="${96 + r * 24}" width="88" height="4" fill="#7A5A3A"/><rect x="222" y="${96 + r * 24}" width="88" height="4" fill="#7A5A3A"/>${[0, 1, 2, 3].map((q) => `<rect x="${34 + q * 21}" y="${84 + r * 24}" width="12" height="12" rx="2" fill="${["#E5483C", "#2E9E5B", "#F3B34C", "#2a78d6"][(r + q) % 4]}"/><rect x="${226 + q * 21}" y="${84 + r * 24}" width="12" height="12" rx="2" fill="${["#F3B34C", "#2a78d6", "#E5483C", "#2E9E5B"][(r + q) % 4]}"/>`).join("")}`).join("")}</g>
    <rect x="144" y="74" width="52" height="116" rx="4" fill="color-mix(in srgb, var(--rema-accent) 30%, #222)"/>
    <rect x="148" y="78" width="44" height="64" rx="3" fill="#BFE3FF" opacity=".5"/>
    <rect x="132" y="-34" width="76" height="26" rx="13" fill="${open ? "#2DD4A7" : "#E34948"}"/><text x="170" y="-16" text-anchor="middle" style="font:800 13px var(--ha-font-family-body, sans-serif);fill:#fff;letter-spacing:.12em">${open ? "ÅBENT" : "LUKKET"}</text>`;
  };
  const BAG = (kind) => `
      <path d="M36 92 l18 -54" stroke="#C88F4A" stroke-width="16" stroke-linecap="round"/><path d="M40 82 l5 -6 M44 70 l5 -6 M48 58 l5 -6" stroke="#9C6A30" stroke-width="2.4" stroke-linecap="round"/>
      <path d="M80 96 q-4 -30 10 -64" stroke="#E9F2E0" stroke-width="10" stroke-linecap="round" fill="none"/><path d="M90 32 q-10 -16 -2 -26 M90 32 q6 -18 18 -22 M90 32 q-14 -6 -22 0" stroke="#2E9E5B" stroke-width="5" stroke-linecap="round" fill="none"/>
      <rect x="100" y="56" width="26" height="44" rx="3" fill="#fff" stroke="#2a78d6" stroke-width="2.4"/><path d="M100 56 l5 -10 h16 l5 10" fill="#fff" stroke="#2a78d6" stroke-width="2.4" stroke-linejoin="round"/><rect x="104" y="70" width="18" height="12" rx="2" fill="#2a78d6"/>
      <path d="M58 78 q-6 -18 4 -30 q4 10 12 14 q-6 4 -16 16Z M62 80 q2 -20 16 -26 q0 10 6 16 q-8 2 -22 10Z" fill="#F5C93B" stroke="#C99A14" stroke-width="1.4"/>
      <path d="M10 96 h140 l-12 104 q-1 6 -7 6 h-102 q-6 0 -7 -6Z" fill="url(#bag-${kind})"/>
      <path d="M10 96 h140" stroke="#B8935F" stroke-width="3"/><path d="M48 96 q0 -24 32 -24 q32 0 32 24" fill="none" stroke="#B8935F" stroke-width="5" stroke-linecap="round"/>
      <g class="baglogo" transform="translate(50 110) scale(.117)">${LOGO}</g>`;
  const scene = (kind = "hero", h = new Date().getHours() + new Date().getMinutes() / 60) => {
    const k = skyAt(h);
    const mob = kind === "mobile", cm = kind === "compactm";
    const W = mob || cm ? 440 : 1200, H = kind === "hero" ? 460 : mob ? 760 : 170;
    const base = kind === "hero" ? 400 : mob ? 470 : 150;
    const day = h >= 6 && h < 19.5;
    const t = day ? (h - 6) / 13.5 : ((h + 24 - 19.5) % 24) / 10.5;
    const sx = (mob || cm ? 30 : 80) + t * (W - (mob || cm ? 60 : 160)), sy = base - (cm ? 40 : 60) - Math.sin(t * Math.PI) * (kind === "hero" ? 300 : mob ? 330 : cm ? 70 : 95);
    const lit = (o) => `opacity:${(k.lit * o).toFixed(2)}`;
    const big = kind !== "compact";
    const stars = Array.from({ length: 34 }, (_, i) => { const x = (i * 263) % W, y = 14 + ((i * 97) % (base - 140 > 40 ? base - 140 : 60)); return `<circle class="tw" style="animation-delay:${(i % 7) * 0.6}s" cx="${x}" cy="${y}" r="${(i % 3) * 0.5 + 0.8}" fill="#fff"/>`; }).join("");
    const sky = `<defs>
      <linearGradient id="sk-${kind}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${k.top}"/><stop offset="1" stop-color="${k.low}"/></linearGradient>
      <radialGradient id="glow-${kind}"><stop offset="0" stop-color="${day ? "#FFE7A3" : "#DDE6FF"}" stop-opacity=".9"/><stop offset="1" stop-color="${day ? "#FFE7A3" : "#DDE6FF"}" stop-opacity="0"/></radialGradient>
      <linearGradient id="win-${kind}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE3A1"/><stop offset="1" stop-color="#FFB35C"/></linearGradient>
      <linearGradient id="bag-${kind}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#E9D3B0"/><stop offset="1" stop-color="#CFAE80"/></linearGradient>
      <linearGradient id="lg-cg2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6E4AFF"/><stop offset="1" stop-color="#FF7A59"/></linearGradient>
    </defs>
    <rect width="${W}" height="${H}" fill="url(#sk-${kind})"/>
    <g style="opacity:${k.stars}">${stars}</g>
    <g class="sunpulse"><circle cx="${sx.toFixed(0)}" cy="${sy.toFixed(0)}" r="${big ? 90 : 46}" fill="url(#glow-${kind})"/></g>
    ${day ? `<circle cx="${sx.toFixed(0)}" cy="${sy.toFixed(0)}" r="${big ? 26 : 15}" fill="#FFD25E"/>`
      : `<circle cx="${sx.toFixed(0)}" cy="${sy.toFixed(0)}" r="${big ? 22 : 13}" fill="#F3F1E6"/><circle cx="${(sx + (big ? 9 : 5)).toFixed(0)}" cy="${(sy - (big ? 6 : 4)).toFixed(0)}" r="${big ? 19 : 11}" fill="${k.top}"/>`}
    ${day ? `<g class="cloud"><path d="M180 ${base - 250} a18 18 0 0 1 34 -8 a14 14 0 0 1 26 9 a10 10 0 0 1 -3 20 h-52 a12 12 0 0 1 -5 -21Z" fill="#fff" opacity=".8"/></g><g class="cloud c2"><path d="M820 ${base - 300} a14 14 0 0 1 26 -6 a11 11 0 0 1 20 7 a9 9 0 0 1 -3 17 h-40 a9 9 0 0 1 -3 -18Z" fill="#fff" opacity=".65"/></g>` : ""}`;
    const far = `<path d="M0 ${base - 70} L60 ${base - 92} L110 ${base - 80} L170 ${base - 110} L230 ${base - 86} L300 ${base - 104} L360 ${base - 82} L430 ${base - 120} L500 ${base - 90} L580 ${base - 108} L650 ${base - 84} L720 ${base - 116} L800 ${base - 92} L880 ${base - 112} L960 ${base - 86} L1040 ${base - 104} L1120 ${base - 84} L1200 ${base - 96} V${base} H0Z" fill="${k.haze}" opacity=".55"/>
    <g fill="${k.ground}" opacity=".55">${Array.from({ length: mob ? 4 : 9 }, (_, i) => { const x = (mob ? 10 : 40) + i * (mob ? 112 : 140), hh = 34 + ((i * 37) % 30); return `<rect x="${x}" y="${base - hh - 30}" width="${48 + (i % 3) * 14}" height="${hh + 30}" rx="3"/><path d="M${x - 4} ${base - hh - 30} l${(52 + (i % 3) * 14) / 2 + 4} -18 l${(52 + (i % 3) * 14) / 2 + 4} 18Z"/>${Array.from({ length: 2 }, (_, j) => `<rect x="${x + 10 + j * 18}" y="${base - hh - 14}" width="9" height="9" fill="url(#win-${kind})" style="${lit(0.85)}"/>`).join("")}`; }).join("")}</g>`;
    const tree = (x, y, s) => `<g transform="translate(${x} ${y}) scale(${s})"><rect x="16" y="70" width="10" height="80" fill="#6B4A36"/><circle cx="21" cy="56" r="40" fill="color-mix(in srgb, #2E8B57 70%, ${k.ground})"/><circle cx="44" cy="78" r="26" fill="color-mix(in srgb, #3FA06A 70%, ${k.ground})"/></g>`;
    const lamp = (x, y, s = 1) => `<g transform="translate(${x} ${y}) scale(${s})"><rect x="0" y="0" width="4" height="46" fill="#3A3F55"/><circle cx="2" cy="0" r="6" fill="${k.lit ? "#FFE3A1" : "#C9CFDB"}"/><circle cx="2" cy="0" r="20" fill="#FFE3A1" style="${lit(0.25)}"/></g>`;
    if (mob) {
      return `<svg class="scene-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMin slice" aria-hidden="true">${sky}${far}
      ${tree(146, base - 118, 0.8)}
      <g transform="translate(186 ${base - 133}) scale(.7)">${shopFront(k, kind, h)}</g>
      <rect x="0" y="${base}" width="${W}" height="${H - base}" fill="${k.ground}"/>
      <path d="M0 ${base + 20} H${W}" stroke="#fff" stroke-opacity=".28" stroke-dasharray="22 16" stroke-width="3"/>
      <g transform="translate(14 ${base - 177}) scale(.86)"><g class="bob">${BAG(kind)}</g></g>
      <ellipse cx="80" cy="${base + 6}" rx="62" ry="5" fill="#000" opacity=".16"/>
      ${lamp(160, base - 46)}${lamp(420, base - 46)}</svg>`;
    }
    if (cm) {
      const roofs = Array.from({ length: 6 }, (_, i) => { const x = 8 + i * 52, hh = 18 + ((i * 13) % 14), w = 30 + (i % 3) * 6; return `<rect x="${x}" y="${base - hh - 16}" width="${w}" height="${hh + 16}" rx="2"/><path d="M${x - 3} ${base - hh - 16} l${w / 2 + 3} -11 l${w / 2 + 3} 11Z"/><rect x="${x + 7}" y="${base - hh - 6}" width="6" height="6" fill="url(#win-${kind})" style="${lit(0.85)}"/><rect x="${x + 17}" y="${base - hh - 6}" width="6" height="6" fill="url(#win-${kind})" style="${lit(0.85)}"/>`; }).join("");
      return `<svg class="scene-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMaxYMax slice" aria-hidden="true">${sky}
      <path d="M0 ${base - 38} L60 ${base - 48} L130 ${base - 40} L200 ${base - 56} L280 ${base - 42} L360 ${base - 52} L440 ${base - 44} V${base} H0Z" fill="${k.haze}" opacity=".5"/>
      <g fill="${k.ground}" opacity=".6">${roofs}</g>
      <g transform="translate(322 ${base - 55.1}) scale(.29)">${shopFront(k, kind, h)}</g>
      <rect x="0" y="${base}" width="${W}" height="${H - base}" fill="${k.ground}"/></svg>`;
    }
    if (kind !== "hero") {
      return `<svg class="scene-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">${sky}${far}
      <rect x="0" y="${base}" width="${W}" height="${H - base}" fill="${k.ground}"/>
      <g transform="translate(940 ${base - 79.8}) scale(.42)">${shopFront(k, kind, h)}</g></svg>`;
    }
    const house = `<g transform="translate(-40 ${base - 190})">
      <path d="M0 80 L110 10 L220 80 V190 H0Z" fill="color-mix(in srgb, #F2EEE6 80%, ${k.ground})"/>
      <path d="M-14 86 L110 0 L234 86" fill="none" stroke="#8E5A48" stroke-width="16" stroke-linejoin="round" stroke-linecap="round"/>
      <rect x="160" y="18" width="24" height="44" fill="#8E5A48"/>
      <g class="smoke"><circle cx="172" cy="6" r="8" fill="#fff" opacity=".35"/><circle cx="180" cy="-12" r="10" fill="#fff" opacity=".25"/><circle cx="170" cy="-32" r="12" fill="#fff" opacity=".15"/></g>
      <rect x="28" y="104" width="76" height="56" rx="6" fill="#20263C"/><rect x="28" y="104" width="76" height="56" rx="6" fill="url(#win-${kind})" style="${lit(1)}"/>
      <path d="M50 150 h32 q0 -16 -16 -16 q-16 0 -16 16Z" fill="#2A2238" opacity=".85"/><rect x="46" y="148" width="40" height="5" rx="2" fill="#2A2238" opacity=".85"/>
      <g class="steam"><path d="M58 128 q-5 -8 0 -16 q5 -8 0 -16" stroke="#fff" stroke-width="2.4" fill="none" opacity=".7" stroke-linecap="round"/><path d="M70 126 q-5 -8 0 -16 q5 -8 0 -16" stroke="#fff" stroke-width="2.4" fill="none" opacity=".55" stroke-linecap="round"/></g>
      <rect x="138" y="116" width="50" height="74" rx="4" fill="#5A4034"/><circle cx="178" cy="154" r="3" fill="#E9C46A"/>
      <path d="M28 132 h76 M66 104 v56" stroke="#F2EEE6" stroke-width="3" opacity=".9"/></g>
      <g transform="translate(196 ${base - 150})"><rect x="16" y="70" width="10" height="80" fill="#6B4A36"/><circle cx="21" cy="56" r="40" fill="color-mix(in srgb, #2E8B57 70%, ${k.ground})"/><circle cx="44" cy="78" r="26" fill="color-mix(in srgb, #3FA06A 70%, ${k.ground})"/></g>`;
    const bag = `<g transform="translate(232 ${base - 200})"><g class="bob">${BAG(kind)}</g></g><ellipse cx="312" cy="${base + 8}" rx="80" ry="6" fill="#000" opacity=".16"/>
      <g transform="translate(960 ${base - 150})"><rect x="16" y="70" width="10" height="80" fill="#6B4A36"/><circle cx="21" cy="50" r="46" fill="color-mix(in srgb, #2E8B57 70%, ${k.ground})"/><circle cx="-6" cy="76" r="26" fill="color-mix(in srgb, #3FA06A 70%, ${k.ground})"/></g>`;
    return `<svg class="scene-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">${sky}${far}
    ${house}
    <g transform="translate(420 ${base - 190})">${shopFront(k, kind, h)}</g>
    <rect x="0" y="${base}" width="${W}" height="${H - base}" fill="${k.ground}"/>
    <path d="M0 ${base + 22} H${W}" stroke="#fff" stroke-opacity=".28" stroke-dasharray="26 18" stroke-width="3"/>
    ${bag}
    ${Array.from({ length: 4 }, (_, i) => `<g transform="translate(${70 + i * 300} ${base - 52})"><rect x="0" y="0" width="5" height="52" fill="#3A3F55"/><circle cx="2.5" cy="0" r="7" fill="${k.lit ? "#FFE3A1" : "#C9CFDB"}"/><circle cx="2.5" cy="0" r="22" fill="#FFE3A1" style="${lit(0.25)}"/></g>`).join("")}
  </svg>`;
  };

  const ICON = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
    clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    bag: '<path d="M5 8h14l-1.4 10.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8Z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
    truck: '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/>',
    receipt: '<path d="M7 3h10v18l-2.5-1.6L12 21l-2.5-1.6L7 21Z M9.5 8h5 M9.5 11.5h5 M9.5 15h3"/>',
    phone: '<rect x="6" y="2.5" width="12" height="19" rx="3"/><path d="M10.5 18.5h3"/>',
    pen: '<path d="M5 19l1-4L16 5l3 3L9 18Z M14 7l3 3"/>',
    send: '<path d="M4 12 20 4l-4.5 16-3.5-6.5Z"/><path d="M12 13.5 20 4"/>',
    home: '<path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5h-5v5H5a1 1 0 0 1-1-1Z"/>',
  };
  const ic = (k, s = 20) => `<svg class="i" viewBox="0 0 24 24" width="${s}" height="${s}" aria-hidden="true">${ICON[k] || ""}</svg>`;

  return {
    fmt, krd, DAYS, DAYS_LONG, MONTHS, MONTHS_LONG, cap, ymd, addDays, daysBetween, isoWeek, weekNo, sundayOf, span, greet,
    P, sector, arc, countUp, GROUPS, GNAME, ORDER, ART, art, dot, groupOf, clean, pic, dishKind, dishArt, skyAt, scene, ICON, ic,
  };
})();

/* The pages drawn with the helpers above: methods of the panel. */
const V3_FEES = "middagsro.fees.v1";
const V3_TITLES = {
  plan: "Madplan", recipes: "Opskrifter", shopping: "Indkøb", favorites: "Favoritter", budget: "Økonomi",
  health: "Sundhed", inventory: "Spisekammer", history: "Historik", settings: "Indstillinger",
};
const V3_METHODS = {
  _v3s() {
    if (!this._v3) {
      let fees = { bilka: "pickup", nemlig: 39, zones: 2 };
      try { fees = { ...fees, ...(JSON.parse(localStorage.getItem(V3_FEES) || "null") || {}) }; } catch { /* a browser without storage */ }
      this._v3 = { week: null, day: null, span: "week", sel: null, solo: null, hw: 0, q: "", hits: [], hitsQ: "", searching: false,
        amt: "", cmp: {}, cmpLoading: null, img: {}, imgAsked: new Set(), sort: "kr", fees, keys: {}, counted: {} };
    }
    return this._v3;
  },

  _v3Phone() { return matchMedia("(max-width: 700px)").matches; },
  _v3Kind() { const phone = this._v3Phone(); return this._tab === "home" ? (phone ? "mobile" : "hero") : phone ? "compactm" : "compact"; },
  _v3Hour() { const d = new Date(); return d.getHours() + d.getMinutes() / 60; },

  /* ------------------------------------------------------------ the header: the street */
  _v3Header() {
    const root = this.shadowRoot;
    const hdr = root.querySelector("#hdr");
    if (!hdr || this._embed) return;
    const s = this._v3s();
    const home = this._tab === "home";
    hdr.classList.toggle("big", home);
    hdr.classList.toggle("small", !home);
    const sky = V3.skyAt(this._v3Hour());
    hdr.dataset.sky = sky.name;
    const kind = this._v3Kind();
    const sceneKey = `${kind}|${Math.floor(this._v3Hour() * 12)}`;
    if (s.keys.scene !== sceneKey) {
      s.keys.scene = sceneKey;
      root.querySelector("#scene").innerHTML = V3.scene(kind, this._v3Hour());
    }
    const body = root.querySelector("#hdr-body");
    const typing = body.contains(root.activeElement);
    const html = this._v3HeaderBody();
    if (!typing && s.keys.body !== html) {
      s.keys.body = html;
      body.innerHTML = html;
      const left = body.querySelector("[data-count]");
      if (left) V3.countUp(left, Number(left.dataset.count), 700);
    }
  },

  // Once a minute the sky moves on (called from the panel's one-second tick).
  _v3SceneTick() {
    if (this._embed || !this.shadowRoot.querySelector("#scene")) return;
    const s = this._v3s();
    const kind = this._v3Kind();
    const key = `${kind}|${Math.floor(this._v3Hour() * 12)}`;
    if (s.keys.scene === key) return;
    s.keys.scene = key;
    this.shadowRoot.querySelector("#scene").innerHTML = V3.scene(kind, this._v3Hour());
    const hdr = this.shadowRoot.querySelector("#hdr");
    if (hdr) hdr.dataset.sky = V3.skyAt(this._v3Hour()).name;
  },

  _v3HeaderBody() {
    if (!this._state) return "";
    if (this._tab !== "home") {
      const [title, sub] = this._v3PageTitle();
      return `<div class="page-title"><h1>${esc(title)}</h1>${sub ? `<p>${sub}</p>` : ""}</div>`;
    }
    const now = new Date();
    const wk = V3.weekNo(V3.sundayOf(localToday()));
    return `<div class="hero-copy"><div class="kicker light">${V3.DAYS_LONG[now.getDay()]} ${now.getDate()}. ${V3.MONTHS_LONG[now.getMonth()]} · uge ${wk}</div>
        <h1 class="hello">${V3.greet(this._v3Hour())}${this._hass?.user?.name ? `, ${esc(String(this._hass.user.name).split(" ")[0])}` : ""}</h1>
        <p class="hero-sub">${this._v3Tonight()}</p></div>
      <div class="glass budget-glass">${this._v3HeroBudget()}</div>`;
  },

  _v3PageTitle() {
    const st = this._state;
    const plan = this._plan;
    const b = st.budget;
    const title = V3_TITLES[this._tab] || "Middagsro";
    const sub = {
      plan: () => (plan ? `Uge ${plan.week || V3.weekNo(V3.sundayOf(plan.start_date))} · ${V3.span(V3.sundayOf(plan.start_date))}` : "Ingen madplan endnu"),
      recipes: () => (this._recipesSub === "collection" ? `${(st.recipes || []).length} retter i samlingen` : "Ugens opskrifter"),
      shopping: () => (plan ? `Til uge ${plan.week || ""} · ${plan.shopping.filter((l) => !l.skipped).length} varer${st.rema_list ? ` + ${st.rema_list.items.filter((i) => !i.bought).length} på ${esc(this._listName())}` : ""}` : esc(this._listName())),
      favorites: () => (this._isRema() ? `${this._favCache?.current?.products?.length ?? ""} varer fra REMA 1000 · overvågning af tilbud`.trim() : "Overvågning af tilbud"),
      budget: () => (b ? `Uge ${b.week.week} · ${kr0(Math.abs(b.week.remaining))} ${b.week.remaining < 0 ? "over" : "tilbage"}` : "Madbudget og forbrug"),
      health: () => "Det, I køber, og det, I spiser",
      inventory: () => "Det, I allerede har hjemme",
      history: () => "Indkøb, madplaner og varer",
      settings: () => "Butikker, logins, budget og udseende",
    }[this._tab];
    return [title, sub ? sub() : ""];
  },

  _v3Today() {
    const today = localToday();
    const tl = this._timeline();
    if (tl) return tl.find((e) => e.date === today && e.day) || null;
    const day = (this._plan?.days || []).find((d) => d.date === today);
    return day ? { plan: this._plan, day, date: today } : null;
  },

  _v3Tonight() {
    const e = this._v3Today();
    if (!e) return this._plan ? "Ingen ret i aften." : "Lav jeres første madplan – den bygges på ugens tilbud.";
    const d = e.day;
    return `I aften: <b>${esc(d.dish || "Ingen ret")}</b>${d.total_minutes ? ` · ${d.total_minutes} min` : ""}`;
  },

  /* The week's money in the street: a ring, the days, and a field to book an amount. */
  _v3HeroBudget() {
    const b = this._state?.budget;
    if (!b) {
      return `<div class="hb-top"><div class="hb-num"><span class="kicker light">Madbudget</span><b>Hold øje med ugen</b><span>Skriv jeres faste beløb, så tæller Middagsro med.</span></div></div>
        <div class="hb-quick"><button class="hb-link" data-action="tab" data-arg="budget">Start madbudget ›</button></div>`;
    }
    const m = this._v3WeekModel(this._v3WeekIndex(true));
    const left = m.budget - m.spent, f = m.budget > 0 ? Math.min(1, m.spent / m.budget) : 1;
    const daysLeft = Math.max(1, 7 - m.todayIdx);
    const dmax = Math.max(200, ...m.days);
    const s = this._v3s();
    const [nx, ny] = V3.P(60, 60, 50, m.nowFrac * 360);
    return `<div class="hb-top">
      <svg class="hb-ring" viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="10"/>
        ${f > 0 ? `<path class="seg-arc" d="${V3.arc(60, 60, 50, 0, f * 360)}" pathLength="100" style="--len:100;fill:none;stroke:${m.spent > m.budget ? "var(--v3-bad)" : "#7CF2C8"};stroke-width:10;stroke-linecap:round"/>` : ""}
        <circle cx="${nx.toFixed(1)}" cy="${ny.toFixed(1)}" r="4" fill="#fff"/></svg>
      <div class="hb-num"><span class="kicker light">Ugens madbudget · uge ${m.wk}</span><b class="num" data-count="${Math.abs(left)}">${V3.krd(Math.abs(left))}</b><span>${left >= 0 ? `tilbage · ≈ ${V3.krd(left / daysLeft)} pr. dag` : "over budget"}</span></div>
    </div>
    <div class="hb-days">${m.days.map((v, d) => `<div class="hbd${d === m.todayIdx ? " now" : ""}"><span class="bar">${V3.ORDER.filter((g) => m.dayG[d][g]).map((g) => `<i style="flex-grow:${m.dayG[d][g].toFixed(2)};background:var(--g-${g})"></i>`).join("")}<em style="height:${Math.max(0, 100 - (v / dmax) * 100).toFixed(1)}%"></em></span><small>${V3.DAYS[m.jsDay(d)][0]}</small></div>`).join("")}</div>
    <div class="hb-book"><label class="hb-amt">${V3.ic("plus", 16)}<input data-bind="v3amt" data-v3book="hero" inputmode="decimal" enterkeyhint="done" value="${esc(s.amt)}" placeholder="Kontér et beløb" aria-label="Beløb i kroner" autocomplete="off"><span>kr.</span></label><button class="hb-go" data-action="v3-book" data-arg="hero">Kontér</button></div>
    <div class="hb-quick">${[100, 250, 500].map((v) => `<button data-action="v3-add" data-arg="${v}">+${v}</button>`).join("")}<button class="hb-link" data-action="tab" data-arg="budget">Se økonomi ›</button></div>`;
  },

  _v3Amount(raw) {
    const v = Number(String(raw || "").replace(/\s/g, "").replace(/\.(?=\d{3}(\D|$))/g, "").replace(",", "."));
    return v > 0 ? Math.round(v * 100) / 100 : 0;
  },

  _v3Book(where) {
    const s = this._v3s();
    const amount = this._v3Amount(s.amt);
    if (!amount) {
      this.shadowRoot.querySelector(`[data-v3book="${where}"]`)?.focus();
      return this._say("Skriv beløbet, der skal konteres.");
    }
    let booked = null;
    s.amt = "";
    s.week = null;
    s.day = null;
    this.shadowRoot.querySelectorAll("[data-v3book]").forEach((i) => { i.value = ""; i.blur(); });
    this._run(async () => {
      booked = (await this._ws("middagsro/purchases/add", { amount, store: this._storeId(), date: localToday() }))?.booked || null;
    }, () => {
      if (booked) this._toastAction = { label: "Fortryd", action: "purchase-undo", arg: booked };
      return `${V3.krd(amount, amount % 1 ? 2 : 0)} er konteret på uge ${this._state?.budget?.week?.week || ""}.`;
    });
  },

  /* ------------------------------------------------------------------ Forside */
  _homeView() {
    return `<div class="v3 home">${this._v3PlanCard()}${this._v3Quick()}</div>${CREDIT}`;
  },

  _v3PlanWeeks() {
    const tl = this._timeline();
    const today = localToday();
    let entries;
    if (tl) entries = tl.filter((e) => e.day || e.skipped);
    else if (this._plan?.days) entries = this._plan.days.map((d) => ({ date: d.date, day: d, plan: this._plan, week: V3.isoWeek(new Date(`${d.date}T12:00:00`)) }));
    else entries = [];
    const weeks = [];
    for (const e of entries) {
      let w = weeks.find((x) => x.week === e.week);
      if (!w) weeks.push((w = { week: e.week, entries: [] }));
      w.entries.push(e);
    }
    // This week first (the one with today, or the first still to come).
    const now = weeks.findIndex((w) => w.entries.some((e) => e.date >= today));
    return now > 0 ? weeks.slice(now) : weeks;
  },

  _v3PlanCard() {
    const s = this._v3s();
    const plan = this._plan;
    if (!plan) {
      return `<div class="card plan-home"><div class="row between wrap"><div><div class="kicker">Madplan</div><h2>Ingen madplan endnu</h2><p class="sub">Madplanen laves med AI ud fra ugens tilbud og jeres indstillinger.</p></div>
        <button class="btn primary" data-action="tab" data-arg="plan">Lav madplan</button></div></div>`;
    }
    const weeks = this._v3PlanWeeks();
    const idx = Math.min(s.hw, Math.max(0, weeks.length - 1));
    const w = weeks[idx];
    const today = localToday();
    // This week starts with today; the days gone are on the Madplan page.
    const shown = idx === 0 && (w?.entries || []).some((e) => e.date >= today) ? w.entries.filter((e) => e.date >= today) : w?.entries || [];
    const tiles = shown.map((e, i) => {
      const d = new Date(`${e.date}T12:00:00`), now = e.date === today, past = e.date < today;
      const day = e.day;
      const dish = e.skipped ? "Springes over" : day?.dish || "Ingen ret";
      const type = day ? TYPE_LABELS[day.type] ?? "" : "";
      return `<button class="dtile${now ? " now" : ""}${past ? " past" : ""}${e.skipped ? " skipped" : ""}" data-action="${e.skipped ? "day-menu-skipped" : "day-menu"}" data-arg="${esc(e.plan.id)}|${esc(e.date)}" style="animation-delay:${i * 0.05}s">
        <span class="dt-day">${now ? "I aften" : V3.DAYS_LONG[d.getDay()]}</span><span class="dt-date">${d.getDate()}. ${V3.MONTHS[d.getMonth()]}</span>
        ${V3.dishArt(e.skipped ? "" : dish)}<b>${esc(dish)}</b>
        <span class="dt-meta">${day?.total_minutes ? `${V3.ic("clock", 13)} ${day.total_minutes} min` : ""}${type ? `<span class="tag">${esc(type)}</span>` : ""}</span></button>`;
    }).join("");
    const dinners = (w?.entries || []).filter((e) => e.day && e.day.dish && !["rester", "egen", "tom"].includes(e.day.type)).length;
    const rest = (w?.entries || []).filter((e) => e.day && (e.day.type === "rester" || e.day.uses_leftovers_from)).length;
    const left = plan.shopping.filter((l) => !l.buy_from && !l.buy_at && !l.sent).length;
    return `<div class="card plan-home">
      <div class="row between wrap"><div><div class="kicker">${esc(w ? `Madplan uge ${w.week}` : plan.title || "Madplan")}</div><h2>${idx === 0 ? "Denne uges aftensmad" : "Næste uges aftensmad"}</h2>
        <p class="sub">${plan.summary && idx === weeks.length - 1 ? `${esc(plan.summary)} ` : ""}Tryk på en dag for at se opskriften eller skifte retten.</p></div>
        ${weeks.length > 1 ? `<div class="seg">${weeks.slice(0, 2).map((x, i) => `<button class="${idx === i ? "on" : ""}" data-action="v3-hw" data-arg="${i}">${i === 0 ? "Denne uge" : "Næste uge"}</button>`).join("")}</div>` : ""}</div>
      <div class="strip">${tiles || '<p class="sub">Ingen dage i ugen.</p>'}</div>
      <div class="plan-foot">
        <span class="pf-stat"><b class="num">${kr0(plan.total)}</b><span>indkøb til planen</span></span>
        <span class="pf-stat"><b class="num">${dinners}</b><span>aftener at lave</span></span>
        <span class="pf-stat"><b class="num">${rest}</b><span>restedage</span></span>
        <span class="spacer"></span>
        <button class="btn" data-action="tab" data-arg="plan">Åbn madplanen</button>
        ${left ? `<button class="btn primary" data-action="tab" data-arg="shopping">${V3.ic("bag", 16)} Indkøbslisten</button>` : `<span class="pill good">${V3.ic("check", 14)} Sendt til listen</span>`}
      </div></div>`;
  },

  /* Quick add: search the shop, tap, and it is on the list. */
  _v3Quick() {
    const s = this._v3s();
    const list = this._state?.rema_list;
    const onList = (list?.items || []).filter((i) => !i.bought);
    const often = ((this._state?.receipts?.items) || []).filter((i) => i.frequent).slice(0, 6);
    return `<div class="card quickadd">
      <div class="row between wrap"><div><div class="kicker">Lyn-tilføj</div><h2>Mangler I noget?</h2></div>
        <button class="cart" data-action="tab" data-arg="shopping" aria-label="Indkøbslisten">${V3.ic("bag", 22)}<span class="cart-n">${onList.length}</span></button></div>
      <div class="qbar${s.q ? " typing" : ""}">${V3.ic("search", 22)}<input data-bind="v3q" value="${esc(s.q)}" placeholder="Tilføj vare – fx mælk, bananer" autocomplete="off" enterkeyhint="done" aria-label="Tilføj vare">
        <button class="qgo" data-action="v3-qadd" aria-label="Tilføj">${V3.ic("plus", 22)}</button></div>
      <div class="qhits" id="v3-qhits">${this._v3QuickHits()}</div>
      ${!s.q && often.length ? `<div class="qchips"><span class="sub" style="margin:0 6px 0 0">Ofte købt</span>${often.map((i) => `<button data-action="v3-qfill" data-arg="${esc(V3.clean(i.name).split(/[ ,]/)[0])}">${esc(V3.clean(i.name).split(",")[0])}</button>`).join("")}</div>` : ""}
      <div class="onlist"><span class="kicker">På ${esc(list?.name || this._listName())} · ${onList.length}</span><div class="ol-chips">${onList.slice(0, 40).map((i) => `<span class="olc">${i.amount > 1 ? `<b>${i.amount}×</b> ` : ""}${esc(i.name)}</span>`).join("") || '<span class="sub">Listen er tom.</span>'}</div></div>
    </div>`;
  },

  _v3QuickHits() {
    const s = this._v3s();
    const q = s.q.trim();
    if (!q) return "";
    const hits = s.hitsQ === q ? s.hits : [];
    const rows = hits.slice(0, 6).map((p, i) => `<button class="qhit" data-action="v3-qpick" data-arg="${i}" style="animation-delay:${i * 0.03}s"><span class="qimg">${V3.pic(p.image, V3.groupOf(p.name))}</span><span class="qname">${esc(V3.clean(p.name))}${p.underline ? `<small>${esc(p.underline)}</small>` : ""}</span>${p.price ? `<span class="qprice">${V3.fmt(p.price, 2)} kr.</span>` : ""}<span class="qplus">${V3.ic("plus", 16)}</span></button>`).join("");
    const free = this._plan ? `<button class="qhit free" data-action="v3-qtext"><span class="qimg">${V3.art(V3.groupOf(q), "")}</span><span class="qname">Tilføj “${esc(q)}” til madplanens liste</span><span class="qplus">${V3.ic("plus", 16)}</span></button>` : "";
    return `${s.searching && s.hitsQ !== q ? '<p class="sub"><span class="spinner small"></span> Søger …</p>' : ""}${rows}${free}`;
  },

  _v3RenderQuick() {
    const node = this.shadowRoot.querySelector("#v3-qhits");
    if (node) { node.innerHTML = this._v3QuickHits(); this._v3Pics(node); }
    this.shadowRoot.querySelector(".qbar")?.classList.toggle("typing", !!this._v3s().q);
  },

  _v3Search() {
    const s = this._v3s();
    const q = s.q.trim();
    if (q.length < 2) { s.hits = []; s.hitsQ = q; this._v3RenderQuick(); return; }
    s.searching = true;
    this._v3RenderQuick();
    this._ws("middagsro/search", { query: q })
      .then((found) => { if (s.q.trim() !== q) return; s.hits = found || []; s.hitsQ = q; })
      .catch(() => { if (s.q.trim() === q) { s.hits = []; s.hitsQ = q; } })
      .finally(() => { s.searching = false; this._v3RenderQuick(); });
  },

  _v3Fly(from, label) {
    const cart = this.shadowRoot.querySelector(".cart");
    if (!from || !cart || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const a = from.getBoundingClientRect(), b = cart.getBoundingClientRect();
    const fly = document.createElement("div");
    fly.className = "v3-fly";
    fly.textContent = label;
    fly.style.left = `${a.left + 20}px`;
    fly.style.top = `${a.top}px`;
    this.shadowRoot.appendChild(fly);
    requestAnimationFrame(() => { fly.style.transform = `translate(${b.left - a.left - 10}px, ${b.top - a.top}px) scale(.3)`; fly.style.opacity = "0"; });
    setTimeout(() => fly.remove(), 700);
    cart.classList.remove("pop"); void cart.offsetWidth; cart.classList.add("pop");
  },
};

/* Økonomi: the week as a clock, the receipts, the rhythm, a year in one dial and the whole story. */
Object.assign(V3_METHODS, {
  // An animation plays when something new is drawn, not again on every redraw of the same.
  _v3Anim(key, sig) {
    const s = this._v3s();
    const same = s.counted[key] === sig;
    s.counted[key] = sig;
    return same ? " still" : "";
  },

  _v3Receipts() {
    const list = this._state?.receipts?.list || [];
    const s = this._v3s();
    if (s.rmapN !== list.length || !s.rmap) { s.rmap = new Map(list.map((r) => [`rcpt_${r.id}`, r])); s.rmapN = list.length; }
    return s.rmap;
  },

  _v3WeekIndex(current = false) {
    const W = this._state?.budget?.weeks || [];
    const cur = Math.max(0, W.findIndex((w) => w.current));
    const s = this._v3s();
    if (current || s.week == null || !W[s.week]) return W.findIndex((w) => w.current) >= 0 ? cur : W.length - 1;
    return s.week;
  },

  _v3Typical() {
    const B = (this._state?.receipts?.overview?.week?.buckets || []).filter((b) => b.count && b.days).slice(-26);
    const t = [0, 0, 0, 0, 0, 0, 0];
    for (const b of B) b.days.forEach((v, d) => (t[d] += v));
    return t.map((v) => (B.length ? v / B.length : 0));
  },

  _v3WeekModel(i) {
    const b = this._state.budget;
    const W = b.weeks || [];
    const w = W[i] || { start: b.week.start, week: b.week.week, budget: b.week.budget, spent: b.week.spent, current: true };
    const cur = !!w.current;
    const start = w.start, end = V3.ymd(V3.addDays(start, 6));
    const startJs = new Date(`${start}T12:00:00`).getDay();
    const jsDay = (k) => (startJs + k) % 7;
    const rmap = this._v3Receipts();
    const dayG = Array.from({ length: 7 }, () => ({}));
    const add = (d, g, v) => { dayG[d][g] = (dayG[d][g] || 0) + v; };
    const buys = (b.purchases || []).filter((p) => p.date >= start && p.date <= end);
    for (const p of buys) {
      const d = Math.min(6, Math.max(0, V3.daysBetween(start, p.date)));
      const r = rmap.get(p.id);
      const g = r?.groups || {};
      const sum = Object.values(g).reduce((a, x) => a + x, 0);
      if (sum > 0) for (const [k, v] of Object.entries(g)) add(d, k, (v / sum) * p.amount);
      else add(d, "none", p.amount);
    }
    const days = dayG.map((g) => Object.values(g).reduce((a, x) => a + x, 0));
    const groups = {};
    for (const g of dayG) for (const [k, v] of Object.entries(g)) groups[k] = (groups[k] || 0) + v;
    const today = localToday();
    const todayIdx = cur ? Math.min(6, Math.max(0, V3.daysBetween(start, today))) : 7;
    const nowFrac = cur ? Math.min(1, (todayIdx + this._v3Hour() / 24) / 7) : 1;
    const typ = this._v3Typical();
    return {
      i, start, end, wk: w.week, current: cur, jsDay, todayIdx, nowFrac, days, dayG, groups,
      budget: cur ? b.week.available : w.budget, spent: cur ? b.week.spent : w.spent,
      typical: Array.from({ length: 7 }, (_, k) => typ[jsDay(k)]),
      buys: buys.slice().sort((x, y) => (y.date + (y.created || "")).localeCompare(x.date + (x.created || ""))),
    };
  },

  _v3WeekDial(m) {
    const s = this._v3s();
    const C = 200, SEC = 360 / 7, R = 170, W = 10, IN = 112, OUT = 146;
    const cur = m.current;
    const cap = Math.max(700, ...m.days, ...m.typical);
    const petalR = (v) => IN + (OUT - IN) * Math.sqrt(Math.min(v, cap) / cap);
    let out = `<defs><linearGradient id="v3budg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="var(--rema-accent)"/><stop offset="1" stop-color="color-mix(in srgb, var(--rema-accent) 55%, #A3E635)"/></linearGradient></defs>`;
    out += `<circle class="face" cx="${C}" cy="${C}" r="160" opacity=".7"/>`;
    if (cur) out += `<path d="${V3.sector(C, C, 90, 160, m.todayIdx * SEC - SEC / 2, m.todayIdx * SEC + SEC / 2)}" fill="var(--rema-tint)"/>`;
    for (let d = 0; d < 7; d += 1) { const a = d * SEC + SEC / 2; const [x1, y1] = V3.P(C, C, 92, a), [x2, y2] = V3.P(C, C, 160, a); out += `<line class="tick" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`; }
    for (let d = 0; d < 7; d += 1) {
      const a0 = d * SEC - SEC / 2 + 4, a1 = d * SEC + SEC / 2 - 4, v = m.days[d];
      out += `<g class="day${s.day === d ? " on" : ""}${s.day != null && s.day !== d ? " dim" : ""}" data-action="v3-day" data-arg="${d}">`;
      out += `<path d="${V3.sector(C, C, 90, 160, d * SEC - SEC / 2, d * SEC + SEC / 2)}" fill="transparent"/>`;
      if (cur && m.typical[d] > 20 && v < m.typical[d]) out += `<path class="ghost" d="${V3.sector(C, C, IN, petalR(m.typical[d]), a0, a1)}"/>`;
      if (v > 0.5) {
        const r1 = petalR(v);
        let r = IN;
        out += `<g class="petal" style="animation-delay:${(0.15 + d * 0.06).toFixed(2)}s">`;
        for (const g of V3.ORDER) {
          const gv = m.dayG[d][g];
          if (!gv) continue;
          const h = (gv / v) * (r1 - IN);
          if (h < 0.5) { r += h; continue; }
          out += `<path d="${V3.sector(C, C, r, r + h, a0, a1)}" fill="var(--g-${g})" stroke="var(--card-background-color)" stroke-width="1.2"/>`;
          r += h;
        }
        out += "</g>";
        const [lx, ly] = V3.P(C, C, r1 + 8, d * SEC);
        out += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" class="dayval">${V3.fmt(v)}</text>`;
      }
      const [x, y] = V3.P(C, C, 101, d * SEC);
      out += `<text class="daylab${cur && d === m.todayIdx ? " today" : ""}" x="${x.toFixed(1)}" y="${y.toFixed(1)}">${V3.DAYS[m.jsDay(d)]}</text></g>`;
    }
    out += `<circle class="track" cx="${C}" cy="${C}" r="${R}" stroke-width="${W}"/>`;
    const frac = m.budget > 0 ? Math.min(1, m.spent / m.budget) : 0;
    if (frac > 0) out += `<path class="seg-arc" d="${V3.arc(C, C, R, 0, frac * 360)}" pathLength="100" style="--len:100;stroke:url(#v3budg);stroke-width:${W};stroke-linecap:round"/>`;
    if (m.budget > 0 && m.spent > m.budget) {
      const over = Math.min(359, ((m.spent - m.budget) / m.budget) * 360);
      out += `<path class="over" d="${V3.arc(C, C, R + 13, 0, over)}" pathLength="100" stroke-dasharray="100" style="--len:100;stroke-width:5"/>`;
      const [x, y] = V3.P(C, C, R + 26, Math.min(over, 340));
      out += `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" class="overval">+${V3.fmt(m.spent - m.budget)}</text>`;
    }
    if (cur) {
      const pa = m.nowFrac * 360;
      const [x1, y1] = V3.P(C, C, 90, pa), [x2, y2] = V3.P(C, C, R + 8, pa), [px, py] = V3.P(C, C, R + 20, pa);
      out += `<line class="needle" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"/>`;
      out += `<text x="${px.toFixed(1)}" y="${py.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" class="nowlab">NU</text>`;
    }
    out += `<circle cx="${C}" cy="${C}" r="90" fill="var(--card-background-color)"/>`;
    return out;
  },

  _v3MiniRing(spent, budget) {
    const f = budget > 0 ? spent / budget : 0, over = f > 1;
    return `<svg viewBox="0 0 28 28" aria-hidden="true"><circle cx="14" cy="14" r="10" fill="none" stroke="var(--rema-subtle)" stroke-width="4"/>
    ${f > 0 ? `<path d="${V3.arc(14, 14, 10, 0, Math.min(1, f) * 360)}" fill="none" stroke="${over ? "var(--v3-bad)" : "var(--rema-accent)"}" stroke-width="4" stroke-linecap="round"/>` : ""}</svg>`;
  },

  _v3Buys(m) {
    const s = this._v3s();
    const rmap = this._v3Receipts();
    const L = s.day == null ? m.buys : m.buys.filter((p) => V3.daysBetween(m.start, p.date) === s.day);
    const dayName = s.day == null ? "" : V3.cap(V3.DAYS_LONG[m.jsDay(s.day)]);
    const head = s.day == null ? "" : `<div class="row between"><b>${dayName}</b><button class="undo" data-action="v3-day" data-arg="${s.day}">Vis hele ugen</button></div>`;
    if (!L.length) return `${head}<p class="sub">${s.day == null ? `Endnu intet konteret i uge ${m.wk}.` : "Ingen køb den dag."}</p>`;
    return head + L.map((p) => {
      const r = rmap.get(p.id);
      const kind = r ? "receipt" : p.source === "action" ? "phone" : "pen";
      const color = r ? "var(--rema-accent)" : p.source === "action" ? "var(--v3-ink)" : "var(--v3-good)";
      const what = r ? "REMA-kvittering" : p.source === "action" ? "Automatisk" : "Konteret";
      const d = new Date(`${p.date}T12:00:00`);
      const t = r?.date ? new Date(r.date) : null;
      const g = r?.groups || null;
      const name = p.store === "other" ? p.note || "Andet" : r ? `REMA 1000${r.store ? ` ${r.store}` : ""}` : this._chainName(p.store);
      const open = r ? ` data-action="v3-bon" data-arg="${esc(r.id)}"` : ` data-action="purchase-edit" data-arg="${esc(p.id)}"`;
      return `<button class="buy open"${open}><span class="ic" style="background:color-mix(in srgb, ${color} 14%, transparent);color:${color}">${V3.ic(kind, 20)}</span>
        <span><b>${esc(name)}</b><small>${V3.DAYS_LONG[d.getDay()]} ${d.getDate()}. ${V3.MONTHS[d.getMonth()]}${t ? ` kl. ${String(t.getHours()).padStart(2, "0")}.${String(t.getMinutes()).padStart(2, "0")}` : ""} · ${what}${r ? ` · ${r.items} linjer` : p.note && p.store !== "other" ? ` · ${esc(p.note)}` : ""}</small>
        ${g && Object.keys(g).length ? `<span class="mini-g">${V3.ORDER.filter((k) => g[k]).map((k) => `<i style="flex-grow:${g[k]};background:var(--g-${k})"></i>`).join("")}</span>` : ""}</span>
        <span class="amt">${V3.krd(p.amount, 2)}<br><small class="chev">${r ? "Se bon ›" : "Ret ›"}</small></span></button>`;
    }).join("");
  },

  // The week's groups, or the chosen day's.
  _v3Legend(m) {
    const s = this._v3s();
    const g = s.day == null ? m.groups : m.dayG[s.day] || {};
    const total = Object.values(g).reduce((a, x) => a + x, 0);
    const head = s.day == null ? "" : `<span class="lg-head">${esc(V3.cap(V3.DAYS_LONG[m.jsDay(s.day)]))} · ${V3.krd(total, 2)}</span>`;
    const chips = V3.ORDER.filter((k) => g[k] > 0.5).map((k) => `<span class="lg">${V3.dot(k)}${esc(V3.GNAME[k])} <span class="v">${V3.fmt(g[k])}</span></span>`).join("");
    return head + (chips || (s.day == null ? "" : '<span class="sub">Intet købt den dag.</span>'));
  },

  _v3PickDay(d) {
    const s = this._v3s();
    s.day = s.day === d ? null : d;
    const root = this.shadowRoot;
    root.querySelectorAll(".dial .day").forEach((g) => { const k = Number(g.dataset.arg); g.classList.toggle("on", s.day === k); g.classList.toggle("dim", s.day != null && s.day !== k); });
    const m = this._v3WeekModel(this._v3WeekIndex());
    const box = root.querySelector("#v3-buys");
    if (box) box.innerHTML = this._v3Buys(m);
    const legend = root.querySelector("#v3-wlegend");
    if (legend) legend.innerHTML = this._v3Legend(m);
  },

  _v3BudgetCard() {
    const b = this._state.budget;
    const s = this._v3s();
    const W = b.weeks || [];
    const i = this._v3WeekIndex();
    const m = this._v3WeekModel(i);
    const cur = m.current;
    const left = m.budget - m.spent;
    const daysLeft = Math.max(1, 7 - m.todayIdx);
    const pace = m.budget * (cur ? m.nowFrac : 1);
    const status = m.spent > m.budget ? ["bad", "Over budget"] : cur && m.spent > pace * 1.1 ? ["bad", "Over tempo"] : ["good", cur ? "På sporet" : "Holdt budgettet"];
    const curI = W.findIndex((w) => w.current);
    const pick = W.slice(-4).map((w) => {
      const j = W.indexOf(w);
      const mm = w.current ? this._v3WeekModel(j) : w;
      return `<button class="wk${j === i ? " on" : ""}" data-action="v3-week" data-arg="${j}" aria-label="Uge ${w.week}">${this._v3MiniRing(mm.spent, w.current ? b.week.available : w.budget)}<span>${w.current ? "Nu" : w.week}</span></button>`;
    }).join("");
    const wk = b.week;
    const per = b.period === "week" ? `${kr0(b.weekly)} hver uge` : `${kr0(b.monthly)} om måneden`;
    const notes = cur ? [
      Math.abs(wk.carry) >= 1 ? `${wk.carry > 0 ? `Heraf ${kr0(wk.carry)} sparet i tidligere uger` : `${kr0(-wk.carry)} trukket fra – brugt for meget tidligere`}.` : "",
      wk.planned > 0 ? `Resten af ugens lister er anslået til ${kr0(wk.planned)}. ${wk.after_planned < 0 ? `Det er ${kr0(-wk.after_planned)} mere, end der er tilbage.` : `Så er der ${kr0(wk.after_planned)} til resten.`}` : "",
    ].filter(Boolean) : [];
    const month = b.month;
    const anim = this._v3Anim("week", `${i}|${m.spent}|${m.budget}|${m.buys.length}`);
    return `<div class="card hero-week${anim}">
      <div class="hero-top">
        <div><div class="kicker">Ugens madbudget · uge ${m.wk}${cur ? " · denne uge" : ""}</div><h2>${V3.span(m.start)}</h2>
          <p class="sub">${cur ? `${esc(per)}. Ugen starter forfra ${V3.DAYS_LONG[new Date(`${m.start}T12:00:00`).getDay()]}.` : `En tidligere uge. <button class="undo" data-action="v3-week" data-arg="${curI}">Tilbage til denne uge</button>`}</p></div>
        <div class="weekpick">${pick}</div>
      </div>
      <div class="grid2" style="margin-top:6px">
        <div>
          <div class="dialwrap">
            <svg class="dial" viewBox="0 0 400 400" role="img" aria-label="Ugens forbrug: ${esc(V3.krd(m.spent))} af ${esc(V3.krd(m.budget))}">${this._v3WeekDial(m)}</svg>
            <div class="wcenter">
              <span class="lab">${left >= 0 ? "Tilbage" : "Over budget"}</span>
              <span class="big num${left < 0 ? " bad" : ""}" data-count="${Math.abs(left)}">${V3.krd(Math.abs(left))}</span>
              <span class="small">${cur ? (left > 0 ? `≈ ${V3.krd(left / daysLeft)} pr. dag · ${daysLeft} ${daysLeft === 1 ? "dag" : "dage"}` : "Resten af ugen") : `brugt ${V3.krd(m.spent)}`}</span>
              <span class="pill ${status[0]} chip">${status[1]}</span>
            </div>
          </div>
          <p class="sub" style="text-align:center">Tryk på en dag for at se dens køb.${cur && m.typical.some((v) => v > 20) ? " Stiplet: hvad dagen plejer at koste." : ""}</p>
        </div>
        <div>
          <div class="kbook">
            <div class="row between"><b>Kontér et beløb</b><span class="pill">uge ${wk.week}</span></div>
            <div class="kbook-row">
              <label class="kamount"><input data-bind="v3amt" data-v3book="eco" inputmode="decimal" enterkeyhint="done" value="${esc(s.amt)}" placeholder="0" aria-label="Beløb i kroner" autocomplete="off"><span>kr.</span></label>
              <button class="kgo" data-action="v3-book" data-arg="eco">Kontér</button>
            </div>
            <div class="kquick">${[50, 100, 250, 500].map((v) => `<button data-action="v3-add" data-arg="${v}">+${v}</button>`).join("")}</div>
            <details class="more-book"${this._book.amount || this._book.store || this._book.date ? " open" : ""}><summary>Anden butik eller dato</summary><div id="budget-book">${this._bookForm()}</div></details>
          </div>
          ${notes.map((n) => `<p class="sub note-line">${esc(n)}</p>`).join("")}
          <div class="stats4">
            <div class="stat"><span>Brugt</span><b class="num">${V3.krd(m.spent)}</b></div>
            <div class="stat"><span>Budget</span><b class="num">${V3.krd(m.budget)}</b></div>
            <div class="stat"><span>${cur ? "Tempo nu" : "Forskel"}</span><b class="num">${cur ? V3.krd(pace) : `${left >= 0 ? "−" : "+"}${V3.krd(Math.abs(left))}`}</b></div>
            <div class="stat"><span>${V3.cap(V3.MONTHS_LONG[Number(month.first.slice(5, 7)) - 1])} · af ${V3.fmt(month.budget)}</span><b class="num">${V3.krd(month.spent)}</b></div>
          </div>
          <div class="legend" id="v3-wlegend">${this._v3Legend(m)}</div>
          <div class="buys" id="v3-buys">${this._v3Buys(m)}</div>
        </div>
      </div></div>`;
  },

  /* The family's rhythm: which day the big shop is, and when. */
  _v3Rhythm() {
    const rh = this._state?.receipts?.overview?.rhythm;
    if (!rh) return "";
    const wd = rh.weekdays || [];
    const trips = wd.reduce((a, d) => a + d[0], 0), kroner = wd.reduce((a, d) => a + d[1], 0);
    if (trips < 6 || !kroner) return "";
    const top = wd.reduce((best, d, i) => (d[1] > wd[best][1] ? i : best), 0);
    const topAvg = wd[top][1] / Math.max(1, wd[top][0]);
    const restTrips = trips - wd[top][0];
    const restAvg = restTrips ? (kroner - wd[top][1]) / restTrips : 0;
    const maxKr = Math.max(...wd.map((d) => d[1]), 1);
    const hrs = top === 0 ? rh.sunday_hours : rh.hours;
    const peakH = hrs.indexOf(Math.max(...hrs));
    const hours = rh.hours.slice(7, 22), hmax = Math.max(...hours, 1);
    const stats = this._state?.budget?.stats;
    const extra = stats?.extra_trips ? ` Hertil ${stats.extra_trips} ekstra ture${stats.extra_average ? ` i snit ${V3.krd(stats.extra_average)}` : ""} de seneste tre måneder.` : "";
    const anim = this._v3Anim("rhythm", `${trips}|${kroner}`);
    return `<div class="card sunday${anim}"><div class="sunday-body">
      <div class="row between wrap"><div><div class="kicker">Jeres rytme</div><h2>${V3.cap(V3.DAYS_LONG[top])} er jeres store handelsdag</h2></div><span class="pill acc">${Math.round((wd[top][1] / kroner) * 100)} % af alle kroner</span></div>
      <p class="sub">${wd[top][0]} af ${trips} ture i REMA 1000 er om ${V3.DAYS_LONG[top]}en, i snit ${V3.krd(topAvg)}${restAvg ? ` – ${V3.fmt(topAvg / restAvg, 1)}× en tur de andre dage` : ""}. Typisk kl. ${peakH}–${peakH + 1}.${extra}</p>
      <div class="rhythm">${wd.map((d, i) => { const size = (this._v3Phone() ? 14 : 18) + (this._v3Phone() ? 30 : 46) * Math.sqrt(d[1] / maxKr); return `<div class="rd${i === top ? " top" : ""}"><div class="bub" style="width:${size.toFixed(0)}px;height:${size.toFixed(0)}px">${size > 28 ? d[0] : ""}</div><span>${V3.DAYS[i]}</span><small>${d[0] ? V3.fmt(d[1] / d[0]) : "–"}</small></div>`; }).join("")}</div>
      <p class="sub" style="margin-top:8px">Boblen er kronerne pr. ugedag, tallet i den antal ture; under den, kroner pr. tur.</p>
      <div class="hours" aria-label="Ture pr. time">${hours.map((h, i) => `<i class="${i + 7 === peakH ? "peak" : ""}" style="height:${Math.max(3, (h / hmax) * 100).toFixed(1)}%" title="kl. ${i + 7}: ${h} ture"></i>`).join("")}</div>
      <div class="hourlab"><span>07</span><span>10</span><span>13</span><span>16</span><span>19</span><span>21</span></div>
    </div></div>`;
  },

  /* One turn of the clock is a year in Uge and in Måned (52 weeks, 12 months); År is five years. */
  _v3Buckets(span) {
    const ov = this._state?.receipts?.overview;
    const g = ov?.[span];
    if (!g?.buckets?.length) return [];
    const today = localToday();
    const curKey = span === "week" ? V3.sundayOf(today) : span === "month" ? today.slice(0, 7) : today.slice(0, 4);
    const src = span === "year" ? g.buckets.slice(-5) : g.buckets;
    return src.map((b, i) => {
      const groups = { ...(b.groups || {}) };
      const gsum = Object.values(groups).reduce((a, x) => a + x, 0);
      if (b.spent > gsum + 1) groups.none = (groups.none || 0) + (b.spent - gsum);
      let label, short = "", long = "";
      if (span === "week") {
        const m0 = new Date(`${b.key}T12:00:00`).getMonth();
        const prev = i ? new Date(`${src[i - 1].key}T12:00:00`).getMonth() : -1;
        label = `Uge ${V3.weekNo(b.key)}`; short = i && m0 !== prev ? V3.MONTHS[m0] : ""; long = V3.span(b.key);
      } else if (span === "month") {
        const mo = Number(b.key.slice(5)) - 1;
        label = `${V3.cap(V3.MONTHS_LONG[mo])} ${b.key.slice(0, 4)}`; short = V3.MONTHS[mo];
      } else { label = b.key; short = b.key; }
      return { key: b.key, label, short, long, spent: b.spent, saved: b.saved, trips: b.count, groups, days: b.days || null, current: b.key === curKey };
    });
  },

  _v3SpendDial(B) {
    const s = this._v3s();
    const C = 220, R0 = 114, RL = 86, N = B.length, SEC = 360 / N, gap = N > 40 ? 1.3 : N > 20 ? 2.4 : N > 8 ? 3.2 : 5;
    const b = this._state.budget;
    const weekly = b ? (b.period === "week" ? b.weekly : (b.monthly * 12) / 52) : 0;
    const max = Math.max(...B.map((x) => x.spent), s.span === "week" ? weekly : 0, 1);
    const maxS = Math.max(...B.map((x) => x.saved), 1);
    const rOf = (v) => R0 + (v / max) * RL;
    const done = B.filter((x) => x.spent > 0 && !x.current);
    const avg = done.reduce((a, x) => a + x.spent, 0) / (done.length || 1);
    const hi = done.reduce((a, x) => (!a || x.spent > a.spent ? x : a), null);
    const lo = done.reduce((a, x) => (!a || x.spent < a.spent ? x : a), null);
    let out = `<circle cx="${C}" cy="${C}" r="${R0 + RL + 4}" fill="var(--rema-subtle)" opacity=".55"/><circle cx="${C}" cy="${C}" r="${R0 - 2}" fill="var(--card-background-color)"/>`;
    for (const f of [0.5, 1]) out += `<circle cx="${C}" cy="${C}" r="${R0 + RL * f}" fill="none" stroke="var(--divider-color)" stroke-width="1"/>`;
    B.forEach((x, i) => {
      const a0 = i * SEC + gap / 2, a1 = (i + 1) * SEC - gap / 2;
      let r = R0;
      const tot = Object.values(x.groups).reduce((p, q) => p + q, 0) || 1;
      out += `<g class="bar" style="animation-delay:${((i / N) * 0.6).toFixed(2)}s">`;
      for (const g of V3.ORDER) {
        const v = x.groups[g];
        if (!v) continue;
        const h = (((v / tot) * x.spent) / max) * RL;
        if (h < 0.4) { r += h; continue; }
        out += `<path class="gs${s.solo && s.solo !== g ? " dim" : ""}" data-g="${g}" d="${V3.sector(C, C, r, r + h, a0, a1)}" fill="var(--g-${g})" stroke="var(--card-background-color)" stroke-width="${N > 40 ? 0.8 : 1.2}"/>`;
        r += h;
      }
      if (x.current && x.spent === 0) out += `<path d="${V3.sector(C, C, R0, R0 + 6, a0, a1)}" fill="none" stroke="var(--v3-soft)" stroke-dasharray="2 3"/>`;
      if (x.saved > 0) { const h = 3 + (x.saved / maxS) * 16; out += `<path class="save" d="${V3.sector(C, C, R0 - 5 - h, R0 - 5, a0 + Math.min(1.2, gap / 2), a1 - Math.min(1.2, gap / 2))}"/>`; }
      out += "</g>";
      if (x.short) { const [tx, ty] = V3.P(C, C, R0 + RL + 26, (i + 0.5) * SEC); out += `<text class="tlab" x="${tx.toFixed(1)}" y="${ty.toFixed(1)}">${x.short}</text>`; }
    });
    if (done.length) {
      out += `<circle class="avg" cx="${C}" cy="${C}" r="${rOf(avg).toFixed(1)}"/>`;
      const [ax, ay] = V3.P(C, C, rOf(avg) + 2, 0);
      out += `<rect x="${(ax - 34).toFixed(1)}" y="${(ay - 17).toFixed(1)}" width="68" height="15" rx="7.5" fill="var(--card-background-color)" stroke="var(--divider-color)"/><text class="ringlab" x="${ax.toFixed(1)}" y="${(ay - 9).toFixed(1)}" text-anchor="middle" dominant-baseline="middle">snit ${V3.fmt(avg)}</text>`;
    }
    if (s.span === "week" && weekly) out += `<circle class="bud" cx="${C}" cy="${C}" r="${rOf(weekly).toFixed(1)}"/>`;
    for (const [x, sym] of [[hi, "▲"], [lo, "▼"]]) {
      if (!x) continue;
      const i = B.indexOf(x);
      const [mx, my] = V3.P(C, C, rOf(x.spent) + 9, (i + 0.5) * SEC);
      out += `<text class="mark" x="${mx.toFixed(1)}" y="${my.toFixed(1)}" style="fill:${sym === "▲" ? "var(--v3-bad)" : "var(--v3-good)"}">${sym}</text>`;
    }
    out += `<path class="sel" id="v3-selpath" d=""/>`;
    return { svg: out, avg, hi, lo, max, SEC, gap, C, R0, RL };
  },

  _v3SelPath() {
    const s = this._v3s();
    const sp = s.sp;
    const x = sp?.B[s.sel];
    if (!x) return "";
    const a0 = s.sel * sp.SEC + sp.gap / 2 - 1, a1 = (s.sel + 1) * sp.SEC - sp.gap / 2 + 1;
    return V3.sector(sp.C, sp.C, sp.R0 - 25, Math.max(sp.R0 + (x.spent / sp.max) * sp.RL, sp.R0 + 6) + 4, a0, a1);
  },

  _v3Center(x) {
    const s = this._v3s();
    const topG = Object.entries(x.groups).filter(([g]) => g !== "none").sort((p, q) => q[1] - p[1])[0];
    const daysMax = x.days ? Math.max(...x.days, 1) : 1;
    // A Sunday-first week, in the order of the week clock's days.
    return `<span class="lab">${esc(x.label)}${x.current ? (s.span === "year" ? " · til nu" : " · i gang") : ""}</span>
      <span class="big num" id="v3-bcbig">${V3.krd(x.spent)}</span>
      <span class="saved num">${x.saved ? `sparet ${V3.krd(x.saved)}` : "&nbsp;"}</span>
      <span class="meta">${x.trips} ${x.trips === 1 ? "tur" : "ture"}${topG ? ` · mest ${esc(V3.GNAME[topG[0]].split(" ")[0].toLowerCase())}` : ""}</span>
      ${x.days ? `<div class="minidays">${x.days.map((v) => `<i class="${v === daysMax && v > 0 ? "hi" : ""}" style="height:${Math.max(3, (v / daysMax) * 26).toFixed(1)}px"></i>`).join("")}</div><div class="minilab">${V3.DAYS.map((d) => `<span>${d[0]}</span>`).join("")}</div>` : `<span class="meta">${V3.krd(x.spent / Math.max(1, x.trips))} pr. tur</span>`}`;
  },

  _v3SpendCard() {
    const s = this._v3s();
    if (!this._isRema()) return "";
    const B = this._v3Buckets(s.span);
    const seg = `<div class="seg" role="tablist">${[["week", "Uge"], ["month", "Måned"], ["year", "År"]].map(([k, t]) => `<button class="${s.span === k ? "on" : ""}" data-action="v3-span" data-arg="${k}">${t}</button>`).join("")}</div>`;
    if (!B.length || !B.some((x) => x.spent > 0)) {
      return `<div class="card spend"><div class="row between wrap"><div><div class="kicker">Forbrug &amp; besparelse</div><h2>REMA-forbrug</h2></div>${seg}</div>
        <p class="sub">Når der er kvitteringer, vises jeres REMA 1000-forbrug her – uge for uge, måned for måned og år for år, med varegrupperne og det, I har sparet på tilbud.</p></div>`;
    }
    if (s.selSpan !== s.span || s.sel == null || !B[s.sel]) {
      s.selSpan = s.span;
      s.sel = B.length - 1;
      while (s.sel > 0 && B[s.sel].spent === 0) s.sel -= 1;
    }
    const d = this._v3SpendDial(B);
    s.sp = { B, ...d };
    const x = B[s.sel];
    const gTot = {};
    for (const b of B) for (const [g, v] of Object.entries(b.groups)) gTot[g] = (gTot[g] || 0) + v;
    const classified = V3.GROUPS.reduce((a, g) => a + (gTot[g.k] || 0), 0);
    const total = B.reduce((a, b) => a + b.spent, 0), savedT = B.reduce((a, b) => a + b.saved, 0);
    const live = B.at(-1).spent === 0 ? B.slice(0, -1) : B;
    const third = s.span === "week" ? 8 : 4;
    const newer = live.slice(-third), older = live.slice(-third * 2, -third);
    const sumG = (L, g) => L.reduce((a, b) => a + (b.groups[g] || 0), 0);
    const word = { week: "uge", month: "måned", year: "år" }[s.span];
    const anim = this._v3Anim("spend", `${s.span}|${total}|${B.length}`);
    return `<div class="card spend${anim}" id="v3-spend">
      <div class="row between wrap"><div><div class="kicker">Forbrug &amp; besparelse</div><h2>${{ week: "Et år i uger", month: "Et år i måneder", year: "Fem år" }[s.span]}</h2>
        <p class="sub">${s.span === "year" ? "Hvert felt er et år." : `Én omgang er et år: hver stråle er ${s.span === "week" ? "en uge" : "en måned"}, med månederne på kanten.`} Farverne er varegrupperne, den mørke kant indad er sparet på tilbud. Træk eller tryk for at gå i tiden.</p></div>
        ${seg}</div>
      <div class="big-dial" id="v3-bd">
        <svg class="bd" viewBox="0 0 440 440" role="img" aria-label="REMA-forbrug pr. ${word}">${d.svg}</svg>
        <div class="bcenter" id="v3-bcenter">${this._v3Center(x)}</div>
        <div class="tip" id="v3-tip"></div>
      </div>
      <div class="stats4">
        <div class="stat"><span>▲ Højest</span><b class="num">${d.hi ? V3.krd(d.hi.spent) : "–"}</b><span>${d.hi ? esc(d.hi.label) : ""}</span></div>
        <div class="stat"><span>▼ Lavest</span><b class="num">${d.lo ? V3.krd(d.lo.spent) : "–"}</b><span>${d.lo ? esc(d.lo.label) : ""}</span></div>
        <div class="stat"><span>Snit</span><b class="num">${V3.krd(d.avg)}</b><span>pr. ${word}</span></div>
        <div class="stat"><span>Sparet</span><b class="num" style="color:var(--v3-good)">${V3.krd(savedT)}</b><span>${total + savedT ? Math.round((savedT / (total + savedT)) * 100) : 0} % rabat</span></div>
      </div>
      <div class="legend">${V3.ORDER.filter((g) => gTot[g] > 1).map((g) => `<button class="lg${s.solo === g ? " solo" : s.solo ? " off" : ""}" data-action="v3-solo" data-arg="${g}">${V3.dot(g)}${g === "none" ? "Uden varelinjer" : esc(V3.GNAME[g])}</button>`).join("")}</div>
      <div class="tiles">${V3.GROUPS.map(({ k, name }) => { const v = gTot[k] || 0; const n = sumG(newer, k), o = sumG(older, k); const tr = o > 0 ? Math.round(((n - o) / o) * 100) : null; return `<button class="tile${s.solo === k ? " solo" : ""}" data-action="v3-solo" data-arg="${k}"><span class="glow" style="background:var(--g-${k})"></span>${V3.art(k)}<b>${esc(name)}</b><span class="v num">${V3.krd(v)}</span>
        <span class="row between"><span class="s">${Math.round((v / (classified || 1)) * 100)} %</span>${tr != null && s.span !== "year" ? `<span class="trend ${tr > 0 ? "up" : "down"}">${tr > 0 ? "↑" : "↓"} ${Math.abs(tr)} %</span>` : ""}</span></button>`; }).join("")}</div>
      <p class="foot">${s.span === "year" ? "Procenterne er af de kroner, der har varelinjer." : `Pilene sammenligner de seneste ${third} ${s.span === "week" ? "uger" : "måneder"} med de ${third} før.`} Kun REMA 1000-kvitteringer.</p>
    </div>`;
  },

  _v3Select(i) {
    const s = this._v3s();
    if (i === s.sel || !s.sp?.B[i]) return;
    s.sel = i;
    const root = this.shadowRoot;
    root.querySelector("#v3-selpath")?.setAttribute("d", this._v3SelPath());
    const center = root.querySelector("#v3-bcenter");
    if (center) center.innerHTML = this._v3Center(s.sp.B[i]);
  },

  _v3ApplySolo() {
    const s = this._v3s();
    const root = this.shadowRoot;
    root.querySelectorAll("#v3-bd .gs").forEach((p) => p.classList.toggle("dim", !!s.solo && p.dataset.g !== s.solo));
    root.querySelectorAll('#v3-spend [data-action="v3-solo"]').forEach((el) => {
      el.classList.toggle("solo", s.solo === el.dataset.arg);
      el.classList.toggle("off", !!s.solo && s.solo !== el.dataset.arg && el.classList.contains("lg"));
    });
  },

  _v3BindDial() {
    const s = this._v3s();
    const el = this.shadowRoot.querySelector("#v3-bd");
    if (!el || el._v3bound || !s.sp) return;
    el._v3bound = true;
    this.shadowRoot.querySelector("#v3-selpath")?.setAttribute("d", this._v3SelPath());
    const tip = this.shadowRoot.querySelector("#v3-tip");
    const idx = (e) => { const r = el.getBoundingClientRect(); const x = e.clientX - r.left - r.width / 2, y = e.clientY - r.top - r.height / 2; const d = Math.hypot(x, y) / (r.width / 2); let a = (Math.atan2(x, -y) * 180) / Math.PI; if (a < 0) a += 360; return { i: Math.floor(a / s.sp.SEC) % s.sp.B.length, d }; };
    let drag = false;
    el.addEventListener("pointerdown", (e) => { const { i, d } = idx(e); if (d < 0.3) return; drag = true; el.setPointerCapture?.(e.pointerId); this._v3Select(i); });
    el.addEventListener("pointermove", (e) => {
      const { i, d } = idx(e);
      if (drag) { this._v3Select(i); return; }
      if (e.pointerType !== "mouse" || d < 0.45 || d > 1.02) { tip?.classList.remove("on"); return; }
      const x = s.sp.B[i];
      const r = el.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(x.label)}</b> · ${V3.krd(x.spent)}<br>${x.saved ? `sparet ${V3.krd(x.saved)} · ` : ""}${x.trips} ${x.trips === 1 ? "tur" : "ture"}`;
      tip.style.left = `${e.clientX - r.left}px`;
      tip.style.top = `${e.clientY - r.top}px`;
      tip.classList.add("on");
    });
    const stop = () => { drag = false; };
    el.addEventListener("pointerup", stop);
    el.addEventListener("pointercancel", stop);
    el.addEventListener("pointerleave", () => tip?.classList.remove("on"));
  },

  /* The bottom: everything saved, everything spent, five years. */
  _v3Story() {
    const Y = (this._state?.receipts?.overview?.year?.buckets || []).filter((y) => y.count).slice(-5);
    if (!Y.length || !this._isRema()) return "";
    const total = Y.reduce((a, y) => a + y.spent, 0), saved = Y.reduce((a, y) => a + y.saved, 0), trips = Y.reduce((a, y) => a + y.count, 0);
    const now = new Date();
    const last = Y.at(-1);
    const curYear = String(now.getFullYear()) === last.key;
    const dayOfYear = Math.round((now - new Date(now.getFullYear(), 0, 1)) / 864e5) + 1;
    const proj = curYear ? (last.spent * 365) / dayOfYear : last.spent;
    const max = Math.max(...Y.map((y) => y.spent), proj, 1);
    const W = 320, H = 170, bw = 40, gx = (W - 20) / Y.length;
    const yOf = (v) => H - 24 - (v / max) * (H - 54);
    const fill = Math.min(1, saved / Math.max(1, total * 0.25));
    const first = this._state.receipts.list?.at(-1)?.date;
    const since = first ? `siden ${V3.MONTHS_LONG[new Date(first).getMonth()]} ${new Date(first).getFullYear()}` : "";
    const k = (v) => (v >= 1000 ? `${V3.fmt(v / 1000, 0)}k` : V3.fmt(v));
    const anim = this._v3Anim("story", `${total}|${saved}`);
    return `<div class="story${anim}">
    <div class="card"><div class="kicker">Sparet på tilbud</div>
      <div class="row between" style="align-items:flex-end">
        <div><div class="huge good num" data-count="${saved}">${V3.krd(saved)}</div><p class="sub">${total + saved ? Math.round((saved / (total + saved)) * 100) : 0} % af hele bonen · i år ${V3.krd(last.saved)}</p></div>
        <svg viewBox="0 0 90 110" width="90" aria-hidden="true">
          <defs><clipPath id="v3jar"><path d="M18 30 h54 q6 0 6 8 v58 q0 10 -10 10 h-46 q-10 0 -10 -10 v-58 q0 -8 6 -8Z"/></clipPath></defs>
          <g clip-path="url(#v3jar)"><rect x="0" y="${(106 - 76 * fill).toFixed(0)}" width="90" height="110" fill="var(--v3-good)" opacity=".18"/>
            ${Array.from({ length: Math.max(3, Math.round(12 * fill)) }, (_, i) => `<ellipse class="coin" style="animation-delay:${i * 0.12}s" cx="${22 + (i % 4) * 15 + (Math.floor(i / 4) % 2) * 7}" cy="${98 - Math.floor(i / 4) * 9}" rx="9" ry="4" fill="#F2C14E" stroke="#C9972A" stroke-width="1.2"/>`).join("")}</g>
          <path d="M18 30 h54 q6 0 6 8 v58 q0 10 -10 10 h-46 q-10 0 -10 -10 v-58 q0 -8 6 -8Z" fill="none" stroke="var(--v3-soft)" stroke-width="2.4"/>
          <rect x="22" y="18" width="46" height="12" rx="4" fill="var(--v3-good)"/>
          <g class="drop"><ellipse cx="45" cy="8" rx="8" ry="3.6" fill="#F2C14E" stroke="#C9972A" stroke-width="1.2"/></g>
        </svg>
      </div></div>
    <div class="card"><div class="kicker">Brugt i REMA i alt</div>
      <div class="row between" style="align-items:flex-end">
        <div><div class="huge num" data-count="${total}">${V3.krd(total)}</div><p class="sub">${trips} ture ${since} · ${V3.krd(total / Math.max(1, trips))} pr. tur</p></div>
        <svg viewBox="0 0 80 110" width="80" aria-hidden="true">
          <path d="M14 8 h52 v86 l-6.5 -5 -6.5 5 -6.5 -5 -6.5 5 -6.5 -5 -6.5 5 -6.5 -5 -6.5 5Z" fill="var(--card-background-color)" stroke="var(--v3-soft)" stroke-width="2" stroke-linejoin="round"/>
          ${Array.from({ length: 7 }, (_, i) => `<path d="M22 ${20 + i * 9} h${18 + ((i * 7) % 14)} M56 ${20 + i * 9} h-6" stroke="var(--divider-color)" stroke-width="3" stroke-linecap="round"/>`).join("")}
          <path d="M22 84 h36" stroke="var(--v3-ink)" stroke-width="3.2" stroke-linecap="round"/>
        </svg>
      </div></div>
    <div class="card years"><div class="kicker">${Y.length} års udvikling</div>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Forbrug pr. år">
        <line x1="10" x2="${W - 10}" y1="${H - 24}" y2="${H - 24}" stroke="var(--divider-color)"/>
        ${Y.map((y, i) => { const x = 10 + gx * i + (gx - bw) / 2, cur = i === Y.length - 1 && curYear; return `
          ${cur ? `<rect x="${x.toFixed(1)}" y="${yOf(proj).toFixed(1)}" width="${bw}" height="${(yOf(y.spent) - yOf(proj)).toFixed(1)}" rx="4" fill="none" stroke="var(--rema-accent)" stroke-dasharray="3 3"/>` : ""}
          <rect class="col" style="animation-delay:${i * 0.1}s" x="${x.toFixed(1)}" y="${yOf(y.spent).toFixed(1)}" width="${bw}" height="${(H - 24 - yOf(y.spent)).toFixed(1)}" rx="4" fill="var(--rema-accent)" opacity="${cur ? 1 : (0.55 + i * 0.1).toFixed(2)}"/>
          <text x="${(x + bw / 2).toFixed(1)}" y="${(yOf(cur ? proj : y.spent) - 7).toFixed(1)}" text-anchor="middle" class="ylab">${k(y.spent)}${cur ? `→${k(proj)}` : ""}</text>
          <text x="${(x + bw / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle" class="yname">${y.key}</text>`; }).join("")}
      </svg>
      <p class="sub">${curYear ? `${last.key} til nu ${V3.krd(last.spent)}; stiplet, hvor året ender i samme tempo.` : ""}</p></div></div>`;
  },

  /* The receipt, as REMA prints it: each line's price is one piece's. */
  _v3OpenBon(id) {
    this._modal = { kind: "v3-bon", id, loading: true, receipt: null, error: null };
    this._renderModal();
    this._ws("middagsro/receipt", { receipt_id: id })
      .then((r) => { if (this._modal?.kind === "v3-bon" && this._modal.id === id) { this._modal.receipt = r; this._modal.loading = false; this._renderModal(); } })
      .catch((err) => { if (this._modal?.kind === "v3-bon" && this._modal.id === id) { this._modal.loading = false; this._modal.error = err?.message || "Kvitteringen kunne ikke hentes."; this._renderModal(); } });
  },

  _v3BonModal(m) {
    const close = `<button class="x" data-action="modal-close" aria-label="Luk">×</button>`;
    let inner;
    if (m.loading) inner = `${close}<p class="r-dim" style="justify-content:center;padding:30px 0"><span class="spinner small"></span>&nbsp;Henter kvitteringen …</p>`;
    else if (m.error || !m.receipt) inner = `${close}<p>${esc(m.error || "Kvitteringen kunne ikke hentes.")}</p>`;
    else inner = close + this._v3Paper(m.receipt);
    return `<div class="scrim" data-action="modal-close"></div><div class="v3 v3-sheet"><div class="paper" role="dialog" aria-modal="true" aria-label="Kvittering">${inner}<div class="r-zig"></div></div></div>`;
  },

  _v3Paper(r) {
    const n2 = (v) => V3.fmt(v, 2);
    const t = r.date ? new Date(r.date) : null;
    const lines = r.items || [];
    const g = {};
    let pieces = 0;
    for (const l of lines) {
      const q = l.quantity || 1;
      pieces += q;
      if (l.price != null && l.price > 0) { const k = V3.groupOf(l.name); g[k] = (g[k] || 0) + q * l.price; }
    }
    const sorted = V3.ORDER.filter((k) => g[k]).sort((a, b) => g[b] - g[a]);
    const st = r.store || {};
    const pay = r.card_type || (r.payment_source ? V3.cap(String(r.payment_source)) : "Kort");
    return `<div class="r-head"><div class="r-logo">REMA 1000</div><div>${esc(st.name || "")}</div>${st.address ? `<div class="r-dim">${esc(st.address)}${st.city ? `, ${esc(st.zip || "")} ${esc(st.city)}` : ""}</div>` : ""}
        ${t ? `<div class="r-dim">${V3.DAYS_LONG[t.getDay()]} ${t.getDate()}. ${V3.MONTHS_LONG[t.getMonth()]} ${t.getFullYear()} · kl. ${String(t.getHours()).padStart(2, "0")}.${String(t.getMinutes()).padStart(2, "0")}</div>` : ""}
        ${r.display_id ? `<div class="r-dim">Bon ${esc(r.display_id)}</div>` : ""}</div>
      ${sorted.length ? `<div class="r-groups">${sorted.map((k) => `<i style="flex-grow:${g[k].toFixed(2)};background:var(--g-${k})" title="${esc(V3.GNAME[k])}: ${esc(V3.krd(g[k], 2))}"></i>`).join("")}</div>
      <div class="r-legend">${sorted.slice(0, 4).map((k) => `<span><i style="background:var(--g-${k})"></i>${esc(V3.GNAME[k].split(" ")[0])} ${V3.fmt(g[k])}</span>`).join("")}</div>` : ""}
      <div class="r-lines">${lines.map((l) => { const q = l.quantity || 1, tot = l.price != null ? q * l.price : null, dis = (l.discount || 0) * q; return `<div class="r-line"><span class="r-dot" style="background:var(--g-${V3.groupOf(l.name)})"></span><span class="r-n">${esc(V3.clean(l.name))}${q > 1 && l.price != null ? `<small>${q} × ${n2(l.price)}</small>` : ""}</span><span class="r-p">${tot != null ? n2(tot) : ""}</span></div>${dis ? `<div class="r-line r-off"><span></span><span class="r-n">Rabat</span><span class="r-p">−${n2(dis)}</span></div>` : ""}${l.deposit ? `<div class="r-line r-dimline"><span></span><span class="r-n">Pant</span><span class="r-p">${n2(l.deposit * q)}</span></div>` : ""}`; }).join("")}</div>
      <div class="r-sum">${r.gross != null ? `<div><span>Før rabat</span><span>${n2(r.gross)}</span></div>` : ""}${r.total_discount ? `<div class="r-off"><span>Rabat i alt</span><span>−${n2(r.total_discount)}</span></div>` : ""}<div class="r-total"><span>I alt</span><span>${n2(r.total)}</span></div>${r.total_vat != null ? `<div class="r-dim"><span>Heraf moms</span><span>${n2(r.total_vat)}</span></div>` : ""}<div class="r-dim"><span>Betalt med ${esc(pay)}${r.masked_pan ? ` ${esc(r.masked_pan)}` : ""}</span><span>${pieces} varer</span></div></div>`;
  },
});

/* Indkøb: the list in the other webshops. Varer: the top 20. Sundhed: the basket's plate. */
Object.assign(V3_METHODS, {
  _v3Fees(shop) {
    const f = this._v3s().fees;
    if (shop.store === "nemlig") {
      const zones = Math.max(1, Math.min(4, Number(f.zones) || 2));
      const fee = Number(f.nemlig) + Math.min(23.8, zones * 5.95);
      return { fee, text: `${V3.fmt(f.nemlig)} kr. levering + ${zones} × 5,95 kr. pakkegebyr`, sub: "Levering til døren" };
    }
    if (f.bilka === "pickup") return { fee: 58, text: "19 kr. levering + 39 kr. pakkeservice", sub: shop.pickup ? `Pickup · ${shop.pickup}` : "Pickup i pakkeboks" };
    return { fee: 0, text: "Pakkeservicegebyr vises i kurven", sub: shop.pickup ? `Afhent i ${shop.pickup}` : "Afhent i Bilka" };
  },

  _v3CompareKey(plan) {
    return `${plan.id}|${plan.shopping.length}|${plan.total}`;
  },

  _v3LoadCompare(plan) {
    const s = this._v3s();
    const key = this._v3CompareKey(plan);
    if (s.cmp[key] || s.cmpLoading === key) return;
    s.cmpLoading = key;
    this._ws("middagsro/baskets/compare", { plan_id: plan.id })
      .then((data) => { s.cmp[key] = { data }; })
      .catch((err) => { s.cmp[key] = { error: err?.message || String(err) }; })
      .finally(() => { if (s.cmpLoading === key) s.cmpLoading = null; if (this._tab === "shopping") this._render(); });
  },

  _v3Compare() {
    const plan = this._plan;
    if (!plan || plan.kind === "freezer") return "";
    const stores = this._state?.stores || [];
    const s = this._v3s();
    const info = `<div class="card compare v3-cmp-info"><div class="kicker">Hvad koster kurven andre steder?</div><h2>Sammenlign med Nemlig.com og Bilka ToGo</h2>
      <p class="sub">Tilføj Nemlig.com eller Bilka ToGo som butik i Middagsro (Indstillinger › Enheder og tjenester › Middagsro › Tilføj post). Så søges ugens liste dér med jeres egne priser, og varerne kan lægges i den butiks kurv – ${esc(this._chainName(this._storeId()))} bliver ved med at være madplanens butik.</p></div>`;
    if (stores.length < 2) return info;
    const key = this._v3CompareKey(plan);
    const got = s.cmp[key];
    if (!got) {
      this._v3LoadCompare(plan);
      return `<div class="card compare"><div class="kicker">Hvad koster kurven andre steder?</div><p class="sub"><span class="spinner small"></span> Søger listen i de andre butikker …</p></div>`;
    }
    if (got.error) return `<div class="card compare"><div class="kicker">Hvad koster kurven andre steder?</div><div class="banner error">${esc(got.error)}</div><button class="btn" data-action="v3-cmp-retry">Prøv igen</button></div>`;
    const { own, shops } = got.data;
    if (!shops.length) return info;
    const opts = [
      { key: "own", name: own.name, sub: "Madplanens butik", goods: own.total, fee: 0, feeText: "Ingen gebyrer", color: "var(--g-mejeri)", count: own.priced, of: own.count },
      ...shops.map((x, i) => { const f = this._v3Fees(x); return { key: x.entry_id, shop: x, name: x.name, sub: f.sub, goods: x.total, fee: x.items.length ? f.fee : 0, feeText: f.text, color: ["var(--g-kolonial)", "var(--g-drikke)"][i % 2], count: x.items.length, of: own.count }; }),
    ];
    const max = Math.max(...opts.map((o) => o.goods + o.fee), 1);
    const full = opts.filter((o) => (o.key === "own" || o.count === o.of) && o.goods > 0);
    const best = (full.length ? full : opts).reduce((a, o) => (o.goods + o.fee < a.goods + a.fee ? o : a));
    const f = s.fees;
    const anim = this._v3Anim("cmp", `${key}|${f.bilka}|${f.nemlig}|${f.zones}`);
    return `<div class="card compare${anim}">
      <div class="row between wrap"><div><div class="kicker">Hvad koster kurven andre steder?</div><h2>${esc(opts.map((o) => o.name).join(", ").replace(/, ([^,]*)$/, " og $1"))}</h2>
        <p class="sub">De samme ${own.count} varer, søgt med jeres egne priser – med levering og gebyrer. Middagsro lægger kun varerne i kurven; I vælger selv tid og bestiller.</p></div>
        <span class="pill good">Billigst: ${esc(best.name)}</span></div>
      <div class="race">${opts.map((o, i) => { const tot = o.goods + o.fee, diff = tot - opts[0].goods; return `<div class="lane" style="animation-delay:${i * 0.1}s">
        <div class="ln-head"><span class="mono big" style="background:${o.color}">${esc(o.name[0])}</span><div><b>${esc(o.name)}</b><small>${esc(o.sub)}</small></div><span class="ln-tot num">${V3.krd(tot, 2)}</span></div>
        <div class="ln-bar"><i class="goods" style="width:${((o.goods / max) * 100).toFixed(1)}%;background:${o.color}"></i><i class="fee" style="width:${((o.fee / max) * 100).toFixed(1)}%"></i></div>
        <div class="ln-foot"><span>Varer ${V3.krd(o.goods, 2)}${o.count < o.of ? ` · ${o.count} af ${o.of} fundet` : ""}</span><span>${esc(o.feeText)}</span>${o.key === "own" ? "" : `<span class="${diff > 0 ? "up" : "down"}">${diff > 0 ? "+" : "−"}${V3.krd(Math.abs(diff), 2)} mod ${esc(opts[0].name)}</span>`}</div>
        ${o.key === "own" ? "" : o.shop.basket ? `<button class="btn ${o === best ? "primary" : ""} xfer" data-action="v3-xfer" data-arg="${esc(o.key)}" ${o.count ? "" : "disabled"}>${V3.ic("truck", 16)} Læg i kurven hos ${esc(o.name)}</button>` : `<span class="sub">Log ind på ${esc(o.name)} i Middagsro for at lægge varerne i kurven.</span>`}</div>`; }).join("")}</div>
      <details class="fees"${s.feesOpen ? " open" : ""} data-fold="v3fees"><summary>Gebyrer og levering</summary>
        <div class="fee-grid">
          ${shops.some((x) => x.store !== "nemlig") ? `<label>Bilka ToGo <select data-bind="v3fee" data-field="bilka"><option value="pickup" ${f.bilka === "pickup" ? "selected" : ""}>Pickup i pakkeboks (19 + 39 kr.)</option><option value="store" ${f.bilka === "store" ? "selected" : ""}>Afhent i Bilka (gebyr i kurven)</option></select></label>` : ""}
          ${shops.some((x) => x.store === "nemlig") ? `<label>Nemlig.com levering <input type="range" min="0" max="69" step="1" value="${f.nemlig}" data-bind="v3fee" data-field="nemlig"><span class="num" id="v3-nfee">${f.nemlig} kr.</span></label>
          <label>Nemlig.com pakkegebyr <select data-bind="v3fee" data-field="zones">${[1, 2, 3, 4].map((z) => `<option value="${z}" ${Number(f.zones) === z ? "selected" : ""}>${z} ${z === 1 ? "zone" : "zoner"} · ${V3.fmt(Math.min(23.8, z * 5.95), 2)} kr.</option>`).join("")}</select></label>` : ""}
        </div>
        <p class="foot">Nemlig.com tager 0–69 kr. for levering alt efter tidspunkt og postnummer og 5,95 kr. i pakkegebyr pr. temperaturzone (højst 23,80 kr.). Bilka ToGo-pickup koster 19 kr. i levering og 39 kr. i pakkeservicegebyr; ved afhentning i varehuset og hjemmelevering står gebyret i kurven. Begge har et minimumskøb.</p>
      </details></div>`;
  },

  _v3OpenTransfer(entryId) {
    const plan = this._plan;
    const got = plan && this._v3s().cmp[this._v3CompareKey(plan)];
    const shop = got?.data?.shops?.find((x) => x.entry_id === entryId);
    if (!shop) return;
    this._modal = { kind: "v3-xfer", shop, busy: false, result: null, error: null };
    this._renderModal();
  },

  _v3XferModal(m) {
    const x = m.shop;
    const url = x.store === "nemlig" ? "https://www.nemlig.com" : "https://www.bilkatogo.dk";
    const done = m.result;
    const failed = new Set(done?.failed || []);
    return `<div class="scrim" data-action="modal-close"></div><div class="v3 v3-sheet"><div class="xsheet" role="dialog" aria-modal="true" aria-label="Læg i kurven hos ${esc(x.name)}">
      <button class="x" data-action="modal-close" aria-label="Luk">×</button>
      <div class="kicker">Læg i kurven</div><h2>Hos ${esc(x.name)}</h2>
      <p class="sub">Middagsro lægger de fundne varer i jeres kurv hos ${esc(x.name)} – mindst så mange, som listen skal bruge. Ingen ordre bliver gennemført; det gør I selv hos butikken.</p>
      <div class="xprog"><i style="width:${done ? 100 : m.busy ? 65 : 0}%"></i></div>
      <div class="xlist">${x.items.map((it, i) => `<div class="xl" style="animation-delay:${(0.05 + i * 0.04).toFixed(2)}s"><span class="xdot ${done && failed.has(it.product.id) ? "miss" : "ok"}">${done && failed.has(it.product.id) ? "!" : "✓"}</span><span>${esc(it.name)}<small> · ${esc(it.product.name)}${it.packages > 1 ? ` · ${it.packages} stk.` : ""}</small></span><small>${V3.fmt(it.cost, 2)}</small></div>`).join("")}
        ${x.missing.map((n) => `<div class="xl"><span class="xdot miss">?</span><span>${esc(n)}</span><small>Ikke fundet – vælg selv</small></div>`).join("")}</div>
      ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
      ${done
        ? `<div class="xdone on"><b>${done.added + done.already} af ${x.items.length} varer ligger i kurven${done.already ? ` (${done.already} lå der i forvejen)` : ""}</b>${done.failed.length ? `<span class="sub">${done.failed.length} kom ikke med – prøv igen, eller læg dem selv i kurven.</span>` : ""}<a class="btn primary big" href="${url}" target="_blank" rel="noopener noreferrer">Åbn kurven hos ${esc(x.name)} ›</a></div>`
        : `<div class="row wrap dlg-foot"><button class="btn" data-action="modal-close" ${m.busy ? "disabled" : ""}>Annullér</button><span class="spacer"></span><button class="btn primary" data-action="v3-xfer-go" ${m.busy || !x.items.length ? "disabled" : ""}>${m.busy ? '<span class="spinner small"></span> Lægger i kurven …' : `${V3.ic("truck", 16)} Læg ${x.items.length} varer i kurven`}</button></div>`}
    </div></div>`;
  },

  _v3Transfer() {
    const m = this._modal;
    if (m?.kind !== "v3-xfer" || m.busy) return;
    m.busy = true;
    m.error = null;
    this._renderModal();
    const items = m.shop.items.map((it) => ({ product_id: it.product.id, packages: it.packages }));
    this._ws("middagsro/baskets/transfer", { target_entry_id: m.shop.entry_id, items })
      .then((result) => { m.result = result; })
      .catch((err) => { m.error = err?.message || String(err); })
      .finally(() => { m.busy = false; if (this._modal === m) this._renderModal(); });
  },

  /* Varer: the top 20, with REMA's own pictures. */
  _v3TopItems() {
    const items = this._state?.receipts?.items || [];
    if (items.length < 3) return "";
    const s = this._v3s();
    const L = [...items].sort((a, b) => (s.sort === "kr" ? (b.total_spent || 0) - (a.total_spent || 0) : b.count - a.count)).slice(0, 20);
    this._v3LoadImages(L.map((p) => p.name));
    const img = (p) => V3.pic(s.img[p.name], p.group || V3.groupOf(p.name));
    const pod = [L[1], L[0], L[2]];
    const receipts = this._state.receipts.count || 0;
    const card = (p, i) => {
      const lo = p.min_price ?? p.last_price ?? 0, hi = p.max_price ?? lo, last = p.last_price ?? lo;
      const pos = hi > lo ? ((last - lo) / (hi - lo)) * 100 : 50;
      return `<div class="vprod" style="animation-delay:${(i * 0.03).toFixed(2)}s"><div class="ph">${img(p)}<span class="rank">${i + 1}</span><span class="gdot" title="${esc(V3.GNAME[p.group] || "")}">${V3.art(p.group || "hjem", "").replace("<svg", '<svg width="26" height="26"')}</span>${p.frequent ? '<span class="vbadge">Fast vare</span>' : ""}</div>
      <b>${esc(V3.clean(p.name))}</b><div class="meta"><span>${p.count}× købt</span><strong>${V3.krd(p.total_spent || 0)}</strong></div>
      <div class="range" title="Prisspænd pr. stk."><i style="left:${pos.toFixed(0)}%"></i></div><div class="range-lab"><span>${V3.fmt(lo, 2)}</span><span>senest ${V3.fmt(last, 2)}</span><span>${V3.fmt(hi, 2)}</span></div></div>`;
    };
    const anim = this._v3Anim("items", `${s.sort}|${items.length}|${Object.keys(s.img).length}`);
    return `<div class="v3${anim}"><div class="card">
      <div class="row between wrap"><div><div class="kicker">Varer</div><h2>Jeres top 20</h2><p class="sub">Af ${V3.fmt(items.length)} forskellige varer på ${V3.fmt(receipts)} kvitteringer.${this._isRema() ? " Billederne er REMA's egne." : ""}</p></div>
        <div class="seg">${[["kr", "Mest brugt"], ["c", "Oftest købt"]].map(([k, t]) => `<button class="${s.sort === k ? "on" : ""}" data-action="v3-sort" data-arg="${k}">${t}</button>`).join("")}</div></div>
      <div class="podium">${pod.filter(Boolean).map((p) => `<div class="pod"><div class="ph">${img(p)}</div><b>${esc(V3.clean(p.name))}</b><small>${s.sort === "kr" ? V3.krd(p.total_spent || 0) : `${p.count}× købt`}</small><div class="pstep">${L.indexOf(p) + 1}</div></div>`).join("")}</div>
    </div>
    ${L.length > 3 ? `<div class="card"><div class="kicker">Resten af top 20</div><div class="shelf">${L.slice(3).map((p, i) => card(p, i + 3)).join("")}</div>
      <p class="foot">Prisspændet er pr. stk. på tværs af alle køb: billigst, senest og dyrest.</p></div>` : ""}</div>`;
  },

  _v3LoadImages(names) {
    const s = this._v3s();
    if (!this._isRema()) return;
    const want = names.filter((n) => !(n in s.img) && !s.imgAsked.has(n));
    if (!want.length) return;
    want.forEach((n) => s.imgAsked.add(n));
    this._ws("middagsro/items/images", { names: want.slice(0, 40) })
      .then((found) => { Object.assign(s.img, found || {}); if (this._tab === "history") this._render(); })
      .catch(() => { want.forEach((n) => { if (!(n in s.img)) s.img[n] = null; }); });
  },

  /* Sundhed: what the receipts say you bought, as a plate. */
  _v3Plate() {
    const ov = this._state?.receipts?.overview;
    const weeks = (ov?.week?.buckets || []).slice(-8);
    const food = ["frugt", "kod", "mejeri", "brod", "kolonial", "snacks"];
    const g = Object.fromEntries(food.map((f) => [f, 0]));
    for (const w of weeks) for (const f of food) g[f] += w.groups?.[f] || 0;
    const tot = food.reduce((a, f) => a + g[f], 0);
    if (!this._isRema() || tot < 50) return "";
    const C = 150;
    let a = 0;
    let plate = `<circle cx="${C}" cy="${C}" r="140" fill="var(--rema-subtle)"/><circle cx="${C}" cy="${C}" r="128" fill="var(--card-background-color)" stroke="var(--divider-color)"/>`;
    const order = [...food].sort((x, y) => g[y] - g[x]).filter((f) => g[f] > 0);
    for (const f of order) {
      const sw = (g[f] / tot) * 360;
      plate += `<path class="petal" style="transform-origin:150px 150px" d="${V3.sector(C, C, 36, 118, a + 0.8, a + sw - 0.8)}" fill="var(--g-${f})" opacity=".9"/>`;
      const [x, y] = V3.P(C, C, 80, a + sw / 2);
      if (sw > 26) plate += `<g transform="translate(${(x - 17).toFixed(1)} ${(y - 17).toFixed(1)}) scale(.53)"><circle cx="32" cy="32" r="30" fill="var(--card-background-color)" opacity=".92"/>${V3.ART[f](f)}</g>`;
      a += sw;
    }
    plate += `<circle cx="${C}" cy="${C}" r="34" fill="var(--card-background-color)"/><text x="${C}" y="${C - 4}" text-anchor="middle" class="pl-big">${Math.round((g.frugt / tot) * 100)} %</text><text x="${C}" y="${C + 14}" text-anchor="middle" class="pl-small">GRØNT</text>`;
    const months = (ov?.month?.buckets || []).filter((b) => food.some((f) => b.groups?.[f]));
    let chart = "";
    if (months.length >= 2) {
      const shares = months.map((b) => { const t = food.reduce((p, f) => p + (b.groups[f] || 0), 0) || 1; return [b.key, ((b.groups.frugt || 0) / t) * 100, ((b.groups.snacks || 0) / t) * 100]; });
      const top = Math.max(30, Math.ceil(Math.max(...shares.map((s) => Math.max(s[1], s[2]))) / 10) * 10);
      const W = this._v3Phone() ? 380 : 960, H = this._v3Phone() ? 200 : 210;
      const x = (i) => 36 + (i / (shares.length - 1)) * (W - 130), y = (v) => H - 26 - (v / top) * (H - 46);
      const line = (j) => shares.map((s, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(s[j]).toFixed(1)}`).join("");
      const ticks = Array.from({ length: top / 10 + 1 }, (_, i) => i * 10);
      chart = `<div style="margin-top:16px"><div class="row between wrap"><b>Grønt mod søde sager, måned for måned</b><span class="sub" style="margin:0">andel af madkronerne</span></div>
        <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;margin-top:6px" role="img" aria-label="Andel frugt og grønt og andel snacks pr. måned">
          ${ticks.map((v) => `<line x1="36" x2="${W - 94}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--divider-color)"/><text x="28" y="${(y(v) + 3).toFixed(1)}" text-anchor="end" class="ax">${v}</text>`).join("")}
          <path d="${line(1)}" fill="none" stroke="var(--g-frugt)" stroke-width="2"/><path d="${line(2)}" fill="none" stroke="var(--g-snacks)" stroke-width="2"/>
          ${shares.map((s, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(s[1]).toFixed(1)}" r="4" fill="var(--g-frugt)" stroke="var(--card-background-color)" stroke-width="2"><title>${esc(s[0])}: grønt ${Math.round(s[1])} %</title></circle><circle cx="${x(i).toFixed(1)}" cy="${y(s[2]).toFixed(1)}" r="4" fill="var(--g-snacks)" stroke="var(--card-background-color)" stroke-width="2"><title>${esc(s[0])}: søde ${Math.round(s[2])} %</title></circle><text x="${x(i).toFixed(1)}" y="${H - 6}" text-anchor="middle" class="ax">${V3.MONTHS[Number(s[0].slice(5)) - 1]}</text>`).join("")}
          <text x="${(x(shares.length - 1) + 8).toFixed(1)}" y="${(y(shares.at(-1)[1]) + 3).toFixed(1)}" class="axv">Grønt ${Math.round(shares.at(-1)[1])}</text>
          <text x="${(x(shares.length - 1) + 8).toFixed(1)}" y="${(y(shares.at(-1)[2]) + 3).toFixed(1)}" class="axv">Søde ${Math.round(shares.at(-1)[2])}</text>
        </svg></div>`;
    }
    const anim = this._v3Anim("plate", `${tot}`);
    return `<div class="v3${anim}"><div class="card"><div class="kicker">Det, I faktisk købte · seneste 8 uger</div><h2>Kurvens tallerken</h2>
      <p class="sub">Fra kvitteringerne, ikke madplanen: madkronerne fordelt på varegrupper (drikke og non-food er ikke med).</p>
      <div class="plate-wrap" style="margin-top:10px">
        <div class="plate"><svg viewBox="0 0 300 300" role="img" aria-label="Madkronerne fordelt på varegrupper">${plate}</svg></div>
        <div><div class="share">${order.map((f) => `<div class="sh">${V3.art(f, "")}<div><b>${esc(V3.GNAME[f])}</b><div class="bar"><i style="width:${((g[f] / g[order[0]]) * 100).toFixed(1)}%;background:var(--g-${f})"></i></div></div><span class="p">${Math.round((g[f] / tot) * 100)} %</span></div>`).join("")}</div>
          <p class="sub" style="margin-top:12px">Frugt og grønt fik ${V3.krd(g.frugt)} – snacks og slik ${V3.krd(g.snacks)}.</p></div>
      </div>${chart}</div></div>`;
  },

  /* ------------------------------------------------------------------ after a redraw */
  _v3Pics(root = this.shadowRoot) {
    root.querySelectorAll("img[data-fb]").forEach((img) => {
      if (img._v3fb) return;
      img._v3fb = true;
      const swap = () => { if (img.isConnected) img.outerHTML = V3.art(img.dataset.fb, ""); };
      if (img.complete && img.naturalWidth === 0 && img.src) swap();
      else img.addEventListener("error", swap, { once: true });
    });
  },

  _v3After() {
    const root = this.shadowRoot;
    this._v3Pics(root);
    this._v3BindDial();
    this._v3BindDrag();
    root.querySelectorAll("#content [data-count]").forEach((el) => {
      if (el.closest(".still")) return;
      const to = Number(el.dataset.count);
      el.dataset.v = 0;
      el.removeAttribute("data-count");
      V3.countUp(el, to, el.classList.contains("huge") ? 1400 : 800);
    });
    if (!this._v3Keys) {
      this._v3Keys = true;
      root.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter") return;
        const el = ev.target;
        if (el?.dataset?.v3book) { ev.preventDefault(); this._v3Book(el.dataset.v3book); }
        else if (el?.dataset?.bind === "v3q") { ev.preventDefault(); this._v3QuickAdd(el); }
      });
    }
  },

  _v3QuickAdd(from) {
    const s = this._v3s();
    const q = s.q.trim();
    if (!q) return;
    const hit = s.hitsQ === q && s.hits[0];
    if (hit) return this._v3QuickPick(0, from);
    this._v3QuickText(from);
  },

  _v3QuickPick(i, from) {
    const s = this._v3s();
    const p = s.hits[i];
    if (!p) return;
    this._v3Fly(from, V3.clean(p.name).split(" ")[0]);
    s.q = ""; s.hits = []; s.hitsQ = "";
    this._addToRemaList(p.id, p.name);
  },

  _v3QuickText(from) {
    const s = this._v3s();
    const name = s.q.trim();
    if (!name || !this._plan) return;
    this._v3Fly(from, name.split(" ")[0]);
    s.q = ""; s.hits = []; s.hitsQ = "";
    this._editPlan(() => this._ws("middagsro/plan/add", { plan_id: this._plan.id, name, part: "main" }), `${name} er tilføjet til indkøbslisten.`);
  },

  /* ------------------------------------------------------------------ events */
  _v3Click(action, arg, el) {
    const s = this._v3s();
    const handlers = {
      "v3-move": () => {
        const [planId, date, direction] = String(arg).split("|");
        this._modal = null;
        this._renderModal();
        this._run(() => this._ws("middagsro/day/move", { plan_id: planId, date, direction }), direction === "up" ? "Retten er flyttet en dag tidligere." : "Retten er flyttet en dag senere.");
      },
      "v3-pw": () => { s.pw = Number(arg) || 0; s.pwPlan = this._plan?.id; this._render(); },
      tab: () => {
        if (arg === "recipes" && this._tab !== "recipes") this._recipesSub = "collection";
        // The tab you are on, tapped again: back to the top.
        if (arg === this._tab) requestAnimationFrame(() => this.shadowRoot.querySelector("#top")?.scrollIntoView({ block: "start", behavior: "smooth" }));
        return false;
      },
      "v3-hw": () => { s.hw = Number(arg) || 0; this._render(); },
      "v3-book": () => this._v3Book(arg),
      "v3-add": () => {
        s.amt = V3.fmt(this._v3Amount(s.amt) + Number(arg), 0).replace(/\./g, "");
        const input = el.closest(".glass, .kbook")?.querySelector("[data-v3book]");
        if (input) { input.value = s.amt; input.focus(); }
      },
      "v3-week": () => { s.week = Number(arg); s.day = null; this._render(); },
      "v3-day": () => this._v3PickDay(Number(arg)),
      "v3-bon": () => this._v3OpenBon(arg),
      "v3-span": () => { if (s.span !== arg) { s.span = arg; s.sel = null; this._render(); } },
      "v3-solo": () => { s.solo = s.solo === arg ? null : arg; this._v3ApplySolo(); },
      "v3-sort": () => { s.sort = arg; this._render(); },
      "v3-qadd": () => this._v3QuickAdd(el),
      "v3-qpick": () => this._v3QuickPick(Number(arg), el),
      "v3-qtext": () => this._v3QuickText(el),
      "v3-qfill": () => {
        s.q = arg;
        const input = this.shadowRoot.querySelector('[data-bind="v3q"]');
        if (input) { input.value = arg; input.focus(); }
        this._v3Search();
      },
      "v3-xfer": () => this._v3OpenTransfer(arg),
      "v3-xfer-go": () => this._v3Transfer(),
      "v3-cmp-retry": () => { s.cmp = {}; this._render(); },
    };
    const fn = handlers[action];
    if (!fn) return false;
    return fn() !== false;
  },

  _v3Input(el, ev) {
    const ds = el.dataset;
    const s = this._v3s();
    if (ds.bind === "v3amt") { s.amt = el.value; return true; }
    if (ds.bind === "v3q") {
      if (ev.type !== "input") return true;
      s.q = el.value;
      this._v3RenderQuick();
      this._soon("v3q", () => this._v3Search(), 260);
      return true;
    }
    if (ds.bind === "v3fee") {
      const v = ds.field === "bilka" ? el.value : Number(el.value);
      s.fees[ds.field] = v;
      try { localStorage.setItem(V3_FEES, JSON.stringify(s.fees)); } catch { /* not kept */ }
      if (ds.field === "nemlig" && ev.type === "input") {
        const out = this.shadowRoot.querySelector("#v3-nfee");
        if (out) out.textContent = `${v} kr.`;
        return true;
      }
      s.feesOpen = true;
      this._render();
      return true;
    }
    return false;
  },
});

/* Madplan, opskrifter, favoritter, spisekammer and the rest, drawn as in the prototype. */
const V3_ICONS = {
  home: '<path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4.5v-5h-5v5H5a1 1 0 0 1-1-1Z"/>',
  plan: '<rect x="4" y="5" width="16" height="15" rx="2.5"/><path d="M4 9.5h16M9 3.5v3M15 3.5v3M8 13h3M8 16.5h6"/>',
  recipes: '<path d="M6 4h9a3 3 0 0 1 3 3v13H8a2 2 0 0 1-2-2Z"/><path d="M6 18a2 2 0 0 1 2-2h10M10 8h5M10 11h4"/>',
  shopping: '<path d="M5 8h14l-1.4 10.2a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8Z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/>',
  favorites: '<path d="M12 19.5s-7-4.3-7-9.6A4 4 0 0 1 12 7.3a4 4 0 0 1 7 2.6c0 5.3-7 9.6-7 9.6Z"/>',
  budget: '<circle cx="12" cy="12" r="8"/><path d="M12 4v8l5.5 5.5"/>',
  health: '<path d="M12 20s-6.5-3.8-6.5-9A3.5 3.5 0 0 1 12 8.8 3.5 3.5 0 0 1 18.5 11c0 5.2-6.5 9-6.5 9Z"/><path d="M8 12.5h2.2l1.2-2 1.6 4 1.2-2H16"/>',
  inventory: '<rect x="5" y="3.5" width="14" height="17" rx="2.5"/><path d="M5 10h14M8.5 6.8v1M8.5 13v2.5"/>',
  history: '<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4.5v3.2h3.2M12 8v4.2l2.8 1.8"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4 18 18M6 18l1.6-1.6M16.4 7.6 18 6"/>',
};
const V3_TAB_ICON = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${V3_ICONS[k] || ""}</svg>`;
const V3_KIND_HINT = { ai: "AI'en finder en ret", skip: "Ingen aftensmad", rest: "Rester af dagen før", rye: "Ingen madlavning", veg: "AI'en finder en vegetarret" };

Object.assign(V3_METHODS, {
  /* ------------------------------------------------------------------ Madplan */
  _v3AllWeeks() {
    const plan = this._plan;
    const tl = this._timeline();
    let entries;
    if (tl) entries = tl.filter((e) => e.day || e.skipped);
    else {
      entries = [
        ...(plan.days || []).map((d) => ({ date: d.date, day: d, plan, skipped: false })),
        ...(plan.skipped || []).map((date) => ({ date, day: null, plan, skipped: true })),
      ].sort((a, b) => a.date.localeCompare(b.date));
      entries.forEach((e) => (e.week = plan.week || V3.weekNo(V3.sundayOf(e.date))));
    }
    const weeks = [];
    for (const e of entries) {
      let w = weeks.find((x) => x.week === e.week);
      if (!w) weeks.push((w = { week: e.week, entries: [] }));
      w.entries.push(e);
    }
    return { weeks, timeline: !!tl };
  },

  _v3RateRow(plan, day) {
    const { cooked, recipe } = this._recipeForDay(plan, day);
    if (!cooked?.dish || cooked.type === "tom" || cooked.type === "egen") return "";
    const on = { like: recipe?.rating === "like", dislike: recipe?.rating === "dislike", favorite: !!recipe?.favorite };
    const glyph = { like: "👍", dislike: "👎", favorite: "♥" };
    return ["like", "dislike", "favorite"].map((a) => `<button class="vrate${on[a] ? " on" : ""}" data-action="rate-day" data-arg="${esc(plan.id)}|${esc(day.date)}|${a}" aria-label="${RATE_LABELS[a]}: ${esc(cooked.dish)}" aria-pressed="${on[a]}" ${this._busy ? "disabled" : ""}>${glyph[a]}</button>`).join("");
  },

  _v3Prow(e, i, drag = false) {
    const today = localToday();
    const d = new Date(`${e.date}T12:00:00`), now = e.date === today, past = e.date < today;
    const day = e.day;
    const arg = `${esc(e.plan.id)}|${esc(e.date)}`;
    if (e.skipped || !day) {
      return `<div class="prow skipped${past ? " past" : ""}" style="animation-delay:${(i * 0.04).toFixed(2)}s">
        <button class="pr-open" data-action="day-menu-skipped" data-arg="${arg}"><span class="pr-date"><span>${V3.DAYS[d.getDay()]}</span><b>${d.getDate()}</b><small>${V3.MONTHS[d.getMonth()]}</small></span>
        ${V3.dishArt("", "pr-art")}<span class="pr-main"><b class="muted">Springes over</b><span class="pr-meta">Tryk for at ændre</span></span></button>
        <div class="pr-tools"><button class="more-b" data-action="day-menu-skipped" data-arg="${arg}" aria-label="Mere">⋯</button></div></div>`;
    }
    const type = TYPE_LABELS[day.type] ?? day.type;
    const { recipe } = this._recipeForDay(e.plan, day);
    const meta = [
      now ? '<span class="tag now">I aften</span>' : "",
      day.total_minutes ? `${V3.ic("clock", 13)} ${day.total_minutes} min` : "",
      type ? `<span class="tag t-${esc(day.type)}">${esc(type)}</span>` : "",
      day.mealie ? '<span class="tag">Mealie</span>' : "",
      day.new_dish ? '<span class="tag t-new">Ny ret – godkend</span>' : "",
      e.plan.surprise ? '<span class="tag">Overraskelse</span>' : "",
      recipe?.times_planned ? `<span class="muted">lavet ${recipe.times_planned}×</span>` : "",
    ].join("");
    const grip = drag ? `<span class="pr-drag" title="Træk for at flytte" aria-label="Træk for at flytte ${esc(day.dish || "retten")}"><svg viewBox="0 0 12 20" aria-hidden="true"><g fill="currentColor"><circle cx="3" cy="3" r="1.6"/><circle cx="9" cy="3" r="1.6"/><circle cx="3" cy="10" r="1.6"/><circle cx="9" cy="10" r="1.6"/><circle cx="3" cy="17" r="1.6"/><circle cx="9" cy="17" r="1.6"/></g></svg></span>` : "";
    return `<div class="prow${now ? " now" : ""}${past ? " past" : ""}${drag ? " has-drag" : ""}"${drag ? ` data-date="${esc(e.date)}" data-plan="${esc(e.plan.id)}"` : ""} style="animation-delay:${(i * 0.04).toFixed(2)}s">${grip}
      <button class="pr-open" data-action="day-menu" data-arg="${arg}" aria-label="Åbn ${esc(day.dish || "dagen")}"><span class="pr-date"><span>${V3.DAYS[d.getDay()]}</span><b>${d.getDate()}</b><small>${V3.MONTHS[d.getMonth()]}</small></span>
      ${V3.dishArt(day.dish || "", "pr-art")}
      <span class="pr-main"><b class="${day.dish ? "" : "muted"}">${esc(day.dish || "Ingen ret – tryk for at vælge en")}</b><span class="pr-meta">${meta}</span></span></button>
      <div class="pr-tools">${this._v3RateRow(e.plan, day)}<button class="more-b" data-action="day-menu" data-arg="${arg}" aria-label="Mere om ${esc(day.dish || "dagen")}">⋯</button></div></div>`;
  },

  _planView() {
    const plan = this._plan;
    if (plan?.kind === "freezer") return this._freezerView(plan);
    const s = this._v3s();
    const cat = this._state.catalogs || {};
    if (!plan) {
      return `<div class="v3">${this._v3GenCard("Lav madplan", true)}${this._freezerCard()}</div>`;
    }
    const { weeks, timeline } = this._v3AllWeeks();
    const today = localToday();
    const auto = Math.max(0, weeks.findIndex((w) => w.entries.some((e) => e.date >= today)));
    const idx = s.pw != null && weeks[s.pw] && s.pwPlan === plan.id ? s.pw : auto;
    const w = weeks[idx] || { week: plan.week, entries: [] };
    const upcoming = w.entries.filter((e) => e.date >= today);
    const earlier = w.entries.filter((e) => e.date < today);
    const owner = (upcoming[0] || w.entries.at(-1) || { plan }).plan;
    const latest = owner.id === plan.id;
    const canDrag = (e) => !!e.day?.dish && e.date >= today && !e.skipped;
    const dragging = upcoming.filter(canDrag).length >= 2;
    const rows = (upcoming.length ? upcoming : earlier).map((e, i) => this._v3Prow(e, i, dragging && canDrag(e))).join("");
    const past = upcoming.length && earlier.length
      ? `<details class="pr-past" data-fold="pastdays"${this._folds?.has("pastdays") ? " open" : ""}><summary>Tidligere i ugen · ${earlier.length} ${earlier.length === 1 ? "dag" : "dage"}</summary><div class="prows">${earlier.map((e, i) => this._v3Prow(e, i)).join("")}</div></details>`
      : "";
    const left = owner.shopping.filter((l) => !l.buy_from && !l.buy_at && !l.sent).length;
    const lines = owner.shopping.filter((l) => !l.skipped).length;
    const pill = owner.status === "generating" ? ["acc", "Laves …"] : owner.status === "sent" ? (left ? ["acc", `Sendt · ${left} nye varer`] : ["good", "Sendt til listen"]) : ["acc", "Kladde – ikke sendt endnu"];
    const title = timeline ? `Madplan uge ${w.week}` : owner.title;
    const first = w.entries[0]?.date, last = w.entries.at(-1)?.date;
    const fa = first ? new Date(`${first}T12:00:00`) : null, la = last ? new Date(`${last}T12:00:00`) : null;
    const period = fa && la ? (fa.getMonth() === la.getMonth() ? `${fa.getDate()}.–${la.getDate()}. ${V3.MONTHS_LONG[la.getMonth()]}` : `${fa.getDate()}. ${V3.MONTHS[fa.getMonth()]}–${la.getDate()}. ${V3.MONTHS[la.getMonth()]}`) : "";
    const over = latest && plan.budget && plan.total > plan.budget;
    const broken = latest ? (plan.checklist || []).filter((c) => !c.ok) : [];
    const waiting = latest ? (plan.days || []).filter((d) => d.new_dish) : [];
    const checklist = (plan.checklist || []).map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.requirement)}</li>`).join("");
    const mealie = this._state.mealie?.available ? `<button class="btn" data-action="mealie-sync" ${this._busy ? "disabled" : ""}>Sæt ugen i Mealie</button>` : "";
    const actions = latest
      ? `<button class="btn primary big" data-action="send" ${this._busy || !left ? "disabled" : ""}>${V3.ic("send", 18)} ${left ? (plan.status === "sent" ? `Send ${left} nye varer til ${this._listName()}` : `Send ${left} varer til ${this._listName()}`) : "Sendt ✓"}</button>
        ${plan.shopping.some((l) => l.buy_from) ? `<p class="sub later">+ ${plan.shopping.filter((l) => l.buy_from).length} varer købes senere – se Indkøb</p>` : ""}
        <button class="btn" data-action="tab" data-arg="shopping">Se indkøbslisten</button><button class="btn" data-action="open-day" data-arg="">Start madlavning</button>${mealie}`
      : `<button class="btn" data-action="tab" data-arg="shopping">Se indkøbslisten</button><button class="btn" data-action="open-day" data-arg="">Start madlavning</button>${mealie}`;
    const anim = this._v3Anim("plan", `${owner.id}|${idx}|${w.entries.length}`);
    return `${this._olderBanner()}${this._updateBanner(plan)}<div class="v3${anim}">
      <div class="card plan-head">
        <div class="row between wrap">${weeks.length > 1 ? `<div class="seg">${weeks.map((x, i) => `<button class="${i === idx ? "on" : ""}" data-action="v3-pw" data-arg="${i}">Uge ${x.week}</button>`).join("")}</div>` : "<span></span>"}
          <span class="row"><span class="pill ${pill[0]}">${pill[1]}</span><button class="help-q" data-action="plan-help" aria-expanded="${this._planHelp ? "true" : "false"}" aria-label="Hjælp" title="Hjælp">?</button></span></div>
        <div class="ph-grid"><div><h2>${esc(title)}</h2>
          <p class="sub">${esc(period)}${owner.summary ? ` · ${esc(owner.summary)}` : ""} Tryk på en dag for opskrift, skift og rester.</p></div>
          <div class="ph-price${over ? " over" : ""}"><b class="num">${V3.krd(owner.total, 2)}</b><span>${lines} varer at købe${latest && plan.budget ? ` · budget ${kr0(plan.budget)}` : ""}</span></div></div>
        ${over ? '<div class="banner warn">Planen er over budget. Prøv at lave en ny, eller ret budgettet i indstillingerne.</div>' : ""}
        ${broken.length ? `<div class="banner warn">AI'en kunne ikke overholde ${broken.length === 1 ? "ét krav" : `${broken.length} krav`}, selv efter at have prøvet igen:<ul class="checklist">${broken.map((c) => `<li class="bad">✗ ${esc(c.requirement)}</li>`).join("")}</ul>Tryk på retten for at skifte den ud, eller lav en ny madplan.</div>` : ""}
        ${waiting.length ? `<div class="banner warn">${waiting.length === 1 ? "1 ny ret venter" : `${waiting.length} nye retter venter`} på godkendelse: ${waiting.map((d) => esc(d.dish)).join(", ")}. Listen sendes først, når de er godkendt eller skiftet ud – tryk på retten.</div>` : ""}
        ${this._planHelp ? '<p class="sub help-text">Tryk på en ret for at se opskriften, skifte den ud eller flytte den. 👍, 👎 og ♥ gemmer retten i opskriftsamlingen – tryk igen for at fortryde.</p>' : ""}
        ${latest ? this._inventoryUsage(plan) : ""}
        ${dragging ? `<p class="dnd-hint"><span class="dnd-ic"><svg viewBox="0 0 12 20" aria-hidden="true"><g fill="currentColor"><circle cx="3" cy="3" r="1.6"/><circle cx="9" cy="3" r="1.6"/><circle cx="3" cy="10" r="1.6"/><circle cx="9" cy="10" r="1.6"/><circle cx="3" cy="17" r="1.6"/><circle cx="9" cy="17" r="1.6"/></g></svg></span>Træk i håndtaget til venstre for at flytte en ret til en anden dag – de andre retter rykker med.</p>` : ""}
        <div class="prows${dragging ? " dnd" : ""}">${rows || '<p class="sub">Ingen dage i ugen.</p>'}</div>
        ${past}
        ${latest ? this._lunchHtml(plan) : ""}
        ${latest && (checklist || plan.deviations) ? `<details class="plan-checks"><summary>Krav-tjekliste</summary><ul class="checklist">${checklist}</ul>${plan.deviations ? `<p class="muted">${esc(plan.deviations)}</p>` : ""}</details>` : ""}
        <div class="vplan-actions">${actions}</div>
      </div>
      ${this._v3GenCard()}
      ${this._freezerCard()}
      <p class="sub cat-line">${esc([cat.current ? `Aktuel avis: ${cat.current.label || ""} (til ${shortDate(localDay(cat.current.valid_to))})` : "", cat.upcoming ? `Næste avis: ${cat.upcoming.label || ""} fra ${shortDate(localDay(cat.upcoming.valid_from))}` : "Næste uges avis er ikke udkommet endnu"].filter(Boolean).join(" · "))}</p>
    </div>`;
  },

  /* Ny madplan: first day, wishes, the days, and the two buttons. */
  _v3GenCard(label = "Lav ny madplan", first = false) {
    const generating = this._state?.status?.state === "generating";
    const note = this._state?.note;
    const cat = this._state?.catalogs || {};
    const last = this._lastAvisDay();
    const dates = this._planDates();
    const shop = this._shopName();
    const tailored = dates.filter((iso) => { const k = this._kindOf(iso), d = this._defaultKind(iso); return k.kind !== d.kind || (k.kind === "fixed" && k.text !== d.text) || (k.kind === "pick" && this._picks[iso]); }).length;
    const kinds = dates.map((iso) => {
      const k = this._kindOf(iso);
      const pick = this._picks[iso];
      const d = new Date(`${iso}T12:00:00`);
      const extra = k.kind === "pick"
        ? pick
          ? `<span class="pick-chip"><button class="link" data-action="pick-open" data-arg="${iso}" title="Skift retten">${esc(pick.dish)}</button><button class="icon-btn" data-action="pick-remove" data-arg="${iso}" aria-label="Fjern ${esc(pick.dish)}">${CLOSE_ICON}</button></span>`
          : `<button class="btn small" data-action="pick-open" data-arg="${iso}">Find ret i opskrifter</button>`
        : k.kind === "fixed"
          ? `<input type="text" data-bind="daykindtext" data-field="${iso}" value="${esc(k.text || "")}" placeholder="Fx pizza" aria-label="Fast ret">`
          : `<span class="kd-hint">${V3_KIND_HINT[k.kind] || ""}</span>`;
      return `<div class="kday k-${k.kind}"><span class="kd-d"><b>${V3.DAYS[d.getDay()]}</b>${d.getDate()}/${d.getMonth() + 1}</span>
        <select data-bind="daykind" data-field="${iso}" aria-label="Hvad er ${esc(dateLabel(iso).toLowerCase())}">${Object.entries(DAY_KIND_LABELS).map(([key, l]) => `<option value="${key}" ${k.kind === key ? "selected" : ""}>${l}</option>`).join("")}</select>${extra}</div>`;
    }).join("");
    const open = tailored || this._folds?.has("days");
    return `<div class="card gen">
      <div class="gen-art">${AI_ICON.replace('class="ai"', 'class="ai" width="34" height="34"')}</div>
      <div class="gen-body"><div class="kicker">Ny madplan</div><h2>${first ? "Lav jeres første madplan" : "Lad AI'en lægge næste uge"}</h2>
        <p class="sub">Ud fra tilbuddene i ${esc(shop)}${cat.upcoming ? ` (${esc(cat.upcoming.label || "")} fra ${esc(shortDate(localDay(cat.upcoming.valid_from)))})` : ""}, jeres favoritter og indstillinger.</p>
        <div class="gen-row"><label class="fld inline">Første dag<input type="date" data-bind="start" value="${esc(this._startDate || "")}" ${last ? `max="${esc(last)}"` : ""}></label></div>
        ${cat.current && !cat.upcoming && last ? '<p class="sub">Næste uges avis er ikke ude endnu. Hele den valgte periode planlægges med kendte priser og tilbud på indkøbsdagen.</p>' : ""}
        <div class="wish${note ? " has" : ""}">
          <div class="wish-h"><span class="wish-ic">💬</span><div><b>Ønsker til madplanen</b><small>${note ? "Bruges i næste madplan" : "Fx “mere fisk”, “noget nyt med kylling”, “gæster lørdag”"}</small></div><button class="btn" data-action="note-open">${note ? "Ret ønsker" : "Skriv ønsker"}</button></div>
          ${note ? `<p class="wish-note">“${esc(note)}”</p>` : ""}
        </div>
        ${kinds ? `<details class="tailor" data-fold="days"${open ? " open" : ""}><summary><b>Tilpas dagene</b>${tailored ? ` <span class="tag now">${tailored} ${tailored === 1 ? "dag" : "dage"}</span>` : ""}<small>Som under Faste dage i indstillingerne – ændr dem for netop denne uge.</small></summary>
          <div class="kinds">${kinds}</div><p class="foot">En rugbrødsdag laves der ikke mad, og der købes ikke noget til.</p></details>` : ""}
        ${(this._state?.freezer_inventory || []).length ? `<label class="check"><input type="checkbox" data-bind="use-freezer" ${this._useFreezer !== false ? "checked" : ""}> Brug råvarer fra spisekammeret i denne madplan</label>` : ""}
        <div class="row wrap gen-go"><button class="btn primary big" data-action="generate" ${generating || this._busy ? "disabled" : ""}>${generating ? '<span class="spinner small"></span> Laves …' : `${AI_ICON} ${esc(label)}`}</button>
          <button class="btn big surprise" data-action="surprise" ${generating || this._busy ? "disabled" : ""} title="Retter I aldrig har fået – fra andre køkkener og med overraskende smage">✨ Overrask os</button></div></div>
    </div>`;
  },

  _freezerCard() {
    const count = (this._state?.freezer_plans || []).length;
    return `<details class="card freezer" data-fold="freezer"${this._folds?.has("freezer") ? " open" : ""}><summary><b>Månedens frysermad${count ? ` <span class="tag">${count} ${count === 1 ? "plan" : "planer"}</span>` : ""}</b><small>Lav mad til fryseren én dag og spis af den hele måneden.</small></summary>${this._freezerControls(false)}</details>`;
  },

  /* ------------------------------------------------------------------ Opskrifter */
  _collectionRows() {
    const list = this._filteredRecipes();
    if (!list.length) {
      return (this._state.recipes || []).length
        ? '<p class="sub">Ingen opskrifter passer til søgningen.</p>'
        : '<p class="sub">Opskriftsamlingen er tom. Giv en ret 👍 eller ♥ på madplanen, indsæt et link til en opskrift, eller skriv en ny.</p>';
    }
    const src = (r) => (r.source === "rema" ? "REMA 1000" : r.source === "link" ? "Fra link" : r.source === "web" ? r.site || "Fra nettet" : r.source === "scan" ? "Fra kogebog" : r.source === "manual" ? "Egen opskrift" : r.source === "plan" ? "Fra planen" : "");
    return `<div class="rgrid">${list.map((r, i) => `<div class="rcard" style="animation-delay:${Math.min(i, 20) * 0.025}s">
        <button class="rc-open" data-action="rc-open" data-arg="${esc(r.id)}">${V3.dishArt(r.name, "rc-art")}${r.favorite ? '<span class="rc-heart">♥</span>' : r.rating === "dislike" ? '<span class="rc-heart no">👎</span>' : ""}
        <b>${esc(r.name)}</b>
        <span class="vrc-meta">${src(r) ? `<span class="tag">${esc(src(r))}</span>` : ""}${r.type === "vegetar" ? '<span class="tag t-veg">Vegetar</span>' : ""}<span>${r.times_planned ? `lavet ${r.times_planned}×` : "ikke lavet endnu"}${r.total_minutes ? ` · ${r.total_minutes} min` : ""}</span>${this._hasPrices() && !r.ready && r.missing ? `<span class="tag t-new">Mangler ${r.missing} ${r.missing === 1 ? "vare" : "varer"}</span>` : ""}</span></button>
        ${this._recipeRateButtons(r)}</div>`).join("")}</div>`;
  },

  _collectionView() {
    const seg = Object.entries(RECIPE_FILTERS).map(([k, l]) => `<button class="${this._rc.filter === k ? "on" : ""}" data-action="rc-filter" data-arg="${k}">${k === "favorite" ? "♥ " : ""}${l}</button>`).join("");
    return `<div class="v3">
      <div class="card">
        <div class="row between wrap"><div class="seg">${seg}</div>
          <label class="fld inline sortf">Sortér<select data-bind="rc" data-field="sort">${Object.entries(RECIPE_SORTS).map(([k, l]) => `<option value="${k}" ${this._rc.sort === k ? "selected" : ""}>${l}</option>`).join("")}</select></label></div>
        <div class="qbar small">${V3.ic("search", 18)}<input type="search" data-bind="rc" data-field="query" value="${esc(this._rc.query)}" placeholder="Søg i opskrifter og ingredienser" aria-label="Søg i opskrifter">${this._rc.query ? '<button class="qx" data-action="clear-field" data-arg="rc" aria-label="Ryd">×</button>' : ""}</div>
        <div id="rc-list" class="rc-list">${this._collectionRows()}</div>
      </div>
      <div class="card addrecipe"><div class="kicker">Tilføj en opskrift</div><h2>Fra et link, en kogebog eller jer selv</h2>
        <div class="qbar small">${V3.ic("plus", 18)}<input type="url" inputmode="url" data-bind="rc" data-field="link" value="${esc(this._rc.link)}" placeholder="Indsæt et link til en opskrift" aria-label="Link til en opskrift">
          <button class="qgo" data-action="rc-import" ${this._rc.importing ? "disabled" : ""} aria-label="Hent opskrift">${this._rc.importing ? '<span class="spinner small"></span>' : V3.ic("plus", 18)}</button></div>
        <div class="row wrap" style="margin-top:12px">
          <button class="btn" data-action="rc-scan" ${this._rc.scanning ? "disabled" : ""}>${this._rc.scanning ? '<span class="spinner small"></span> Læser opskriften …' : `${CAMERA_ICON} Scan fra kogebog`}</button>
          <input type="file" id="scan-input" accept="image/*" multiple hidden>
          <button class="btn" data-action="rc-new">Skriv selv</button></div>
        <p class="foot">Opskriften hentes fra siden eller billedet, og du kan rette den, før den gemmes. Linket og billederne gemmes ikke. Tag gerne flere billeder, hvis opskriften fylder mere end én side.</p>
      </div></div>`;
  },

  /* ------------------------------------------------------------------ Favoritter */
  _productCard(p) {
    const sale = onOffer(p);
    const until = validTo(p.price_valid_to);
    const off = sale && p.normal_price && p.normal_price > p.price ? p.normal_price - p.price : 0;
    return `<div class="pcard${sale ? " onsale" : ""}">
      <div class="ph">${V3.pic(p.image, V3.groupOf(p.name))}${off ? `<span class="sale-b">−${V3.fmt(off, 2)}</span>` : sale ? '<span class="sale-b">Tilbud</span>' : ""}${this._bell(p).replace('class="bell', 'class="vbell bell')}</div>
      <b>${esc(V3.cap(String(p.name || "").toLowerCase()))}</b>
      <small>${esc((p.underline || "").toLowerCase())}</small>
      <span class="pc-tags">${p.is_advertised ? '<span class="tag t-new">Avisvare</span>' : ""}${p.is_organic ? '<span class="tag t-veg">Øko</span>' : ""}${p.offer_from ? `<span class="tag">fra ${esc(dayShort(p.offer_from))}</span>` : sale && until ? `<span class="muted">til ${esc(until)}</span>` : ""}</span>
      ${p.avis ? `<small class="avis">Avis: ${esc(p.avis)}${p.avis_quantity ? ` · ${esc(p.avis_quantity)}` : ""}</small>` : ""}
      ${this._favCheaper(p)}
      <div class="pc-price"><span class="num${sale ? " now" : ""}">${V3.krd(p.price, 2)}</span>${off ? `<s>${V3.fmt(p.normal_price, 2)}</s>` : ""}<button class="add" data-action="fav-add" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""} aria-label="Læg ${esc(p.name)} på ${esc(this._listName())}">${V3.ic("plus", 16)}</button></div>
    </div>`;
  },

  /* ------------------------------------------------------------------ Spisekammer */
  _v3PantryArt() {
    const n = (this._state?.freezer_inventory || []).length;
    return `<div class="v3"><div class="card pantry-empty">
      <svg viewBox="0 0 320 200" class="pantry-art" aria-hidden="true">
        <rect x="40" y="20" width="110" height="170" rx="12" fill="var(--rema-subtle)" stroke="var(--divider-color)" stroke-width="2"/>
        <rect x="40" y="20" width="110" height="64" rx="12" fill="color-mix(in srgb, var(--g-mejeri) 16%, var(--rema-subtle))"/>
        <path d="M58 52h16M58 120v24" stroke="var(--v3-soft)" stroke-width="4" stroke-linecap="round"/>
        <g class="frost"><path d="M95 50 l0 -14 M88 43 l14 0 M90 38 l10 10 M100 38 l-10 10" stroke="var(--g-mejeri)" stroke-width="2" stroke-linecap="round"/></g>
        <rect x="170" y="44" width="120" height="8" rx="4" fill="var(--divider-color)"/><rect x="170" y="104" width="120" height="8" rx="4" fill="var(--divider-color)"/><rect x="170" y="164" width="120" height="8" rx="4" fill="var(--divider-color)"/>
        <g transform="translate(176 6) scale(.6)">${V3.ART.kolonial("kolonial")}</g><g transform="translate(222 66) scale(.6)">${V3.ART.mejeri("mejeri")}</g><g transform="translate(250 6) scale(.6)">${V3.ART.drikke("drikke")}</g><g transform="translate(184 126) scale(.6)">${V3.ART.frugt("frugt")}</g>
      </svg>
      <div><div class="kicker">Fryseren og skabet</div><h2>${n ? `${n} ${n === 1 ? "råvare" : "råvarer"} på lager` : "Tomt – endnu"}</h2>
        <p class="sub">Skriv det, I har hjemme, så bruger madplanen det først, og det kommer ikke på indkøbslisten.</p></div>
    </div></div>`;
  },
});

/* Tilbud og priser at the top of Indkøb, and moving a dinner from its menu. */
Object.assign(V3_METHODS, {
  _chainsCard() {
    const ids = [this._storeId(), ...(this._state.settings.chains || []).filter((id) => id !== this._storeId())];
    const e = this._everywhere;
    const cat = this._state.catalogs || {};
    const compare = this._plan ? this._ensureCompare() : null;
    const lines = Object.entries(compare?.lines || {}).map(([id, c]) => ({ line: this._plan.shopping.find((l) => l.id === id), ...c })).filter((x) => x.line && !x.line.sent && !x.line.buy_at);
    return `<div class="v3"><div class="card offers-top">
      <div class="row between wrap"><div><div class="kicker">Tilbud og priser</div><h2>Ugens tilbud i jeres butikker</h2></div>
        ${cat.current ? `<span class="pill">Avis ${esc((cat.current.label || "").toLowerCase())}${cat.upcoming ? ` · ${esc((cat.upcoming.label || "").toLowerCase())} fra ${esc(V3.DAYS_LONG[new Date(localDay(cat.upcoming.valid_from) + "T12:00:00").getDay()])}` : ""}</span>` : ""}</div>
      <div class="chainrow">${ids.map((id, i) => `<button class="vchain${i === 0 ? " on" : ""}" data-action="chain-open" data-arg="${esc(id)}">${this._chainLogo(id, "tiny")}<span>${esc(this._chainName(id))}</span></button>`).join("")}</div>
      <div class="qbar small">${V3.ic("search", 20)}<input type="search" data-bind="everywhere" value="${esc(e.query)}" placeholder="Søg på en vare i alle butikker – fx kaffe, smør eller laks" enterkeyhint="search" aria-label="Søg på en vare">
        ${e.query || e.data ? '<button class="qx" data-action="everywhere-clear" aria-label="Ryd">×</button>' : ""}
        <button class="qgo" data-action="everywhere" ${e.loading ? "disabled" : ""} aria-label="Søg">${e.loading ? '<span class="spinner small"></span>' : V3.ic("search", 18)}</button></div>
      <div class="ev-out">${e.error ? `<div class="banner error">${esc(e.error)}</div>` : ""}${e.data ? this._everywhereHtml(e.data) : ""}</div>
      ${lines.length ? `<div class="vcheaper"><span class="kicker">Billigere andre steder · fra jeres liste</span><div class="ch-row">${lines.map((x) => `<button class="ch-card" data-action="chain-move" data-arg="${esc(x.line.id)}|${esc(x.dealer_id)}" title="Køb den i ${esc(this._chainName(x.dealer_id))} i stedet">${this._chainLogo(x.dealer_id, "tiny")}<span><b>${esc(x.heading || x.line.name)}</b><small>${esc(this._chainName(x.dealer_id))}${x.price != null ? ` · ${V3.fmt(x.price, 2)} kr.` : ""}${x.quantity ? ` ${esc(x.quantity)}` : ""}</small></span><span class="save">−${V3.fmt(x.saving || 0, 2)}</span></button>`).join("")}</div></div>` : compare?.loading ? '<p class="sub"><span class="spinner small"></span> Sammenligner listen med de andre butikkers tilbud …</p>' : ""}
    </div></div>`;
  },

  // Move the dinner a day up or down, from the day's menu.
  _v3MoveRow(m) {
    if (m.skipped || !m.dish) return "";
    const plan = this._planOf(m.planId);
    if (!plan) return "";
    const today = localToday();
    if (m.date < today) return "";
    const near = (step) => { const d = new Date(`${m.date}T12:00:00`); d.setDate(d.getDate() + step); const iso = V3.ymd(d); return (plan.days || []).find((x) => x.date === iso); };
    const btn = (dir, other, label) => `<button class="btn small" data-action="v3-move" data-arg="${esc(plan.id)}|${esc(m.date)}|${dir}" ${!other || other.date < today || m.busy ? "disabled" : ""}>${label}</button>`;
    return `<div class="row wrap day-move"><span class="muted small">Flyt retten</span>${btn("up", near(-1), "↑ En dag tidligere")}${btn("down", near(1), "↓ En dag senere")}</div>`;
  },
});

/* Historik's receipts, and moving dinners in the plan by dragging them. */
Object.assign(V3_METHODS, {
  _v3ReceiptRow(r) {
    const t = r.date ? new Date(r.date) : null;
    const g = r.groups || {};
    return `<button class="buy open" data-action="v3-bon" data-arg="${esc(r.id)}"><span class="ic" style="background:var(--rema-tint);color:var(--rema-accent)">${V3.ic("receipt", 20)}</span>
      <span><b>REMA 1000${r.store ? ` ${esc(r.store)}` : r.city ? ` ${esc(r.city)}` : ""}</b><small>${t ? `${V3.DAYS_LONG[t.getDay()]} ${t.getDate()}. ${V3.MONTHS[t.getMonth()]} ${t.getFullYear() !== new Date().getFullYear() ? `${t.getFullYear()} ` : ""}kl. ${String(t.getHours()).padStart(2, "0")}.${String(t.getMinutes()).padStart(2, "0")}` : ""} · ${r.items} ${r.items === 1 ? "linje" : "linjer"}${r.total_discount ? ` · sparet ${V3.krd(r.total_discount, 2)}` : ""}</small>
      ${Object.keys(g).length ? `<span class="mini-g">${V3.ORDER.filter((k) => g[k]).map((k) => `<i style="flex-grow:${g[k]};background:var(--g-${k})"></i>`).join("")}</span>` : ""}</span>
      <span class="amt">${V3.krd(r.total, 2)}<br><small class="chev">Se bon ›</small></span></button>`;
  },

  // Drag a dinner by its handle to another day: it moves day by day, the others make room.
  _v3BindDrag() {
    const list = this.shadowRoot.querySelector(".prows.dnd");
    if (!list || list._v3dnd) return;
    list._v3dnd = true;
    list.addEventListener("pointerdown", (ev) => {
      const handle = ev.target.closest(".pr-drag");
      if (!handle || this._busy || (ev.pointerType === "mouse" && ev.button !== 0)) return;
      const row = handle.closest(".prow");
      const rows = [...list.querySelectorAll(":scope > .prow[data-date]")].filter((r) => r.dataset.plan === row.dataset.plan);
      const from = rows.indexOf(row);
      if (from < 0 || rows.length < 2) return;
      ev.preventDefault();
      const scroll = () => window.scrollY || document.documentElement.scrollTop || 0;
      const y0 = scroll();
      const rects = rows.map((r) => { const b = r.getBoundingClientRect(); return { top: b.top + y0, h: b.height }; });
      const gap = rows[1] ? rects[1].top - rects[0].top - rects[0].h : 8;
      const startY = ev.clientY + y0;
      let to = from, auto = 0, lastY = ev.clientY;
      try { handle.setPointerCapture(ev.pointerId); } catch { /* old browsers */ }
      row.classList.add("dragging");
      list.classList.add("dragging");
      const place = () => {
        const dy = lastY + scroll() - startY;
        row.style.transform = `translateY(${dy}px)`;
        const mid = rects[from].top + rects[from].h / 2 + dy;
        to = rows.length - 1;
        for (let i = 0; i < rows.length; i += 1) if (mid < rects[i].top + rects[i].h) { to = i; break; }
        const h = rects[from].h + gap;
        rows.forEach((r, i) => {
          if (i === from) return;
          const shift = from < to && i > from && i <= to ? -h : from > to && i < from && i >= to ? h : 0;
          r.style.transform = shift ? `translateY(${shift}px)` : "";
        });
      };
      const tick = () => { if (!auto) return; window.scrollBy(0, auto); place(); requestAnimationFrame(tick); };
      const move = (e) => {
        lastY = e.clientY;
        const was = auto;
        auto = e.clientY < 90 ? -8 : e.clientY > innerHeight - 140 ? 8 : 0;
        if (auto && !was) requestAnimationFrame(tick);
        place();
      };
      const end = (commit) => {
        auto = 0;
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onCancel);
        rows.forEach((r) => { r.style.transform = ""; });
        row.classList.remove("dragging");
        list.classList.remove("dragging");
        if (commit && to !== from) this._v3DragMove(row.dataset.plan, rows[from].dataset.date, rows[to].dataset.date);
      };
      const onUp = () => end(true);
      const onCancel = () => end(false);
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onCancel);
    });
  },

  _v3DragMove(planId, fromDate, toDate) {
    const steps = V3.daysBetween(fromDate, toDate);
    if (!steps) return;
    const direction = steps < 0 ? "up" : "down";
    const name = this._planOf(planId)?.days.find((d) => d.date === fromDate)?.dish || "Retten";
    this._run(async () => {
      let date = fromDate;
      for (let i = 0; i < Math.abs(steps); i += 1) {
        await this._ws("middagsro/day/move", { plan_id: planId, date, direction });
        date = V3.ymd(V3.addDays(date, direction === "up" ? -1 : 1));
      }
    }, `${name} er flyttet til ${V3.DAYS_LONG[new Date(`${toDate}T12:00:00`).getDay()]}.`);
  },
});

Object.assign(Rema1000Panel.prototype, V3_METHODS);
for (const key of Object.keys(V3_ICONS)) TAB_ICONS[key] = V3_TAB_ICON(key);

const V3_STYLE = `
.v3 .num {font-variant-numeric: tabular-nums;}
.v3 .disp {font-family: var(--display); letter-spacing: -.025em;}
.v3 .brand {display: flex; align-items: center; gap: 10px;}
.v3 .logo {width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: var(--rema-accent); color: var(--rema-on-accent);}
.v3 .wordmark {font-family: var(--display); font-weight: 650; font-size: 21px; letter-spacing: -.025em;}
.v3 .spacer {flex: 1;}
@keyframes rise { from { opacity: 0; transform: translateY(10px); } }
.v3 .card {position: relative; background: var(--rema-card); border-radius: var(--ha-card-border-radius); border: 1px solid var(--line);
  box-shadow: var(--ha-card-box-shadow); padding: 18px; margin-bottom: 16px; overflow: hidden;}
.v3 .kicker {font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--soft);}
.v3 h2 {margin: 2px 0 0; font-family: var(--display); font-size: 22px; font-weight: 650; letter-spacing: -.02em;}
.v3 .sub {margin: 4px 0 0; color: var(--soft); font-size: 13.5px; line-height: 1.45;}
.v3 .row {display: flex; align-items: center; gap: 10px;}
.v3 .wrap {flex-wrap: wrap;}
.v3 .between {justify-content: space-between;}
.v3 .grid2 {display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 16px; align-items: start;}
@media (max-width: 860px) {
  .v3 .grid2 {grid-template-columns: minmax(0, 1fr);}
}
.v3 .pill {display: inline-flex; align-items: center; gap: 6px; height: 26px; padding: 0 10px; border-radius: 999px; font-size: 12px; font-weight: 650; background: var(--rema-subtle); color: var(--soft);}
.v3 .pill.good {background: color-mix(in srgb, var(--good) 14%, transparent); color: var(--good);}
.v3 .pill.bad {background: color-mix(in srgb, var(--bad) 14%, transparent); color: var(--bad);}
.v3 .pill.acc {background: var(--rema-tint); color: var(--rema-accent);}
.v3 .seg {display: inline-flex; padding: 3px; border-radius: 999px; background: var(--rema-subtle);}
.v3 .seg button {border: 0; background: none; padding: 7px 16px; border-radius: 999px; font-weight: 650; font-size: 13.5px; color: var(--soft); cursor: pointer; transition: all .2s;}
.v3 .seg button.on {background: var(--card-background-color); color: var(--ink); box-shadow: 0 1px 3px rgba(0,0,0,.14);}
.v3 .hero {background:
  radial-gradient(120% 70% at 50% -10%, color-mix(in srgb, var(--rema-accent) 16%, transparent), transparent 60%), var(--rema-card);}
.v3 .hero-top {display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap;}
.v3 .weekpick {display: flex; gap: 6px;}
.v3 .wk {width: 46px; border: 1px solid var(--line); background: var(--card-background-color); border-radius: 14px; padding: 6px 0 5px; cursor: pointer; display: grid; justify-items: center; gap: 2px; transition: border-color .2s, transform .2s;}
.v3 .wk:hover {transform: translateY(-1px);}
.v3 .wk.on {border-color: var(--rema-accent); box-shadow: 0 0 0 3px var(--rema-tint);}
.v3 .wk svg {width: 28px; height: 28px;}
.v3 .wk span {font-size: 10.5px; font-weight: 700; color: var(--soft);}
.v3 .dialwrap {position: relative; width: min(100%, 420px); aspect-ratio: 1; margin: 6px auto 0;}
.v3 .dialwrap svg.dial {position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible;}
.v3 .dial .face {fill: var(--rema-subtle);}
.v3 .dial .track {fill: none; stroke: color-mix(in srgb, var(--ink) 9%, transparent);}
.v3 .dial .tick {stroke: var(--line); stroke-width: 1.4;}
.v3 .dial .daylab {font: 700 9.5px var(--ha-font-family-body); letter-spacing: .08em; fill: var(--soft); text-anchor: middle; dominant-baseline: middle;}
.v3 .dial .daylab.today {fill: var(--rema-accent);}
.v3 .dial .petal {transform-box: view-box; transform-origin: 200px 200px; animation: petal .7s cubic-bezier(.2,.8,.2,1) both;}
@keyframes petal { from { transform: scale(.6); opacity: 0; } }
.v3 .dial .ghost {fill: none; stroke: var(--soft); stroke-width: 1.2; stroke-dasharray: 2.5 3.5; opacity: .55;}
.v3 .dial .seg-arc {fill: none; stroke-linecap: butt; animation: sweep 1.3s cubic-bezier(.45,.05,.25,1) both;}
@keyframes sweep { from { stroke-dashoffset: var(--len); } }
.v3 .dial .over {fill: none; stroke: var(--bad); stroke-linecap: round; animation: sweep 1.2s .9s cubic-bezier(.45,.05,.25,1) both; filter: url(#glow);}
.v3 .dial .pace {stroke: var(--ink); stroke-width: 2.2; stroke-linecap: round;}
.v3 .dial .needle {stroke: var(--ink); stroke-width: 1.6; stroke-linecap: round; stroke-dasharray: 2 4;}
.v3 .wcenter {position: absolute; inset: 27%; border-radius: 50%; display: grid; place-content: center; text-align: center; gap: 2px; pointer-events: none;}
.v3 .wcenter .lab {font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--soft);}
.v3 .wcenter .big {font-family: var(--display); font-weight: 680; font-size: clamp(24px, 6.6vw, 36px); letter-spacing: -.035em; line-height: 1.02;}
.v3 .wcenter .big.bad {color: var(--bad);}
.v3 .wcenter .small {font-size: 12.5px; color: var(--soft);}
.v3 .wcenter .chip {justify-self: center; margin-top: 4px;}
.v3 .kbook {display: grid; gap: 10px; margin-top: 8px; padding: 14px; border-radius: 18px; background: var(--rema-subtle);}
.v3 .kbook-row {display: flex; gap: 8px; align-items: center;}
.v3 .kamount {flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; height: 52px; padding: 0 16px; border-radius: 16px; background: var(--card-background-color); border: 1.5px solid var(--line); transition: border-color .2s, box-shadow .2s;}
.v3 .kamount:focus-within {border-color: var(--rema-accent); box-shadow: 0 0 0 4px var(--rema-tint);}
.v3 .kamount input {flex: 1; min-width: 0; width: 100%; border: 0; outline: 0; background: none; color: var(--ink); font: 650 24px var(--display); letter-spacing: -.02em;}
.v3 .kamount span {color: var(--soft); font-weight: 600;}
.v3 .kgo {height: 52px; padding: 0 20px; border: 0; border-radius: 16px; background: var(--rema-accent); color: var(--rema-on-accent); font-weight: 700; font-size: 15px; cursor: pointer; transition: transform .15s;}
.v3 .kgo:active {transform: scale(.97);}
.v3 .kquick {display: flex; gap: 6px; flex-wrap: wrap;}
.v3 .kquick button {border: 1px solid var(--line); background: var(--card-background-color); border-radius: 999px; padding: 6px 12px; font-weight: 650; font-size: 13px; cursor: pointer;}
.v3 .kquick button:hover {border-color: var(--rema-accent); color: var(--rema-accent);}
.v3 .buys {display: grid; gap: 6px; margin-top: 12px;}
.v3 .buy {display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 14px; background: var(--card-background-color); border: 1px solid var(--line); animation: rise .4s both;}
.v3 .buy .ic {width: 34px; height: 34px; border-radius: 11px; display: grid; place-items: center;}
.v3 .buy b {font-size: 14px;}
.v3 .buy small {display: block; color: var(--soft); font-size: 12px;}
.v3 .buy .amt {font-weight: 700; font-variant-numeric: tabular-nums;}
.v3 .undo {border: 0; background: none; color: var(--soft); cursor: pointer; font-size: 12px; text-decoration: underline;}
.v3 .stats4 {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 14px;}
@media (max-width: 520px) {
  .v3 .stats4 {grid-template-columns: repeat(2, minmax(0, 1fr));}
}
.v3 .stat {padding: 10px 12px; border-radius: 14px; background: var(--rema-subtle);}
.v3 .stat span {display: block; font-size: 11.5px; color: var(--soft); font-weight: 600;}
.v3 .stat b {font-family: var(--display); font-size: 19px; font-weight: 650; letter-spacing: -.02em;}
.v3 .groupbar {display: flex; height: 10px; border-radius: 999px; overflow: hidden; gap: 2px; background: var(--rema-subtle); margin-top: 10px;}
.v3 .groupbar i {display: block; height: 100%; transition: flex-grow .5s ease;}
.v3 .legend {display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;}
.v3 .lg {display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px 4px 4px; border-radius: 999px; border: 1px solid var(--line); background: var(--card-background-color); font-size: 12.5px; font-weight: 600; cursor: pointer; transition: opacity .2s, border-color .2s;}
.v3 .lg svg {width: 24px; height: 24px;}
.v3 .lg .v {color: var(--soft); font-weight: 600; font-variant-numeric: tabular-nums;}
.v3 .lg.off {opacity: .38;}
.v3 .lg.solo {border-color: var(--ink);}
.v3 .sunday {padding: 0;}
.v3 .scene {display: block; width: 100%; height: auto;}
.v3 .sunday-body {padding: 16px 18px 18px;}
.v3 .rhythm {display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 6px; margin-top: 12px; align-items: end;}
.v3 .rd {display: grid; justify-items: center; gap: 6px;}
.v3 .rd .bub {border-radius: 50%; display: grid; place-items: center; font-size: 11px; font-weight: 700; color: #fff; background: color-mix(in srgb, var(--rema-accent) 40%, var(--rema-subtle)); transition: transform .3s;}
.v3 .rd.top .bub {background: var(--rema-accent); box-shadow: 0 10px 24px -10px var(--rema-accent);}
.v3 .rd span {font-size: 11px; font-weight: 700; color: var(--soft); letter-spacing: .06em;}
.v3 .rd small {font-size: 11px; color: var(--soft); font-variant-numeric: tabular-nums;}
.v3 .hours {display: flex; align-items: flex-end; gap: 2px; height: 46px; margin-top: 12px;}
.v3 .hours i {flex: 1; border-radius: 3px 3px 0 0; background: color-mix(in srgb, var(--rema-accent) 28%, var(--rema-subtle)); min-height: 2px;}
.v3 .hours i.peak {background: var(--rema-accent);}
.v3 .hourlab {display: flex; justify-content: space-between; font-size: 10.5px; color: var(--soft); margin-top: 4px;}
.v3 .big-dial {position: relative; width: min(100%, 560px); aspect-ratio: 1; margin: 4px auto 0; touch-action: none;}
.v3 .big-dial svg {position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible;}
.v3 .bd .bar {transition: opacity .25s ease; transform-box: view-box; transform-origin: 220px 220px; animation: grow .8s cubic-bezier(.2,.8,.2,1) both;}
@keyframes grow { from { transform: scale(.45); opacity: 0; } }
.v3 .bd .bar.dim {opacity: .22;}
.v3 .bd .save {fill: var(--ink); opacity: .32;}
.v3 .bd .avg {fill: none; stroke: var(--ink); stroke-width: 1.2; stroke-dasharray: 3 5; opacity: .55;}
.v3 .bd .bud {fill: none; stroke: var(--rema-accent); stroke-width: 1.4; stroke-dasharray: 1 4; stroke-linecap: round;}
.v3 .bd .ringlab {font: 650 10px var(--ha-font-family-body); fill: var(--soft);}
.v3 .bd .tlab {font: 700 9.5px var(--ha-font-family-body); fill: var(--soft); text-anchor: middle; dominant-baseline: middle;}
.v3 .bd .mark {font: 700 10px var(--ha-font-family-body); text-anchor: middle; dominant-baseline: middle; fill: var(--ink);}
.v3 .bd .sel {fill: none; stroke: var(--ink); stroke-width: 1.6;}
.v3 .bd .hand {stroke: var(--ink); stroke-width: 1.4; stroke-dasharray: 2 4;}
.v3 .bcenter {position: absolute; inset: 31%; border-radius: 50%; display: grid; place-content: center; text-align: center; gap: 3px; pointer-events: none;}
.v3 .bcenter .lab {font-size: 11.5px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--soft);}
.v3 .bcenter .big {font-family: var(--display); font-weight: 680; font-size: clamp(24px, 6.4vw, 40px); letter-spacing: -.035em; line-height: 1;}
.v3 .bcenter .saved {color: var(--good); font-weight: 700; font-size: 13px;}
.v3 .bcenter .meta {color: var(--soft); font-size: 12px;}
.v3 .minidays {display: flex; gap: 3px; justify-content: center; align-items: flex-end; height: 26px; margin-top: 4px;}
.v3 .minidays i {width: 9px; border-radius: 3px; background: color-mix(in srgb, var(--ink) 18%, transparent); min-height: 3px;}
.v3 .minidays i.hi {background: var(--rema-accent);}
.v3 .minilab {display: flex; gap: 3px; justify-content: center;}
.v3 .minilab span {width: 9px; font-size: 7.5px; font-weight: 700; color: var(--soft);}
.v3 .tip {position: absolute; z-index: 3; pointer-events: none; padding: 8px 10px; border-radius: 12px; background: var(--ink); color: var(--card-background-color); font-size: 12.5px; line-height: 1.35; transform: translate(-50%, calc(-100% - 12px)); white-space: nowrap; opacity: 0; transition: opacity .15s;}
.v3 .tip.on {opacity: 1;}
.v3 .tiles {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px;}
@media (max-width: 720px) {
  .v3 .tiles {grid-template-columns: repeat(2, minmax(0, 1fr));}
}
.v3 .tile {position: relative; padding: 12px; border-radius: 18px; background: var(--rema-subtle); overflow: hidden; cursor: pointer; transition: transform .2s; border: 1px solid transparent;}
.v3 .tile:hover {transform: translateY(-2px);}
.v3 .tile.solo {border-color: var(--ink);}
.v3 .tile svg.art {width: 58px; height: 58px; display: block;}
.v3 .tile b {display: block; font-size: 13px; margin-top: 6px;}
.v3 .tile .v {font-family: var(--display); font-weight: 650; font-size: 20px; letter-spacing: -.02em;}
.v3 .tile .s {font-size: 12px; color: var(--soft);}
.v3 .tile .glow {position: absolute; right: -30px; top: -30px; width: 110px; height: 110px; border-radius: 50%; opacity: .16;}
.v3 .trend {font-size: 12px; font-weight: 700;}
.v3 .trend.up {color: var(--bad);}
.v3 .trend.down {color: var(--good);}
.v3 .story {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px;}
@media (max-width: 860px) {
  .v3 .story {grid-template-columns: 1fr;}
}
.v3 .story .card {margin: 0;}
.v3 .huge {font-family: var(--display); font-weight: 700; font-size: 38px; letter-spacing: -.04em; line-height: 1; margin-top: 8px;}
.v3 .huge.good {color: var(--good);}
.v3 .years svg {width: 100%; height: auto; display: block; margin-top: 8px;}
.v3 .podium {display: grid; grid-template-columns: 1fr 1.18fr 1fr; gap: 12px; align-items: end; margin-top: 14px;}
.v3 .pod {position: relative; display: grid; justify-items: center; text-align: center; gap: 6px;}
.v3 .pod .ph {position: relative; width: 100%; max-width: 240px; aspect-ratio: 1; border-radius: 22px; background: radial-gradient(70% 70% at 50% 40%, var(--card-background-color), var(--rema-subtle)); display: grid; place-items: center; overflow: hidden;}
.v3 .pod .ph img, .v3 .pod .ph svg {width: 78%; height: 78%; object-fit: contain; filter: drop-shadow(0 14px 18px rgba(0,0,0,.18)); animation: float 5s ease-in-out infinite;}
@keyframes float { 50% { transform: translateY(-6px); } }
.v3 .pod .pstep {width: 100%; border-radius: 14px 14px 6px 6px; display: grid; place-items: center; font-family: var(--display); font-size: 26px; font-weight: 750; color: var(--rema-on-accent); background: var(--rema-accent);}
.v3 .pod:nth-child(1) .pstep {height: 54px; opacity: .78;}
.v3 .pod:nth-child(2) .pstep {height: 76px;}
.v3 .pod:nth-child(3) .pstep {height: 40px; opacity: .6;}
.v3 .pod b {font-size: 13.5px; line-height: 1.25;}
.v3 .pod small {color: var(--soft); font-size: 12px;}
.v3 .shelf {display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); gap: 12px; margin-top: 16px;}
.v3 .vprod {position: relative; display: grid; gap: 8px; padding: 10px; border-radius: 18px; background: var(--rema-subtle); border: 1px solid transparent; transition: transform .2s, border-color .2s; animation: rise .5s both;}
.v3 .vprod:hover {transform: translateY(-2px); border-color: var(--line);}
.v3 .vprod .ph {position: relative; aspect-ratio: 4/3; border-radius: 14px; background: var(--card-background-color); display: grid; place-items: center; overflow: hidden;}
.v3 .vprod .ph img, .v3 .vprod .ph svg {width: 76%; height: 84%; object-fit: contain;}
.v3 .vprod .rank {position: absolute; left: 8px; top: 8px; min-width: 26px; height: 26px; padding: 0 7px; border-radius: 999px; background: var(--ink); color: var(--card-background-color); font-size: 12px; font-weight: 800; display: grid; place-items: center;}
.v3 .vprod .gdot {position: absolute; right: 8px; top: 8px;}
.v3 .vprod b {font-size: 13px; line-height: 1.25; min-height: 32px;}
.v3 .vprod .meta {display: flex; justify-content: space-between; font-size: 12px; color: var(--soft); font-variant-numeric: tabular-nums;}
.v3 .vprod .meta strong {color: var(--ink);}
.v3 .range {position: relative; height: 6px; border-radius: 999px; background: color-mix(in srgb, var(--ink) 10%, transparent);}
.v3 .range i {position: absolute; top: -4px; width: 14px; height: 14px; border-radius: 50%; background: var(--card-background-color); border: 3px solid var(--rema-accent); transform: translateX(-50%);}
.v3 .range-lab {display: flex; justify-content: space-between; font-size: 11px; color: var(--soft); font-variant-numeric: tabular-nums;}
.v3 .vbadge {position: absolute; right: 8px; bottom: 8px; font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: var(--rema-tint); color: var(--rema-accent);}
.v3 .plate-wrap {display: grid; grid-template-columns: minmax(0, 300px) minmax(0, 1fr); gap: 18px; align-items: center;}
@media (max-width: 720px) {
  .v3 .plate-wrap {grid-template-columns: 1fr;}
}
.v3 .plate svg {width: 100%; height: auto; display: block;}
.v3 .share {display: grid; gap: 8px;}
.v3 .sh {display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: 10px; align-items: center;}
.v3 .sh svg {width: 30px; height: 30px;}
.v3 .sh .bar {height: 8px; border-radius: 999px; background: var(--rema-subtle); overflow: hidden; margin-top: 4px;}
.v3 .sh .bar i {display: block; height: 100%; border-radius: 999px;}
.v3 .sh b {font-size: 13.5px;}
.v3 .sh .p {font-weight: 700; font-variant-numeric: tabular-nums;}
.v3 .marks {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 12px;}
.v3 .mk {display: grid; justify-items: center; gap: 6px; text-align: center;}
.v3 .mk svg {width: 100%; max-width: 128px; height: auto;}
.v3 .mk b {font-size: 13.5px;}
.v3 .mk small {color: var(--soft); font-size: 12px;}
.v3 .plates {display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; margin-top: 12px;}
@media (max-width: 640px) {
  .v3 .plates {grid-template-columns: repeat(4, minmax(0, 1fr));}
}
.v3 .pl {display: grid; justify-items: center; gap: 6px; text-align: center;}
.v3 .pl svg {width: 100%; max-width: 74px; height: auto;}
.v3 .pl span {font-size: 11px; font-weight: 700; color: var(--soft); letter-spacing: .06em;}
.v3 .pl b {font-size: 12px; line-height: 1.25;}
.v3 .pl.today svg circle:first-child {stroke: var(--rema-accent); stroke-width: 3;}
.v3 .advice {display: grid; gap: 10px; margin-top: 10px;}
.v3 .adv {display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px 12px;}
.v3 .adv .meter {grid-column: 1 / -1; height: 8px; border-radius: 999px; background: var(--rema-subtle); overflow: hidden;}
.v3 .adv .meter i {display: block; height: 100%; background: var(--good);}
.v3 .foot {color: var(--soft); font-size: 12px; line-height: 1.5; margin-top: 10px;}
.v3 .sunpulse {animation: pulse 6s ease-in-out infinite; transform-box: fill-box; transform-origin: center;}
@keyframes pulse { 50% { transform: scale(1.12); opacity: .8; } }
.v3 .cloud {animation: drift 16s ease-in-out infinite alternate;}
.v3 .cloud.c2 {animation-duration: 22s;}
@keyframes drift { from { transform: translateX(-18px); } to { transform: translateX(18px); } }
.v3 .bob {animation: bob 4.5s ease-in-out infinite; transform-box: view-box; transform-origin: 250px 206px;}
@keyframes bob { 50% { transform: translateY(-3px) rotate(-.6deg); } }
.v3 .coin {animation: coin .5s cubic-bezier(.2,.8,.2,1) both;}
@keyframes coin { from { transform: translateY(-40px); opacity: 0; } }
.v3 .drop {animation: drop 2.6s cubic-bezier(.5,0,.75,0) infinite;}
@keyframes drop { 0% { transform: translateY(-8px); opacity: 0; } 20% { opacity: 1; } 70% { transform: translateY(40px); opacity: 1; } 71%, 100% { opacity: 0; transform: translateY(40px); } }
.v3 .col {transform-box: fill-box; transform-origin: bottom; animation: colup .8s cubic-bezier(.2,.8,.2,1) both;}
@keyframes colup { from { transform: scaleY(0); } }
.v3 .seg-arc {stroke-dasharray: 100;}
@media (max-width: 560px) {
  .v3 .wordmark {font-size: 18px;}
  .v3 .hero-top .weekpick {width: 100%; justify-content: space-between;}
  .v3 .wk {width: 44px;}
}
.v3 .bd .sel {stroke-linejoin: round; stroke-width: 1.4; opacity: .75;}
.v3 .wcenter .small {max-width: 150px;}
.v3 .dial .day {cursor: pointer; transition: opacity .25s ease;}
.v3 .dial .day.dim {opacity: .3;}
.v3 .dial .day.on .daylab {fill: var(--rema-accent);}
.v3 .dial .day.on > path:first-child {fill: var(--rema-tint);}
.v3 .bd .gs {transition: opacity .25s ease;}
.v3 .bd .gs.dim {opacity: .14;}
.v3 .buy.open {cursor: pointer; transition: border-color .2s, transform .15s;}
.v3 .buy.open:hover {border-color: var(--rema-accent);}
.v3 .buy.open:active {transform: scale(.99);}
.v3 .buy .chev {color: var(--rema-accent); font-weight: 700; font-size: 11.5px;}
.v3 .mini-g {display: flex; gap: 1.5px; height: 5px; margin-top: 5px; border-radius: 999px; overflow: hidden; max-width: 220px;}
.v3 .mini-g i {display: block; height: 100%;}
.v3 .paper {position: relative; width: min(100%, 400px); max-height: calc(100dvh - 40px); overflow: auto; padding: 22px 22px 28px; border-radius: 6px 6px 0 0;
  background: #FFFEFB; color: #1d1d1f; font: 13px ui-monospace, "SF Mono", Menlo, Consolas, monospace; box-shadow: 0 30px 60px -20px rgba(0,0,0,.5);}
:host([dark]) .v3 .paper {background: #F4F1EA;}
.v3 .paper .x {position: sticky; top: 0; float: right; width: 32px; height: 32px; margin: -8px -8px 0 0; border: 0; border-radius: 50%; background: #EEE; font-size: 20px; cursor: pointer; color: #333;}
.v3 .r-head {text-align: center; display: grid; gap: 2px; padding-bottom: 12px; border-bottom: 1.5px dashed #BBB;}
.v3 .r-logo {font: 900 22px Inter, sans-serif; letter-spacing: -.02em; color: #1d3a8a;}
.v3 .r-dim {color: #777; font-size: 12px; display: flex; justify-content: space-between; gap: 8px;}
.v3 .r-head .r-dim {justify-content: center;}
.v3 .r-groups {display: flex; gap: 2px; height: 8px; margin: 12px 0 6px; border-radius: 999px; overflow: hidden;}
.v3 .r-groups i {display: block;}
.v3 .r-legend {display: flex; flex-wrap: wrap; gap: 4px 12px; font: 600 11px Inter, sans-serif; color: #555; margin-bottom: 10px;}
.v3 .r-legend span {display: inline-flex; align-items: center; gap: 5px;}
.v3 .r-legend i {width: 8px; height: 8px; border-radius: 2px;}
.v3 .r-lines {display: grid; gap: 4px; padding: 8px 0 12px; border-bottom: 1.5px dashed #BBB;}
.v3 .r-line {display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; gap: 8px; align-items: baseline;}
.v3 .r-dot {width: 7px; height: 7px; border-radius: 2px; align-self: center;}
.v3 .r-n small {display: block; color: #888; font-size: 11.5px;}
.v3 .r-p {font-variant-numeric: tabular-nums;}
.v3 .r-off {color: #C2410C;}
.v3 .r-sum {display: grid; gap: 4px; padding-top: 10px;}
.v3 .r-sum > div {display: flex; justify-content: space-between;}
.v3 .r-total {font-weight: 800; font-size: 16px; padding: 6px 0; border-top: 1.5px solid #222; border-bottom: 1.5px solid #222; margin: 4px 0;}
.v3 .r-zig {position: absolute; left: 0; right: 0; bottom: -10px; height: 12px; background: linear-gradient(-45deg, transparent 6px, #FFFEFB 0) 0 0/12px 12px repeat-x, linear-gradient(45deg, transparent 6px, #FFFEFB 0) 0 0/12px 12px repeat-x;}
.v3 .btn {display: inline-flex; align-items: center; justify-content: center; gap: 7px; height: 40px; padding: 0 16px; border-radius: 12px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); font-weight: 650; font-size: 14px; cursor: pointer; text-decoration: none; transition: transform .15s, border-color .2s, background .2s;}
.v3 .btn:hover {border-color: var(--rema-accent);}
.v3 .btn:active {transform: scale(.97);}
.v3 .btn.primary {background: var(--rema-accent); border-color: transparent; color: var(--rema-on-accent); box-shadow: 0 8px 20px -10px var(--rema-accent);}
.v3 .btn.big {height: 48px; padding: 0 20px; font-size: 15px; border-radius: 14px;}
.v3 .i {fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; flex: none;}
.v3 .tag {display: inline-flex; align-items: center; height: 20px; padding: 0 8px; border-radius: 999px; font-size: 11px; font-weight: 700; background: var(--rema-subtle); color: var(--soft);}
.v3 .tag.t-rester {background: color-mix(in srgb, var(--g-mejeri) 14%, transparent); color: var(--g-mejeri);}
.v3 .tag.t-ude {background: color-mix(in srgb, var(--soft) 14%, transparent);}
.v3 .tag.t-frost {background: color-mix(in srgb, var(--g-drikke) 16%, transparent); color: var(--g-drikke);}
.v3 .tag.now {background: var(--rema-accent); color: var(--rema-on-accent);}
.v3 .tag.offer {background: color-mix(in srgb, var(--bad) 14%, transparent); color: var(--bad);}
.v3 .kicker.light {color: rgba(255,255,255,.8);}
.v3 .hdr {position: relative; color: #fff; overflow: hidden; isolation: isolate;}
.v3 .hdr.big {min-height: clamp(520px, 58vw, 600px);}
.v3 .hdr.small {min-height: 200px;}
.v3 .scene-wrap {position: absolute; inset: 0; z-index: -1;}
.v3 .scene-svg {width: 100%; height: 100%; display: block;}
.v3 .hdr::after {content: ""; position: absolute; inset: 0; z-index: -1; background: linear-gradient(180deg, rgba(5,10,30,.38) 0%, rgba(5,10,30,0) 34%, rgba(5,10,30,0) 62%, rgba(5,10,30,.5) 100%); pointer-events: none;}
.v3 .hdr.small::after {background: linear-gradient(90deg, rgba(5,10,30,.55), rgba(5,10,30,.05) 70%), linear-gradient(0deg, rgba(5,10,30,.45), transparent 50%);}
:host([dark]) .v3 .scene-svg {filter: brightness(.86) saturate(.95);}
.v3 .hdr-top {display: flex; align-items: center; gap: 10px; max-width: 1180px; margin: 0 auto; padding: 14px 16px 0;}
.v3 .brand {display: flex; align-items: center; gap: 10px; border: 0; background: none; color: #fff; cursor: pointer; padding: 0;}
.v3 .logo {width: 40px; height: 40px; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 22px -8px rgba(0,0,0,.6);}
.v3 .logo svg {width: 100%; height: 100%; display: block;}
.v3 .wordmark {font-family: var(--display); font-weight: 750; font-size: 23px; letter-spacing: -.03em; text-shadow: 0 2px 14px rgba(0,0,0,.35);}
.v3 .prof-wrap {position: relative;}
.v3 .prof {width: 40px; height: 40px; border-radius: 50%; border: 2px solid rgba(255,255,255,.7); background: linear-gradient(135deg, #6E4AFF, #FF7A59); color: #fff; font-weight: 800; font-size: 16px; cursor: pointer; box-shadow: 0 8px 22px -8px rgba(0,0,0,.6);}
.v3 .prof-menu {position: absolute; right: 0; top: 48px; z-index: 30; min-width: 220px; padding: 6px; border-radius: 16px; background: var(--card-background-color); color: var(--ink); border: 1px solid var(--line); box-shadow: 0 24px 48px -16px rgba(0,0,0,.4);}
.v3 .prof-menu button {display: flex; align-items: center; gap: 10px; width: 100%; padding: 10px 12px; border: 0; background: none; border-radius: 10px; font-weight: 600; font-size: 14px; cursor: pointer; text-align: left;}
.v3 .prof-menu button:hover {background: var(--rema-subtle);}
.v3 .hero-copy {max-width: 1180px; margin: 0 auto; padding: 26px 18px 0; text-shadow: 0 2px 18px rgba(0,0,0,.35);}
.v3 .hello {margin: 4px 0 0; font-family: var(--display); font-size: clamp(38px, 6.4vw, 64px); font-weight: 760; letter-spacing: -.04em; line-height: 1;}
.v3 .hero-sub {margin: 10px 0 0; font-size: clamp(15px, 1.8vw, 18px); opacity: .95; max-width: 520px;}
.v3 .page-title {max-width: 1180px; margin: 0 auto; padding: 18px 18px 0; text-shadow: 0 2px 14px rgba(0,0,0,.35);}
.v3 .page-title h1 {margin: 0; font-family: var(--display); font-size: clamp(28px, 4vw, 38px); font-weight: 760; letter-spacing: -.035em;}
.v3 .page-title p {margin: 4px 0 0; opacity: .92; font-size: 14px;}
.v3 .glass {background: rgba(14, 20, 44, .42); border: 1px solid rgba(255,255,255,.22); backdrop-filter: blur(18px) saturate(1.3); -webkit-backdrop-filter: blur(18px) saturate(1.3); border-radius: 24px; box-shadow: 0 30px 60px -30px rgba(0,0,0,.7);}
.v3 .budget-glass {position: absolute; right: max(16px, calc((100vw - 1180px) / 2 + 16px)); bottom: 70px; width: min(400px, calc(100% - 32px)); padding: 16px; display: grid; gap: 12px; animation: rise .6s .15s both;}
.v3 .hb-top {display: flex; gap: 14px; align-items: center;}
.v3 .hb-ring {width: 84px; height: 84px; flex: none;}
.v3 .hb-num {display: grid; gap: 2px;}
.v3 .hb-num b {font-family: var(--display); font-size: 34px; font-weight: 760; letter-spacing: -.035em; line-height: 1;}
.v3 .hb-num span:last-child {font-size: 13px; opacity: .85;}
.v3 .hb-days {display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px;}
.v3 .hbd {display: grid; justify-items: center; gap: 4px;}
.v3 .hbd .bar {position: relative; width: 100%; max-width: 30px; height: 40px; border-radius: 8px; background: rgba(255,255,255,.12); display: flex; flex-direction: column-reverse; overflow: hidden;}
.v3 .hbd .bar i {display: block; width: 100%;}
.v3 .hbd .bar em {position: absolute; left: 0; right: 0; top: 0; background: rgba(14,20,44,.0);}
.v3 .hbd small {font-size: 10.5px; font-weight: 700; opacity: .75;}
.v3 .hbd.now small {opacity: 1; color: #7CF2C8;}
.v3 .hbd.now .bar {box-shadow: inset 0 0 0 1.5px #7CF2C8;}
.v3 .hb-book {display: flex; gap: 8px;}
.v3 .hb-amt {flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; height: 48px; padding: 0 14px; border-radius: 14px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.26); transition: background .2s, box-shadow .2s;}
.v3 .hb-amt:focus-within {background: rgba(255,255,255,.22); box-shadow: 0 0 0 4px rgba(124,242,200,.25);}
.v3 .hb-amt input {flex: 1; min-width: 0; width: 100%; border: 0; outline: 0; background: none; color: #fff; font: 650 18px var(--ha-font-family-body);}
.v3 .hb-amt input::placeholder {color: rgba(255,255,255,.7); font-weight: 500; font-size: 15px;}
.v3 .hb-go {height: 48px; padding: 0 18px; border: 0; border-radius: 14px; background: #fff; color: #10182E; font-weight: 750; font-size: 15px; cursor: pointer;}
.v3 .hb-quick {display: flex; gap: 6px; flex-wrap: wrap; align-items: center;}
.v3 .hb-quick button {border: 1px solid rgba(255,255,255,.3); background: rgba(255,255,255,.08); color: #fff; border-radius: 999px; padding: 5px 11px; font-weight: 650; font-size: 12.5px; cursor: pointer;}
.v3 .hb-quick .hb-link {margin-left: auto; border: 0; background: none; opacity: .9;}
@media (max-width: 700px) {
  .v3 .hdr.big {min-height: 0; padding-bottom: 64px;}
  .v3 .budget-glass {position: relative; right: auto; bottom: auto; margin: 150px 16px 0; width: auto; padding: 14px; gap: 10px;}
  .v3 .hb-days {display: none;}
  .v3 .hb-num b {font-size: 28px;}
  .v3 .hb-ring {width: 64px; height: 64px;}
  .v3 .hero-copy {padding-top: 18px;}
}
.v3 .strip {display: grid; grid-auto-flow: column; grid-auto-columns: minmax(138px, 1fr); gap: 10px; margin-top: 14px; overflow-x: auto; padding: 4px 2px 10px; scroll-snap-type: x mandatory;}
.v3 .dtile {scroll-snap-align: start; position: relative; display: grid; justify-items: center; align-content: start; gap: 4px; padding: 12px 10px 12px; border-radius: 20px; border: 1px solid var(--line); background: var(--rema-subtle); cursor: pointer; text-align: center; transition: transform .2s, border-color .2s, box-shadow .2s; animation: rise .5s both;}
.v3 .dtile:hover {transform: translateY(-3px);}
.v3 .dtile.now {background: linear-gradient(180deg, var(--rema-tint), var(--rema-subtle)); border-color: var(--rema-accent); box-shadow: 0 14px 30px -18px var(--rema-accent);}
.v3 .dtile.on {border-color: var(--ink);}
.v3 .dtile.past {opacity: .62;}
.v3 .dt-day {font-size: 12px; font-weight: 750; letter-spacing: .06em; text-transform: uppercase; color: var(--soft);}
.v3 .dtile.now .dt-day {color: var(--rema-accent);}
.v3 .dt-date {font-size: 12px; color: var(--soft);}
.v3 .dish-art {width: 92px; height: 92px; margin: 4px 0; filter: drop-shadow(0 8px 10px rgba(0,0,0,.08)); transition: transform .3s;}
.v3 .dtile:hover .dish-art {transform: rotate(-8deg) scale(1.04);}
.v3 .dtile b {font-size: 13px; line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; min-height: 48px;}
.v3 .dt-meta {display: flex; gap: 6px; align-items: center; justify-content: center; flex-wrap: wrap; font-size: 11.5px; color: var(--soft);}
.v3 .plan-foot {display: flex; align-items: center; gap: 18px; flex-wrap: wrap; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line);}
.v3 .pf-stat {display: grid;}
.v3 .pf-stat b {font-family: var(--display); font-size: 22px; letter-spacing: -.02em;}
.v3 .pf-stat span {font-size: 12px; color: var(--soft);}
.v3 .quickadd {background: radial-gradient(120% 90% at 100% 0%, color-mix(in srgb, var(--rema-accent) 14%, transparent), transparent 55%), var(--rema-card);}
.v3 .cart {position: relative; width: 52px; height: 52px; border-radius: 16px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); cursor: pointer; display: grid; place-items: center;}
.v3 .cart-n {position: absolute; top: -6px; right: -6px; min-width: 22px; height: 22px; padding: 0 6px; border-radius: 999px; background: var(--rema-accent); color: var(--rema-on-accent); font-size: 12px; font-weight: 800; display: grid; place-items: center;}
.v3 .cart.pop {animation: pop .45s cubic-bezier(.3,1.6,.5,1);}
@keyframes pop { 40% { transform: scale(1.18) rotate(-6deg); } }
.v3 .qbar {display: flex; align-items: center; gap: 10px; height: 64px; margin-top: 14px; padding: 0 8px 0 18px; border-radius: 22px; background: var(--card-background-color); border: 2px solid var(--line); color: var(--soft); transition: border-color .2s, box-shadow .25s;}
.v3 .qbar:focus-within, .v3 .qbar.typing {border-color: var(--rema-accent); box-shadow: 0 0 0 6px var(--rema-tint), 0 18px 40px -24px var(--rema-accent); color: var(--rema-accent);}
.v3 .qbar input {flex: 1; min-width: 0; width: 100%; border: 0; outline: 0; background: none; color: var(--ink); font: 600 18px var(--ha-font-family-body);}
.v3 .qbar input::placeholder {color: var(--soft); font-weight: 500;}
.v3 .qgo {width: 48px; height: 48px; border-radius: 16px; border: 0; background: var(--rema-accent); color: var(--rema-on-accent); cursor: pointer; display: grid; place-items: center; flex: none;}
.v3 .qbar.small {height: 50px; border-radius: 16px; padding-left: 14px; margin-top: 12px;}
.v3 .qbar.small input {font-size: 15px;}
.v3 .qbar.small .qgo {width: 38px; height: 38px; border-radius: 12px;}
.v3 .qhits {display: grid; gap: 6px; margin-top: 8px;}
.v3 .qhit {display: grid; grid-template-columns: 44px minmax(0, 1fr) auto 32px; gap: 12px; align-items: center; padding: 6px 8px; border-radius: 14px; border: 1px solid var(--line); background: var(--card-background-color); cursor: pointer; text-align: left; animation: rise .25s both;}
.v3 .qhit:hover {border-color: var(--rema-accent);}
.v3 .qimg {width: 44px; height: 44px; border-radius: 10px; background: #fff; display: grid; place-items: center; overflow: hidden;}
.v3 .qimg img, .v3 .qimg svg {width: 86%; height: 86%; object-fit: contain;}
.v3 .qname {font-weight: 650; font-size: 14px;}
.v3 .qprice {color: var(--soft); font-size: 12.5px; font-variant-numeric: tabular-nums;}
.v3 .qplus {width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; background: var(--rema-tint); color: var(--rema-accent);}
.v3 .qchips {display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 12px;}
.v3 .qchips button {border: 1px solid var(--line); background: var(--card-background-color); border-radius: 999px; padding: 7px 13px; font-weight: 650; font-size: 13px; cursor: pointer;}
.v3 .qchips button:hover {border-color: var(--rema-accent); color: var(--rema-accent);}
.v3 .onlist {margin-top: 16px;}
.v3 .ol-chips {display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;}
.v3 .olc {display: inline-flex; align-items: center; gap: 6px; padding: 5px 6px 5px 11px; border-radius: 999px; background: var(--rema-subtle); font-size: 13px; font-weight: 600;}
.v3 .olc.fresh {background: var(--rema-tint); color: var(--rema-accent); animation: pop .4s;}
.v3 .olc button {width: 20px; height: 20px; border-radius: 50%; border: 0; background: rgba(0,0,0,.06); color: inherit; cursor: pointer; display: grid; place-items: center;}
.v3 .plan-head {background: radial-gradient(100% 60% at 0% 0%, var(--rema-tint), transparent 60%), var(--rema-card);}
.v3 .ph-grid {display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap; margin-top: 12px;}
.v3 .ph-price {text-align: right; display: grid;}
.v3 .ph-price b {font-family: var(--display); font-size: 30px; letter-spacing: -.03em;}
.v3 .ph-price span {color: var(--soft); font-size: 12.5px;}
.v3 .prows {display: grid; gap: 8px; margin-top: 14px;}
.v3 .prow {display: grid; grid-template-columns: 52px 76px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 8px 10px 8px 8px; border-radius: 20px; background: var(--rema-subtle); border: 1px solid transparent; animation: rise .45s both; transition: border-color .2s;}
.v3 .prow:hover {border-color: var(--line);}
.v3 .prow.now {background: linear-gradient(90deg, var(--rema-tint), var(--rema-subtle)); border-color: var(--rema-accent);}
.v3 .prow.past {opacity: .6;}
.v3 .pr-date {display: grid; justify-items: center; line-height: 1.05;}
.v3 .pr-date span {font-size: 10.5px; font-weight: 800; letter-spacing: .08em; color: var(--soft);}
.v3 .pr-date b {font-family: var(--display); font-size: 24px;}
.v3 .pr-date small {font-size: 11px; color: var(--soft);}
.v3 .pr-art {width: 76px; height: 76px;}
.v3 .pr-main b {font-size: 15px; line-height: 1.3;}
.v3 .pr-meta {display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 4px; font-size: 12.5px; color: var(--soft);}
.v3 .pr-tools {display: flex; gap: 4px;}
.v3 .vrate, .v3 .more-b {width: 36px; height: 36px; border-radius: 12px; border: 1px solid var(--line); background: var(--card-background-color); cursor: pointer; font-size: 15px; filter: grayscale(1); opacity: .6;}
.v3 .vrate.on {filter: none; opacity: 1; border-color: var(--rema-accent); background: var(--rema-tint);}
.v3 .more-b {filter: none; opacity: 1; font-weight: 800; color: var(--soft);}
@media (max-width: 620px) {
  .v3 .prow {grid-template-columns: 44px 60px minmax(0, 1fr);}
  .v3 .pr-art {width: 60px; height: 60px;}
  .v3 .pr-tools {grid-column: 2 / -1;}
}
.v3 .vplan-actions {display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px;}
.v3 .gen {display: grid; grid-template-columns: 76px minmax(0, 1fr); gap: 16px; background: linear-gradient(135deg, color-mix(in srgb, #6E4AFF 12%, var(--rema-card)), color-mix(in srgb, #FF7A59 10%, var(--rema-card)));}
.v3 .gen-art {width: 76px; height: 76px; border-radius: 22px; display: grid; place-items: center; color: #fff; background: linear-gradient(135deg, #6E4AFF, #FF7A59); box-shadow: 0 16px 30px -16px #6E4AFF;}
.v3 .gen-opts {display: flex; flex-wrap: wrap; gap: 10px 14px; margin: 12px 0; align-items: center; font-size: 14px;}
.v3 .gen-opts select {margin-left: 6px; height: 34px; border-radius: 10px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); padding: 0 8px; font: inherit;}
.v3 .offers-top {background: radial-gradient(110% 80% at 100% 0%, color-mix(in srgb, var(--g-kolonial) 12%, transparent), transparent 55%), var(--rema-card);}
.v3 .chainrow {display: flex; gap: 8px; overflow-x: auto; margin-top: 12px; padding-bottom: 4px;}
.v3 .vchain {flex: none; display: inline-flex; align-items: center; gap: 8px; height: 46px; padding: 0 14px 0 6px; border-radius: 16px; border: 1px solid var(--line); background: var(--card-background-color); font-weight: 650; cursor: pointer;}
.v3 .vchain.on {border-color: var(--ink);}
.v3 .mono {width: 34px; height: 34px; border-radius: 11px; display: grid; place-items: center; color: #fff; font: 800 15px var(--display); flex: none;}
.v3 .mono.big {width: 44px; height: 44px; border-radius: 14px; font-size: 19px;}
.v3 .mono.m0 {background: var(--g-mejeri);}
.v3 .mono.m1 {background: var(--g-brod); color: #2a1d00;}
.v3 .mono.m2 {background: var(--g-hjem);}
.v3 .mono.m3 {background: var(--g-drikke);}
.v3 .mono.m4 {background: var(--g-kod);}
.v3 .mono.m5 {background: var(--g-kolonial);}
.v3 .vcheaper {margin-top: 14px;}
.v3 .ch-row {display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 8px; margin-top: 8px;}
.v3 .ch-card {display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 10px; border-radius: 16px; background: var(--rema-subtle);}
.v3 .ch-card b {font-size: 13.5px;}
.v3 .ch-card small {display: block; color: var(--soft); font-size: 12px;}
.v3 .ch-card .save {font-weight: 800; color: var(--good); font-variant-numeric: tabular-nums;}
.v3 .limg {width: 44px; height: 44px; border-radius: 10px; background: #fff; border: 1px solid var(--line); display: grid; place-items: center; overflow: hidden;}
.v3 .limg img, .v3 .limg svg {width: 84%; height: 84%; object-fit: contain;}
.v3 .lname b {font-size: 14px; display: block;}
.v3 .lname small {color: var(--soft); font-size: 12px;}
.v3 .lprice {font-variant-numeric: tabular-nums; font-weight: 650;}
.v3 .compare {background: radial-gradient(100% 70% at 0% 100%, color-mix(in srgb, var(--g-drikke) 10%, transparent), transparent 60%), var(--rema-card);}
.v3 .race {display: grid; gap: 12px; margin-top: 14px;}
.v3 .lane {padding: 14px; border-radius: 20px; background: var(--rema-subtle); display: grid; gap: 10px; animation: rise .5s both;}
.v3 .ln-head {display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 12px; align-items: center;}
.v3 .ln-head b {font-size: 16px;}
.v3 .ln-head small {display: block; color: var(--soft); font-size: 12.5px;}
.v3 .ln-tot {font-family: var(--display); font-size: 24px; font-weight: 750; letter-spacing: -.02em;}
.v3 .ln-bar {display: flex; gap: 3px; height: 14px; border-radius: 999px; background: color-mix(in srgb, var(--ink) 6%, transparent); overflow: hidden;}
.v3 .ln-bar i {display: block; height: 100%; border-radius: 999px; animation: fill 1s cubic-bezier(.2,.8,.2,1) both; transform-origin: left;}
.v3 .ln-bar .fee {background: repeating-linear-gradient(45deg, var(--soft) 0 3px, transparent 3px 6px); opacity: .6;}
@keyframes fill { from { transform: scaleX(0); } }
.v3 .ln-foot {display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--soft);}
.v3 .ln-foot .up {color: var(--bad); font-weight: 700;}
.v3 .ln-foot .down {color: var(--good); font-weight: 700;}
.v3 .xfer {justify-self: start;}
.v3 .fees {margin-top: 14px;}
.v3 .fees summary {cursor: pointer; font-weight: 700;}
.v3 .fee-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 10px;}
.v3 .fee-grid label {display: grid; gap: 6px; font-size: 13px; font-weight: 650;}
.v3 .fee-grid select {height: 38px; border-radius: 10px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); padding: 0 8px; font: inherit;}
.v3 .fee-grid input[type=range] {accent-color: var(--rema-accent);}
.v3 .xsheet {position: relative; width: min(100%, 520px); max-height: calc(100dvh - 40px); overflow: auto; padding: 22px; border-radius: 24px; background: var(--card-background-color); color: var(--ink); box-shadow: 0 40px 80px -30px rgba(0,0,0,.6); animation: rise .3s both;}
.v3 .xsheet .x {position: absolute; right: 14px; top: 14px; width: 34px; height: 34px; border: 0; border-radius: 50%; background: var(--rema-subtle); color: var(--ink); font-size: 20px; cursor: pointer;}
.v3 .xprog {height: 8px; border-radius: 999px; background: var(--rema-subtle); overflow: hidden; margin: 14px 0 10px;}
.v3 .xprog i {display: block; height: 100%; width: 0; background: linear-gradient(90deg, var(--rema-accent), #7CF2C8); transition: width 1.8s cubic-bezier(.4,0,.2,1);}
.v3 .xlist {display: grid; gap: 4px;}
.v3 .xl {display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; gap: 10px; align-items: center; font-size: 14px; animation: rise .3s both;}
.v3 .xl small {color: var(--soft); font-size: 12px;}
.v3 .xdot {width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 800; color: #fff;}
.v3 .xdot.ok {background: var(--good);}
.v3 .xdot.miss {background: var(--warning-color, #E0A52E);}
.v3 .xdone {display: none; gap: 8px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line);}
.v3 .xdone.on {display: grid; animation: rise .4s both;}
.v3 .rgrid {display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; margin-top: 14px;}
.v3 .rcard {position: relative; display: grid; justify-items: center; gap: 6px; padding: 14px 12px; border-radius: 20px; border: 1px solid var(--line); background: var(--rema-subtle); cursor: pointer; text-align: center; animation: rise .4s both; transition: transform .2s, box-shadow .2s;}
.v3 .rcard:hover {transform: translateY(-3px); box-shadow: 0 18px 30px -22px rgba(0,0,0,.4);}
.v3 .rc-art {width: 104px; height: 104px; transition: transform .35s;}
.v3 .rcard:hover .rc-art {transform: rotate(10deg);}
.v3 .rcard b {font-size: 13.5px; line-height: 1.3;}
.v3 .rc-heart {position: absolute; top: 10px; right: 12px; color: var(--bad); font-size: 16px;}
.v3 .rc-heart.no {color: inherit; font-size: 13px;}
.v3 .vrc-meta {display: flex; gap: 6px; align-items: center; justify-content: center; flex-wrap: wrap; font-size: 12px; color: var(--soft);}
.v3 .fgrid {display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; margin-top: 14px;}
.v3 .fcard {display: grid; grid-template-columns: 92px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 12px; border-radius: 22px; background: var(--rema-subtle); animation: rise .45s both;}
.v3 .fc-art {width: 92px; height: 92px;}
.v3 .fcard b {font-size: 14.5px; line-height: 1.3;}
.v3 .fcard .vrc-meta {justify-content: flex-start; margin-top: 6px;}
.v3 .pantry-empty {display: grid; grid-template-columns: minmax(0, 300px) minmax(0, 1fr); gap: 20px; align-items: center;}
@media (max-width: 720px) {
  .v3 .pantry-empty {grid-template-columns: 1fr;}
}
.v3 .pantry-art {width: 100%; height: auto;}
.v3 .frost {animation: pulse 4s ease-in-out infinite; transform-box: fill-box; transform-origin: center;}
.v3 .hlist {display: grid; gap: 8px; margin-top: 14px;}
.v3 .sgrid {display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; margin-bottom: 16px;}
.v3 .stile {display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 12px; align-items: center; padding: 12px; border-radius: 18px; border: 1px solid var(--line); background: var(--rema-card); cursor: pointer; text-align: left; box-shadow: var(--ha-card-box-shadow); transition: transform .15s, border-color .2s;}
.v3 .stile:hover {transform: translateY(-2px);}
.v3 .stile.on {border-color: var(--rema-accent); box-shadow: 0 0 0 3px var(--rema-tint);}
.v3 .st-ic {width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; background: var(--rema-tint); color: var(--rema-accent);}
.v3 .stile b {display: block; font-size: 14.5px;}
.v3 .stile small {color: var(--soft); font-size: 12.5px;}
.v3 .spanel {animation: rise .35s both;}
.v3 .sw {display: flex; gap: 4px; margin-bottom: 6px;}
.v3 .sw i {width: 26px; height: 26px; border-radius: 8px;}
.v3 .tw {animation: twinkle 3.5s ease-in-out infinite;}
@keyframes twinkle { 50% { opacity: .25; } }
.v3 .steam {animation: steam 3s ease-in-out infinite;}
@keyframes steam { 0% { transform: translateY(4px); opacity: 0; } 40% { opacity: 1; } 100% { transform: translateY(-10px); opacity: 0; } }
.v3 .smoke {animation: smoke 6s ease-in-out infinite; transform-box: fill-box;}
@keyframes smoke { 0% { transform: translate(0, 6px); opacity: 0; } 30% { opacity: 1; } 100% { transform: translate(12px, -24px); opacity: 0; } }
.v3 .hdr .cloud {animation: drift 30s ease-in-out infinite alternate;}
.v3 .btn.small {height: 32px; padding: 0 12px; font-size: 13px; border-radius: 10px;}
.v3 .btn.danger {color: var(--bad); border-color: color-mix(in srgb, var(--bad) 40%, var(--line));}
.v3 .link {border: 0; background: none; padding: 0; color: var(--rema-accent); font-weight: 650; cursor: pointer; text-decoration: underline;}
.v3 .note-b {margin: 10px 0; padding: 10px 12px; border-radius: 14px; background: var(--rema-tint); color: var(--ink); font-size: 13.5px; line-height: 1.45;}
.v3 .seg.fit {display: flex; width: 100%;}
.v3 .seg.fit button {flex: 1; padding: 8px 6px;}
.v3 .fld {display: grid; gap: 6px; font-size: 13px; font-weight: 650; margin-top: 12px;}
.v3 .fld.inline {display: inline-grid; margin: 0;}
.v3 .fld .row input {flex: 1;}
@keyframes spinin { from { transform: rotate(-40deg) scale(.7); opacity: 0; } }
.v3 .prow {grid-template-columns: minmax(0, 1fr) auto; padding: 0 10px 0 0;}
.v3 .pr-open {display: grid; grid-template-columns: 52px 76px minmax(0, 1fr); gap: 12px; align-items: center; padding: 8px; border: 0; background: none; color: inherit; text-align: left; cursor: pointer; border-radius: 20px; min-width: 0;}
.v3 .pr-open:hover .pr-art {transform: rotate(-8deg);}
.v3 .pr-art {transition: transform .3s;}
@media (max-width: 620px) {
  .v3 .prow {grid-template-columns: 1fr; padding: 0 0 8px;}
  .v3 .pr-open {grid-template-columns: 44px 60px minmax(0, 1fr);}
  .v3 .pr-tools {padding-left: 8px;}
}
.v3 .gen {align-items: start;}
.v3 .gen-body {min-width: 0;}
.v3 .gen-row {margin: 14px 0 10px;}
.v3 .wish {padding: 12px; border-radius: 18px; background: var(--card-background-color); border: 1px solid var(--line);}
.v3 .wish.has {border-color: var(--rema-accent);}
.v3 .wish-h {display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: 10px; align-items: center;}
.v3 .wish-ic {font-size: 22px;}
.v3 .wish-h small {display: block; color: var(--soft); font-size: 12.5px;}
.v3 .wish-note {margin: 8px 0 0; padding: 8px 12px; border-radius: 12px; background: var(--rema-tint); font-style: italic;}
.v3 .tailor {margin-top: 10px; padding: 12px; border-radius: 18px; background: var(--card-background-color); border: 1px solid var(--line);}
.v3 .tailor summary {cursor: pointer; display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center;}
.v3 .tailor summary small {flex-basis: 100%; color: var(--soft); font-size: 12.5px;}
.v3 .kinds {display: grid; gap: 6px; margin-top: 10px;}
.v3 .kday {display: grid; grid-template-columns: 70px minmax(0, 180px) minmax(0, 1fr); gap: 10px; align-items: center; padding: 6px 8px; border-radius: 12px; background: var(--rema-subtle);}
.v3 .kday.k-skip, .v3 .kday.k-rye {opacity: .7;}
.v3 .kd-d {font-size: 12.5px; color: var(--soft);}
.v3 .kd-d b {display: block; color: var(--ink); font-size: 12px; letter-spacing: .06em;}
.v3 .kday select, .v3 .kday input {height: 36px; border-radius: 10px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); padding: 0 8px; font: inherit; min-width: 0;}
.v3 .kd-hint {font-size: 12.5px; color: var(--soft);}
@media (max-width: 560px) {
  .v3 .kday {grid-template-columns: 56px minmax(0, 1fr);}
  .v3 .kday > :last-child {grid-column: 1 / -1;}
}
.v3 .gen-go {margin-top: 14px;}
.v3 .btn.surprise {background: linear-gradient(135deg, #FFE6D9, #EDE6FF); border-color: transparent; color: #3A2A66;}
:host([dark]) .v3 .btn.surprise {background: linear-gradient(135deg, #3A2A33, #2A2448); color: #F1EFFA;}
.v3 .freezer summary {cursor: pointer; display: grid; gap: 2px;}
.v3 .freezer summary small {color: var(--soft);}
.v3 .watch {background: radial-gradient(100% 80% at 100% 0%, color-mix(in srgb, var(--g-brod) 14%, transparent), transparent 60%), var(--rema-card);}
.v3 .watch .kicker {display: inline-flex; align-items: center; gap: 6px;}
.v3 .w-list {display: grid; gap: 6px; margin-top: 12px;}
.v3 .w-item {display: grid; grid-template-columns: 34px minmax(0, 1fr) auto auto; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 14px; background: var(--rema-subtle); animation: rise .3s both;}
.v3 .w-item svg.art, .v3 .w-item > svg {width: 34px; height: 34px;}
.v3 .w-item small {display: block; color: var(--soft); font-size: 12.5px;}
.v3 .pgrid {display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-top: 14px;}
.v3 .pgrid.small {grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));}
.v3 .pcard {position: relative; display: grid; gap: 4px; align-content: start; padding: 10px; border-radius: 18px; background: var(--rema-subtle); border: 1px solid transparent; animation: rise .4s both; transition: transform .2s, border-color .2s;}
.v3 .pcard:hover {transform: translateY(-2px); border-color: var(--line);}
.v3 .pcard.onsale {background: linear-gradient(180deg, color-mix(in srgb, var(--bad) 8%, var(--rema-subtle)), var(--rema-subtle));}
.v3 .pcard .ph {position: relative; aspect-ratio: 1; border-radius: 14px; background: #fff; display: grid; place-items: center; overflow: hidden; margin-bottom: 4px;}
.v3 .pcard .ph img, .v3 .pcard .ph svg {width: 78%; height: 78%; object-fit: contain;}
.v3 .sale-b {position: absolute; left: 8px; top: 8px; padding: 3px 8px; border-radius: 999px; background: var(--bad); color: #fff; font-size: 11.5px; font-weight: 800;}
.v3 .vbell {position: absolute; right: 8px; top: 8px; width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--line); background: rgba(255,255,255,.92); color: #6B7280; cursor: pointer; display: grid; place-items: center; transition: transform .2s, background .2s, color .2s;}
.v3 .vbell.on {background: var(--g-brod); color: #2a1d00; border-color: transparent; animation: ring .5s;}
.v3 .w-item .vbell {position: static;}
@keyframes ring { 20% { transform: rotate(18deg); } 40% { transform: rotate(-14deg); } 60% { transform: rotate(8deg); } }
.v3 .pcard b {font-size: 13px; line-height: 1.25;}
.v3 .pcard small {color: var(--soft); font-size: 11.5px; line-height: 1.3;}
.v3 .pc-price {display: flex; align-items: center; gap: 6px; margin-top: 4px;}
.v3 .pc-price .num {font-weight: 750; font-size: 14.5px;}
.v3 .pc-price .now {color: var(--bad);}
.v3 .pc-price s {color: var(--soft); font-size: 12px;}
.v3 .pc-price .add {margin-left: auto; width: 32px; height: 32px; border-radius: 10px; border: 0; background: var(--rema-accent); color: var(--rema-on-accent); cursor: pointer; display: grid; place-items: center;}
.v3 .more-grid {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 8px 18px 22px;}
.v3 .mg {display: grid; justify-items: center; gap: 8px; padding: 14px 6px; border-radius: 18px; border: 1px solid var(--line); background: var(--rema-subtle); color: var(--ink); cursor: pointer; font-size: 13px;}
.v3 .mg.on {border-color: var(--rema-accent); background: var(--rema-tint);}
@media (max-width: 700px) {
  .v3 .card {padding: 16px; border-radius: 20px; margin-bottom: 12px;}
  .v3 h2 {font-size: 20px;}
  .v3 .hdr.big {padding-bottom: 18px;}
  .v3 .hdr.small {min-height: 132px;}
  .v3 .page-title {padding-top: 12px;}
  .v3 .page-title h1 {font-size: 30px;}
  .v3 .hdr-top {padding: 12px 14px 0;}
  .v3 .logo {width: 36px; height: 36px; border-radius: 11px;}
  .v3 .wordmark {font-size: 21px;}
  .v3 .prof {width: 36px; height: 36px; font-size: 15px;}
  .v3 .hello {font-size: 40px;}
  .v3 .budget-glass {margin-top: calc(100vw - 138px);}
  .v3 .xsheet, .v3 .paper {width: 100%; max-width: none; max-height: 92dvh; border-radius: 26px 26px 0 0; padding-bottom: env(safe-area-inset-bottom); animation: sheetup .32s cubic-bezier(.2,.8,.2,1) both;}
  .v3 .paper {padding: 22px 18px calc(28px + env(safe-area-inset-bottom));}
  .v3 .xsheet {padding: 20px 18px calc(24px + env(safe-area-inset-bottom));}
  .v3 .seg.fit button {font-size: 12.5px; padding: 8px 4px;}
  .v3 .seg:not(.fit) {max-width: 100%; overflow-x: auto; scrollbar-width: none;}
  .v3 .seg:not(.fit)::-webkit-scrollbar {display: none;}
  .v3 .seg button {white-space: nowrap; flex: none; padding: 7px 13px;}
  .v3 .prow {grid-template-columns: minmax(0, 1fr); padding: 0 0 8px;}
  .v3 .pr-open {grid-template-columns: 40px 58px minmax(0, 1fr); gap: 10px; padding: 8px 8px 4px;}
  .v3 .pr-art {width: 58px; height: 58px;}
  .v3 .pr-main b {font-size: 14px;}
  .v3 .pr-tools {grid-column: auto; justify-content: flex-end; padding: 0 8px;}
  .v3 .vrate, .v3 .more-b {width: 34px; height: 34px;}
  .v3 .ph-grid {display: grid;}
  .v3 .ph-price {text-align: left;}
  .v3 .vplan-actions .btn {flex: 1 1 auto;}
  .v3 .gen {grid-template-columns: 1fr;}
  .v3 .gen-art {width: 56px; height: 56px; border-radius: 18px;}
  .v3 .wish-h {grid-template-columns: 30px minmax(0, 1fr);}
  .v3 .wish-h .btn {grid-column: 1 / -1; width: 100%;}
  .v3 .gen-go .btn {flex: 1 1 auto;}
  .v3 .strip {grid-auto-columns: 132px; margin: 12px -16px 0; padding: 4px 16px 10px; scroll-padding: 16px;}
  .v3 .plan-foot {gap: 14px;}
  .v3 .plan-foot .spacer {display: none;}
  .v3 .plan-foot .btn, .v3 .plan-foot .pill {flex: 1 1 auto;}
  .v3 .qbar {height: 56px; padding-left: 14px;}
  .v3 .qbar input {font-size: 16px;}
  .v3 .qgo {width: 42px; height: 42px;}
  .v3 .pgrid, .v3 .pgrid.small, .v3 .rgrid {grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;}
  .v3 .pcard {padding: 8px;}
  .v3 .pcard b {font-size: 12.5px;}
  .v3 .rcard {padding: 12px 8px;}
  .v3 .rc-art {width: 84px; height: 84px;}
  .v3 .rcard b {font-size: 12.5px;}
  .v3 .fgrid {grid-template-columns: 1fr;}
  .v3 .fcard {grid-template-columns: 72px minmax(0, 1fr) auto;}
  .v3 .fc-art {width: 72px; height: 72px;}
  .v3 .shelf {grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;}
  .v3 .podium {gap: 8px;}
  .v3 .pod b {font-size: 12px;}
  .v3 .pod .pstep {font-size: 20px;}
  .v3 .sgrid {grid-template-columns: 1fr; gap: 8px;}
  .v3 .more-grid {grid-template-columns: repeat(3, minmax(0, 1fr));}
  .v3 .ch-row {grid-template-columns: 1fr;}
  .v3 .line .tag.offer {grid-column: 3; grid-row: 2; justify-self: start; margin-top: -4px;}
  .v3 .lprice {grid-row: 1; grid-column: 4;}
  .v3 .limg {width: 40px; height: 40px;}
  .v3 .ln-tot {font-size: 20px;}
  .v3 .bcenter {inset: 32%;}
  .v3 .bcenter .big {font-size: 22px;}
  .v3 .bcenter .lab {font-size: 9.5px;}
  .v3 .bcenter .meta, .v3 .bcenter .saved {font-size: 10.5px;}
  .v3 .minidays {height: 18px;}
  .v3 .minidays i {width: 6px;}
  .v3 .minilab span {width: 6px; font-size: 6px;}
  .v3 .wcenter .big {font-size: 28px;}
  .v3 .wcenter .small {font-size: 11.5px;}
  .v3 .weekpick {width: 100%; justify-content: space-between;}
  .v3 .wk {width: 15%;}
  .v3 .stats4 {gap: 6px;}
  .v3 .stat b {font-size: 17px;}
  .v3 .huge {font-size: 32px;}
  .v3 .plates {grid-template-columns: repeat(4, minmax(0, 1fr));}
  .v3 .adv {grid-template-columns: 1fr;}
  .v3 .adv .sub {margin: 0;}
  .v3 .marks {gap: 6px;}
  .v3 .mk b {font-size: 12.5px;}
  .v3 .mk small {font-size: 11px;}
  .v3 .kday {grid-template-columns: 52px minmax(0, 1fr);}
  .v3 .kday > :last-child {grid-column: 1 / -1;}
}
@keyframes sheetup { from { transform: translateY(40%); opacity: .4; } }
@media (max-width: 380px) {
  .v3 .hello {font-size: 34px;}
  .v3 .pgrid, .v3 .rgrid {gap: 8px;}
}
@media (max-width: 700px) {
  .v3 .pr-tools {justify-content: flex-start; padding: 0 8px 0 116px; margin-top: -6px;}
}
  /* ===================== Middagsro 3: the street, the clocks, the plates ===================== */
  :host { --ink: var(--primary-text-color); --soft: var(--secondary-text-color); --line: var(--divider-color);
    --good: var(--success-color, #0E9F6E); --bad: var(--error-color, #E34948);
    --display: "Inter Display", Inter, var(--ha-font-family-body, system-ui), sans-serif;
    --v3-ink: var(--ink); --v3-soft: var(--soft); --v3-good: var(--good); --v3-bad: var(--bad); --v3-display: var(--display);
    /* Varegrupper: eight hues in a fixed, validated order. */
    --g-mejeri: #2a78d6; --g-kolonial: #eb6834; --g-drikke: #1baf7a; --g-brod: #eda100;
    --g-snacks: #e87ba4; --g-frugt: #008300; --g-hjem: #6250d6; --g-kod: #e34948; --g-none: #A9B2C3; }
  :host([dark]) { --g-mejeri: #3987e5; --g-kolonial: #d95926; --g-drikke: #199e70; --g-brod: #c98500;
    --g-snacks: #d55181; --g-frugt: #0ca30c; --g-hjem: #9085e9; --g-kod: #e66767; --g-none: #4A556B; }
  :host([look="hverdag"]) { --display: Figtree, var(--ha-font-family-body, system-ui), sans-serif; }
  :host([embed]) .hdr-host { display: none !important; }

  /* The header: the street, alive. The toolbar and the tabs live in it. */
  .hdr-host { position: relative; z-index: 5; }
  .hdr .toolbar { position: relative; top: auto; z-index: 2; max-width: 1180px; margin: 0 auto; height: auto;
    min-height: calc(60px + var(--rema-safe-top, 0px)); padding: calc(10px + var(--rema-safe-top, 0px)) 16px 0;
    background: none; border: 0; color: #fff; --app-header-text-color: #fff; --sidebar-icon-color: #fff; }
  .hdr .toolbar ha-menu-button { color: #fff; }
  .hdr .brand { cursor: pointer; border-radius: 14px; }
  .hdr .brand:focus-visible { outline: 2px solid #fff; outline-offset: 3px; }
  .hdr .logo { width: 40px; height: 40px; border-radius: 12px; background: none; box-shadow: 0 8px 22px -8px rgba(0,0,0,.6); }
  .hdr .wordmark { color: #fff; font-family: var(--display); font-weight: 750; font-size: 23px; letter-spacing: -.03em; text-shadow: 0 2px 14px rgba(0,0,0,.35); }
  .hdr .prof { width: 40px; height: 40px; border: 2px solid rgba(255,255,255,.75); background: linear-gradient(135deg, #6E4AFF, #FF7A59); color: #fff; font-weight: 800; font-size: 16px; box-shadow: 0 8px 22px -8px rgba(0,0,0,.6); }
  .hdr .prof-menu { z-index: 30; color: var(--primary-text-color); text-shadow: none; }
  .hdr #busy { color: #fff; }
  .hdr .timer-chip:not(:empty) { position: fixed; top: calc(12px + var(--rema-safe-top, 0px)); right: 70px; z-index: 7; box-shadow: 0 8px 20px -8px rgba(0,0,0,.5); }

  .v3 .hdr .page-title, .v3 .hdr .hero-copy { padding-left: 18px; padding-right: 18px; }
  .v3 .hdr.small { min-height: 206px; }
  .v3 .hdr.small .page-title { padding-bottom: 64px; }
  .v3 .page-title p b { font-weight: 700; }
  @media (min-width: 701px) {
    .hdr nav.tabs { position: absolute; left: 0; right: 0; bottom: 0; top: auto; z-index: 3; max-width: 1180px; margin: 0 auto;
      padding: 0 12px 12px; background: none; border: 0; gap: 4px; scrollbar-width: none; }
    .hdr nav.tabs::-webkit-scrollbar { display: none; }
    .hdr nav.tabs .tab { flex: none; height: 40px; padding: 0 14px; margin: 0; border: 0; border-radius: 999px; background: rgba(255,255,255,.14); color: #fff;
      font-weight: 650; font-size: 14px; -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); }
    .hdr nav.tabs .tab:hover { background: rgba(255,255,255,.26); }
    .hdr nav.tabs .tab.active { background: #fff; color: #10182E; box-shadow: 0 10px 24px -12px rgba(0,0,0,.6); }
    .hdr nav.tabs .tab.customize { margin-left: auto; background: none; -webkit-backdrop-filter: none; backdrop-filter: none; opacity: .85; }
    .more-sheet:not([hidden]) { top: 120px; }
  }
  /* A phone: the street stays, the tabs float at the bottom like the iPhone's own bar. */
  @media (max-width: 700px) {
    :host { --rema-tabbar: calc(78px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); }
    .hdr nav.tabs { left: 10px; right: 10px; bottom: calc(10px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); padding: 6px; gap: 2px;
      border-radius: 26px; border: 1px solid var(--divider-color); border-top: 1px solid var(--divider-color);
      background: color-mix(in srgb, var(--card-background-color) 82%, transparent);
      -webkit-backdrop-filter: blur(20px) saturate(1.5); backdrop-filter: blur(20px) saturate(1.5); box-shadow: 0 18px 40px -18px rgba(0,0,0,.45); }
    .hdr nav.tabs .tab { color: var(--secondary-text-color); border-radius: 20px; padding: 7px 2px 6px; font-size: 10.5px; font-weight: 650; }
    .hdr nav.tabs .tab.active { color: var(--rema-accent); background: var(--rema-tint); }
    .hdr nav.tabs .tab.active svg { stroke-width: 2.2; }
    .hdr .toolbar { padding: calc(8px + var(--rema-safe-top, 0px)) 10px 0; min-height: 0; gap: 6px; }
    .hdr .logo { width: 36px; height: 36px; border-radius: 11px; }
    .hdr .wordmark { font-size: 21px; }
    .hdr .prof { width: 36px; height: 36px; font-size: 15px; }
    .v3 .hdr.small { min-height: 132px; }
    .v3 .hdr.small .page-title { padding-bottom: 18px; }
    .hdr .timer-chip:not(:empty) { right: 58px; }
  }

  /* Text drawn in the clocks. */
  .v3 .dial .dayval { font: 750 9.5px var(--ha-font-family-body, sans-serif); fill: var(--ink); }
  .v3 .dial .overval { font: 800 11px var(--ha-font-family-body, sans-serif); fill: var(--bad); }
  .v3 .dial .nowlab { font: 700 9.5px var(--ha-font-family-body, sans-serif); fill: var(--soft); }
  .v3 .years .ylab { font: 700 10.5px var(--ha-font-family-body, sans-serif); fill: var(--ink); }
  .v3 .years .yname { font: 650 11px var(--ha-font-family-body, sans-serif); fill: var(--soft); }
  .v3 .pl-big { font: 750 20px var(--display); fill: var(--ink); }
  .v3 .pl-small { font: 650 9.5px var(--ha-font-family-body, sans-serif); fill: var(--soft); }
  .v3 .ax { font: 600 9.5px var(--ha-font-family-body, sans-serif); fill: var(--soft); }
  .v3 .axv { font: 700 10.5px var(--ha-font-family-body, sans-serif); fill: var(--ink); }
  .v3 .hero-week { background: radial-gradient(120% 70% at 50% -10%, color-mix(in srgb, var(--rema-accent) 16%, transparent), transparent 60%), var(--rema-card); }
  .v3 .dial .day { cursor: pointer; }
  .v3 .buy { width: 100%; text-align: left; font: inherit; color: inherit; border: 1px solid var(--line); background: var(--card-background-color); }
  .v3 .buy .amt { text-align: right; }
  .v3 .note-line { margin-top: 8px; }
  .v3 .more-book { font-size: 13.5px; }
  .v3 .more-book summary { cursor: pointer; color: var(--soft); font-weight: 650; }
  .v3 .more-book .book { padding: 8px 0 0; background: none; }
  .v3 .lg, .v3 .tile { font: inherit; color: inherit; text-align: left; cursor: pointer; }
  .v3 .tile { border: 1px solid transparent; display: block; width: 100%; }
  .v3 .qname small { display: block; color: var(--soft); font-weight: 500; font-size: 12px; }
  .v3 .qhit { width: 100%; text-align: left; font: inherit; color: inherit; cursor: pointer; }
  .v3 .dtile { font: inherit; color: inherit; cursor: pointer; }
  .v3 .dtile.skipped { opacity: .55; }
  .v3 .plan-home { background: radial-gradient(110% 80% at 0% 0%, var(--rema-tint), transparent 60%), var(--rema-card); }
  .v3-section { margin: 26px 4px 10px; font-size: 13px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--secondary-text-color); }
  /* Redrawn without a change: no animation again. */
  .v3 .still, .v3 .still *, .v3.still, .v3.still * { animation: none !important; }
  .v3-fly { position: fixed; z-index: 50; padding: 6px 12px; border-radius: 999px; background: var(--rema-accent); color: var(--rema-on-accent); font-weight: 700; font-size: 13px; pointer-events: none; transition: transform .6s cubic-bezier(.5,-0.3,.6,1), opacity .6s; }
  /* The receipt and the basket, as sheets. */
  .v3-sheet { position: fixed; inset: 0; z-index: 21; display: grid; place-items: center; padding: 20px; pointer-events: none; }
  .v3-sheet > * { pointer-events: auto; }
  .v3 .xsheet .x, .v3 .paper .x { cursor: pointer; }
  .v3 .xl small { margin-left: 2px; }
  @media (max-width: 700px) { .v3-sheet { padding: 0; place-items: end stretch; } }

  /* Madplan: the dishes drawn on their plates. */
  .day.art { grid-template-columns: 56px 130px minmax(0, 1fr) auto; }
  .day .d-art { width: 56px; height: 56px; transition: transform .3s; filter: drop-shadow(0 4px 6px rgba(0,0,0,.06)); }
  .day.art:hover .d-art { transform: rotate(-8deg); }
  @media (max-width: 700px) {
    .day.art { grid-template-columns: 52px minmax(0, 1fr); column-gap: 12px; row-gap: 2px; }
    .day.art .d-art { grid-row: 1 / span 3; width: 52px; height: 52px; align-self: center; }
  }
  .dialog-top.day-hero { display: grid; grid-template-columns: 84px minmax(0, 1fr) auto; gap: 14px; align-items: center; }
  .day-hero .dlg-art { width: 84px; height: 84px; animation: spinin .6s cubic-bezier(.2,.8,.2,1) both; }
  .day-hero h2 { margin: 0; }
  @media (max-width: 700px) { .dialog-top.day-hero { grid-template-columns: 64px minmax(0, 1fr) auto; } .day-hero .dlg-art { width: 64px; height: 64px; } }
  /* Popups become sheets from the bottom on a phone, like on iPhone. */
  @media (max-width: 700px) {
    .dialog { left: 0; right: 0; top: auto; bottom: 0; transform: none; width: 100%; max-height: 92dvh; border-radius: 24px 24px 0 0;
      padding-bottom: calc(18px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); animation: sheetup .3s cubic-bezier(.2,.8,.2,1) both; }
  }

  /* Keep the screen on, as a switch. */
  .v3-wake { display: grid; grid-template-columns: 36px minmax(0, 1fr) 46px; gap: 10px; align-items: center; width: 100%; margin: 10px 0 4px; padding: 10px 12px;
    border-radius: 16px; border: 1px solid var(--divider-color); background: var(--rema-subtle); color: var(--primary-text-color); text-align: left; font: inherit; cursor: pointer; }
  .v3-wake .wk-sun { width: 36px; height: 36px; border-radius: 12px; display: grid; place-items: center; font-size: 19px; background: var(--card-background-color); transition: transform .4s, background .3s; }
  .v3-wake b { display: block; font-size: 14px; }
  .v3-wake small { color: var(--secondary-text-color); font-size: 12px; }
  .v3-wake .wk-sw { width: 46px; height: 28px; border-radius: 999px; background: color-mix(in srgb, var(--primary-text-color) 18%, transparent); position: relative; transition: background .3s; }
  .v3-wake .wk-sw i { position: absolute; left: 3px; top: 3px; width: 22px; height: 22px; border-radius: 50%; background: #fff; box-shadow: 0 2px 6px rgba(0,0,0,.25); transition: transform .3s cubic-bezier(.3,1.4,.5,1); }
  .v3-wake.on { background: color-mix(in srgb, var(--g-brod) 18%, var(--rema-subtle)); border-color: var(--g-brod); }
  .v3-wake.on .wk-sun { background: var(--g-brod); transform: rotate(90deg); }
  .v3-wake.on .wk-sw { background: var(--g-brod); }
  .v3-wake.on .wk-sw i { transform: translateX(18px); }
  @media (prefers-reduced-motion: reduce) { .v3 *, .v3-wake * { animation: none !important; transition: none !important; } }
  /* The panel's own .num is a step badge; here it only means tabular figures. */
  :where(.v3) .num { flex: initial; width: auto; height: auto; border-radius: 0; background: none; color: inherit; display: revert; font-size: inherit; align-items: initial; justify-content: initial; }
  #hdr-body { position: static; }
  #hdr-body > * { position: relative; z-index: 1; }
  .v3 #hdr-body > .budget-glass { position: absolute; }
  @media (max-width: 700px) { .v3 #hdr-body > .budget-glass { position: relative; } }
  :where(.v3) button { font-family: inherit; color: inherit; }
  /* ---- 3.0.0b2: the rest of the prototype ---- */
  .v3 .seg button.active { background: var(--card-background-color); color: var(--ink); box-shadow: 0 1px 3px rgba(0,0,0,.14); }
  .v3 .seg button { cursor: pointer; }
  .v3 h1 { margin: 2px 0 0; font-family: var(--display); font-size: 22px; font-weight: 650; letter-spacing: -.02em; }
  /* Madplan */
  .v3 .pr-open { width: 100%; font: inherit; color: inherit; text-align: left; cursor: pointer; border-radius: 18px; }
  .v3 .pr-main b { display: block; }
  .v3 .vrate { font-size: 15px; }
  .v3 .vrate:disabled { opacity: .4; }
  .v3 .prow.skipped .pr-art { opacity: .6; }
  .v3 .pr-past { margin-top: 10px; }
  .v3 .pr-past > summary { cursor: pointer; color: var(--soft); font-weight: 650; font-size: 13.5px; padding: 6px 2px; }
  .v3 .pr-past .prows { margin-top: 6px; }
  .v3 .ph-price.over b { color: var(--bad); }
  .v3 .plan-head .banner { margin-top: 12px; }
  .v3 .plan-head .help-q { vertical-align: middle; }
  .v3 .vplan-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; align-items: center; }
  .v3 .vplan-actions .later { flex-basis: 100%; margin: 0; }
  .v3 .tag.t-new { background: color-mix(in srgb, var(--warning-color, #E0A52E) 18%, transparent); color: color-mix(in srgb, var(--warning-color, #E0A52E) 70%, var(--ink)); }
  .v3 .tag.t-veg, .v3 .tag.t-vegetar { background: color-mix(in srgb, var(--g-frugt) 14%, transparent); color: var(--g-frugt); }
  .v3 .tag.t-egen { background: color-mix(in srgb, var(--soft) 14%, transparent); }
  .v3 .gen .gen-art .ai { width: 34px; height: 34px; fill: #fff; stroke: none; }
  .v3 .gen .btn .ai { width: 18px; height: 18px; fill: currentColor; }
  .v3 .gen .check { display: flex; gap: 8px; margin-top: 10px; font-size: 13.5px; }
  .v3 .kday .btn.small { justify-self: start; }
  .v3 .freezer > summary { list-style: none; }
  .v3 .freezer > summary::-webkit-details-marker { display: none; }
  .v3 .freezer[open] > summary { margin-bottom: 10px; }
  .v3 .cat-line { margin: 0 4px 12px; font-size: 12.5px; }
  .day-move { margin-top: 12px; gap: 8px; }
  .day-move .muted { margin-right: 4px; }
  /* Opskrifter */
  .v3 .rcard { padding: 0 0 10px; }
  .v3 .rcard .rc-open { display: grid; justify-items: center; gap: 6px; width: 100%; padding: 14px 12px 6px; border: 0; background: none; font: inherit; color: inherit; cursor: pointer; text-align: center; }
  .v3 .rcard .rate { justify-content: center; display: flex; }
  .v3 .vrc-meta { display: flex; gap: 6px; align-items: center; justify-content: center; flex-wrap: wrap; font-size: 12px; color: var(--soft); }
  .v3 .sortf select { height: 34px; border-radius: 10px; border: 1px solid var(--line); background: var(--card-background-color); color: var(--ink); padding: 0 8px; font: inherit; }
  .v3 .qx { width: 30px; height: 30px; border: 0; border-radius: 50%; background: var(--rema-subtle); color: var(--soft); cursor: pointer; font-size: 17px; flex: none; }
  .v3 .rc-list { margin-top: 4px; }
  /* Indkøb */
  .v3 .vchain .chain-logo { width: 34px; height: 34px; }
  .v3 .ch-card { width: 100%; text-align: left; font: inherit; color: inherit; cursor: pointer; border: 1px solid transparent; }
  .v3 .ch-card:hover { border-color: var(--rema-accent); }
  .v3 .ch-card .chain-logo { width: 34px; height: 34px; }
  .v3 .offers-top .ev-out:not(:empty) { margin-top: 12px; }
  .shopv .card { border-radius: var(--ha-card-border-radius, 20px); padding: 18px; }
  .shopv .kicker { font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--secondary-text-color); }
  .shopv .shop-card h1, .shopv .card > .row > h2, .shopv .card > .row h2 { margin: 2px 0 0; font-family: var(--display); font-size: 22px; font-weight: 650; letter-spacing: -.02em; }
  .shopv .shop-card > h2 { margin: 16px 0 4px; font-size: 11px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--secondary-text-color); }
  .shopv .lines .line { grid-template-columns: 44px minmax(0, 1fr) auto; gap: 10px; padding: 7px 6px; border: 0; border-radius: 12px; }
  .shopv .lines .line.has-send { grid-template-columns: 44px minmax(0, 1fr) auto 32px; }
  .shopv .limg { width: 44px; height: 44px; border-radius: 10px; background: #fff; border: 1px solid var(--divider-color); display: grid; place-items: center; overflow: hidden; flex: none; }
  .shopv .limg img, .shopv .limg svg { width: 84%; height: 84%; object-fit: contain; border: 0; background: none; border-radius: 0; }
  .shopv .line .what b { font-size: 14px; }
  .shopv .line .what .muted { font-size: 12px; }
  .shopv .line .cost { font-size: 11.5px; }
  .shopv .line .cost b { font-size: 15px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .shopv ul.rema { display: grid; gap: 2px; }
  .shopv ul.rema li { display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 10px; align-items: center; padding: 6px 4px; border-radius: 12px; }
  .shopv ul.rema li.bought { opacity: .45; }
  .shopv ul.rema li.bought .lname b { text-decoration: line-through; }
  .shopv .lname b { display: block; font-size: 14px; } .shopv .lname small { color: var(--secondary-text-color); font-size: 12px; }
  @media (max-width: 700px) {
    .shopv .lines .line { grid-template-columns: 40px minmax(0, 1fr) auto; }
    .shopv .lines .line .cost { grid-column: auto; text-align: right; flex-direction: column; gap: 0; }
    .shopv .lines .line.has-send { grid-template-columns: 40px minmax(0, 1fr) auto 30px; }
    .shopv .lines .line.has-send .to-rema-line { grid-column: 4; grid-row: auto; }
    .shopv .limg { width: 40px; height: 40px; }
  }
  /* Favoritter */
  .v3.favv .watch-card { background: radial-gradient(100% 80% at 100% 0%, color-mix(in srgb, var(--g-brod) 14%, transparent), transparent 60%), var(--rema-card); }
  .v3.favv .watch-title { font-size: 22px; }
  .v3.favv .pgrid { margin-top: 14px; }
  .v3 .pcard .vbell { position: absolute; right: 8px; top: 8px; }
  .v3 .pcard .vbell svg { width: 15px; height: 15px; }
  .v3 .pcard .ph img, .v3 .pcard .ph > svg { width: 78%; height: 78%; object-fit: contain; }
  .v3 .pcard .pc-tags { display: flex; flex-wrap: wrap; gap: 4px; font-size: 11.5px; }
  .v3 .pcard .pc-tags:empty { display: none; }
  .v3 .pcard .pc-price .add svg { width: 16px; height: 16px; }
  .v3.favv .favlist, .v3.favv details > summary { margin-top: 4px; }
  .v3.favv details > summary { cursor: pointer; font-weight: 650; }
  /* Indstillinger */
  .v3 .stile { font: inherit; color: inherit; text-align: left; cursor: pointer; width: 100%; }
  .v3 .st-ic svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  /* The Mere sheet: tiles, as in the prototype. */
  .more-sheet .ms-top { display: flex; align-items: center; justify-content: space-between; padding: 6px 8px 10px; }
  .more-sheet .ms-top h2 { margin: 0; font-family: var(--display); font-size: 21px; letter-spacing: -.02em; }
  .more-sheet .ms-x { width: 34px; height: 34px; border: 0; border-radius: 50%; background: var(--rema-subtle); color: var(--primary-text-color); font-size: 19px; cursor: pointer; }
  .more-sheet .ms-grab { display: none; }
  .more-sheet .more-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 0 8px 8px; }
  .more-sheet .more-item.mg { display: grid; justify-items: center; gap: 8px; padding: 14px 6px; border-radius: 18px; border: 1px solid var(--divider-color); background: var(--rema-subtle); color: var(--primary-text-color); text-align: center; font-size: 13.5px; }
  .more-sheet .more-item.mg b { font-weight: 650; }
  .more-sheet .more-item.mg.active { border-color: var(--rema-accent); background: var(--rema-tint); color: var(--rema-accent); }
  .more-sheet .st-ic { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; background: var(--rema-tint); color: var(--rema-accent); }
  .more-sheet .st-ic svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
  .more-sheet .ms-custom { display: block; margin: 4px auto 6px; border: 0; background: none; color: var(--secondary-text-color); font: inherit; font-size: 13px; text-decoration: underline; cursor: pointer; }
  .more-sheet:not([hidden]) { width: min(420px, calc(100vw - 24px)); padding: 10px; border-radius: 24px; }
  .more-scrim:not([hidden]) { background: rgba(8,14,28,.35); }
  @media (max-width: 700px) {
    .more-sheet:not([hidden]) { left: 0; right: 0; bottom: 0; width: 100%; max-height: 80dvh; border-radius: 26px 26px 0 0; border-bottom: 0;
      padding: 8px 10px calc(18px + var(--rema-safe-bottom, env(safe-area-inset-bottom, 0px))); z-index: 22; animation: sheetup .3s cubic-bezier(.2,.8,.2,1) both; }
    .more-scrim:not([hidden]) { z-index: 21; }
    .more-sheet .ms-grab { display: block; width: 40px; height: 5px; border-radius: 999px; background: color-mix(in srgb, var(--primary-text-color) 20%, transparent); margin: 2px auto 6px; }
    .more-sheet .more-item.mg { display: grid; }
    .more-sheet .more-item.mg.mobile-primary { display: none; }
  }
  @media (min-width: 701px) { .more-sheet .more-item.mg.desktop-primary { display: none; } }
  /* Spisekammer */
  .v3 .pantry-empty { margin-bottom: 16px; }
  /* Drag and drop in the plan: a handle you can see. */
  .v3 .prow.has-drag { grid-template-columns: 36px minmax(0, 1fr) auto; padding-left: 0; }
  .v3 .pr-drag { align-self: stretch; display: grid; place-items: center; cursor: grab; touch-action: none; user-select: none; -webkit-user-select: none;
    color: color-mix(in srgb, var(--rema-accent) 70%, var(--soft)); border-radius: 18px 0 0 18px;
    background: color-mix(in srgb, var(--rema-accent) 9%, transparent); border-right: 1.5px dashed color-mix(in srgb, var(--rema-accent) 40%, transparent); }
  .v3 .pr-drag svg { width: 12px; height: 20px; }
  .v3 .pr-drag:hover { color: var(--rema-accent); background: var(--rema-tint); }
  .v3 .pr-drag:active { cursor: grabbing; }
  .v3 .prows.dnd .prow { animation-fill-mode: backwards; }
  .v3 .prows.dragging { user-select: none; -webkit-user-select: none; }
  .v3 .prows.dragging .prow:not(.dragging) { transition: transform .18s ease; }
  .v3 .prow.dragging { position: relative; z-index: 6; cursor: grabbing; background: var(--card-background-color); border-color: var(--rema-accent);
    box-shadow: 0 22px 44px -18px rgba(0,0,0,.55), 0 0 0 2px var(--rema-tint); }
  .v3 .prow.dragging .pr-drag { color: var(--rema-on-accent); background: var(--rema-accent); }
  .v3 .dnd-hint { display: flex; align-items: center; gap: 10px; margin: 14px 0 0; padding: 9px 12px; border-radius: 14px; font-size: 12.5px; color: var(--soft);
    background: color-mix(in srgb, var(--rema-accent) 6%, transparent); border: 1.5px dashed color-mix(in srgb, var(--rema-accent) 35%, transparent); }
  .v3 .dnd-ic { flex: none; width: 26px; height: 30px; border-radius: 8px; display: grid; place-items: center; color: var(--rema-accent); background: var(--rema-tint); }
  .v3 .dnd-ic svg { width: 10px; height: 18px; }
  @media (max-width: 700px) {
    .v3 .prow.has-drag { grid-template-columns: 32px minmax(0, 1fr); padding: 0 0 8px; }
    .v3 .prow.has-drag .pr-drag { grid-row: 1 / span 2; }
    .v3 .prow.has-drag .pr-tools { grid-column: 2; padding-left: 84px; }
  }

`;
const STYLE = STYLE_BASE + V3_STYLE;

if (!customElements.get("middagsro-panel")) customElements.define("middagsro-panel", Rema1000Panel);

// For the dashboard cards (middagsro-cards.js), which use the panel's own drawing.
export { Rema1000Panel, STYLE, TAB_ICONS, TYPE_LABELS, WEEKDAYS, esc, kr, kr0, dateLabel, shortDate, sentWhen, localToday };
