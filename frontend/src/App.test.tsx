import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { App } from "./App.tsx";
import { healthStrings } from "./health/strings.ts";
import { server } from "./test-server.ts";
import { renderWithProviders } from "./test-utils.tsx";

function apiStatusText() {
  return screen.getByRole("status").textContent;
}

describe("home page API health", () => {
  it("shows that the API is being checked while /healthz is pending", () => {
    server.use(http.get("/healthz", () => new Promise<never>(() => undefined)));

    renderWithProviders(<App />);

    expect(apiStatusText()).toBe(healthStrings.checking);
  });

  it("shows the API as online when /healthz answers ok", async () => {
    server.use(http.get("/healthz", () => HttpResponse.json({ status: "ok" })));

    renderWithProviders(<App />);

    await expect.poll(apiStatusText).toBe(healthStrings.online);
  });

  it.each([
    ["an error status", () => new HttpResponse(null, { status: 503 })],
    ["a network error", () => HttpResponse.error()],
  ])("shows the API as unavailable when /healthz returns %s", async (_case, resolver) => {
    server.use(http.get("/healthz", resolver));

    renderWithProviders(<App />);

    await expect.poll(apiStatusText).toBe(healthStrings.offline);
  });
});
