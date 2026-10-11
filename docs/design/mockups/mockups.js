const SPRITE = `
<svg xmlns="http://www.w3.org/2000/svg" style="display:none">
  <symbol id="feather" viewBox="0 0 64 64">
    <path d="M32 6C37 16 44 26 44 40C44 48 38.6 54 32 54C25.4 54 20 48 20 40C20 26 27 16 32 6Z"/>
  </symbol>
  <symbol id="crest" viewBox="0 0 64 64">
    <g transform="rotate(-32 32 56) translate(32 56) scale(.7) translate(-32 -56)"><use href="#feather" fill="#E8894B"/></g>
    <g transform="rotate(32 32 56) translate(32 56) scale(.7) translate(-32 -56)"><use href="#feather" fill="#E8894B"/></g>
    <g transform="translate(0 2)"><use href="#feather" fill="#DE7A3E"/></g>
    <path d="M32 28C35 33 38 37 38 43C38 47 35.3 50 32 50C28.7 50 26 47 26 43C26 37 29 33 32 28Z" fill="#F2C14E"/>
  </symbol>
  <symbol id="bubble" viewBox="0 0 64 64">
    <circle cx="32" cy="27" r="21" fill="#9CC7E6" stroke="#6FAED9" stroke-width="3"/>
    <ellipse cx="24" cy="19" rx="6.5" ry="4" transform="rotate(-35 24 19)" fill="#fff" opacity=".9"/>
    <circle cx="19" cy="28" r="2.2" fill="#fff" opacity=".8"/>
    <path d="M29 47.5h6l-1 3.5h-4z" fill="#6FAED9"/>
    <ellipse cx="32" cy="55" rx="8" ry="5.5" fill="#F2A7B8"/>
    <ellipse cx="29.5" cy="53.5" rx="2.4" ry="1.4" fill="#fff" opacity=".7"/>
  </symbol>
  <symbol id="bubble-flat" viewBox="0 0 64 64">
    <ellipse cx="32" cy="38" rx="23" ry="13" fill="#9CC7E6" stroke="#6FAED9" stroke-width="3"/>
    <ellipse cx="23" cy="34" rx="5" ry="2.5" fill="#fff" opacity=".8"/>
    <ellipse cx="32" cy="56" rx="8" ry="5.5" fill="#F2A7B8"/>
  </symbol>
  <symbol id="badge" viewBox="0 0 64 64">
    <circle cx="32" cy="32" r="30" fill="#FFFDF8" stroke="#E6D9C3" stroke-width="2"/>
    <circle cx="32" cy="32" r="25" fill="#FBF6EC"/>
    <g transform="translate(4 9) scale(.62)"><use href="#crest"/></g>
    <g transform="translate(27 13) scale(.58)"><use href="#bubble"/></g>
  </symbol>
  <symbol id="ember" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5" fill="#F2C14E"/><circle cx="8" cy="8" r="2.5" fill="#DE7A3E"/></symbol>
  <symbol id="mini-bubble" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#9CC7E6" stroke="#6FAED9" stroke-width="1.5"/><circle cx="6" cy="6" r="1.6" fill="#fff"/></symbol>
  <symbol id="mini-feather" viewBox="0 0 16 16"><path d="M8 1C10 4 12 7 12 10A4 4 0 0 1 4 10C4 7 6 4 8 1Z" fill="#DE7A3E"/></symbol>
  <symbol id="i-check" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></symbol>
  <symbol id="i-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></symbol>
  <symbol id="i-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></symbol>
  <symbol id="i-x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
  <symbol id="i-left" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></symbol>
  <symbol id="i-right" viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></symbol>
  <symbol id="i-refresh" viewBox="0 0 24 24"><path d="M20 11a8 8 0 0 0-14.9-3.9M4 4v4h4M4 13a8 8 0 0 0 14.9 3.9M20 20v-4h-4"/></symbol>
</svg>`;

