const entryRows = new Map();
let installed = false;

function normalizePath(url) {
  try {
    return new URL(String(url || ""), window.location.origin)
      .pathname
      .replace(/^\/api\//, "")
      .replace(/^\/+/, "");
  } catch {
    return String(url || "").split("?")[0].replace(/^\/+/, "");
  }
}

function rowsFromPayload(payload) {
  const rows = payload?.results || payload || [];
  return Array.isArray(rows) ? rows : [];
}

function normalizeHeader(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function productNames(row) {
  const names = (row?.items || [])
    .map((item) => item.product_name || item.product_name_snapshot || "")
    .map((name) => String(name).trim())
    .filter(Boolean);

  return [...new Set(names)];
}

function isEntriesList(url) {
  const path = normalizePath(url);
  return path === "entries" || path === "entries/";
}

function cacheEntry(row) {
  if (row?.number) entryRows.set(String(row.number), row);
}

function findEntriesTable() {
  return [...document.querySelectorAll("table")].find((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((header) =>
      normalizeHeader(header.textContent),
    );

    return headers.includes("numero")
      && headers.includes("fornecedor")
      && headers.includes("valor total da compra")
      && headers.includes("itens");
  }) || null;
}

function renderProductCell(cell, row) {
  const names = productNames(row);
  const itemCount = Array.isArray(row?.items) ? row.items.length : 0;
  const signature = JSON.stringify([names, itemCount]);

  if (cell.dataset.entryProductsSignature === signature) return;
  cell.dataset.entryProductsSignature = signature;
  cell.classList.add("entry-products-cell");
  cell.title = names.join(", ");
  cell.replaceChildren();

  const wrapper = document.createElement("div");
  wrapper.className = "entry-products-summary";

  const primary = document.createElement("strong");
  primary.textContent = names[0] || "Produto não informado";
  wrapper.appendChild(primary);

  const details = [];
  if (names.length > 1) {
    details.push(`+ ${names.length - 1} ${names.length - 1 === 1 ? "outro produto" : "outros produtos"}`);
  }
  details.push(`${itemCount} ${itemCount === 1 ? "item" : "itens"}`);

  const meta = document.createElement("small");
  meta.textContent = details.join(" • ");
  wrapper.appendChild(meta);

  cell.appendChild(wrapper);
}

function enhanceEntriesTable() {
  const table = findEntriesTable();
  if (!table) return;

  const headers = [...table.querySelectorAll("thead th")];
  const itemsIndex = headers.findIndex(
    (header) => normalizeHeader(header.textContent) === "itens",
  );

  if (itemsIndex < 0) return;

  const itemsHeader = headers[itemsIndex];
  if (itemsHeader.textContent.trim() !== "Produto(s)") {
    itemsHeader.textContent = "Produto(s)";
  }
  itemsHeader.classList.add("entry-products-header");

  for (const tableRow of table.querySelectorAll("tbody tr")) {
    const number = tableRow.querySelector("td strong")?.textContent?.trim() || "";
    const row = entryRows.get(number);
    const cell = tableRow.children[itemsIndex];
    if (!cell || !row) continue;
    renderProductCell(cell, row);
  }
}

function scheduleEnhancement() {
  window.setTimeout(enhanceEntriesTable, 0);
}

export function installEntryProductColumn(client) {
  if (installed || typeof document === "undefined") return;
  installed = true;

  client.interceptors.response.use((response) => {
    const method = String(response.config?.method || "get").toLowerCase();
    const path = normalizePath(response.config?.url);

    if (method === "get" && isEntriesList(response.config?.url)) {
      rowsFromPayload(response.data).forEach(cacheEntry);
    } else if (method === "get" && /^entries\/\d+\/?$/.test(path)) {
      cacheEntry(response.data);
    }

    scheduleEnhancement();
    return response;
  });

  const observer = new MutationObserver(scheduleEnhancement);
  observer.observe(document.body, { childList: true, subtree: true });
}
