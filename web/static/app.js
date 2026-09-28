"use strict";

const STORE_COLORS = {
  Auchan: "var(--auchan)",
  Lidl: "var(--lidl)",
  Kaufland: "var(--kaufland)",
};

const state = {
  products: [],
  settings: null,
  report: null,
  editingId: null,
  selectedLidl: new Map(),
  lidlCandidates: [],
  polling: null,
};

// ============================================================
// HELPERS
// ============================================================

const $ = (selector, root = document) => root.querySelector(selector);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function lei(value) {
  return value == null ? "–" : `${Number(value).toFixed(2)} lei`;
}

function storeStyle(store) {
  return `style="--store:${STORE_COLORS[store] || "var(--text)"}"`;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 2600);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error((data && data.error) || `Request failed (${response.status})`);
  }

  return data;
}

function formatDate(isoText) {
  const date = new Date(isoText);
  return date.toLocaleString(undefined, {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

// ============================================================
// NAVIGATION
// ============================================================

function showView(name) {
  document.querySelectorAll(".tab").forEach((tab) =>
    tab.classList.toggle("active", tab.dataset.view === name));
  document.querySelectorAll(".view").forEach((view) =>
    view.classList.toggle("active", view.id === `view-${name}`));
  try { localStorage.setItem("view", name); } catch { /* storage unavailable */ }
}

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => showView(tab.dataset.view)));

document.addEventListener("click", (event) => {
  const link = event.target.closest("[data-goto]");
  if (!link) return;
  event.preventDefault();
  showView(link.dataset.goto);
});

// ============================================================
// MY PRODUCTS
// ============================================================

function renderProducts() {
  const filter = $("#product-filter").value.trim().toLowerCase();
  const container = $("#product-groups");

  const visible = state.products.filter((product) =>
    !filter
    || product.label.toLowerCase().includes(filter)
    || product.category.toLowerCase().includes(filter)
    || product.search_term.toLowerCase().includes(filter));

  if (!state.products.length) {
    container.innerHTML = `<div class="empty">No products yet. Add the products you buy regularly with <strong>+ Add product</strong>.</div>`;
    return;
  }

  if (!visible.length) {
    container.innerHTML = `<div class="empty">No products match “${esc(filter)}”.</div>`;
    return;
  }

  const byCategory = {};
  visible.forEach((product) => {
    (byCategory[product.category || "Other"] ||= []).push(product);
  });

  container.innerHTML = Object.keys(byCategory).sort().map((category) => `
    <div class="category">
      <h2>${esc(category)}</h2>
      <div class="grid">
        ${byCategory[category].sort((a, b) => a.label.localeCompare(b.label)).map((product) => `
          <div class="product-card ${product.in_shopping_list ? "in-list" : ""}"
               role="button" tabindex="0" data-id="${product.id}"
               aria-pressed="${product.in_shopping_list}">
            <div class="name">${esc(product.label)}</div>
            <div class="term">“${esc(product.search_term)}”</div>
            <div class="state">${product.in_shopping_list ? "✓ In shopping list" : "Tap when you run out"}</div>
            <button class="icon-btn edit" data-edit="${product.id}" title="Edit product" aria-label="Edit ${esc(product.label)}">✎</button>
          </div>`).join("")}
      </div>
    </div>`).join("");

  const categories = [...new Set(state.products.map((product) => product.category))].sort();
  $("#category-options").innerHTML = categories.map((c) => `<option value="${esc(c)}">`).join("");
}

async function toggleInList(productId) {
  const product = state.products.find((p) => p.id === productId);
  if (!product) return;

  const inList = !product.in_shopping_list;
  state.products = await api("/api/shopping-list", {
    method: "POST",
    body: { ids: [productId], in_list: inList },
  });

  renderAll();
  toast(inList ? `${product.label} added to your shopping list` : `${product.label} removed from the list`);
}

$("#product-groups").addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit]");
  if (editButton) {
    event.stopPropagation();
    openEditor(editButton.dataset.edit);
    return;
  }

  const card = event.target.closest(".product-card");
  if (card) toggleInList(card.dataset.id).catch((error) => toast(error.message));
});

$("#product-groups").addEventListener("keydown", (event) => {
  const card = event.target.closest(".product-card");
  if (card && (event.key === "Enter" || event.key === " ") && event.target === card) {
    event.preventDefault();
    toggleInList(card.dataset.id).catch((error) => toast(error.message));
  }
});

