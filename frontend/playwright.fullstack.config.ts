import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  testMatch: /auction-r2-fullstack\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  outputDir: 'test-results-fullstack',
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-fullstack-report' }]],
  use: {
    baseURL: process.env.OXSTORE_FULLSTACK_BASE_URL || 'http://127.0.0.1:4174',
    channel: 'chrome',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
