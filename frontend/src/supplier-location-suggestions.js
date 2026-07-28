import { api } from "./shared.jsx";
import { loadBrazilCities, normalizeLocationSearch } from "./brazilLocations.js";

let installed = false;
let citiesPromise = null;
const searchTimers = new WeakMap();
const resultMaps = new WeakMap();
const requestTokens = new WeakMap();

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}

function fieldByLabel(form, expected) {
  return [...form.querySelectorAll("label.field")].find((field) =>
    normalize(field.querySelector(":scope > span")?.textContent) === normalize(expected),
  );
}

function supplierForm() {
  return [...document.querySelectorAll("form")].find((form) =>
    Boolean(fieldByLabel(form, "Nome do fornecedor")),
  );
}

function setReactInputValue(input, value) {
  if (!input) return;
  const descriptor = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype,
    "value",
  );
  descriptor?.set?.call(input, String(value || ""));
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function installStyles() {
  if (document.getElementById("supplier-location-suggestions-style")) return;
  const style = document.createElement("style");
  style.id = "supplier-location-suggestions-style";
  style.textContent = `
    .supplier-location-field { position: relative; align-content: start; }
    .supplier-location-menu {
      position: static;
      display: none;
      width: 100%;
      max-height: 240px;
      overflow-y: auto;
      margin-top: 2px;
      border: 1px solid var(--border, #374151);
      border-radius: 10px;
      background: var(--panel, #17191d);
      box-shadow: 0 10px 25px rgba(0, 0, 0, .25);
      padding: 6px;
    }
    .supplier-location-menu.is-open { display: block; }
    .supplier-location-option {
      width: 100%;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 2px;
      padding: 10px 11px;
      text-align: left;
    }
    .supplier-location-option:hover,
    .supplier-location-option:focus-visible {
      background: rgba(234, 179, 8, .14);
      outline: none;
    }
    .supplier-location-option strong { font-size: 13px; }
    .supplier-location-option small { opacity: .72; }
    .supplier-location-message {
      padding: 10px 11px;
      font-size: 12px;
      line-height: 1.35;
      opacity: .76;
    }
    .supplier-location-attribution {
      padding: 7px 11px 5px;
      border-top: 1px solid var(--border, #374151);
      font-size: 10px;
      opacity: .62;
    }
  `;
  document.head.appendChild(style);
}

function ensureMenu(field, mode) {
  field.classList.add("supplier-location-field");
  let menu = field.querySelector(`.supplier-location-menu[data-mode="${mode}"]`);
  if (!menu) {
    menu = document.createElement("div");
    menu.className = "supplier-location-menu";
    menu.dataset.mode = mode;
    menu.setAttribute("role", "listbox");
    const hint = field.querySelector(":scope > small");
    if (hint) field.insertBefore(menu, hint);
    else field.appendChild(menu);
  }
  return menu;
}

function menuForInput(input) {
  return input?.closest("label.field")?.querySelector(".supplier-location-menu");
}

function closeMenu(input) {
  const menu = menuForInput(input);
  menu?.classList.remove("is-open");
}

function closeAllMenus(form) {
  form.querySelectorAll(".supplier-location-menu").forEach((menu) => {
    menu.classList.remove("is-open");
    menu.replaceChildren();
  });
}

function showMessage(input, message) {
  const menu = menuForInput(input);
  if (!menu) return;
  const item = document.createElement("div");
  item.className = "supplier-location-message";
  item.textContent = message;
  menu.replaceChildren(item);
  menu.classList.add("is-open");
}

function cityList() {
  if (!citiesPromise) citiesPromise = loadBrazilCities();
  return citiesPromise;
}

