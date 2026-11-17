import { expect, test } from "@playwright/test";
import { watchErrors } from "./helpers";

test("landing tells the story and every section is reachable from the nav", async ({ page }) => {
  const done = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/Sewing-floor monitoring for garment factories/);
  await expect(page.getByRole("img", { name: /Animated factory line/ })).toBeVisible();
  for (const [link, heading] of [
    ["How it works", "From the needle to the shift report"],
    ["Needle tracing", "Needle breaks, traced to the batch"],
    ["Fair use", "Numbers people can trust, checked by people"],
    ["Installation", "Installed in your factory, on your server"],
  ]) {
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: link }).click();
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeInViewport();
  }
  done();
});

test("the factory animation keeps producing", async ({ page }) => {
  await page.goto("/");
  const sewn = page.locator("text=garments sewn").locator("..").locator("span").first();
  const read = async () => Number((await sewn.textContent())?.replace(/,/g, ""));
  await expect.poll(read).toBeGreaterThan(0);
  const first = await read();
  await expect.poll(read, { timeout: 15_000 }).toBeGreaterThan(first);
});

test("site-survey form validates, then sends", async ({ page }) => {
  await page.goto("/#contact");
  const form = page.getByRole("form", { name: "Book a site survey" });
  await form.getByRole("button", { name: "Book a site survey" }).click();
  await expect(form.getByLabel("Your name")).toBeFocused(); // browser validation stops the empty send
  await form.getByLabel("Your name").fill("Test Buyer");
  await form.getByLabel("Work email").fill("buyer@factory.example");
  await form.getByLabel("Factory or company").fill("Example Garments");
  await form.getByLabel("Sewing stations").selectOption("100_500");
  await form.getByRole("button", { name: "Book a site survey" }).click();
  await expect(page.getByRole("status")).toContainText("We will be in touch");
});
