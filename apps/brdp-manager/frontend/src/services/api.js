/**
 * API service layer — REST calls to the FastAPI backend (`/api/v1/*`).
 */

const BASE = '/api/v1';

// ─── BRDPs ────────────────────────────────────────────────────────────────────

export async function fetchBRDPs() {
  const res = await fetch(`${BASE}/brdps`);
  if (!res.ok) throw new Error('Failed to fetch BRDPs');
  return res.json();
}

export async function createBRDP(brdp) {
  const res = await fetch(`${BASE}/brdps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brdp),
  });
  if (!res.ok) throw new Error('Failed to create BRDP');
  return res.json();
}

export async function updateBRDPApi(id, brdp) {
  const res = await fetch(`${BASE}/brdps/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brdp),
  });
  if (!res.ok) throw new Error('Failed to update BRDP');
  return res.json();
}

export async function deleteBRDP(id) {
  const res = await fetch(`${BASE}/brdps/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete BRDP');
  return res.json();
}

export async function deleteAllBRDPs() {
  const res = await fetch(`${BASE}/brdps`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete all BRDPs');
  return res.json();
}

export async function saveBRDPs(brdps) {
  // Save full array: delete all then insert each
  await deleteAllBRDPs();
  for (const brdp of brdps) {
    await createBRDP(brdp);
  }
}

export async function resetToDemoBRDPs() {
  const res = await fetch(`${BASE}/brdps/reset-demo`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset BRDPs to demo data');
  return res.json();
}

// ─── Project config ───────────────────────────────────────────────────────────

export async function fetchConfig() {
  const res = await fetch(`${BASE}/project-config`);
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export async function saveConfig(config) {
  const res = await fetch(`${BASE}/project-config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to save config');
  return res.json();
}

// ─── Settings (Mistral runtime config) ─────────────────────────────────────────

export async function fetchSettings() {
  const res = await fetch(`${BASE}/settings`);
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function saveSettings(settings) {
  const res = await fetch(`${BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error('Failed to save settings');
  return res.json();
}

export async function testSettingsConnection() {
  const res = await fetch(`${BASE}/settings/test`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to test connection');
  return res.json();
}

// ─── Notes ────────────────────────────────────────────────────────────────────

export async function fetchNote(brdpId) {
  const res = await fetch(`${BASE}/notes/${brdpId}`);
  if (!res.ok) return '';
  const data = await res.json();
  return data.text || '';
}

export async function saveNote(brdpId, text) {
  const res = await fetch(`${BASE}/notes/${brdpId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error('Failed to save note');
  return res.json();
}

// ─── Health / admin ─────────────────────────────────────────────────────────────

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`);
  if (!res.ok) throw new Error('Failed to fetch health');
  return res.json();
}

export async function fetchAdminStats() {
  const res = await fetch(`${BASE}/admin/stats`);
  if (!res.ok) throw new Error('Failed to fetch admin stats');
  return res.json();
}

export async function resetAllData() {
  const res = await fetch(`${BASE}/admin/reset/all`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset data');
  return res.json();
}
