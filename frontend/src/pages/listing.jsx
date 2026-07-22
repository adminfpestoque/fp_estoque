import { React, useEffect, useMemo, useState, api, unwrap, fmtMoney, fmtQty, fmtDate, today, getError, Logo, Button, Modal, Toast, Field, EmptyState, Pagination, DataTable, StatusBadge, AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine, BarChart3, Bell, Boxes, Check, ChevronDown, CircleDollarSign, ClipboardCheck, Eye, EyeOff, FileDown, FileText, Gauge, History, Layers3, LogOut, Menu, Package, Pencil, Plus, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal, Trash2, Truck, UserCog, Users, Warehouse, X, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "../shared.jsx";
export function useList(endpoint, initialParams = {}) {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [params, setParams] = useState({ page: 1, ...initialParams });
  const reload = async (override = {}) => {
    setLoading(true);
    const merged = { ...params, ...override };
    try {
      const response = await api.get(endpoint, { params: merged });
      setRows(unwrap(response.data));
      setCount(response.data?.count ?? unwrap(response.data).length);
      if (Object.keys(override).length) setParams(merged);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { reload(); }, [endpoint, JSON.stringify(params)]); // eslint-disable-line react-hooks/exhaustive-deps
  return { rows, count, loading, params, setParams, reload };
}

export function SearchBar({ value, onChange, placeholder = "Pesquisar..." }) {
  return <div className="search-box"><Search size={17} /><input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} /></div>;
}
