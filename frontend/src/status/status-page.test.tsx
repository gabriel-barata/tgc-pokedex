import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { components } from "../api-schema.gen.ts";
import { App } from "../App.tsx";
import { server } from "../test-server.ts";
import { renderWithProviders } from "../test-utils.tsx";
import { statusStrings } from "./strings.ts";

type SyncRunEntry = components["schemas"]["SyncRunEntry"];
type SyncStatus = components["schemas"]["SyncStatus"];

function makeRun(id: string, overrides: Partial<SyncRunEntry> = {}): SyncRunEntry {
  return {
    id,
    kind: "catalog",
    status: "succeeded",
    started_at: "2026-10-12T07:00:00Z",
    finished_at: "2026-10-12T07:02:05Z",
    duration_ms: 125_000,
    counts: { fetched: 120, updated: 4, failed: 0 },
    failures: [],
    error: null,
    ...overrides,
  };
}

let status: SyncStatus;

beforeEach(() => {
  status = {
    running: false,
    runs: [
      makeRun("images", {
        kind: "images",
        status: "partial",
        started_at: "2026-10-12T07:02:05Z",
        duration_ms: 42_000,
        counts: { fetched: 30, updated: 30, failed: 1 },
        failures: [{ kind: "card", provider_id: "sv01-002", reason: "HTTP 500" }],
      }),
      makeRun("catalog"),
      makeRun("dead", {
        status: "failed",
        finished_at: null,
        duration_ms: null,
        counts: null,
        error: "interrupted: the process running this sync stopped",
      }),
    ],
  };
  server.use(
    http.get("/api/sync", () => HttpResponse.json(status)),
    http.post("/api/sync", () => {
      status = {
        running: true,
        runs: [
          makeRun("new", { status: "running", finished_at: null, duration_ms: null, counts: null }),
          ...status.runs,
        ],
      };
      return HttpResponse.json(status, { status: 202 });
    }),
  );
});

async function openStatusPage() {
  const user = userEvent.setup();
  renderWithProviders(<App />, { route: "/status" });
  const runs = await screen.findByRole("list", { name: statusStrings.runs });
  return { user, runs };
}

describe("status page", () => {
  it("lists the latest runs with their status, counts, duration and errors", async () => {
    const { user, runs } = await openStatusPage();

    const items = within(runs).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      expect.stringMatching(/Imagens.*Parcial.*42 s.*30 buscados.*30 alterados.*1 falha/),
      expect.stringMatching(/Catálogo.*Concluída.*2 min 5 s.*120 buscados.*4 alterados.*0 falhas/),
      expect.stringMatching(/Catálogo.*Falhou.*interrupted/),
    ]);
    const showFailures = within(runs).getByRole("button", {
      name: statusStrings.showFailures(1),
    });
    await user.click(showFailures);

    expect(showFailures.getAttribute("aria-expanded")).toBe("true");
    const failures = within(runs).getByRole("list", { name: statusStrings.failures });
    expect(
      within(failures)
        .getAllByRole("listitem")
        .map((item) => item.textContent),
    ).toEqual(["Carta sv01-002: HTTP 500"]);
  });

  it("starts a sync and shows it in progress", async () => {
    const { user } = await openStatusPage();

    await user.click(screen.getByRole("button", { name: statusStrings.syncNow }));

    const busy = await screen.findByRole("button", { name: statusStrings.syncing });
    expect(busy).toHaveProperty("disabled", true);
    const runs = screen.getByRole("list", { name: statusStrings.runs });
    expect(within(runs).getAllByRole("listitem")[0]?.textContent).toMatch(/Catálogo.*Em andamento/);
  });
});