async function resolveCity(form) {
  const cityInput = fieldByLabel(form, "Cidade")?.querySelector("input");
  const cityName = String(cityInput?.value || "").trim();
  if (!cityName) return null;

  const storedUf = String(form.dataset.supplierSelectedUf || "").trim().toUpperCase();

  try {
    const cities = await cityList();
    const matches = cities.filter((item) =>
      normalizeLocationSearch(item.name) === normalizeLocationSearch(cityName)
      && (!storedUf || item.state === storedUf),
    );
    if (matches.length === 1) {
      form.dataset.supplierSelectedUf = matches[0].state;
      form.dataset.supplierSelectedCityId = String(matches[0].id || "");
      return {
        city: matches[0].name,
        state: matches[0].state,
        id: matches[0].id,
      };
    }
  } catch {
    if (storedUf.length !== 2) return null;
  }

  if (storedUf.length === 2) {
    return {
      city: cityName,
      state: storedUf,
      id: form.dataset.supplierSelectedCityId || "",
    };
  }
  return null;
}

function updateSuggestionState(form, location) {
  const addressInput = fieldByLabel(form, "Endereço")?.querySelector("input");
  const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
  const hasSelectedCity = Boolean(location?.city && location?.state);

  for (const input of [addressInput, districtInput]) {
    if (!input) continue;
    input.disabled = false;
    input.removeAttribute("aria-disabled");
    input.removeAttribute("list");
  }

  if (addressInput) {
    addressInput.placeholder = hasSelectedCity
      ? "Digite para filtrar ou escreva o endereço"
      : "Digite o endereço";
  }
  if (districtInput) {
    districtInput.placeholder = hasSelectedCity
      ? "Digite para filtrar ou escreva o bairro"
      : "Digite o bairro";
  }

  if (!hasSelectedCity) closeAllMenus(form);
}

