const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function getMetrics(storeId: string) {
  const res = await fetch(`${API_BASE}/stores/${storeId}/metrics`);
  return res.json();
}

export async function getFunnel(storeId: string) {
  const res = await fetch(`${API_BASE}/stores/${storeId}/funnel`);
  return res.json();
}

export async function getHeatmap(storeId: string) {
  const res = await fetch(`${API_BASE}/stores/${storeId}/heatmap`);
  return res.json();
}

export async function getAnomalies(storeId: string) {
  const res = await fetch(`${API_BASE}/stores/${storeId}/anomalies`);
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}
