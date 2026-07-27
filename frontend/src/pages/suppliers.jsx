import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  fmtMoney,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  Pagination,
  DataTable,
  StatusBadge,
  Pencil,
  Plus,
  Power,
  PowerOff,
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
  active: true,
};

function formatCep(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
  return digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
}

function chooseBestCep(results, address, district) {
  const targetAddress = normalizeLocationSearch(address);
  const targetDistrict = normalizeLocationSearch(district);
  return [...results]
    .map((item) => {
      const street = normalizeLocationSearch(item.logradouro);
      const neighborhood = normalizeLocationSearch(item.bairro);
      let score = 0;
      if (street === targetAddress) score += 10;
      else if (street.includes(targetAddress) || targetAddress.includes(street)) score += 6;
      if (targetDistrict && neighborhood === targetDistrict) score += 4;
      return { item, score };
    })
    .sort((a, b) => b.score - a.score)[0]?.item || null;
}

async function findCepByAddress({ state, city, address, district }) {
  const uf = String(state || "").trim().toUpperCase();
  const cityName = String(city || "").trim();
  const street = String(address || "").trim();
  if (!uf || cityName.length < 3 || street.length < 3) return null;

  const url = `https://viacep.com.br/ws/${encodeURIComponent(uf)}/${encodeURIComponent(cityName)}/${encodeURIComponent(street)}/json/`;
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Não foi possível consultar o CEP.");
  const payload = await response.json();
  return chooseBestCep(Array.isArray(payload) ? payload : [], street, district);
}

