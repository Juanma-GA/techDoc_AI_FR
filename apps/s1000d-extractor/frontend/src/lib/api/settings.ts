import { api } from "./client";
import type { HealthDto, AdminStatsDto, AdminResetDto, SettingsDto } from "./types";

export const healthApi = { read: () => api<HealthDto>("/health") };


export const adminApi = {
  stats: () => api<AdminStatsDto>("/admin/stats"),
  reset: (scope: "documents" | "all", confirmToken: string) =>
    api<AdminResetDto>(
      `/admin/reset/${scope}?confirm_token=${encodeURIComponent(confirmToken)}`,
      { method: "POST" },
    ),
};


export const settingsApi = {
  read: () => api<SettingsDto>("/settings"),
  write: (body: { demo_enabled?: boolean }) =>
    api<SettingsDto>("/settings", { method: "POST", body: JSON.stringify(body) }),
};
