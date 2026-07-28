const outputRows = new Map();
let editingOutputNumber = "";
let settlingCreditOutputNumber = "";
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

function isOutputConfirm(config) {
  const method = String(config?.method || "get").toLowerCase();
  return method === "post" && /^outputs\/\d+\/confirm\/$/.test(normalizePath(config?.url));
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

function customerInputFrom(modal) {
  return [...modal.querySelectorAll("input")].find((input) =>
    String(input.placeholder || "").toLowerCase().includes("cliente"),
  ) || null;
}

function formatDateOnly(value, fallback = "--") {
  if (!value) return fallback;
  const [year, month, day] = String(value).slice(0, 10).split("-");
  return year && month && day ? `${day}/${month}/${year}` : String(value);
}

function todayDateOnly() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function isPastDueDate(value) {
  return Boolean(value) && String(value).slice(0, 10) < todayDateOnly();
}

function formatQuantity(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value || 0);
  return number.toLocaleString("pt-BR", { maximumFractionDigits: 3 });
}

function shortSaleUnit(value) {
  const unit = String(value || "Unidade").trim();
  return /^(unidade|un|uni)$/i.test(unit) ? "Uni" : unit;
}

function itemSummary(row) {
  const items = Array.isArray(row?.items) ? row.items : [];
  if (!items.length) return "0";
  return items
    .map((item) => `${formatQuantity(item.sale_quantity ?? item.quantity ?? 0)} ${shortSaleUnit(item.sale_unit_name)}`)
    .join(" • ");
}

function paymentStatus(row) {
  if (!row || row.reason !== "COMMERCIAL" || row.payment_method === "NONE") return null;
  return row.status === "CONFIRMED"
    ? { value: "paid", label: "Pago" }
    : { value: "pending", label: "Pendente" };
}

function outputNumberFromButton(button) {
  return button.closest("tr")?.querySelector("td strong")?.textContent?.trim() || "";
}

function isSettlingCurrentCredit() {
  return Boolean(
    settlingCreditOutputNumber
      && editingOutputNumber
      && settlingCreditOutputNumber === editingOutputNumber,
  );
}

function ensureStyles() {
  if (document.querySelector("style[data-credit-workflow-styles]")) return;
  const style = document.createElement("style");
  style.dataset.creditWorkflowStyles = "true";
  style.textContent = `
    .credit-payment-status {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 9px;
      border: 1px solid currentColor;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .credit-payment-status.paid {
      color: #22c55e;
      background: rgba(34, 197, 94, .10);
    }
    .credit-payment-status.pending {
      color: #f59e0b;
      background: rgba(245, 158, 11, .10);
    }
    [data-credit-due-cell],
    [data-credit-status-cell] { white-space: nowrap; }
  `;
  document.head.appendChild(style);
}

function findOutputTable() {
  return [...document.querySelectorAll("table")].find((table) => {
    const headers = [...table.querySelectorAll("thead th")].map((cell) => cell.textContent.trim());
    return headers.includes("Número") && headers.includes("Pagamento") && headers.includes("Itens") && headers.includes("Situação");
  }) || null;
}

function createHeader(label, dataKey) {
  const cell = document.createElement("th");
  cell.textContent = label;
  cell.dataset[dataKey] = "true";
  return cell;
}

function ensureCell(tableRow, selector, dataKey, beforeCell) {
  let cell = tableRow.querySelector(selector);
  if (cell) return cell;
  cell = document.createElement("td");
  cell.dataset[dataKey] = "true";
  tableRow.insertBefore(cell, beforeCell || null);
  return cell;
}

function updateStatusCell(cell, status) {
  const statusText = status?.label || "--";
  const existingBadge = cell.querySelector(".credit-payment-status");
  const expectedClass = status ? `credit-payment-status ${status.value}` : "";

  if (!status) {
    if (existingBadge || cell.textContent !== statusText) cell.textContent = statusText;
    return;
  }

  if (existingBadge && existingBadge.className === expectedClass && existingBadge.textContent === statusText) return;
  const badge = document.createElement("span");
  badge.className = expectedClass;
  badge.textContent = statusText;
  cell.replaceChildren(badge);
}