$("#product-filter").addEventListener("input", renderProducts);

// ============================================================
// PRODUCT EDITOR
// ============================================================

const dialog = $("#product-dialog");
const form = $("#product-form");

function openEditor(productId = null) {
  state.editingId = productId;
  const product = state.products.find((p) => p.id === productId);

  form.reset();
  $("#preview").classList.add("hidden");
  $("#dialog-title").textContent = product ? "Edit product" : "Add product";
  $("#delete-product").classList.toggle("hidden", !product);
  $("#add-to-list-row").classList.toggle("hidden", Boolean(product));

  if (product) {
    form.label.value = product.label;
    form.category.value = product.category;
    form.search_term.value = product.search_term;
    form.required_words.value = product.required_words.join(", ");
    form.excluded_words.value = (product.excluded_words || []).join(", ");
    form.match_start.checked = Boolean(product.match_start);
  }

  dialog.showModal();
  form.label.focus();
}

function formPayload() {
  return {
    label: form.label.value,
    category: form.category.value || "Other",
    search_term: form.search_term.value,
    required_words: form.required_words.value,
    excluded_words: form.excluded_words.value,
    match_start: form.match_start.checked,
    in_shopping_list: form.in_shopping_list.checked,
  };
}

$("#add-product").addEventListener("click", () => openEditor());
dialog.querySelectorAll("[data-close]").forEach((button) =>
  button.addEventListener("click", () => dialog.close()));

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    if (state.editingId) {
      await api(`/api/products/${state.editingId}`, { method: "PUT", body: formPayload() });
      toast("Product saved");
    } else {
      await api("/api/products", { method: "POST", body: formPayload() });
      toast("Product added");
    }

    dialog.close();
    await loadProducts();
  } catch (error) {
    toast(error.message);
  }
});

$("#delete-product").addEventListener("click", async () => {
  const product = state.products.find((p) => p.id === state.editingId);
  if (!product || !confirm(`Delete “${product.label}”?`)) return;

  await api(`/api/products/${product.id}`, { method: "DELETE" });
  dialog.close();
  toast("Product deleted");
  await loadProducts();
});

$("#preview-product").addEventListener("click", async () => {
  const button = $("#preview-product");
  const preview = $("#preview");

  button.disabled = true;
  button.textContent = "Searching…";
  preview.classList.remove("hidden");
  preview.innerHTML = `<p class="muted">Searching Auchan, Lidl and Kaufland…</p>`;

  try {
    const report = await api("/api/products/preview", { method: "POST", body: formPayload() });
    const item = report.items[0];

    preview.innerHTML = `
      <strong>${item.found} matching products.</strong>
      ${item.best ? ` Cheapest: <span class="store-tag" ${storeStyle(item.best.store)}>${esc(item.best.store)}</span> ${esc(item.best.name)} (${priceText(item.best, item.compare_unit)})` : ""}
      <p class="muted">Check that these are the right products; add wrong words to “Exclude”.</p>
      ${report.stores.map((store) => {
        const matches = item.products.filter((p) => p.store === store);
        return `<h4 class="store-tag" ${storeStyle(store)}>${esc(store)} (${item.per_store[store].count})</h4>
          ${matches.length
            ? `<ul>${matches.map((p) => `<li>${esc(p.name)} · ${priceText(p, item.compare_unit)}${promoBadges(p)}${branchLine(p)}</li>`).join("")}</ul>`
            : `<p class="muted">No matches.</p>`}`;
      }).join("")}
      ${errorList(report.errors)}`;
  } catch (error) {
    preview.innerHTML = `<p>${esc(error.message)}</p>`;
  } finally {
    button.disabled = false;
    button.textContent = "Test search";
  }
});

// ============================================================
// SHOPPING LIST
// ============================================================

function renderShoppingList() {
  const inList = state.products.filter((p) => p.in_shopping_list);
  const count = $("#list-count");

  count.textContent = inList.length;
  count.classList.toggle("zero", inList.length === 0);

  $("#list-subtitle").textContent = inList.length
    ? `${inList.length} product${inList.length === 1 ? "" : "s"} to buy. Tap ✓ when bought.`
    : "Empty. Go to My products and tap the products you ran out of.";

  $("#search-markets").disabled = inList.length === 0 || Boolean(state.polling);
  $("#clear-list").classList.toggle("hidden", inList.length === 0);

  $("#shopping-items").innerHTML = inList
    .sort((a, b) => (a.added_to_list_at || "").localeCompare(b.added_to_list_at || ""))
    .map((product) => `
      <span class="chip">${esc(product.label)}
        <button data-bought="${product.id}" title="Bought / remove from list">✓ bought</button>
      </span>`).join("");
}

