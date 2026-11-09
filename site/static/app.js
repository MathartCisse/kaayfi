const view = document.querySelector("#view");

const CATEGORIES = [
  ["Sénégalaise", "senegalaise", "/figma/cat-senegalaise.jpg"],
  ["Burger", "burger", "/figma/cat-burger.jpg"],
  ["Pizza", "pizza", "/figma/cat-pizza.jpg"],
  ["Sushi", "sushi", "/figma/cat-sushi.jpg"],
  ["Healthy", "healthy", "/figma/cat-healthy.jpg"],
  ["Brunch", "brunch", "/figma/cat-brunch.jpg"],
];

const BANDS = [
  ["Moins de 3\u00a0000", "1000", "3000"],
  ["3\u00a0000 – 5\u00a0000", "3000", "5000"],
  ["5\u00a0000 – 10\u00a0000", "5000", "10000"],
];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function money(value) {
  if (value == null || value === "") return "";
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
}

function withFcfa(value) {
  const text = String(value || "").trim();
  if (!text) return "Prix non indiqué";
  if (/prix non indiqu/i.test(text)) return text;
  if (/fcfa/i.test(text)) return text.replace(/fcfa/gi, "Fcfa");
  return text.replace(/\d{1,3}(?:[\s\u00a0]\d{3})+|\d{2,6}/g, (num) => `${num} Fcfa`);
}

function rangeLabel(min, max) {
  if (min == null) return "";
  if (max == null || min === max) return `${money(min)} Fcfa`;
  return `${money(min)} – ${money(max)} Fcfa`;
}

function printed(value) {
  if (!value || /^non imprim/i.test(value)) return "";
  return value;
}

function shortHours(value) {
  const full = printed(value);
  if (!full) return "";
  const cut = full.split(/[.;]/)[0].trim();
  return cut.length > 42 ? `${cut.slice(0, 40)}…` : cut;
}

function favSet() {
  try {
    return new Set(JSON.parse(localStorage.getItem("kaayfi-favoris") || "[]"));
  } catch {
    return new Set();
  }
}

function toggleFav(name) {
  const saved = favSet();
  if (saved.has(name)) saved.delete(name);
  else saved.add(name);
  localStorage.setItem("kaayfi-favoris", JSON.stringify([...saved]));
  return saved.has(name);
}

function searchHash(query, min, max, ou) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (min) params.set("prix_min", min);
  if (max) params.set("prix_max", max);
  if (ou) params.set("ou", ou);
  const text = params.toString();
  return text ? `#/recherche?${text}` : "#/recherche";
}

function fieldCombo(kind, name, value, placeholder, icon, klass, extra = "") {
  return `<div class="combo" data-kind="${kind}">
    <label class="${klass}">
      ${icon}
      <input name="${name}" value="${esc(value)}" placeholder="${placeholder}" autocomplete="off" role="combobox" aria-expanded="false" aria-autocomplete="list">
      ${extra}
    </label>
    <ul class="suggestions" hidden role="listbox"></ul>
  </div>`;
}

