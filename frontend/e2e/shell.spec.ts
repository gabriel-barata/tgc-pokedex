import { shellStrings } from "../src/shell/strings.ts";
import { expect, test } from "./test.ts";

test("keyboard users move through the top bar in reading order", async ({ page }) => {
  await page.goto("/");

  const stops = [
    page.getByRole("link", { name: shellStrings.skipToContent }),
    page.getByRole("link", { name: shellStrings.home }),
    page.getByRole("searchbox", { name: shellStrings.searchLabel }),
    page.getByRole("link", { name: shellStrings.collections }),
    page.getByRole("link", { name: shellStrings.status }),
  ];
  for (const stop of stops) {
    await page.keyboard.press("Tab");
    await expect(stop).toBeFocused();
  }
});

test("the main navigation opens the Coleções page", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: shellStrings.collections }).click();

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
