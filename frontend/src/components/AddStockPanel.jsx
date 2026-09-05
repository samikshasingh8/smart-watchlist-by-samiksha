import { useState, useEffect, useRef } from "react";
import { searchStocks } from "../api";
import { formatPrice, formatPct } from "../format";

export default function AddStockPanel({ open, onClose, onAdd, existingSymbols }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    runSearch("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function handleChange(e) {
    const value = e.target.value;
    setQuery(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(value), 300);
  }

  async function runSearch(q) {
    setLoading(true);
    try {
      const data = await searchStocks(q);
      setResults(data.results);
    } catch (e) {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  if (!open) return null;

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel__header">
          <h2>Add a stock</h2>
          <button className="panel__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <input
          autoFocus
          className="panel__search"
          type="text"
          placeholder="Search by name or symbol…"
          value={query}
          onChange={handleChange}
        />

        <div className="panel__results">
          {loading && <p className="panel__hint">Searching…</p>}
          {!loading && results.length === 0 && (
            <p className="panel__hint">No matches.</p>
          )}
          {!loading &&
            results.map((r) => {
              const already = existingSymbols.includes(r.symbol);
              const changeClass =
                r.day_change_pct > 0 ? "is-up" : r.day_change_pct < 0 ? "is-down" : "";
              return (
                <div key={r.symbol} className="search-row">
                  <div className="search-row__identity">
                    <span className="search-row__symbol">{r.symbol}</span>
                    <span className="search-row__name">{r.name}</span>
                    <span className="search-row__sector">{r.sector}</span>
                  </div>
                  <div className="search-row__stats mono">
                    <span>{formatPrice(r.ltp)}</span>
                    <span className={changeClass}>{formatPct(r.day_change_pct)}</span>
                  </div>
                  <button
                    className="search-row__add"
                    disabled={already}
                    onClick={() => onAdd(r.symbol)}
                  >
                    {already ? "Added" : "Add"}
                  </button>
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
}