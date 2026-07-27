let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function removeCostFromProductPayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;

  delete value.cost_price;
  if (Array.isArray(value.packaging_options)) {
    value.packaging_options.forEach((option) => {
      if (option && typeof option === "object") delete option.cost_price;
    });
  }
  return value;
}

function cleanProductForm() {
  const form = document.querySelector(".product-form-simple");
  if (!form) return;

  for (const field of form.querySelectorAll("label.field")) {
    const label = normalize(field.querySelector(":scope > span")?.textContent);
    if (!label.startsWith("preco de custo")) continue;

    field.hidden = true;
    field.setAttribute("aria-hidden", "true");
    field.querySelectorAll("input, select, textarea, button").forEach((control) => {
      control.disabled = true;
    });
  }

  if (!form.querySelector("[data-entry-cost-note]")) {
    const saleField = [...form.querySelectorAll("label.field")].find((field) =>
      normalize(field.querySelector(":scope > span")?.textContent).startsWith("preco de venda"),
    );
    if (saleField) {
      const note = document.createElement("div");
      note.dataset.entryCostNote = "true";
      note.className = "document-edit-warning neutral full";
      note.textContent = "O preço de custo é informado em Entradas > Nova entrada, conforme a forma recebida: unidade, caixa, fardo, grade ou pacote.";
      saleField.before(note);
    }
  }
}

export function installProductCostEntryOnly(client) {
  if (installed) return;
  installed = true;

  client.interceptors.request.use((config) => {
    const method = String(config.method || "get").toLowerCase();
    const url = String(config.url || "").replace(/^\/+/, "");
    const changesProduct = ["post", "put", "patch"].includes(method)
      && /^products\/(?:\d+\/)?$/.test(url.split("?")[0]);

    if (!changesProduct) return config;

    if (typeof config.data === "string") {
      try {
        const parsed = JSON.parse(config.data);
        config.data = JSON.stringify(removeCostFromProductPayload(parsed));
      } catch {
        // Mantém cargas que não são JSON.
      }
    } else {
      removeCostFromProductPayload(config.data);
    }
    return config;
  });

  const observer = new MutationObserver(() => window.setTimeout(cleanProductForm, 0));
  observer.observe(document.body, { childList: true, subtree: true });
  cleanProductForm();
}
