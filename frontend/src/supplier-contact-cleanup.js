let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function removeTableColumn(table, expectedLabel) {
  const headers = [...table.querySelectorAll("thead th")];
  const index = headers.findIndex(
    (header) => normalize(header.textContent) === normalize(expectedLabel),
  );
  if (index < 0) return;

  headers[index].remove();
  for (const row of table.querySelectorAll("tbody tr")) {
    row.querySelectorAll("td")[index]?.remove();
  }
}

function cleanSupplierUi() {
  for (const form of document.querySelectorAll("form")) {
    const fields = [...form.querySelectorAll("label.field")];
    const isSupplierForm = fields.some(
      (field) => normalize(field.querySelector(":scope > span")?.textContent) === "nome do fornecedor",
    );
    if (!isSupplierForm) continue;

    for (const field of fields) {
      const label = normalize(field.querySelector(":scope > span")?.textContent);
      if (!["whatsapp do responsavel", "e-mail do responsavel"].includes(label)) continue;

      field.hidden = true;
      field.setAttribute("aria-hidden", "true");
      field.querySelectorAll("input, select, textarea, button").forEach((control) => {
        control.disabled = true;
      });
    }
  }

  for (const table of document.querySelectorAll("table")) {
    const labels = [...table.querySelectorAll("thead th")].map((header) =>
      normalize(header.textContent),
    );
    if (!labels.includes("fornecedor") || !labels.includes("cnpj/cpf")) continue;

    removeTableColumn(table, "WhatsApp do responsável");
    removeTableColumn(table, "E-mail do responsável");
  }
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
    window.setTimeout(cleanSupplierUi, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  cleanSupplierUi();
}