function icon(id, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`;
}

function topbar(active) {
  const link = (href, label, key) =>
    `<a href="${href}"${active === key ? ' aria-current="page"' : ""}>${label}</a>`;
  return `
  <header class="topbar">
    <a class="brand" href="sets.html" aria-label="TCG Pokédex, início">
      <svg aria-hidden="true"><use href="#badge"/></svg><span><b>TCG</b> Pokédex</span>
    </a>
    <label class="search">${icon("i-search")}<span class="sr-only">Buscar carta</span>
      <input type="search" placeholder="Buscar carta…"></label>
    <nav class="nav" aria-label="Principal">
      ${link("sets.html", "Coleções", "sets")}
      ${link("#", "Status", "status")}
    </nav>
  </header>`;
}

function mount(active, note) {
  document.body.insertAdjacentHTML("afterbegin", SPRITE + topbar(active));
  if (note) {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<p class="mock-note">${note} · <a href="index.html">mockups</a></p>`,
    );
  }
}

const EUR_BRL = 6.2;
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const VERSION_LABEL = { normal: "Normal", reverse: "Reverse", holo: "Holo" };
const RARITY_SYMBOL = { Comum: "●", Incomum: "◆", Rara: "★", "Rara Dupla": "★★" };

const SV09 = {
  id: "sv09",
  name: "Amigos de Jornada",
  series: "Escarlate e Violeta",
  year: 2025,
  official: 159,
  tint: "#3f9fb0",
  logo: "https://assets.tcgdex.net/pt/sv/sv09/logo.png",
  unseen: { wanted: 31, partial: 3 },
};

const CARDS = [
  ["001", "Caterpie", "Comum", "nr", 0.03, 0.11],
  ["002", "Metapod", "Comum", "nr", 0.04, 0.11],
  ["003", "Butterfree", "Rara", "rh", 0.08, 0.23],
  ["004", "Paras", "Comum", "nr", 0.03, 0.09],
  ["005", "Parasect", "Comum", "nr", 0.05, 0.09],
  ["006", "Petilil", "Comum", "nr", 0.02, 0.09],
  ["007", "Lilligant", "Comum", "nr", 0.04, 0.1],
  ["008", "Maractus", "Incomum", "nr", 0.04, 0.11],
  ["009", "Karrablast", "Comum", "nr", 0.03, 0.1],
  ["010", "Foongus", "Comum", "nr", 0.02, 0.08],
  ["011", "Amoonguss ex", "Rara Dupla", "h", 0.6, null],
  ["012", "Shelmet", "Comum", "nr", 0.02, 0.09],
  ["013", "Accelgor", "Incomum", "nr", 0.02, 0.09],
  ["014", "Durant", "Comum", "nr", 0.03, 0.07],
  ["015", "Virizion", "Incomum", "nr", 0.03, 0.29],
  ["016", "Sprigatito", "Comum", "nr", 0.03, 0.11],
  ["017", "Floragato", "Comum", "nr", 0.04, 0.12],
  ["018", "Meowscarada", "Rara", "rh", 0.06, 0.22],
  ["019", "Nymble", "Comum", "nr", 0.02, 0.07],
  ["020", "Magmar", "Comum", "nr", 0.03, 0.1],
  ["021", "Magmortar", "Rara", "rh", 0.06, 0.26],
  ["022", "Torchic", "Comum", "nr", 0.03, 0.12],
  ["023", "Combusken", "Incomum", "nr", 0.03, 0.1],
  ["024", "Blaziken ex", "Rara Dupla", "h", 2.1, null],
  ["025", "Torkoal", "Comum", "nr", 0.04, 0.09],
  ["026", "Darumaka do N", "Comum", "nr", 0.03, 0.11],
  ["027", "Darmanitan do N", "Incomum", "nrh", 0.03, 0.27],
  ["028", "Larvesta", "Comum", "nr", 0.02, 0.09],
  ["029", "Volcarona", "Incomum", "nr", 0.03, 0.07],
  ["030", "Reshiram ex", "Rara Dupla", "h", 0.67, null],
  ["031", "Volcanion ex", "Rara Dupla", "h", 0.67, null],
  ["032", "Articuno", "Incomum", "nrh", 0.04, 0.4],
  ["033", "Remoraid", "Comum", "nr", 0.02, 0.08],
  ["034", "Octillery", "Incomum", "nr", 0.02, 0.26],
  ["035", "Lotad", "Comum", "nr", 0.03, 0.1],
  ["036", "Lombre", "Comum", "nr", 0.04, 0.1],
].map(([n, name, rarity, v, p, ph]) => ({
  n,
  name,
  rarity,
  versions: [...v].map((c) => ({ n: "normal", r: "reverse", h: "holo" })[c]),
  price: { normal: p, reverse: ph ?? p, holo: ph ?? p },
  img: `https://assets.tcgdex.net/pt/sv/sv09/${n}`,
}));

