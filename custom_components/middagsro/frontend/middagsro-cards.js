/* Middagsro – cards for your own dashboards.

   Loaded by the integration on every dashboard, so there is no resource to add and nothing
   to install in HACS. The cards use the panel's own code (middagsro-panel.js) for the week
   and the wording, and all cards on a page share one connection to Middagsro.

     type: custom:middagsro-week-card              the week's dinners on one line
     type: custom:middagsro-tonight-card           tonight's dinner, and tomorrow's
     type: custom:middagsro-tonight-large-card     tonight's recipe, as on the panel's Opskrifter page
     type: custom:middagsro-shopping-card          the basket and the REMA list, with "Send til REMA"
     type: custom:middagsro-budget-card            the food budget of the week
     type: custom:middagsro-bubble-card            show: tonight | shopping | budget, as a Bubble Card button

   tap_action: popup (default) | panel | none
*/

const VERSION = new URL(import.meta.url).searchParams.get("v") || "";
// The same address as the panel's, so cards and panel share one copy of its code.
const PANEL_URL = new URL(`./middagsro-panel.js${VERSION ? `?v=${encodeURIComponent(VERSION)}` : ""}`, import.meta.url).href;
const STATIC_URL = new URL(".", import.meta.url).pathname.replace(/\/$/, "");
const { Rema1000Panel, TAB_ICONS, TYPE_LABELS, WEEKDAYS, esc, kr, kr0, dateLabel, sentWhen, localToday } = await import(PANEL_URL);

const PANEL_PATH = "/middagsro";
const TAP_ACTIONS = ["popup", "panel", "none"];
const SHOW = ["tonight", "shopping", "budget"];
const DOCS = "https://github.com/Dinnsen/ha-middagsro#cards-for-your-own-dashboards";

const TEXT = {
  card_week: "Middagsro – ugen",
  card_week_desc: "Ugens aftensmåltider på én linje, med i aften fremhævet.",
  card_tonight: "Middagsro – i aften",
  card_tonight_desc: "Aftenens ret med tid og type, og hvad der er i morgen.",
  card_tonight_large: "Middagsro – i aften, stor",
  card_tonight_large_desc: "Aftenens opskrift som i panelet: ingredienser, fremgangsmåde og æggeure.",
  card_shopping: "Middagsro – indkøb",
  card_shopping_desc: "Kurven og REMA-listen, med Send til REMA.",
  card_budget: "Middagsro – økonomi",
  card_budget_desc: "Ugens madbudget: brugt, tilbage og tempoet.",
  card_bubble: "Middagsro – Bubble",
  card_bubble_desc: "I aften, indkøb eller økonomi som en Bubble Card-knap.",
  missing: "Middagsro er ikke sat op.",
  no_plan: "Ingen madplan endnu",
  no_dinner: "Ingen ret i aften",
  tonight: "I aften",
  tomorrow: "I morgen",
  open_panel: "Åbn i Middagsro",
  close: "Luk",
  ed_tap: "Tryk på kortet",
  ed_show: "Vis",
  ed_name: "Navn (valgfrit)",
  tap_popup: "Åbn pop-up",
  tap_panel: "Åbn Middagsro",
  tap_none: "Ingenting",
  show_tonight: "I aften",
  show_shopping: "Indkøb",
  show_budget: "Økonomi",
};

/* Icons for a dish by its type; the rest are the panel's tab icons. */
const ICONS = {
  ...TAB_ICONS,
  normal: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12h16a8 8 0 0 1-16 0z"/><path d="M2.5 12h19M9 8.5c0-1.5 1-1.5 1-3M13 8.5c0-1.5 1-1.5 1-3"/></svg>',
  vegetar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14z"/><path d="M5 19 13 11"/></svg>',
  rester: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="9" width="16" height="10" rx="2"/><path d="M3 9h18M9 6h6"/><path d="M9.5 14a2.5 2.5 0 1 0 2.5-2.5h-1.5M10 10l1.5 1.5L10 13"/></svg>',
  fast: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.6-6-10.5A6 6 0 0 1 18 10.5C18 15.4 12 21 12 21z"/><circle cx="12" cy="10.5" r="2.2"/></svg>',
  tom: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 12h7"/></svg>',
  send: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12 20 4l-6 16-3-6.5z"/><path d="M11 13.5 20 4"/></svg>',
  close: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
};

/* ------------------------------------------------------------------ one connection for all cards */

const stores = new WeakMap();

function storeOf(hass) {
  let store = stores.get(hass.connection);
  if (!store) {
    store = { state: null, error: null, listeners: new Set(), unsub: null, pending: null, timer: null };
    stores.set(hass.connection, store);
  }
  return store;
}

function startStore(store, hass) {
  if (store.unsub || store.pending) return;
  store.pending = hass.connection
    .subscribeMessage(
      (message) => {
        if (message.reload) {
          // Middagsro was reloaded (settings, a new login): subscribe again.
          stopStore(store);
          setTimeout(() => store.listeners.size && startStore(store, hass), 1500);
          return;
        }
        store.state = message;
        store.error = null;
        store.listeners.forEach((listener) => listener());
      },
      { type: "middagsro/subscribe" },
    )
    .then((unsub) => {
      store.unsub = unsub;
      store.pending = null;
      if (!store.listeners.size) stopStore(store);
    })
    .catch((err) => {
      store.pending = null;
      store.error = err || true;
      store.listeners.forEach((listener) => listener());
    });
}

function stopStore(store) {
  const unsub = store.unsub;
  store.unsub = null;
  if (unsub) Promise.resolve(unsub()).catch(() => {});
}

/* Follow Middagsro's state; returns the function that stops following. */
function watch(hass, listener) {
  const store = storeOf(hass);
  store.listeners.add(listener);
  clearTimeout(store.timer);
  startStore(store, hass);
  if (store.state || store.error) queueMicrotask(listener);
  return () => {
    store.listeners.delete(listener);
    // Kept a little, so moving between dashboard views does not subscribe again.
    if (!store.listeners.size) store.timer = setTimeout(() => stopStore(store), 5000);
  };
}

/* ------------------------------------------------------------------ shared helpers */

