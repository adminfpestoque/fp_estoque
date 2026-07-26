import {
  React,
  useEffect,
  useState,
  api,
  unwrap,
  getError,
  Button,
  ConfirmModal,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Pencil,
  Plus,
  Power,
  PowerOff,
  Trash2,
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";

function sortedTypes(rows) {
  return [...rows].sort((a, b) => a.name.localeCompare(b.name, "pt-BR"));
}

export function CategoriesPage({ notify, me }) {
  const list = useList("categories/");
  const [form, setForm] = useState(null);
  const [packagingTypes, setPackagingTypes] = useState([]);
  const [typeForm, setTypeForm] = useState(null);
  const [newTypeName, setNewTypeName] = useState("");
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);

  async function loadPackagingTypes() {
    try {
      const response = await api.get("packaging-types/?page_size=500");
      setPackagingTypes(sortedTypes(unwrap(response.data)));
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  useEffect(() => {
    loadPackagingTypes();
  }, []);

  function openCategory(row = null) {
    setNewTypeName("");
    setForm(row
      ? {
          ...row,
          packaging_types: (row.packaging_types || []).map(String),
        }
      : { name: "", description: "", active: true, packaging_types: [] });
  }

  async function saveCategory(event) {
    event.preventDefault();
    const payload = {
      name: form.name.trim(),
      description: form.description?.trim() || "",
      active: Boolean(form.active),
      packaging_types: (form.packaging_types || []).map(Number),
    };
    try {
      if (form.id) await api.put(`categories/${form.id}/`, payload);
      else await api.post("categories/", payload);
      notify("Categoria salva com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    }
  }

  function toggleCategoryType(typeId) {
    const key = String(typeId);
    setForm((current) => ({
      ...current,
      packaging_types: (current.packaging_types || []).includes(key)
        ? current.packaging_types.filter((item) => item !== key)
        : [...(current.packaging_types || []), key],
    }));
  }

  async function createTypeForCategory() {
    const name = newTypeName.trim();
    if (!name) {
      notify("Digite o nome do novo tipo de embalagem.", "error");
      return;
    }
    setBusy(true);
    try {
      const response = await api.post("packaging-types/", { name, active: true });
      const created = response.data;
      setPackagingTypes((current) => sortedTypes([...current.filter((item) => item.id !== created.id), created]));
      setForm((current) => ({
        ...current,
        packaging_types: [...new Set([...(current.packaging_types || []), String(created.id)])],
      }));
      setNewTypeName("");
      notify(`Tipo de embalagem “${created.name}” criado e selecionado.`);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function savePackagingType(event) {
    event.preventDefault();
    const payload = { name: typeForm.name.trim(), active: Boolean(typeForm.active) };
    setBusy(true);
    try {
      if (typeForm.id) await api.patch(`packaging-types/${typeForm.id}/`, payload);
      else await api.post("packaging-types/", payload);
      notify("Tipo de embalagem salvo com sucesso.");
      setTypeForm(null);
      loadPackagingTypes();
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function executePendingAction() {
    if (!pendingAction) return;
    setBusy(true);
    try {
      if (pendingAction.entity === "category") {
        const activate = !pendingAction.row.active;
        await api.post(`categories/${pendingAction.row.id}/${activate ? "activate" : "deactivate"}/`);
        notify(`Categoria ${activate ? "ativada" : "inativada"} com sucesso.`);
        list.reload();
      } else if (pendingAction.action === "delete") {
        await api.delete(`packaging-types/${pendingAction.row.id}/`);
        notify("Tipo de embalagem excluído com sucesso.");
        loadPackagingTypes();
        list.reload();
      } else {
        const activate = !pendingAction.row.active;
        await api.post(`packaging-types/${pendingAction.row.id}/${activate ? "activate" : "deactivate"}/`);
        notify(`Tipo de embalagem ${activate ? "ativado" : "inativado"} com sucesso.`);
        loadPackagingTypes();
      }
      setPendingAction(null);
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  const confirmation = pendingAction && (() => {
    const row = pendingAction.row;
    if (pendingAction.entity === "category") {
      return {
        title: row.active ? "Inativar categoria" : "Ativar categoria",
        message: `${row.active ? "Inativar" : "Ativar"} “${row.name}”?`,
        detail: row.active
          ? "A categoria será preservada no histórico, mas ficará indisponível para novos produtos."
          : "A categoria voltará a ficar disponível para novos produtos.",
        confirmLabel: row.active ? "Inativar categoria" : "Ativar categoria",
        confirmVariant: row.active ? "warning" : "success",
      };
    }
    if (pendingAction.action === "delete") {
      return {
        title: "Excluir tipo de embalagem",
        message: `Deseja excluir “${row.name}”?`,
        detail: "A exclusão só será permitida quando o tipo não estiver associado a categorias, produtos, entradas ou saídas. Caso exista histórico, inative o tipo.",
        confirmLabel: "Excluir tipo",
        confirmVariant: "danger",
      };
    }
    return {
      title: row.active ? "Inativar tipo de embalagem" : "Ativar tipo de embalagem",
      message: `${row.active ? "Inativar" : "Ativar"} “${row.name}”?`,
      detail: row.active
        ? "O tipo continuará nos registros históricos, mas não poderá ser selecionado em novos cadastros."
        : "O tipo voltará a ficar disponível em categorias e produtos.",
      confirmLabel: row.active ? "Inativar tipo" : "Ativar tipo",
      confirmVariant: row.active ? "warning" : "success",
    };
  })();

  return (
    <>
      <PageHeader
        title="Categorias e tipos de embalagem"
        description="Organize as categorias dos produtos e mantenha uma única lista de tipos como Caixa, Fardo, Pacote e Grade."
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => openCategory()}>
            Nova categoria
          </Button>
        )}
      />

      <div className="filters-bar">
        <SearchBar
          value={list.params.search || ""}
          onChange={(search) => list.setParams({ ...list.params, search, page: 1 })}
          placeholder="Nome ou descrição da categoria..."
        />
        <select
          value={list.params.active ?? ""}
          onChange={(event) => list.setParams({ ...list.params, active: event.target.value, page: 1 })}
        >
          <option value="">Ativas e inativas</option>
          <option value="true">Somente ativas</option>
          <option value="false">Somente inativas</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "name", label: "Categoria do produto", render: (row) => <strong>{row.name}</strong> },
            { key: "description", label: "Descrição da categoria" },
            {
              key: "packaging_type_names",
              label: "Tipos de embalagem disponíveis",
              render: (row) => row.packaging_type_names?.length
                ? <div className="tag-list">{row.packaging_type_names.map((name) => <span className="mini-tag" key={name}>{name}</span>)}</div>
                : <span className="muted-text">Nenhum tipo definido</span>,
            },
            {
              key: "active",
              label: "Situação da categoria",
              render: (row) => <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativa" : "Inativa"} />,
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => openCategory(row)} title="Editar categoria" aria-label={`Editar ${row.name}`}><Pencil size={16} /></button>
                  <button className={row.active ? "warning" : "success"} onClick={() => setPendingAction({ entity: "category", row })} title={row.active ? "Inativar categoria" : "Ativar categoria"}>
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                </div>
              ) : "-",
            },
          ]}
        />
      </section>

      <section className="panel packaging-type-manager">
        <div className="section-heading">
          <div>
            <h2>Lista única de tipos de embalagem</h2>
            <p>Os tipos criados aqui aparecem automaticamente em Produtos. Tipos criados em Produtos também aparecem aqui.</p>
          </div>
          {me.permissions.is_admin && <Button icon={Plus} variant="secondary" onClick={() => setTypeForm({ name: "", active: true })}>Novo tipo de embalagem</Button>}
        </div>
        <DataTable
          rows={packagingTypes}
          columns={[
            { key: "name", label: "Nome do tipo de embalagem", render: (row) => <strong>{row.name}</strong> },
            { key: "categories_count", label: "Categorias associadas", render: (row) => row.categories_count ?? 0 },
            { key: "products_count", label: "Produtos associados", render: (row) => row.products_count ?? 0 },
            { key: "active", label: "Situação do tipo", render: (row) => <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativo" : "Inativo"} /> },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => setTypeForm({ ...row })} title="Editar tipo de embalagem"><Pencil size={16} /></button>
                  <button className={row.active ? "warning" : "success"} onClick={() => setPendingAction({ entity: "type", action: "toggle", row })} title={row.active ? "Inativar tipo" : "Ativar tipo"}>
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                  <button className="danger" onClick={() => setPendingAction({ entity: "type", action: "delete", row })} title="Excluir tipo de embalagem"><Trash2 size={16} /></button>
                </div>
              ) : "-",
            },
          ]}
        />
      </section>

      {form && (
        <Modal title={form.id ? "Editar categoria" : "Nova categoria"} onClose={() => setForm(null)} size="lg">
          <form className="form-grid" onSubmit={saveCategory}>
            <Field label="Nome completo da categoria" required>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Refrigerantes" required />
            </Field>
            <Field label="Descrição da categoria">
              <textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </Field>

            <div className="category-packaging-types full">
              <div>
                <strong>Tipos de embalagem permitidos nesta categoria</strong>
                <p>Selecione os tipos que normalmente serão usados pelos produtos desta categoria.</p>
              </div>
              <div className="type-choice-grid">
                {packagingTypes.map((type) => (
                  <label className={`type-choice ${!type.active ? "inactive" : ""}`} key={type.id}>
                    <input type="checkbox" checked={(form.packaging_types || []).includes(String(type.id))} onChange={() => toggleCategoryType(type.id)} disabled={!type.active && !(form.packaging_types || []).includes(String(type.id))} />
                    <span>{type.name}{type.active ? "" : " (inativo)"}</span>
                  </label>
                ))}
              </div>
              <div className="inline-create-type">
                <Field label="Adicionar um tipo que ainda não existe">
                  <input value={newTypeName} onChange={(event) => setNewTypeName(event.target.value)} placeholder="Ex.: Caixa térmica" />
                </Field>
                <Button type="button" variant="secondary" icon={Plus} onClick={createTypeForCategory} disabled={busy}>Criar e selecionar</Button>
              </div>
            </div>

            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar categoria</Button>
            </div>
          </form>
        </Modal>
      )}

      {typeForm && (
        <Modal title={typeForm.id ? "Editar tipo de embalagem" : "Novo tipo de embalagem"} onClose={() => setTypeForm(null)}>
          <form className="form-grid" onSubmit={savePackagingType}>
            <Field label="Nome completo do tipo de embalagem" required hint="Ex.: Caixa, Fardo, Pacote ou Grade retornável.">
              <input value={typeForm.name} onChange={(event) => setTypeForm({ ...typeForm, name: event.target.value })} required />
            </Field>
            <label className="checkbox-line">
              <input type="checkbox" checked={typeForm.active !== false} onChange={(event) => setTypeForm({ ...typeForm, active: event.target.checked })} />
              <span>Disponível para novos produtos e categorias</span>
            </label>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setTypeForm(null)}>Cancelar</Button>
              <Button disabled={busy}>{busy ? "Salvando..." : "Salvar tipo"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {confirmation && (
        <ConfirmModal
          {...confirmation}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={executePendingAction}
        />
      )}
    </>
  );
}