function uniqueResults(results, mode) {
  const seen = new Set();
  return results.filter((item) => {
    const value = mode === "address" ? item.address : item.district;
    const key = normalize(value);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function renderResults(form, input, mode, results, attribution = "") {
  const menu = menuForInput(input);
  if (!menu) return;

  const filtered = uniqueResults(results, mode).slice(0, 20);
  resultMaps.set(input, results);

  if (!filtered.length) {
    showMessage(
      input,
      mode === "address"
        ? "Nenhum endereço foi encontrado para esse texto. Você pode continuar digitando normalmente."
        : "Nenhum bairro foi encontrado para esse texto. Você pode continuar digitando normalmente.",
    );
    return;
  }

  const buttons = filtered.map((item) => {
    const value = mode === "address" ? item.address : item.district;
    const details = mode === "address"
      ? [item.district, item.cep].filter(Boolean).join(" — ")
      : [item.address, item.cep].filter(Boolean).join(" — ");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "supplier-location-option";
    button.setAttribute("role", "option");

    const title = document.createElement("strong");
    title.textContent = value;
    button.appendChild(title);

    if (details) {
      const subtitle = document.createElement("small");
      subtitle.textContent = details;
      button.appendChild(subtitle);
    }

    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      setReactInputValue(input, value);

      if (mode === "address") {
        const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
        if (item.district && districtInput && !districtInput.value.trim()) {
          setReactInputValue(districtInput, item.district);
        }
      }

      closeMenu(input);
      input.focus();
    });

    return button;
  });

  const children = [...buttons];
  if (attribution) {
    const source = document.createElement("div");
    source.className = "supplier-location-attribution";
    source.textContent = attribution;
    children.push(source);
  }

  menu.replaceChildren(...children);
  menu.classList.add("is-open");
}

async function searchSuggestions(form, input, mode) {
  const location = await resolveCity(form);
  updateSuggestionState(form, location);

  if (!location) {
    closeMenu(input);
    return;
  }

  const query = String(input.value || "").trim();
  if (query.length < 3) {
    closeMenu(input);
    return;
  }

  const token = Symbol("supplier-location-request");
  requestTokens.set(input, token);
  showMessage(input, "Buscando sugestões...");

  try {
    const response = await api.get("suppliers/address-suggestions/", {
      params: {
        state: location.state,
        city: location.city,
        city_id: location.id || undefined,
        q: query,
      },
    });

    if (requestTokens.get(input) !== token) return;
    if (String(input.value || "").trim() !== query) return;

    const results = Array.isArray(response.data?.results) ? response.data.results : [];
    renderResults(form, input, mode, results, response.data?.attribution || "");
  } catch (error) {
    if (requestTokens.get(input) !== token) return;
    const status = error?.response?.status;
    showMessage(
      input,
      status === 404
        ? "A busca de sugestões ainda não está disponível no servidor. Você pode continuar digitando normalmente."
        : "Não foi possível carregar as sugestões agora. Você pode continuar digitando normalmente.",
    );
  }
}

function scheduleSearch(form, input, mode) {
  window.clearTimeout(searchTimers.get(input));
  const timer = window.setTimeout(() => searchSuggestions(form, input, mode), 500);
  searchTimers.set(input, timer);
}

async function handleCityChange(form) {
  const cityInput = fieldByLabel(form, "Cidade")?.querySelector("input");
  const currentCity = normalize(cityInput?.value);

  if (form.dataset.lastSupplierCity !== currentCity) {
    form.dataset.supplierSelectedUf = "";
    form.dataset.supplierSelectedCityId = "";
    closeAllMenus(form);
  }

  form.dataset.lastSupplierCity = currentCity;
  const location = await resolveCity(form);
  updateSuggestionState(form, location);

  if (!location) return;
  const addressInput = fieldByLabel(form, "Endereço")?.querySelector("input");
  const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
  if (String(addressInput?.value || "").trim().length >= 3) {
    scheduleSearch(form, addressInput, "address");
  }
  if (String(districtInput?.value || "").trim().length >= 3) {
    scheduleSearch(form, districtInput, "district");
  }
}

function prepareForm() {
  const form = supplierForm();
  if (!form) return;

  installStyles();

  const cityInput = fieldByLabel(form, "Cidade")?.querySelector("input");
  const addressField = fieldByLabel(form, "Endereço");
  const districtField = fieldByLabel(form, "Bairro");
  const addressInput = addressField?.querySelector("input");
  const districtInput = districtField?.querySelector("input");
  if (!cityInput || !addressInput || !districtInput) return;

  ensureMenu(addressField, "address");
  ensureMenu(districtField, "district");
  addressInput.removeAttribute("list");
  districtInput.removeAttribute("list");

  if (form.dataset.locationSuggestionsInstalled !== "true") {
    form.dataset.locationSuggestionsInstalled = "true";

    cityInput.addEventListener("input", () => handleCityChange(form));
    cityInput.addEventListener("change", () => handleCityChange(form));

    addressInput.addEventListener("input", () => scheduleSearch(form, addressInput, "address"));
    addressInput.addEventListener("focus", () => {
      if (addressInput.value.trim().length >= 3) scheduleSearch(form, addressInput, "address");
    });
    addressInput.addEventListener("blur", () => window.setTimeout(() => closeMenu(addressInput), 160));

    districtInput.addEventListener("input", () => scheduleSearch(form, districtInput, "district"));
    districtInput.addEventListener("focus", () => {
      if (districtInput.value.trim().length >= 3) scheduleSearch(form, districtInput, "district");
    });
    districtInput.addEventListener("blur", () => window.setTimeout(() => closeMenu(districtInput), 160));
  }

  handleCityChange(form);
}

export function installSupplierLocationSuggestions() {
  if (installed) return;
  installed = true;

  document.addEventListener("mousedown", (event) => {
    const cityButton = event.target.closest(".city-suggestions button");
    const form = cityButton?.closest("form");
    if (cityButton && form && fieldByLabel(form, "Nome do fornecedor")) {
      const state = String(cityButton.querySelector("strong")?.textContent || "").trim().toUpperCase();
      if (state.length === 2) form.dataset.supplierSelectedUf = state;
      window.setTimeout(() => handleCityChange(form), 0);
      return;
    }

    const supplier = supplierForm();
    if (supplier && !event.target.closest(".supplier-location-menu")) {
      supplier.querySelectorAll(".supplier-location-menu").forEach((menu) => menu.classList.remove("is-open"));
    }
  }, true);

  const observer = new MutationObserver(() => {
    window.setTimeout(prepareForm, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  prepareForm();
}
