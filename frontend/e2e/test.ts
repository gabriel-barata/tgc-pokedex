import { test as base, expect } from "@playwright/test";

export const test = base.extend<{ blockExternalRequests: undefined }>({
  blockExternalRequests: [
    async ({ context, baseURL }, use) => {
      const appOrigin = new URL(baseURL ?? "").origin;
      const blocked: string[] = [];
      await context.route(
        (url) => url.origin !== appOrigin,
        (route) => {
          blocked.push(route.request().url());
          return route.abort("blockedbyclient");
        },
      );
      await use(undefined);
      expect(blocked, "requests outside the app origin (Principle VI)").toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };
