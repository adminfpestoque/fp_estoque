const IBGE_LOCALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome";
const CACHE_KEY = "fp_ibge_municipios_v1";

export const BRAZIL_STATES = [
  ["AC", "Acre"], ["AL", "Alagoas"], ["AP", "Amapá"], ["AM", "Amazonas"],
  ["BA", "Bahia"], ["CE", "Ceará"], ["DF", "Distrito Federal"], ["ES", "Espírito Santo"],
  ["GO", "Goiás"], ["MA", "Maranhão"], ["MT", "Mato Grosso"], ["MS", "Mato Grosso do Sul"],
  ["MG", "Minas Gerais"], ["PA", "Pará"], ["PB", "Paraíba"], ["PR", "Paraná"],
  ["PE", "Pernambuco"], ["PI", "Piauí"], ["RJ", "Rio de Janeiro"], ["RN", "Rio Grande do Norte"],
  ["RS", "Rio Grande do Sul"], ["RO", "Rondônia"], ["RR", "Roraima"], ["SC", "Santa Catarina"],
  ["SP", "São Paulo"], ["SE", "Sergipe"], ["TO", "Tocantins"],
];

let citiesPromise;

function cityState(city) {
  return city?.microrregiao?.mesorregiao?.UF?.sigla
    || city?.["regiao-imediata"]?.["regiao-intermediaria"]?.UF?.sigla
    || "";
}

function normalizeCities(payload) {
  return (Array.isArray(payload) ? payload : [])
    .map((city) => ({
      id: city.id,
      name: String(city.nome || "").trim(),
      state: cityState(city),
    }))
    .filter((city) => city.name && city.state)
    .sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

function readCache() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
    return Array.isArray(cached) && cached.length ? cached : null;
  } catch {
    return null;
  }
}

export async function loadBrazilCities() {
  const cached = readCache();
  if (cached) return cached;

  citiesPromise ||= fetch(IBGE_LOCALITIES_URL, { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error("Não foi possível consultar a lista de cidades.");
      return response.json();
    })
    .then(normalizeCities)
    .then((cities) => {
      try {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify(cities));
      } catch {
        // O formulário continua funcionando sem armazenamento local.
      }
      return cities;
    })
    .catch((error) => {
      citiesPromise = undefined;
      throw error;
    });

  return citiesPromise;
}

export function normalizeLocationSearch(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR")
    .trim();
}
