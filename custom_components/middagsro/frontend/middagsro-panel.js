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
const TYPE_LABELS = { normal: "", vegetar: "Vegetar", rester: "Rester", fast: "Fast dag", tom: "Ingen ret" };
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
  plan: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4M7.5 14h3M13.5 14h3M7.5 17h3"/></svg>',
  recipes: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7.5c-1.6-1.6-4.3-2.3-8-2.2v12.5c3.7-.1 6.4.6 8 2.2 1.6-1.6 4.3-2.3 8-2.2V5.3c-3.7-.1-6.4.6-8 2.2zM12 7.5V20"/></svg>',
  shopping: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2.2l2.3 10.3a1 1 0 0 0 1 .7h8.9a1 1 0 0 0 1-.8L20 8H6.3"/><circle cx="9.5" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/></svg>',
  favorites: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7a4.3 4.3 0 0 1 7.5 2.8C19.5 15.4 12 20 12 20z"/></svg>',
  health: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h4l2-5 4 10 2-5h6"/></svg>',
  history: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>',
  settings: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg>',
  budget: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5h14.5a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18V6.5A1.5 1.5 0 0 1 5.5 5H17"/><path d="M16 12.5h4v3h-4a1.5 1.5 0 0 1 0-3z"/></svg>',
};
// On a phone the bottom bar shows the first tabs; the rest sit behind "Mere".
const EXTRA_TABS = new Set(["budget", "health", "history", "settings"]);
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
const RECIPE_FILTERS = { all: "Alle", favorite: "Favoritter", like: "Synes om", dislike: "Synes ikke om" };
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
  ["plan", "Madplan"],
  ["recipes", "Opskrifter"],
  ["shopping", "Indkøb"],
  ["favorites", "Favoritter"],
  ["budget", "Økonomi"],
  ["health", "Sundhed"],
  ["history", "Historik"],
  ["settings", "Indstillinger"],
];

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
      summary: shop.rema ? "REMA 1000 · priser på alle varer og REMA-appens liste" : shop.bilka_cart ? `BilkaToGo · ${shop.pickup_name} · kurv i appen` : `${shop.name} · tilbudsavis og liste i Home Assistant` },
    { key: "plan", title: "Ugens madplan", form: true,
      summary: `${f.days} dage fra ${WEEKDAYS[f.start_weekday].toLowerCase()} · ${f.monthly_budget ? "budget efter madbudgettet" : `budget ${f.budget} kr.`}${f.auto_generate ? " · laves automatisk" : ""}` },
    { key: "ai", title: "AI til madplanen", form: true,
      summary: state.ai_entities?.find(x => x.entity_id === f.ai_task_entity)?.name || "Home Assistants standard" },
    { key: "budget", title: "Madbudget", form: true,
      summary: f.monthly_budget ? `${kr0(f.monthly_budget)} om måneden${f.budget_notify ? " · besked ved 80 %" : ""}` : "Ikke sat op" },
    { key: "family", title: "Familie og portioner", form: true,
      summary: `${f.household.length} personer${f.portion_percent > 100 ? ` · +${f.portion_percent - 100} % mad` : ""}${allergies ? ` · ${allergies} allergi${allergies === 1 ? "" : "er"}` : ""}${f.avoid.length ? ` · undgår ${f.avoid.length}` : ""}` },
    { key: "dishes", title: "Retter og vaner", form: true,
      summary: `${state.favorites.length} favoritretter · ${dislikes} kan ikke lide · ${f.leftover_days} restedage` },
    { key: "shopping", title: "Indkøb og basisvarer", form: true,
      summary: `${organic}${f.must_haves.length ? ` · ${f.must_haves.length} faste varer` : ""}` },
    { key: "rules", title: "Det skal AI'en huske", form: false,
      summary: `${(state.settings.rules || []).length} punkter` },
    { key: "nutrition", title: "Næring", form: true,
      summary: f.nutrition_enabled ? `${f.kcal_min}–${f.kcal_max} kcal · ${f.protein_pct}/${f.carb_pct}/${f.fat_pct} %` : "Slået fra" },
    { key: "chains", title: "Andre butikker", form: true,
      summary: (f.chains || []).filter((id) => id !== panel._storeId()).length ? `${f.chains.filter((id) => id !== panel._storeId()).map((id) => panel._chainName(id)).join(", ")}${f.plan_all_chains ? " · madplan på tværs" : " · sammenligning"}` : `Kun ${panel._shopName()}` },
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
const dateLabel = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return `${WEEKDAYS[(d.getDay() + 6) % 7]} ${d.getDate()}/${d.getMonth() + 1}`;
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
    this._tab = "plan";
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
    this._recipesSub = "week"; // "week" (the plan's recipes) or "collection"
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
    this._sites = { query: "", results: [], loading: false, error: null, searched: false, opening: null };
    this._budgetSpan = "month";
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

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
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
    const key = TABS.some(([k]) => k === tab) ? tab : "plan";
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
    // No zooming: pinch (Safari's gesture events) and two-finger touches.
    this._noZoom = (ev) => ev.preventDefault();
    this._noPinch = (ev) => {
      if (ev.touches?.length > 1) ev.preventDefault();
    };
    // Not inside a dashboard card: the dashboard decides about zooming there.
    if (!this._embed) {
      document.addEventListener("gesturestart", this._noZoom, { passive: false });
      document.addEventListener("touchmove", this._noPinch, { passive: false });
    }
    this._tick = setInterval(() => this._tickTimers(), 1000);
    if (this._hass && !this._state) this._load();
    else if (this._hass && this._state?.status?.state === "generating") this._load(true);
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisibility);
    document.removeEventListener("gesturestart", this._noZoom);
    document.removeEventListener("touchmove", this._noPinch);
    this._stopDictation?.();
    clearInterval(this._tick);
    clearTimeout(this._poll);
    this._releaseWake();
  }

  // ------------------------------------------------------------------ data

  async _ws(type, data = {}) {
    const entry = this._state?.entry_id ? { entry_id: this._state.entry_id } : {};
    return this._hass.callWS({ type, ...entry, ...data });
  }

  async _load(silent = false, refresh = false) {
    const before = this._signature();
    try {
      const state = await this._ws("middagsro/state", refresh ? { refresh: true } : {});
      this._state = state;
      this._error = null;
      this._loadedAt = Date.now();
      if (!this._startDate || !this._startDateTouched) this._startDate = state.default_start;
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

  // One product on the REMA list in the app; the meal plan's list is left as it is.
  _addToRemaList(productId, name) {
    this._run(() => this._ws("middagsro/list/add", { product_id: Number(productId), amount: 1 }), `${name} er sat på ${this._listName()}.`);
  }

  // A toast is its own little render: it never redraws the page under the user's fingers.
  _say(message) {
    this._toast = message;
    this._renderToast();
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = null;
      this._renderToast();
    }, 3500);
  }

  _renderToast() {
    const node = this.shadowRoot.querySelector("#toast");
    if (node) node.innerHTML = this._toast ? `<div class="toast">${esc(this._toast)}</div>` : "";
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
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        this._toast = null;
        this._renderToast();
      }, 3500);
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
    const keys = TABS.map(([key]) => key);
    const next = keys[keys.indexOf(this._tab) + (dx < 0 ? 1 : -1)];
    this._goTab(next, dx < 0 ? 1 : -1);
  }

  _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el) return;
    const { action, arg } = el.dataset;
    const actions = {
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
        const count = this._state?.rema_list?.items?.length || 0;
        const name = this._listName();
        if (!count) return this._say(`${name[0].toUpperCase()}${name.slice(1)} er allerede tom.`);
        if (!confirm(`Fjern alle ${count} varer fra ${name}?${this._isRema() || this._state?.shop?.bilka_cart ? " Kurven/listen bliver også tom i appen." : ""}`)) return;
        this._run(() => this._ws("middagsro/list/clear"), `${name[0].toUpperCase()}${name.slice(1)} er tømt.`);
      },
      generate: () => this._run(() => this._generate(), GENERATING_MESSAGE),
      "freezer-generate": () => this._run(
        () => this._ws("middagsro/freezer/generate", {
          count: Number(arg),
          note: (this._freezerNote ?? this._state?.freezer_note ?? "").slice(0, 2000),
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
            : this._state?.shop?.bilka_cart ? "De fundne varer er sendt til BilkaToGo-kurven. Eventuelle manglende varer vises under Indkøb." : part === "late" ? `Varerne til ${this._lateDayName()} er sat på indkøbslisten.` : "Varerne er sat på indkøbslisten."
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
        this._run(async () => {
          await this._ws("middagsro/purchases/add", data);
          this._book = { amount: "", store: this._book.store, date: "" };
        }, `${kr0(amount)} er konteret.`);
      },
      "budget-suggest": () => {
        this._book.amount = String(Math.round(Number(arg) || 0));
        this._renderBudgetForms();
      },
      "purchase-delete": () => {
        const p = (this._state?.budget?.purchases || []).find((x) => x.id === arg);
        if (!p || !confirm(`Slet købet på ${kr0(p.amount)} fra ${dateLabel(p.date).toLowerCase()}?`)) return;
        this._run(() => this._ws("middagsro/purchases/delete", { purchase_id: arg }), "Købet er slettet.");
      },
      "budget-setup": () => {
        const value = Math.round(Number(String(this._book.monthly || "").replace(",", ".")));
        if (!(value > 0)) return this._say("Skriv jeres madbudget pr. måned.");
        this._run(async () => {
          const saved = await this._ws("middagsro/settings", { settings: { ...this._state.settings, monthly_budget: value } });
          if (this._form && !this._dirty) this._form = clone(saved);
        }, `Madbudgettet er sat til ${kr0(value)} om måneden.`);
      },
      "budget-view": () => {
        this._budgetSpan = arg;
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
        if (!confirm("Slet denne madplan fra historikken?")) return;
        this._run(async () => {
          await this._ws("middagsro/plan/delete", { plan_id: arg });
          if (this._plan?.id === arg) {
            this._viewingLatest = true;
          }
        }, "Madplanen er slettet.");
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
        this._picks[m.date] = pick;
        this._modal = null;
        this._renderModal();
        this._render();
      },
      "pick-remove": () => {
        delete this._picks[arg];
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
        this._renderModal();
      },
      "rc-save": () => this._recipeSave(),
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
      surprise: () => this._run(() => this._generate(true), "Madplanen med nye, overraskende retter er ved at blive lavet – det tager typisk 1-2 minutter."),
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
      "settings-open": () => {
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
          fixed_days: { weekday: 3, text: "" },
          must_haves: { name: "", amount: 1, product_id: null },
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
        this._form.must_haves.push({ name, product_id: product.id, amount: 1 });
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
        this._modal = { kind: "day", planId, date, dish: day.dish, leftovers: !!day.uses_leftovers_from || day.type === "rester" };
        this._renderModal();
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
      "review-skip": () => this._reviewAction(arg, "skip", null, "Varen er udeladt fra listen."),
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
      "pantry-open": () => this._pantryOpen(),
      "plan-rematch": () =>
        this._editPlan(
          () => this._ws("middagsro/plan/rematch", { plan_id: this._plan.id }),
          "Varerne er fundet igen. Jeres egne valg er beholdt, og usikre varer står øverst."
        ),
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
      this._dirty = true;
      this._updateSettingsSavebar();
      if (ev.type === "change" && (el.type === "radio" || el.tagName === "SELECT" || /_pct$/.test(ds.path))) this._render();
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
    const days = new Set(this._planDates());
    await this._ws("middagsro/generate", {
      start_date: this._startDate || null,
      skip_dates: [...this._skip].filter((d) => days.has(d)),
      surprise,
      picks: Object.fromEntries(Object.entries(this._picks).filter(([d]) => days.has(d) && !this._skip.has(d))),
    });
    this._skip.clear();
    this._picks = {};
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

  async _swapOptions() {
    const m = this._modal;
    if (!m || m.busy) return;
    m.busy = "options";
    m.error = null;
    this._renderModal();
    try {
      const result = await this._ws("middagsro/swap/options", { plan_id: m.planId, date: m.date });
      Object.assign(m, { date: result.date, dish: result.dish, options: result.options });
    } catch (err) {
      m.error = err?.message || String(err);
    }
    m.busy = null;
    this._renderModal();
  }

  async _swapPick(idx) {
    const m = this._modal;
    const option = m?.options?.[idx];
    if (!option || m.busy) return;
    m.busy = "swap";
    m.picked = idx;
    m.error = null;
    this._renderModal();
    try {
      const plan = await this._ws("middagsro/swap", { plan_id: m.planId, date: m.date, option });
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

  async _lineAction(data, okMessage) {
    const m = this._modal;
    if (!m || m.busy) return;
    m.busy = true;
    m.error = null;
    this._renderModal();
    try {
      const plan = await this._ws("middagsro/plan/line", { plan_id: m.planId, line_id: m.lineId, ...data });
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
        ${line.skipped ? `<div class="banner info">Varen er udeladt fra listen. <button class="btn small" data-action="review-unskip" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>Tag den med igen</button></div>` : ""}
        ${this._needsReview(line) ? `<div class="banner warn"><div>Middagsro er ikke sikker på, at det er den rigtige vare${line.note ? ` (${esc(line.note)})` : ""}.
          <div class="row wrap">${p ? `<button class="btn small primary" data-action="review-keep" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>✓ Behold varen</button>` : ""}
          <button class="btn small" data-action="review-skip" data-arg="${esc(line.id)}" ${busy ? "disabled" : ""}>Udelad varen</button></div></div></div>` : ""}
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
        <button class="btn back" data-action="chain-close">‹ Madplan</button>
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
                <button class="btn small" data-action="ev-rema-list" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""} title="Direkte på REMA-listen i appen">+ REMA-listen</button>
              </span>`
            : `<button class="btn small" data-action="ev-rema-list" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""}>+ REMA-listen</button>`}
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
    if (!cooked?.dish || cooked.type === "tom") return '<span class="rate"><span class="rate-gap"></span><span class="rate-gap"></span><span class="rate-gap"></span></span>';
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
    return this._isRema() ? "REMA-listen" : this._state?.shop?.bilka_cart ? "BilkaToGo-kurven" : "indkøbslisten";
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
              .join(" · ")}</span>
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
        </div>${ing.product
          ? `<p class="muted small rc-prod">REMA: ${esc(ing.product.name)}${ing.product.underline ? ` · ${esc(ing.product.underline)}` : ""}${ing.basic ? " · basisvare" : ""}
              <button class="link small" data-action="rc-ing-unlink" data-arg="${i}">Fjern</button></p>`
          : ""}<div class="rc-sugg" data-idx="${i}"></div>`
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
          ? `<p class="muted small">Fra REMA 1000's opskrifter. Ingredienserne er koblet til REMA's varer, så indkøbslisten får de rigtige varer.${r.id ? "" : " Gem den i opskriftsamlingen, eller sæt den direkte på madplanen."}</p>`
          : m.imported ? `<p class="muted small">${m.recipe.source === "scan" ? "Læst fra billedet af AI'en – tjek mængder og trin" : m.recipe.source === "web" ? `Fra ${esc(m.recipe.site || "madsiden")}` : "Hentet fra linket"}. Ret det, der skal rettes, og gem den i opskriftsamlingen.</p>` : ""}
        ${m.recipe.url ? `<p class="muted small"><a href="${esc(m.recipe.url)}" target="_blank" rel="noopener">Se opskriften på ${esc(m.recipe.site || "siden")} ↗</a></p>` : ""}
        ${this._remaPick && r.rema_slug
          ? `<div class="banner info">Vælg den til ${esc(dateLabel(this._remaPick.date).toLowerCase())}?
              <button class="btn primary small" data-action="rr-pick" data-arg="${esc(r.rema_slug)}" ${busy ? "disabled" : ""}>${m.busy === "pick" ? '<span class="spinner small"></span> Sætter på …' : "Sæt på madplanen"}</button></div>`
          : ""}
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
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
        ${ingredients}
        <button class="btn small" data-action="rc-row" data-arg="ingredients|add">+ Ingrediens</button>
        <h3>Sådan gør du</h3>
        ${steps}
        <button class="btn small" data-action="rc-row" data-arg="steps|add">+ Trin</button>
        <label class="field">Tip <textarea rows="2" data-bind="rcp" data-field="tip">${esc(r.tip || "")}</textarea></label>
        ${targets}
        <div class="dialog-bottom wrap">
          <button class="btn primary" data-action="rc-save" ${busy ? "disabled" : ""}>${r.id ? "Gem" : "Gem i samlingen"}</button>
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
          plan: () => this._planView(),
          recipes: () => this._recipesView(),
          shopping: () => this._shoppingView(),
          favorites: () => this._favoritesView(),
          budget: () => this._budgetView(),
          health: () => this._healthView(),
          history: () => this._historyView(),
          settings: () => this._settingsView(),
        }[this._tab]();
        if (this._tab === "plan" && this._chain) body = this._chainView();
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
      const tabs = TABS.map(
        ([key, label]) =>
          `<button class="tab${EXTRA_TABS.has(key) ? " extra" : ""}" data-action="tab" data-arg="${key}">${TAB_ICONS[key] || ""}<span>${label}</span></button>`
      ).join("");
      const extra = TABS.filter(([key]) => EXTRA_TABS.has(key))
        .map(([key, label]) => `<button class="more-item" data-action="tab" data-arg="${key}">${TAB_ICONS[key] || ""}<span>${label}</span></button>`)
        .join("");
      root.innerHTML = `
        <style>${STYLE}</style>
        <div id="top"></div>
        <div class="toolbar">
          <ha-menu-button></ha-menu-button>
          <span class="brand"><img class="logo" src="${this._img("icon.svg")}" alt=""><span class="wordmark">Middagsro</span></span>
          <span class="spacer"></span>
          <span id="timerchip" class="timer-chip" data-action="tab" data-arg="recipes"></span>
          <span id="busy"></span>
        </div>
        <nav class="tabs">${tabs}<button class="tab more" data-action="more" aria-expanded="false"></button></nav>
        <div class="more-scrim" data-action="more" hidden></div>
        <div class="more-sheet" hidden>${extra}</div>
        <main id="content"></main>
        <div id="modal"></div>
        <div id="toast" role="status" aria-live="polite"></div>`;
    }
    const menu = root.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    root.querySelectorAll(".tab, .more-item").forEach((tab) => tab.classList.toggle("active", tab.dataset.arg === this._tab));
    const more = root.querySelector(".tab.more");
    if (more) {
      more.classList.toggle("active", this._moreOpen || EXTRA_TABS.has(this._tab));
      more.setAttribute("aria-expanded", String(!!this._moreOpen));
      more.innerHTML = this._moreOpen ? `${CLOSE_ICON}<span>Luk</span>` : `${MORE_ICON}<span>Mere</span>`;
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
    if (this._modal?.kind === "pantry") {
      node.innerHTML = this._pantryModal(this._modal);
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
    const options = (m.options || [])
      .map(
        (o, i) => `<button class="option" data-action="swap-pick" data-arg="${i}" ${busy ? "disabled" : ""}>
          <span class="option-dish"><b>${esc(o.dish)}</b>${o.type === "vegetar" ? ' <span class="badge eco">Vegetar</span>' : ""}${o.mealie ? ' <span class="badge mealie">Mealie</span>' : ""}</span>
          ${o.why ? `<span class="muted small">${esc(o.why)}</span>` : ""}
          <span class="muted small">${o.active_minutes ? `${o.active_minutes} min aktiv` : ""}${o.total_minutes ? ` · ${o.total_minutes} min i alt` : ""}</span>
          ${m.busy === "swap" && m.picked === i ? '<span class="muted small"><span class="spinner small"></span> Finder varer og skriver opskriften …</span>' : ""}
        </button>`
      )
      .join("");
    const body = m.options
      ? `<p class="muted small">Vælg en ret. Indkøbslisten og opskriften bliver lavet om${m.leftovers ? ", også for resterne" : ""}.</p>
         <div class="options">${options}</div>
         <div class="row wrap dialog-actions">
           <button class="btn" data-action="swap-options" ${busy ? "disabled" : ""}>
             ${m.busy === "options" ? '<span class="spinner small"></span> Finder andre retter …' : aiLabel("Tre nye forslag")}</button>
           <span class="spacer"></span>
           <button class="btn" data-action="modal-close" ${busy ? "disabled" : ""}>Annullér</button>
         </div>`
      : `${m.leftovers ? '<p class="muted small">Det er rester – skifter du, skiftes retten, de er rester af.</p>' : ""}
         <div class="row wrap dialog-actions">
           ${m.dish ? `<button class="btn" data-action="day-recipe" ${busy ? "disabled" : ""}>Se opskriften</button>` : ""}
           ${this._mealieButton(m.planId, m.date)}
           <button class="btn primary" data-action="swap-options" ${busy ? "disabled" : ""}>
             ${m.busy === "options" ? '<span class="spinner small"></span> Finder retter …' : aiLabel(m.dish ? "Skift retten – tre forslag" : "Find en ret – tre forslag")}</button>
           ${this._isRema() ? `<button class="btn" data-action="day-rema" ${busy ? "disabled" : ""}>Vælg en REMA-opskrift</button>` : ""}
         </div>
         <div class="row wrap dialog-actions">
           ${m.dish ? `<button class="btn danger" data-action="day-clear" data-arg="delete" ${busy ? "disabled" : ""}>Slet retten</button>` : ""}
           <button class="btn danger" data-action="day-clear" data-arg="skip" ${busy ? "disabled" : ""}>Spring dagen over</button>
           <span class="spacer"></span>
           <button class="btn" data-action="modal-close" ${busy ? "disabled" : ""}>Luk</button>
         </div>`;
    return `
      <div class="scrim" data-action="modal-close"></div>
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="day-title">
        <h2 id="day-title">${esc(m.dish || "Ingen ret")}</h2>
        <p class="muted">${esc(dateLabel(m.date))}</p>
        ${m.error ? `<div class="banner error">${esc(m.error)}</div>` : ""}
        ${body}
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
    if ((this._state.settings.recipe_sites || []).length) tabs.push(["sites", "Madsider"]);
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
        <p class="muted small">Madplanen bygges omkring den valgte ret, og dens varer kommer på indkøbslisten.</p>
        ${body}
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
              ${this._isRema() ? `<button class="btn small to-rema" data-action="shop-offer-add-list" data-arg="${i}" ${this._busy ? "disabled" : ""} title="Direkte på REMA-listen i appen, ikke på madplanens liste">+ REMA-listen</button>` : ""}</div>`
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
    const last = this._lastAvisDay();
    return Array.from({ length: count }, (_, i) => {
      const d = new Date(`${start}T12:00:00`);
      d.setDate(d.getDate() + i);
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }).filter((iso) => !last || iso <= last || start > last);
  }

  // The last day of the newest avis that is out: a plan can't be priced after it.
  _lastAvisDay() {
    const cat = this._state?.catalogs || {};
    return localDay(cat.upcoming?.valid_to || cat.current?.valid_to || "");
  }

  _generateControls(label = "Lav ny madplan") {
    const generating = this._state?.status?.state === "generating";
    const skip = this._planDates()
      .map((iso) => {
        const pick = this._picks[iso];
        const skipped = this._skip.has(iso);
        return `<div class="pickday ${pick ? "picked" : ""} ${skipped ? "skipped" : ""}"><b>${esc(dateLabel(iso))}</b><label class="check skipday"><input type="checkbox" data-bind="skip" value="${iso}" ${skipped ? "checked" : ""}> Spring over</label>
          ${skipped ? "" : pick
            ? `<span class="pick-chip"><button class="link" data-action="pick-open" data-arg="${iso}" title="Skift retten">${esc(pick.dish)}</button><button class="icon-btn" data-action="pick-remove" data-arg="${iso}" aria-label="Fjern ${esc(pick.dish)}">${CLOSE_ICON}</button></span>`
            : `<button class="btn small pick-btn" data-action="pick-open" data-arg="${iso}" title="Vælg selv retten til ${esc(dateLabel(iso).toLowerCase())}">Vælg ret</button>`}</div>`;
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
      ? `<p class="muted small">Næste uges avis er ikke ude endnu, så madplanen kan højst gå til og med ${esc(dateLabel(last))}.</p>`
      : ""}
    <div class="wishes">
      <button class="btn" data-action="note-open">${note ? "Ret ønsker til madplanen" : "Ønsker til madplanen"}</button>
      ${note ? `<p class="muted small note-preview">Bruges i næste madplan: ${esc(note)}</p>` : ""}
    </div>
    ${skip ? (() => {
      const dates = this._planDates();
      const tailored = dates.filter((iso) => this._skip.has(iso) || this._picks[iso]).length;
      const open = tailored || this._folds?.has("days");
      return `<details class="fold" data-fold="days" ${open ? "open" : ""}><summary>Tilpas dagene${tailored ? ` <span class="badge">${tailored} ${tailored === 1 ? "dag" : "dage"}</span>` : ""}</summary>
        <p class="muted small">AI'en vælger retterne. Du kan selv vælge en ret eller springe en dag over.</p><div class="skipdays">${skip}</div></details>`;
    })() : ""}
    <div class="row wrap skipgo">
      <button class="btn primary" data-action="generate" ${generating || this._busy ? "disabled" : ""}>
        ${generating ? "Laves …" : aiLabel(label)}
      </button>
      <button class="btn surprise" data-action="surprise" ${generating || this._busy ? "disabled" : ""}
        title="Retter I aldrig har fået – fra andre køkkener og med overraskende smage">${SURPRISE_ICON}Overrask os</button>
    </div>`;
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
      <div class="row wrap">${[4, 5].map(n => `<button class="btn" data-action="freezer-generate" data-arg="${n}" ${busy ? "disabled" : ""}>${aiLabel(`Lav en plan med ${n} retter`)}</button>`).join("")}</div>
      ${plans.length ? `<h3>Dine fryserplaner</h3><div class="batch-plans">${plans.map(p => `<button class="setting-row" data-action="freezer-open" data-arg="${esc(p.id)}"><span class="setting-text"><b>${esc(p.title)}</b><span class="muted small">${p.dishes?.length || ""} retter · ${kr(p.total)}</span></span><span class="chev" aria-hidden="true">›</span></button>`).join("")}</div>` : '<p class="muted small">Når planen er klar, kan du åbne den her. Den ændrer ikke ugens madplan.</p>'}
    </section>`;
  }

  _freezerView(plan) {
    const locked = plan.portions_locked || plan.shopping.some(l => l.sent);
    const portions = day => {
      const values = [...new Set([4, 8, 12, 16, 20, 24, 32, 40, day.servings])].sort((a, b) => a - b);
      return `<label class="field batch-portions">Antal portioner <select data-bind="freezer-portions" data-date="${day.date}" aria-label="Portioner til ${esc(day.dish)}" ${locked || this._busy ? "disabled" : ""}>${values.map(n => `<option value="${n}" ${n === day.servings ? "selected" : ""}>${n} portioner</option>`).join("")}</select></label>`;
    };
    return `<div class="card">
      <h1>${esc(plan.title)}</h1>
      <ol class="batch-steps" aria-label="Sådan bruger du fryserplanen"><li>Retterne er valgt</li><li ${!locked ? 'aria-current="step"' : ""}>Vælg portioner</li><li ${locked ? 'aria-current="step"' : ""}>Gennemgå indkøb</li></ol>
      <p>Hvor meget vil I lave af hver ret? Vælg fx 16 portioner. Opskrift og indkøbsliste opdateres automatisk.</p>
      <p class="muted small">Familiens portionsprocent bruges ikke her. Ris og pasta til spisedagen købes separat.</p>
      ${locked ? '<div class="banner info">Portionsvalget er låst, fordi overførsel til indkøbskurven er startet.</div>' : ""}
      <div class="batch-dishes">${plan.days.map((day, i) => `<article class="batch-dish"><div class="batch-dish-name"><span class="batch-number" aria-hidden="true">${i + 1}</span><h2>${esc(day.dish)}</h2></div>${portions(day)}
        ${day.tip ? `<p class="muted">${esc(day.tip)}</p>` : ""}
        <button class="btn small" data-action="open-day" data-arg="${esc(plan.id)}|${day.date}" aria-label="Se opskrift på ${esc(day.dish)}">Se opskrift</button></article>`).join("")}</div>
      <details><summary>Fordeling i fryseposer</summary><p class="muted small">Fordel den færdige ret i fx 400 g poser. Antallet afhænger af rettens færdige vægt og beregnes ikke automatisk.</p></details>
      <div class="batch-footer"><div><span class="muted small">Anslået indkøb i alt</span><strong>${kr(plan.total)}</strong></div><button class="btn primary" data-action="tab" data-arg="shopping">Se indkøbsliste →</button></div>
      <button class="link" data-action="view-latest">‹ Til ugens madplan</button>
    </div>${this._freezerControls()}`;
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
      return `${this._chainsCard()}<div class="card hero">
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
      return `<div class="day-row ${past ? "past" : ""}"><button class="day ${day.date === today ? "today" : ""}" data-action="day-menu" data-arg="${esc(owner.id)}|${day.date}">
          <span class="date">${day.date === today ? `I aften · ${esc(dateLabel(day.date))}` : esc(dateLabel(day.date))}</span>
          <span class="dish ${day.dish ? "" : "muted"}">${esc(day.dish || "Ingen ret – tryk for at vælge en")}</span>
          <span class="meta">${day.total_minutes ? `${day.total_minutes} min` : ""}${type ? ` <span class="badge">${esc(type)}</span>` : ""}${day.mealie ? ' <span class="badge mealie">Mealie</span>' : ""}${owner.surprise ? ' <span class="badge surprise">Overraskelse</span>' : ""}</span>
        </button><span class="day-tools">${this._rateButtons(owner, day)}${this._moveButtons(owner, day, past)}</span></div>`;
    };
    // The newest plan decides each date; this week and the coming days show as one plan.
    const timeline = this._timeline();
    let title = plan.title;
    let period = `${dateLabel(plan.start_date)} – ${dateLabel(plan.end_date)}`;
    let skipped = plan.skipped || [];
    let avis = plan.catalog ? ` · ${plan.catalog.label || ""}` : "";
    let shopFrom = "";
    let days;
    if (timeline) {
      const weeks = [...new Set(timeline.map((e) => e.week))];
      title = weeks.length > 1 ? `Madplan uge ${weeks[0]}–${weeks[weeks.length - 1]}` : `Madplan uge ${weeks[0]}`;
      const shown = timeline.filter((e) => e.day);
      period = shown.length ? `${dateLabel(shown[0].date)} – ${dateLabel(shown[shown.length - 1].date)}` : period;
      skipped = timeline.filter((e) => e.skipped && e.date >= today).map((e) => e.date);
      avis = "";
      // Days from older plans: the price and the list are the newest plan's.
      if (timeline.some((e) => e.plan.id !== plan.id)) shopFrom = `indkøb fra ${dateLabel(plan.start_date)}`;
      let week = null;
      days = shown
        .map((e) => {
          const head = weeks.length > 1 && e.week !== week ? `<h3 class="week-head">Uge ${esc(e.week)}</h3>` : "";
          week = e.week;
          return head + dayRow(e.plan, e.day);
        })
        .join("");
    } else {
      days = plan.days.map((day) => dayRow(plan, day)).join("");
    }
    const checklist = (plan.checklist || [])
      .map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.requirement)}</li>`)
      .join("");
    return `
      ${this._chainsCard()}
      ${this._olderBanner()}
      ${this._updateBanner(plan)}
      ${this._budgetCard(true)}
      <div class="card">
        <div class="row between wrap">
          <div>
            <h1>${esc(title)}</h1>
            <p class="muted">${esc(period)}${esc(avis)}${skipped.length ? `<br>Springes over: ${skipped.map((d) => esc(dateLabel(d))).join(", ")}` : ""}</p>
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
        <div class="days">${days}</div>
        <div class="help-row">
          ${this._planHelp ? '<p class="muted small help-text">Tryk på en ret for at se opskriften eller skifte den ud. 👍, 👎 og ♥ gemmer retten i opskriftsamlingen – tryk igen for at fortryde.</p>' : ""}
          <button class="help-q" data-action="plan-help" aria-expanded="${this._planHelp ? "true" : "false"}" aria-label="Hjælp" title="Hjælp">?</button>
        </div>
        <div class="row wrap actions">
          ${(() => {
            const left = plan.shopping.filter((line) => !line.buy_from && !line.buy_at && !line.sent).length;
            return `<button class="btn primary" data-action="send" ${this._busy || !left ? "disabled" : ""}>
              ${left ? (plan.status === "sent" ? `Send ${left} nye varer til ${this._listName()}` : `Send til ${this._listName()}`) : "Sendt ✓"}</button>`;
          })()}
          ${plan.shopping.some((line) => line.buy_from)
            ? `<span class="muted small">+ ${plan.shopping.filter((line) => line.buy_from).length} varer købes senere – se Indkøb</span>`
            : ""}
          <button class="btn" data-action="tab" data-arg="shopping">Se indkøbsliste</button>
          <button class="btn" data-action="open-day" data-arg="">Start madlavning</button>
          ${this._state.mealie?.available ? `<button class="btn" data-action="mealie-sync" ${this._busy ? "disabled" : ""}>Sæt ugen i Mealie-kalenderen</button>` : ""}
        </div>
        ${checklist || plan.deviations ? `<details><summary>Krav-tjekliste</summary><ul class="checklist">${checklist}</ul>${plan.deviations ? `<p class="muted">${esc(plan.deviations)}</p>` : ""}</details>` : ""}
      </div>
      <div class="card">
        <h2>Det skal AI'en huske</h2>
        <p class="muted small">Faste ønsker til alle madplaner – skriv eller diktér. De kan også rettes under Indstillinger.</p>
        ${this._rulesHtml()}
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
          <span class="rr-badges">${r.on_offer ? `<span class="badge offer">${r.on_offer} på tilbud</span>` : ""}${r.vegetarian ? '<span class="badge eco">Vegetar</span>' : ""}</span>
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
      <div class="row wrap">
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
    const seg = `<div class="seg subnav fit">
        <button class="${this._recipesSub === "week" ? "active" : ""}" data-action="recipes-sub" data-arg="week">Ugens<span class="wide"> opskrifter</span></button>
        <button class="${this._recipesSub === "collection" ? "active" : ""}" data-action="recipes-sub" data-arg="collection"><span class="wide">Opskriftsamling</span><span class="narrow">Samling</span>${this._state.recipes?.length ? ` (${this._state.recipes.length})` : ""}</button>
        ${this._isRema() ? `<button class="${this._recipesSub === "rema" ? "active" : ""}" data-action="recipes-sub" data-arg="rema">REMA<span class="wide">-opskrifter</span></button>` : ""}
        <button class="${this._recipesSub === "sites" ? "active" : ""}" data-action="recipes-sub" data-arg="sites">Madsider</button>
      </div>`;
    const view = { collection: () => this._collectionView(), rema: this._isRema() ? () => this._remaView() : null, sites: () => this._sitesView() }[this._recipesSub];
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
          <button class="btn ${this._wake ? "primary" : ""}" data-action="wake">
            ${this._wake ? "☀ Skærmen holdes tændt" : "☀ Hold skærmen tændt"}
          </button>
        </div>
        <p class="muted">${plan.kind === "freezer" ? "Fryserret" : esc(dateLabel(day.date))}${day.servings ? ` · ${day.servings} ${plan.kind === "freezer" ? "portioner" : "personer"}` : ""}${day.active_minutes ? ` · ${day.active_minutes} min aktiv` : ""}${day.total_minutes ? ` · ${day.total_minutes} min i alt` : ""}${type ? ` · ${esc(type)}` : ""}</p>
        ${leftovers}
        ${day.nutrition
          ? `<p class="nutri">Pr. voksenportion: <b>${Math.round(day.nutrition.kcal)} kcal</b>${["protein_g", "carbs_g", "fat_g"]
              .filter((k) => day.nutrition[k] != null)
              .map((k) => ` · ${Math.round(day.nutrition[k])} g ${{ protein_g: "protein", carbs_g: "kulhydrat", fat_g: "fedt" }[k]}`)
              .join("")}</p>`
          : ""}
        ${day.recipe_error || (!day.steps.length && !day.uses_leftovers_from && day.type !== "rester" && day.type !== "tom")
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
            <button class="btn small" data-action="review-skip" data-arg="${esc(line.id)}" ${busy}>Udelad</button>
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
                line.skipped ? '<span class="badge skipped">Udeladt</span>' : this._needsReview(line) ? `<span class="badge doubt">${line.confidence === "low" ? "Tjek" : "Usikker"}</span>` : "",
                line.remembered ? '<span class="badge remembered" title="Den vare I valgte til ingrediensen sidst">Jeres valg</span>' : "",
                line.must_have ? '<span class="badge">Fast vare</span>' : "",
                line.buy_from ? `<span class="badge from">Købes ${esc(dayShort(line.buy_from))}</span>` : "",
                line.price_source === "avis" ? '<span class="badge">Avispris</span>' : "",
              ].join("");
              const need = line.amount && line.unit && line.unit !== "pk" ? `${line.amount} ${line.unit}` : "";
              return `<li class="line tappable ${this._isRema() && line.id ? "has-send" : ""} ${line.skipped ? "is-skipped" : ""}" data-action="line-menu" data-arg="${esc(line.id || "")}">
                ${p?.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
                <div class="what">
                  <span class="title"><b>${esc(p ? p.name : line.name)}</b> ${badges}</span>
                  <span class="muted">${esc(p?.underline || (this._state?.shop?.bilka_cart ? "Vælg en vare" : "Tilføjes som fritekst"))}${need ? ` · behov ${esc(need)}` : ""}</span>
                  ${line.offer_name ? `<span class="muted">Avisvare: ${esc(line.offer_name)}</span>` : ""}
                  ${line.note ? `<span class="note">${esc(line.note)}</span>` : ""}
                  ${compare?.lines?.[line.id]
                    ? `<button class="cheaper" data-action="chain-move" data-arg="${esc(line.id)}|${esc(compare.lines[line.id].dealer_id)}"
                        title="Flyt til ${esc(this._chainName(compare.lines[line.id].dealer_id))}-listen">${this._chainLogo(compare.lines[line.id].dealer_id, "tiny")}
                        <span>${esc(compare.lines[line.id].heading)}: spar ${kr(compare.lines[line.id].saving)}</span></button>`
                    : ""}
                </div>
                <div class="cost">${p && p.price != null ? `${line.packages} × ${kr(p.price)}<b>${kr(line.cost)}</b>` : line.packages > 1 ? `${line.packages} stk.` : "–"}</div>
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
          <div><h1>${lateLines.length ? "Indkøb på indkøbsdagen" : "Indkøbsliste"}</h1><p class="muted">${esc(plan.title)}${lateLines.length ? ` · plus ${lateLines.length} varer ${esc(dayShort(lateDay))}` : ""}</p></div>
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
          ? `<div class="banner info sent-banner"><span>✓ ${sentCount} ${sentCount === 1 ? "vare er sendt" : "varer er sendt"} til ${this._isRema() ? "REMA-appen" : this._state?.shop?.bilka_cart ? "BilkaToGo-kurven" : "indkøbslisten"}${plan.last_sent?.at ? ` ${esc(sentWhen(plan.last_sent.at))}` : ""} – kurven her har kun det, der ikke er sendt endnu.${onList ? ` ${onList} ${onList === 1 ? "fast vare stod" : "faste varer stod"} der allerede og blev ikke sendt igen.` : ""}</span>
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
            title="Alle varer, der ikke er sendt, findes igen med de nyeste regler. Retterne og jeres egne valg bliver.">Find varer igen</button>` : ""}
          <button class="btn small" data-action="plan-refresh" ${this._busy ? "disabled" : ""}>Opdatér tilbudspriser</button>
          ${!missingProducts.length && this._hasPrices() && plan.shopping.some(line => !line.product && !line.sent && !line.product_id && !line.added && !line.buy_at) ? `<button class="btn small" data-action="rematch-missing" ${this._busy ? "disabled" : ""}>Søg manglende varer igen</button>` : ""}
        </div></details>
      </div>${lateHtml}${this._chainListsHtml(plan)}`;
    }
    const remaItems = rema?.items?.length
      ? rema.items
          .map((i) => `<li class="${i.bought ? "bought" : ""}">${i.amount > 1 ? `${i.amount} × ` : ""}${esc(i.name)}</li>`)
          .join("")
      : "<li class='muted'>Listen er tom.</li>";
    return `${this._olderBanner()}${planHtml}
      <div class="card">
        <div class="row between wrap">
          <h2>På ${this._listName()} lige nu${rema && this._isRema() ? ` (${esc(rema.name)})` : ""}</h2>
          <button class="btn small danger" data-action="clear-list" ${this._busy || !rema?.items?.length ? "disabled" : ""}>Tøm kurv</button>
        </div>
        <ul class="rema">${remaItems}</ul>
        ${rema && this._isRema() ? `<p class="muted">Anslået pris for det, der mangler: ${kr(rema.total)}</p>` : ""}
        ${!this._isRema() && this._state.settings.ha_todo_entity ? `<p class="muted small">Det, der sendes, kommer også på ${esc(this._hass?.states?.[this._state.settings.ha_todo_entity]?.attributes?.friendly_name || this._state.settings.ha_todo_entity)}.</p>` : ""}
      </div>`;
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
      ${compact ? '<div class="row"><button class="link" data-action="tab" data-arg="budget">Se økonomien</button></div>' : ""}
    </div>`;
  }

  _bookForm() {
    const chains = [this._storeId(), ...(this._state.settings.chains || []).filter((id) => id !== this._storeId()), "other"];
    const chip = (id) => `<button class="chip ${(this._book.store || this._storeId()) === id ? "active" : ""}" data-action="budget-store" data-arg="${esc(id)}">${id === "other" ? "Andet" : esc(this._chainName(id))}</button>`;
    // The list just sent is what was bought: offer its price.
    const sent = (this._plan?.shopping || []).filter((l) => l.sent && String(l.sent).slice(0, 10) === localToday());
    const suggestion = sent.reduce((sum, l) => sum + (Number(l.cost) || 0), 0);
    return `<div class="book">
        <input type="text" inputmode="decimal" data-bind="book" data-field="amount" value="${esc(this._book.amount)}" placeholder="Beløb" aria-label="Beløb">
        <input type="date" data-bind="book" data-field="date" value="${esc(this._book.date || localToday())}" max="${localToday()}" aria-label="Dato">
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
        <p>Skriv jeres faste beløb til indkøb pr. måned. Så kan I kontere hvert køb, se hvad der er tilbage af ugen, og madplanen holder sig inden for det.</p>
        <div class="row wrap"><input class="grow" type="text" inputmode="numeric" data-bind="book" data-field="monthly" value="${esc(this._book.monthly)}" placeholder="Fx 5000">
          <button class="btn primary" data-action="budget-setup">Start madbudget</button></div></div>`;
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
    return `${this._budgetCard()}
      <div class="stats">
        <div class="stat"><span class="muted small">Brugt i ${MONTHS_SHORT[Number(m.first.slice(5, 7)) - 1]}.</span><b>${kr0(m.spent)}</b><span class="muted small">af ${kr0(m.budget)}</span></div>
        <div class="stat"><span class="muted small">Prognose</span><b class="${forecastDiff > 0 ? "over" : "ok"}">${kr0(m.forecast)}</b><span class="muted small">${forecastDiff > 0 ? `${kr0(forecastDiff)} over` : `${kr0(-forecastDiff)} under`}</span></div>
      </div>
      ${seg}${body}`;
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
        <div class="what"><b>${kr0(p.amount)}</b><span class="muted small">${esc(dateLabel(p.date))} · ${esc(p.store === "other" ? p.note || "Andet" : this._chainName(p.store))}${p.note && p.store !== "other" ? ` · ${esc(p.note)}` : ""}${p.source === "action" ? " · automatisk" : ""}</span></div>
        <button class="icon-btn" data-action="purchase-delete" data-arg="${esc(p.id)}" aria-label="Slet købet">${CLOSE_ICON}</button></li>`
    ).join("");
    return `<div class="card"><h3 class="flush">De seneste to måneder</h3>${rows ? `<ul class="purchases">${rows}</ul>` : '<p class="muted">Ingen køb konteret endnu.</p>'}</div>`;
  }

  _favoritesView() {
    // Another shop has no favourites in an app: the watch list, and something to watch.
    if (!this._isRema()) {
      const q = this._favSearch.query;
      return `${this._watchHtml()}
        <div class="card">
          <h2 class="flush">Overvåg en vare</h2>
          <p class="muted small">Skriv, hvad I gerne vil have besked om, når det kommer på tilbud – fx kaffe eller laks. Middagsro leder i ${esc(this._shopGen())} og jeres andre butikkers aviser.</p>
          <div class="row wrap">
            <input class="grow" type="search" data-bind="favsearch" value="${esc(q)}" placeholder="Fx kaffe" enterkeyhint="done">
            <button class="btn small primary" data-action="watch-text">Overvåg</button>
          </div>
        </div>`;
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
          ? `<div class="prod-grid">${offers.map((p) => this._productCard(p)).join("")}</div>`
          : `<p class="muted">Ingen af dine favoritter er på tilbud ${next ? "i næste uge" : "lige nu"}.</p>`}`;
    }
    const count = data?.products?.length;
    return `${this._watchHtml()}
      <div class="card">
        <div class="row between wrap">
          <div><h1>Dine favoritter</h1>
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
      ${this._favSearchHtml()}`;
  }

  _historyView() {
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
        (d, i) => `<div class="row wrap rowitem">
          ${weekdaySelect(`fixed_days.${i}.weekday`, d.weekday)}
          <input class="grow" type="text" data-path="fixed_days.${i}.text" value="${esc(d.text)}" placeholder="Fx Rugbrødsdag">
          <button class="btn small danger" data-action="remove-row" data-arg="fixed_days|${i}">Fjern</button>
        </div>`
      )
      .join("");
    const musts = f.must_haves
      .map(
        (m, i) => `<div class="row wrap rowitem">
          <input class="grow" type="text" data-path="must_haves.${i}.name" value="${esc(m.name)}" placeholder="Vare">
          <label class="field inline">Antal pr. uge ${num(`must_haves.${i}.amount`, m.amount, 1, 99)}</label>
          ${m.product_id ? '<span class="badge">REMA-vare</span>' : ""}
          <button class="btn small danger" data-action="remove-row" data-arg="must_haves|${i}">Fjern</button>
        </div>`
      )
      .join("");
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
        ${fixed}
        <button class="btn small" data-action="add-row" data-arg="fixed_days">+ Tilføj fast dag</button>
        <label class="field">Ønsker til maden <textarea data-path="wishes" rows="2">${esc(f.wishes)}</textarea></label>
        `) + card(`        <h2 class="flush">Familiens favoritter</h2>
        <p class="muted small">Favoritter gemmes med det samme, når du tilføjer, retter eller sletter.</p>
        <p class="muted">Beskriv retten, fx “Ovnbagt laks med citronskiver, frisk spinatpasta med pesto og broccoli”.</p>
        <textarea data-bind="newfav" data-field="text" rows="2" placeholder="Ret">${esc(this._newFav.text)}</textarea>
        <div class="row wrap">
          <select data-bind="newfav" data-field="frequency">${opts.frequencies.map((q) => `<option value="${q}" ${this._newFav.frequency === q ? "selected" : ""}>${FREQ_LABELS[q]}</option>`).join("")}</select>
          <button class="btn primary small" data-action="add-fav">Tilføj</button>
        </div>
        <ul class="favs">${favs || "<li class='muted'>Ingen favoritter endnu.</li>"}</ul>
        `) + card(`        <h2 class="flush">Retter familien ikke kan lide</h2>
        <p class="muted">Retter, der aldrig skal på madplanen, fx “Fiskefrikadeller” eller “Gryderetter med kål”.</p>
        <textarea data-bind="newdislike" rows="2" placeholder="Ret">${esc(this._newDislike)}</textarea>
        <div class="row wrap">
          <button class="btn primary small" data-action="add-dislike" ${this._busy ? "disabled" : ""}>Tilføj</button>
        </div>
        <ul class="favs">${dislikes || "<li class='muted'>Ingen endnu.</li>"}</ul>
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
        <p class="muted">Jeres faste beløb til indkøb pr. måned. Det fordeles på månedens dage (5.000 kr. i oktober er 161 kr. om dagen, 1.129 kr. om ugen). Det, en uge ikke bruger, går videre til de næste uger i samme måned; en ny måned starter forfra den 1.</p>
        <label class="field">Madbudget pr. måned (kr., 0 = slået fra) ${num("monthly_budget", f.monthly_budget, 0, 1000000)}</label>
        <p class="muted small">Med et madbudget må en ny madplan koste det, der er tilbage af ugen – i stedet for det faste budget under Madplan og uge. Alt, der konteres, tæller med (også bleer og opvask).</p>
        <label class="check"><input type="checkbox" data-path="budget_notify" ${f.budget_notify ? "checked" : ""}> Giv besked, når 80 % af ugens budget er brugt</label>
        <p class="muted small">Beskeden går samme sted hen som overvågningens (Overvågning og beskeder${f.watch_notify ? "" : " – vælg en modtager dér"}).</p>
        <h3>Kontér automatisk</h3>
        <p class="muted small">Handlingen <b>middagsro.register_purchase</b> konterer et køb (beløb og butik) og svarer med, hvad der er tilbage af ugen. Betaler I med Apple Pay, kan en automatisering i Genveje-appen (Personlig › Transaktion › Wallet, butikker: REMA 1000, Netto …) kalde den med <i>Beløb</i> og <i>Forhandler</i> via Home Assistant-appens "Udfør handling" – så konteres købet af sig selv, når I betaler. Med Siri kan en genvej spørge om beløbet og kalde den samme handling.</p>`),
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
        const how = `Butikken skiftes under <b>Indstillinger › Enheder og tjenester › Middagsro › ⋮ › Omkonfigurér</b>. Madplaner, opskrifter, budget og indstillinger beholdes.`;
        if (shop.rema) {
          return card(`        <h2 class="flush">I handler i REMA 1000</h2>
        <p>Middagsro er logget ind på jeres REMA 1000-konto: alle varer har en pris, REMA's opskrifter kan bruges, og indkøbslisten sendes til REMA-appen.</p>
        <p class="muted">Handler I et andet sted – Netto, føtex, Lidl, Bilka, 365discount, MENY, Coop eller andre – kan I vælge den butik i stedet. Så bygges madplanen på dens tilbudsavis, og indkøbslisten ligger i Home Assistant.</p>
        <p class="muted small">${how}</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Åbn Middagsro under Enheder og tjenester</a>`);
        }
        if (shop.bilka_cart) {
          return card(`<h2 class="flush">I handler med BilkaToGo</h2>
        <p>Varehus: <b>${esc(shop.pickup_name)}</b>. Sortiment og priser følger dette varehus.</p>
        <p>Madplanens varer sendes til kurven i BilkaToGo-appen og på hjemmesiden. Du gennemgår selv kurven, vælger afhentningstid og bestiller i BilkaToGo.</p>
        <p>Fundne varer sendes til kurven. Ingredienser uden match vises særskilt og bliver i Middagsro, så du kan vælge en vare eller tilføje dem selv. Kurven kan ikke afkrydses som en indkøbsliste.</p>
        <p class="muted small">${how} Vælg Bilka igen for at ændre varehus eller login.</p>
        <a class="btn" href="/config/integrations/integration/middagsro" target="_top">Vælg butik, varehus eller login</a>`);
        }
        const todos = Object.keys(this._hass?.states || {})
          .filter((id) => id.startsWith("todo.") && !id.includes("middagsro"))
          .sort();
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
    return `
      <div class="settings-intro">
        <h1>Indstillinger</h1>
        <p class="muted">Start med familien og ugens madplan. Du kan rette flere sider og gemme ændringerne samlet.</p>
      </div>
      <div class="settings-groups">${groups.map(group => `<section class="card settings-group">
        <h2 class="flush">${group.title}</h2><p class="muted small">${group.help}</p>
        <div class="setting-rows">${group.keys.map(key => row(sections.find(sec => sec.key === key))).join("")}</div>
      </section>`).join("")}</div>
      ${this._dirty ? savebar : ""}`;
  }
}

const STYLE = `
  /* No double-tap zoom; 16 px inputs so a phone doesn't zoom in on them. */
  :host, button, input, select, textarea, .day, .line { touch-action: manipulation; }
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
  .tab.more { display: none; }
  .more-scrim, .more-sheet { display: none; }
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
  .freezer-section { border-top: 1px solid var(--divider-color); margin-top: 24px; padding-top: 8px; text-align: left; }
  .freezer-section.flat { border-top: 0; margin-top: 4px; padding-top: 0; }
  details.fold > summary { cursor: pointer; font-weight: 600; padding: 6px 0; list-style-position: inside; }
  details.fold[open] > summary { margin-bottom: 6px; }
  .freezer-card > summary .fold-title { font-size: 18px; font-weight: 700; }
  .pickday.skipped { opacity: .6; }
  .update-banner { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
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
  .badge.eco, .badge.sent { background: var(--rema-ok); color: var(--rema-on-accent); }
  .badge.from { background: var(--info-color, #039be5); color: #fff; }
  .badge.doubt { background: var(--rema-warn); color: #000; }
  .badge.skipped { background: var(--secondary-text-color); color: var(--rema-on-accent); }
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
  .book { margin-top: 12px; display: grid; grid-template-columns: minmax(0, 1fr) 150px auto; gap: 8px; align-items: center; }
  .book input { min-width: 0; width: 100%; box-sizing: border-box; }
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
    .tab.extra { display: none; }
    .tab.more { display: flex; }
    .more-scrim:not([hidden]) { display: block; position: fixed; inset: 0; z-index: 4; }
    .more-sheet:not([hidden]) { display: flex; flex-direction: column; position: fixed; right: 8px; z-index: 6;
      bottom: calc(var(--rema-tabbar) + 8px); min-width: 200px; padding: 6px; border-radius: 16px;
      background: var(--rema-solid-card); border: 1px solid var(--divider-color); box-shadow: 0 8px 28px rgba(0, 0, 0, .22); }
    .more-item { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: none; border-radius: 10px;
      background: none; color: var(--primary-text-color); font-size: 16px; font-weight: 500; text-align: left; cursor: pointer; }
    .more-item svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .more-item.active { color: var(--rema-accent); background: var(--rema-tint); }
    .tab svg { display: block; }
    main { padding-bottom: calc(96px + var(--rema-tabbar)); }
    .savebar { bottom: calc(8px + var(--rema-tabbar)); }
    .sticky { bottom: var(--rema-tabbar); padding-bottom: 12px; }
    .toast { bottom: calc(16px + var(--rema-tabbar)); }
  }
`;

if (!customElements.get("middagsro-panel")) customElements.define("middagsro-panel", Rema1000Panel);

// For the dashboard cards (middagsro-cards.js), which use the panel's own drawing.
export { Rema1000Panel, STYLE, TAB_ICONS, TYPE_LABELS, WEEKDAYS, esc, kr, kr0, dateLabel, shortDate, sentWhen, localToday };
