"use strict";

// Stockage local (favoris, cartes lues) : protégé car indisponible en navigation privée
const store = {
  get(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignoré */ }
  },
};

const state = {
  editions: [],
  edition: null,
  filter: store.get("filter", "all"),
  favs: store.get("favs", {}),          // id -> carte complète (survit aux éditions)
  read: new Set(store.get("read", [])),
};

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const FALLBACK_DOMAIN = { label: "Autre", emoji: "🔬", color: "#64748b" };
const domainOf = (id) => (state.edition?.domains || []).find((d) => d.id === id) || FALLBACK_DOMAIN;

function fmtDate(iso) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

function fmtEdition(iso, i) {
  const d = new Date(iso + "T12:00:00");
  const label = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" });
  return i === 0 ? `${label} · dernière` : label;
}

// Petit générateur pseudo-aléatoire déterministe : chaque papier a toujours la même couverture
function seeded(str) {
  let h = 2166136261;
  for (const c of str) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507), h ^= h >>> 13, (h >>> 0) / 4294967296));
}

// Couverture générée pour les papiers (pas d'image disponible) : un motif "molécule" aux couleurs du domaine
function generatedCover(item, dom) {
  const rnd = seeded(item.id);
  const nodes = Array.from({ length: 9 }, () => [rnd() * 320, rnd() * 180, 3 + rnd() * 7]);
  const links = [];
  nodes.forEach((a, i) => nodes.forEach((b, j) => {
    if (j > i && Math.hypot(a[0] - b[0], a[1] - b[1]) < 110) links.push([a, b]);
  }));
  const angle = Math.floor(rnd() * 360);
  return `
    <div class="media gen" style="background:linear-gradient(${angle}deg, ${dom.color}, color-mix(in srgb, ${dom.color} 45%, #0b1020))">
      <svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        ${links.map(([a, b]) => `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="#fff" stroke-opacity=".25" stroke-width="1.5"/>`).join("")}
        ${nodes.map(([x, y, r]) => `<circle cx="${x}" cy="${y}" r="${r}" fill="#fff" fill-opacity=".35"/>`).join("")}
      </svg>
      <span class="big" aria-hidden="true">${dom.emoji}</span>
      <span class="journal">${esc(item.source)}</span>
    </div>`;
}