function routeParts() {
  const raw = (location.hash || "#/").replace(/^#/, "");
  const cut = raw.indexOf("?");
  return {
    path: cut < 0 ? raw : raw.slice(0, cut),
    params: new URLSearchParams(cut < 0 ? "" : raw.slice(cut + 1)),
  };
}

function heartButton(name) {
  const on = favSet().has(name);
  return `<button class="heart" type="button" data-fav="${esc(name)}" aria-pressed="${on ? "true" : "false"}" aria-label="Retenir ${esc(name)}"><img src="/figma/heart.svg" alt=""></button>`;
}

function phoneBook(sites) {
  const seen = new Set();
  const book = [];
  const several = (sites || []).length > 1;
  for (const site of sites || []) {
    for (const phone of site.telephones || []) {
      if (!phone.e164 || seen.has(phone.e164)) continue;
      seen.add(phone.e164);
      const place = several && site.lieu ? site.lieu : "";
      book.push({ e164: phone.e164, affichage: phone.affichage, place });
    }
  }
  return book;
}

function calls(sites) {
  return phoneBook(sites).map((phone) => (
    `<a class="call" href="tel:${esc(phone.e164)}">Appeler ${esc(phone.affichage)}</a>`
  )).join("");
}

function phoneIcon() {
  return `<svg class="phone-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 7a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1 11.4 11.4 0 0 0 .57 3.6 1 1 0 0 1-.25 1l-2.22 2.2z"/></svg>`;
}

function callFloat(sites) {
  const book = phoneBook(sites);
  if (!book.length) return "";
  const icon = phoneIcon();
  if (book.length === 1) {
    const phone = book[0];
    return `<a class="call-float-main" href="tel:${esc(phone.e164)}">${icon}Appeler</a>`;
  }
  const list = book.map((phone) => {
    const label = phone.place ? `${phone.place} · ${phone.affichage}` : phone.affichage;
    return `<a class="call" href="tel:${esc(phone.e164)}">${icon}${esc(label)}</a>`;
  }).join("");
  return `<div class="call-dock">
    <div class="call-dock-list" hidden>${list}</div>
    <button class="call-float-main" type="button" aria-expanded="false">${icon}Appeler</button>
  </div>`;
}

function firstSite(sites) {
  return (sites || [])[0] || {};
}

function banner(logo, hours, name) {
  const badge = hours ? `<span class="badge">${esc(shortHours(hours))}</span>` : "<span></span>";
  const image = logo ? `<img class="mark" src="${esc(logo)}" alt="">` : "";
  return `<div class="cover logo-banner">${image}${badge}${heartButton(name)}</div>`;
}

function placeCard(place) {
  const hours = printed(place.horaires);
  const price = rangeLabel(place.prix_min, place.prix_max);
  return `<article class="place">
    ${banner(place.logo, hours, place.nom)}
    <div class="place-body">
      <div>
        <div class="row-between"><h3>${esc(place.nom)}</h3></div>
        <p class="muted">${esc(place.adresse || "")}</p>
      </div>
      <div class="row-between">
        <p class="price-line">${price ? `💰 ${esc(price)}` : ""}</p>
        <a class="menu-btn" href="#/menu?e=${encodeURIComponent(place.nom)}">Voir le menu</a>
      </div>
    </div>
  </article>`;
}

const FOOD_RULES = [
  ["pizza", /pizza/],
  ["burger", /burger|hamburger/],
  ["sushi", /sushi|maki|sashimi/],
  ["coffee", /cafe|coffee|cappu|latte|espresso|expresso|the\b|thé/],
  ["drink", /boisson|jus|smoothie|milkshake|cocktail|soda|sirop/],
  ["breakfast", /petit|brunch|matin|viennois|croissant/],
  ["dessert", /dessert|crepe|crêpe|gaufre|pancake|gateau|gâteau|brownie|cookie|muffin|glace|gelato|donut|waffle|souffle|profiterole|cheesecake/],
  ["salad", /salade|bowl|poke|quinoa/],
  ["sandwich", /sandwich|bagel|club|dwich|tartine|panini|wrap/],
  ["soup", /soupe|veloute|velouté/],
  ["grill", /grill|brochette|kebab|chawarma|shawarma|tacos|yakitori/],
];

const FOOD_SVG = {
  plat: `<path d="M8 3v8M8 3c-1.6 0-2.6 1.3-2.6 3S6.4 9 8 9M8 11v10M16 3v18"/>`,
  burger: `<path d="M6 10c0-2.2 2.2-4 6-4s6 1.8 6 4H6zM5 13h14M6.5 16.5c.8 1.2 2.2 2 5.5 2s4.7-.8 5.5-2"/>`,
  pizza: `<path d="M12 4l8 14H4L12 4zM12 4v14M9.2 13.2h.01M14.2 11h.01"/>`,
  sushi: `<rect x="4" y="8" width="16" height="8" rx="4"/><path d="M4 12h16M12 8v8"/>`,
  sandwich: `<path d="M5 9c2-2 12-2 14 0M5 12h14M5 15c2 2 12 2 14 0"/>`,
  salad: `<path d="M5 14c0 3 3 5 7 5s7-2 7-5H5zM8 14c.5-3 2-5 4-6 2 1 3.5 3 4 6"/>`,
  dessert: `<path d="M7 11l5-6 5 6M6 11h12v2a6 6 0 0 1-12 0v-2z"/>`,
  coffee: `<path d="M7 8h8v6a4 4 0 0 1-8 0V8zM15 9h2.2a2 2 0 0 1 0 4H15M8 19h8"/>`,
  drink: `<path d="M8 4h8l-1 8a3 3 0 0 1-6 0L8 4zM12 15v4M9 19h6"/>`,
  breakfast: `<path d="M12 5v2M7.5 7.5l1.2 1.2M16.5 7.5l-1.2 1.2M8 16h8M9 16c0-2 1.3-4 3-4s3 2 3 4"/>`,
  soup: `<path d="M5 12h14M6 12c.4 3.2 2.4 5 6 5s5.6-1.8 6-5M9 8c.4.8 1.2.8 1.6 0M13 8c.4.8 1.2.8 1.6 0"/>`,
  grill: `<path d="M7 17l10-10M9 7l1.2 1.2M14 16l1.2 1.2M8 13.5l2.2 2.2M13.5 8l2.2 2.2"/>`,
};

function foldText(value) {
  return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function foodKind(plat) {
  const type = foldText(plat.type);
  const nom = foldText(plat.nom);
  for (const [kind, rule] of FOOD_RULES) {
    if (rule.test(type)) return kind;
  }
  for (const [kind, rule] of FOOD_RULES) {
    if (rule.test(nom)) return kind;
  }
  return "plat";
}

function foodSvg(kind) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${FOOD_SVG[kind] || FOOD_SVG.plat}</svg>`;
}

function dishVisual(plat) {
  if (plat.image) return `<img src="${esc(plat.image)}" alt="">`;
  return `<span class="food-icon">${foodSvg(foodKind(plat))}</span>`;
}

function platHref(plat) {
  const params = new URLSearchParams({ id: String(plat.id) });
  if (plat.etablissement) params.set("e", plat.etablissement);
  return `#/plat?${params}`;
}

function siteBlock(site, multiple, showCalls = true) {
  const title = multiple && site.nom ? `<h3>${esc(site.nom)}</h3>` : "";
  const phones = showCalls ? `<div class="calls">${calls([site])}</div>` : "";
  return `<div class="site-card">${title}${printed(site.adresse) ? `<p>${esc(printed(site.adresse))}</p>` : ""}${printed(site.horaires) ? `<p>${esc(printed(site.horaires))}</p>` : ""}${phones}</div>`;
}

function thumb(plat) {
  return `<a class="thumb" href="${platHref(plat)}">
    ${dishVisual(plat)}
    <strong>${esc(plat.nom)}</strong>
    <em>${esc(withFcfa(plat.prix))}</em>
  </a>`;
}

function matchRow(plat) {
  const detail = plat.composition || plat.type || "";
  return `<a class="dish" href="${platHref(plat)}">
    ${dishVisual(plat)}
    <span class="dish-copy">
      <strong>${esc(plat.nom)}</strong>
      ${detail ? `<span>${esc(detail)}</span>` : ""}
      <em>${esc(withFcfa(plat.prix))}</em>
    </span>
  </a>`;
}

function resultGroup(carte) {
  const site = firstSite(carte.sites);
  const hours = printed(site.horaires);
  const shown = (carte.plats || []).length;
  const price = rangeLabel(carte.prix_min, carte.prix_max);
  const more = carte.total > shown
    ? `<p class="sub">${shown} sur ${carte.total} plats. La suite est dans le menu.</p>`
    : "";
  return `<article class="place result-group">
    ${banner(carte.logo, hours, carte.nom)}
    <div class="place-body">
      <div>
        <h3>${esc(carte.nom)}</h3>
        ${printed(site.adresse) ? `<p class="muted">${esc(printed(site.adresse))}</p>` : ""}
      </div>
      ${price ? `<p class="price-line">${esc(price)}</p>` : ""}
      <div class="calls">
        ${calls([site])}
        <a class="menu-link" href="#/menu?e=${encodeURIComponent(carte.nom)}">Voir le menu</a>
      </div>
      <div class="match-list">${(carte.plats || []).map(matchRow).join("")}</div>
      ${more}
    </div>
  </article>`;
}

function dishRow(plat) {
  return `<a class="dish" href="${platHref(plat)}">
    ${dishVisual(plat)}
    <span class="dish-copy">
      <strong>${esc(plat.nom)}</strong>
      <span>${esc(plat.etablissement)}</span>
      <em>${esc(withFcfa(plat.prix))}</em>
    </span>
  </a>`;
}

function budgetChips(query, min, max, ou) {
  return BANDS.map(([label, lo, hi]) => {
    const active = String(min || "") === lo && String(max || "") === hi;
    const href = active ? searchHash(query, "", "", ou) : searchHash(query, lo, hi, ou);
    return `<a class="chip${active ? " active" : ""}" href="${href}">${label}</a>`;
  }).join("");
}

function plural(count, one, many) {
  return `${count} ${count > 1 ? many : one}`;
}

const MOMENTS = {
  matin: {
    titre: "Un petit déjeuner ?",
    lead: "Formules, brunchs et viennoiseries du catalogue, à appeler pour commander.",
    section: "Pour le petit déjeuner",
    sub: "Les petits déjeuners et brunchs imprimés au catalogue",
    query: "petit déjeuner",
    cats: ["Brunch", "Healthy", "Sénégalaise", "Burger", "Pizza", "Sushi"],
  },
  midi: {
    titre: "On mange où à midi ?",
    lead: "Plats, sandwiches et burgers du catalogue, à commander en appelant.",
    section: "Pour le déjeuner",
    sub: "Des plats du catalogue pour le milieu de journée",
    query: "plat",
    cats: ["Sénégalaise", "Burger", "Pizza", "Sushi", "Healthy", "Brunch"],
  },
  apres: {
    titre: "Une pause sucrée ?",
    lead: "Cafés, crêpes et desserts du catalogue.",
    section: "Pour le goûter",
    sub: "Crêpes, viennoiseries et desserts du catalogue",
    query: "crêpe",
    cats: ["Healthy", "Brunch", "Sénégalaise", "Burger", "Pizza", "Sushi"],
  },
  soir: {
    titre: "Qu'est-ce qu'on mange ce soir ?",
    lead: "Plats du soir du catalogue, à commander en appelant.",
    section: "Pour le dîner",
    sub: "Plats, grillades, pizzas et sushis du catalogue",
    query: "plat",
    cats: ["Burger", "Pizza", "Sushi", "Sénégalaise", "Healthy", "Brunch"],
  },
  nuit: {
    titre: "Encore une petite faim ?",
    lead: "Les plats du catalogue, à commander en appelant.",
    section: "Pour plus tard",
    sub: "Plats, grillades, pizzas et sushis du catalogue",
    query: "plat",
    cats: ["Burger", "Pizza", "Sushi", "Sénégalaise", "Healthy", "Brunch"],
  },
};

const LIEU_TITRE = {
  Almadies: "Aux Almadies",
  "Point E": "À Point E",
  "Corniche Ouest": "Corniche Ouest",
  Saly: "À Saly",
  "Centre-ville": "Au centre-ville",
  "Cité Keur Gorgui": "Cité Keur Gorgui",
  Ngor: "À Ngor",
  Ouakam: "À Ouakam",
  Yoff: "À Yoff",
  Médina: "À la Médina",
  "Sicap Baobabs": "Sicap Baobabs",
  "Amitié 3": "Amitié 3",
  Mariste: "Mariste",
  Parcelles: "Parcelles",
  Ngaparou: "À Ngaparou",
  "Rufisque Ouest": "Rufisque Ouest",
  Diamniadio: "Diamniadio",
};

// Position de démonstration : Pointe des Almadies, le temps de brancher la vraie géolocalisation.
const POSITION_SIMULEE = { lat: 14.7455, lng: -17.516 };

function savedLieu() {
  try {
    return (localStorage.getItem("kaayfi-lieu") || "").trim();
  } catch {
    return "";
  }
}

function lieuSimule() {
  try {
    return localStorage.getItem("kaayfi-lieu-simule") === "1";
  } catch {
    return false;
  }
}

function simulationEnPause() {
  try {
    return sessionStorage.getItem("kaayfi-pas-simuler") === "1";
  } catch {
    return false;
  }
}

async function appliquerPositionSimulee() {
  const params = new URLSearchParams({
    lat: String(POSITION_SIMULEE.lat),
    lng: String(POSITION_SIMULEE.lng),
  });
  const data = await fetch(`/api/lieu?${params}`).then((response) => response.json());
  if (!data.texte) return "";
  localStorage.setItem("kaayfi-lieu", data.texte);
  localStorage.setItem("kaayfi-lieu-simule", "1");
  sessionStorage.removeItem("kaayfi-lieu-plus-tard");
  return data.texte;
}

function lieuDismissed() {
  try {
    return sessionStorage.getItem("kaayfi-lieu-plus-tard") === "1";
  } catch {
    return false;
  }
}

function lieuAsk(lieu) {
  if (lieu) {
    const label = lieuSimule() ? "Position simulée" : "Quartier retenu";
    return `<p class="lieu-set">${label} : <strong>${esc(lieu)}</strong> <button type="button" id="lieu-changer">Changer</button></p>`;
  }
  const hidden = lieuDismissed() ? " hidden" : "";
  return `<div class="ask-lieu"${hidden} id="ask-lieu">
      <p>Utiliser votre position pour proposer un quartier du catalogue ?</p>
      <div class="ask-actions">
        <button class="ask-yes" type="button" id="lieu-oui">Autoriser</button>
        <button class="ask-no" type="button" id="lieu-non">Plus tard</button>
      </div>
    </div>
    <p class="lieu-note" id="lieu-note"></p>`;
}

function heroChips(moment) {
  const prox = savedLieu()
    ? `<a class="chip" href="#pres"><img src="/figma/pin.svg" alt="">À proximité</a>`
    : `<button class="chip" type="button" id="lieu-prox"><img src="/figma/pin.svg" alt="">À proximité</button>`;
  const dej = `<a class="chip${moment === "matin" ? " moment" : ""}" href="${searchHash("petit déjeuner")}"><img src="/figma/sunrise.svg" alt="">Petit déjeuner</a>`;
  const cafe = `<a class="chip${moment === "apres" ? " moment" : ""}" href="${searchHash("café")}"><img src="/figma/coffee.svg" alt="">Café</a>`;
  const brunch = `<a class="chip" href="${searchHash("brunch")}"><img src="/figma/utensils.svg" alt="">Brunch</a>`;
  const budget = `<a class="chip" href="${searchHash("", "1000", "3000")}"><img src="/figma/wallet.svg" alt="">-de 3000 Fcfa</a>`;
  const midi = `<a class="chip moment" href="#moment"><img src="/figma/utensils.svg" alt="">Déjeuner</a>`;
  const soir = `<a class="chip moment" href="#moment"><img src="/figma/utensils.svg" alt="">Dîner</a>`;
  const order = {
    matin: [dej, brunch, cafe, prox, budget],
    midi: [midi, prox, cafe, brunch, budget],
    apres: [cafe, brunch, prox, dej, budget],
    soir: [soir, prox, brunch, cafe, budget],
    nuit: [soir, prox, cafe, brunch, budget],
  };
  return (order[moment] || order.soir).join("");
}

function usePosition() {
  const note = document.querySelector("#lieu-note");
  if (!navigator.geolocation) {
    if (note) note.textContent = "La position n'est pas disponible sur cet appareil. Indiquez un quartier.";
    return;
  }
  if (note) note.textContent = "Demande d'autorisation…";
  navigator.geolocation.getCurrentPosition(async (pos) => {
    const params = new URLSearchParams({
      lat: String(pos.coords.latitude),
      lng: String(pos.coords.longitude),
    });
    const data = await fetch(`/api/lieu?${params}`).then((response) => response.json());
    if (!data.texte) {
      const line = document.querySelector("#lieu-note");
      if (line) line.textContent = "Aucun quartier du catalogue n'est proche de cette position.";
      return;
    }
    localStorage.setItem("kaayfi-lieu", data.texte);
    localStorage.removeItem("kaayfi-lieu-simule");
    sessionStorage.removeItem("kaayfi-lieu-plus-tard");
    sessionStorage.removeItem("kaayfi-pas-simuler");
    route();
  }, () => {
    const line = document.querySelector("#lieu-note");
    if (line) line.textContent = "Position refusée. Indiquez un quartier du catalogue.";
  }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
}

async function renderHome() {
  view.innerHTML = `<p class="loading">Chargement…</p>`;
  if (!savedLieu() && !lieuDismissed() && !simulationEnPause()) {
    await appliquerPositionSimulee();
  }
  const lieu = savedLieu();
  const params = new URLSearchParams({ heure: String(new Date().getHours()) });
  if (lieu) params.set("ou", lieu);
  const data = await fetch(`/api/home?${params}`).then((response) => response.json());
  const moment = MOMENTS[data.moment] || MOMENTS.soir;
  const catOrder = new Map(moment.cats.map((label, index) => [label, index]));
  const cats = [...CATEGORIES].sort((a, b) => (catOrder.get(a[0]) ?? 9) - (catOrder.get(b[0]) ?? 9)).map(([label, query, image]) => (
    `<a class="cat" href="${searchHash(query)}" style="background-image:url('${image}')"><span>${esc(label)}</span></a>`
  )).join("");
  const heading = data.pres_perso && lieu ? (LIEU_TITRE[lieu] || lieu) : "Aux Almadies";
  const places = (data.pres || []).length
    ? `<div class="stack places">${data.pres.map(placeCard).join("")}</div>`
    : `<p class="sub">Aucun établissement du catalogue à cette adresse.</p>`;
  const duMoment = (data.du_moment || []).length
    ? `<section class="block" id="moment">
        <div>
          <div class="section-head">
            <h2>${esc(moment.section)}</h2>
            <a class="linkish" href="${searchHash(moment.query)}">Voir tout</a>
          </div>
          <p class="sub">${esc(moment.sub)}</p>
        </div>
        <div class="stack dishes">${data.du_moment.map(dishRow).join("")}</div>
      </section>`
    : "";
  const collections = [
    ["brunch", "Les meilleurs brunchs de Dakar", "/figma/col-brunch.jpg"],
    ["", "Où manger à moins de 3 000 Fcfa ?", "/figma/col-budget.jpg"],
    ["dessert", "Les meilleurs restaurants pour un date", "/figma/col-date.jpg"],
  ];
  if (data.moment === "matin") collections.sort((a, b) => Number(b[0] === "brunch") - Number(a[0] === "brunch"));
  view.innerHTML = `
    <section class="hero">
      <div class="hero-copy">
        <h1>${esc(moment.titre)}</h1>
        <p class="lead">${esc(moment.lead)}</p>
      </div>
      <div class="chips">${heroChips(data.moment || "soir")}</div>
      <form class="search-card find">
        ${fieldCombo("met", "q", "", "Un plat ou un restaurant...", `<img src="/figma/search.svg" alt="">`, "field")}
        <div class="rule"></div>
        ${fieldCombo("lieu", "ou", lieu, "Un quartier ou une adresse...", `<img src="/figma/pin.svg" alt="">`, "field")}
        ${lieuAsk(lieu)}
        <button class="cta" type="submit">Rechercher</button>
      </form>
    </section>
    ${duMoment}
    <section class="section">
      <div class="section-head">
        <h2>Qu'avez-vous envie de manger ?</h2>
        <button class="linkish" type="button" id="focus-search">Voir tout</button>
      </div>
    </section>
    <div class="cats">${cats}</div>
    <section class="block" id="pres">
      <h2>${esc(heading)}</h2>
      ${places}
    </section>
    <section class="block">
      <div>
        <h2>Bien manger sans se ruiner</h2>
        <p class="sub">Les plats photographiés à petit prix</p>
      </div>
      <div class="stack dishes">${(data.budget || []).map(dishRow).join("")}</div>
      <a class="more" href="${searchHash("", "1000", "3000")}">Voir tous les plats économiques →</a>
    </section>
    <section class="block">
      <h2>Collections de la semaine</h2>
      <div class="collections">
        ${collections.map(([query, label, image]) => (
          `<a class="collection" href="${query ? searchHash(query) : searchHash("", "1000", "3000")}" style="background-image:url('${image}')">${esc(label)}</a>`
        )).join("")}
      </div>
    </section>`;
}

function searchForm(query, ou, min, max, clear) {
  const eraser = clear
    ? `<button class="clear" type="button" data-clear aria-label="Effacer"><img src="/figma/close.svg" alt=""></button>`
    : "";
  return `<form class="search-bar find">
      <div class="search-line">
        <a class="back" href="#/" aria-label="Retour"><img src="/figma/back.svg" alt=""></a>
        ${fieldCombo("met", "q", query, "Un plat ou un restaurant...", `<img src="/figma/search2.svg" alt="">`, "query", eraser)}
        ${fieldCombo("lieu", "ou", ou, "Un quartier ou une adresse...", `<img src="/figma/pin.svg" alt="">`, "query")}
      </div>
      <div class="budget">
        <p>Votre budget ?</p>
        <div class="chips">${budgetChips(query, min, max, ou)}</div>
      </div>
    </form>`;
}

async function renderSearch(params) {
  const query = params.get("q") || "";
  const min = params.get("prix_min") || "";
  const max = params.get("prix_max") || "";
  const ou = params.get("ou") || "";
  if (!query && !min && !max && !ou) {
    view.innerHTML = `
      ${searchForm("", "", "", "", false)}
      <p class="empty">Indiquez un plat, un restaurant, un quartier, ou choisissez un budget.</p>`;
    return;
  }
  view.innerHTML = `<p class="loading">Recherche…</p>`;
  const url = new URL("/api/search", location.origin);
  if (query) url.searchParams.set("q", query);
  if (min) url.searchParams.set("prix_min", min);
  if (max) url.searchParams.set("prix_max", max);
  if (ou) url.searchParams.set("ou", ou);
  const data = await fetch(url).then((response) => response.json());
  const lieu = data.lieu
    ? `<article class="place"><div class="place-body">
        <div class="identity">${data.lieu.logo ? `<img src="${esc(data.lieu.logo)}" alt="">` : ""}<h1>${esc(data.lieu.nom)}</h1></div>
        ${(data.lieu.sites || []).map((site) => siteBlock(site, (data.lieu.sites || []).length > 1)).join("")}
      </div></article>`
    : "";
  const body = data.cartes && data.cartes.length
    ? `<div class="stack results">${data.cartes.map(resultGroup).join("")}</div>`
    : (lieu || `<p class="empty">Aucun plat ne correspond. Essayez un autre mot, ou un budget.</p>`);
  const shown = (data.cartes || []).length;
  const rests = data.restaurants || 0;
  const count = data.total
    ? `<p class="count">${plural(data.total, "plat", "plats")} · ${plural(rests, "restaurant", "restaurants")}${shown && shown < rests ? ` · ${shown} adresses affichées` : ""}</p>`
    : "";
  view.innerHTML = `
    ${searchForm(query, ou, min, max, Boolean(query))}
    ${count}
    <section class="block">${body}</section>`;
}

async function renderMenu(params) {
  const name = params.get("e") || "";
  view.innerHTML = `<p class="loading">Menu…</p>`;
  const response = await fetch(`/api/menu?e=${encodeURIComponent(name)}`);
  if (!response.ok) {
    view.innerHTML = `<p class="empty">Ce restaurant n'est pas dans le catalogue.</p>`;
    return;
  }
  const data = await response.json();
  const groups = new Map();
  for (const plat of data.plats || []) {
    const key = plat.type || "Carte";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(plat);
  }
  const entries = [...groups];
  const tabs = entries.length > 1
    ? `<div class="type-tabs" role="tablist">${entries.map(([type], index) =>
        `<button type="button" class="type-tab" role="tab" data-panel="${index}" aria-selected="${index === 0 ? "true" : "false"}">${esc(type)}</button>`
      ).join("")}</div>`
    : "";
  const list = entries.map(([type, plats], index) => `
    <section class="menu-group" data-panel="${index}"${index === 0 ? "" : " hidden"}>
      <h2 class="type-title">${esc(type)}</h2>
      <div class="menu-grid">
        ${plats.map((plat) => `<a class="menu-row" href="${platHref(plat)}">
          ${dishVisual(plat)}
          <span class="menu-copy"><strong>${esc(plat.nom)}</strong><em>${esc(withFcfa(plat.prix))}</em></span>
        </a>`).join("")}
      </div>
    </section>
  `).join("");
  const menuSites = data.lieu.sites || [];
  const sites = menuSites.map((site) => siteBlock(site, menuSites.length > 1, false)).join("");
  view.innerHTML = `
    <div class="sheet">
      <a class="back" href="#/" aria-label="Retour"><img src="/figma/back.svg" alt=""></a>
      <div class="identity">
        ${data.lieu.logo ? `<img src="${esc(data.lieu.logo)}" alt="">` : ""}
        <h1>${esc(data.lieu.nom)}</h1>
      </div>
      ${sites || `<p class="plain">Aucun numéro imprimé pour cet établissement.</p>`}
      ${data.plats.length ? `${tabs}${list}` : `<p class="empty">Le catalogue n'a pas encore les plats de cet établissement. Le numéro ci-dessus permet d'appeler.</p>`}
    </div>
    ${callFloat(menuSites)}`;
}

async function renderDish(params) {
  view.innerHTML = `<p class="loading">Plat…</p>`;
  const response = await fetch(`/api/plat?id=${encodeURIComponent(params.get("id") || "")}&e=${encodeURIComponent(params.get("e") || "")}`);
  if (!response.ok) {
    view.innerHTML = `<p class="empty">Ce plat est introuvable.</p>`;
    return;
  }
  const plat = await response.json();
  const shot = plat.image
    ? `<img class="hero-shot" src="${esc(plat.image)}" alt="">`
    : `<div class="hero-shot food-icon">${foodSvg(foodKind(plat))}</div>`;
  const dishSites = plat.sites || [];
  const sites = dishSites.map((site) => siteBlock(site, dishSites.length > 1, false)).join("");
  view.innerHTML = `
    <div class="sheet">
      <a class="back" href="#/menu?e=${encodeURIComponent(plat.etablissement)}" aria-label="Retour"><img src="/figma/back.svg" alt=""></a>
    </div>
    ${shot}
    <article class="detail">
      <p class="eyebrow">${esc(plat.type || "")}</p>
      <h1>${esc(plat.nom)}</h1>
      <a class="resto" href="#/menu?e=${encodeURIComponent(plat.etablissement)}">${esc(plat.etablissement)}</a>
      ${plat.composition ? `<p class="composition">${esc(plat.composition)}</p>` : ""}
      <p class="amount">${esc(withFcfa(plat.prix))}</p>
      ${sites}
    </article>
    ${callFloat(dishSites)}`;
}

async function route() {
  const { path, params } = routeParts();
  window.scrollTo(0, 0);
  try {
    if (path === "/recherche") await renderSearch(params);
    else if (path === "/menu") await renderMenu(params);
    else if (path === "/plat") await renderDish(params);
    else await renderHome();
  } catch (error) {
    view.innerHTML = `<p class="empty">La page n'a pas pu charger. Relancez la recherche.</p>`;
  }
}

const GENRE = { plat: "Plat", restaurant: "Restaurant", lieu: "Lieu", type: "Type" };
let suggestSeq = 0;

function closeSuggest(combo) {
  const list = combo.querySelector(".suggestions");
  const input = combo.querySelector("input");
  if (list) list.hidden = true;
  if (input) input.setAttribute("aria-expanded", "false");
  combo._items = [];
}

function closeAllSuggest() {
  document.querySelectorAll(".combo").forEach(closeSuggest);
}

async function loadSuggest(combo, value, selectFirst) {
  const input = combo.querySelector("input");
  const kind = combo.dataset.kind;
  const folded = value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (kind === "met" && folded.replace(/[^a-z0-9]/g, "").length < 2) {
    closeSuggest(combo);
    return;
  }
  const seq = ++suggestSeq;
  const response = await fetch(`/api/suggest?kind=${kind}&q=${encodeURIComponent(value)}`);
  const data = await response.json();
  if (seq !== suggestSeq || document.activeElement !== input) return;
  const items = data.suggestions || [];
  const list = combo.querySelector(".suggestions");
  if (!items.length) {
    closeSuggest(combo);
    return;
  }
  combo._items = items;
  list.innerHTML = items.map((item, index) => `
    <li role="option" data-i="${index}">
      <span class="genre">${esc(GENRE[item.genre] || item.genre)}</span>
      <strong>${esc(item.texte)}</strong>
      ${item.detail ? `<small>${esc(item.detail)}</small>` : ""}
    </li>`).join("");
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
  if (selectFirst && list.children[0]) list.children[0].setAttribute("aria-selected", "true");
}

function moveSuggest(combo, direction) {
  const items = combo._items || [];
  if (!items.length) return;
  const list = combo.querySelector(".suggestions");
  const current = [...list.querySelectorAll("li")].findIndex((item) => item.getAttribute("aria-selected") === "true");
  const next = (current + direction + items.length) % items.length;
  list.querySelectorAll("li").forEach((item, index) => {
    item.toggleAttribute("aria-selected", index === next);
  });
  list.children[next].scrollIntoView({ block: "nearest" });
}

function applySuggest(combo, item) {
  const input = combo.querySelector("input");
  input.value = item.texte;
  closeSuggest(combo);
  const form = combo.closest("form");
  if (form) form.requestSubmit();
}

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.classList.contains("find")) return;
  event.preventDefault();
  closeAllSuggest();
  const data = new FormData(form);
  const query = String(data.get("q") || "").trim();
  const ou = String(data.get("ou") || "").trim();
  const { params } = routeParts();
  location.hash = searchHash(query, params.get("prix_min") || "", params.get("prix_max") || "", ou);
});

