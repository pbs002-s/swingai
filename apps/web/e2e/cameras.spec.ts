import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { login, watchErrors } from "./helpers";

// Needs the demo seed's EDGE-1 to be a simulated edge box ({"simulated": true}).

async function next(page: Page) {
  await page.getByRole("button", { name: "Next", exact: true }).click();
}

async function clickSnapshot(page: Page, x: number, y: number) {
  const box = await page.getByRole("img", { name: /Camera snapshot with/ }).boundingBox();
  if (!box) throw new Error("zone canvas not visible");
  await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
}

test("add a camera with the wizard against the simulated edge box", async ({ page }) => {
  test.setTimeout(90_000);
  const done = watchErrors(page);
  await login(page);
  await page.goto("/app/cameras");
  await expect(page.getByRole("heading", { level: 1, name: "Cameras" })).toBeVisible();
  await page.getByRole("link", { name: "Add camera" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Add camera" })).toBeVisible();
  const steps = page.getByRole("navigation", { name: "Add camera steps" });
  await expect(steps.locator('[aria-current="step"]')).toContainText("Edge box");

  // 1 Edge box
  await page.getByRole("radio", { name: /EDGE-1/ }).check();
  await next(page);

  // 2 Find camera: scan, pick the first one, fill credentials
  await expect(steps.locator('[aria-current="step"]')).toContainText("Find camera");
  await page.getByRole("button", { name: "Start scan" }).click();
  const found = page.getByRole("list", { name: "Cameras found" });
  await expect(found).toBeVisible({ timeout: 15_000 });
  await found.getByRole("button", { name: /^Use / }).first().click();
  await expect(page.getByLabel("IP address or hostname")).toHaveValue(/^10\.20\.0\./);
  await page.getByLabel("Camera name").fill("E2E camera");
  await page.getByLabel("Camera username").fill("admin");
  const password = page.getByLabel("Camera password");
  await expect(password).toHaveAttribute("type", "password");
  await password.fill("wrong");
  await page.getByRole("button", { name: "Show" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await next(page);

  // 3 Test: a wrong password fails clearly, then the right one works
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Connection test failed" })).toContainText("Authentication failed (401)", { timeout: 15_000 });
  await page.getByRole("button", { name: "Back" }).click();
  await page.getByRole("button", { name: "Enter manually" }).click();
  await page.getByLabel("Camera password").fill("camera-pass-1");
  await next(page);
  await page.getByRole("button", { name: "Test connection" }).click();
  const details = page.getByRole("definition");
  await expect(page.getByText("Connection works.")).toBeVisible({ timeout: 15_000 });
  await expect(details.filter({ hasText: "1920x1080" })).toBeVisible();
  await expect(details.filter({ hasText: "H.264" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Snapshot from the camera under test" })).toBeVisible();
  await next(page);

  // 4 Assign: line, then two stations; a third is refused
  await page.getByLabel("Line", { exact: true }).selectOption({ index: 1 });
  const boxes = page.getByRole("checkbox");
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await expect(boxes.nth(2)).toBeDisabled();
  await next(page);

  // 5 Zones: a work zone by clicking, a privacy mask by keyboard entry
  await clickSnapshot(page, 0.3, 0.3);
  await clickSnapshot(page, 0.6, 0.3);
  await clickSnapshot(page, 0.5, 0.7);
  await clickSnapshot(page, 0.2, 0.7);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Points in this zone (3)")).toBeVisible();
  await page.getByRole("button", { name: "Close polygon" }).click();
  await page.getByRole("radio", { name: "Privacy mask" }).check();
  for (const [x, y] of [["0", "0"], ["20", "0"], ["20", "100"]]) {
    await page.getByLabel("Across (%)").fill(x);
    await page.getByLabel("Down (%)").fill(y);
    await page.getByRole("button", { name: "Add point" }).click();
  }
  await page.getByRole("button", { name: "Close polygon" }).click();
  await expect(page.getByText("Saved zones (2)")).toBeVisible();
  await next(page);

  // 6 Settings: defaults are activity, 5 fps, face blur on
  await expect(page.getByRole("radio", { name: /Worker activity/ })).toBeChecked();
  await expect(page.getByLabel("Analysis rate (frames per second)")).toHaveValue("5");
  await expect(page.getByRole("checkbox", { name: /Blur faces/ })).toBeChecked();
  await next(page);

  // 7 Save and verify
  await page.getByRole("button", { name: "Save and run test detection" }).click();
  await expect(page.getByText(/^Saved as CAM-/)).toBeVisible();
  const detections = page.getByRole("list", { name: "Detections" });
  await expect(detections).toContainText("person", { timeout: 15_000 });
  await expect(detections).toContainText("phone");
  await expect(page.getByRole("img", { name: /Annotated snapshot/ })).toBeVisible();
  await expect(page.getByText("camera-pass-1")).toHaveCount(0);

  await page.getByRole("link", { name: "Done, back to cameras" }).click();
  const row = page.getByRole("row").filter({ hasText: "E2E camera" }).first();
  await expect(row).toContainText("Online");
  await expect(row).toContainText("2");
  done();
});

test("a supervisor cannot add cameras", async ({ page }) => {
  await login(page, "supervisor");
  await page.goto("/app/cameras/new");
  await expect(page.getByText("Only a factory admin can add cameras")).toBeVisible();
});