$("#shopping-items").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-bought]");
  if (!button) return;

  state.products = await api("/api/shopping-list", {
    method: "POST",
    body: { ids: [button.dataset.bought], in_list: false },
  });
  renderAll();
});

$("#clear-list").addEventListener("click", async () => {
  if (!confirm("Remove everything from the shopping list?")) return;

  const ids = state.products.filter((p) => p.in_shopping_list).map((p) => p.id);
  state.products = await api("/api/shopping-list", { method: "POST", body: { ids, in_list: false } });
  renderAll();
});

$("#search-markets").addEventListener("click", async () => {
  try {
    await api("/api/search", { method: "POST" });
    startPolling();
  } catch (error) {
    toast(error.message);
  }
});

function startPolling() {
  $("#progress").classList.remove("hidden");
  $("#search-markets").disabled = true;
  $("#search-markets").textContent = "Searching…";

  clearInterval(state.polling);
  state.polling = setInterval(pollStatus, 700);
  pollStatus();
}

async function pollStatus() {
  const status = await api("/api/search/status").catch(() => null);
  if (!status) return;

  const percent = status.total ? Math.round((status.done / status.total) * 100) : 3;
  $("#progress-fill").style.width = `${percent}%`;
  $("#progress-message").textContent = status.message || "Searching…";
  $("#progress-count").textContent = status.total ? `${status.done} / ${status.total}` : "";

  if (status.running) return;

  clearInterval(state.polling);
  state.polling = null;
  $("#progress").classList.add("hidden");
  $("#search-markets").textContent = "🔍 Search markets";
  renderShoppingList();

  if (status.error) {
    toast(`Search failed: ${status.error}`);
    return;
  }

  state.report = await api("/api/search/latest");
  renderResults();
  toast("Prices updated");
}

// ============================================================
// RESULTS
// ============================================================

function priceText(product, compareUnit) {
  if (!product) return "–";
  if (compareUnit && product.comparison_price != null) {
    return `${Number(product.comparison_price).toFixed(2)} lei/${compareUnit}`;
  }
  return lei(product.price);
}

function promoBadges(product) {
  let html = "";
  if (product.on_sale) html += `<span class="badge">${esc(product.promo_label || "Promo")}</span>`;
  if (product.loyalty_card) html += `<span class="badge card">${esc(product.loyalty_card)}</span>`;
  if (product.suspect_price) html += `<span class="badge warn" title="Size could not be read reliably; ignored for 'best price'">size?</span>`;
  return html;
}

function branchLine(product) {
  return product && product.branch ? `<div class="branch">${esc(product.branch)}</div>` : "";
}

function errorList(errors) {
  const entries = Object.entries(errors || {});
  if (!entries.length) return "";
  return `<div class="card errors"><h3>Some sources failed</h3><ul>
    ${entries.map(([key, message]) => `<li><strong>${esc(key)}</strong>: ${esc(message)}</li>`).join("")}
  </ul></div>`;
}

function renderHero(recommendation) {
  const card = (label, entry) => entry ? `
    <div class="hero-card" ${storeStyle(entry.store)}>
      <div class="label">${label}</div>
      <div class="store">${esc(entry.store)}</div>
      <p>${esc(entry.reason)}</p>
    </div>` : "";

  return `<div class="hero">
    ${card("🏆 Best market today · promotions", recommendation.best)}
    ${card("🥈 Second best · cheapest prices", recommendation.second)}
  </div>`;
}

function renderSummary(summaries, itemCount) {
  return `<div class="card"><h3>Stores compared</h3><div class="table-wrap">
    <table class="summary-table">
      <thead><tr>
        <th>Store</th><th class="num">Items found</th><th class="num">Cheapest for</th>
        <th class="num">On promotion</th><th class="num">Avg. discount</th>
        <th class="num" title="Average of the store's best price ÷ the lowest price. 1.00 = always cheapest.">Price index</th>
      </tr></thead>
      <tbody>${summaries.map((s) => `
        <tr>
          <td class="store-tag" ${storeStyle(s.store)}>${esc(s.store)}</td>
          <td class="num">${s.found} / ${itemCount}</td>
          <td class="num">${s.cheapest_wins}</td>
          <td class="num">${s.promo_items}</td>
          <td class="num">${s.average_discount != null ? `${Math.round(s.average_discount)}%` : "–"}</td>
          <td class="num">${s.price_index != null ? s.price_index.toFixed(2) : "–"}</td>
        </tr>`).join("")}
      </tbody>
    </table></div></div>`;
}

