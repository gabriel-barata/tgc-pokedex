import { statusStrings } from "../src/status/strings.ts";
import { expect, test } from "./test.ts";

test("the status page lists the sync runs and a run's failures", async ({ page }) => {
  await page.goto("/status");

  const runs = page.getByRole("list", { name: statusStrings.runs });
  const images = runs.getByRole("listitem").filter({ hasText: "16 buscados" });
  await expect(images).toContainText(statusStrings.status.succeeded);
  await expect(images).toContainText("42 s");
  const catalog = runs.getByRole("listitem").filter({ hasText: "125 buscados" });
  await expect(catalog).toContainText(statusStrings.status.partial);
  await expect(catalog).toContainText("6 alterados · 1 falha");

  await catalog.getByRole("button", { name: statusStrings.showFailures(1) }).click();

  await expect(catalog.getByRole("list", { name: statusStrings.failures })).toHaveText(
    "Coleção sv02: HTTP 500 after 3 attempts",
  );
});
