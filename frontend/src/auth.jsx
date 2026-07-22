import { React, useEffect, useMemo, useState, api, unwrap, fmtMoney, fmtQty, fmtDate, today, getError, Logo, Button, Modal, Toast, Field, EmptyState, Pagination, DataTable, StatusBadge, AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine, BarChart3, Bell, Boxes, Check, ChevronDown, CircleDollarSign, ClipboardCheck, Eye, EyeOff, FileDown, FileText, Gauge, History, Layers3, LogOut, Menu, Package, Pencil, Plus, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal, Trash2, Truck, UserCog, Users, Warehouse, X, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "./shared.jsx";
export function Login({ onLogin }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [identifier, setIdentifier] = useState("");
  const [recovery, setRecovery] = useState(null);
  const [newPassword, setNewPassword] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await api.post("auth/login/", { username, password });
      localStorage.setItem("fp_access", response.data.access);
      localStorage.setItem("fp_refresh", response.data.refresh);
      onLogin();
    } catch (err) {
      setError(getError(err) || "Usuário ou senha inválidos.");
    } finally {
      setBusy(false);
    }
  }

  async function requestRecovery(event) {
    event.preventDefault();
    setError("");
    try {
      const response = await api.post("auth/forgot-password/", { identifier });
      setRecovery(response.data);
    } catch (err) {
      setError(getError(err));
    }
  }

  async function resetPassword(event) {
    event.preventDefault();
    try {
      await api.post("auth/reset-password/", { uid: recovery.uid, token: recovery.token, password: newPassword });
      setForgot(false);
      setRecovery(null);
      setError("");
      alert("Senha redefinida. Faça login com a nova senha.");
    } catch (err) {
      setError(getError(err));
    }
  }

  return (
    <main className="login-page">
      <div className="login-accent" />
      <section className="login-showcase" aria-label="FP Depósito de Bebidas">
        <img src="/fp-logo.png" alt="Logomarca do FP Depósito de Bebidas" />
      </section>
      <form className="login-card" onSubmit={submit}>
        <Logo />
        <div className="login-heading">
          <p>Controle interno de estoque</p>
          <h1>Acesse o sistema</h1>
        </div>
        <Field label="E-mail ou nome de usuário" required>
          <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </Field>
        <Field label="Senha" required>
          <div className="password-input">
            <input type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <button type="button" onClick={() => setShow(!show)} aria-label="Mostrar ou ocultar senha">{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
          </div>
        </Field>
        {error && <div className="form-error">{error}</div>}
        <Button disabled={busy}>{busy ? "Entrando..." : "Entrar"}</Button>
        <button type="button" className="link-button" onClick={() => { setForgot(true); setError(""); }}>Esqueci minha senha</button>
      </form>
      {forgot && (
        <Modal title="Recuperação de senha" onClose={() => setForgot(false)}>
          {!recovery?.uid ? (
            <form className="form-grid" onSubmit={requestRecovery}>
              <Field label="E-mail ou usuário" required><input value={identifier} onChange={(e) => setIdentifier(e.target.value)} required /></Field>
              <p className="muted full">Em desenvolvimento, o sistema fornece um token temporário. Em produção, configure o envio por e-mail.</p>
              {error && <div className="form-error full">{error}</div>}
              <div className="form-actions full"><Button>Gerar recuperação</Button></div>
            </form>
          ) : (
            <form className="form-grid" onSubmit={resetPassword}>
              <Field label="Nova senha" required><input type="password" minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required /></Field>
              <div className="form-actions full"><Button>Redefinir senha</Button></div>
            </form>
          )}
        </Modal>
      )}
    </main>
  );
}