let sheet = null;
function cardSheet() {
  if (!sheet) {
    sheet = new CSSStyleSheet();
    sheet.replaceSync(CARD_STYLE);
  }
  return sheet;
}

/* The panel's own code for the week, without a panel on the page. */
function makeRenderer(state) {
  const r = Object.create(Rema1000Panel.prototype);
  Object.assign(r, { _state: state, _plan: state?.latest_plan || null, _viewingLatest: true });
  return r;
}

function navigate(path) {
  history.pushState(null, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
}

/* A pop-up through Home Assistant's own dialogs, so it sits above everything (also inside
   a Bubble Card pop-up) and closes with the back button. Outside Home Assistant: on the page. */
function openPopup(source, view, title) {
  const params = { view, title, hass: source._hass };
  if (document.querySelector("home-assistant")) {
    source.dispatchEvent(
      new CustomEvent("show-dialog", {
        bubbles: true,
        composed: true,
        detail: { dialogTag: "middagsro-dialog", dialogImport: () => Promise.resolve(), dialogParams: params },
      }),
    );
    return;
  }
  const dialog = document.body.querySelector("middagsro-dialog") || document.body.appendChild(document.createElement("middagsro-dialog"));
  dialog.showDialog(params);
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const dayShortName = (iso) => WEEKDAYS[(new Date(`${iso}T12:00:00`).getDay() + 6) % 7].slice(0, 3);
const dayIcon = (day) => ICONS[day?.type] || (day ? ICONS.normal : ICONS.tom);
const minutes = (day) => (day?.total_minutes ? `${day.total_minutes} min` : "");

/* Tonight's and the coming dinners: [{date, plan, day}] from the week the panel shows. */
function weekOf(state) {
  const r = makeRenderer(state);
  const timeline = r._timeline();
  if (timeline) return timeline.map((e) => ({ date: e.date, plan: e.plan, day: e.day }));
  const plan = state?.latest_plan;
  return plan ? plan.days.map((day) => ({ date: day.date, plan, day })) : [];
}

/* What the basket and the REMA list hold now. */
function shoppingOf(state) {
  const plan = state?.latest_plan;
  const lines = plan?.shopping || [];
  const open = lines.filter((l) => !l.sent && !l.buy_at);
  const main = open.filter((l) => !l.buy_from);
  const late = open.filter((l) => l.buy_from);
  const sum = (list) => list.reduce((total, l) => total + (Number(l.cost) || 0), 0);
  const list = state?.rema_list;
  const listOpen = (list?.items || []).filter((i) => !i.bought);
  return {
    plan,
    main,
    late,
    mainCost: sum(main),
    lateCost: sum(late),
    sent: lines.filter((l) => l.sent && !l.buy_at).length,
    total: lines.filter((l) => !l.buy_at).length,
    lastSent: plan?.last_sent?.at || null,
    list: list ? { count: listOpen.length, total: list.total } : null,
  };
}

/* ------------------------------------------------------------------ the cards */

class MiddagsroCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.adoptedStyleSheets = [cardSheet()];
    this.shadowRoot.innerHTML = `<ha-card></ha-card>`;
    this._config = {};
    this._html = null;
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    if (config.tap_action && !TAP_ACTIONS.includes(config.tap_action)) {
      throw new Error(`tap_action must be one of: ${TAP_ACTIONS.join(", ")}`);
    }
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first && this.isConnected) this._follow();
    this._render();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this._follow();
    clearInterval(this._tick);
    // "I aften" moves on at midnight, "sendt i dag" becomes "i går".
    this._tick = setInterval(() => this._render(), 60000);
  }

  disconnectedCallback() {
    clearInterval(this._tick);
    this._unwatch?.();
    this._unwatch = null;
  }

  _follow() {
    if (!this._hass || this._unwatch) return;
    this._unwatch = watch(this._hass, () => this._render());
  }

  get _store() {
    return this._hass ? storeOf(this._hass) : null;
  }

  get _state() {
    return this._store?.state || null;
  }

  _render() {
    const card = this.shadowRoot.querySelector("ha-card");
    let html;
    if (!this._hass) html = "";
    else if (this._store?.error && !this._state) html = `<p class="mc-msg">${esc(TEXT.missing)}</p>`;
    else if (!this._state) html = `<div class="mc-loading" aria-busy="true"></div>`;
    else html = this._content();
    if (html === this._html) return;
    this._html = html;
    const focus = this.shadowRoot.activeElement?.dataset?.f;
    card.innerHTML = html;
    if (focus) card.querySelector(`[data-f="${focus}"]`)?.focus({ preventScroll: true });
  }

  _onClick(ev) {
    const el = ev.target.closest("[data-act], [data-view]");
    if (!el || el.disabled) return;
    if (el.dataset.act === "send") {
      ev.stopPropagation();
      this._send(el);
      return;
    }
    if (el.dataset.view) this._tap(el.dataset.view, el.dataset.title, el.dataset.force);
  }

  /* What tapping does: the pop-up, Middagsro on that page, or nothing. */
  _tap(view, title, force) {
    const action = force || this._config.tap_action || "popup";
    if (action === "none") return;
    if (action === "panel") navigate(`${PANEL_PATH}/${view}`);
    else openPopup(this, view, title || "Middagsro");
  }

  /* "Send til REMA": the basket onto the REMA list, as the panel's button does. */
  async _send(el) {
    const s = shoppingOf(this._state);
    if (!s.plan || !s.main.length) return;
    const week = this._state.budget?.week;
    if (week && s.mainCost > week.remaining
      && !confirm(`Listen er anslået til ${kr0(s.mainCost)}, men der er kun ${kr0(week.remaining)} tilbage af ugens madbudget. Send den alligevel?`)) return;
    el.disabled = true;
    try {
      const message = { type: "middagsro/send", plan_id: s.plan.id, part: "main" };
      if (this._state.entry_id) message.entry_id = this._state.entry_id;
      await this._hass.callWS(message);
      this._notify("Indkøbslisten er sendt til REMA 1000-appen.");
    } catch (err) {
      this._notify(`Fejl: ${err?.message || err}`);
    } finally {
      el.disabled = false;
    }
  }

  _notify(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { bubbles: true, composed: true, detail: { message } }));
  }

  getCardSize() {
    return 2;
  }

  static getConfigElement() {
    return document.createElement("middagsro-card-editor");
  }

  static async getStubConfig() {
    return {};
  }
}

