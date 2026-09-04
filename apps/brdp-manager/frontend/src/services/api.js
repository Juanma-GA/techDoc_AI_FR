/**
 * API service layer — REST calls to the FastAPI backend (`/api/v1/*`).
 */

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

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

// Confirmation marker required by the backend (see brdps.py::_require_confirm_token).
// Not a secret — the real confirmation is the double-click UX gate the caller has
// already passed (DetailPanel's delete button, BRDPTable's "delete selected") before
// any of the functions below ever run.
const DELETE_CONFIRM_TOKEN = 'ui-confirmed-delete';

export async function deleteBRDP(id) {
  const res = await fetch(`${BASE}/brdps/${id}?confirm_token=${DELETE_CONFIRM_TOKEN}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete BRDP');
  return res.json();
}

/**
 * Reconciles the backend with the new BRDP list by diffing against the
 * previous one: only the items that actually changed are deleted / created /
 * updated, one targeted request per item — never a blind "delete everything"
 * (see H-NEW-09: that used to be the whole save strategy and a bug meant
 * deleting a single BRDP silently wiped every BRDP on the server).
 */
export async function syncBRDPs(newBrdps, previousBrdps) {
  const newIds = new Set(newBrdps.map((b) => b.id));
  const prevIds = new Set(previousBrdps.map((b) => b.id));

  const removed = previousBrdps.filter((b) => !newIds.has(b.id));
  for (const brdp of removed) {
    await deleteBRDP(brdp.id);
  }

  for (const brdp of newBrdps) {
    if (prevIds.has(brdp.id)) {
      await updateBRDPApi(brdp.id, brdp);
    } else {
      await createBRDP(brdp);
    }
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
