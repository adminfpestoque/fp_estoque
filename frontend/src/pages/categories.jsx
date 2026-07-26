import {
  React,
  useState,
  api,
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
} from "../shared.jsx";
import { PageHeader } from "../layout.jsx";
import { useList, SearchBar } from "./listing.jsx";

export function CategoriesPage({ notify, me }) {
  const list = useList("categories/");
  const [form, setForm] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const [busy, setBusy] = useState(false);

  function openCategory(row = null) {
    setForm(row ? { ...row } : { name: "", description: "", active: true });
  }

  async function saveCategory(event) {
    event.preventDefault();
    const payload = {
      name: form.name.trim(),
      description: form.description?.trim() || "",
      active: Boolean(form.active),
    };
    setBusy(true);
    try {
      if (form.id) await api.put(`categories/${form.id}/`, payload);
      else await api.post("categories/", payload);
      notify("Categoria salva com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function toggleCategory() {
    if (!pendingAction) return;
    setBusy(true);
    try {
      const activate = !pendingAction.active;
      await api.post(`categories/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      notify(`Categoria ${activate ? "ativada" : "inativada"} com sucesso.`);
      setPendingAction(null);
      list.reload();
    } catch (error) {
      notify(getError(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Categorias"
        description="Organize os produtos por grupos, como Refrigerantes, Cervejas, Águas e Destilados."
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => openCategory()}>Nova categoria</Button>
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
            { key: "name", label: "Categoria", render: (row) => <strong>{row.name}</strong> },
            { key: "description", label: "Descrição", render: (row) => row.description || "—" },
            {
              key: "active",
              label: "Situação",
              render: (row) => <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativa" : "Inativa"} />,
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => openCategory(row)} title="Editar categoria"><Pencil size={16} /></button>
                  <button
                    className={row.active ? "warning" : "success"}
                    onClick={() => setPendingAction(row)}
                    title={row.active ? "Inativar categoria" : "Ativar categoria"}
                  >
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                </div>
              ) : "—",
            },
          ]}
        />
      </section>

      {form && (
        <Modal title={form.id ? "Editar categoria" : "Nova categoria"} onClose={() => !busy && setForm(null)}>
          <form className="form-grid" onSubmit={saveCategory}>
            <Field label="Nome da categoria" required>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Refrigerantes" required />
            </Field>
            <Field label="Descrição da categoria">
              <textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Opcional" />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={busy}>Cancelar</Button>
              <Button disabled={busy}>{busy ? "Salvando..." : "Salvar categoria"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {pendingAction && (
        <ConfirmModal
          title={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          message={`${pendingAction.active ? "Inativar" : "Ativar"} “${pendingAction.name}”?`}
          detail={pendingAction.active
            ? "A categoria ficará indisponível para novos produtos, mas continuará no histórico."
            : "A categoria voltará a ficar disponível para novos produtos."}
          confirmLabel={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          confirmVariant={pendingAction.active ? "warning" : "success"}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={toggleCategory}
        />
      )}
    </>
  );
}
