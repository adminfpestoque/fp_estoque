const outputStatusByNumber = new Map();
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

function rememberOutput(row) {
  if (row?.number?.startsWith?.("SAI-")) {
    outputStatusByNumber.set(row.number, row.payment_status || row.status || "");
  }
}

function ensureStyles() {
  if (document.querySelector("style[data-output-payment-consistency]")) return;
  const style = document.createElement("style");
  style.dataset.outputPaymentConsistency = "true";
  style.textContent = `
    tr[data-payment-cancelled="true"] [data-credit-status-cell] .credit-payment-status {
      display: none !important;
    }
    tr[data-payment-cancelled="true"] [data-credit-status-cell]::after {
      content: "Cancelado";
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 9px;
      border: 1px solid currentColor;
      border-radius: 999px;
      color: #94a3b8;
      background: rgba(148, 163, 184, .10);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    [data-credit-status-detail][data-payment-cancelled="true"] strong {
      display: none !important;
    }
    [data-credit-status-detail][data-payment-cancelled="true"]::after {
      content: "Cancelado";
      font-weight: 700;
    }
  `;
  document.head.appendChild(style);
}

function applyStatusConsistency() {
  ensureStyles();

  for (const table of document.querySelectorAll("table")) {
    const headers = [...table.querySelectorAll("thead th")].map((cell) => cell.textContent.trim());
    if (!headers.includes("Número") || !headers.includes("Status pagamento")) continue;

    for (const row of table.querySelectorAll("tbody tr")) {
      const number = row.querySelector("td strong")?.textContent?.trim() || "";
      const cancelled = outputStatusByNumber.get(number) === "CANCELLED";
      if (cancelled) {
        row.dataset.paymentCancelled = "true";
        row.querySelector("[data-credit-status-cell]")?.setAttribute("aria-label", "Cancelado");
      } else {
        delete row.dataset.paymentCancelled;
        row.querySelector("[data-credit-status-cell]")?.removeAttribute("aria-label");
      }
    }
  }

  for (const modal of document.querySelectorAll(".modal")) {
    const title = modal.querySelector(".modal-header h2")?.textContent?.trim() || "";
    const number = title.match(/^Saída\s+(SAI-[A-Z0-9-]+)$/i)?.[1] || "";
    const detail = modal.querySelector("[data-credit-status-detail]");
    if (!detail) continue;
    if (outputStatusByNumber.get(number) === "CANCELLED") {
      detail.dataset.paymentCancelled = "true";
      detail.setAttribute("aria-label", "Status do pagamento: Cancelado");
    } else {
      delete detail.dataset.paymentCancelled;
      detail.removeAttribute("aria-label");
    }
  }
}

export function installOutputPaymentStatusConsistency(client) {
  if (installed || typeof document === "undefined") return;
  installed = true;

  client.interceptors.response.use((response) => {
    const path = normalizePath(response.config?.url);
    if (/^outputs\/?$/.test(path)) {
      rowsFromPayload(response.data).forEach(rememberOutput);
    } else {
      rememberOutput(response.data);
    }
    window.setTimeout(applyStatusConsistency, 0);
    return response;
  });

  const observer = new MutationObserver(() => window.setTimeout(applyStatusConsistency, 0));
  observer.observe(document.body, { childList: true, subtree: true });
  window.setTimeout(applyStatusConsistency, 0);
}
