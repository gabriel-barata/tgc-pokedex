import { healthStrings } from "../src/health/strings.ts";
import { expect, test } from "./test.ts";

test("home page shows the API as online", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("status")).toHaveText(healthStrings.online);
});
