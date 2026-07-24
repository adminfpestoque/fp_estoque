import { React, useEffect, useState, api, unwrap, Search } from "../shared.jsx";

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
      const nextRows = unwrap(response.data);
      setRows(nextRows);
      setCount(response.data?.count ?? nextRows.length);
      if (Object.keys(override).length) setParams(merged);
      return nextRows;
    } finally {
      setLoading(false);
    }
  };

  const replaceRow = (nextRow) => {
    if (!nextRow?.id) return;
    setRows((current) => current.map((row) => row.id === nextRow.id ? nextRow : row));
  };

  useEffect(() => { reload(); }, [endpoint, JSON.stringify(params)]); // eslint-disable-line react-hooks/exhaustive-deps
  return { rows, count, loading, params, setParams, setRows, replaceRow, reload };
}

export function SearchBar({ value, onChange, placeholder = "Pesquisar..." }) {
  return <div className="search-box"><Search size={17} /><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></div>;
}
