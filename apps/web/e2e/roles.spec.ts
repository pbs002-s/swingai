import { expect, test } from "@playwright/test";
import { login } from "./helpers";
import type { USERS } from "./helpers";

// Each demo login holds one role; the menu must show exactly that role's pages.
const MENU: Record<keyof typeof USERS, string[]> = {
  admin: ["Overview", "Live floor", "Review queue", "Alerts", "Live cameras", "Cameras", "Needles", "Performance", "Reports", "Setup", "Settings", "Lab"],
  supervisor: ["Overview", "Live floor", "Review queue", "Alerts", "Live cameras"],
  quality: ["Overview", "Review queue", "Alerts", "Needles"],
  maintenance: ["Overview", "Live floor", "Review queue", "Alerts", "Needles"],
  manager: ["Overview", "Live cameras", "Needles", "Performance", "Reports"],
};

for (const [who, items] of Object.entries(MENU) as [keyof typeof USERS, string[]][]) {
  test(`${who} sees only their pages`, async ({ page }) => {
    await login(page, who);
    await expect(page.getByRole("navigation", { name: "App" }).getByRole("link")).toHaveText(items);
  });
}

test("a page outside the role shows no-access instead of its content", async ({ page }) => {
  await login(page, "supervisor");
  await page.goto("/app/performance");
  await expect(page.getByRole("heading", { name: "Your role cannot open this page" })).toBeVisible();
  await page.goto("/app/cameras/live"); // the longer href wins over /app/cameras
  await expect(page.getByRole("heading", { level: 1, name: "Live cameras" })).toBeVisible();
});
