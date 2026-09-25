import { test, expect } from "@playwright/test";
const token = process.env.TEST_API_TOKEN || "local-demo-token-change-me";
test.beforeEach(async ({page}) => {
  await page.goto("/");
  await page.getByLabel("Analyst access token").fill(token);
  await page.getByRole("button", {name: "Open workspace"}).click();
  await expect(page.locator(".queue-row").first()).toBeVisible();
  await expect(page.getByRole("heading", {name: "Connected evidence"})).toBeVisible();
});

test("investigate, assess, export and audit", async ({page}) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await expect(page.locator(".graph-canvas canvas").first()).toBeVisible();
  await page.getByRole("button", {name: "Zoom in", exact:true}).click();
  await page.getByRole("button", {name: "Fit graph", exact:true}).click();
  await page.screenshot({path:"../../docs/screenshots/workspace.png", fullPage:true});
  await page.getByLabel("Disposition").selectOption("investigating");
  await page.getByLabel("Investigation note").fill("Demo walkthrough: shared infrastructure observed. Verify device ownership and customer context before escalation.");
  await page.getByRole("button", {name:"Save assessment"}).click();
  await expect(page.getByText("Assessment saved")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", {name:"Export case", exact:true}).click();
  expect((await download).suggestedFilename()).toContain("fraudgraph-case-");
  await page.getByRole("button", {name:"My cases", exact:true}).click();
  await expect(page.locator(".case-row").first()).toContainText("Demo walkthrough");
  await page.getByRole("button", {name:"Audit trail", exact:true}).click();
  await expect(page.getByText("case exported").first()).toBeVisible();
  await page.getByRole("button", {name:"Model registry", exact:true}).click();
  await expect(page.getByText("temporal-entity-snapshots-v2", {exact:true})).toBeVisible();
  expect(errors).toEqual([]);
});

test("filters, empty state and pagination", async ({page}) => {
  await page.getByRole("combobox", {name:"Risk", exact:true}).selectOption("0.5");
  await expect(page.locator(".queue-row").first()).toBeVisible();
  await page.getByLabel("Min. value").fill("100000000");
  await expect(page.getByText("No transactions match these filters.")).toBeVisible();
  await page.getByLabel("Min. value").fill("");
  await page.getByRole("combobox", {name:"Risk", exact:true}).selectOption("0");
  await expect(page.getByRole("button", {name:"Next page", exact:true})).toBeEnabled();
  await page.getByRole("button", {name:"Next page", exact:true}).click();
  await expect(page.getByText("31–60 of 360", {exact:true})).toBeVisible();
});

test("responsive layout and keyboard assessment", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.getByLabel("Investigation note").focus();
  await page.keyboard.type("Keyboard walkthrough: review pending.");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", {name:"Save assessment"})).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({path:"../../docs/screenshots/mobile.png", fullPage:true});
});

test("service error is visible and recoverable", async ({page}) => {
  await page.route("**/api/v1/alerts?**", route => route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Test service unavailable"})}));
  await page.getByRole("button", {name:"Refresh", exact:true}).click();
  await expect(page.locator(".error[role=alert]")).toContainText("Test service unavailable");
  await page.unroute("**/api/v1/alerts?**");
  await page.getByRole("button", {name:"Refresh", exact:true}).click();
  await expect(page.locator(".error[role=alert]")).toHaveCount(0);
});

test("entity exploration and persistent assessment", async ({page}) => {
  await page.getByText(/Accessible entity list/).click();
  await page.locator(".graph-list button").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Association summary, not an independent entity probability")).toBeVisible();
  await page.getByRole("button", {name:"Close entity details", exact:true}).click();
  await page.reload();
  await expect(page.locator(".saved-note").first()).toContainText("Demo walkthrough");
});
