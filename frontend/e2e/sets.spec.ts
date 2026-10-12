import type { Locator, Page } from "@playwright/test";
import { setsStrings } from "../src/strings/sets.ts";
import { expect, test } from "./test.ts";

async function pressUntilFocused(page: Page, target: Locator, key: "Tab" | "Shift+Tab") {
  for (let presses = 0; presses < 40; presses++) {
    await page.keyboard.press(key);
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`${key} never reached the target`);
}

test("keyboard users track a set from the catalog and open it from its cover", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL("/colecoes");
  const catalog = page.getByRole("region", { name: setsStrings.allSets });
  await expect(catalog.getByRole("listitem")).toHaveText([
    /Fogo Fantasmagórico.*2025.*94 cartas/,
    /MEP Black Star Promos.*2025.*88 cartas/,
    /Rivais Predestinados.*2025.*182 cartas/,
  ]);
  const covers = page.getByRole("region", { name: setsStrings.trackedSets });
  await expect(covers).toContainText(setsStrings.noTrackedSets);

  const track = catalog
    .getByRole("listitem")
    .filter({ hasText: "Fogo Fantasmagórico" })
    .getByRole("button");
  await pressUntilFocused(page, track, "Tab");
  await page.keyboard.press("Enter");

  await expect(track).toHaveAttribute("aria-pressed", "true");
  const cover = covers.getByRole("link", { name: "Fogo Fantasmagórico" });
  await expect(cover).toBeVisible();

  await pressUntilFocused(page, cover, "Shift+Tab");
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL("/colecoes/me02");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Fogo Fantasmagórico");
});