const OWNED = {
  "001": { normal: 1, reverse: 1 },
  "002": { reverse: 1 },
  "003": { holo: 1 },
  "005": { normal: 1 },
  "006": { reverse: 2 },
  "008": { normal: 1, reverse: 1 },
  "009": { normal: 1 },
  "012": { reverse: 1 },
  "013": { normal: 1 },
  "015": { reverse: 1 },
  "016": { normal: 2, reverse: 1 },
  "017": { reverse: 1 },
  "019": { normal: 1 },
  "021": { reverse: 1 },
  "022": { normal: 1, reverse: 1 },
  "023": { normal: 1 },
  "024": { holo: 1 },
  "026": { reverse: 1 },
  "027": { holo: 1 },
  "029": { normal: 1 },
  "031": { holo: 1 },
  "032": { normal: 1 },
  "033": { reverse: 1 },
  "035": { normal: 1, reverse: 1 },
};

const qty = (card, v) => OWNED[card.n]?.[v] ?? 0;
const total = (card) => card.versions.reduce((s, v) => s + qty(card, v), 0);
const wantedVersions = (card) => {
  const foil = card.versions.filter((v) => v !== "normal");
  return foil.length ? foil : card.versions;
};
const hasWanted = (card) => wantedVersions(card).some((v) => qty(card, v) > 0);
const bestOwned = (card) => ["holo", "reverse", "normal"].find((v) => qty(card, v) > 0) ?? null;
const cardState = (card) => (total(card) === 0 ? "missing" : hasWanted(card) ? "owned" : "pending");
const pendingLabel = (card) => wantedVersions(card).map((v) => VERSION_LABEL[v]).join("/");
const priceOf = (card, v) => brl.format(card.price[v] * EUR_BRL);

function progress() {
  let wanted = SV09.unseen.wanted;
  let partial = SV09.unseen.partial;
  for (const c of CARDS) {
    const s = cardState(c);
    if (s === "owned") wanted += 1;
    if (s === "pending") partial += 1;
  }
  return { wanted, partial, total: SV09.official };
}

function spineHTML({ wanted, partial, total }, { label = true } = {}) {
  const pw = (wanted / total) * 100;
  const pp = (partial / total) * 100;
  const complete = wanted === total;
  const text = `<strong>${wanted + partial}</strong> de ${total}${partial ? ` · ${partial} só normal` : ""}`;
  return `
    <div class="spine">
      <div class="spine-track" role="img" aria-label="${wanted + partial} de ${total} cartas possuídas, ${partial} só na versão normal">
        <div class="spine-deep" style="width:${pw}%"></div>
        <div class="spine-partial" style="width:${pp}%"></div>
      </div>
      ${complete ? `<svg class="spine-cap" aria-hidden="true"><use href="#badge"/></svg>` : ""}
      ${label ? `<span class="spine-label">${text}</span>` : ""}
    </div>`;
}

