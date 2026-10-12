import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "@/App.tsx";
import { server } from "@/testing/server.ts";
import { renderWithProviders } from "@/testing/render.tsx";
import { layoutStrings } from "@/strings/layout.ts";

function menuButton() {
  return screen.getByRole("button", { name: layoutStrings.menu });
}

beforeEach(() => {
  server.use(http.get("/api/sets", () => new Promise<never>(() => undefined)));
});

describe("top bar menu on narrow screens", () => {
  it("opens the main navigation and closes it with Escape, returning focus to the button", async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />, { route: "/colecoes" });
    expect(menuButton().getAttribute("aria-expanded")).toBe("false");

    await user.click(menuButton());

    expect(menuButton().getAttribute("aria-expanded")).toBe("true");
    const nav = screen.getByRole("navigation", { name: layoutStrings.mainNav });
    expect(menuButton().getAttribute("aria-controls")).toBe(nav.id);

    await user.tab();
    await user.keyboard("{Escape}");

    expect(menuButton().getAttribute("aria-expanded")).toBe("false");
    expect(menuButton().matches(":focus")).toBe(true);
  });
});