function enhanceOutputTable() {
  const table = findOutputTable();
  if (!table) return;
  const headerRow = table.querySelector("thead tr");
  if (!headerRow) return;

  let headers = [...headerRow.querySelectorAll("th")];
  let itemsHeader = headers.find((cell) => cell.textContent.trim() === "Itens");
  if (!itemsHeader) return;

  if (!headerRow.querySelector("[data-credit-due-header]")) {
    headerRow.insertBefore(createHeader("Data prazo", "creditDueHeader"), itemsHeader);
  }
  headers = [...headerRow.querySelectorAll("th")];
  itemsHeader = headers.find((cell) => cell.textContent.trim() === "Itens");

  if (!headerRow.querySelector("[data-credit-status-header]")) {
    headerRow.insertBefore(createHeader("Status pagamento", "creditStatusHeader"), itemsHeader);
  }

  const originalHeaders = [...headerRow.querySelectorAll("th")].filter(
    (cell) => !cell.dataset.creditDueHeader && !cell.dataset.creditStatusHeader,
  );
  const originalItemsIndex = originalHeaders.findIndex((cell) => cell.textContent.trim() === "Itens");

  for (const tableRow of table.querySelectorAll("tbody tr")) {
    const number = tableRow.querySelector("td strong")?.textContent?.trim() || "";
    const row = outputRows.get(number);
    if (!row) continue;

    const originalCells = [...tableRow.querySelectorAll("td")].filter(
      (cell) => !cell.dataset.creditDueCell && !cell.dataset.creditStatusCell,
    );
    const itemsCell = originalCells[originalItemsIndex] || null;
    const dueCell = ensureCell(tableRow, "[data-credit-due-cell]", "creditDueCell", itemsCell);
    const statusCell = ensureCell(tableRow, "[data-credit-status-cell]", "creditStatusCell", itemsCell);

    const dueText = row.payment_method === "ON_ACCOUNT"
      ? formatDateOnly(row.payment_due_date)
      : "--";
    if (dueCell.textContent !== dueText) dueCell.textContent = dueText;
    updateStatusCell(statusCell, paymentStatus(row));

    if (itemsCell) {
      const summary = itemSummary(row);
      if (itemsCell.textContent !== summary) itemsCell.textContent = summary;
      if (itemsCell.title !== summary) itemsCell.title = summary;
    }
  }
}

function ensurePaymentStatusDetail() {
  for (const modal of document.querySelectorAll(".modal")) {
    const title = modal.querySelector(".modal-header h2")?.textContent?.trim() || "";
    const match = title.match(/^Saída\s+(SAI-[A-Z0-9-]+)$/i);
    if (!match) continue;
    const row = outputRows.get(match[1]);
    const grid = modal.querySelector(".checkout-detail-grid");
    if (!row || !grid || grid.querySelector("[data-credit-status-detail]")) continue;

    const item = document.createElement("div");
    item.dataset.creditStatusDetail = "true";
    item.innerHTML = `<span>Status do pagamento</span><strong>${paymentStatus(row)?.label || "--"}</strong>`;
    grid.appendChild(item);
  }
}

function ensureCreditFormState() {
  const modal = currentOutputFormModal();
  if (!modal) return;
  const paymentSelect = paymentSelectFrom(modal);
  if (!paymentSelect) return;

  const onAccount = paymentSelect.value === "ON_ACCOUNT";
  const dueInput = modal.querySelector("[data-credit-due-date]");
  const customerInput = customerInputFrom(modal);
  if (dueInput) {
    dueInput.required = onAccount;
    if (!dueInput.dataset.creditWorkflowListener) {
      dueInput.dataset.creditWorkflowListener = "true";
      dueInput.addEventListener("input", () => window.setTimeout(enhanceAll, 0));
    }
  }
  if (customerInput) customerInput.required = onAccount;

  let warning = modal.querySelector("[data-credit-settlement-warning]");
  if (!isSettlingCurrentCredit()) {
    warning?.remove();
    return;
  }

  if (!warning) {
    warning = document.createElement("div");
    warning.dataset.creditSettlementWarning = "true";
    modal.querySelector("form")?.insertAdjacentElement("afterbegin", warning);
  }

  const dueDate = dueInput?.value || outputRows.get(editingOutputNumber)?.payment_due_date || "";
  const overdue = isPastDueDate(dueDate);
  const className = `document-edit-warning${overdue ? "" : " neutral"}`;
  const message = overdue
    ? `O prazo de pagamento venceu em ${formatDateOnly(dueDate)}. Atualize a data do pagamento antes de confirmar o recebimento.`
    : "Revise todos os dados e a data do pagamento. Ao confirmar, a venda será marcada como paga e a saída será finalizada.";
  if (warning.className !== className) warning.className = className;
  if (warning.textContent !== message) warning.textContent = message;

  const finalizeButton = [...modal.querySelectorAll("button")].find((button) => {
    const text = String(button.textContent || "").trim().toLowerCase();
    return text.includes("finalizar saída") || text.includes("salvar e recalcular") || text.includes("confirmar pagamento");
  });
  if (finalizeButton) {
    const label = "Finalizar saída e confirmar pagamento";
    const textNode = [...finalizeButton.childNodes].find((node) => node.nodeType === Node.TEXT_NODE);
    if (textNode && textNode.textContent.trim() !== label) textNode.textContent = label;
    else if (!textNode && finalizeButton.textContent.trim() !== label) finalizeButton.textContent = label;
  }
}