function initSetPage() {
  mount("sets", "Mockup: data is fictional · click a card, its sticker, or the filters");
  const root = document.querySelector("main");
  document.documentElement.style.setProperty("--tint", SV09.tint);

  root.innerHTML = `
    <section class="set-header" aria-label="Coleção">
      <div class="set-head-top">
        <img src="${SV09.logo}" alt="${SV09.name}">
        <div>
          <h1>${SV09.name}</h1>
          <div class="meta">${SV09.series} · ${SV09.year} · ${SV09.official} cartas</div>
        </div>
        <div id="spine" style="flex:1;max-width:520px;margin-left:auto"></div>
      </div>
      <div class="filters" role="toolbar" aria-label="Filtros">
        <button class="chip" data-f="all" aria-pressed="true">Todas <span class="count"></span></button>
        <button class="chip" data-f="owned" aria-pressed="false">Possuídas <span class="count"></span></button>
        <button class="chip" data-f="missing" aria-pressed="false">Faltando <span class="count"></span></button>
        <button class="chip" data-f="pending" aria-pressed="false">Versão pendente <span class="count"></span></button>
        <select class="select" aria-label="Raridade">
          <option value="">Raridade</option><option>Comum</option><option>Incomum</option><option>Rara</option><option>Rara Dupla</option>
        </select>
        <select class="select" aria-label="Versão"><option>Versão</option><option>Normal</option><option>Reverse</option><option>Holo</option></select>
        <span class="grow"></span>
        <label class="search">${icon("i-search")}<span class="sr-only">Buscar nesta coleção</span><input type="search" id="q" placeholder="Buscar nesta coleção"></label>
        <label class="switch"><input type="checkbox" id="prices"> Mostrar preços</label>
      </div>
    </section>
    <section class="binder-page" aria-label="Cartas">
      <div class="grid" id="grid"></div>
      <p class="grid-foot">Mockup mostra 001–036 de ${SV09.official} · cartas restantes omitidas</p>
    </section>`;

  root.insertAdjacentHTML(
    "afterend",
    `<div class="scrim" id="scrim"></div>
     <aside class="panel" id="panel" aria-label="Detalhes da carta" aria-hidden="true"></aside>`,
  );

  const state = { filter: "all", rarity: "", q: "", prices: false, open: null };
  const grid = document.getElementById("grid");

  const visible = () =>
    CARDS.filter((c) => {
      const s = cardState(c);
      if (state.filter === "owned" && s === "missing") return false;
      if (state.filter === "missing" && s !== "missing") return false;
      if (state.filter === "pending" && s !== "pending") return false;
      if (state.rarity && c.rarity !== state.rarity) return false;
      const q = state.q.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
      const nm = c.name.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
      return !q || nm.includes(q) || c.n.includes(q);
    });

  function tileHTML(c) {
    const s = cardState(c);
    const best = bestOwned(c);
    const dots = c.versions
      .map((v) => `<span class="dot${qty(c, v) ? " on" : ""}" title="${VERSION_LABEL[v]}: ${qty(c, v)}"></span>`)
      .join("");
    const dup = total(c) > 1 ? `<span class="dup">×${total(c)}</span>` : "";
    const versionsLabel = c.versions.map((v) => `${VERSION_LABEL[v]}: ${qty(c, v)}`).join(", ");
    const stateLabel = { missing: "faltando", pending: `possuída, falta ${pendingLabel(c)}`, owned: "possuída" }[s];
    const foil = best && best !== "normal" ? `<span class="foil ${best}"></span>` : "";
    const priceV = best ?? wantedVersions(c)[0];
    return `
      <div class="tile" data-n="${c.n}">
        <div style="position:relative">
          <div class="sleeve ${s === "missing" ? "missing" : ""}" role="button" tabindex="0" data-open="${c.n}"
               aria-label="${c.name}, ${SV09.name}, ${c.n}/${SV09.official}, ${stateLabel}">
            <div class="card-face">
              <img src="${c.img}/low.webp" alt="" loading="lazy">
              ${foil}
            </div>
            ${s === "missing" ? `<span class="empty-label"><span class="n">${c.n}</span><span class="nm">${c.name}</span></span>` : ""}
          </div>
          ${s === "pending" ? `<span class="ribbon">${pendingLabel(c)}</span>` : ""}
          <button class="sticker ${s === "missing" ? "" : "on"}" data-toggle="${c.n}"
                  aria-pressed="${s !== "missing"}" aria-label="Possuída: ${c.name}">
            ${icon(s === "missing" ? "i-plus" : "i-check", "")}
          </button>
        </div>
        <div class="tile-meta">
          <span class="no">${c.n}/${SV09.official}</span>
          <span class="vs" aria-label="${versionsLabel}">${dots}${dup}</span>
          <span class="nm" title="${c.name}">${c.name}</span>
          ${state.prices ? `<span class="price-line">≈ ${priceOf(c, priceV)}</span>` : ""}
        </div>
      </div>`;
  }

  function renderCounts() {
    const counts = { all: CARDS.length, owned: 0, missing: 0, pending: 0 };
    for (const c of CARDS) {
      const s = cardState(c);
      if (s === "missing") counts.missing += 1;
      else counts.owned += 1;
      if (s === "pending") counts.pending += 1;
    }
    document.querySelectorAll(".chip").forEach((ch) => {
      ch.querySelector(".count").textContent = counts[ch.dataset.f];
      ch.setAttribute("aria-pressed", String(ch.dataset.f === state.filter));
    });
    document.getElementById("spine").innerHTML = spineHTML(progress());
  }

  function render() {
    grid.innerHTML = visible().map(tileHTML).join("");
    renderCounts();
  }

  function puff(tile) {
    const host = tile.querySelector("div");
    const p = document.createElement("span");
    p.className = "puff";
    const kinds = ["mini-feather", "mini-bubble", "ember", "mini-bubble", "mini-feather"];
    p.innerHTML = kinds
      .map((k, i) => {
        const a = -150 + i * 30;
        const dx = Math.cos((a * Math.PI) / 180) * 34;
        const dy = Math.sin((a * Math.PI) / 180) * 34 - 6;
        return `<svg style="--dx:${dx}px;--dy:${dy}px;animation-delay:${i * 30}ms"><use href="#${k}"/></svg>`;
      })
      .join("");
    host.appendChild(p);
    setTimeout(() => p.remove(), 900);
  }

  function toggle(n) {
    const c = CARDS.find((x) => x.n === n);
    if (total(c) > 0) {
      delete OWNED[n];
    } else {
      OWNED[n] = { [c.versions.includes("normal") ? "normal" : c.versions[0]]: 1 };
    }
    const owned = total(c) > 0;
    const old = grid.querySelector(`[data-n="${n}"]`);
    old.outerHTML = tileHTML(c);
    const tile = grid.querySelector(`[data-n="${n}"]`);
    if (owned) {
      tile.querySelector(".sleeve").classList.add("slide-in");
      puff(tile);
    }
    tile.querySelector(".sticker").focus();
    renderCounts();
    if (state.open === n) renderPanel();
  }

  const panel = document.getElementById("panel");
  const scrim = document.getElementById("scrim");

  function renderPanel() {
    const list = visible();
    const c = CARDS.find((x) => x.n === state.open);
    const s = cardState(c);
    const best = bestOwned(c);
    const i = list.findIndex((x) => x.n === c.n);
    const foil = best && best !== "normal" ? `<span class="foil ${best}" id="bigfoil"></span>` : "";
    panel.innerHTML = `
      <div class="panel-head">
        <span class="meta">${SV09.name} · ${c.n}/${SV09.official}</span>
        <button class="icon-btn" id="close" aria-label="Fechar">${icon("i-x")}</button>
      </div>
      <div class="panel-body">
        <div class="stage">
          <div class="big-card ${s === "missing" ? "missing" : ""}" id="big">
            <img src="${c.img}/high.webp" alt="${c.name}, ${SV09.name}, ${c.n}/${SV09.official}">
            ${foil}<span class="glare"></span>
          </div>
          ${s === "missing" ? `<p class="missing-note">Ainda não possuída</p>` : ""}
        </div>
        <div class="detail-title"><h2>${c.name}</h2></div>
        <div class="facts">
          <span><span class="rarity-sym" aria-hidden="true">${RARITY_SYMBOL[c.rarity] ?? "●"}</span>${c.rarity}</span>
          <span>${c.n}/${SV09.official}</span>
          <span>${c.versions.map((v) => VERSION_LABEL[v]).join(" · ")}</span>
        </div>
        ${s === "pending" ? `<div class="pending-note">Versão pendente: ${pendingLabel(c)}</div>` : ""}
        <div class="versions">
          ${c.versions
            .map(
              (v) => `
            <div class="version">
              <span class="vname"><span class="dot${qty(c, v) ? " on" : ""}"></span>${VERSION_LABEL[v]}</span>
              <span class="vprice">≈ ${priceOf(c, v)}</span>
              <span class="stepper" role="group" aria-label="Quantidade ${VERSION_LABEL[v]}">
                <button data-step="-1" data-v="${v}" aria-label="Remover uma ${VERSION_LABEL[v]}" ${qty(c, v) ? "" : "disabled"}>−</button>
                <output aria-live="polite">${qty(c, v)}</output>
                <button data-step="1" data-v="${v}" aria-label="Adicionar uma ${VERSION_LABEL[v]}">+</button>
              </span>
            </div>`,
            )
            .join("")}
        </div>
        <p class="source">Preços: Cardmarket, convertido em 10/10/2026</p>
      </div>
      <div class="panel-foot">
        <button class="btn" id="prev" ${i <= 0 ? "disabled" : ""}>${icon("i-left")} Anterior</button>
        <button class="btn" id="next" ${i >= list.length - 1 ? "disabled" : ""}>Próxima ${icon("i-right")}</button>
      </div>`;

    const big = document.getElementById("big");
    const bigfoil = document.getElementById("bigfoil");
    big.addEventListener("pointermove", (e) => {
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const r = big.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      big.style.setProperty("--ry", `${(x - 0.5) * 16}deg`);
      big.style.setProperty("--rx", `${(0.5 - y) * 16}deg`);
      big.style.setProperty("--gx", `${x * 100}%`);
      big.style.setProperty("--gy", `${y * 100}%`);
      if (bigfoil) {
        bigfoil.style.setProperty("--mx", `${x * 100}%`);
        bigfoil.style.setProperty("--my", `${y * 100}%`);
      }
    });
    big.addEventListener("pointerleave", () => {
      big.style.setProperty("--rx", "0deg");
      big.style.setProperty("--ry", "0deg");
    });
    document.getElementById("close").onclick = () => closePanel();
    document.getElementById("prev").onclick = () => openPanel(list[i - 1].n);
    document.getElementById("next").onclick = () => openPanel(list[i + 1].n);
    panel.querySelectorAll("[data-step]").forEach((b) => {
      b.onclick = () => {
        const v = b.dataset.v;
        const next = Math.max(0, qty(c, v) + Number(b.dataset.step));
        OWNED[c.n] = { ...(OWNED[c.n] ?? {}), [v]: next };
        if (total(c) === 0) delete OWNED[c.n];
        grid.querySelector(`[data-n="${c.n}"]`).outerHTML = tileHTML(c);
        renderCounts();
        renderPanel();
        panel.querySelector(`[data-v="${v}"][data-step="${b.dataset.step}"]`)?.focus();
      };
    });
  }

  function openPanel(n, push = true) {
    state.open = n;
    renderPanel();
    panel.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    scrim.classList.add("open");
    if (push) history.pushState({ card: n }, "", `?card=${n}`);
    document.getElementById("close").focus();
  }

  function closePanel(push = true) {
    const n = state.open;
    state.open = null;
    panel.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
    scrim.classList.remove("open");
    if (push) history.pushState({}, "", location.pathname);
    grid.querySelector(`[data-open="${n}"]`)?.focus();
  }

  scrim.onclick = () => closePanel();
  addEventListener("popstate", () => {
    const n = new URLSearchParams(location.search).get("card");
    if (n) openPanel(n, false);
    else if (state.open) closePanel(false);
  });

  grid.addEventListener("click", (e) => {
    const t = e.target.closest("[data-toggle]");
    if (t) return toggle(t.dataset.toggle);
    const o = e.target.closest("[data-open]");
    if (o) openPanel(o.dataset.open);
  });
  grid.addEventListener("keydown", (e) => {
    const o = e.target.closest("[data-open]");
    if (!o) return;
    if (e.key === "Enter") openPanel(o.dataset.open);
    if (e.key === " ") {
      e.preventDefault();
      toggle(o.dataset.open);
      grid.querySelector(`[data-open="${o.dataset.open}"]`).focus();
    }
  });
  addEventListener("keydown", (e) => {
    if (!state.open) return;
    if (e.key === "Escape") closePanel();
    if (e.key === "ArrowRight") document.getElementById("next")?.click();
    if (e.key === "ArrowLeft") document.getElementById("prev")?.click();
  });

  document.querySelectorAll(".chip").forEach((ch) => {
    ch.onclick = () => {
      state.filter = ch.dataset.f;
      render();
    };
  });
  document.querySelector('.select[aria-label="Raridade"]').onchange = (e) => {
    state.rarity = e.target.value;
    render();
  };
  document.getElementById("q").oninput = (e) => {
    state.q = e.target.value;
    render();
  };
  document.getElementById("prices").onchange = (e) => {
    state.prices = e.target.checked;
    render();
  };

  render();
  const pre = new URLSearchParams(location.search).get("card");
  if (pre) openPanel(pre, false);
}

