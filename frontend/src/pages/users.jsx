import {
  React,
  useState,
  api,
  fmtDate,
  getError,
  Button,
  Modal,
  Field,
  DataTable,
  StatusBadge,
  Pencil,
  Plus,
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

export function UsersPage({ notify }) {
  const list = useList("users/");
  const [form, setForm] = useState(null);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

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
      if (form.id) {
        await api.put(`users/${form.id}/`, payload);
      } else {
        await api.post("users/", payload);
      }
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

  return (
    <>
      <PageHeader
        title="Usuários e permissões"
        description="Cadastre usuários e defina diretamente o perfil de acesso de cada pessoa."
        actions={<Button icon={Plus} onClick={startNewUser}>Novo usuário</Button>}
      />

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
                  value={row.is_active && row.profile?.active ? "active" : "inactive"}
                  label={row.is_active && row.profile?.active ? "Ativo" : "Inativo"}
                />
              ),
            },
            { key: "last_login", label: "Último acesso", render: (row) => fmtDate(row.last_login) },
            {
              key: "actions",
              label: "Ações",
              render: (row) => (
                <button className="icon-btn" onClick={() => edit(row)} aria-label={`Editar ${row.username}`}>
                  <Pencil size={16} />
                </button>
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
              <input
                value={form.cpf}
                onChange={(event) => setForm({ ...form, cpf: event.target.value })}
              />
            </Field>

            <Field label="Telefone" hint="Opcional">
              <input
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </Field>

            <Field label="E-mail" hint="Opcional">
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
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
              <select
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value })}
              >
                <option value="ADMIN">Administrador</option>
                <option value="OPERATOR">Operador de estoque</option>
              </select>
            </Field>

            <Field label="Situação" required>
              <select
                value={String(form.is_active && form.profile_active)}
                onChange={(event) => {
                  const active = event.target.value === "true";
                  setForm({ ...form, is_active: active, profile_active: active });
                }}
              >
                <option value="true">Ativo</option>
                <option value="false">Inativo</option>
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
    </>
  );
}
