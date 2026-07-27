let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function fieldByLabel(form, label) {
  return [...form.querySelectorAll("label.field")].find((field) =>
    normalize(field.querySelector(":scope > span")?.textContent) === normalize(label),
  );
}

const CONFIGS = [
  {
    key: "packaging",
    fieldLabels: ["Adicionar nova embalagem", "Nome da nova embalagem"],
    closedLabel: "Adicionar nova embalagem",
    openLabel: "Criar embalagem",
    fieldLabel: "Nome da nova embalagem",
  },
  {
    key: "grouping",
    fieldLabels: ["Cadastrar novo tipo", "Nome do novo tipo"],
    closedLabel: "Adicionar novo tipo",
    openLabel: "Criar tipo",
    fieldLabel: "Nome do novo tipo",
  },
];

function findConfiguredField(form, config) {
  for (const label of config.fieldLabels) {
    const field = fieldByLabel(form, label);
    if (field) return field;
  }
  return null;
}

function applyCreatorState(form, config) {
  const field = findConfiguredField(form, config);
  const grid = field?.closest(".simple-packaging-select-grid");
  const action = grid?.querySelector(".simple-packaging-create");
  const button = action?.querySelector("button");
  const input = field?.querySelector("input");
  const label = field?.querySelector(":scope > span");
  if (!field || !grid || !action || !button || !input) return;

  const stateKey = `${config.key}CreatorOpen`;
  const isOpen = form.dataset[stateKey] === "true";
  const buttonLabel = isOpen ? config.openLabel : `+ ${config.closedLabel}`;

  field.hidden = !isOpen;
  field.setAttribute("aria-hidden", isOpen ? "false" : "true");
  input.disabled = !isOpen;
  action.style.gridColumn = isOpen ? "" : "2 / span 2";
  button.dataset.inlineCreator = config.key;
  button.dataset.creatorOpen = isOpen ? "true" : "false";
  if (button.textContent !== buttonLabel) button.textContent = buttonLabel;
  if (label && label.textContent !== config.fieldLabel) label.textContent = config.fieldLabel;
}

function prepareProductCreators() {
  const form = document.querySelector("form.product-form-simple");
  if (!form) return;

  for (const config of CONFIGS) applyCreatorState(form, config);

  if (form.dataset.inlineCreatorsInstalled === "true") return;
  form.dataset.inlineCreatorsInstalled = "true";

  form.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-inline-creator]");
    if (!button || !form.contains(button)) return;

    const config = CONFIGS.find((item) => item.key === button.dataset.inlineCreator);
    if (!config) return;

    const stateKey = `${config.key}CreatorOpen`;
    const isOpen = form.dataset[stateKey] === "true";
    if (isOpen) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    form.dataset[stateKey] = "true";
    applyCreatorState(form, config);
    findConfiguredField(form, config)?.querySelector("input")?.focus();
  }, true);
}

export function installProductInlineCreate() {
  if (installed) return;
  installed = true;

  const observer = new MutationObserver(() => {
    window.setTimeout(prepareProductCreators, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  prepareProductCreators();
}
