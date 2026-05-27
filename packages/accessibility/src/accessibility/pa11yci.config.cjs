/**
 * Pa11y-CI defaults. URL list is injected per worker chunk via a generated config
 * (see run_pa11y_workers.mjs). Override concurrency with PA11YCI_CONCURRENCY.
 */
const concurrency = Math.max(
  1,
  parseInt(process.env.PA11YCI_CONCURRENCY || "5", 10) || 5
);

module.exports = {
  concurrency,
  defaults: {
    standard: process.env.PA11Y_STANDARD || "WCAG2AA",
    timeout: parseInt(process.env.PA11Y_TIMEOUT_MS || "60000", 10) || 60000,
    wait: parseInt(process.env.PA11Y_WAIT_MS || "1000", 10) || 1000,
    chromeLaunchConfig: {
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
    headers: {
      "User-Agent":
        process.env.ACCESSIBILITY_USER_AGENT ||
        "OpenNavigator-AccessibilityBot/1.0 (+https://www.communityone.com)",
    },
  },
  urls: [],
};