/* The week's dinners on one line. */
class WeekCard extends MiddagsroCard {
  _content() {
    const today = localToday();
    const all = weekOf(this._state);
    if (!all.length) return this._empty();
    // The panel's week starts on the family's first weekday; show the seven days with today.
    const at = all.findIndex((e) => e.date >= today);
    const start = at >= 7 ? at - (at % 7) : 0;
    const days = all.slice(start, start + 7);
    const chips = days.map((e) => {
      const isToday = e.date === today;
      const name = e.day?.dish || "Ingen ret";
      return `<button class="mw-day ${isToday ? "today" : ""} ${e.date < today ? "past" : ""} type-${esc(e.day?.type || "tom")}"
          data-view="recipes/${esc(e.date)}" data-title="${esc(name)}" data-f="d-${esc(e.date)}" aria-label="${esc(`${dateLabel(e.date)}: ${name}`)}">
        <span class="mw-when">${isToday ? TEXT.tonight : esc(dayShortName(e.date))}<i>${new Date(`${e.date}T12:00:00`).getDate()}</i></span>
        <span class="mw-icon">${dayIcon(e.day)}</span>
        <b>${esc(name)}</b>
        ${e.day && TYPE_LABELS[e.day.type] ? `<small>${esc(TYPE_LABELS[e.day.type])}</small>` : e.day?.total_minutes ? `<small>${esc(minutes(e.day))}</small>` : ""}
      </button>`;
    });
    return `<div class="mw" role="list" lang="da">${chips.join("")}</div>`;
  }

  _render() {
    const before = this._html;
    super._render();
    // Today in view when the week first shows (a phone shows three or four days).
    if (this._html !== before && !this._scrolled) {
      const strip = this.shadowRoot.querySelector(".mw");
      const today = strip?.querySelector(".mw-day.today");
      if (strip && today) {
        this._scrolled = true;
        strip.scrollLeft = Math.max(0, today.offsetLeft - strip.offsetLeft - 10);
      }
    }
  }

  _empty() {
    return `<button class="mc static-open" data-view="plan" data-title="Middagsro" data-f="card">
      <span class="mc-head"><span class="mc-pic">${ICONS.plan}</span><span class="mc-name"><strong>${esc(TEXT.no_plan)}</strong><span>Lav madplanen i Middagsro</span></span></span>
    </button>`;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }
}

/* Tonight's dinner, and tomorrow's. */
class TonightCard extends MiddagsroCard {
  _content() {
    const today = localToday();
    const week = weekOf(this._state);
    const at = week.findIndex((e) => e.date === today);
    const tonight = at >= 0 ? week[at] : null;
    const tomorrow = at >= 0 ? week[at + 1] : week.find((e) => e.date > today);
    const day = tonight?.day;
    const title = this._config.name || TEXT.tonight;
    const meta = [
      day?.total_minutes ? `${day.total_minutes} min` : "",
      day?.servings ? `${day.servings} pers.` : "",
      day && TYPE_LABELS[day.type] ? TYPE_LABELS[day.type] : "",
    ].filter(Boolean);
    const note = day?.uses_leftovers_from ? `Rester fra ${dateLabel(day.uses_leftovers_from)}` : day?.makes_leftovers ? "Lav dobbelt portion" : "";
    return `<button class="mc" data-view="recipes/${esc(today)}" data-title="${esc(day?.dish || title)}" data-f="card" aria-label="${esc(`${title}: ${day?.dish || TEXT.no_dinner}`)}">
      <span class="mc-head">
        <span class="mc-pic type-${esc(day?.type || "tom")}">${dayIcon(day)}</span>
        <span class="mc-name"><span class="mc-over">${esc(title)}</span><strong>${esc(day?.dish || (week.length ? TEXT.no_dinner : TEXT.no_plan))}</strong></span>
      </span>
      ${meta.length ? `<span class="mc-tags">${meta.map((m) => `<span class="mc-tag">${esc(m)}</span>`).join("")}</span>` : ""}
      ${note ? `<span class="mc-note">${esc(note)}</span>` : ""}
      ${tomorrow ? `<span class="mc-row"><span class="soft">${esc(TEXT.tomorrow)}</span><span class="mc-next">${esc(tomorrow.day?.dish || "Ingen ret")}</span></span>` : ""}
    </button>`;
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }
}

/* Tonight's recipe: the panel's own Opskrifter page, in the card. */
class TonightLargeCard extends MiddagsroCard {
  constructor() {
    super();
    this.shadowRoot.querySelector("ha-card").classList.add("large");
  }

  _render() {
    if (!this._hass) return;
    const card = this.shadowRoot.querySelector("ha-card");
    if (!this._panelEl) {
      const panel = document.createElement("middagsro-panel");
      panel.panel = { config: { static_url: STATIC_URL, version: VERSION } };
      panel.narrow = true;
      panel.embed = { view: `recipes/${localToday()}` };
      card.replaceChildren(panel);
      this._panelEl = panel;
    }
    this._panelEl.hass = this._hass;
  }

  _follow() {}

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }
}