function renderPlan(plan, items) {
  const units = Object.fromEntries(items.map((item) => [item.label, item.compare_unit]));
  const stores = Object.keys(plan);
  if (!stores.length) return "";

  return `<div class="card"><h3>Shopping plan</h3>
    <p class="muted" style="margin-bottom:10px">Each item goes to whichever of the two recommended stores is cheaper for it.</p>
    <div class="plan">${stores.map((store) => `
      <div class="plan-store" ${storeStyle(store)}>
        <h4>${esc(store)}</h4>
        <ul>${plan[store].map((entry) => `
          <li><strong>${esc(entry.label)}</strong>
            ${entry.product ? `· ${priceText(entry.product, units[entry.label])}${promoBadges(entry.product)}${branchLine(entry.product)}` : ""}
            ${entry.cheaper_elsewhere ? `<div class="muted" style="font-size:.8rem">Cheaper at <span class="store-tag" ${storeStyle(entry.cheaper_elsewhere.store)}>${esc(entry.cheaper_elsewhere.store)}</span>: ${priceText(entry.cheaper_elsewhere, units[entry.label])}</div>` : ""}</li>`).join("")}
        </ul>
      </div>`).join("")}
    </div></div>`;
}

function renderItem(item, stores) {
  const unit = item.compare_unit;
  const best = item.best;

  const storeCells = stores.map((store) => {
    const entry = item.per_store[store];
    const product = entry.best;

    if (!product) {
      return `<div class="store-cell none" ${storeStyle(store)}>
        <div class="store-name">${esc(store)}</div>${entry.count ? "No comparable price" : "Not found"}</div>`;
    }

    const isWinner = best && best.store === store;
    const promo = entry.promo && entry.promo !== product ? entry.promo : null;

    return `<div class="store-cell ${isWinner ? "winner" : ""}" ${storeStyle(store)}>
      <div class="store-name">${esc(store)} ${isWinner ? `<span class="badge win">Cheapest</span>` : ""}</div>
      <div class="price">${priceText(product, unit)}
        ${unit ? `<small>· ${lei(product.price)}${product.package ? ` / ${esc(product.package)}` : ""}</small>` : ""}</div>
      <div class="pname"><a href="${esc(product.url)}" target="_blank" rel="noopener">${esc(product.name)}</a>${promoBadges(product)}
        ${product.old_price ? `<span class="old-price">${lei(product.old_price)}</span>` : ""}</div>
      ${branchLine(product)}
      ${promo && promo.name !== product.name ? `<div class="pname">Best promo: ${esc(promo.name)} · ${priceText(promo, unit)}${promoBadges(promo)}</div>${branchLine(promo)}` : ""}
    </div>`;
  }).join("");

  const rows = item.products.map((product) => `
    <tr>
      <td class="store-tag" ${storeStyle(product.store)}>${esc(product.store)}</td>
      <td><a href="${esc(product.url)}" target="_blank" rel="noopener">${esc(product.name)}</a>${promoBadges(product)}
        ${branchLine(product)}
        <div class="muted" style="font-size:.78rem">${esc(product.source || "")}</div></td>
      <td>${esc(product.package || "")}</td>
      <td class="num">${lei(product.price)}${product.old_price ? `<br><span class="old-price">${lei(product.old_price)}</span>` : ""}</td>
      <td class="num">${product.unit_price != null ? `${product.unit_price.toFixed(2)} /${esc(product.unit)}` : "–"}</td>
      <td><button class="not-this" data-item="${esc(item.id)}" data-name="${esc(product.name)}" title="Exclude products like this one">✕ not this</button></td>
    </tr>`).join("");

  return `<article class="item-card">
    <div class="item-head">
      <h3>${esc(item.label)} <span class="muted" style="font-weight:400;font-size:.85rem">· ${esc(item.category)}</span></h3>
      <div class="item-best">${best
        ? `Best: <span class="store-tag" ${storeStyle(best.store)}>${esc(best.store)}</span> · <strong>${priceText(best, unit)}</strong>${promoBadges(best)}`
        : `<span class="muted">No prices found. Try another search term.</span>`}</div>
    </div>
    <div class="store-row">${storeCells}</div>
    ${item.products.length ? `
      <details class="more">
        <summary>All matches (${item.found}${item.found > item.products.length ? `, showing cheapest ${item.products.length}` : ""})</summary>
        <div class="table-wrap"><table class="matches">
          <thead><tr><th>Store</th><th>Product</th><th>Size</th><th class="num">Price</th><th class="num">Per unit</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>
      </details>` : ""}
  </article>`;
}

