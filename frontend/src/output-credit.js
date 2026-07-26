const outputRows = new Map();
let editingOutputNumber = "";
let finalizingOutput = false;
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

function isOutputCollection(url) {
  const path = normalizePath(url);
  return path === "outputs" || path === "outputs/";
}

function isOutputDocumentWrite(config) {
  const method = String(config?.method || "get").toLowerCase();
  const path = normalizePath(config?.url);
  return ["post", "put", "patch"].includes(method)
    && /^outputs\/(?:\d+\/)?$/.test(path);
}

function rowsFromPayload(payload) {
  const rows = payload?.results || payload || [];
  return Array.isArray(rows) ? rows : [];
}

function currentOutputFormModal() {
  return [...document.querySelectorAll(".modal")].find((modal) => {
    const title = modal.querySelector(".modal-header h2")?.textContent?.trim() || "";
    return /^(Nova|Editar) saída$/i.test(title);
  }) || null;
}

function paymentSelectFrom(modal) {
  return [...modal.querySelectorAll("select")].find((select) =>
    [...select.options].some((option) => option.value === "ON_ACCOUNT"),
  ) || null;
}

function labelByText(modal, text) {
  return [...modal.querySelectorAll("label.field")].find((label) =>
    (label.querySelector(":scope > span")?.textContent || "").trim().startsWith(text),
  ) || null;
}

function customerInputFrom(modal) {
  return [...modal.querySelectorAll("input")].find((input) =>
    String(input.placeholder || "").toLowerCase().includes("cliente"),
  ) || null;
}

