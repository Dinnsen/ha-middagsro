/* REMA 1000 – madplan-panel til Home Assistant. Ingen build-trin, ingen afhængigheder. */

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
const TYPE_LABELS = { normal: "", vegetar: "Vegetar", rester: "Rester", fast: "Fast dag" };
const EGG_LABELS = {
  caged: "Skrabeæg (alle æg)",
  free_range: "Mindst frilandsæg",
  organic: "Kun økologiske æg",
};
const onOffer = (p) =>
  Boolean(p.is_advertised || p.is_campaign || (p.normal_price && p.price && p.price < p.normal_price - 0.01));
const validTo = (iso) => (iso && !iso.startsWith("2099") ? shortDate(iso.slice(0, 10)) : "");
const STATUS_LABELS = { draft: "Klar", sent: "Sendt", generating: "Laves", error: "Fejl" };
const TABS = [
  ["plan", "Madplan"],
  ["recipes", "Opskrifter"],
  ["shopping", "Indkøb"],
  ["favorites", "Favoritter"],
  ["history", "Historik"],
  ["settings", "Indstillinger"],
];

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const kr = (value) =>
  value == null || Number.isNaN(Number(value))
    ? "–"
    : `${Number(value).toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.`;
const dateLabel = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return `${WEEKDAYS[(d.getDay() + 6) % 7]} ${d.getDate()}/${d.getMonth() + 1}`;
};
const shortDate = (iso) => {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  return `${d.getDate()}/${d.getMonth() + 1}`;
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
    this._form = null;
    this._dirty = false;
    this._busy = false;
    this._toast = null;
    this._error = null;
    this._search = { query: "", results: [], loading: false };
    this._editFav = null;
    this._newFav = { text: "", frequency: "weekly" };
    this._newDislike = "";
    this._startDate = null;
    this._checked = {}; // ingredient/step ticks per plan+day
    this._timers = {};
    this._favs = null; // REMA favourite products
    this._favsLoading = false;
    this._favsError = null;
    this._favFilter = "";
    this._wake = null;
    this._wakeWanted = false;
    this._onVisibility = () => {
      if (document.visibilityState === "visible" && this._wakeWanted && !this._wake) this._requestWake();
    };
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onInput(ev));
    this.shadowRoot.addEventListener("touchstart", (ev) => this._onTouchStart(ev), { passive: true });
    this.shadowRoot.addEventListener("touchend", (ev) => this._onTouchEnd(ev), { passive: true });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
    if (first) this._load();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  get _static() {
    return this._panel?.config?.static_url || "/rema1000_static";
  }

  connectedCallback() {
    document.addEventListener("visibilitychange", this._onVisibility);
    this._tick = setInterval(() => this._tickTimers(), 1000);
    if (this._hass && !this._state) this._load();
  }

  disconnectedCallback() {
    document.removeEventListener("visibilitychange", this._onVisibility);
    clearInterval(this._tick);
    clearTimeout(this._poll);
    this._releaseWake();
  }

  // ------------------------------------------------------------------ data

  async _ws(type, data = {}) {
    const entry = this._state?.entry_id ? { entry_id: this._state.entry_id } : {};
    return this._hass.callWS({ type, ...entry, ...data });
  }

  async _load(silent = false) {
    try {
      const state = await this._ws("rema1000/state");
      this._state = state;
      this._error = null;
      if (!this._startDate) this._startDate = state.default_start;
      if (this._viewingLatest) this._plan = state.latest_plan;
      if (!this._form || !this._dirty) this._form = clone(state.settings);
    } catch (err) {
      this._error = err?.message || String(err);
    }
    clearTimeout(this._poll);
    if (this._state?.status?.state === "generating") {
      this._poll = setTimeout(() => this._load(true), 3000);
    }
    // Don't redraw the settings form under the user's fingers while polling.
    if (silent && this._tab === "settings") {
      this._renderStatus();
      return;
    }
    this._render();
  }

  _say(message) {
    this._toast = message;
    this._render();
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = null;
      this._render();
    }, 3500);
  }

  async _run(fn, okMessage) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      await fn();
      if (okMessage) this._toast = okMessage;
    } catch (err) {
      this._toast = `Fejl: ${err?.message || err}`;
    } finally {
      this._busy = false;
      await this._load();
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => {
        this._toast = null;
        this._render();
      }, 3500);
    }
  }

  // ------------------------------------------------------------------ events

  // Saved right away like the favourites, without saving other unsaved settings.
  _saveDislikes(list, okMessage) {
    this._run(async () => {
      const saved = await this._ws("rema1000/settings", {
        settings: { ...this._state.settings, disliked_dishes: list },
      });
      if (this._form) this._form.disliked_dishes = saved.disliked_dishes;
    }, okMessage);
  }

  _goTab(key, direction = 0) {
    if (!key || key === this._tab) return;
    this._tab = key;
    if (key !== "recipes") this._releaseWake();
    if (key === "favorites" && !this._favs && !this._favsLoading) this._loadFavs();
    this._render();
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
    if (ev.touches.length !== 1) return;
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
      tab: () => this._goTab(arg),
      "fav-refresh": () => this._loadFavs(true),
      "fav-add": () =>
        this._run(
          () => this._ws("rema1000/list/add", { product_id: Number(arg), amount: 1 }),
          "Tilføjet til REMA-listen."
        ),
      "clear-list": () => {
        const count = this._state?.rema_list?.items?.length || 0;
        if (!count) return this._say("REMA-listen er allerede tom.");
        if (!confirm(`Fjern alle ${count} varer fra REMA-listen? Listen er delt, så den bliver også tom i appen.`)) return;
        this._run(() => this._ws("rema1000/list/clear"), "REMA-listen er tømt.");
      },
      generate: () =>
        this._run(async () => {
          await this._ws("rema1000/generate", { start_date: this._startDate || null });
          this._viewingLatest = true;
          this._tab = "plan";
        }, "Madplanen er ved at blive lavet – det tager typisk 1-2 minutter."),
      send: () =>
        this._run(
          () => this._ws("rema1000/send", { plan_id: this._plan?.id }),
          "Indkøbslisten er sendt til REMA 1000-appen."
        ),
      "open-day": () => {
        this._day = Number(arg);
        this._tab = "recipes";
        this._render();
      },
      day: () => {
        this._day = Number(arg);
        this._render();
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
        this._render();
      },
      wake: () => (this._wakeWanted ? this._releaseWake(true) : this._requestWake()),
      "view-plan": () =>
        this._run(async () => {
          this._plan = await this._ws("rema1000/plan", { plan_id: arg });
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
          await this._ws("rema1000/plan/delete", { plan_id: arg });
          if (this._plan?.id === arg) {
            this._viewingLatest = true;
          }
        }, "Madplanen er slettet.");
      },
      "save-settings": () =>
        this._run(async () => {
          await this._ws("rema1000/settings", { settings: this._form });
          this._dirty = false;
        }, "Indstillingerne er gemt."),
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
          await this._ws("rema1000/favorite/save", { favorite: this._newFav });
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
          await this._ws("rema1000/favorite/save", { favorite: this._editFav });
          this._editFav = null;
        }, "Favoritten er gemt."),
      "cancel-fav": () => {
        this._editFav = null;
        this._render();
      },
      "delete-fav": () => {
        if (!confirm("Slet denne favorit?")) return;
        this._run(() => this._ws("rema1000/favorite/delete", { favorite_id: arg }), "Favoritten er slettet.");
      },
      recipe: () =>
        this._run(async () => {
          const day = this._plan.days[this._day];
          const updated = await this._ws("rema1000/recipe", { plan_id: this._plan.id, date: day.date });
          this._plan.days[this._day] = updated;
          if (!this._viewingLatest) this._plan = await this._ws("rema1000/plan", { plan_id: this._plan.id });
        }, "Opskriften er lavet igen."),
      refresh: () => this._load(),
    };
    actions[action]?.();
  }

  _onInput(ev) {
    const el = ev.target;
    const ds = el.dataset;
    if (ds.bind === "start") {
      this._startDate = el.value;
      return;
    }
    if (ds.bind === "favfilter") {
      this._favFilter = el.value;
      const list = this.shadowRoot.querySelector("#fav-all");
      if (list) list.innerHTML = this._favRows();
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
      const list = this._form[ds.list];
      const idx = list.indexOf(el.value);
      if (el.checked && idx < 0) list.push(el.value);
      if (!el.checked && idx >= 0) list.splice(idx, 1);
      this._dirty = true;
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
      if (ev.type === "change" && (el.type === "radio" || el.tagName === "SELECT")) this._render();
    }
  }

  async _loadFavs(force = false) {
    this._favsLoading = true;
    this._favsError = null;
    this._render();
    try {
      this._favs = await this._ws("rema1000/favorites", { force });
    } catch (err) {
      this._favsError = err?.message || String(err);
    }
    this._favsLoading = false;
    this._render();
  }

  async _doSearch() {
    const query = this._search.query.trim();
    if (!query) return;
    this._search.loading = true;
    this._render();
    try {
      this._search.results = await this._ws("rema1000/search", { query });
    } catch (err) {
      this._say(`Søgningen fejlede: ${err?.message || err}`);
    }
    this._search.loading = false;
    this._render();
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

  _tickTimers() {
    const nodes = this.shadowRoot.querySelectorAll("[data-timer]");
    nodes.forEach((node) => {
      const end = this._timers[node.dataset.timer];
      if (!end) return;
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      node.textContent = left > 0 ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` : "Færdig!";
      if (left === 0 && !node.dataset.done) {
        node.dataset.done = "1";
        node.closest(".step")?.classList.add("alarm");
        if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
        this._beep();
      }
    });
  }

  _beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
      body = `<div class="card"><h2>REMA 1000 kunne ikke indlæses</h2><p>${esc(this._error)}</p>
        <button class="btn" data-action="refresh">Prøv igen</button></div>`;
    } else if (!state) {
      body = `<div class="card center"><span class="spinner"></span> Indlæser …</div>`;
    } else {
      body = {
        plan: () => this._planView(),
        recipes: () => this._recipesView(),
        shopping: () => this._shoppingView(),
        favorites: () => this._favoritesView(),
        history: () => this._historyView(),
        settings: () => this._settingsView(),
      }[this._tab]();
    }
    const root = this.shadowRoot;
    // The toolbar and tabs are built once, so their horizontal scroll survives.
    if (!root.querySelector("#content")) {
      const tabs = TABS.map(
        ([key, label]) => `<button class="tab" data-action="tab" data-arg="${key}">${label}</button>`
      ).join("");
      root.innerHTML = `
        <style>${STYLE}</style>
        <div class="toolbar">
          <ha-menu-button></ha-menu-button>
          <img class="logo" src="${this._static}/logo.png" alt="REMA 1000">
          <span class="spacer"></span>
          <span id="busy"></span>
        </div>
        <nav class="tabs">${tabs}</nav>
        <main id="content"></main>
        <div id="toast"></div>`;
    }
    const menu = root.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    root.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.arg === this._tab));
    root.querySelector("#busy").innerHTML = this._busy ? '<span class="spinner small"></span>' : "";
    const oldChips = root.querySelector(".chips");
    const chipsLeft = oldChips ? oldChips.scrollLeft : 0;
    root.querySelector("#content").innerHTML = `<div id="status">${this._statusHtml()}</div>${body}`;
    root.querySelector("#toast").innerHTML = this._toast ? `<div class="toast">${esc(this._toast)}</div>` : "";
    const chips = root.querySelector(".chips");
    if (chips) chips.scrollLeft = chipsLeft;
    this._keepVisible(root.querySelector(".tabs"), root.querySelector(".tab.active"));
    this._keepVisible(chips, chips?.querySelector(".chip.active"));
    this._tickTimers();
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

  _generateControls(label = "Lav ny madplan") {
    const generating = this._state?.status?.state === "generating";
    return `<div class="row wrap">
      <label class="field inline">Første dag
        <input type="date" data-bind="start" value="${esc(this._startDate || "")}">
      </label>
      <button class="btn primary" data-action="generate" ${generating || this._busy ? "disabled" : ""}>
        ${generating ? "Laves …" : label}
      </button>
    </div>`;
  }

  _planView() {
    const plan = this._plan;
    const cat = this._state.catalogs;
    const catLine = [
      cat.current ? `Aktuel avis: ${esc(cat.current.label || "")} (til ${shortDate(cat.current.valid_to?.slice(0, 10))})` : "",
      cat.upcoming
        ? `Næste avis: ${esc(cat.upcoming.label || "")} fra ${shortDate(cat.upcoming.valid_from?.slice(0, 10))}`
        : "Næste uges avis er ikke udkommet endnu",
    ]
      .filter(Boolean)
      .join(" · ");
    if (!plan) {
      return `<div class="card hero">
        <img src="${this._static}/icon.png" class="hero-icon" alt="">
        <h1>Ingen madplan endnu</h1>
        <p>Madplanen laves med AI ud fra ugens tilbud og jeres indstillinger. Tjek indstillingerne først, og tryk så på knappen.</p>
        ${this._generateControls("Lav madplan")}
        <p class="muted">${catLine}</p>
      </div>`;
    }
    const over = plan.budget && plan.total > plan.budget;
    const days = plan.days
      .map((day, idx) => {
        const type = TYPE_LABELS[day.type] ?? day.type;
        return `<button class="day" data-action="open-day" data-arg="${idx}">
          <span class="date">${esc(dateLabel(day.date))}</span>
          <span class="dish">${esc(day.dish)}</span>
          <span class="meta">${day.total_minutes ? `${day.total_minutes} min` : ""}${type ? ` <span class="badge">${esc(type)}</span>` : ""}</span>
        </button>`;
      })
      .join("");
    const checklist = (plan.checklist || [])
      .map((c) => `<li class="${c.ok ? "ok" : "bad"}">${c.ok ? "✓" : "✗"} ${esc(c.requirement)}</li>`)
      .join("");
    return `
      ${this._viewingLatest ? "" : `<div class="banner info">Du ser en ældre madplan. <button class="link" data-action="view-latest">Vis nyeste</button></div>`}
      <div class="card">
        <div class="row between wrap">
          <div>
            <h1>${esc(plan.title)}</h1>
            <p class="muted">${esc(dateLabel(plan.start_date))} – ${esc(dateLabel(plan.end_date))}${plan.catalog ? ` · ${esc(plan.catalog.label || "")}` : ""}</p>
          </div>
          <div class="price ${over ? "over" : ""}">
            <span class="big">${kr(plan.total)}</span>
            <span class="muted">${plan.budget ? `budget ${kr(plan.budget)}` : ""}</span>
          </div>
        </div>
        ${plan.summary ? `<p>${esc(plan.summary)}</p>` : ""}
        ${over ? `<div class="banner warn">Planen er over budget. Prøv at lave en ny, eller ret budgettet i indstillingerne.</div>` : ""}
        <div class="days">${days}</div>
        <div class="row wrap actions">
          <button class="btn primary" data-action="send" ${this._busy ? "disabled" : ""}>
            ${plan.status === "sent" ? "Sendt ✓ – send igen" : "Send til REMA-listen"}
          </button>
          <button class="btn" data-action="tab" data-arg="shopping">Se indkøbsliste</button>
          <button class="btn" data-action="open-day" data-arg="0">Start madlavning</button>
        </div>
        ${checklist || plan.deviations ? `<details><summary>Krav-tjekliste</summary><ul class="checklist">${checklist}</ul>${plan.deviations ? `<p class="muted">${esc(plan.deviations)}</p>` : ""}</details>` : ""}
      </div>
      <div class="card">
        <h2>Ny madplan</h2>
        ${this._generateControls()}
        <p class="muted">${catLine}</p>
      </div>`;
  }

  _recipesView() {
    const plan = this._plan;
    if (!plan) return `<div class="card">Der er ingen madplan endnu.</div>`;
    const idx = Math.min(this._day, plan.days.length - 1);
    const day = plan.days[idx];
    const key = `${plan.id}|${day.date}`;
    const chips = plan.days
      .map(
        (d, i) =>
          `<button class="chip ${i === idx ? "active" : ""}" data-action="day" data-arg="${i}">${esc(dateLabel(d.date))}</button>`
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
          <h1>${esc(day.dish)}</h1>
          <button class="btn ${this._wake ? "primary" : ""}" data-action="wake">
            ${this._wake ? "☀ Skærmen holdes tændt" : "☀ Hold skærmen tændt"}
          </button>
        </div>
        <p class="muted">${esc(dateLabel(day.date))}${day.servings ? ` · ${day.servings} personer` : ""}${day.active_minutes ? ` · ${day.active_minutes} min aktiv` : ""}${day.total_minutes ? ` · ${day.total_minutes} min i alt` : ""}${type ? ` · ${esc(type)}` : ""}</p>
        ${leftovers}
        ${day.recipe_error || (!day.steps.length && !day.uses_leftovers_from && day.type !== "rester")
          ? `<div class="banner warn">Opskriften kunne ikke laves${day.recipe_error ? `: ${esc(day.recipe_error)}` : ""}
             <button class="btn small" data-action="recipe" ${this._busy ? "disabled" : ""}>Prøv igen</button></div>`
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
            <p><button class="link" data-action="recipe" ${this._busy ? "disabled" : ""}>Lav opskriften igen</button></p>
          </section>
        </div>
      </div>`;
  }

  _shoppingView() {
    const plan = this._plan;
    const rema = this._state.rema_list;
    let planHtml = `<div class="card">Der er ingen madplan endnu.</div>`;
    if (plan) {
      const groups = {};
      plan.shopping.forEach((line) => (groups[line.category || "Andet"] ||= []).push(line));
      const sections = Object.entries(groups)
        .map(([category, lines]) => {
          const rows = lines
            .map((line) => {
              const p = line.product;
              const badges = [
                p?.is_advertised || p?.is_campaign ? '<span class="badge offer">Tilbud</span>' : "",
                p?.is_organic ? '<span class="badge eco">Øko</span>' : "",
                line.must_have ? '<span class="badge">Fast vare</span>' : "",
              ].join("");
              const need = line.amount && line.unit && line.unit !== "pk" ? `${line.amount} ${line.unit}` : "";
              return `<li class="line">
                ${p?.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : '<span class="noimg">?</span>'}
                <div class="what">
                  <b>${esc(p ? p.name : line.name)}</b> ${badges}
                  <span class="muted">${esc(p?.underline || "Tilføjes som fritekst")}${need ? ` · behov ${esc(need)}` : ""}</span>
                  ${line.offer_name ? `<span class="muted">Avisvare: ${esc(line.offer_name)}</span>` : ""}
                  ${line.note ? `<span class="note">${esc(line.note)}</span>` : ""}
                </div>
                <div class="cost">${p ? `${line.packages} × ${kr(p.price)}<b>${kr(line.cost)}</b>` : "–"}</div>
              </li>`;
            })
            .join("");
          return `<h2>${esc(category)}</h2><ul class="lines">${rows}</ul>`;
        })
        .join("");
      planHtml = `<div class="card">
        <div class="row between wrap">
          <div><h1>Indkøbsliste</h1><p class="muted">${esc(plan.title)}</p></div>
          <div class="price ${plan.budget && plan.total > plan.budget ? "over" : ""}"><span class="big">${kr(plan.total)}</span>
          <span class="muted">${plan.budget ? `budget ${kr(plan.budget)}` : ""}</span></div>
        </div>
        ${sections}
        <div class="row wrap actions">
          <button class="btn primary" data-action="send" ${this._busy ? "disabled" : ""}>
            ${plan.status === "sent" ? "Sendt ✓ – send igen" : "Send til REMA-listen"}</button>
        </div>
      </div>`;
    }
    const remaItems = rema?.items?.length
      ? rema.items
          .map((i) => `<li class="${i.bought ? "bought" : ""}">${i.amount > 1 ? `${i.amount} × ` : ""}${esc(i.name)}</li>`)
          .join("")
      : "<li class='muted'>Listen er tom.</li>";
    return `${planHtml}
      <div class="card">
        <div class="row between wrap">
          <h2>På REMA-listen lige nu${rema ? ` (${esc(rema.name)})` : ""}</h2>
          <button class="btn small danger" data-action="clear-list" ${this._busy || !rema?.items?.length ? "disabled" : ""}>Tøm kurv</button>
        </div>
        <ul class="rema">${remaItems}</ul>
        ${rema ? `<p class="muted">Anslået pris for det, der mangler: ${kr(rema.total)}</p>` : ""}
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
          ${sale && until ? `<span class="muted small">til ${esc(until)}</span>` : ""}</span>
      </div>
      <button class="btn small primary" data-action="fav-add" data-arg="${esc(p.id)}" ${this._busy ? "disabled" : ""}>+ Tilføj</button>
    </div>`;
  }

  _favRows() {
    const filter = this._favFilter.trim().toLowerCase();
    const rows = (this._favs || [])
      .filter((p) => !filter || `${p.name} ${p.underline || ""}`.toLowerCase().includes(filter))
      .map(
        (p) => `<li class="fav-row">
          <div class="what"><b>${esc(p.name)}</b><span class="muted small">${esc(p.underline || "")}</span></div>
          <span class="${onOffer(p) ? "sale" : ""}">${kr(p.price)}</span>
          <button class="btn small" data-action="fav-add" data-arg="${esc(p.id)}">+ Tilføj</button>
        </li>`
      )
      .join("");
    return rows || "<li class='muted'>Ingen favoritter matcher.</li>";
  }

  _favoritesView() {
    if (this._favsLoading && !this._favs) {
      return `<div class="card center"><span class="spinner"></span> Henter dine favoritter fra REMA 1000 …</div>`;
    }
    if (this._favsError && !this._favs) {
      return `<div class="card"><h2>Favoritterne kunne ikke hentes</h2><p>${esc(this._favsError)}</p>
        <button class="btn" data-action="fav-refresh">Prøv igen</button></div>`;
    }
    const favs = this._favs || [];
    const now = favs.filter(onOffer);
    const next = favs.filter((p) => !onOffer(p) && p.upcoming_is_advertised && p.upcoming_price);
    const nextFrom = next[0]?.upcoming_from ? shortDate(next[0].upcoming_from.slice(0, 10)) : "";
    return `
      <div class="card">
        <div class="row between wrap">
          <div><h1>Dine favoritter</h1>
          <p class="muted">Varer du har markeret med hjerte i REMA 1000-appen – ${favs.length} i alt.</p></div>
          <button class="btn small" data-action="fav-refresh" ${this._favsLoading ? "disabled" : ""}>
            ${this._favsLoading ? '<span class="spinner small"></span>' : "Opdatér"}</button>
        </div>
        <h2>På tilbud nu (${now.length})</h2>
        ${now.length ? `<div class="prod-grid">${now.map((p) => this._productCard(p)).join("")}</div>` : '<p class="muted">Ingen af dine favoritter er på tilbud lige nu.</p>'}
        ${next.length
          ? `<h2>På tilbud i næste avis${nextFrom ? ` (fra ${esc(nextFrom)})` : ""} (${next.length})</h2>
             <div class="prod-grid">${next
               .map((p) => this._productCard({ ...p, price: p.upcoming_price, normal_price: p.price, is_advertised: true, price_valid_to: null }))
               .join("")}</div>`
          : ""}
      </div>
      <div class="card">
        <details>
          <summary>Alle favoritter (${favs.length})</summary>
          <input class="grow filter" type="search" data-bind="favfilter" value="${esc(this._favFilter)}" placeholder="Filtrér, fx mælk">
          <ul class="favlist" id="fav-all">${this._favRows()}</ul>
        </details>
      </div>`;
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
      `<label class="check"><input type="checkbox" data-list="${list}" value="${key}" ${f[list].includes(key) ? "checked" : ""}> ${esc(labels[key] || key)}</label>`;
    const weekdaySelect = (path, value) =>
      `<select data-path="${path}" data-type="number">${WEEKDAYS.map((d, i) => `<option value="${i}" ${Number(value) === i ? "selected" : ""}>${d}</option>`).join("")}</select>`;
    const num = (path, value, min = 0, max = 999) =>
      `<input type="number" data-path="${path}" data-type="number" min="${min}" max="${max}" value="${esc(value)}">`;
    const ai = this._state.ai_entities
      .map((e) => `<option value="${esc(e.entity_id)}" ${f.ai_task_entity === e.entity_id ? "selected" : ""}>${esc(e.name)}</option>`)
      .join("");
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

    return `
      <div class="card">
        <h1>Indstillinger</h1>
        <p class="muted">Bruges hver gang en madplan laves. Husk at gemme nederst.</p>

        <h2>AI</h2>
        <label class="field">AI-opgave-entitet
          <select data-path="ai_task_entity" data-type="nullable">
            <option value="">Home Assistants standard</option>${ai}
          </select></label>

        <h2>Uge og budget</h2>
        <div class="grid">
          <label class="field">Madplanen starter / der handles ind ${weekdaySelect("start_weekday", f.start_weekday)}</label>
          <label class="field">Antal dage ${num("days", f.days, 1, 14)}</label>
          <label class="field">Budget for hele listen (kr.) ${num("budget", f.budget, 0, 100000)}</label>
        </div>

        <h2>Økologi</h2>
        <div class="row wrap">
          ${[["only", "Udelukkende økologi"], ["prefer", "Foretræk økologi"], ["none", "Ligeglad (prisbevidst)"]]
            .map(([v, l]) => `<label class="check"><input type="radio" name="organic" data-path="organic" value="${v}" ${f.organic === v ? "checked" : ""}> ${l}</label>`)
            .join("")}
        </div>
        ${f.organic === "prefer" ? `<label class="field inline">Højst så mange % dyrere end den billigste ${num("organic_max_extra_pct", f.organic_max_extra_pct, 0, 500)}</label>` : ""}

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

        <h2>Undgå</h2>
        <div class="checks">${opts.avoid.map((k) => check("avoid", k, AVOID_LABELS)).join("")}</div>
        <label class="field">Andet at undgå <input type="text" data-path="avoid_other" value="${esc(f.avoid_other)}" placeholder="Fx svampe, oliven"></label>

        <h2>Allergier</h2>
        <div class="checks">${opts.allergies.map((k) => check("allergies", k, ALLERGY_LABELS)).join("")}</div>
        <label class="field">Andre allergier <input type="text" data-path="allergies_other" value="${esc(f.allergies_other)}"></label>

        <h2>Familien</h2>
        ${household}
        <button class="btn small" data-action="add-row" data-arg="household">+ Tilføj person</button>

        <h2>Retter</h2>
        <div class="grid">
          <label class="field">Mindst vegetarretter ${num("min_vegetarian", f.min_vegetarian, 0, 14)}</label>
          <label class="field">Højst vegetarretter ${num("max_vegetarian", f.max_vegetarian, 0, 14)}</label>
          <label class="field">Restedage (laves dagen før) ${num("leftover_days", f.leftover_days, 0, 7)}</label>
          <label class="field">Maks. minutter på hverdage ${num("max_cook_minutes_weekday", f.max_cook_minutes_weekday, 5, 300)}</label>
          <label class="field">Ingen gentagelse i antal uger ${num("no_repeat_weeks", f.no_repeat_weeks, 0, 52)}</label>
        </div>
        <h3>Faste dage</h3>
        ${fixed}
        <button class="btn small" data-action="add-row" data-arg="fixed_days">+ Tilføj fast dag</button>
        <label class="field">Ønsker til maden <textarea data-path="wishes" rows="2">${esc(f.wishes)}</textarea></label>
        <label class="field">Basisvarer I altid har (købes ikke) <textarea data-path="pantry" rows="2">${esc(f.pantry)}</textarea></label>

        <h2>Faste varer hver uge</h2>
        ${musts}
        <div class="row wrap">
          <input class="grow" type="search" data-bind="search" value="${esc(this._search.query)}" placeholder="Søg i REMA 1000, fx letmælk">
          <button class="btn small" data-action="search">Søg</button>
          <button class="btn small" data-action="add-row" data-arg="must_haves">+ Fritekst</button>
        </div>
        <div class="results">${results}</div>

        <h2>Automatik</h2>
        <label class="check"><input type="checkbox" data-path="auto_generate" ${f.auto_generate ? "checked" : ""}> Lav næste uges madplan automatisk, når den nye tilbudsavis udkommer</label>
        <label class="check"><input type="checkbox" data-path="auto_send" ${f.auto_send ? "checked" : ""}> Send den automatisk til REMA-listen</label>

      </div>

      <div class="card">
        <h1>Familiens favoritter</h1>
        <p class="muted">Beskriv retten, fx “Ovnbagt laks med citronskiver, frisk spinatpasta med pesto og broccoli”.</p>
        <textarea data-bind="newfav" data-field="text" rows="2" placeholder="Ret">${esc(this._newFav.text)}</textarea>
        <div class="row wrap">
          <select data-bind="newfav" data-field="frequency">${opts.frequencies.map((q) => `<option value="${q}" ${this._newFav.frequency === q ? "selected" : ""}>${FREQ_LABELS[q]}</option>`).join("")}</select>
          <button class="btn primary small" data-action="add-fav">Tilføj</button>
        </div>
        <ul class="favs">${favs || "<li class='muted'>Ingen favoritter endnu.</li>"}</ul>
      </div>

      <div class="card">
        <h1>Retter familien ikke kan lide</h1>
        <p class="muted">Retter, der aldrig skal på madplanen, fx “Fiskefrikadeller” eller “Gryderetter med kål”.</p>
        <textarea data-bind="newdislike" rows="2" placeholder="Ret">${esc(this._newDislike)}</textarea>
        <div class="row wrap">
          <button class="btn primary small" data-action="add-dislike" ${this._busy ? "disabled" : ""}>Tilføj</button>
        </div>
        <ul class="favs">${dislikes || "<li class='muted'>Ingen endnu.</li>"}</ul>
      </div>

      <div class="card">
        <h1>App på hjemmeskærmen</h1>
        <p class="muted">Åbn linket i Safari (eller Chrome), log ind og vælg Del › Føj til hjemmeskærm. Så åbner REMA 1000 i fuld skærm i dit tema.</p>
        <p><a href="${esc(`${location.origin}/rema1000_app/rema.html`)}" target="_blank" rel="noopener">${esc(`${location.origin}/rema1000_app/rema.html`)}</a></p>
      </div>

      <div class="savebar">
        <button class="btn primary" data-action="save-settings" ${this._busy ? "disabled" : ""}>Gem indstillinger</button>
        <button class="btn" data-action="reset-settings">Fortryd ændringer</button>
        ${this._dirty ? '<span class="muted">Ikke gemt</span>' : ""}
      </div>`;
  }
}

const STYLE = `
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
    --rema-tint: color-mix(in srgb, var(--rema-accent) 12%, transparent); }
  * { box-sizing: border-box; }
  a { color: var(--rema-accent); overflow-wrap: anywhere; }
  #content.from-right { animation: rema-from-right .2s ease-out; }
  #content.from-left { animation: rema-from-left .2s ease-out; }
  @keyframes rema-from-right { from { transform: translateX(32px); opacity: .4; } }
  @keyframes rema-from-left { from { transform: translateX(-32px); opacity: .4; } }
  @media (prefers-reduced-motion: reduce) { #content.from-right, #content.from-left { animation: none; } }
  .toolbar { display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 12px;
    background: var(--app-header-background-color, var(--card-background-color)); color: var(--app-header-text-color, inherit);
    border-bottom: 1px solid var(--divider-color); position: sticky; top: 0; z-index: 3; }
  .logo { height: 26px; }
  .spacer { flex: 1; }
  .tabs { display: flex; gap: 4px; overflow-x: auto; padding: 8px 12px 0; background: var(--card-background-color);
    border-bottom: 1px solid var(--divider-color); position: sticky; top: var(--header-height, 56px); z-index: 2; }
  .tab { border: none; background: none; color: var(--secondary-text-color); padding: 10px 14px; font-size: 15px; cursor: pointer;
    border-bottom: 3px solid transparent; white-space: nowrap; font-weight: 500; }
  .tab.active { color: var(--rema-accent); border-color: var(--rema-accent); }
  main { max-width: 1100px; margin: 0 auto; padding: 16px 12px 96px; }
  .card { background: var(--rema-card); border-radius: var(--ha-card-border-radius, 12px);
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
  .note { color: var(--rema-warn); font-size: 13px; }
  .cost { text-align: right; display: flex; flex-direction: column; font-size: 13px; color: var(--secondary-text-color); white-space: nowrap; }
  .cost b { color: var(--primary-text-color); font-size: 15px; }
  .rema li { padding: 6px 0; border-bottom: 1px solid var(--divider-color); } .rema .bought { opacity: .45; text-decoration: line-through; }
  .hist, .fav { display: flex; gap: 10px; align-items: center; padding: 12px 0; border-bottom: 1px solid var(--divider-color); }
  .hist .what, .fav .what { flex: 1; cursor: pointer; } .fav.edit { flex-direction: column; align-items: stretch; }
  .field { display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: var(--secondary-text-color); margin: 8px 0; }
  .field.inline { flex-direction: row; align-items: center; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 4px 16px; }
  input[type=text], input[type=number], input[type=date], input[type=search], select, textarea {
    font: inherit; font-size: 15px; color: var(--primary-text-color); background: var(--secondary-background-color, transparent);
    border: 1px solid var(--divider-color); border-radius: 8px; padding: 8px 10px; }
  input[type=number] { width: 90px; } textarea { width: 100%; resize: vertical; }
  .checks { display: flex; flex-wrap: wrap; gap: 6px 18px; }
  .check { display: flex; align-items: center; gap: 6px; font-size: 15px; padding: 4px 0; }
  .rowitem { padding: 6px 0; border-bottom: 1px dashed var(--divider-color); }
  .results { display: grid; gap: 6px; margin-top: 8px; }
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
  .sticky { position: sticky; bottom: 0; background: var(--card-background-color); padding: 12px 0; border-top: 1px solid var(--divider-color); }
  /* Last in the settings view, so it stays at the bottom of the screen all the way down. */
  .savebar { position: sticky; bottom: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
    margin-top: 16px; padding: 12px 16px; background: var(--rema-card); border: 1px solid var(--divider-color);
    border-radius: var(--ha-card-border-radius, 12px); box-shadow: 0 -2px 12px rgba(0, 0, 0, .12); }
  .toast { position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%); background: var(--primary-text-color); color: var(--primary-background-color);
    padding: 12px 20px; border-radius: 10px; z-index: 10; max-width: 90vw; box-shadow: 0 4px 12px rgba(0,0,0,.3); }
  @media (max-width: 700px) {
    .recipe-grid { grid-template-columns: 1fr; }
    .day { grid-template-columns: 1fr; gap: 4px; }
    .step-text { font-size: 18px; }
    .line { grid-template-columns: 40px 1fr; } .line .cost { grid-column: 2; text-align: left; flex-direction: row; gap: 8px; }
    .prod-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
    .prod { padding: 6px; gap: 4px; font-size: 12px; border-radius: 10px; }
    .prod img, .prod .noimg { height: 64px; }
    .prod-price { font-size: 14px; }
    .prod .badge { font-size: 10px; padding: 1px 5px; }
    .prod .btn { padding: 6px 4px; font-size: 12px; }
  }
`;

if (!customElements.get("rema1000-panel")) customElements.define("rema1000-panel", Rema1000Panel);
