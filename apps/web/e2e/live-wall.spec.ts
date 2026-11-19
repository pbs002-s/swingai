import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("live wall opens a camera full screen and arrow keys switch cameras", async ({ page }) => {
  await login(page, "supervisor");
  await page.goto("/app/cameras/live");
  await page.getByRole("button", { name: /full screen/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const first = await dialog.getAttribute("aria-label");
  await page.keyboard.press("ArrowRight");
  await expect(dialog).not.toHaveAttribute("aria-label", first ?? "");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