function setNativeInputValue(input, value) {
  if (!input || input.value === value) return;
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")?.set;
  if (setter) setter.call(input, value);
  else input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function formatDateOnly(value) {
  if (!value) return "Não informada";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : String(value);
}

function cachedEditingRow() {
  return editingOutputNumber ? outputRows.get(editingOutputNumber) || null : null;
}

function ensureDueDateField(modal, paymentField) {
  let field = modal.querySelector("[data-credit-due-field]");
  if (field) return field;

  field = document.createElement("label");
  field.className = "field credit-due-date-field";
  field.dataset.creditDueField = "true";
  field.innerHTML = `
    <span>Data prevista para recebimento *</span>
    <input type="date" data-credit-due-date />
    <small>Escolha no calendário o dia combinado para receber do cliente.</small>
  `;

  paymentField.insertAdjacentElement("afterend", field);

  const input = field.querySelector("[data-credit-due-date]");
  input.addEventListener("input", () => {
    modal.dataset.creditDueDate = input.value;
  });

  return field;
}

function enhanceOutputForm() {
  const modal = currentOutputFormModal();
  if (!modal) return;

  const paymentSelect = paymentSelectFrom(modal);
  if (!paymentSelect) return;

  const paymentField = paymentSelect.closest("label.field");
  const customerInput = customerInputFrom(modal);
  const customerField = customerInput?.closest("label.field") || null;
  const customerLabel = customerField?.querySelector(":scope > span") || null;
  const referenceField = labelByText(modal, "Referência do pagamento");
  const referenceInput = referenceField?.querySelector("input") || null;
  const dueField = ensureDueDateField(modal, paymentField);
  const dueInput = dueField.querySelector("[data-credit-due-date]");
  const onAccount = paymentSelect.value === "ON_ACCOUNT";

  if (!paymentSelect.dataset.creditListener) {
    paymentSelect.dataset.creditListener = "true";
    paymentSelect.addEventListener("change", () => window.setTimeout(enhanceOutputForm, 0));
  }

  if (!modal.dataset.creditInitialized) {
    const row = cachedEditingRow();
    modal.dataset.creditDueDate = row?.payment_due_date || "";
    modal.dataset.creditInitialized = "true";
  }

  if (dueInput.value !== (modal.dataset.creditDueDate || "")) {
    dueInput.value = modal.dataset.creditDueDate || "";
  }

  dueField.hidden = !onAccount;
  referenceField && (referenceField.hidden = onAccount);

  if (customerLabel) {
    customerLabel.textContent = onAccount ? "Cliente *" : "Cliente";
  }

  if (customerInput) {
    customerInput.placeholder = onAccount
      ? "Nome do cliente que ficará devendo"
      : "Nome ou identificação do cliente";
  }

  if (onAccount && !modal.dataset.creditCustomerMigrated) {
    const row = cachedEditingRow();
    const legacyName = String(row?.customer_name || row?.payment_reference || referenceInput?.value || "").trim();
    if (legacyName && customerInput && !customerInput.value.trim()) {
      setNativeInputValue(customerInput, legacyName);
    }
    modal.dataset.creditCustomerMigrated = "true";
  }
}

function enhanceOutputDetails() {
  for (const modal of document.querySelectorAll(".modal")) {
    const title = modal.querySelector(".modal-header h2")?.textContent?.trim() || "";
    const match = title.match(/^Saída\s+(SAI-[A-Z0-9-]+)$/i);
    if (!match) continue;

    const row = outputRows.get(match[1]);
    const grid = modal.querySelector(".checkout-detail-grid");
    if (!row || !grid || row.payment_method !== "ON_ACCOUNT") continue;
    if (grid.querySelector("[data-credit-due-detail]")) continue;

    const item = document.createElement("div");
    item.dataset.creditDueDetail = "true";
    item.innerHTML = `<span>Receber em</span><strong>${formatDateOnly(row.payment_due_date)}</strong>`;
    grid.appendChild(item);
  }
}

function enhanceAll() {
  enhanceOutputForm();
  enhanceOutputDetails();
}

function clientValidationError(config, message) {
  const error = new Error(message);
  error.config = config;
  error.response = { status: 400, data: { detail: message } };
  return error;
}

function readRequestData(config) {
  if (!config?.data) return { data: null, wasString: false };
  if (typeof config.data !== "string") return { data: config.data, wasString: false };
  try {
    return { data: JSON.parse(config.data), wasString: true };
  } catch {
    return { data: null, wasString: true };
  }
}

export function installCreditSaleEnhancements(client) {
  if (installed || typeof document === "undefined") return;
  installed = true;

  client.interceptors.response.use((response) => {
    if (String(response.config?.method || "get").toLowerCase() === "get"
      && isOutputCollection(response.config?.url)) {
      for (const row of rowsFromPayload(response.data)) {
        if (row?.number) outputRows.set(row.number, row);
      }
    }
    window.setTimeout(enhanceAll, 0);
    return response;
  });

  client.interceptors.request.use((config) => {
    if (!isOutputDocumentWrite(config)) return config;

    const parsed = readRequestData(config);
    const data = parsed.data;
    if (!data || typeof data !== "object") return config;

    const modal = currentOutputFormModal();
    const dueDate = modal?.querySelector("[data-credit-due-date]")?.value
      || modal?.dataset.creditDueDate
      || data.payment_due_date
      || "";
    const customerInput = modal ? customerInputFrom(modal) : null;
    const customerName = String(customerInput?.value || data.customer_name || "").trim();

    if (data.payment_method === "ON_ACCOUNT") {
      data.payment_due_date = dueDate || null;
      data.customer_name = customerName;
      data.payment_reference = "";

      if (finalizingOutput && !customerName) {
        finalizingOutput = false;
        return Promise.reject(clientValidationError(config, "Informe o nome do cliente para finalizar a venda a prazo/fiado."));
      }
      if (finalizingOutput && !dueDate) {
        finalizingOutput = false;
        return Promise.reject(clientValidationError(config, "Escolha no calendário a data prevista para recebimento."));
      }
    } else {
      data.payment_due_date = null;
    }

    config.data = parsed.wasString ? JSON.stringify(data) : data;
    window.setTimeout(() => { finalizingOutput = false; }, 0);
    return config;
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;

    const text = String(button.textContent || "").trim().toLowerCase();
    const title = String(button.getAttribute("title") || "").toLowerCase();

    if (text.includes("nova saída")) editingOutputNumber = "";

    if (title.startsWith("editar")) {
      const row = button.closest("tr");
      const number = row?.querySelector("td strong")?.textContent?.trim() || "";
      if (number.startsWith("SAI-")) editingOutputNumber = number;
    }

    if (text.includes("finalizar saída") || text.includes("salvar e recalcular")) {
      finalizingOutput = true;
    } else if (text.includes("salvar rascunho")) {
      finalizingOutput = false;
    }

    window.setTimeout(enhanceAll, 0);
  }, true);

  const observer = new MutationObserver(() => window.setTimeout(enhanceAll, 0));
  observer.observe(document.body, { childList: true, subtree: true });
}
