import path from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";


const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../tests/fixtures/scripts/e2e-30min-public-security.md"
);


async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
      )
    )
    .toBe(true);
}


for (const width of [1440, 1024, 768, 390]) {
  test(`fixture review remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let confirmRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/confirm")) confirmRequests += 1;
    });

    await page.goto("/");
    await expect(page.getByRole("heading", {
      name: "Upload a script. Skip the questionnaire.",
    })).toBeVisible();
    await expectNoHorizontalScroll(page);

    await page.getByLabel("Choose a script").setInputFiles(fixture);
    await page.getByRole("button", { name: "Extract project details" }).click();

    await expect(page.getByLabel("Project title")).toHaveValue("先挂电话");
    await expect(page.getByText("1 episode · 30 min · 15 scenes")).toBeVisible();
    await expect(page.getByLabel("Episode count")).toHaveValue("10");
    await expect(page.getByLabel("Minutes per episode")).toHaveValue("3");
    expect(confirmRequests).toBe(0);
    await expect(page.getByText("Nothing runs until you confirm.")).toBeVisible();
    await expectNoHorizontalScroll(page);

    const reviewUrl = page.url();
    expect(reviewUrl).toMatch(/\?review=rev_/);
    await page.reload();
    await expect(page.getByLabel("Project title")).toHaveValue("先挂电话");
    expect(page.url()).toBe(reviewUrl);

    await page.getByRole("button", { name: "Confirm & analyze risks" }).click();
    await expect(page.getByRole("heading", { name: "Review results" })).toBeVisible();
    expect(confirmRequests).toBe(1);
    await expect(page.getByText("Class 1")).toBeVisible();
    await expect(page.getByText("Co-review required")).toBeVisible();
    await expect(page.getByText("Public security subject")).toBeVisible();
    await expect(page.getByText(/semantic review is pending/i)).toBeVisible();
    await expect(page.getByText("Needs human review").first()).toBeVisible();
    await expect(page.getByText(/^Passed$/i)).toHaveCount(0);
    await expectNoHorizontalScroll(page);

    const packageRegion = page.getByRole("region", { name: "Review package" });
    await expect(packageRegion.getByRole("link")).toHaveCount(4);
    const beyond = page.getByRole("region", { name: "Beyond this demo" });
    await expect(beyond.getByRole("link")).toHaveCount(0);
    await expect(beyond.getByRole("button")).toHaveCount(0);

    if (width === 1440) {
      const expectedContent: Record<string, string> = {
        "project-review-form.pdf": "Routing authority",
        "risk-summary.pdf": "Counts by category",
        "annotated-script.md": "<!-- RISK-001",
        "e2e-30min-public-security.md": "# 《先挂电话》",
      };
      for (const [filename, marker] of Object.entries(expectedContent)) {
        const downloadPromise = page.waitForEvent("download");
        const linkName = filename.startsWith("e2e-") ? /Original source/ : new RegExp(filename);
        await packageRegion.getByRole("link", { name: linkName }).click();
        const download = await downloadPromise;
        expect(download.suggestedFilename()).toBe(filename);
        const downloadedPath = await download.path();
        expect(downloadedPath).not.toBeNull();
        const content = await readFile(downloadedPath!);
        if (filename.endsWith(".pdf")) expect(content.subarray(0, 5).toString()).toBe("%PDF-");
        expect(content.toString("utf8")).toContain(marker);
      }
    }
  });
}


test("primary path remains keyboard navigable", async ({ page }) => {
  await page.goto("/");
  const fileInput = page.getByLabel("Choose a script");
  await expect(fileInput).toBeFocused();
  await fileInput.setInputFiles(fixture);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Extract project details" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.getByLabel("Project title")).toBeFocused();
  for (let index = 0; index < 6; index += 1) await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Confirm & analyze risks" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Review results" })).toBeFocused();
});
