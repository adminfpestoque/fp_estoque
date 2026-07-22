import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine, BarChart3, Bell, Boxes, Check,
  ChevronDown, CircleDollarSign, ClipboardCheck, Eye, EyeOff, FileDown, FileText, Gauge,
  History, Layers3, LogOut, Menu, Package, Pencil, Plus, RefreshCw, Search, Settings,
  ShieldCheck, SlidersHorizontal, Trash2, Truck, UserCog, Users, Warehouse, X,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import "./styles.css";

function resolveApiBase() {
  const detected = `${window.location.protocol}//${window.location.hostname}:8000/api/`;
  const configured = String(import.meta.env.VITE_API_URL || "").trim();

  if (!configured) return detected;

  try {
    const parsed = new URL(configured, window.location.origin);
    const browserIsRemote = !["localhost", "127.0.0.1"].includes(window.location.hostname);
    const apiUsesLoopback = ["localhost", "127.0.0.1"].includes(parsed.hostname);

    if (browserIsRemote && apiUsesLoopback) {
      parsed.hostname = window.location.hostname;
      return parsed.toString();
    }

    return configured.endsWith("/") ? configured : `${configured}/`;
  } catch {
    return detected;
  }
}

export const API_BASE = resolveApiBase();
export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("fp_access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original?._retry && localStorage.getItem("fp_refresh")) {
      original._retry = true;
      refreshing ||= axios
        .post(`${API_BASE}auth/refresh/`, { refresh: localStorage.getItem("fp_refresh") })
        .then((response) => {
          localStorage.setItem("fp_access", response.data.access);
          if (response.data.refresh) localStorage.setItem("fp_refresh", response.data.refresh);
          return response.data.access;
        })
        .finally(() => (refreshing = null));
      try {
        const token = await refreshing;
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        localStorage.removeItem("fp_access");
        localStorage.removeItem("fp_refresh");
        window.location.reload();
      }
    }
    return Promise.reject(error);
  },
);

export const unwrap = (payload) => payload?.results || payload || [];
export const fmtMoney = (value) => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
export const fmtQty = (value) => Number(value || 0).toLocaleString("pt-BR", { maximumFractionDigits: 3 });
export const fmtDate = (value, withTime = true) => value ? new Date(value).toLocaleString("pt-BR", withTime ? {} : { dateStyle: "short" }) : "-";
export const today = () => new Date().toISOString().slice(0, 10);

export function getError(error) {
  const data = error?.response?.data;
  if (!data) return "Não foi possível concluir a operação.";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.join(" ");
  if (data.detail) return Array.isArray(data.detail) ? data.detail.join(" ") : String(data.detail);
  return Object.entries(data)
    .filter(([key]) => key !== "status_code")
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(" ") : value}`)
    .join(" • ");
}

export function Logo({ compact = false }) {
  return (
    <div className={`brand ${compact ? "compact" : ""}`}>
      <img className="logo-mark" src="/fp-icon.svg" alt="FP Depósito de Bebidas" />
      {!compact && <div><strong>FP Estoque</strong><small>Depósito de Bebidas</small></div>}
    </div>
  );
}

export function Button({ children, variant = "primary", icon: Icon, className = "", ...props }) {
  return <button className={`btn btn-${variant} ${className}`} {...props}>{Icon && <Icon size={17} />}{children}</button>;
}

export function Modal({ title, children, onClose, size = "md" }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className={`modal modal-${size}`} onMouseDown={(event) => event.stopPropagation()}><div className="modal-header"><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="Fechar"><X size={20} /></button></div><div className="modal-body">{children}</div></div></div>;
}

export function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(onClose, 4500);
    return () => clearTimeout(timer);
  }, [toast, onClose]);
  if (!toast) return null;
  return <div className={`toast toast-${toast.type || "success"}`}><span>{toast.message}</span><button onClick={onClose}><X size={16} /></button></div>;
}

export function Field({ label, children, hint, required }) {
  return <label className="field"><span>{label}{required && " *"}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export function EmptyState({ title = "Nenhum registro encontrado", text = "Altere os filtros ou cadastre um novo registro." }) {
  return <div className="empty-state"><Archive size={38} /><h3>{title}</h3><p>{text}</p></div>;
}

export function Pagination({ page, count, pageSize = 20, onChange }) {
  const pages = Math.max(1, Math.ceil((count || 0) / pageSize));
  if (pages <= 1) return null;
  return <div className="pagination"><button disabled={page <= 1} onClick={() => onChange(page - 1)}>Anterior</button><span>Página {page} de {pages}</span><button disabled={page >= pages} onClick={() => onChange(page + 1)}>Próxima</button></div>;
}

export function DataTable({ columns, rows, loading, emptyText, rowKey = "id" }) {
  if (loading) return <div className="loading"><RefreshCw className="spin" /> Carregando...</div>;
  if (!rows?.length) return <EmptyState text={emptyText} />;
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={row[rowKey] ?? index}>{columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : row[column.key] ?? "-"}</td>)}</tr>)}</tbody></table></div>;
}

export function StatusBadge({ value, label }) {
  const normalized = String(value || "").toLowerCase();
  const tone = normalized.includes("confirm") || normalized.includes("done") || normalized === "active" || normalized === "normal"
    ? "success"
    : normalized.includes("cancel") || normalized.includes("expired") || normalized.includes("out") || normalized.includes("critical")
      ? "danger"
      : normalized.includes("draft") || normalized.includes("open") || normalized.includes("waiting") || normalized.includes("warning") || normalized.includes("low")
        ? "warning"
        : "neutral";
  return <span className={`badge badge-${tone}`}>{label || value}</span>;
}

export {
  React, useEffect, useMemo, useState,
  AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine, BarChart3, Bell, Boxes, Check, ChevronDown,
  CircleDollarSign, ClipboardCheck, Eye, EyeOff, FileDown, FileText, Gauge, History, Layers3, LogOut, Menu,
  Package, Pencil, Plus, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal, Trash2, Truck, UserCog,
  Users, Warehouse, X, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
};
