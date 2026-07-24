import {
  React,
  useState,
  api,
  fmtDate,
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
import { useList } from "./listing.jsx";

const EMPTY_USER = {
  username: "",
  email: "",
  first_name: "",
  last_name: "",
  is_active: true,
  full_name: "",
  cpf: "",
  phone: "",
  role: "OPERATOR",
  profile_active: true,
  password: "",
};

function isActive(row) {
  return Boolean(row.is_active && row.profile?.active);
}

export function UsersPage({ notify, me }) {
  const list = useList("users/");
  const [form, setForm] = useState(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  function startNewUser() {
    setFormError("");
    setForm({ ...EMPTY_USER });
  }

  function edit(row) {
    setFormError("");
    setForm({
      id: row.id,
      username: row.username,
      email: row.email || "",
      first_name: row.first_name || "",
      last_name: row.last_name || "",
      is_active: row.is_active,
      full_name: row.profile?.full_name || "",
      cpf: row.profile?.cpf || "",
      phone: row.profile?.phone || "",
      role: row.profile?.role || "OPERATOR",
      profile_active: row.profile?.active ?? true,
      password: "",
    });
  }

  async function save(event) {
    event.preventDefault();
    setFormError("");
    setSaving(true);

    const payload = {
      username: form.username.trim(),
      email: form.email.trim(),
      first_name: form.first_name || "",
      last_name: form.last_name || "",
      is_active: form.is_active,
      full_name: form.full_name.trim(),
      cpf: form.cpf.trim() || null,
      phone: form.phone.trim(),
      role: form.role,
      profile_active: form.profile_active,
      ...(form.password ? { password: form.password } : {}),
    };

    try {
      if (form.id) await api.put(`users/${form.id}/`, payload);
      else await api.post("users/", payload);
      notify(form.id ? "Usuário atualizado com sucesso." : "Usuário criado com sucesso.");
      setForm(null);
      list.reload();
    } catch (error) {
      const message = getError(error);
      setFormError(message);
      notify(message, "error");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus() {
    if (!pendingAction) return;
    setActionBusy(true);
    try {
      const activate = !isActive(pendingAction);
      await api.post(`users/${pendingAction.id}/${activate ? "activate" : "deactivate"}/`);
      notify(`Usuário ${activate ? "ativado" : "inativado"} com sucesso.`);
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
        title="Usuários e permissões"
        description="Contas são preservadas para auditoria e podem ser ativadas ou inativadas."
        actions={<Button icon={Plus} onClick={startNewUser}>Novo usuário</Button>}
      />

      <div className="filters-bar">
        <select
          value={list.params.is_active ?? ""}
          onChange={(event) => list.setParams({ ...list.params, is_active: event.target.value, page: 1 })}
        >
          <option value="">Ativos e inativos</option>
          <option value="true">Somente ativos</option>
          <option value="false">Somente inativos</option>
        </select>
        <select
          value={list.params.inventory_profile__role || ""}
          onChange={(event) => list.setParams({ ...list.params, inventory_profile__role: event.target.value, page: 1 })}
        >
          <option value="">Todos os perfis</option>
          <option value="ADMIN">Administradores</option>
          <option value="OPERATOR">Operadores de estoque</option>
        </select>
      </div>

      <section className="panel">
        <DataTable
          loading={list.loading}
          rows={list.rows}
          columns={[
            { key: "username", label: "Usuário" },
            { key: "profile", label: "Nome completo", render: (row) => row.profile?.full_name },
            { key: "email", label: "E-mail", render: (row) => row.email || "-" },
            {
              key: "role",
              label: "Perfil de acesso",
              render: (row) => (
                <StatusBadge
                  value={row.profile?.role}
                  label={row.profile?.role === "ADMIN" ? "Administrador" : "Operador de estoque"}
                />
              ),
            },
            {
              key: "is_active",
              label: "Situação",
              render: (row) => (
                <StatusBadge
                  value={isActive(row) ? "active" : "inactive"}
                  label={isActive(row) ? "Ativo" : "Inativo"}
                />
              ),
            },
            { key: "last_login", label: "Último acesso", render: (row) => fmtDate(row.last_login) },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <div className="row-actions">
                  <button onClick={() => edit(row)} title="Editar usuário" aria-label={`Editar ${row.username}`}>
                    <Pencil size={16} />
                  </button>
                  <button
                    className={isActive(row) ? "warning" : "success"}
                    onClick={() => setPendingAction(row)}
                    disabled={row.id === me?.id && isActive(row)}
                    title={row.id === me?.id && isActive(row)
                      ? "O usuário atual não pode ser inativado"
                      : isActive(row) ? "Inativar usuário" : "Ativar usuário"}
                    aria-label={`${isActive(row) ? "Inativar" : "Ativar"} ${row.username}`}
                  >
                    {isActive(row) ? <PowerOff size={16} /> : <Power size={16} />}
                  </button>
                </div>
              ),
            },
          ]}
        />
      </section>

      {form && (
        <Modal
          title={form.id ? "Editar usuário" : "Novo usuário"}
          onClose={() => setForm(null)}
          size="lg"
        >
          <form className="form-grid cols-2" onSubmit={save}>
            <Field label="Nome completo" required>
              <input
                value={form.full_name}
                onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                required
              />
            </Field>

            <Field label="CPF" hint="Opcional">
              <input value={form.cpf} onChange={(event) => setForm({ ...form, cpf: event.target.value })} />
            </Field>

            <Field label="Telefone" hint="Opcional">
              <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
            </Field>

            <Field label="E-mail" hint="Opcional">
              <input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            </Field>

            <Field label="Nome de usuário" required>
              <input
                value={form.username}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                required
                autoComplete="off"
              />
            </Field>

            <Field
              label={form.id ? "Nova senha" : "Senha"}
              required={!form.id}
              hint={form.id ? "Deixe em branco para manter a senha atual." : "Use pelo menos 8 caracteres e evite senhas muito comuns."}
            >
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                required={!form.id}
                minLength={8}
                autoComplete="new-password"
              />
            </Field>

            <Field label="Perfil de acesso" required>
              <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
                <option value="ADMIN">Administrador</option>
                <option value="OPERATOR">Operador de estoque</option>
              </select>
            </Field>

            {formError && <div className="form-error full">{formError}</div>}

            <div className="form-actions full">
              <Button type="button" variant="secondary" onClick={() => setForm(null)} disabled={saving}>
                Cancelar
              </Button>
              <Button disabled={saving}>{saving ? "Salvando..." : "Salvar usuário"}</Button>
            </div>
          </form>
        </Modal>
      )}

      {pendingAction && (
        <ConfirmModal
          title={isActive(pendingAction) ? "Inativar usuário" : "Ativar usuário"}
          message={`${isActive(pendingAction) ? "Inativar" : "Ativar"} “${pendingAction.profile?.full_name || pendingAction.username}”?`}
          detail={isActive(pendingAction)
            ? "A conta será preservada para auditoria, mas o usuário perderá o acesso ao sistema imediatamente."
            : "O usuário voltará a ter acesso conforme seu perfil de permissões."}
          confirmLabel={isActive(pendingAction) ? "Inativar usuário" : "Ativar usuário"}
          confirmVariant={isActive(pendingAction) ? "warning" : "success"}
          busy={actionBusy}
          onClose={() => setPendingAction(null)}
          onConfirm={toggleStatus}
        />
      )}
    </>
  );
}
