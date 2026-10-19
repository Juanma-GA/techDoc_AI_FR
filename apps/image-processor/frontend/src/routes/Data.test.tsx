import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../i18n";
import { adminApi, type AdminResetDto, type AdminStatsDto } from "../lib/api";
import { Data } from "./Data";

// L-13: regression coverage for the M-06 fix — `common.loading` /
// `common.confirm` keys existed nowhere in locales/{fr,en}.json, and
// `data.resetDone` used `{count}` instead of i18next's `{{count}}` syntax,
// so the interpolated value never substituted into the rendered string.

vi.mock("../lib/api", () => ({
  adminApi: {
    stats: vi.fn(),
    resetAll: vi.fn(),
  },
}));

function renderData() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <Data />
    </QueryClientProvider>,
  );
}

const STATS: AdminStatsDto = {
  documents: 3,
  chunks: 10,
  sessions: 1,
  messages: 5,
  total_size_bytes: 2048,
};

describe("Data", () => {
  beforeEach(async () => {
    // The language detector resolves from navigator/localStorage, which is
    // nondeterministic in jsdom — pin it so the FR assertions below are
    // reliable regardless of the test environment's locale.
    await i18n.changeLanguage("fr");
  });

  it("renders the translated loading label while stats are pending", () => {
    vi.mocked(adminApi.stats).mockReturnValue(new Promise(() => {}));
    renderData();
    expect(screen.getByText("Chargement…")).toBeInTheDocument();
  });

  it("arms the destructive reset button on first click, requiring a second click to confirm", async () => {
    vi.mocked(adminApi.stats).mockResolvedValue(STATS);
    renderData();
    await waitFor(() => expect(adminApi.stats).toHaveBeenCalled());

    const button = await screen.findByRole("button", { name: "Tout supprimer" });
    await userEvent.click(button);
    expect(await screen.findByRole("button", { name: "Confirmer" })).toBeInTheDocument();
    expect(adminApi.resetAll).not.toHaveBeenCalled();
  });

  it("resets on the second click and shows the count correctly interpolated", async () => {
    vi.mocked(adminApi.stats).mockResolvedValue(STATS);
    const resetResult: AdminResetDto = { scope: "all", deleted: { documents: 3, sessions: 1 } };
    vi.mocked(adminApi.resetAll).mockResolvedValue(resetResult);
    renderData();
    await waitFor(() => expect(adminApi.stats).toHaveBeenCalled());

    const button = await screen.findByRole("button", { name: "Tout supprimer" });
    await userEvent.click(button);
    await userEvent.click(await screen.findByRole("button", { name: "Confirmer" }));

    expect(adminApi.resetAll).toHaveBeenCalledTimes(1);
    // 3 + 1 = 4 — the `{{count}}` placeholder must be replaced by the real
    // sum, not left as a literal "{{count}}" (the M-06 bug's signature).
    expect(
      await screen.findByText("Réinitialisation terminée (4 éléments supprimés)."),
    ).toBeInTheDocument();
  });
});
