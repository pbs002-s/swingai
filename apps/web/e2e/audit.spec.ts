import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("audit log: admin reads and filters entries, supervisors cannot open it", async ({ page }) => {
  await login(page, "admin");
  await page.getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Audit log" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Audit entries" })).toBeVisible(); // logging in writes rows
  await page.getByLabel("Action starts with").fill("no.such.action");
  await expect(page.getByText("Nothing matches these filters.")).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL("**/login");
  await login(page, "supervisor");
  await page.goto("/app/audit");
  await expect(page.getByRole("heading", { name: "Your role cannot open this page" })).toBeVisible();
});
