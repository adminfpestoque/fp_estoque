let installed = false;

function onlyDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function formatDocument(value) {
  const digits = onlyDigits(value);

  if (digits.length === 14) {
    return digits.replace(
      /^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,
      "$1.$2.$3/$4-$5",
    );
  }

  if (digits.length === 11) {
    return digits.replace(
      /^(\d{3})(\d{3})(\d{3})(\d{2})$/,
      "$1.$2.$3-$4",
    );
  }

  return value || "—";
}

function updateSupplierTable() {
  for (const table of document.querySelectorAll("table")) {
    const headers = [...table.querySelectorAll("thead th")];
    const labels = headers.map((header) => String(header.textContent || "").trim());

    const supplierIndex = labels.indexOf("Fornecedor");
    const documentIndex = labels.indexOf("CNPJ/CPF");
    const amountIndex = labels.findIndex((label) =>
      label === "Valor recebido" || label === "Valor total pago",
    );

    if (supplierIndex < 0 || documentIndex < 0) continue;

    if (amountIndex >= 0) {
      headers[amountIndex].textContent = "Valor total pago";
    }

    for (const row of table.querySelectorAll("tbody tr")) {
      const cells = row.querySelectorAll("td");
      const documentCell = cells[documentIndex];
      if (!documentCell) continue;

      const rawValue = documentCell.dataset.rawDocument || documentCell.textContent;
      documentCell.dataset.rawDocument = rawValue;
      documentCell.textContent = formatDocument(rawValue);
    }
  }
}

export function installSupplierTableFormat() {
  if (installed) return;
  installed = true;

  const observer = new MutationObserver(() => {
    window.setTimeout(updateSupplierTable, 0);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
  });

  updateSupplierTable();
}
