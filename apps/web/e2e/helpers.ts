import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export const PASSWORD = "stitchsense-demo";
export const USERS = {
  admin: "admin@stitchsense.local",
  supervisor: "supervisor@stitchsense.local",
  quality: "quality@stitchsense.local",
  maintenance: "maintenance@stitchsense.local",
  manager: "manager@stitchsense.local",
} as const;

export async function login(page: Page, who: keyof typeof USERS = "admin") {
  await page.goto("/login");
  await page.getByLabel("Email").fill(USERS[who]);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await page.waitForURL("**/app");
  await expect(page.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
}

/** Collects console errors and page errors; call the returned function at the end of a test. */
export function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error" && !/Download the React DevTools|net::ERR_ABORTED/.test(m.text())) errors.push(m.text());
  });
  return () => expect(errors, errors.join("\n")).toEqual([]);
}

export async function nav(page: Page, name: string) {
  await page.getByRole("navigation", { name: "App" }).getByRole("link", { name, exact: true }).click();
}
