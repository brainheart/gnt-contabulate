const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 0,
  workers: 2,
  use: {
    baseURL: 'http://localhost:8775',
    headless: true,
  },
  webServer: {
    command: 'python3 -m http.server 8775 -d docs',
    port: 8775,
    stdout: 'ignore',
    stderr: 'ignore',
    reuseExistingServer: false,
  },
});
