import { shellStrings } from "../src/shell/strings.ts";
import { expect, test } from "./test.ts";

test("keyboard users move through the top bar in reading order", async ({ page }) => {
  await page.goto("/");

  const stops = [
    page.getByRole("link", { name: shellStrings.skipToContent }),
    page.getByRole("link", { name: shellStrings.home }),
    page.getByRole("searchbox", { name: shellStrings.searchLabel }),
    page.getByRole("link", { name: shellStrings.collections, exact: true }),
    page.getByRole("link", { name: shellStrings.status, exact: true }),
  ];
  for (const stop of stops) {
    await page.keyboard.press("Tab");
    await expect(stop).toBeFocused();
  }
});

test("the main navigation opens the Coleções page", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: shellStrings.collections, exact: true }).click();

  await expect(page).toHaveURL("/colecoes");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(shellStrings.collections);
});

test("submitting the search keeps the current page", async ({ page }) => {
  await page.goto("/status");

  const search = page.getByRole("searchbox", { name: shellStrings.searchLabel });
  await search.fill("Torchic");
  await search.press("Enter");

  await expect(page).toHaveURL("/status");
  await expect(search).toHaveValue("Torchic");
});

test("the display and text fonts load from the app itself", async ({ page }) => {
  await page.goto("/colecoes");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const loadedFamilies = await page.evaluate(async () => {
    await document.fonts.ready;
    const families: string[] = [];
    document.fonts.forEach((font) => {
      if (font.status === "loaded") families.push(font.family);
    });
    return families;
  });

  expect(loadedFamilies).toEqual(expect.arrayContaining(["Fredoka", "Nunito"]));
});

test.describe("on a phone", () => {
  test.use({ viewport: { width: 375, height: 800 } });

  test("the menu button reveals the navigation links", async ({ page }) => {
    await page.goto("/colecoes");
    const statusLink = page.getByRole("link", { name: shellStrings.status });
    await expect(statusLink).toBeHidden();

    await page.getByRole("button", { name: shellStrings.menu }).click();
    await statusLink.click();

    await expect(page).toHaveURL("/status");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(shellStrings.status);
    await expect(statusLink).toBeHidden();
  });

  test("the search button reveals the search field", async ({ page }) => {
    await page.goto("/");
    const search = page.getByRole("searchbox", { name: shellStrings.searchLabel });
    await expect(search).toBeHidden();

    await page.getByRole("button", { name: shellStrings.openSearch }).click();

    await expect(search).toBeFocused();
  });
});
