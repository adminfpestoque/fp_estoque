let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function fieldByLabel(form, expected) {
  return [...form.querySelectorAll("label.field")].find((field) =>
    normalize(field.querySelector(":scope > span")?.textContent) === normalize(expected),
  );
}

function fieldStartingWith(form, prefix) {
  return [...form.querySelectorAll("label.field")].find((field) =>
    normalize(field.querySelector(":scope > span")?.textContent).startsWith(normalize(prefix)),
  );
}

function integerValue(value) {
  const parsed = Number.parseInt(String(value || "0"), 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
}

function setReactInputValue(input, value) {
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  );
  descriptor?.set?.call(input, String(value));
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function groupingDetails(form) {
  const typeField = fieldByLabel(form, "Tipo já cadastrado");
  const typeSelect = typeField?.querySelector("select");
  const unitsField = fieldStartingWith(form, "Unidades contidas em cada");
  const unitsInput = unitsField?.querySelector("input");
  const selectedOption = typeSelect?.selectedOptions?.[0];
  const typeName = String(selectedOption?.textContent || "")
    .replace(/\s*\(inativo\)\s*$/i, "")
    .trim();
  const unitsPerPackage = integerValue(unitsInput?.value);
  const hasGrouping = Boolean(typeSelect?.value && typeName && unitsPerPackage >= 2);

  return {
    hasGrouping,
    typeName,
    unitsPerPackage,
  };
}

function refreshMinimumSection(form) {
  const section = form.querySelector("[data-minimum-stock-section]");
  if (!section) return;

  const unitField = fieldByLabel(form, "Estoque mínimo em unidades");
  const unitInput = unitField?.querySelector("input");
  const packageField = section.querySelector("[data-minimum-package-field]");
  const packageLabel = packageField?.querySelector(":scope > span");
  const packageInput = packageField?.querySelector("input");
  const packageHint = packageField?.querySelector("small");
  if (!unitInput || !packageField || !packageInput || !packageLabel) return;

  const { hasGrouping, typeName, unitsPerPackage } = groupingDetails(form);
  packageField.hidden = !hasGrouping;
  packageInput.disabled = !hasGrouping;

  if (!hasGrouping) {
    packageInput.value = "0";
    return;
  }

  const minimumUnits = integerValue(unitInput.value);
  const packageMinimum = minimumUnits === 0
    ? 0
    : Math.ceil(minimumUnits / unitsPerPackage);

  packageLabel.textContent = `Estoque mínimo em ${typeName}`;
  packageInput.value = String(packageMinimum);
  if (packageHint) {
    packageHint.textContent = `1 ${typeName} equivale a ${unitsPerPackage} unidades. Ao alterar este campo, o mínimo em unidades será atualizado automaticamente.`;
  }
}

function buildMinimumSection(form) {
  const unitField = fieldByLabel(form, "Estoque mínimo em unidades");
  const activeField = form.querySelector(".product-active-check");
  if (!unitField || !activeField) return null;

  let section = form.querySelector("[data-minimum-stock-section]");
  if (!section) {
    section = document.createElement("div");
    section.className = "simple-packaging-config full";
    section.dataset.minimumStockSection = "true";
    section.innerHTML = `
      <div class="section-heading compact-heading">
        <div>
          <h3>Estoque mínimo</h3>
          <p>Informe o limite por unidade individual ou pelo tipo de empacotamento selecionado.</p>
        </div>
      </div>
      <div class="simple-packaging-fields" data-minimum-stock-fields></div>
    `;
    activeField.before(section);
  }

  const fields = section.querySelector("[data-minimum-stock-fields]");
  if (unitField.parentElement !== fields) fields.appendChild(unitField);

  let packageField = section.querySelector("[data-minimum-package-field]");
  if (!packageField) {
    packageField = document.createElement("label");
    packageField.className = "field";
    packageField.dataset.minimumPackageField = "true";
    packageField.innerHTML = `
      <span>Estoque mínimo no tipo escolhido</span>
      <input type="number" min="0" step="1" value="0" inputmode="numeric" />
      <small>Selecione um tipo de empacotamento para usar este campo.</small>
    `;
    fields.appendChild(packageField);
  }

  return section;
}

function prepareProductMinimumStock() {
  const form = document.querySelector("form.product-form-simple");
  if (!form) return;

  const section = buildMinimumSection(form);
  if (!section) return;

  if (form.dataset.minimumStockInstalled !== "true") {
    form.dataset.minimumStockInstalled = "true";

    form.addEventListener("input", (event) => {
      const unitField = fieldByLabel(form, "Estoque mínimo em unidades");
      const unitInput = unitField?.querySelector("input");
      const packageInput = section.querySelector("[data-minimum-package-field] input");
      const unitsInput = fieldStartingWith(form, "Unidades contidas em cada")?.querySelector("input");

      if (event.target === packageInput) {
        const { hasGrouping, unitsPerPackage } = groupingDetails(form);
        if (!hasGrouping || !unitInput) return;
        const packages = integerValue(packageInput.value);
        setReactInputValue(unitInput, packages * unitsPerPackage);
        return;
      }

      if (event.target === unitInput || event.target === unitsInput) {
        window.setTimeout(() => refreshMinimumSection(form), 0);
      }
    });

    form.addEventListener("change", () => {
      window.setTimeout(() => refreshMinimumSection(form), 0);
    });
  }

  refreshMinimumSection(form);
}

export function installProductMinimumStock() {
  if (installed) return;
  installed = true;

  const observer = new MutationObserver(() => {
    window.setTimeout(prepareProductMinimumStock, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  prepareProductMinimumStock();
}
