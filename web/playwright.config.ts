import { defineConfig } from "@playwright/test";


const python = process.env.E2E_PYTHON ?? "python3";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "chrome",
    headless: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: `${python} -m uvicorn scripts.review_demo_server:app --host 127.0.0.1 --port 8080`,
      cwd: "..",
      env: {
        DEMO_LLM_BACKEND: "local",
      },
      url: "http://127.0.0.1:8080/healthz",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1",
      cwd: ".",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
