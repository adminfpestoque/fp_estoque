import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  fmtMoney,
  getError,
  Button,
  Modal,
  Field,
  Pagination,
  DataTable,
  Pencil,
  Plus,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";
import {
  BRAZIL_STATES,
  loadBrazilCities,
  normalizeLocationSearch,
} from "../brazilLocations.js";

const supplierInitial = {
  name: "",
  corporate_name: "",
  document: "",
  state_registration: "",
  contact_name: "",
  phone: "",
  whatsapp: "",
  email: "",
  cep: "",
  address: "",
  address_number: "",
  district: "",
  city: "",
  state: "",
  notes: "",
  active: true,
};

function CityStateFields({ form, setForm }) {
  const [cities, setCities] = useState([]);
  const [loadingCities, setLoadingCities] = useState(true);
  const [citiesError, setCitiesError] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    let active = true;
    setLoadingCities(true);
    loadBrazilCities()
      .then((items) => {
        if (active) setCities(items);
      })
      .catch(() => {
        if (active) setCitiesError("A lista automática não pôde ser carregada. Ainda é possível digitar a cidade manualmente.");
      })
      .finally(() => {
        if (active) setLoadingCities(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const filteredCities = useMemo(() => {
    const query = normalizeLocationSearch(form.city);
    return cities
      .filter((city) => !form.state || city.state === form.state)
      .filter((city) => !query || normalizeLocationSearch(city.name).includes(query))
      .slice(0, 30);
  }, [cities, form.city, form.state]);

  function selectCity(city) {
    setForm((current) => ({ ...current, city: city.name, state: city.state }));
    setShowSuggestions(false);
  }

  function changeState(state) {
    const currentCity = cities.find(
      (city) => normalizeLocationSearch(city.name) === normalizeLocationSearch(form.city),
    );
    setForm((current) => ({
      ...current,
      state,
      city: currentCity && currentCity.state === state ? current.city : "",
    }));
    setShowSuggestions(true);
  }

  function confirmTypedCity() {
    const query = normalizeLocationSearch(form.city);
    if (!query) return;
    const exactMatches = cities.filter(
      (city) => normalizeLocationSearch(city.name) === query && (!form.state || city.state === form.state),
    );
    if (exactMatches.length === 1) selectCity(exactMatches[0]);
  }

  return (
    <>
      <Field label="Estado (UF)">
        <select value={form.state || ""} onChange={(event) => changeState(event.target.value)}>
          <option value="">Selecione ou escolha primeiro a cidade</option>
          {BRAZIL_STATES.map(([code, name]) => (
            <option key={code} value={code}>{code} — {name}</option>
          ))}
        </select>
      </Field>

      <Field
        label="Cidade"
        hint={loadingCities ? "Carregando cidades do Brasil..." : citiesError || "Digite para filtrar ou escolha uma cidade da lista."}
      >
        <div className="city-combobox">
          <input
            type="text"
            value={form.city || ""}
            onChange={(event) => {
              setForm((current) => ({ ...current, city: event.target.value }));
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => {
              window.setTimeout(() => {
                confirmTypedCity();
                setShowSuggestions(false);
              }, 150);
            }}
            placeholder={form.state ? `Digite uma cidade de ${form.state}` : "Digite o nome da cidade"}
            autoComplete="off"
            role="combobox"
            aria-expanded={showSuggestions}
            aria-autocomplete="list"
          />
          {showSuggestions && !loadingCities && cities.length > 0 && (
            <div className="city-suggestions" role="listbox">
              {filteredCities.length ? filteredCities.map((city) => (
                <button
                  key={city.id}
                  type="button"
                  role="option"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectCity(city)}
                >
                  <span>{city.name}</span>
                  <strong>{city.state}</strong>
                </button>
              )) : (
                <div className="city-suggestions-empty">Nenhuma cidade encontrada.</div>
              )}
            </div>
          )}
        </div>
      </Field>
    </>
  );
}

export function SuppliersPage({ notify, me }) {
  const list = useList("suppliers/");
  const [form, setForm] = useState(null);

  async function save(event) {
    event.preventDefault();
    try {
      const payload = {
        name: form.name.trim(),
        corporate_name: form.corporate_name || "",
        document: form.document?.trim() || null,
        state_registration: form.state_registration?.trim() || "",
        contact_name: form.contact_name?.trim() || "",
        phone: form.phone?.trim() || "",
        whatsapp: form.whatsapp?.trim() || "",
        email: form.email?.trim() || "",
        cep: form.cep?.trim() || "",
        address: form.address?.trim() || "",
        address_number: form.address_number?.trim() || "",
        district: form.district?.trim() || "",
        city: form.city?.trim() || "",
        state: form.state || "",
        notes: form.notes?.trim() || "",
        active: Boolean(form.active),
      };

      if (form.id) await api.patch(`suppliers/${form.id}/`, payload);
      else await api.post("suppliers/", payload);
      notify("Fornecedor salvo com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <>
      <PageHeader
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => setForm({ ...supplierInitial })}>Novo fornecedor</Button>
        )}
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
          placeholder="Fornecedor, documento, responsável ou cidade..."
        />
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "name", label: "Fornecedor", render: (row) => <strong>{row.name}</strong> },
            { key: "document", label: "CNPJ/CPF" },
            { key: "contact_name", label: "Responsável" },
            { key: "phone", label: "Telefone do responsável" },
            { key: "whatsapp", label: "WhatsApp do responsável" },
            { key: "city", label: "Cidade/UF", render: (row) => `${row.city || "-"}${row.state ? `/${row.state}` : ""}` },
            { key: "entries_count", label: "Entradas" },
            { key: "entries_value", label: "Valor recebido", render: (row) => fmtMoney(row.entries_value) },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => setForm({ ...row })} aria-label={`Editar ${row.name}`}><Pencil size={16} /></button>
                </div>
              ) : "-",
            },
          ]}
        />
        <Pagination
          page={list.params.page}
          count={list.count}
          onChange={(page) => list.setParams({ ...list.params, page })}
        />
      </section>

      {form && (
        <Modal title={form.id ? "Editar fornecedor" : "Novo fornecedor"} onClose={() => setForm(null)} size="xl">
          <form className="form-grid cols-3" onSubmit={save}>
            <Field label="Nome do fornecedor" required>
              <input value={form.name || ""} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </Field>
            <Field label="CNPJ ou CPF">
              <input value={form.document || ""} onChange={(event) => setForm({ ...form, document: event.target.value })} />
            </Field>
            <Field label="Inscrição estadual">
              <input value={form.state_registration || ""} onChange={(event) => setForm({ ...form, state_registration: event.target.value })} />
            </Field>
            <Field label="Responsável">
              <input value={form.contact_name || ""} onChange={(event) => setForm({ ...form, contact_name: event.target.value })} />
            </Field>
            <Field label="Telefone do responsável">
              <input value={form.phone || ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
            </Field>
            <Field label="WhatsApp do responsável">
              <input value={form.whatsapp || ""} onChange={(event) => setForm({ ...form, whatsapp: event.target.value })} />
            </Field>
            <Field label="E-mail do responsável">
              <input type="email" value={form.email || ""} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            </Field>
            <Field label="CEP">
              <input value={form.cep || ""} onChange={(event) => setForm({ ...form, cep: event.target.value })} />
            </Field>
            <Field label="Endereço">
              <input value={form.address || ""} onChange={(event) => setForm({ ...form, address: event.target.value })} />
            </Field>
            <Field label="Número">
              <input value={form.address_number || ""} onChange={(event) => setForm({ ...form, address_number: event.target.value })} />
            </Field>
            <Field label="Bairro">
              <input value={form.district || ""} onChange={(event) => setForm({ ...form, district: event.target.value })} />
            </Field>

            <CityStateFields form={form} setForm={setForm} />

            <Field label="Observações">
              <textarea value={form.notes || ""} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
            </Field>
            <Field label="Situação">
              <select value={String(form.active)} onChange={(event) => setForm({ ...form, active: event.target.value === "true" })}>
                <option value="true">Ativo</option>
                <option value="false">Inativo</option>
              </select>
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar fornecedor</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