const TRACKED = [
  { ...SV09, cover: true },
  {
    id: "me05",
    name: "Escuridão Absoluta",
    series: "Megaevolução",
    year: 2026,
    official: 84,
    tint: "#6b4a8a",
    logo: "https://assets.tcgdex.net/pt/me/me05/logo.png",
    p: { wanted: 52, partial: 6 },
  },
  {
    id: "sv08.5",
    name: "Evoluções Prismáticas",
    series: "Escarlate e Violeta",
    year: 2025,
    official: 131,
    tint: "#d07ab0",
    logo: "https://assets.tcgdex.net/pt/sv/sv08.5/logo.png",
    p: { wanted: 131, partial: 0 },
  },
  {
    id: "sv08",
    name: "Fagulhas Impetuosas",
    series: "Escarlate e Violeta",
    year: 2024,
    official: 191,
    tint: "#e0a43a",
    logo: null,
    p: { wanted: 18, partial: 2 },
  },
];

const CATALOG = [
  {
    series: "Megaevolução",
    sets: [
      ["me05", "Escuridão Absoluta", 2026, 120, "https://assets.tcgdex.net/univ/me/me05/symbol.png"],
      ["me04", "Caos Ascendente", 2026, 122, "https://assets.tcgdex.net/univ/me/me04/symbol.png"],
      ["me03", "Equilíbrio Perfeito", 2026, 124, "https://assets.tcgdex.net/univ/me/me03/symbol.png"],
      ["me02.5", "Heróis Excelsos", 2026, 295, "https://assets.tcgdex.net/univ/me/me02.5/symbol.png"],
      ["me02", "Fogo Fantasmagórico", 2025, 130, null],
      ["me01", "Megaevolução", 2025, 188, "https://assets.tcgdex.net/univ/me/me01/symbol.png"],
    ],
  },
  {
    series: "Escarlate e Violeta",
    sets: [
      ["sv10.5b", "Raio Preto", 2025, 172, null],
      ["sv10.5w", "Fogo Branco", 2025, 173, null],
      ["sv10", "Rivais Predestinados", 2025, 244, null],
      ["sv09", "Amigos de Jornada", 2025, 190, null],
      ["sv08.5", "Evoluções Prismáticas", 2025, 180, null],
      ["sv08", "Fagulhas Impetuosas", 2024, 252, null],
    ],
  },
];

