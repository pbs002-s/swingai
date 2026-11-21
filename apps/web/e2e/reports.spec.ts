import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("management opens the day report and can download CSV; supervisors cannot open Reports", async ({ page }) => {
  await login(page, "manager");
  await page.goto("/app/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByRole("article", { name: "Day report" })).toBeVisible();
  const csv = await page.evaluate(async () => {
    const lineId = (document.querySelector("select") as HTMLSelectElement).value;
    const date = (document.querySelector("input[type=date]") as HTMLInputElement).value;
    const r = await fetch(`/api/v1/reports/day.csv?date=${date}&line_id=${lineId}`);
    return { status: r.status, type: r.headers.get("content-type") };
  });
  expect(csv.status).toBe(200);
  expect(csv.type).toContain("text/csv");

  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL("**/login");
  await login(page, "supervisor");
  await page.goto("/app/reports");
  await expect(page.getByRole("heading", { name: "Your role cannot open this page" })).toBeVisible();
});