/* The basket and the REMA list. */
class ShoppingCard extends MiddagsroCard {
  _content() {
    const s = shoppingOf(this._state);
    const title = this._config.name || "Indkøb";
    if (!s.plan) {
      return `<button class="mc" data-view="shopping" data-title="${esc(title)}" data-f="card">
        <span class="mc-head"><span class="mc-pic">${ICONS.shopping}</span><span class="mc-name"><strong>${esc(title)}</strong><span>${esc(TEXT.no_plan)}</span></span></span>
        ${s.list ? `<span class="mc-row"><span class="soft">På REMA-listen</span><b>${esc(plural(s.list.count, "vare", "varer"))} · ${kr(s.list.total)}</b></span>` : ""}
      </button>`;
    }
    const status = s.main.length
      ? `${plural(s.main.length, "vare", "varer")} · ${kr(s.mainCost)}`
      : s.lastSent ? `Sendt ${sentWhen(s.lastSent)}` : "Kurven er tom";
    const share = s.total ? Math.round((s.sent / s.total) * 100) : 0;
    return `<div class="mc static">
      <button class="mc-open" data-view="shopping" data-title="${esc(title)}" data-f="card" aria-label="Åbn indkøb">
        <span class="mc-head between">
          <span class="mc-head"><span class="mc-pic">${ICONS.shopping}</span><span class="mc-name"><strong>${esc(title)}</strong><span>${esc(status)}</span></span></span>
          ${s.main.length ? "" : s.sent ? `<span class="mc-pill ok">Sendt</span>` : ""}
        </span>
        ${s.sent ? `<span class="mc-bar" role="img" aria-label="${share} % af listen er sendt"><i style="width:${share}%"></i></span>
          <span class="mc-row"><span class="soft">Sendt til REMA</span><b>${s.sent} af ${s.total}</b></span>` : ""}
        ${s.late.length ? `<span class="mc-row"><span class="soft">Senere på ugen</span><b>${esc(plural(s.late.length, "vare", "varer"))} · ${kr(s.lateCost)}</b></span>` : ""}
        ${s.list ? `<span class="mc-row"><span class="soft">På REMA-listen nu</span><b>${esc(plural(s.list.count, "vare", "varer"))} · ${kr(s.list.total)}</b></span>` : ""}
      </button>
      ${s.main.length ? `<button class="mc-btn primary" data-act="send" data-f="send" aria-label="Send ${esc(plural(s.main.length, "vare", "varer"))} til REMA">${ICONS.send}<span>Send til REMA</span></button>` : ""}
    </div>`;
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }
}

/* The food budget of the week. */
class BudgetCard extends MiddagsroCard {
  _content() {
    const b = this._state.budget;
    const title = this._config.name || "Madbudget";
    if (!b) {
      return `<button class="mc" data-view="settings" data-title="${esc(title)}" data-force="panel" data-f="card">
        <span class="mc-head"><span class="mc-pic">${ICONS.budget}</span><span class="mc-name"><strong>${esc(title)}</strong><span>Intet madbudget – sæt det under Indstillinger</span></span></span>
      </button>`;
    }
    const w = b.week;
    const over = w.remaining < 0;
    const used = w.available > 0 ? Math.min(100, Math.max(0, (w.spent / w.available) * 100)) : 100;
    const pace = w.available > 0 ? Math.min(100, Math.max(0, (w.pace / w.available) * 100)) : 0;
    const ahead = !over && w.spent > w.pace * 1.1;
    return `<button class="mc" data-view="budget" data-title="${esc(title)}" data-f="card" aria-label="Åbn økonomien">
      <span class="mc-head between">
        <span class="mc-head"><span class="mc-pic">${ICONS.budget}</span><span class="mc-name"><strong>${esc(title)}</strong><span>Uge ${esc(w.week)}</span></span></span>
        <span class="mc-pill ${over ? "bad" : ahead ? "warn" : "ok"}">${over ? "Over" : ahead ? "Foran tempoet" : "I tempo"}</span>
      </span>
      <span class="mc-big ${over ? "bad" : ""}">${kr0(Math.abs(w.remaining))}<small>${over ? "over budgettet" : `tilbage · ${kr0(Math.max(0, w.per_day))} om dagen`}</small></span>
      <span class="mc-bar ${over ? "bad" : ahead ? "warn" : ""}" role="img" aria-label="Brugt ${kr0(w.spent)} af ${kr0(w.available)}"><i style="width:${used.toFixed(1)}%"></i><em style="left:${pace.toFixed(1)}%"></em></span>
      <span class="mc-row"><span class="soft">Brugt ${kr0(w.spent)} af ${kr0(w.available)}</span>${w.planned > 0 ? `<span class="soft">Lister: ${kr0(w.planned)}</span>` : ""}</span>
      ${b.month ? `<span class="mc-row"><span class="soft">Måneden</span><b>${kr0(b.month.spent)}${b.month.forecast ? ` · prognose ${kr0(b.month.forecast)}` : ""}</b></span>` : ""}
    </button>`;
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }
}

/* Tonight, the basket or the budget as one Bubble Card button: Bubble's measures and
   its --bubble-* variables, so a theme that styles Bubble Card styles this too. */
class BubbleCard extends MiddagsroCard {
  setConfig(config) {
    if (config?.show && !SHOW.includes(config.show)) throw new Error(`show must be one of: ${SHOW.join(", ")}`);
    super.setConfig(config);
  }

  _content() {
    const show = this._config.show || "tonight";
    if (show === "shopping") return this._shopping();
    if (show === "budget") return this._budget();
    return this._tonight();
  }

  _shell({ view, title, label, icon, name, state, fill = null, mark = null, on = false, subs = "", tone = "" }) {
    const filled = fill !== null && Number.isFinite(Number(fill));
    return `<div class="bub ${on ? "is-on" : ""} ${tone}">
      ${filled ? `<i class="bub-fill" style="width:${Math.min(100, Math.max(0, Number(fill)))}%"></i>` : ""}
      ${filled && mark !== null ? `<i class="bub-target" style="left:${Math.min(100, Math.max(0, Number(mark)))}%"></i>` : ""}
      <button class="bub-main" data-view="${esc(view)}" data-title="${esc(title)}" data-f="card" aria-label="${esc(label)}">
        <span class="bub-icon">${icon}</span>
        <span class="bub-name"><b>${esc(name)}</b><span>${esc(state)}</span></span>
      </button>
      ${subs ? `<span class="bub-subs">${subs}</span>` : ""}
    </div>`;
  }

  _tonight() {
    const today = localToday();
    const week = weekOf(this._state);
    const at = week.findIndex((e) => e.date === today);
    const day = at >= 0 ? week[at].day : null;
    const tomorrow = at >= 0 ? week[at + 1] : null;
    const state = [this._config.name || TEXT.tonight, day && TYPE_LABELS[day.type] ? TYPE_LABELS[day.type] : "", tomorrow?.day ? `i morgen ${tomorrow.day.dish}` : ""]
      .filter(Boolean)
      .join(" · ");
    return this._shell({
      view: `recipes/${today}`,
      title: day?.dish || TEXT.tonight,
      label: `${TEXT.tonight}: ${day?.dish || TEXT.no_dinner}`,
      icon: dayIcon(day),
      name: day?.dish || (week.length ? TEXT.no_dinner : TEXT.no_plan),
      state,
      subs: day?.total_minutes ? `<span class="bub-sub info">${esc(minutes(day))}</span>` : "",
    });
  }

