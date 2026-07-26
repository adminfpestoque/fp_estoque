let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function stripMaximumStock(value) {
  if (Array.isArray(value)) {
    value.forEach(stripMaximumStock);
    return value;
  }
  if (!value || typeof value !== "object") return value;

  delete value.maximum_stock;
  Object.values(value).forEach(stripMaximumStock);

  if (Array.isArray(value.columns) && Array.isArray(value.rows)) {
    const indexes = value.columns
      .map((column, index) => ({ column: normalize(column), index }))
      .filter(({ column }) => column === "maximo" || column === "estoque maximo")
      .map(({ index }) => index);

    [...indexes].reverse().forEach((index) => {
      value.columns.splice(index, 1);
      value.rows.forEach((row) => {
        if (Array.isArray(row) && index < row.length) row.splice(index, 1);
      });
    });
  }
  return value;
}

function cleanProductForm() {
  for (const field of document.querySelectorAll("label.field")) {
    const title = field.querySelector(":scope > span");
    const label = normalize(title?.textContent);

    if (label === "estoque maximo") {
      field.hidden = true;
      field.setAttribute("aria-hidden", "true");
      field.querySelectorAll("input, select, textarea, button").forEach((control) => {
        control.disabled = true;
      });
      continue;
    }

    if (label === "estoque minimo" && title) {
      title.textContent = "Estoque mínimo em unidades";
      if (!field.querySelector(":scope > small")) {
        const hint = document.createElement("small");
        hint.textContent = "O sistema avisará quando o saldo atingir ou ficar abaixo deste valor.";
        field.appendChild(hint);
      }
    }
  }
}

export function installMaximumStockRemoval(client) {
  if (installed) return;
  installed = true;

  client.interceptors.request.use((config) => {
    if (config.data && typeof config.data === "string") {
      try {
        const parsed = JSON.parse(config.data);
        config.data = JSON.stringify(stripMaximumStock(parsed));
      } catch {
        // Mantém cargas que não são JSON.
      }
    } else {
      stripMaximumStock(config.data);
    }
    return config;
  });

  client.interceptors.response.use((response) => {
    stripMaximumStock(response.data);
    window.setTimeout(cleanProductForm, 0);
    return response;
  });

  const observer = new MutationObserver(() => window.setTimeout(cleanProductForm, 0));
  observer.observe(document.body, { childList: true, subtree: true });
  cleanProductForm();
}
