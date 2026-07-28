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

function installStyle() {
  if (document.getElementById("supplier-required-label-bridge-style")) return;
  const style = document.createElement("style");
  style.id = "supplier-required-label-bridge-style";
  style.textContent = ".supplier-required-label::after{content:' *';}";
  document.head.appendChild(style);
}

function normalizeSupplierRequiredLabel() {
  document.querySelectorAll("label.field > span").forEach((label) => {
    if (normalize(label.textContent) !== "nome do fornecedor") return;
    label.textContent = "Nome do fornecedor";
    label.classList.add("supplier-required-label");
  });
}

export function installSupplierRequiredLabelBridge() {
  if (installed) return;
  installed = true;
  installStyle();

  const observer = new MutationObserver(() => {
    window.setTimeout(normalizeSupplierRequiredLabel, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  normalizeSupplierRequiredLabel();
}