  _shopping() {
    const s = shoppingOf(this._state);
    const name = this._config.name || "Indkøb";
    const state = !s.plan
      ? s.list ? `REMA-listen: ${plural(s.list.count, "vare", "varer")}` : TEXT.no_plan
      : s.main.length
        ? `${plural(s.main.length, "vare", "varer")} · ${kr(s.mainCost)}`
        : s.lastSent ? `Sendt ${sentWhen(s.lastSent)}` : "Kurven er tom";
    return this._shell({
      view: "shopping",
      title: name,
      label: `${name}: ${state}`,
      icon: ICONS.shopping,
      name,
      state,
      fill: s.total ? (s.sent / s.total) * 100 : null,
      subs: s.main.length
        ? `<button class="bub-sub on" data-act="send" data-f="send" aria-label="Send ${esc(plural(s.main.length, "vare", "varer"))} til REMA">${ICONS.send}<span>Send</span></button>`
        : s.list ? `<span class="bub-sub info">${kr(s.list.total)}</span>` : "",
    });
  }

  _budget() {
    const b = this._state.budget;
    const name = this._config.name || "Madbudget";
    if (!b) {
      return this._shell({ view: "settings", title: name, label: name, icon: ICONS.budget, name, state: "Intet madbudget" });
    }
    const w = b.week;
    const over = w.remaining < 0;
    return this._shell({
      view: "budget",
      title: name,
      label: `${name}: ${kr0(w.remaining)} tilbage`,
      icon: ICONS.budget,
      name,
      state: over ? `${kr0(-w.remaining)} over · uge ${w.week}` : `${kr0(Math.max(0, w.per_day))} om dagen · uge ${w.week}`,
      fill: w.available > 0 ? (w.spent / w.available) * 100 : 100,
      mark: w.available > 0 ? (w.pace / w.available) * 100 : null,
      tone: over ? "bub-over" : "",
      subs: `<span class="bub-sub info">${over ? "−" : ""}${kr0(Math.abs(w.remaining))}</span>`,
    });
  }

  static async getStubConfig() {
    return { show: "tonight" };
  }

  getCardSize() {
    return 1;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 1, min_rows: 1, max_rows: 1 };
  }
}

/* ------------------------------------------------------------------ the pop-up */

class MiddagsroDialog extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._onKey = (ev) => {
      if (ev.key === "Escape" && this._open && !this._panelEl?._modal) this._close();
    };
  }

  set hass(hass) {
    this._hass = hass;
    if (this._panelEl) this._panelEl.hass = hass;
  }

  /* Called by Home Assistant's dialog manager (or by the card outside Home Assistant). */
  showDialog(params) {
    this._hass = params?.hass || this._hass;
    this._view = params?.view || "plan";
    this._open = true;
    this.hidden = false;
    this.shadowRoot.innerHTML = `<style>${DIALOG_STYLE}</style>
      <div class="scrim"></div>
      <section class="sheet" role="dialog" aria-modal="true" tabindex="-1" aria-label="${esc(params?.title || "Middagsro")}">
        <header>
          <span class="grab" aria-hidden="true"></span>
          <h2>${esc(params?.title || "")}</h2>
          <a class="open" href="${PANEL_PATH}/${esc(this._view)}">${esc(TEXT.open_panel)} ›</a>
          <button class="close" aria-label="${esc(TEXT.close)}">${ICONS.close}</button>
        </header>
        <div class="body"></div>
      </section>`;
    const panel = document.createElement("middagsro-panel");
    panel.panel = { config: { static_url: STATIC_URL, version: VERSION } };
    panel.narrow = innerWidth < 870;
    panel.embed = { view: this._view };
    this.shadowRoot.querySelector(".body").appendChild(panel);
    this._panelEl = panel;
    if (this._hass) panel.hass = this._hass;
    this.shadowRoot.querySelector(".scrim").addEventListener("click", () => this._close());
    this.shadowRoot.querySelector(".close").addEventListener("click", () => this._close());
    this.shadowRoot.querySelector(".open").addEventListener("click", (ev) => {
      ev.preventDefault();
      const path = `${PANEL_PATH}/${panel._path || this._view}`;
      this._close();
      // After the dialog's history entry is gone, or the panel would be closed again.
      setTimeout(() => navigate(path), 60);
    });
    this._dragToClose(this.shadowRoot.querySelector("header"));
    document.addEventListener("keydown", this._onKey);
    requestAnimationFrame(() => this.shadowRoot.querySelector(".sheet")?.focus({ preventScroll: true }));
  }

  /* Called by Home Assistant when the dialog's history entry goes (the back button). */
  closeDialog() {
    this._teardown();
    return true;
  }

  _close() {
    if (!this._open) return;
    this._teardown();
    this.dispatchEvent(new CustomEvent("dialog-closed", { bubbles: true, composed: true, detail: { dialog: this.localName } }));
  }

  _teardown() {
    this._open = false;
    document.removeEventListener("keydown", this._onKey);
    this._panelEl?.remove();
    this._panelEl = null;
    this.shadowRoot.innerHTML = "";
    this.hidden = true;
  }

  /* On a phone the sheet can be pulled down to close it. */
  _dragToClose(handle) {
    const sheetEl = this.shadowRoot.querySelector(".sheet");
    let startY = null;
    handle.addEventListener("touchstart", (ev) => (startY = ev.touches.length === 1 ? ev.touches[0].clientY : null), { passive: true });
    handle.addEventListener(
      "touchmove",
      (ev) => {
        if (startY === null) return;
        sheetEl.style.transform = `translateY(${Math.max(0, ev.touches[0].clientY - startY)}px)`;
      },
      { passive: true },
    );
    const end = (ev) => {
      if (startY === null) return;
      const dy = (ev.changedTouches?.[0]?.clientY ?? startY) - startY;
      startY = null;
      sheetEl.style.transform = "";
      if (dy > 90) this._close();
    };
    handle.addEventListener("touchend", end, { passive: true });
    handle.addEventListener("touchcancel", end, { passive: true });
  }
}