function cardHTML(item) {
  const dom = domainOf(item.domain);
  const isFav = Boolean(state.favs[item.id]);
  const media = item.image
    ? `<div class="media"><img src="${esc(item.image)}" alt="" loading="lazy" referrerpolicy="no-referrer" data-fallback="1"></div>`
    : generatedCover(item, dom);
  const kind = item.kind === "paper" ? "Papier" : "Vulgarisation";
  const tags = (item.tags || []).filter((t) => t !== "Vulgarisation");
  return `
  <article class="card ${state.read.has(item.id) ? "read" : ""}" data-id="${esc(item.id)}">
    <a class="cover-link" href="${esc(item.url)}" target="_blank" rel="noopener">
      ${media}
      <div class="body">
        <div class="meta">
          <span class="dom"><span class="dot" style="background:${dom.color}"></span>${esc(dom.label)}</span>
          <span>·</span><span class="kind">${kind}</span>
          ${item.kind !== "paper" ? `<span>·</span><span>${esc(item.source)}</span>` : ""}
        </div>
        <h2>${esc(item.title)}</h2>
        ${item.summary ? `<p>${esc(item.summary)}</p>` : ""}
        ${tags.length ? `<div class="tags">${tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
      </div>
    </a>
    <div class="actions">
      <span class="date">${fmtDate(item.date)}</span>
      <div class="right">
        ${item.oa ? `<a class="oa" href="${esc(item.oa.url)}" target="_blank" rel="noopener">🔓 ${esc(item.oa.label)}</a>` : ""}
        <button class="star" type="button" aria-pressed="${isFav}" aria-label="${isFav ? "Retirer des favoris" : "Garder pour plus tard"}">${isFav ? "★" : "☆"}</button>
      </div>
    </div>
  </article>`;
}

function renderFilters() {
  const items = state.edition?.items || [];
  const counts = {};
  items.forEach((it) => (counts[it.domain] = (counts[it.domain] || 0) + 1));
  const favCount = Object.keys(state.favs).length;
  const chips = [
    { id: "all", label: "Tout", n: items.length },
    { id: "favs", label: "★ À lire", n: favCount },
    ...(state.edition?.domains || []).filter((d) => counts[d.id]).map((d) => ({ id: d.id, label: `${d.emoji} ${d.label}`, n: counts[d.id] })),
  ];
  if (!chips.some((c) => c.id === state.filter)) state.filter = "all";
  $("#filters").innerHTML = chips.map((c) =>
    `<button class="chip" type="button" data-filter="${c.id}" aria-pressed="${c.id === state.filter}">${esc(c.label)}<span class="n">${c.n}</span></button>`
  ).join("");
}

function renderFeed() {
  const feed = $("#feed");
  const items = state.edition?.items || [];
  let html = "";
  if (state.filter === "favs") {
    const favs = Object.values(state.favs).sort((a, b) => (b.savedAt || "").localeCompare(a.savedAt || ""));
    html = favs.length ? favs.map(cardHTML).join("") : `<p class="empty">Aucun favori. Touche ☆ sur une carte pour la garder ici.</p>`;
  } else if (state.filter === "all") {
    const main = items.filter((it) => it.domain !== "exotique");
    const exotic = items.filter((it) => it.domain === "exotique");
    html = main.map(cardHTML).join("");
    if (exotic.length) html += `<h3 class="section-title">🧭 Hors des sentiers battus</h3>` + exotic.map(cardHTML).join("");
  } else {
    html = items.filter((it) => it.domain === state.filter).map(cardHTML).join("");
  }
  feed.innerHTML = html || `<p class="empty">Rien ici pour cette édition.</p>`;
  feed.querySelectorAll("img[data-fallback]").forEach((img) =>
    img.addEventListener("error", () => {
      const card = img.closest(".card");
      const item = findItem(card.dataset.id);
      img.parentElement.outerHTML = generatedCover(item, domainOf(item.domain));
    }, { once: true }));
  renderProgress();
}

function renderProgress() {
  const items = state.edition?.items || [];
  const n = items.filter((it) => state.read.has(it.id)).length;
  $("#progress").textContent = items.length ? `${n}/${items.length} lues` : "";
}

function findItem(id) {
  return (state.edition?.items || []).find((it) => it.id === id) || state.favs[id];
}

async function loadEdition(date) {
  const res = await fetch(`data/editions/${date}.json`, { cache: "no-cache" });
  if (!res.ok) throw new Error(res.status);
  state.edition = await res.json();
  renderFilters();
  renderFeed();
  window.scrollTo({ top: 0 });
}

async function init() {
  try {
    const res = await fetch("data/index.json", { cache: "no-cache" });
    state.editions = (await res.json()).editions || [];
  } catch {
    state.editions = [];
  }
  const sel = $("#edition");
  sel.innerHTML = state.editions.map((e, i) => `<option value="${e}">${fmtEdition(e, i)}</option>`).join("");
  if (!state.editions.length) {
    $("#feed").innerHTML = `<p class="empty">Pas encore d'édition. La première arrive à la prochaine collecte.</p>`;
    return;
  }
  await loadEdition(state.editions[0]).catch(() => {
    $("#feed").innerHTML = `<p class="empty">Impossible de charger l'édition (hors ligne ?).</p>`;
  });
}

// ---- interactions
$("#edition").addEventListener("change", (e) => loadEdition(e.target.value));

$("#filters").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  state.filter = chip.dataset.filter;
  store.set("filter", state.filter);
  $("#filters").querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", c === chip));
  renderFeed();
});

$("#feed").addEventListener("click", (e) => {
  const card = e.target.closest(".card");
  if (!card) return;
  const id = card.dataset.id;
  if (e.target.closest(".star")) {
    if (state.favs[id]) delete state.favs[id];
    else state.favs[id] = { ...findItem(id), savedAt: new Date().toISOString() };
    store.set("favs", state.favs);
    renderFilters();
    if (state.filter === "favs") renderFeed();
    else {
      const btn = e.target.closest(".star"), on = Boolean(state.favs[id]);
      btn.setAttribute("aria-pressed", on);
      btn.setAttribute("aria-label", on ? "Retirer des favoris" : "Garder pour plus tard");
      btn.textContent = on ? "★" : "☆";
    }
    return;
  }
  if (e.target.closest("a")) {  // ouverture de l'article ou du texte intégral -> marquée comme lue
    state.read.add(id);
    store.set("read", [...state.read].slice(-3000));
    card.classList.add("read");
    renderProgress();
  }
});

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}

init();
