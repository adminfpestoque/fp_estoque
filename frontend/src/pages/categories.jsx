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

  async function save(event) {
    event.preventDefault();
    const payload = {
      name: form.name.trim(),
      description: form.description?.trim() || "",
      active: Boolean(form.active),
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

  async function toggleStatus() {
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
        description="Cadastros de governança são preservados e podem ser ativados ou inativados."
        actions={me.permissions.is_admin && (
          <Button icon={Plus} onClick={() => setForm({ name: "", description: "", active: true })}>
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
            { key: "name", label: "Categoria", render: (row) => <strong>{row.name}</strong> },
            { key: "description", label: "Descrição" },
            {
              key: "active",
              label: "Situação",
              render: (row) => (
                <StatusBadge value={row.active ? "active" : "inactive"} label={row.active ? "Ativa" : "Inativa"} />
              ),
            },
            {
              key: "actions",
              label: "Ações",
              render: (row) => me.permissions.is_admin ? (
                <div className="row-actions">
                  <button onClick={() => setForm({ ...row })} title="Editar categoria" aria-label={`Editar ${row.name}`}>
                    <Pencil size={16} />
                  </button>
                  <button
                    className={row.active ? "warning" : "success"}
                    onClick={() => setPendingAction(row)}
                    title={row.active ? "Inativar categoria" : "Ativar categoria"}
                    aria-label={`${row.active ? "Inativar" : "Ativar"} ${row.name}`}
                  >
                    {row.active ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                </div>
              ) : "-",
            },
          ]}
        />
      </section>

      {form && (
        <Modal title={form.id ? "Editar categoria" : "Nova categoria"} onClose={() => setForm(null)}>
          <form className="form-grid" onSubmit={save}>
            <Field label="Nome" required>
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
            </Field>
            <Field label="Descrição">
              <textarea value={form.description || ""} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </Field>
            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)}>Cancelar</Button>
              <Button>Salvar categoria</Button>
            </div>
          </form>
        </Modal>
      )}

      {pendingAction && (
        <ConfirmModal
          title={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          message={`${pendingAction.active ? "Inativar" : "Ativar"} “${pendingAction.name}”?`}
          detail={pendingAction.active
            ? "A categoria será preservada para relatórios e histórico, mas ficará indisponível para novos cadastros."
            : "A categoria voltará a ficar disponível para novos cadastros."}
          confirmLabel={pendingAction.active ? "Inativar categoria" : "Ativar categoria"}
          confirmVariant={pendingAction.active ? "warning" : "success"}
          busy={busy}
          onClose={() => setPendingAction(null)}
          onConfirm={toggleStatus}
        />
      )}
    </>
  );
}
