import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e", timeout: 45000, workers: 1,
  use: {baseURL: process.env.WEB_URL || "http://127.0.0.1:3000", viewport: {width: 1440, height: 1100}, video: "on", trace: "retain-on-failure"},
  reporter: [["list"], ["html", {open: "never"}]],
});
