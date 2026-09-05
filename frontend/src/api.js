const BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function getDeviceId() {
  let id = localStorage.getItem("device_id");
  if (id) return id;

  const res = await fetch(`${BASE_URL}/device/register`, { method: "POST" });
  if (!res.ok) throw new Error("Could not register device");
  const data = await res.json();
  localStorage.setItem("device_id", data.device_id);
  return data.device_id;
}

export async function fetchWatchlist(deviceId) {
  const res = await fetch(`${BASE_URL}/watchlist?device_id=${deviceId}`);
  if (!res.ok) throw new Error("Could not load watchlist");
  return res.json();
}

export async function addStock(deviceId, symbol) {
  const res = await fetch(`${BASE_URL}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_id: deviceId, symbol }),
  });
  if (!res.ok) throw new Error("Could not add stock");
  return res.json();
}

export async function removeStock(deviceId, symbol) {
  const res = await fetch(
    `${BASE_URL}/watchlist/${symbol}?device_id=${deviceId}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error("Could not remove stock");
  return res.json();
}

export async function searchStocks(query) {
  const res = await fetch(
    `${BASE_URL}/stocks/search?q=${encodeURIComponent(query)}`
  );
  if (!res.ok) throw new Error("Search failed");
  return res.json();
}