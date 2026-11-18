import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { login, watchErrors } from "./helpers";

const tag = Date.now().toString(36).slice(-5).toUpperCase();

async function openTab(page: Page, name: string) {
  await page.goto("/app/setup");
  await expect(page.getByRole("heading", { level: 1, name: "Setup" })).toBeVisible();
  await page.getByRole("tab", { name, exact: true }).click();
  await expect(page.getByRole("tab", { name, exact: true })).toHaveAttribute("aria-selected", "true");
}

test("structure: add a line, then add stations in bulk", async ({ page }) => {
  const done = watchErrors(page);
  await login(page);
  await openTab(page, "Structure");
  const floors = page.getByRole("region", { name: "Floors and lines" });
  await floors.getByLabel("Line code").first().fill(`E2E${tag}`);
  await floors.getByLabel("Line name").first().fill(`E2E line ${tag}`);
  await floors.getByRole("button", { name: "Add line" }).first().click();
  await expect(floors.getByRole("status").filter({ hasText: "Line added." })).toBeVisible();

  await page.getByLabel("Show stations for line").selectOption({ label: `E2E line ${tag} (E2E${tag})` });
  const stations = page.getByRole("region", { name: `Stations on E2E line ${tag}` });
  await stations.getByLabel("How many").fill("3");
  await stations.getByRole("button", { name: "Add stations" }).click();
  await expect(stations.getByRole("status")).toContainText("Added 3 stations");
  await expect(stations.getByRole("cell", { name: `E2E${tag}-S003`, exact: true })).toBeVisible();
  done();
});

test("lists and machines: add a type and a brand, then a machine using them", async ({ page }) => {
  await login(page);
  await openTab(page, "Lists");
  const types = page.getByRole("region", { name: "Machine types" });
  await types.getByLabel("Code").fill(`T${tag}`);
  await types.getByLabel("Name", { exact: true }).fill(`Type ${tag}`);
  await types.getByRole("button", { name: "Add" }).click();
  await expect(types.getByRole("status")).toContainText("added");
  const brands = page.getByRole("region", { name: "Machine brands" });
  await brands.getByLabel("Name", { exact: true }).fill(`Brand ${tag}`);
  await brands.getByRole("button", { name: "Add" }).click();
  await expect(brands.getByRole("status")).toContainText("added");

  await page.getByRole("tab", { name: "Machines", exact: true }).click();
  const machines = page.getByRole("region", { name: "Machines" });
  await machines.getByLabel("Asset code").fill(`M-${tag}`);
  await machines.getByLabel("Machine type").selectOption({ label: `Type ${tag}` });
  await machines.getByLabel("Brand").selectOption({ label: `Brand ${tag}` });
  await machines.getByRole("button", { name: "Add machine" }).click();
  await expect(machines.getByRole("status")).toContainText(`Machine M-${tag} added.`);
  await expect(machines.getByRole("cell", { name: `M-${tag}`, exact: true })).toBeVisible();
});

test("workers: add a worker", async ({ page }) => {
  await login(page);
  await openTab(page, "Workers");
  const workers = page.getByRole("region", { name: "Workers" });
  await workers.getByLabel("Employee code").fill(`E-${tag}`);
  await workers.getByLabel("Full name", { exact: true }).fill(`E2E Worker ${tag}`);
  await workers.getByRole("button", { name: "Add worker" }).click();
  await expect(workers.getByRole("status")).toContainText(`Worker E-${tag} added.`);
});

test("import: preview of a bad CSV lists row errors and saves nothing", async ({ page }) => {
  await login(page);
  await openTab(page, "Import");
  await page.getByLabel("What to import").selectOption("workers");
  const csv = [
    "employee_code,factory_code,full_name,full_name_bn,rfid_card_id,joined_on,skills",
    `E-B${tag},NOPE,Bad Factory,,,,`,
    `E-C${tag},U2,,,,,`,
  ].join("\n");
  await page.getByLabel("CSV file").setInputFiles({ name: "bad.csv", mimeType: "text/csv", buffer: Buffer.from(csv, "utf-8") });
  await page.getByRole("button", { name: "Preview" }).click();
  const errors = page.getByRole("table", { name: "Row errors" });
  await expect(errors.getByRole("row")).toHaveCount(3); // header + 2 rows
  await expect(errors).toContainText("factory_code");
  await expect(errors).toContainText("full_name");
  await expect(page.getByRole("button", { name: "Import valid rows" })).toBeDisabled();
});

test("a supervisor cannot open setup", async ({ page }) => {
  await login(page, "supervisor");
  await page.goto("/app/setup");
  await expect(page.getByRole("heading", { name: "Your role cannot open this page" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add line" })).toHaveCount(0);
});