function renderResults() {
  const container = $("#results");
  const report = state.report;

  if (!report) {
    container.innerHTML = state.products.some((p) => p.in_shopping_list)
      ? `<div class="empty">Press <strong>Search markets</strong> to compare today's prices.</div>`
      : "";
    return;
  }

  const listIds = new Set(state.products.filter((p) => p.in_shopping_list).map((p) => p.id));
  const reportIds = new Set(report.items.map((item) => item.id));
  const changed = listIds.size !== reportIds.size || [...listIds].some((id) => !reportIds.has(id));

  container.innerHTML = `
    <h2>Results</h2>
    <div class="results-meta">Searched ${formatDate(report.created_at)} · ${report.items.length} products
      ${changed ? ` · <strong>your list changed since. Search again to update.</strong>` : ""}</div>
    ${renderHero(report.recommendation)}
    ${renderPlan(report.plan, report.items)}
    ${renderSummary(report.store_summaries, report.items.length)}
    ${errorList(report.errors)}
    <h2 style="margin:22px 0 12px">Per product</h2>
    ${report.items.map((item) => renderItem(item, report.stores)).join("")}`;
}

function suggestExcludeWord(productName, product) {
  const normalize = (text) => text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const required = normalize([...product.required_words, product.search_term].join(" "));

  const words = normalize(productName)
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 3 && !/\d/.test(word) && !required.includes(word));

  return words[0] || "";
}

$("#results").addEventListener("click", async (event) => {
  const button = event.target.closest(".not-this");
  if (!button) return;

  const product = state.products.find((p) => p.id === button.dataset.item);
  if (!product) return;

  const word = prompt(
    `Exclude products containing which word?\n\n“${button.dataset.name}”\n\nIt is added to the Exclude list of ${product.label}.`,
    suggestExcludeWord(button.dataset.name, product),
  );

  if (!word || !word.trim()) return;

  await api(`/api/products/${product.id}`, {
    method: "PUT",
    body: { excluded_words: [...(product.excluded_words || []), word.trim()] },
  });

  button.closest("tr").remove();
  await loadProducts();
  toast(`“${word.trim()}” excluded. Search again to refresh the comparison.`);
});

// ============================================================
// SETTINGS
// ============================================================

const settingsForm = $("#settings-form");

