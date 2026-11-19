import { expect, test } from "@playwright/test";
import { login } from "./helpers";

// Chrome's fake camera shows a test pattern with no person in it.
test.use({
  permissions: ["camera"],
  launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] },
});

test("lab: camera streams to Live cameras and the analysis reports an empty scene as away", async ({ page }) => {
  test.setTimeout(90_000); // the detection model downloads on first use
  await login(page, "admin");
  await page.goto("/app/lab");
  const name = `E2E lab cam ${Date.now()}`; // unique, so reruns never match an old camera
  await page.getByLabel("Camera name").fill(name);
  await page.getByRole("button", { name: "Start camera" }).click();
  await expect(page.getByText("Live, also in Live cameras")).toBeVisible();

  await expect(page.getByText("Away from camera").first()).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Phone use detected (0)")).toBeVisible();

  const wall = await page.context().newPage();
  await wall.goto("/app/cameras/live");
  const tile = wall.getByRole("button", { name: new RegExp(name) });
  await expect(tile.getByText("Test camera")).toBeVisible();
  await expect(tile.getByText(/Waiting for the camera/)).toBeHidden();
});
