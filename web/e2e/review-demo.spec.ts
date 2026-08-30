import path from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";


const fixtures = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../tests/fixtures/scripts"
);
const thirtyMinuteFixture = path.join(fixtures, "e2e-30min-public-security-en.md");
const seventyMinuteFixture = path.join(fixtures, "e2e-70min-judicial-long-context-en.md");

const THIRTY_MINUTE_SYNOPSIS =
  "A community police officer helps a father and daughter turn an almost-successful scam call into an honest public warning and a new way to stay in contact.";
const SEVENTY_MINUTE_SYNOPSIS =
  "A playwright challenges the missing credit on her late mentor's work, and a mediation and hearing force every contributor to confront the evidence of shared authorship.";


async function expectNoHorizontalScroll(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth
      )
    )
    .toBe(true);
}


async function extractFixture(page: Page, fixture: string) {
  await page.getByLabel("Choose a script").setInputFiles(fixture);
  await page.getByRole("button", { name: "Extract project details" }).click();
  await expect(page.getByLabel("Project title")).toBeVisible();
}


for (const width of [1440, 1024, 768, 390]) {
  test(`English fixture review and reanalysis remain usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    let confirmRequests = 0;
    let reanalysisRequests = 0;
    page.on("request", (request) => {
      if (request.method() === "POST" && request.url().endsWith("/confirm")) {
        confirmRequests += 1;
      }
      if (request.method() === "POST" && request.url().endsWith("/reanalyze")) {
        reanalysisRequests += 1;
      }
    });

    await page.goto("/");
    const uploadTab = page.getByRole("tab", { name: /Upload/ });
    const confirmTab = page.getByRole("tab", { name: /Confirm details/ });
    const resultsTab = page.getByRole("tab", { name: /Review results/ });
    await expect(uploadTab).toHaveAttribute("aria-selected", "true");
    await expect(confirmTab).toBeDisabled();
    await expect(resultsTab).toBeDisabled();
    await expect(page.getByRole("button", { name: /^Back$/i })).toHaveCount(0);
    await expectNoHorizontalScroll(page);

    await extractFixture(page, thirtyMinuteFixture);

    await expect(page.getByLabel("Project title")).toHaveValue("Hang Up First");
    await expect(page.getByLabel("Tags")).toHaveValue(
      "public security, anti-fraud, family drama"
    );
    await expect(page.getByLabel("Synopsis")).toHaveValue(THIRTY_MINUTE_SYNOPSIS);
    await expect(page.getByText("1 episode · 30 min · 15 scenes")).toBeVisible();
    await expect(page.getByLabel("Episode count")).toHaveValue("10");
    await expect(page.getByLabel("Minutes per episode")).toHaveValue("3");
    await expect(confirmTab).toHaveAttribute("aria-selected", "true");
    await expect(resultsTab).toBeDisabled();
    expect(confirmRequests).toBe(0);
    expect(reanalysisRequests).toBe(0);
    await expect(page.getByText("Nothing runs until you confirm.")).toBeVisible();
    await expectNoHorizontalScroll(page);

    const reviewUrl = page.url();
    expect(reviewUrl).toMatch(/\?review=rev_/);
    await page.reload();
    await expect(page.getByLabel("Project title")).toHaveValue("Hang Up First");
    await expect(page.getByLabel("Tags")).toHaveValue(
      "public security, anti-fraud, family drama"
    );
    await expect(page.getByLabel("Synopsis")).toHaveValue(THIRTY_MINUTE_SYNOPSIS);
    expect(page.url()).toBe(reviewUrl);

    await page.getByLabel("Project title").fill("Hang Up First - Confirmed");
    await page.getByRole("button", { name: "Confirm & analyze risks" }).click();
    await expect(page.getByRole("heading", { name: "Review results" })).toBeVisible();
    await expect(resultsTab).toHaveAttribute("aria-selected", "true");
    expect(confirmRequests).toBe(1);
    expect(reanalysisRequests).toBe(0);
    await expect(page.getByText("Class 2")).toBeVisible();
    await expect(page.getByText("No co-review indicated")).toBeVisible();
    await expect(page.getByText("Public security subject")).toBeVisible();
    await expect(page.getByText("Needs human review").first()).toBeVisible();
    await expect(page.getByText(/^Passed$/i)).toHaveCount(0);
    await expectNoHorizontalScroll(page);

    await confirmTab.click();
    await expect(page.getByLabel("Project title")).toHaveValue("Hang Up First - Confirmed");
    await expect(page.getByLabel("Tags")).toHaveValue(
      "public security, anti-fraud, family drama"
    );
    await expect(page.getByLabel("Synopsis")).toHaveValue(THIRTY_MINUTE_SYNOPSIS);
    await page.getByLabel("Project title").fill("Hang Up First - Final Demo Cut");
    await page.getByRole("button", { name: "Confirm changes & reanalyze" }).click();

    await expect(page.getByRole("heading", { name: "Review results" })).toBeVisible();
    await expect(page.getByText("Hang Up First - Final Demo Cut")).toBeVisible();
    expect(confirmRequests).toBe(1);
    expect(reanalysisRequests).toBe(1);
    await expectNoHorizontalScroll(page);

    await uploadTab.click();
    await expect(page.getByLabel("Current script")).toContainText(
      "e2e-30min-public-security-en.md"
    );
    await expect(page.getByRole("button", { name: "Continue with current script" })).toBeVisible();
    await resultsTab.click();
    await expect(page.getByText("Hang Up First - Final Demo Cut")).toBeVisible();
    expect(confirmRequests).toBe(1);
    expect(reanalysisRequests).toBe(1);
    await expect(page.getByRole("button", { name: /^Back$/i })).toHaveCount(0);

    const packageRegion = page.getByRole("region", { name: "Review package" });
    await expect(packageRegion.getByRole("link")).toHaveCount(4);
    const beyond = page.getByRole("region", { name: "Beyond this demo" });
    await expect(beyond.getByRole("link")).toHaveCount(0);
    await expect(beyond.getByRole("button")).toHaveCount(0);

    const downloadPromise = page.waitForEvent("download");
    await packageRegion.getByRole("link", { name: /project-review-form\.pdf/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("project-review-form.pdf");
    const downloadedPath = await download.path();
    expect(downloadedPath).not.toBeNull();
    const content = await readFile(downloadedPath!);
    expect(content.subarray(0, 5).toString()).toBe("%PDF-");
    expect(content.toString("utf8")).toContain("Title: Hang Up First - Final Demo Cut");

    if (width === 1440) {
      const expectedDownloads: Array<{
        linkName: RegExp;
        filename: string;
        marker: string;
      }> = [
        {
          linkName: /risk-summary\.pdf/,
          filename: "risk-summary.pdf",
          marker: "Counts by category",
        },
        {
          linkName: /annotated-script\.md/,
          filename: "annotated-script.md",
          marker: "<!-- RISK-001",
        },
        {
          linkName: /Original source/,
          filename: "e2e-30min-public-security-en.md",
          marker: "# Hang Up First",
        },
      ];
      for (const expected of expectedDownloads) {
        const nextDownloadPromise = page.waitForEvent("download");
        await packageRegion.getByRole("link", { name: expected.linkName }).click();
        const nextDownload = await nextDownloadPromise;
        expect(nextDownload.suggestedFilename()).toBe(expected.filename);
        const nextDownloadedPath = await nextDownload.path();
        expect(nextDownloadedPath).not.toBeNull();
        const nextContent = await readFile(nextDownloadedPath!);
        if (expected.filename.endsWith(".pdf")) {
          expect(nextContent.subarray(0, 5).toString()).toBe("%PDF-");
        }
        expect(nextContent.toString("utf8")).toContain(expected.marker);
      }
    }
  });
}


test("the English 70-minute fixture produces distinct long-form intake", async ({ page }) => {
  await page.goto("/");
  await extractFixture(page, seventyMinuteFixture);

  await expect(page.getByLabel("Project title")).toHaveValue("The Blank Byline");
  await expect(page.getByText("7 episodes · 70 min · 28 scenes")).toBeVisible();
  await expect(page.getByLabel("Episode count")).toHaveValue("7");
  await expect(page.getByLabel("Minutes per episode")).toHaveValue("10");
  await expect(page.getByLabel("Tags")).toHaveValue(
    "judicial, authorship dispute, theater drama"
  );
  await expect(page.getByLabel("Tags")).not.toHaveValue(
    "public security, anti-fraud, family drama"
  );
  await expect(page.getByLabel("Synopsis")).toHaveValue(SEVENTY_MINUTE_SYNOPSIS);
  await expect(page.getByLabel("Synopsis")).not.toHaveValue(THIRTY_MINUTE_SYNOPSIS);
  await expect(page.getByRole("tab", { name: /Review results/ })).toBeDisabled();
  await expectNoHorizontalScroll(page);
});


test("visited progress tabs are keyboard navigable", async ({ page }) => {
  await page.goto("/");
  const fileInput = page.getByLabel("Choose a script");
  await expect(fileInput).toBeFocused();
  await fileInput.setInputFiles(thirtyMinuteFixture);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Extract project details" })).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(page.getByLabel("Project title")).toBeFocused();
  for (let index = 0; index < 6; index += 1) await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Confirm & analyze risks" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Review results" })).toBeFocused();

  const resultsTab = page.getByRole("tab", { name: /Review results/ });
  await resultsTab.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: /Confirm details/ })).toBeFocused();
  await expect(page.getByRole("tab", { name: /Confirm details/ })).toHaveAttribute(
    "aria-selected",
    "true"
  );
  await expect(page.getByLabel("Project title")).toHaveValue("Hang Up First");
});