/* ------------------------------------------------------------------ the card editor */

class MiddagsroCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  get _kind() {
    return String(this._config?.type || "").replace("custom:middagsro-", "").replace("-card", "");
  }

  _schema() {
    const tap = {
      name: "tap_action",
      selector: { select: { mode: "dropdown", options: TAP_ACTIONS.map((value) => ({ value, label: TEXT[`tap_${value}`] })) } },
    };
    const name = { name: "name", selector: { text: {} } };
    switch (this._kind) {
      case "bubble":
        return [{ name: "show", selector: { select: { mode: "dropdown", options: SHOW.map((value) => ({ value, label: TEXT[`show_${value}`] })) } } }, name, tap];
      case "tonight-large":
        return [];
      case "week":
        return [tap];
      default:
        return [name, tap];
    }
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        const value = { ...ev.detail.value };
        for (const key of Object.keys(value)) if (value[key] === "" || value[key] === undefined) delete value[key];
        if (value.tap_action === "popup") delete value.tap_action;
        this._config = { type: this._config.type, ...value };
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const labels = { show: "ed_show", name: "ed_name", tap_action: "ed_tap" };
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = { tap_action: "popup", ...(this._kind === "bubble" ? { show: "tonight" } : {}), ...this._config };
    this._form.computeLabel = (item) => TEXT[labels[item.name]] || item.name;
  }
}

/* ------------------------------------------------------------------ styles */

/* Themes reach the cards through Home Assistant's own variables (--ha-card-*), Theme Studio's
   (--theme-studio-*) and, for the Bubble card, Bubble Card's (--bubble-*). Each has a fallback,
   so the cards look like Home Assistant's own without them. */
