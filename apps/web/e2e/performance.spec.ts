import { expect, test } from "@playwright/test";
import { login, nav, watchErrors } from "./helpers";

test("performance: ranking renders and a row opens its explanation", async ({ page }) => {
  const done = watchErrors(page);
  await login(page);
  await nav(page, "Performance");
  await expect(page.getByRole("heading", { level: 1, name: "Performance" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("Bonus and training suggestions stay off");
  await expect(page.getByRole("heading", { name: "Ranking" })).toBeVisible();
  const explain = page.getByRole("region", { name: /Score explanation|Why |insufficient data/ });
  await expect(explain).toContainText("Pick a worker");

  const workers = page.getByRole("table").getByRole("button");
  if ((await workers.count()) === 0) {
    await expect(page.getByText("No production in this period")).toBeVisible();
  } else {
    await workers.first().click();
    await expect(workers.first()).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("region", { name: /^Why .+ scores|insufficient data/ })).toContainText("Production");
  }
  await page.getByLabel("Period").selectOption("14");
  await expect(page.getByRole("heading", { name: "Ranking" })).toBeVisible();
  done();
});

test("performance: weights must be whole numbers totalling 100", async ({ page }) => {
  await login(page);
  await nav(page, "Performance");
  await page.getByRole("button", { name: "Edit weights" }).click();
  const form = page.getByRole("form", { name: "Ranking weights" });
  const save = form.getByRole("button", { name: /^Save as version/ });

  await form.getByLabel("Production").fill("60");
  await form.getByLabel("Quality").fill("35");
  await form.getByLabel("Productive time").fill("15");
  await expect(form).toContainText("Total 110 of 100");
  await expect(save).toBeDisabled();

  await form.getByLabel("Quality").fill("25");
  await expect(form).toContainText("Total 100 of 100");
  await expect(save).toBeEnabled();

  await form.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByRole("button", { name: "Edit weights" })).toBeVisible();
});

test("performance: management sees the ranking but cannot edit weights", async ({ page }) => {
  await login(page, "manager");
  await nav(page, "Performance");
  await expect(page.getByRole("heading", { name: "Ranking" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit weights" })).toHaveCount(0);
});
