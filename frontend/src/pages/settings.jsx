import {
  React,
  useEffect,
  useMemo,
  useState,
  api,
  unwrap,
  getError,
  Button,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Eye,
  Pencil,
  Plus,
  RefreshCw,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
} from "../shared.jsx";
import {
  DEFAULT_PREFERENCES,
  applyAndStorePreferences,
  normalizePreferences,
} from "../preferences.js";

const OPERATIONAL_DEFAULTS = {
  expiration_alert_days: "30",
  credit_due_alert_days: "3",
  stock_alerts_enabled: "true",
  expiration_alerts_enabled: "true",
  inventory_divergence_alerts_enabled: "true",
  credit_due_alerts_enabled: "true",
};

const SETTING_DESCRIPTIONS = {
  expiration_alert_days: "Quantidade de dias de antecedência para avisar sobre vencimentos.",
  credit_due_alert_days: "Quantidade de dias de antecedência para avisar sobre pagamentos a prazo.",
  stock_alerts_enabled: "Gerar alertas para produtos sem estoque ou abaixo do mínimo.",
  expiration_alerts_enabled: "Gerar alertas para lotes vencidos ou próximos do vencimento.",
  inventory_divergence_alerts_enabled: "Gerar alertas quando a contagem do inventário divergir do sistema.",
  credit_due_alerts_enabled: "Gerar alertas para pagamentos a prazo próximos do vencimento ou vencidos.",
};

const THEME_OPTIONS = [
  { value: "LIGHT", label: "Claro", description: "Visual atual, com superfícies claras e detalhes em amarelo." },
  { value: "DARK", label: "Escuro", description: "Reduz o brilho usando preto e cinza com destaque amarelo." },
  { value: "HIGH_CONTRAST", label: "Alto contraste", description: "Preto, amarelo e branco com bordas reforçadas." },
];

function valuesFromRows(rows) {
  const values = { ...OPERATIONAL_DEFAULTS };
  rows.forEach((row) => {
    if (row.key in values) values[row.key] = String(row.value);
  });
  return values;
}

function isTrue(value) {
  return ["true", "1", "sim"].includes(String(value).toLowerCase());
}