const CARD_STYLE = `
:host {
  display: block; height: auto; background: none;
  --mc-ink: var(--primary-text-color, #1c1c1c);
  --mc-soft: var(--secondary-text-color, #5e5e5e);
  --mc-accent: var(--primary-color, #009ac7);
  --mc-ok: var(--success-color, #43a047);
  --mc-warn: var(--warning-color, #ffa600);
  --mc-bad: var(--error-color, #db4437);
  --mc-surface: var(--theme-studio-soft-background-color, color-mix(in srgb, var(--mc-ink) 5%, transparent));
  --mc-chip-radius: var(--theme-studio-chip-radius, 14px);
  /* Theme Studio's glass blur is for the cards that ask for it; these do. */
  --ha-card-backdrop-filter: var(--theme-studio-card-backdrop-filter, none);
  font-family: var(--ha-font-family-body, Roboto, system-ui, sans-serif);
}
* { box-sizing: border-box; }
ha-card { height: 100%; overflow: hidden; color: var(--mc-ink); }
/* The large card is the panel's own page: its chips and its recipe card, on the dashboard. */
:host(middagsro-tonight-large-card) { --ha-card-backdrop-filter: none; }
ha-card.large { overflow: visible; background: none; border: 0; box-shadow: none; }
ha-card.large middagsro-panel { --rema-safe-bottom: 0px; }
svg { fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.mc, .mc-open { position: relative; display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; align-content: start; width: 100%; min-width: 0; border: 0; background: none; color: inherit; font: inherit; text-align: left; cursor: pointer; }
.mc { height: 100%; padding: 14px 16px 16px; overflow: hidden; }
.mc.static { cursor: default; }
.mc-open { padding: 0; border-radius: 10px; }
.mc:focus-visible, .mc-open:focus-visible, .mw-day:focus-visible, .mc-btn:focus-visible { outline: 2px solid var(--mc-accent); outline-offset: -2px; }
.mc-head { display: flex; align-items: center; gap: 10px; min-width: 0; }
.mc-head.between { justify-content: space-between; flex-wrap: wrap; gap: 6px; }
.mc-pic { width: 44px; height: 44px; flex: none; border-radius: var(--mc-chip-radius); display: grid; place-items: center; color: var(--mc-accent); background: var(--mc-surface); }
.mc-pic svg { width: 24px; height: 24px; }
.mc-pic.type-vegetar { color: var(--mc-ok); }
.mc-pic.type-rester, .mc-pic.type-fast { color: var(--mc-warn); }
.mc-pic.type-tom { color: var(--mc-soft); }
.mc-name { display: grid; min-width: 0; gap: 1px; }
.mc-name strong { font-size: 15.5px; font-weight: 600; line-height: 1.25; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.mc-name > span { color: var(--mc-soft); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mc-over { color: var(--mc-accent) !important; font-size: 12px !important; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
.mc-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.mc-tag { padding: 3px 10px; border-radius: 999px; background: var(--mc-surface); font-size: 12.5px; color: var(--mc-soft); }
.mc-note { font-size: 13px; color: var(--mc-soft); }
.mc-row { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 2px 10px; font-size: 13.5px; font-variant-numeric: tabular-nums; min-width: 0; }
.mc-row .soft { color: var(--mc-soft); }
.mc-next { font-weight: 500; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; text-align: right; }
.mc-pill { padding: 3px 10px; border-radius: 999px; font-size: 12.5px; font-weight: 600; white-space: nowrap; background: var(--mc-surface); }
.mc-pill.ok { color: var(--mc-ok); background: color-mix(in srgb, var(--mc-ok) 14%, transparent); }
.mc-pill.warn { color: color-mix(in srgb, var(--mc-warn) 70%, var(--mc-ink)); background: color-mix(in srgb, var(--mc-warn) 16%, transparent); }
.mc-pill.bad { color: var(--mc-bad); background: color-mix(in srgb, var(--mc-bad) 14%, transparent); }
.mc-big { display: grid; font-size: 28px; font-weight: 700; letter-spacing: -.02em; font-variant-numeric: tabular-nums; line-height: 1.1; }
.mc-big.bad { color: var(--mc-bad); }
.mc-big small { font-size: 13px; font-weight: 400; letter-spacing: 0; color: var(--mc-soft); }
.mc-bar { position: relative; display: block; height: 8px; border-radius: 999px; background: var(--mc-surface); overflow: hidden; }
.mc-bar i { position: absolute; inset: 0 auto 0 0; border-radius: 999px; background: var(--mc-accent); transition: width .5s ease; }
.mc-bar.warn i { background: var(--mc-warn); } .mc-bar.bad i { background: var(--mc-bad); }
.mc-bar em { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: var(--mc-ink); opacity: .45; }
.mc-btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 42px; padding: 10px 14px; border: 0; border-radius: var(--mc-chip-radius); background: var(--mc-surface); color: inherit; font: inherit; font-weight: 600; cursor: pointer; }
.mc-btn.primary { background: var(--mc-accent); color: var(--text-primary-color, #fff); }
.mc-btn[disabled] { opacity: .6; cursor: default; }
.mc-btn svg { width: 18px; height: 18px; }
.mc-msg { margin: 0; padding: 16px; color: var(--mc-soft); }
.mc-loading { height: 96px; margin: 14px; border-radius: 12px; background: linear-gradient(90deg, var(--mc-surface), color-mix(in srgb, var(--mc-ink) 9%, transparent), var(--mc-surface)); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }

/* The week */
.mw { display: flex; gap: 8px; padding: 10px; overflow-x: auto; scroll-snap-type: x proximity; scrollbar-width: none; overscroll-behavior-x: contain; }
.mw::-webkit-scrollbar { display: none; }
.mw-day { flex: 1 0 96px; max-width: 160px; min-width: 0; scroll-snap-align: start; display: grid; justify-items: start; align-content: start; gap: 6px; padding: 10px 10px 11px; border: 0; border-radius: var(--mc-chip-radius); background: var(--mc-surface); color: inherit; font: inherit; text-align: left; cursor: pointer; }
.mw-day.today { background: color-mix(in srgb, var(--mc-accent) 16%, var(--mc-surface)); box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--mc-accent) 60%, transparent); }
.mw-day.past { opacity: .55; }
.mw-when { display: flex; width: 100%; justify-content: space-between; align-items: baseline; font-size: 12px; font-weight: 600; color: var(--mc-soft); text-transform: uppercase; letter-spacing: .04em; }
.mw-day.today .mw-when { color: var(--mc-accent); }
.mw-when i { font-style: normal; font-size: 13px; font-variant-numeric: tabular-nums; }
.mw-icon { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; color: var(--mc-accent); background: color-mix(in srgb, var(--mc-accent) 12%, transparent); }
.mw-icon svg { width: 18px; height: 18px; }
.mw-day.type-vegetar .mw-icon { color: var(--mc-ok); background: color-mix(in srgb, var(--mc-ok) 13%, transparent); }
.mw-day.type-rester .mw-icon, .mw-day.type-fast .mw-icon { color: var(--mc-warn); background: color-mix(in srgb, var(--mc-warn) 14%, transparent); }
.mw-day.type-tom .mw-icon { color: var(--mc-soft); background: var(--mc-surface); }
.mw-day b { font-size: 13px; font-weight: 600; line-height: 1.25; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow-wrap: break-word; hyphens: auto; }
.mw-day small { font-size: 12px; color: var(--mc-soft); }

/* The Bubble card: Bubble Card's button, measure for measure, and its variables. */
:host(middagsro-bubble-card) { --ha-card-backdrop-filter: none; }
:host(middagsro-bubble-card) ha-card { background: none; border: 0; box-shadow: none; border-radius: 0; overflow: visible; container-type: inline-size; }
.bub {
  --bub-radius: var(--bubble-button-border-radius, var(--bubble-border-radius, calc(var(--row-height, 56px) / 2)));
  --bub-accent: var(--bubble-button-accent-color, var(--bubble-accent-color, var(--bubble-default-color, var(--accent-color, var(--primary-color)))));
  --bub-sub-bg: var(--bubble-sub-button-background-color, var(--bubble-icon-background-color, var(--bubble-secondary-background-color, var(--card-background-color, var(--ha-card-background)))));
  position: relative; display: flex; align-items: center; height: 50px; width: 100%; overflow: hidden; overflow: clip;
  border-radius: var(--bub-radius);
  background-color: var(--bubble-button-main-background-color, var(--bubble-main-background-color, var(--background-color-2, var(--secondary-background-color))));
  box-shadow: var(--bubble-button-box-shadow, var(--bubble-box-shadow, none));
  border: var(--bubble-button-border, var(--bubble-border, none));
  color: var(--primary-text-color);
  -webkit-tap-highlight-color: transparent;
}
.bub-fill { position: absolute; inset: 0 auto 0 0; background-color: var(--bub-accent); transition: width .5s ease-in-out; pointer-events: none; }
.bub.bub-over .bub-fill { background-color: color-mix(in srgb, var(--mc-bad) 45%, var(--bub-accent)); }
.bub-target { position: absolute; top: 10px; bottom: 10px; width: 2px; margin-left: -1px; border-radius: 1px; pointer-events: none; background: color-mix(in srgb, var(--primary-text-color) 32%, transparent); }
.bub-main { position: relative; display: flex; align-items: center; flex: 1; min-width: 0; height: 100%; padding: 0; border: 0; background: none; color: inherit; font: inherit; text-align: left; cursor: pointer; border-radius: var(--bub-radius); }
.bub-main:focus-visible, .bub-sub:focus-visible { outline: 2px solid var(--bub-accent); outline-offset: -2px; }
.bub-icon {
  position: relative; display: grid; place-items: center; flex: none; width: 38px; height: 38px; margin: 6px; overflow: hidden;
  border-radius: var(--bubble-button-icon-border-radius, var(--bubble-icon-border-radius, var(--bubble-border-radius, 50%)));
  background-color: var(--bubble-button-icon-background-color, var(--bubble-icon-background-color, var(--bubble-secondary-background-color, var(--card-background-color, var(--ha-card-background)))));
  color: var(--bubble-icon-color, var(--primary-text-color));
}
.bub-icon > svg { width: 22px; height: 22px; }
.bub-name { display: flex; flex-direction: column; justify-content: center; flex: 1; min-width: 0; margin: 0 16px 0 4px; line-height: 18px; }
.bub-name b { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bub-name > span { font-size: 12px; opacity: .7; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-variant-numeric: tabular-nums; }
.bub-subs { position: relative; display: flex; align-items: center; gap: 8px; margin-right: 8px; flex: none; }
.bub-sub {
  display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-width: 36px; height: var(--bubble-sub-button-height, 36px); padding: 0 8px;
  border: 0; border-radius: var(--bubble-sub-button-border-radius, var(--bubble-border-radius, 18px));
  background-color: var(--bub-sub-bg); color: var(--primary-text-color); font: inherit; font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums;
}
button.bub-sub { cursor: pointer; }
button.bub-sub[disabled] { opacity: .6; }
.bub-sub.on { background-color: var(--bubble-sub-button-light-background-color, var(--bub-accent)); }
.bub-sub > svg { width: 18px; height: 18px; flex: none; stroke-width: 2; }
.bub .mc-msg { padding: 0 18px; font-size: 13px; }
@container (max-width: 250px) { .bub-sub > span { display: none; } }
@media (prefers-reduced-motion: reduce) { .bub-fill, .mc-bar i { transition: none; } .mc-loading { animation: none; } }
`;