function distanceKm(latA, lonA, latB, lonB) {
  const rad = (degrees) => (degrees * Math.PI) / 180;
  const a = Math.sin(rad(latB - latA) / 2) ** 2
    + Math.cos(rad(latA)) * Math.cos(rad(latB)) * Math.sin(rad(lonB - lonA) / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function renderSettings() {
  const settings = state.settings;
  if (!settings) return;

  settingsForm.latitude.value = settings.latitude;
  settingsForm.longitude.value = settings.longitude;
  settingsForm.kaufland_radius_km.value = settings.kaufland_radius_km;
  settingsForm.include_loyalty_prices.checked = settings.include_loyalty_prices;
  settingsForm.send_to_telegram.checked = settings.send_to_telegram;
  settingsForm.telegram_chat_id.value = settings.telegram_chat_id || "";
  settingsForm.telegram_bot_token.value = "";
  settingsForm.telegram_bot_token.placeholder = settings.telegram_token_saved
    ? `Saved (${settings.telegram_token_hint}). Paste a new token to replace it.`
    : "123456789:AAH…";

  $("#location-notice").classList.toggle("hidden", !settings.is_default_location);

  $("#store-toggles").innerHTML = settings.available_stores.map((store) => `
    <label class="check"><input type="checkbox" name="store" value="${esc(store)}"
      ${settings.enabled_stores.includes(store) ? "checked" : ""}>
      <span class="store-tag" ${storeStyle(store)}>${esc(store)}</span></label>`).join("");

  state.selectedLidl = new Map((settings.lidl_stores || []).map((store) => [store.id, store]));
  renderLidlStores();
  renderTelegramState();
}

// ---------- Lidl store picker ----------

function renderLidlStores() {
  const latitude = Number(settingsForm.latitude.value);
  const longitude = Number(settingsForm.longitude.value);

  const all = new Map(state.selectedLidl);
  state.lidlCandidates.forEach((store) => {
    if (!all.has(store.id)) all.set(store.id, store);
  });

  const stores = [...all.values()]
    .map((store) => ({ ...store, km: distanceKm(latitude, longitude, store.latitude, store.longitude) }))
    .sort((a, b) => a.km - b.km);

  const selectedCount = state.selectedLidl.size;
  $("#lidl-status").textContent = selectedCount
    ? `${selectedCount} selected`
    : "None selected: using Lidl's national price list.";

  $("#lidl-stores").innerHTML = stores.map((store) => `
    <label class="store-option">
      <input type="checkbox" data-lidl="${esc(store.id)}" ${state.selectedLidl.has(store.id) ? "checked" : ""}>
      <span><span class="store-title">${esc(store.name)}</span><br>
        <span class="store-address">${esc(store.address)}</span></span>
      <span class="store-distance">${store.km.toFixed(1)} km</span>
    </label>`).join("");
}

$("#lidl-stores").addEventListener("change", (event) => {
  const box = event.target.closest("[data-lidl]");
  if (!box) return;

  const id = box.dataset.lidl;
  const store = [...state.lidlCandidates, ...state.selectedLidl.values()].find((s) => s.id === id);

  if (box.checked && store) state.selectedLidl.set(id, store);
  else state.selectedLidl.delete(id);

  renderLidlStores();
});

$("#find-lidl").addEventListener("click", async () => {
  const button = $("#find-lidl");
  button.disabled = true;
  $("#lidl-status").textContent = "Searching…";

  try {
    const params = new URLSearchParams({
      lat: settingsForm.latitude.value,
      lon: settingsForm.longitude.value,
      radius: settingsForm.kaufland_radius_km.value,
    });
    state.lidlCandidates = await api(`/api/stores/lidl?${params}`);
    renderLidlStores();

    if (!state.lidlCandidates.length) {
      $("#lidl-status").textContent = "No Lidl stores found. Try a larger search radius.";
    } else {
      toast(`${state.lidlCandidates.length} Lidl stores found. Tick yours, then Save settings.`);
    }
  } catch (error) {
    $("#lidl-status").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

["latitude", "longitude"].forEach((name) =>
  settingsForm[name].addEventListener("change", renderLidlStores));

// ---------- Telegram ----------

function setResult(selector, ok, html) {
  const element = $(selector);
  element.className = `small-print ${ok ? "ok-text" : "err-text"}`;
  element.innerHTML = html;
}

function renderTelegramState() {
  const settings = state.settings;
  const box = $("#telegram-state");

  if (!settings.telegram_configured) {
    box.classList.add("hidden");
    return;
  }

  box.innerHTML = settings.telegram_from_env
    ? "✓ Telegram is set up through the <code>.env</code> file. Enter a token below to use a different bot."
    : `✓ Telegram is set up (token ${esc(settings.telegram_token_hint)}, chat ${esc(settings.telegram_chat_id)}).`
      + (settings.send_to_telegram ? " Results are sent after each search." : " Tick step 6 to receive results.");
  box.classList.remove("hidden");
}

function typedToken() {
  return settingsForm.telegram_bot_token.value.trim();
}

$("#tg-check").addEventListener("click", async () => {
  try {
    const bot = await api("/api/telegram/check", { method: "POST", body: { token: typedToken() } });
    const link = `<a href="https://t.me/${esc(bot.username)}" target="_blank" rel="noopener">@${esc(bot.username)}</a>`;
    setResult("#tg-check-result", true, `✓ Token works: your bot is ${link}.`);
    $("#tg-bot-link").innerHTML = `(${link})`;
  } catch (error) {
    setResult("#tg-check-result", false, esc(error.message));
  }
});

$("#tg-chats").addEventListener("click", async () => {
  try {
    const chats = await api("/api/telegram/chats", { method: "POST", body: { token: typedToken() } });

    if (!chats.length) {
      setResult("#tg-chats-result", false,
        "No messages found yet. Send your bot a message (step 3), wait a few seconds, then press this again.");
      return;
    }

    settingsForm.telegram_chat_id.value = chats[0].id;

    const others = chats.slice(1).map((chat) =>
      `<button type="button" class="linkish" data-chat="${esc(chat.id)}">${esc(chat.name)}</button>`).join(", ");

    setResult("#tg-chats-result", true, chats.length === 1
      ? `✓ Found: ${esc(chats[0].name)}.`
      : `✓ Filled in ${esc(chats[0].name)}. Other chats: ${others}`);
  } catch (error) {
    setResult("#tg-chats-result", false, esc(error.message));
  }
});

$("#tg-chats-result").addEventListener("click", (event) => {
  const button = event.target.closest("[data-chat]");
  if (button) settingsForm.telegram_chat_id.value = button.dataset.chat;
});

$("#tg-test").addEventListener("click", async () => {
  try {
    await api("/api/telegram/test", {
      method: "POST",
      body: { token: typedToken(), chat_id: settingsForm.telegram_chat_id.value },
    });
    setResult("#tg-test-result", true, "✓ Sent. Check Telegram. Then tick step 6 and Save settings.");
  } catch (error) {
    setResult("#tg-test-result", false, esc(error.message));
  }
});

$("#tg-remove").addEventListener("click", async () => {
  if (!confirm("Remove the saved Telegram token and chat ID from this computer?")) return;

  state.settings = await api("/api/settings", {
    method: "PUT",
    body: { telegram_bot_token: "", telegram_chat_id: "", send_to_telegram: false },
  });
  renderSettings();
  ["#tg-check-result", "#tg-chats-result", "#tg-test-result", "#tg-bot-link"].forEach((selector) => {
    $(selector).innerHTML = "";
  });
  toast("Telegram details removed");
});

// ---------- save ----------

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const body = {
    latitude: settingsForm.latitude.value,
    longitude: settingsForm.longitude.value,
    kaufland_radius_km: settingsForm.kaufland_radius_km.value,
    include_loyalty_prices: settingsForm.include_loyalty_prices.checked,
    send_to_telegram: settingsForm.send_to_telegram.checked,
    enabled_stores: [...settingsForm.querySelectorAll("input[name=store]:checked")].map((input) => input.value),
    lidl_stores: [...state.selectedLidl.values()].map(({ id, name, address, latitude, longitude }) =>
      ({ id, name, address, latitude, longitude })),
    telegram_chat_id: settingsForm.telegram_chat_id.value,
  };

  // Only replace the saved token when a new one was typed.
  if (typedToken()) body.telegram_bot_token = typedToken();

  const hasToken = typedToken() || state.settings.telegram_token_saved || state.settings.telegram_from_env;
  if (body.send_to_telegram && !hasToken) {
    toast("Add your bot token (step 2) before turning Telegram on.");
    return;
  }

  try {
    state.settings = await api("/api/settings", { method: "PUT", body });
    renderSettings();
    toast("Settings saved");
  } catch (error) {
    toast(error.message);
  }
});

$("#use-location").addEventListener("click", () => {
  if (!navigator.geolocation) {
    toast("Location is not available in this browser");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      settingsForm.latitude.value = position.coords.latitude.toFixed(5);
      settingsForm.longitude.value = position.coords.longitude.toFixed(5);
      renderLidlStores();
      toast("Location filled in. Now find your Lidl stores, then Save settings.");
    },
    () => toast("Could not get your location. You can type the coordinates instead."),
  );
});

// ============================================================
// STARTUP
// ============================================================

function renderAll() {
  renderProducts();
  renderShoppingList();
  renderResults();
}

async function loadProducts() {
  state.products = await api("/api/products");
  renderAll();
}

async function init() {
  const [products, settings, report, status] = await Promise.all([
    api("/api/products"),
    api("/api/settings"),
    api("/api/search/latest"),
    api("/api/search/status"),
  ]);

  state.products = products;
  state.settings = settings;
  state.report = report;

  renderAll();
  renderSettings();

  let savedView = null;
  try { savedView = localStorage.getItem("view"); } catch { /* storage unavailable */ }
  if (savedView) showView(savedView);

  if (status.running) startPolling();
}

init().catch((error) => toast(`Could not load the app: ${error.message}`));