function initSetsPage() {
  mount("sets", "Mockup: tracked sets and progress are fictional");
  const trackedIds = new Set(TRACKED.map((t) => t.id));
  const covers = TRACKED.map((t) => {
    const p = t.cover ? progress() : { ...t.p, total: t.official };
    const complete = p.wanted === p.total;
    const art = t.logo
      ? `<img src="${t.logo}" alt="">`
      : `<span class="logo-fallback">${t.name}</span>`;
    return `
      <a class="cover" href="${t.cover ? "set.html" : "#"}" style="--tint:${t.tint}" aria-label="${t.name}">
        <div class="cover-art">${art}<span class="ruff-edge"></span>
          ${complete ? `<span class="complete-chip"><svg aria-hidden="true"><use href="#badge"/></svg>Coleção completa</span>` : ""}</div>
        <div class="cover-body">
          <div class="cover-title">
            <div><h3>${t.name}</h3><div class="meta">${t.series} · ${t.year} · ${t.official} cartas</div></div>
          </div>
          ${spineHTML(p)}
        </div>
      </a>`;
  }).join("");

  const rows = CATALOG.map(
    (g) => `
    <section class="series" aria-labelledby="s-${g.series}">
      <h2 class="section-title" id="s-${g.series}">${g.series}</h2>
      <div class="rows">
        ${g.sets
          .map(([id, name, year, count, sym]) => {
            const tracked = trackedIds.has(id);
            return `
          <div class="row">
            <span class="sym">${sym ? `<img src="${sym}" alt="" onerror="this.replaceWith('${id.toUpperCase()}')">` : id.toUpperCase()}</span>
            <span class="name">${name}</span>
            <span class="meta">${year}</span>
            <span class="meta">${count} cartas</span>
            <button class="btn ${tracked ? "btn-tracked" : ""}" aria-pressed="${tracked}" data-track>
              ${tracked ? `${icon("i-check")} Acompanhando` : `${icon("i-plus")} Acompanhar`}
            </button>
          </div>`;
          })
          .join("")}
      </div>
    </section>`,
  ).join("");

  document.querySelector("main").innerHTML = `
    <h1 style="font:600 36px/40px var(--font-display);margin-bottom:24px">Coleções</h1>
    <h2 class="section-title">Acompanhando <small>${TRACKED.length} coleções</small></h2>
    <div class="ruff-divider"></div>
    <div class="covers">${covers}</div>
    <h2 class="section-title">Todas as coleções</h2>
    <div class="ruff-divider"></div>
    ${rows}`;

  document.querySelectorAll("[data-track]").forEach((b) => {
    b.onclick = () => {
      const on = b.getAttribute("aria-pressed") !== "true";
      b.setAttribute("aria-pressed", String(on));
      b.classList.toggle("btn-tracked", on);
      b.innerHTML = on ? `${icon("i-check")} Acompanhando` : `${icon("i-plus")} Acompanhar`;
    };
  });
}

function initStatic(active, note) {
  mount(active, note);
}

const page = document.body.dataset.page;
if (page === "set") initSetPage();
else if (page === "sets") initSetsPage();
else initStatic(document.body.dataset.active ?? "", document.body.dataset.note ?? "");
