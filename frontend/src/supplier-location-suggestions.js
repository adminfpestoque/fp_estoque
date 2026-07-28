import { api } from "./shared.jsx";
import { loadBrazilCities, normalizeLocationSearch } from "./brazilLocations.js";

let installed = false;
let citiesPromise = null;
const searchTimers = new WeakMap();
const resultMaps = new WeakMap();

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

function ensureDatalist(form, input, id) {
  let datalist = form.querySelector(`#${id}`);
  if (!datalist) {
    datalist = document.createElement("datalist");
    datalist.id = id;
    form.appendChild(datalist);
  }
  input.setAttribute("list", id);
  return datalist;
}

function renderOptions(datalist, values) {
  const unique = [];
  const seen = new Set();
  for (const value of values) {
    const key = normalize(value.value);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    unique.push(value);
  }

  datalist.replaceChildren(...unique.slice(0, 30).map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    if (item.label) option.label = item.label;
    return option;
  }));
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
  if (storedUf.length === 2) return { city: cityName, state: storedUf };

  try {
    const cities = await cityList();
    const matches = cities.filter(
      (item) => normalizeLocationSearch(item.name) === normalizeLocationSearch(cityName),
    );
    if (matches.length === 1) {
      form.dataset.supplierSelectedUf = matches[0].state;
      return { city: matches[0].name, state: matches[0].state };
    }
  } catch {
    return null;
  }
  return null;
}

function clearSuggestionLists(form) {
  form.querySelector("#supplier-address-options")?.replaceChildren();
  form.querySelector("#supplier-district-options")?.replaceChildren();
}

function updateSuggestionState(form, location) {
  const addressInput = fieldByLabel(form, "Endereço")?.querySelector("input");
  const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
  const hasSelectedCity = Boolean(location?.city && location?.state);

  for (const input of [addressInput, districtInput]) {
    if (!input) continue;
    input.disabled = false;
    input.removeAttribute("aria-disabled");
  }

  if (addressInput) {
    addressInput.placeholder = hasSelectedCity
      ? "Digite 3 letras para escolher ou escreva o endereço"
      : "Digite o endereço";
  }
  if (districtInput) {
    districtInput.placeholder = hasSelectedCity
      ? "Digite 3 letras para escolher ou escreva o bairro"
      : "Digite o bairro";
  }

  if (!hasSelectedCity) clearSuggestionLists(form);
}

async function searchSuggestions(form, input, mode) {
  const location = await resolveCity(form);
  updateSuggestionState(form, location);

  const datalist = form.querySelector(
    mode === "address" ? "#supplier-address-options" : "#supplier-district-options",
  );
  if (!datalist) return;

  if (!location) {
    datalist.replaceChildren();
    return;
  }

  const query = String(input.value || "").trim();
  if (query.length < 3) {
    datalist.replaceChildren();
    return;
  }

  try {
    const response = await api.get("suppliers/address-suggestions/", {
      params: {
        state: location.state,
        city: location.city,
        q: query,
      },
    });
    const results = Array.isArray(response.data?.results) ? response.data.results : [];
    resultMaps.set(input, results);

    if (mode === "address") {
      renderOptions(datalist, results
        .filter((item) => item.address)
        .map((item) => ({
          value: item.address,
          label: [item.district, item.cep].filter(Boolean).join(" — "),
        })));
    } else {
      renderOptions(datalist, results
        .filter((item) => item.district)
        .map((item) => ({
          value: item.district,
          label: [item.address, item.cep].filter(Boolean).join(" — "),
        })));
    }
  } catch {
    datalist.replaceChildren();
  }
}

function scheduleSearch(form, input, mode) {
  window.clearTimeout(searchTimers.get(input));
  const timer = window.setTimeout(() => searchSuggestions(form, input, mode), 350);
  searchTimers.set(input, timer);
}

function applySelectedAddress(form, addressInput) {
  const results = resultMaps.get(addressInput) || [];
  const selected = results.find(
    (item) => normalize(item.address) === normalize(addressInput.value),
  );
  if (!selected) return;

  const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
  if (selected.district && districtInput && !districtInput.value.trim()) {
    setReactInputValue(districtInput, selected.district);
  }
}

async function handleCityChange(form) {
  const cityInput = fieldByLabel(form, "Cidade")?.querySelector("input");
  const currentCity = normalize(cityInput?.value);

  if (form.dataset.lastSupplierCity !== currentCity) {
    form.dataset.supplierSelectedUf = "";
    clearSuggestionLists(form);
  }

  form.dataset.lastSupplierCity = currentCity;
  const location = await resolveCity(form);
  updateSuggestionState(form, location);
}

function prepareForm() {
  const form = supplierForm();
  if (!form) return;

  const cityInput = fieldByLabel(form, "Cidade")?.querySelector("input");
  const addressInput = fieldByLabel(form, "Endereço")?.querySelector("input");
  const districtInput = fieldByLabel(form, "Bairro")?.querySelector("input");
  if (!cityInput || !addressInput || !districtInput) return;

  ensureDatalist(form, addressInput, "supplier-address-options");
  ensureDatalist(form, districtInput, "supplier-district-options");

  if (form.dataset.locationSuggestionsInstalled !== "true") {
    form.dataset.locationSuggestionsInstalled = "true";

    cityInput.addEventListener("input", () => handleCityChange(form));
    cityInput.addEventListener("change", () => handleCityChange(form));

    addressInput.addEventListener("input", () => scheduleSearch(form, addressInput, "address"));
    addressInput.addEventListener("change", () => applySelectedAddress(form, addressInput));
    districtInput.addEventListener("input", () => scheduleSearch(form, districtInput, "district"));
  }

  handleCityChange(form);
}

export function installSupplierLocationSuggestions() {
  if (installed) return;
  installed = true;

  document.addEventListener("mousedown", (event) => {
    const button = event.target.closest(".city-suggestions button");
    const form = button?.closest("form");
    if (!button || !form || !fieldByLabel(form, "Nome do fornecedor")) return;
    const state = String(button.querySelector("strong")?.textContent || "").trim().toUpperCase();
    if (state.length === 2) form.dataset.supplierSelectedUf = state;
    window.setTimeout(() => handleCityChange(form), 0);
  }, true);

  const observer = new MutationObserver(() => {
    window.setTimeout(prepareForm, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  prepareForm();
}
