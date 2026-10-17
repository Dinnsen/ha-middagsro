/* Demo data for the README screenshots: a family's week in October 2026.
   Prices and products are made up to look like REMA 1000's; no real account is used. */

const pic = (emoji, bg) =>
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><rect width="120" height="120" rx="22" fill="${bg}"/>` +
      `<text x="60" y="64" font-size="66" text-anchor="middle" dominant-baseline="middle" font-family="Noto Color Emoji, Apple Color Emoji, sans-serif">${emoji}</text></svg>`
  );

const P = {
  chicken: { id: 30101, name: "KYLLINGEOVERLÅR", underline: "1000 GR. / DANSK", price: 45, normal_price: 59, is_advertised: true, is_campaign: false, is_organic: false, image: pic("🍗", "#FCE9D9") },
  beef: { id: 30001, name: "HK. OKSEKØD 8-12%", underline: "500 GR. / DANSK", price: 35, normal_price: 45, is_advertised: true, is_campaign: false, is_organic: false, image: pic("🥩", "#FBE1E1") },
  ham: { id: 30230, name: "SKINKE I TERN", underline: "2 X 125 GR.", price: 22, normal_price: 22, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥓", "#FBE1E1") },
  salmon: { id: 31010, name: "LAKSEFILET", underline: "2 X 125 GR. / NORGE", price: 49, normal_price: 59, is_advertised: false, is_campaign: true, is_organic: false, image: pic("🐟", "#DDEFFB") },
  carrots: { id: 50010, name: "GULERØDDER", underline: "1 KG / DANMARK / ØKOLOGI", price: 12, normal_price: 12, is_advertised: false, is_campaign: false, is_organic: true, image: pic("🥕", "#FDEBD3") },
  potatoes: { id: 50020, name: "KARTOFLER", underline: "2 KG / DANMARK", price: 15, normal_price: 15, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥔", "#F3E9D8") },
  broccoli: { id: 50002, name: "BROCCOLI", underline: "STK. / SPANIEN", price: 10, normal_price: 14, is_advertised: true, is_campaign: false, is_organic: false, image: pic("🥦", "#E2F2DF") },
  onions: { id: 50003, name: "LØG", underline: "1 KG / DANMARK", price: 8, normal_price: 8, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🧅", "#F6ECDD") },
  mushrooms: { id: 50040, name: "CHAMPIGNON", underline: "250 GR. / DANMARK", price: 12, normal_price: 12, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🍄", "#EFE7E1") },
  cabbage: { id: 50050, name: "SPIDSKÅL", underline: "STK. / DANMARK", price: 10, normal_price: 10, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥬", "#E2F2DF") },
  milk: { id: 20496, name: "LETMÆLK", underline: "1 LTR. / ØKOLOGISK", price: 13.5, normal_price: 13.5, is_advertised: false, is_campaign: false, is_organic: true, image: pic("🥛", "#E7EEF8") },
  eggs: { id: 40002, name: "FRILANDSÆG", underline: "10 STK. / M/L", price: 29, normal_price: 29, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥚", "#FBF3DC") },
  cheese: { id: 41020, name: "REVET MOZZARELLA", underline: "200 GR.", price: 18, normal_price: 22, is_advertised: true, is_campaign: false, is_organic: false, image: pic("🧀", "#FBF3DC") },
  creme: { id: 41030, name: "CREME FRAICHE 18%", underline: "200 GR.", price: 9, normal_price: 9, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥣", "#EEF1F6") },
  spaghetti: { id: 60003, name: "SPAGHETTI", underline: "500 GR. / ITALIEN", price: 8, normal_price: 8, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🍝", "#FBF0D9") },
  tomatoes: { id: 60010, name: "HAKKEDE TOMATER", underline: "400 GR.", price: 6, normal_price: 6, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🍅", "#FBE1E1") },
  lentils: { id: 60020, name: "RØDE LINSER", underline: "500 GR. / ØKOLOGISK", price: 18, normal_price: 18, is_advertised: false, is_campaign: false, is_organic: true, image: pic("🫘", "#F8E6DA") },
  coconut: { id: 60030, name: "KOKOSMÆLK", underline: "400 ML.", price: 12, normal_price: 12, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🥥", "#EEF1F6") },
  ryebread: { id: 70001, name: "RUGBRØD", underline: "1000 GR. / SKÅRET", price: 18, normal_price: 18, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🍞", "#F3E9D8") },
  wraps: { id: 70010, name: "TORTILLA WRAPS", underline: "8 STK.", price: 15, normal_price: 15, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🌯", "#F6ECDD") },
  naan: { id: 70020, name: "NAANBRØD", underline: "4 STK.", price: 16, normal_price: 16, is_advertised: false, is_campaign: false, is_organic: false, image: pic("🫓", "#F6ECDD") },
};

const line = (name, product, packages, extra = {}) => ({
  name,
  amount: packages,
  unit: "pk",
  search: name.toLowerCase(),
  category: extra.category || "Andet",
  offer: product && product.is_advertised ? "o1" : null,
  offer_name: extra.offer_name || null,
  must_have: !!extra.must_have,
  product_id: product ? product.id : null,
  product: product ? { ...product } : null,
  packages,
  cost: product ? Math.round(packages * product.price * 100) / 100 : null,
  note: extra.note || null,
});

const shopping = [
  line("Kyllingeoverlår", P.chicken, 1, { category: "Kød og fisk", offer_name: "Kyllingeoverlår 1 kg" }),
  line("Hakket oksekød", P.beef, 1, { category: "Kød og fisk", offer_name: "Hakket oksekød 8-12%" }),
  line("Skinke i tern", P.ham, 1, { category: "Kød og fisk" }),
  line("Laksefilet", P.salmon, 2, { category: "Kød og fisk" }),
  line("Gulerødder", P.carrots, 1, { category: "Frugt og grønt" }),
  line("Kartofler", P.potatoes, 1, { category: "Frugt og grønt" }),
  line("Broccoli", P.broccoli, 2, { category: "Frugt og grønt", offer_name: "Broccoli" }),
  line("Løg", P.onions, 1, { category: "Frugt og grønt" }),
  line("Champignon", P.mushrooms, 1, { category: "Frugt og grønt" }),
  line("Spidskål", P.cabbage, 1, { category: "Frugt og grønt" }),
  line("Frisk koriander", null, 1, { category: "Frugt og grønt", note: "Ingen sikker vare fundet – tilføjes som fritekst" }),
  line("Letmælk", P.milk, 3, { category: "Mejeri og æg", must_have: true }),
  line("Æg", P.eggs, 1, { category: "Mejeri og æg" }),
  line("Revet mozzarella", P.cheese, 1, { category: "Mejeri og æg", offer_name: "Revet ost" }),
  line("Creme fraiche", P.creme, 1, { category: "Mejeri og æg" }),
  line("Spaghetti", P.spaghetti, 1, { category: "Kolonial" }),
  line("Hakkede tomater", P.tomatoes, 2, { category: "Kolonial" }),
  line("Røde linser", P.lentils, 1, { category: "Kolonial" }),
  line("Kokosmælk", P.coconut, 1, { category: "Kolonial" }),
  line("Rugbrød", P.ryebread, 1, { category: "Brød", must_have: true }),
  line("Tortilla wraps", P.wraps, 1, { category: "Brød" }),
  line("Naanbrød", P.naan, 1, { category: "Brød" }),
];
const total = Math.round(shopping.reduce((s, l) => s + (l.cost || 0), 0) * 100) / 100;

const day = (date, weekday, dish, type, total_minutes, active_minutes, extra = {}) => ({
  date,
  weekday,
  dish,
  type,
  favorite_id: extra.favorite_id || null,
  uses_leftovers_from: extra.uses || null,
  makes_leftovers: !!extra.makes,
  servings: 4,
  active_minutes,
  total_minutes,
  ingredients: extra.ingredients || [],
  steps: extra.steps || [],
  tip: extra.tip || "",
});

const plan = {
  id: "plan-43",
  created: "2026-10-17T07:12:00+02:00",
  start_date: "2026-10-18",
  end_date: "2026-10-24",
  week: 43,
  status: "draft",
  sent_at: null,
  title: "Madplan uge 43",
  summary: "Efterårsmad bygget op om ugens kylling, hakket oksekød og broccoli på tilbud. Søndagens kylling bliver til wraps mandag, og onsdag er rugbrødsdag.",
  catalog: { id: "cat-43", label: "Uge 43" },
  budget: 900,
  total,
  over_budget: false,
  skipped: [],
  checklist: [
    { requirement: "Budget 900 kr.", ok: true },
    { requirement: "Mindst frilandsæg", ok: true },
    { requirement: "Økologisk mælk", ok: true },
    { requirement: "Højst 30 min. aktiv tid på hverdage", ok: true },
    { requirement: "1 vegetarret", ok: true },
  ],
  deviations: "",
  days: [
    day("2026-10-18", "søndag", "Ovnbagt kylling med rodfrugter og flødekartofler", "normal", 70, 25, {
      makes: true,
      favorite_id: "fav1",
      ingredients: [
        { name: "kyllingeoverlår", amount: "1 kg" },
        { name: "gulerødder", amount: "500 g" },
        { name: "kartofler", amount: "1 kg" },
        { name: "løg", amount: "2 stk." },
        { name: "creme fraiche 18 %", amount: "200 g" },
        { name: "timian, salt og peber", amount: "" },
      ],
      steps: [
        { text: "Tænd ovnen på 200 °C varmluft.", minutes: 0 },
        { text: "Skræl gulerødder og kartofler, og skær dem i både. Skær løgene i kvarte.", minutes: 10 },
        { text: "Vend grøntsagerne med olie, timian, salt og peber i et stort fad. Læg kyllingen ovenpå.", minutes: 5 },
        { text: "Bag i ovnen, til kyllingen er gylden og gennemstegt.", minutes: 45 },
        { text: "Rør creme fraiche med lidt af stegesoen, og server.", minutes: 5 },
      ],
      tip: "Læg 4 overlår til side – de bliver til wraps i morgen.",
    }),
    day("2026-10-19", "mandag", "Wraps med kylling, spidskål og coleslaw", "rester", 15, 15, { uses: "2026-10-18" }),
    day("2026-10-20", "tirsdag", "Spaghetti med kødsovs og revet gulerod", "normal", 35, 15, {
      ingredients: [{ name: "hakket oksekød", amount: "500 g" }, { name: "spaghetti", amount: "500 g" }],
      steps: [{ text: "Brun kødet i en gryde.", minutes: 5 }],
    }),
    day("2026-10-21", "onsdag", "Rugbrødsdag – æg, leverpostej og grønt", "fast", 15, 15),
    day("2026-10-22", "torsdag", "Linsesuppe med kokos og naanbrød", "vegetar", 30, 15),
    day("2026-10-23", "fredag", "Hjemmelavet pizza med skinke og champignon", "normal", 45, 25),
    day("2026-10-24", "lørdag", "Laks i ovn med kartofler og broccoli", "normal", 35, 15),
  ],
  shopping,
};

const settings = {
  ai_task_entity: "ai_task.google_ai_task",
  start_weekday: 6,
  days: 7,
  budget: 900,
  organic: "prefer",
  organic_max_extra_pct: 20,
  avoid: ["spicy"],
  avoid_other: "oliven",
  allergies: [],
  allergies_other: "",
  household: [
    { role: "adult", age: 41, sex: "male" },
    { role: "adult", age: 39, sex: "female" },
    { role: "child", age: 9, sex: "female" },
    { role: "child", age: 6, sex: "male" },
  ],
  must_haves: [
    { name: "LETMÆLK (1 LTR. / ØKOLOGISK)", product_id: 20496, amount: 3 },
    { name: "RUGBRØD (1000 GR.)", product_id: 70001, amount: 1 },
  ],
  min_vegetarian: 1,
  max_vegetarian: 2,
  leftover_days: 1,
  fixed_days: [{ weekday: 2, text: "Rugbrødsdag" }],
  max_cook_minutes_weekday: 30,
  no_repeat_weeks: 3,
  pantry: "salt, peber, olie, smør, mel, sukker, eddike, bouillon, krydderier",
  wishes: "Sund, varieret og børnevenlig mad, som er let at lave og hurtig at rydde op efter.",
  egg_min: "free_range",
  milk_organic: true,
  produce_organic: false,
  auto_generate: true,
  auto_send: false,
  disliked_dishes: ["Fiskefrikadeller", "Gryderetter med kål"],
};

const favorites = [
  { id: "fav1", text: "Ovnbagt kylling med rodfrugter", frequency: "biweekly", last_used: "2026-10-18" },
  { id: "fav2", text: "Lasagne med masser af grønt", frequency: "monthly", last_used: "2026-09-27" },
  { id: "fav3", text: "Laks med citron, spinatpasta og pesto", frequency: "on_offer", last_used: null },
  { id: "fav4", text: "Tacos fredag", frequency: "weekly", last_used: "2026-10-16" },
];

const history = [
  { id: "plan-43", title: "Madplan uge 43", start_date: "2026-10-18", end_date: "2026-10-24", total, status: "draft", dishes: plan.days.map((d) => d.dish.split(" – ")[0]) },
  { id: "plan-42", title: "Madplan uge 42", start_date: "2026-10-11", end_date: "2026-10-17", total: 812.5, status: "sent", dishes: ["Frikadeller med kartofler", "Rester: frikadellesandwich", "Kyllingewok med nudler", "Rugbrødsdag", "Grøntsagslasagne", "Tacos", "Pasta med laks"] },
  { id: "plan-41", title: "Madplan uge 41", start_date: "2026-10-04", end_date: "2026-10-10", total: 845, status: "sent", dishes: ["Boller i karry", "Rester", "Fiskefilet med rodfrugter", "Rugbrødsdag", "Pastasalat", "Pizza", "Kylling i karry"] },
  { id: "plan-40", title: "Madplan uge 40", start_date: "2026-09-27", end_date: "2026-10-03", total: 790.25, status: "sent", dishes: ["Lasagne", "Rester", "Burger", "Rugbrødsdag", "Tomatsuppe", "Tacos", "Stegt flæsk"] },
];

const remaFavorites = [
  { ...P.chicken, price_valid_to: "2026-10-24T23:59:59+02:00" },
  { ...P.beef, price_valid_to: "2026-10-24T23:59:59+02:00" },
  { ...P.broccoli, price_valid_to: "2026-10-24T23:59:59+02:00" },
  { ...P.cheese, price_valid_to: "2026-10-24T23:59:59+02:00" },
  { ...P.salmon, price_valid_to: "2026-10-20T23:59:59+02:00" },
  { ...P.milk, upcoming_price: 11.95, upcoming_from: "2026-10-25T00:00:00+02:00", upcoming_is_advertised: true },
  { ...P.eggs, upcoming_price: 25, upcoming_from: "2026-10-25T00:00:00+02:00", upcoming_is_advertised: true },
  { ...P.ryebread },
  { ...P.spaghetti },
  { ...P.carrots },
  { ...P.coconut },
];

const remaList = {
  name: "Indkøbsliste",
  items: [
    { id: "r1", name: "Letmælk økologisk", amount: 3, bought: false },
    { id: "r2", name: "Rugbrød", amount: 1, bought: false },
    { id: "r3", name: "Opvasketabs", amount: 1, bought: false },
    { id: "r4", name: "Bananer", amount: 1, bought: true },
  ],
  total: 74.5,
};

window.DEMO = {
  state: {
    entry_id: "demo",
    title: "familien@example.com",
    settings,
    favorites,
    plans: history,
    latest_plan: plan,
    status: { state: "idle", message: null, started: null },
    default_start: "2026-10-25",
    ai_entities: [
      { entity_id: "ai_task.google_ai_task", name: "Google AI Task" },
      { entity_id: "ai_task.openai_ai_task", name: "OpenAI AI Task" },
    ],
    catalogs: {
      current: { id: "cat-43", label: "Uge 43", valid_from: "2026-10-18T00:00:00+02:00", valid_to: "2026-10-24T23:59:59+02:00" },
      upcoming: { id: "cat-44", label: "Uge 44", valid_from: "2026-10-25T00:00:00+02:00", valid_to: "2026-10-31T23:59:59+01:00" },
    },
    rema_list: remaList,
    options: {
      avoid: ["meat", "pork", "beef", "fish", "shellfish", "animal_products", "spicy"],
      allergies: ["gluten", "lactose", "milk", "egg", "nuts", "peanuts", "soy", "sesame", "celery", "mustard", "fish", "shellfish", "molluscs", "lupin", "sulphites"],
      frequencies: ["weekly", "biweekly", "monthly", "on_offer", "inspiration"],
    },
  },
  remaFavorites,
  search: [P.milk, { ...P.milk, id: 20494, name: "LETMÆLK", underline: "1 LTR.", price: 10.95, normal_price: 10.95, is_organic: false }],
};

// Answers for swapping a dish, the basic items and adding products.
window.DEMO.swapOptions = [
  { dish: "Kyllingewok med nudler, broccoli og peanutsauce", type: "normal", active_minutes: 20, total_minutes: 25,
    why: "Bruger kyllingeoverlår og broccoli fra ugens tilbud." },
  { dish: "Grøntsagslasagne med linser og revet mozzarella", type: "vegetar", active_minutes: 25, total_minutes: 60,
    why: "Vegetar, og mozzarellaen er på tilbud." },
  { dish: "Frikadeller med kartofler og stuvet spidskål", type: "normal", active_minutes: 30, total_minutes: 40,
    why: "En klassiker børnene kender, med hakket kød fra avisen." },
];
window.DEMO.pantry = [
  { name: "olie", uses: [{ dish: "Ovnbagt kylling med rodfrugter", amount: "3 spsk" }, { dish: "Spaghetti med kødsovs", amount: "1 spsk" }],
    amount: null, unit: null, on_list: false },
  { name: "smør", uses: [{ dish: "Laks med kartofler og broccoli", amount: "25 g" }, { dish: "Linsegryde med naan", amount: "30 g" }],
    amount: 55, unit: "g", on_list: false },
  { name: "bouillon", uses: [{ dish: "Spaghetti med kødsovs", amount: "1 terning" }], amount: null, unit: null, on_list: false },
  { name: "mel", uses: [{ dish: "Laks med kartofler og broccoli", amount: "2 spsk" }], amount: null, unit: null, on_list: false },
];
window.DEMO.pantryProducts = {
  olie: { id: 80010, name: "RAPSOLIE", underline: "1 LTR. / DANSK", price: 19, normal_price: 19, is_advertised: false, is_organic: false },
  smør: { id: 80020, name: "SMØR", underline: "250 GR. / ØKOLOGISK", price: 24, normal_price: 24, is_advertised: false, is_organic: true },
  bouillon: { id: 80030, name: "HØNSEBOUILLON", underline: "12 STK.", price: 10, normal_price: 10, is_advertised: false, is_organic: false },
  mel: { id: 80040, name: "HVEDEMEL", underline: "2 KG.", price: 11, normal_price: 11, is_advertised: false, is_organic: false },
};
window.DEMO.coffee = [
  { id: 90010, name: "KAFFE FORMALET", underline: "400 GR. / ØKOLOGISK", price: 42, normal_price: 49, is_advertised: true, is_organic: true,
    image: pic("☕", "#F3E9D8") },
  { id: 90011, name: "KAFFEBØNNER MELLEMRISTET", underline: "500 GR.", price: 55, normal_price: 55, is_advertised: false, is_organic: false,
    image: pic("☕", "#EFE7E1") },
];
