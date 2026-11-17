import { expect, test } from "@playwright/test";
import { login, nav } from "./helpers";

const noSideScroll = async (page: import("@playwright/test").Page) =>
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

test("landing fits a phone screen", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await noSideScroll(page);
  await page.goto("/#contact");
  await noSideScroll(page);
});

test("dashboard fits a phone screen", async ({ page }) => {
  await login(page);
  await noSideScroll(page);
  await nav(page, "Live floor");
  await expect(page.getByRole("tablist", { name: "Lines" })).toBeVisible();
  await noSideScroll(page);
});