const DIALOG_STYLE = `
:host { position: fixed; inset: 0; z-index: 1000; display: block; --md-radius: var(--bubble-pop-up-border-radius, var(--ha-dialog-border-radius, 24px)); }
/* Closed: nothing on the screen, and nothing in the way of taps. */
:host([hidden]) { display: none; }
/* Like Home Assistant's own dialogs, and like a Bubble pop-up where the theme styles those
   (Theme Studio does): the scrim, the surface, the corners, the border and the shadow. */
.scrim {
  position: absolute; inset: 0; background: var(--mdc-dialog-scrim-color, rgba(0, 0, 0, .45)); animation: fade .2s ease;
  -webkit-backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none); backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none);
}
.sheet {
  position: absolute; left: 50%; bottom: 0; translate: -50% 0; width: 100%; height: min(92dvh, 100% - 24px);
  display: flex; flex-direction: column; overflow: hidden; border-radius: var(--md-radius) var(--md-radius) 0 0; box-sizing: border-box;
  background: var(--bubble-pop-up-background-color, var(--ha-dialog-surface-background, var(--primary-background-color, #fafafa)));
  -webkit-backdrop-filter: var(--theme-studio-card-backdrop-filter, none); backdrop-filter: var(--theme-studio-card-backdrop-filter, none);
  border: var(--theme-studio-popup-border-css, var(--bubble-pop-up-border, none)); border-bottom: 0;
  color: var(--primary-text-color, #1c1c1c);
  box-shadow: var(--theme-studio-popup-shadow-css, 0 -10px 40px rgba(0, 0, 0, .25)); animation: up .32s cubic-bezier(.2, .8, .2, 1);
  font-family: var(--ha-font-family-body, Roboto, system-ui, sans-serif);
}
header { position: relative; display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 8px; padding: 16px 12px 6px 20px; touch-action: none; }
.grab { position: absolute; top: 6px; left: 50%; width: 40px; height: 5px; margin-left: -20px; border-radius: 3px; background: color-mix(in srgb, var(--primary-text-color, #000) 22%, transparent); }
h2 { margin: 0; font-size: 19px; font-weight: 650; letter-spacing: -.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.open { color: var(--primary-color, #009ac7); font-size: 14px; font-weight: 500; text-decoration: none; white-space: nowrap; }
.close { width: 40px; height: 40px; border: 0; border-radius: 12px; background: transparent; color: inherit; display: grid; place-items: center; cursor: pointer; }
.close svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; }
.sheet:focus { outline: none; }
.close:hover { background: color-mix(in srgb, var(--primary-text-color, #000) 7%, transparent); }
.close:focus-visible, .open:focus-visible { outline: 2px solid var(--primary-color, #009ac7); outline-offset: 2px; }
.body { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.body middagsro-panel { --rema-safe-bottom: env(safe-area-inset-bottom, 0px); }
@media (min-width: 870px) {
  .sheet { top: 50%; bottom: auto; width: min(1080px, 94vw); height: min(88dvh, 960px); border-radius: var(--md-radius); border-bottom: var(--theme-studio-popup-border-css, var(--bubble-pop-up-border, none)); translate: -50% -50%; animation: pop .25s cubic-bezier(.2, .8, .2, 1); }
  .grab { display: none; }
}
@keyframes fade { from { opacity: 0; } }
@keyframes up { from { transform: translateY(100%); } }
@keyframes pop { from { opacity: 0; transform: scale(.97); } }
@media (prefers-reduced-motion: reduce) { .scrim, .sheet { animation: none; } }
`;

/* ------------------------------------------------------------------ registration */

const CARDS = [
  ["middagsro-week-card", WeekCard, "card_week"],
  ["middagsro-tonight-card", TonightCard, "card_tonight"],
  ["middagsro-tonight-large-card", TonightLargeCard, "card_tonight_large"],
  ["middagsro-shopping-card", ShoppingCard, "card_shopping"],
  ["middagsro-budget-card", BudgetCard, "card_budget"],
  ["middagsro-bubble-card", BubbleCard, "card_bubble"],
];

for (const [tag, cls] of CARDS) if (!customElements.get(tag)) customElements.define(tag, cls);
if (!customElements.get("middagsro-dialog")) customElements.define("middagsro-dialog", MiddagsroDialog);
if (!customElements.get("middagsro-card-editor")) customElements.define("middagsro-card-editor", MiddagsroCardEditor);

window.customCards = window.customCards || [];
for (const [tag, , key] of CARDS) {
  if (window.customCards.some((card) => card.type === tag)) continue;
  window.customCards.push({ type: tag, name: TEXT[key], description: TEXT[`${key}_desc`], preview: true, documentationURL: DOCS });
}

export { WeekCard, TonightCard, TonightLargeCard, ShoppingCard, BudgetCard, BubbleCard, MiddagsroDialog, MiddagsroCardEditor, watch };
