import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/App.tsx";
import { server } from "@/testing/server.ts";
import { renderWithProviders } from "@/testing/render.tsx";
import { layoutStrings } from "@/strings/layout.ts";

function mainNav() {
  return screen.getByRole("navigation", { name: layoutStrings.mainNav });
}

beforeEach(() => {
  server.use(
    http.get("/api/sets", () => new Promise<never>(() => undefined)),
    http.get("/api/sync", () => new Promise<never>(() => undefined)),
  );
});

describe("app shell", () => {
  it("renders the page inside the banner, main navigation and main landmarks", () => {
    renderWithProviders(<App />);

    expect(within(screen.getByRole("banner")).getByRole("navigation")).toBe(mainNav());
    expect(within(screen.getByRole("main")).getByRole("status")).toBeTruthy();
  });

  it("starts the tab order with a skip link to the main content", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />);

    await user.tab();

    const skipLink = screen.getByRole("link", { name: layoutStrings.skipToContent });
    expect(skipLink.matches(":focus")).toBe(true);
    expect(skipLink.getAttribute("href")).toBe(`#${screen.getByRole("main").id}`);
  });

  it.each([
    [layoutStrings.collections, layoutStrings.status],
    [layoutStrings.status, layoutStrings.collections],
  ])(
    "opens %s from the main navigation and marks it as the current page",
    async (target, other) => {
      const user = userEvent.setup();
      renderWithProviders(<App />);

      await user.click(within(mainNav()).getByRole("link", { name: target }));

      expect(screen.getByRole("heading", { level: 1, name: target })).toBeTruthy();
      expect(
        within(mainNav()).getByRole("link", { name: target }).getAttribute("aria-current"),
      ).toBe("page");
      expect(
        within(mainNav()).getByRole("link", { name: other }).hasAttribute("aria-current"),
      ).toBe(false);
    },
  );

  it("goes back to the home page from the logo", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/status" });

    await user.click(screen.getByRole("link", { name: layoutStrings.home }));

    expect(screen.getByRole("heading", { level: 1, name: layoutStrings.collections })).toBeTruthy();
  });

  it("shows a not-found page with a way home for an unknown path", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/nao-existe" });

    expect(screen.getByRole("heading", { level: 1, name: layoutStrings.notFound })).toBeTruthy();

    await user.click(screen.getByRole("link", { name: layoutStrings.backHome }));

    expect(screen.getByRole("heading", { level: 1, name: layoutStrings.collections })).toBeTruthy();
  });

  it("offers a labelled card search field in the top bar", () => {
    renderWithProviders(<App />);

    const search = within(screen.getByRole("banner")).getByRole("search");
    expect(within(search).getByRole("searchbox", { name: layoutStrings.searchLabel })).toBeTruthy();
  });
});