export function SettingsPage({ notify, me, onMeChanged }) {
  const [tab, setTab] = useState("accessibility");
  const [preferences, setPreferences] = useState(() => normalizePreferences(me?.profile || {}));
  const [settingsRows, setSettingsRows] = useState([]);
  const [operational, setOperational] = useState({ ...OPERATIONAL_DEFAULTS });
  const [advancedForm, setAdvancedForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [savingOperational, setSavingOperational] = useState(false);

  const settingsByKey = useMemo(
    () => Object.fromEntries(settingsRows.map((row) => [row.key, row])),
    [settingsRows],
  );

  async function loadSettings() {
    setLoading(true);
    try {
      const response = await api.get("settings/?page_size=200");
      const rows = unwrap(response.data);
      setSettingsRows(rows);
      setOperational(valuesFromRows(rows));
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPreferences(normalizePreferences(me?.profile || {}));
  }, [me?.id, me?.profile?.theme, me?.profile?.font_scale, me?.profile?.reduced_motion, me?.profile?.enhanced_focus]);

  useEffect(() => { loadSettings(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function changePreference(key, value) {
    setPreferences((current) => {
      const next = normalizePreferences({ ...current, [key]: value });
      applyAndStorePreferences(next);
      return next;
    });
  }

  async function savePreferences() {
    setSavingPreferences(true);
    try {
      const response = await api.patch("users/me/", preferences);
      const saved = normalizePreferences(response.data.profile || preferences);
      applyAndStorePreferences(saved);
      setPreferences(saved);
      onMeChanged?.(response.data);
      notify("Preferências de aparência e acessibilidade salvas.");
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setSavingPreferences(false);
    }
  }

  async function restorePreferences() {
    const defaults = { ...DEFAULT_PREFERENCES };
    setPreferences(defaults);
    applyAndStorePreferences(defaults);
    setSavingPreferences(true);
    try {
      const response = await api.patch("users/me/", defaults);
      onMeChanged?.(response.data);
      notify("Preferências restauradas para o padrão.");
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setSavingPreferences(false);
    }
  }

  async function upsertSetting(key, value, description) {
    const payload = { key, value: String(value), description };
    if (settingsByKey[key]) {
      return api.put(`settings/${encodeURIComponent(key)}/`, payload);
    }
    return api.post("settings/", payload);
  }

  async function saveOperational(event) {
    event.preventDefault();
    setSavingOperational(true);
    try {
      const expirationDays = Number(operational.expiration_alert_days);
      if (!Number.isInteger(expirationDays) || expirationDays < 1 || expirationDays > 365) {
        throw new Error("Informe entre 1 e 365 dias para os alertas de validade.");
      }
      const creditDays = Number(operational.credit_due_alert_days);
      if (!Number.isInteger(creditDays) || creditDays < 0 || creditDays > 365) {
        throw new Error("Informe entre 0 e 365 dias para os alertas de pagamentos a prazo.");
      }
      await Promise.all(
        Object.entries(operational).map(([key, value]) =>
          upsertSetting(key, value, SETTING_DESCRIPTIONS[key] || ""),
        ),
      );
      await api.post("alerts/refresh/");
      await loadSettings();
      notify("Configurações de alertas atualizadas e recalculadas.");
    } catch (error) {
      notify(error?.response ? getError(error) : error.message, "error");
    } finally {
      setSavingOperational(false);
    }
  }

  async function saveAdvanced(event) {
    event.preventDefault();
    try {
      await upsertSetting(
        advancedForm.key.trim(),
        advancedForm.value,
        advancedForm.description || "",
      );
      setAdvancedForm(null);
      await loadSettings();
      notify("Configuração salva com sucesso.");
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  return (
    <>
      <div className="settings-tabs" role="tablist" aria-label="Seções de configurações">
        <button type="button" className={tab === "accessibility" ? "active" : ""} onClick={() => setTab("accessibility")}>
          <Eye size={18} /> Aparência e acessibilidade
        </button>
        <button type="button" className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
          <ShieldCheck size={18} /> Alertas e operação
        </button>
        <button type="button" className={tab === "advanced" ? "active" : ""} onClick={() => setTab("advanced")}>
          <SlidersHorizontal size={18} /> Parâmetros avançados
        </button>
      </div>

      {tab === "accessibility" && (
        <section className="panel settings-section" aria-labelledby="accessibility-heading">
          <div className="settings-heading">
            <div>
              <h2 id="accessibility-heading">Aparência e acessibilidade</h2>
              <p>As preferências ficam vinculadas à sua conta e são aplicadas em todo o sistema.</p>
            </div>
            <StatusBadge value="active" label="Preferência individual" />
          </div>

          <div className="settings-group">
            <h3>Tema da interface</h3>
            <div className="theme-options">
              {THEME_OPTIONS.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={`theme-option theme-${option.value.toLowerCase().replaceAll("_", "-")} ${preferences.theme === option.value ? "selected" : ""}`}
                  aria-pressed={preferences.theme === option.value}
                  onClick={() => changePreference("theme", option.value)}
                >
                  <span className="theme-swatch" aria-hidden="true"><i /><i /><i /></span>
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </button>
              ))}
            </div>
          </div>

          <div className="settings-grid two-columns">
            <div className="settings-group">
              <Field label="Tamanho do texto" hint="Aumenta textos e controles sem usar o zoom do navegador.">
                <select value={preferences.font_scale} onChange={(event) => changePreference("font_scale", event.target.value)}>
                  <option value="NORMAL">Padrão</option>
                  <option value="LARGE">Grande</option>
                  <option value="EXTRA_LARGE">Muito grande</option>
                </select>
              </Field>
            </div>
            <div className="accessibility-preview" aria-live="polite">
              <Settings size={22} />
              <div><strong>Prévia da leitura</strong><p>Texto, campos, tabelas e botões acompanham as opções selecionadas.</p></div>
            </div>
          </div>

          <div className="settings-switches">
            <label className="settings-switch">
              <input type="checkbox" checked={preferences.reduced_motion} onChange={(event) => changePreference("reduced_motion", event.target.checked)} />
              <span><strong>Reduzir animações</strong><small>Remove movimentos e transições que podem causar desconforto.</small></span>
            </label>
            <label className="settings-switch">
              <input type="checkbox" checked={preferences.enhanced_focus} onChange={(event) => changePreference("enhanced_focus", event.target.checked)} />
              <span><strong>Destaque reforçado de foco</strong><small>Mostra um contorno amarelo forte ao navegar pelo teclado.</small></span>
            </label>
          </div>

          <div className="form-actions settings-actions">
            <Button type="button" variant="secondary" onClick={restorePreferences} disabled={savingPreferences}>Restaurar padrão</Button>
            <Button type="button" onClick={savePreferences} disabled={savingPreferences}>
              {savingPreferences ? "Salvando..." : "Salvar preferências"}
            </Button>
          </div>
        </section>
      )}

      {tab === "alerts" && (
        <section className="panel settings-section" aria-labelledby="alerts-settings-heading">
          <div className="settings-heading">
            <div>
              <h2 id="alerts-settings-heading">Alertas e operação</h2>
              <p>Estes parâmetros alteram diretamente a geração de alertas e notificações do estoque.</p>
            </div>
            <Button type="button" variant="secondary" icon={RefreshCw} onClick={loadSettings} disabled={loading}>Atualizar</Button>
          </div>
          <form onSubmit={saveOperational}>
            <div className="settings-grid two-columns">
              <Field label="Avisar vencimento com antecedência" hint="De 1 a 365 dias.">
                <div className="input-with-suffix">
                  <input
                    type="number"
                    min="1"
                    max="365"
                    step="1"
                    value={operational.expiration_alert_days}
                    onChange={(event) => setOperational({ ...operational, expiration_alert_days: event.target.value })}
                    required
                  />
                  <span>dias</span>
                </div>
              </Field>
              <Field label="Avisar pagamento a prazo com antecedência" hint="De 0 a 365 dias. Use 0 para avisar apenas no vencimento.">
                <div className="input-with-suffix">
                  <input
                    type="number"
                    min="0"
                    max="365"
                    step="1"
                    value={operational.credit_due_alert_days}
                    onChange={(event) => setOperational({ ...operational, credit_due_alert_days: event.target.value })}
                    required
                  />
                  <span>dias</span>
                </div>
              </Field>
              <div className="settings-info-box">
                <ShieldCheck size={21} />
                <p>Ao salvar, os alertas atuais são recalculados sem criar duplicações.</p>
              </div>
            </div>

            <div className="settings-switches">
              {[
                ["stock_alerts_enabled", "Alertas de estoque", "Avisar quando um produto estiver sem estoque ou abaixo do mínimo."],
                ["expiration_alerts_enabled", "Alertas de validade", "Avisar sobre lotes vencidos ou próximos do vencimento."],
                ["inventory_divergence_alerts_enabled", "Alertas de inventário", "Avisar quando a contagem física divergir do sistema."],
                ["credit_due_alerts_enabled", "Alertas de pagamentos a prazo", "Avisar sobre vendas fiadas próximas do vencimento ou vencidas."],
              ].map(([key, label, description]) => (
                <label className="settings-switch" key={key}>
                  <input
                    type="checkbox"
                    checked={isTrue(operational[key])}
                    onChange={(event) => setOperational({ ...operational, [key]: String(event.target.checked) })}
                  />
                  <span><strong>{label}</strong><small>{description}</small></span>
                </label>
              ))}
            </div>

            <div className="form-actions settings-actions">
              <Button disabled={savingOperational || loading}>
                {savingOperational ? "Salvando..." : "Salvar e recalcular alertas"}
              </Button>
            </div>
          </form>
        </section>
      )}

      {tab === "advanced" && (
        <section className="panel settings-section">
          <div className="settings-heading">
            <div>
              <h2>Parâmetros avançados</h2>
              <p>Área administrativa para consultar e manter configurações adicionais do sistema.</p>
            </div>
            <Button icon={Plus} onClick={() => setAdvancedForm({ key: "", value: "", description: "" })}>Nova configuração</Button>
          </div>
          <DataTable
            rows={settingsRows}
            loading={loading}
            emptyText="Nenhuma configuração adicional foi cadastrada."
            columns={[
              { key: "key", label: "Chave" },
              { key: "value", label: "Valor" },
              { key: "description", label: "Descrição", render: (row) => row.description || "-" },
              {
                key: "actions",
                label: "Ações",
                render: (row) => (
                  <button className="icon-btn" onClick={() => setAdvancedForm({ ...row })} title={`Editar ${row.key}`} aria-label={`Editar ${row.key}`}>
                    <Pencil size={16} />
                  </button>
                ),
              },
            ]}
          />
        </section>
      )}

      {advancedForm && (
        <Modal title={advancedForm.id ? "Editar configuração" : "Nova configuração"} onClose={() => setAdvancedForm(null)}>
          <form className="form-grid" onSubmit={saveAdvanced}>
            <Field label="Chave" required>
              <input disabled={Boolean(advancedForm.id)} value={advancedForm.key} onChange={(event) => setAdvancedForm({ ...advancedForm, key: event.target.value })} required />
            </Field>
            <Field label="Valor" required>
              <input value={advancedForm.value} onChange={(event) => setAdvancedForm({ ...advancedForm, value: event.target.value })} required />
            </Field>
            <Field label="Descrição">
              <textarea value={advancedForm.description || ""} onChange={(event) => setAdvancedForm({ ...advancedForm, description: event.target.value })} />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setAdvancedForm(null)}>Cancelar</Button>
              <Button>Salvar configuração</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
