import { expect, test } from "@playwright/test";

test("live wall opens a camera full screen and arrow keys switch cameras", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("supervisor@stitchsense.local");
  await page.getByLabel(/password/i).fill("stitchsense-demo");
  await page.getByRole("button", { name: /log in|sign in/i }).click();
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
