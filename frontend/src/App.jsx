import { useState, useEffect, useCallback } from "react";
import { getDeviceId, fetchWatchlist, addStock, removeStock } from "./api";
import DigestBanner from "./components/DigestBanner";
import WatchlistRow from "./components/WatchlistRow";
import AddStockPanel from "./components/AddStockPanel";
import PortfolioInsight from "./components/PortfolioInsight";

export default function App() {
  const [deviceId, setDeviceId] = useState(null);
  const [digest, setDigest] = useState(null);
  const [insight, setInsight] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const refresh = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWatchlist(id);
      setDigest(data.digest);
      setItems(data.items);
      setInsight(data.insight);
    } catch (e) {
      setError("Couldn't reach the backend. Is it running on port 8000?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const id = await getDeviceId();
        setDeviceId(id);
        await refresh(id);
      } catch (e) {
        setError("Couldn't reach the backend. Is it running on port 8000?");
        setLoading(false);
      }
    })();
  }, [refresh]);

  async function handleAdd(symbol) {
    await addStock(deviceId, symbol);
    await refresh(deviceId);
  }

  async function handleRemove(symbol) {
    await removeStock(deviceId, symbol);
    await refresh(deviceId);
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>Watchlist</h1>
        <div className="app__header-actions">
          <button className="btn btn--ghost" onClick={() => refresh(deviceId)}>
            Refresh
          </button>
          <button className="btn btn--primary" onClick={() => setPanelOpen(true)}>
            + Add stock
          </button>
        </div>
      </header>

      {error && <div className="banner banner--error">{error}</div>}

      <DigestBanner digest={digest} loading={loading} />
      <PortfolioInsight insight={insight} />

      <div className="watchlist">
        {items.map((item) => (
          <WatchlistRow key={item.symbol} item={item} onRemove={handleRemove} />
        ))}
      </div>

      <AddStockPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        onAdd={handleAdd}
        existingSymbols={items.map((i) => i.symbol)}
      />
    </div>
  );
}