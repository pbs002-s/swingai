import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("policies: admin saves a new version and sees it in the history; invalid input explains itself", async ({ page }) => {
  await login(page, "admin");
  await page.getByRole("link", { name: "Policies" }).click();
  const retention = page.getByRole("region", { name: "Data retention" });
  await expect(retention).toBeVisible();

  await retention.getByLabel(/Keep activity events/).fill("5");
  await retention.getByRole("button", { name: "Save as new version" }).click();
  await expect(retention.getByRole("alert")).toContainText("events_days");

  const days = String(300 + (Date.now() % 50));
  await retention.getByLabel(/Keep activity events/).fill(days);
  await retention.getByRole("button", { name: "Save as new version" }).click();
  await expect(retention.getByRole("status")).toContainText("New version saved");
  await retention.getByText(/History \(/).click();
  await expect(retention.getByRole("listitem").first()).toContainText(`"events_days":${days}`);
});

test("policies: management can read but not change", async ({ page }) => {
  await login(page, "manager");
  await page.goto("/app/policies");
  await expect(page.getByRole("region", { name: "Shift" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save as new version" })).toHaveCount(0);
});