function CityStateFields({ form, setForm, onLocationChange }) {
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
    setForm((current) => {
      const next = { ...current, city: city.name, state: city.state, cep: "" };
      window.setTimeout(() => onLocationChange?.(next), 0);
      return next;
    });
    setShowSuggestions(false);
  }

  function changeState(state) {
    const currentCity = cities.find(
      (city) => normalizeLocationSearch(city.name) === normalizeLocationSearch(form.city),
    );
    setForm((current) => {
      const next = {
        ...current,
        state,
        city: currentCity && currentCity.state === state ? current.city : "",
        cep: "",
      };
      window.setTimeout(() => onLocationChange?.(next), 0);
      return next;
    });
    setShowSuggestions(true);
  }

  function confirmTypedCity() {
    const query = normalizeLocationSearch(form.city);
    if (!query) return;
    const exactMatches = cities.filter(
      (city) => normalizeLocationSearch(city.name) === query && (!form.state || city.state === form.state),
    );
    if (exactMatches.length === 1) selectCity(exactMatches[0]);
    else onLocationChange?.(form);
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
              setForm((current) => ({ ...current, city: event.target.value, cep: "" }));
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
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [cepLookup, setCepLookup] = useState({ loading: false, message: "" });

  function openForm(value) {
    setCepLookup({ loading: false, message: "" });
    setForm(value);
  }

  async function resolveCep(candidate = form) {
    if (!candidate) return candidate;
    if (!candidate.state || String(candidate.city || "").trim().length < 3 || String(candidate.address || "").trim().length < 3) {
      setCepLookup({
        loading: false,
        message: "Selecione a cidade e informe o endereço para buscar o CEP automaticamente.",
      });
      return candidate;
    }

    setCepLookup({ loading: true, message: "Buscando CEP pelo endereço..." });
    try {
      const result = await findCepByAddress(candidate);
      if (!result?.cep) {
        setCepLookup({
          loading: false,
          message: "CEP não localizado. Revise a cidade e o endereço; o preenchimento continua opcional.",
        });
        return candidate;
      }

      const next = {
        ...candidate,
        cep: formatCep(result.cep),
        district: candidate.district || result.bairro || "",
      };
      setForm((current) => current ? { ...current, cep: next.cep, district: next.district } : current);
      setCepLookup({ loading: false, message: `CEP localizado automaticamente: ${next.cep}.` });
      return next;
    } catch {
      setCepLookup({
        loading: false,
        message: "Não foi possível consultar o CEP agora. O fornecedor pode ser salvo normalmente.",
      });
      return candidate;
    }
  }

  async function save(event) {
    event.preventDefault();
    try {
      const resolvedForm = form.cep ? form : await resolveCep(form);
      const payload = {
        name: resolvedForm.name.trim(),
        corporate_name: resolvedForm.corporate_name || "",
        document: resolvedForm.document?.trim() || null,
        state_registration: "",
        contact_name: resolvedForm.contact_name?.trim() || "",
        phone: resolvedForm.phone?.trim() || "",
        whatsapp: resolvedForm.whatsapp?.trim() || "",
        email: resolvedForm.email?.trim() || "",
        cep: resolvedForm.cep?.trim() || "",
        address: resolvedForm.address?.trim() || "",
        address_number: resolvedForm.address_number?.trim() || "",
        district: resolvedForm.district?.trim() || "",
        city: resolvedForm.city?.trim() || "",
        state: resolvedForm.state || "",
        notes: "",
        active: Boolean(resolvedForm.active),
      };

      if (resolvedForm.id) await api.patch(`suppliers/${resolvedForm.id}/`, payload);
      else await api.post("suppliers/", payload);
      notify("Fornecedor salvo com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  async function toggleStatus() {
    if (!pendingAction) return;
    setActionBusy(true);
    try {
      const activate = !pendingAction.active;
      await api.post(`suppliers/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      notify(`Fornecedor ${activate ? "ativado" : "inativado"} com sucesso.`);
      setPendingAction(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => openForm({ ...supplierInitial })}>Novo fornecedor</Button>
        )}
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
          placeholder="Fornecedor, documento, responsável ou cidade..."
        />
        <select
          value={list.params.active ?? ""}
          onChange={(event) => list.setParams({ ...list.params, active: event.target.value, page: 1 })}
        >
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
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
              key: "active",
              label: "Situação",
              render: (row) => (
                <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} />
              ),
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => openForm({ ...row })} title="Editar fornecedor" aria-label={`Editar ${row.name}`}><Pencil size={16} /></button>
                  <button
                    className={row.active ? "warning" : "success"}
                    onClick={() => setPendingAction(row)}
                    title={row.active ? "Inativar fornecedor" : "Ativar fornecedor"}
                    aria-label={`${row.active ? "Inativar" : "Ativar"} ${row.name}`}
                  >
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
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
            <Field label="Endereço" hint="Depois de informar cidade e endereço, o CEP será buscado automaticamente.">
              <input
                value={form.address || ""}
                onChange={(event) => setForm({ ...form, address: event.target.value, cep: "" })}
                onBlur={() => resolveCep(form)}
              />
            </Field>
            <Field label="Número">
              <input value={form.address_number || ""} onChange={(event) => setForm({ ...form, address_number: event.target.value })} />
            </Field>
            <Field label="Bairro">
              <input
                value={form.district || ""}
                onChange={(event) => setForm({ ...form, district: event.target.value, cep: "" })}
                onBlur={() => resolveCep(form)}
              />
            </Field>

            <CityStateFields form={form} setForm={setForm} onLocationChange={resolveCep} />

            <Field
              label="CEP automático"
              hint={cepLookup.message || "Selecione a cidade e informe o endereço para buscar o CEP automaticamente."}
            >
              <input value={form.cep || ""} readOnly placeholder={cepLookup.loading ? "Buscando..." : "Preenchido automaticamente"} />
            </Field>

            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar fornecedor</Button>
            </div>
          </form>
        </Modal>
      )}

      {pendingAction && (
        <ConfirmModal
          title={pendingAction.active ? "Inativar fornecedor" : "Ativar fornecedor"}
          message={`${pendingAction.active ? "Inativar" : "Ativar"} “${pendingAction.name}”?`}
          detail={pendingAction.active
            ? "O fornecedor e todo o histórico de entradas serão preservados, mas ele ficará indisponível para novos vínculos."
            : "O fornecedor voltará a ficar disponível para novos vínculos e cadastros."}
          confirmLabel={pendingAction.active ? "Inativar fornecedor" : "Ativar fornecedor"}
          confirmVariant={pendingAction.active ? "warning" : "success"}
          busy={actionBusy}
          onClose={() => setPendingAction(null)}
          onConfirm={toggleStatus}
        />
      )}
    </>
  );
}
