let installed = false;

function normalize(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("pt-BR")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ");
}

function optionKey(option) {
  const text = normalize(option.textContent)
    .replace(/\s*\(inativ[oa]\)\s*$/i, "")
    .replace(/\s*—\s*contem\s+1\s+unidade$/i, "");
  return text;
}

function cleanSelect(select) {
  if (!(select instanceof HTMLSelectElement)) return;

  const options = [...select.options];
  const selectedValue = String(select.value || "");
  const seen = new Map();

  for (const option of options) {
    const text = normalize(option.textContent);
    if (!option.value && text.startsWith("selecione")) {
      option.disabled = true;
      option.hidden = true;
      continue;
    }

    if (!option.value) continue;
    const key = optionKey(option);
    if (!key) continue;

    const previous = seen.get(key);
    if (!previous) {
      seen.set(key, option);
      continue;
    }

    if (String(option.value) === selectedValue && String(previous.value) !== selectedValue) {
      previous.remove();
      seen.set(key, option);
    } else {
      option.remove();
    }
  }
}

function cleanAllSelects() {
  document.querySelectorAll("select").forEach(cleanSelect);
}

export function installSelectOptionCleanup() {
  if (installed) return;
  installed = true;

  const observer = new MutationObserver(() => {
    window.setTimeout(cleanAllSelects, 0);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  cleanAllSelects();
}
