import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "../App.tsx";
import { renderWithProviders } from "../test-utils.tsx";
import { shellStrings } from "./strings.ts";

function menuButton() {
  return screen.getByRole("button", { name: shellStrings.menu });
}

function searchButton() {
  return screen.getByRole("button", { name: shellStrings.openSearch });
}

describe("top bar menu on narrow screens", () => {
  it("opens the main navigation and closes it with Escape, returning focus to the button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/colecoes" });
    expect(menuButton().getAttribute("aria-expanded")).toBe("false");

    await user.click(menuButton());

    expect(menuButton().getAttribute("aria-expanded")).toBe("true");
    const nav = screen.getByRole("navigation", { name: shellStrings.mainNav });
    expect(menuButton().getAttribute("aria-controls")).toBe(nav.id);

    await user.tab();
    await user.keyboard("{Escape}");

    expect(menuButton().getAttribute("aria-expanded")).toBe("false");
    expect(menuButton().matches(":focus")).toBe(true);
  });

  it("closes after a link in it is chosen", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/colecoes" });

    await user.click(menuButton());
    const nav = screen.getByRole("navigation", { name: shellStrings.mainNav });
    await user.click(within(nav).getByRole("link", { name: shellStrings.status }));

    expect(screen.getByRole("heading", { level: 1, name: shellStrings.status })).toBeTruthy();
    expect(menuButton().getAttribute("aria-expanded")).toBe("false");
  });
});

describe("top bar search on phones", () => {
  it("reveals the search field with focus and hides it again with Escape", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/colecoes" });
    expect(searchButton().getAttribute("aria-expanded")).toBe("false");

    await user.click(searchButton());

    expect(searchButton().getAttribute("aria-expanded")).toBe("true");
    const field = screen.getByRole("searchbox", { name: shellStrings.searchLabel });
    expect(field.matches(":focus")).toBe(true);

    await user.keyboard("{Escape}");

    expect(searchButton().getAttribute("aria-expanded")).toBe("false");
    expect(searchButton().matches(":focus")).toBe(true);
  });
});
