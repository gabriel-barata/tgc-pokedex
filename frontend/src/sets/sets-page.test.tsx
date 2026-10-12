import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import type { components } from "../api-schema.gen.ts";
import { App } from "../App.tsx";
import { server } from "../test-server.ts";
import { renderWithProviders } from "../test-utils.tsx";
import { setsStrings } from "./strings.ts";

type SetEntry = components["schemas"]["SetEntry"];

function makeSet(id: string, name: string, overrides: Partial<SetEntry> = {}): SetEntry {
  const card_count = overrides.card_count ?? 182;
  return {
    id,
    name,
    release_date: "2025-05-30",
    card_count,
    has_logo: false,
    has_symbol: false,
    tracked: false,
    downloading: false,
    completion: { owned: 0, so_normal: 0, total: card_count, complete: false },
    ...overrides,
  };
}

let sets: SetEntry[];

function serveCatalog() {
  const setTracked = (setId: unknown, tracked: boolean) => {
    sets = sets.map((each) => (each.id === setId ? { ...each, tracked } : each));
    return HttpResponse.json({});
  };
  server.use(
    http.get("/api/sets", () =>
      HttpResponse.json([
        { id: "me", name: "Megaevolução", sets: sets.slice(0, 1) },
        { id: "sv", name: "Escarlate e Violeta", sets: sets.slice(1) },
      ]),
    ),
    http.put("/api/sets/:setId/tracking", ({ params }) => setTracked(params.setId, true)),
    http.delete("/api/sets/:setId/tracking", ({ params }) => setTracked(params.setId, false)),
  );
}

async function openSetsPage() {
  const user = userEvent.setup();
  renderWithProviders(<App />, { route: "/colecoes" });
  await screen.findByRole("region", { name: setsStrings.allSets });
  return user;
}

function region(name: string) {
  return screen.getByRole("region", { name });
}

beforeEach(() => {
  sets = [
    makeSet("me02", "Fogo Fantasmagórico", { release_date: "2025-11-14", card_count: 94 }),
    makeSet("sv10", "Rivais Predestinados", { tracked: true, downloading: true }),
  ];
  serveCatalog();
});

describe("sets page", () => {
  it("shows tracked sets as covers above every set grouped by series", async () => {
    const user = await openSetsPage();

    const all = region(setsStrings.allSets);
    expect(
      within(all)
        .getAllByRole("heading", { level: 3 })
        .map((h) => h.textContent),
    ).toEqual(["Megaevolução", "Escarlate e Violeta"]);
    expect(within(all).getAllByRole("listitem")[0]?.textContent).toMatch(
      /Fogo Fantasmagórico.*2025.*94 cartas/,
    );
    const covers = region(setsStrings.trackedSets);
    expect(within(covers).getByText(setsStrings.syncingImages)).toBeTruthy();
    await user.click(within(covers).getByRole("link", { name: "Rivais Predestinados" }));

    expect(screen.getByRole("heading", { level: 1, name: "Rivais Predestinados" })).toBeTruthy();
  });

  it("tracks and untracks a set from the catalog", async () => {
    const user = await openSetsPage();
    const track = screen.getByRole("button", { name: `${setsStrings.track} Fogo Fantasmagórico` });

    await user.click(track);

    const covers = region(setsStrings.trackedSets);
    expect(await within(covers).findByRole("link", { name: "Fogo Fantasmagórico" })).toBeTruthy();
    expect(track.getAttribute("aria-pressed")).toBe("true");

    await user.click(track);

    await expect
      .poll(() => within(covers).queryByRole("link", { name: "Fogo Fantasmagórico" }))
      .toBeNull();
    expect(track.getAttribute("aria-pressed")).toBe("false");
  });

  it("keeps a set's state and says so when tracking fails", async () => {
    server.use(
      http.put("/api/sets/:setId/tracking", () => new HttpResponse(null, { status: 500 })),
    );
    const user = await openSetsPage();
    const track = screen.getByRole("button", { name: `${setsStrings.track} Fogo Fantasmagórico` });

    await user.click(track);

    expect((await screen.findByRole("alert")).textContent).toBe(
      setsStrings.trackError("Fogo Fantasmagórico"),
    );
    expect(track.getAttribute("aria-pressed")).toBe("false");
  });

  it("points to the catalog when no set is tracked", async () => {
    sets = sets.map((each) => ({ ...each, tracked: false }));
    const user = await openSetsPage();

    await user.click(screen.getByRole("link", { name: setsStrings.seeAllSets }));

    expect(
      screen.getByRole("heading", { level: 2, name: setsStrings.allSets }).matches(":focus"),
    ).toBe(true);
  });

  it("offers a retry when the sets cannot be loaded", async () => {
    server.use(http.get("/api/sets", () => HttpResponse.error(), { once: true }));
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/colecoes" });

    await user.click(await screen.findByRole("button", { name: setsStrings.retry }));

    expect(await screen.findByRole("region", { name: setsStrings.allSets })).toBeTruthy();
  });
});
