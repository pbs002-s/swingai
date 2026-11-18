import { expect, test } from "@playwright/test";
import { login, nav, watchErrors } from "./helpers";

test("dashboard pages need a login", async ({ page }) => {
  await page.goto("/app");
  await page.waitForURL("**/login");
});

test("a wrong password shows a clear error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@stitchsense.local");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "wrong" })).toHaveText("Email or password is wrong.");
});

test("overview shows the shift, all lines, alerts and devices", async ({ page }) => {
  const done = watchErrors(page);
  await login(page);
  await expect(page.getByRole("region", { name: "Shift summary" })).toContainText("SMV efficiency");
  const lines = page.getByRole("table").first().getByRole("row");
  await expect.poll(() => lines.count()).toBeGreaterThanOrEqual(7); // header + the 6 demo lines (setup tests may add more)
  await expect(page.getByRole("heading", { name: "Alert center" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Devices" })).toBeVisible();
  await expect(page.getByText("live", { exact: true })).toBeVisible();
  done();
});

test("live floor: switch line, pick a station, see its timeline", async ({ page }) => {
  const done = watchErrors(page);
  await login(page);
  await nav(page, "Live floor");
  await page.getByRole("tab", { name: "Line 5" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Line 5/);
  const tiles = page.getByRole("button", { name: /^L5-S\d+/ });
  await expect(tiles).toHaveCount(24);
  await tiles.nth(6).click();
  await expect(page.getByRole("heading", { name: /^L5-S07/ })).toBeVisible();
  await expect(page.getByRole("img", { name: "Worker timeline" })).toBeVisible();
  done();
});

test("review queue: a supervisor confirms an event", async ({ page }) => {
  await login(page, "supervisor");
  await nav(page, "Review queue");
  const confirm = page.getByRole("button", { name: "Confirm" }).first();
  await expect(confirm).toBeVisible();
  await confirm.click();
  await expect(page.getByRole("status").filter({ hasText: "Confirmed" }).first()).toBeVisible();
});

test("alerts: filter by severity and acknowledge one", async ({ page }) => {
  await login(page);
  await nav(page, "Alerts");
  await page.getByRole("button", { name: /^Warning/ }).click();
  await expect(page.getByRole("button", { name: /^Warning/ })).toHaveAttribute("aria-pressed", "true");
  const ack = page.getByRole("button", { name: "Acknowledge" }).first();
  if (await ack.count()) {
    await ack.click();
    await expect(page.getByText("acknowledged").first()).toBeVisible();
  }
});

test("needles: the bad lot shows a batch pattern and can be quarantined", async ({ page }) => {
  await login(page, "quality");
  await nav(page, "Needles");
  const row = page.locator("tr", { hasText: "B-104" });
  await expect(row).toContainText("Batch pattern");
  const button = page.getByRole("button", { name: "Quarantine lot B-104" });
  if (await button.count()) await button.click();
  await expect(row).toContainText("quarantined");
});

test("settings: admin edits an alert rule; supervisor cannot", async ({ page }) => {
  await login(page);
  await nav(page, "Settings");
  await expect(page.getByRole("heading", { name: "Factory simulator" })).toBeVisible();
  const idle = page.getByRole("listitem").filter({ hasText: "Idle at station" });
  const input = idle.getByRole("spinbutton");
  const next = String(Number(await input.inputValue()) === 8 ? 9 : 8);
  await input.fill(next);
  await idle.getByRole("button", { name: "Save" }).click();
  await expect(idle.getByRole("button", { name: "Saved" })).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL("**/login");
  await login(page, "supervisor");
  await nav(page, "Settings");
  await expect(page.getByText("Only a factory admin can change these.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Factory simulator" })).toHaveCount(0);
});

test("language and theme switch", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "বাংলা" }).click();
  await expect(page.getByRole("link", { name: "লাইভ ফ্লোর" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "bn");
  await page.getByRole("button", { name: "EN" }).click();
  await page.getByRole("button", { name: /Switch to (dark|light) theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", /dark|light/);
});

test("log out ends the session", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await page.waitForURL("**/login");
  await page.goto("/app");
  await page.waitForURL("**/login");
});