let suggestTimer = 0;
document.addEventListener("input", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.closest(".combo")) return;
  const combo = input.closest(".combo");
  clearTimeout(suggestTimer);
  suggestTimer = setTimeout(() => loadSuggest(combo, input.value), 120);
});

document.addEventListener("focusin", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement)) return;
  const combo = input.closest(".combo");
  if (!combo) return;
  document.querySelectorAll(".combo").forEach((other) => {
    if (other !== combo) closeSuggest(other);
  });
  if (combo.dataset.kind === "lieu") loadSuggest(combo, input.value);
});

document.addEventListener("keydown", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || !input.closest(".combo")) return;
  const combo = input.closest(".combo");
  const open = combo.querySelector(".suggestions") && !combo.querySelector(".suggestions").hidden;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    if (!open) loadSuggest(combo, input.value, true);
    else moveSuggest(combo, 1);
  } else if (event.key === "ArrowUp" && open) {
    event.preventDefault();
    moveSuggest(combo, -1);
  } else if (event.key === "Escape") {
    closeSuggest(combo);
  } else if (event.key === "Enter" && open) {
    const chosen = combo.querySelector("li[aria-selected='true']");
    if (!chosen) return;
    event.preventDefault();
    applySuggest(combo, combo._items[Number(chosen.dataset.i)]);
  }
});

