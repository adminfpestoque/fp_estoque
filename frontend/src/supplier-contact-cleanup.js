let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s*\*+\s*$/g, "")
    .replace(/\s+/g, " ");
}

const REMOVED_FORM_LABELS = new Set([
  "whatsapp do responsavel",
  "e-mail do responsavel",
]);

const REMOVED_TABLE_LABELS = new Set([
  "whatsapp do responsavel",
  "e-mail do responsavel",
]);

function supplierFields(form) {
  return [...form.querySelectorAll("label.field")];
}

function isSupplierForm(form) {
  return supplierFields(form).some((field) => {
    const label = field.querySelector(":scope > span")?.textContent;
    return normalize(label) === "nome do fornecedor";
  });
}

function removeSupplierFormFields() {
  for (const form of document.querySelectorAll("form")) {
    if (!isSupplierForm(form)) continue;

    for (const field of supplierFields(form)) {
      const label = normalize(field.querySelector(":scope > span")?.textContent);
      if (REMOVED_FORM_LABELS.has(label)) field.remove();
    }
  }
}

function removeSupplierTableColumns() {
  for (const table of document.querySelectorAll("table")) {
    const headers = [...table.querySelectorAll("thead th")];
    const labels = headers.map((header) => normalize(header.textContent));
    if (!labels.includes("fornecedor") || !labels.includes("cnpj/cpf")) continue;

    const indexes = headers
      .map((header, index) => ({ index, label: normalize(header.textContent) }))
      .filter(({ label }) => REMOVED_TABLE_LABELS.has(label))
      .map(({ index }) => index)
      .sort((a, b) => b - a);

    for (const index of indexes) {
      table.querySelectorAll("tr").forEach((row) => {
        row.children[index]?.remove();
      });
    }
  }
}

function cleanSupplierUi() {
  removeSupplierFormFields();
  removeSupplierTableColumns();
}

function clearRemovedContacts(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return payload;
  payload.whatsapp = "";
  payload.email = "";
  return payload;
}

export function installSupplierContactCleanup(client) {
  if (installed) return;
  installed = true;

  client.interceptors.request.use((config) => {
    const method = String(config.method || "get").toLowerCase();
    const url = String(config.url || "").replace(/^\/+/, "").split("?")[0];
    const changesSupplier = ["post", "put", "patch"].includes(method)
      && /^suppliers\/(?:\d+\/)?$/.test(url);

    if (!changesSupplier) return config;

    if (typeof config.data === "string") {
      try {
        config.data = JSON.stringify(clearRemovedContacts(JSON.parse(config.data)));
      } catch {
        // Mantém cargas que não são JSON.
      }
    } else {
      clearRemovedContacts(config.data);
    }
    return config;
  });

  const observer = new MutationObserver(() => {
    window.requestAnimationFrame(cleanSupplierUi);
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  cleanSupplierUi();
  window.setTimeout(cleanSupplierUi, 100);
  window.setTimeout(cleanSupplierUi, 500);
  window.setTimeout(cleanSupplierUi, 1500);
}