function enhanceAll() {
  ensureStyles();
  enhanceOutputTable();
  ensurePaymentStatusDetail();
  ensureCreditFormState();
}

function openCreditSettlement(button, row) {
  const number = row?.number || outputNumberFromButton(button);
  const tableRow = button.closest("tr");
  const editButton = [...(tableRow?.querySelectorAll("button") || [])].find((candidate) =>
    String(candidate.getAttribute("title") || "").toLowerCase().startsWith("editar"),
  );
  if (!number || !editButton) return false;

  settlingCreditOutputNumber = number;
  editingOutputNumber = number;
  editButton.click();
  window.setTimeout(enhanceAll, 0);
  return true;
}

function saveCreditAsPending(event, modal) {
  const form = modal?.querySelector("form");
  if (form && !form.reportValidity()) return true;

  const draftButton = [...(modal?.querySelectorAll("button") || [])].find((candidate) =>
    String(candidate.textContent || "").trim().toLowerCase().includes("salvar rascunho"),
  );
  if (!draftButton) return false;

  event.preventDefault();
  event.stopPropagation();
  event.stopImmediatePropagation();
  draftButton.click();
  return true;
}

export function installCreditPaymentWorkflow(client) {
  if (installed || typeof document === "undefined") return;
  installed = true;

  client.interceptors.response.use((response) => {
    const method = String(response.config?.method || "get").toLowerCase();
    if (method === "get" && isOutputCollection(response.config?.url)) {
      for (const row of rowsFromPayload(response.data)) {
        if (row?.number) outputRows.set(row.number, row);
      }
    } else if (response.data?.number?.startsWith?.("SAI-")) {
      outputRows.set(response.data.number, response.data);
    }

    if (isOutputConfirm(response.config)) {
      settlingCreditOutputNumber = "";
      editingOutputNumber = "";
    }

    window.setTimeout(enhanceAll, 0);
    return response;
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;

    const text = String(button.textContent || "").trim().toLowerCase();
    const title = String(button.getAttribute("title") || "").toLowerCase();
    const number = outputNumberFromButton(button);
    const row = number ? outputRows.get(number) : null;

    if (text.includes("nova saída")) {
      editingOutputNumber = "";
      settlingCreditOutputNumber = "";
    }

    if (title.startsWith("editar")) {
      editingOutputNumber = number;
      if (settlingCreditOutputNumber !== number) settlingCreditOutputNumber = "";
    }

    if (title === "confirmar" && row?.payment_method === "ON_ACCOUNT" && row.status === "DRAFT") {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openCreditSettlement(button, row);
      return;
    }

    const modal = currentOutputFormModal();
    const paymentSelect = modal ? paymentSelectFrom(modal) : null;
    if (text.includes("finalizar saída") && paymentSelect?.value === "ON_ACCOUNT" && !isSettlingCurrentCredit()) {
      if (saveCreditAsPending(event, modal)) return;
    }

    if (text === "cancelar" && modal) {
      editingOutputNumber = "";
      settlingCreditOutputNumber = "";
    }

    window.setTimeout(enhanceAll, 0);
  }, true);

  const observer = new MutationObserver(() => window.setTimeout(enhanceAll, 0));
  observer.observe(document.body, { childList: true, subtree: true });
  window.setTimeout(enhanceAll, 0);
}