document.addEventListener("mousedown", (event) => {
  const option = event.target.closest(".suggestions li");
  if (!option) return;
  event.preventDefault();
  const combo = option.closest(".combo");
  applySuggest(combo, combo._items[Number(option.dataset.i)]);
});

document.addEventListener("click", (event) => {
  const opener = event.target.closest(".call-dock .call-float-main");
  if (opener) {
    const dock = opener.closest(".call-dock");
    const list = dock.querySelector(".call-dock-list");
    const open = list.hidden;
    list.hidden = !open;
    opener.setAttribute("aria-expanded", open ? "true" : "false");
    return;
  }
  if (!event.target.closest(".call-dock")) {
    for (const dock of document.querySelectorAll(".call-dock")) {
      const list = dock.querySelector(".call-dock-list");
      const button = dock.querySelector(".call-float-main");
      if (list) list.hidden = true;
      if (button) button.setAttribute("aria-expanded", "false");
    }
  }
  const tab = event.target.closest(".type-tab");
  if (tab) {
    const bar = tab.closest(".type-tabs");
    const panel = tab.dataset.panel;
    for (const button of bar.querySelectorAll(".type-tab")) {
      button.setAttribute("aria-selected", button === tab ? "true" : "false");
    }
    for (const group of view.querySelectorAll(".menu-group")) {
      group.hidden = group.dataset.panel !== panel;
    }
    tab.scrollIntoView({ inline: "nearest", block: "nearest" });
    return;
  }
  const fav = event.target.closest("[data-fav]");
  if (fav) {
    event.preventDefault();
    fav.setAttribute("aria-pressed", toggleFav(fav.dataset.fav) ? "true" : "false");
    return;
  }
  if (event.target.closest("[data-clear]")) {
    const ou = view.querySelector('input[name="ou"]');
    const { params } = routeParts();
    location.hash = searchHash("", params.get("prix_min") || "", params.get("prix_max") || "", ou ? ou.value.trim() : "");
    return;
  }
  if (!event.target.closest(".combo")) closeAllSuggest();
  if (event.target.closest("#focus-search")) {
    const field = view.querySelector("input[name=q]");
    if (field) field.focus();
  }
  if (event.target.closest("#lieu-oui")) {
    event.preventDefault();
    usePosition();
    return;
  }
  if (event.target.closest("#lieu-non")) {
    event.preventDefault();
    sessionStorage.setItem("kaayfi-lieu-plus-tard", "1");
    const ask = document.querySelector("#ask-lieu");
    if (ask) ask.hidden = true;
    return;
  }
  if (event.target.closest("#lieu-changer")) {
    event.preventDefault();
    localStorage.removeItem("kaayfi-lieu");
    localStorage.removeItem("kaayfi-lieu-simule");
    sessionStorage.setItem("kaayfi-pas-simuler", "1");
    sessionStorage.removeItem("kaayfi-lieu-plus-tard");
    route();
    return;
  }
  if (event.target.closest("#lieu-prox")) {
    event.preventDefault();
    sessionStorage.removeItem("kaayfi-lieu-plus-tard");
    const ask = document.querySelector("#ask-lieu");
    if (ask) {
      ask.hidden = false;
      ask.scrollIntoView({ block: "center" });
    } else {
      route();
    }
  }
});

window.addEventListener("hashchange", route);
route();
