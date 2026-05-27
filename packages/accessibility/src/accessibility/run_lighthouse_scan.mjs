#!/usr/bin/env node
/**
 * Lighthouse (Chrome Launcher) batch runner for jurisdiction homepages.
 * Writes NDJSON for scripts.accessibility.persist_lighthouse_results.
 *
 * Reuse the **same urls.json batch_id** as axe so rows join in
 * public.v_jurisdiction_audits_axe_lighthouse.
 *
 * Sequential runs against one Chrome instance (lighter than spawning Chrome per URL).
 * Scale out with Lambda / multiple hosts using export_urls --limit/--offset shards.
 *
 * Usage:
 *   node run_lighthouse_scan.mjs --urls ../../data/cache/accessibility/urls.json
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import lighthouse from "lighthouse";
import * as chromeLauncher from "chrome-launcher";
import { executablePath as puppeteerExecutablePath } from "puppeteer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Match axe (`run_axe_scan.mjs`) so both engines behave similarly toward origin servers / WAF. */
const ACCESSIBILITY_USER_AGENT =
  process.env.ACCESSIBILITY_USER_AGENT ||
  "OpenNavigator-AccessibilityBot/1.0 (+https://www.communityone.com)";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function navTimeoutMs() {
  const fromAxe = parseInt(process.env.AXE_NAV_TIMEOUT_MS || "0", 10);
  const lhOnly = parseInt(process.env.LIGHTHOUSE_MAX_WAIT_FOR_LOAD_MS || "0", 10);
  if (lhOnly > 0) return lhOnly;
  if (fromAxe > 0) return fromAxe;
  return 60000;
}

function navRetries() {
  const lhOnly = parseInt(process.env.LIGHTHOUSE_NAV_RETRIES || "0", 10);
  if (lhOnly > 0) return Math.max(1, lhOnly);
  return Math.max(1, parseInt(process.env.AXE_NAV_RETRIES || "3", 10) || 3);
}

function retryBackoffMs() {
  const lhOnly = parseInt(process.env.LIGHTHOUSE_RETRY_BACKOFF_MS || "0", 10);
  if (lhOnly > 0) return lhOnly;
  return parseInt(process.env.AXE_RETRY_BACKOFF_MS || "2500", 10) || 2500;
}

function chromeFlagsResolved() {
  if (process.env.LIGHTHOUSE_CHROME_FLAGS?.trim()) {
    return process.env.LIGHTHOUSE_CHROME_FLAGS.trim().split(/\s+/).filter(Boolean);
  }
  const flags = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu", "--disable-dev-shm-usage"];
  if (process.env.AXE_HEADLESS !== "false") {
    flags.unshift("--headless=new");
  }
  return flags;
}

function parseCategories() {
  const raw = (process.env.LIGHTHOUSE_CATEGORIES || "accessibility,performance,best-practices").trim();
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

function parseArgs(argv) {
  const out = { urls: "", out: "", limit: 0, offset: 0 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--urls" && argv[i + 1]) out.urls = argv[++i];
    else if (a === "--out" && argv[i + 1]) out.out = argv[++i];
    else if (a === "--limit" && argv[i + 1]) out.limit = parseInt(argv[++i], 10);
    else if (a === "--offset" && argv[i + 1]) out.offset = parseInt(argv[++i], 10);
  }
  return out;
}

function loadExport(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const batchId = raw.batch_id || `lh-${Date.now()}`;
  const jobs = Array.isArray(raw.urls) ? raw.urls : raw;
  return { batchId, jobs };
}

function scoresFromLhr(lhr) {
  const s = {};
  const cats = lhr?.categories;
  if (!cats) return s;
  for (const key of ["accessibility", "performance", "best-practices"]) {
    const id = key === "best-practices" ? "best-practices" : key;
    const cat = cats[id];
    if (cat?.score != null) s[id] = Math.round(cat.score * 100);
  }
  return s;
}

async function lighthouseOne(url, job, chromePort) {
  const meta = typeof job === "object" && job !== null ? job : { url };
  const maxAttempts = navRetries();
  const backoffMs = retryBackoffMs();
  const maxWaitForLoad = navTimeoutMs();

  let lastErr;
  const startedOuter = Date.now();
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    /** @type {import('lighthouse').Flags} */
    const flags = {
      port: chromePort,
      logLevel: process.env.LIGHTHOUSE_LOG_LEVEL || "error",
      output: "json",
      onlyCategories: parseCategories(),
      maxWaitForLoad,
      emulatedUserAgent: ACCESSIBILITY_USER_AGENT,
      formFactor: "desktop",
      screenEmulation: {
        width: 1280,
        height: 720,
        deviceScaleFactor: 1,
        mobile: false,
        disabled: false,
      },
    };
    try {
      const runnerResult = await lighthouse(url, flags);
      const lhr = runnerResult?.lhr;
      const scores = scoresFromLhr(lhr);
      return {
        status: "ok",
        meta,
        url,
        final_url: lhr?.finalDisplayedUrl ?? lhr?.finalUrl ?? url,
        scanned_at: new Date().toISOString(),
        scan_duration_ms: Date.now() - startedOuter,
        lighthouse_version: lhr?.lighthouseVersion,
        scores,
        lhr,
        lh_attempts: attempt,
      };
    } catch (err) {
      lastErr = err;
      if (attempt < maxAttempts) await sleep(backoffMs * attempt);
    }
  }
  return {
    status: "error",
    meta,
    url,
    error: String(lastErr?.message || lastErr),
    scanned_at: new Date().toISOString(),
    scan_duration_ms: Date.now() - startedOuter,
    lh_attempts: maxAttempts,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const urlsFile = path.resolve(
    args.urls || path.join(__dirname, "../../data/cache/accessibility/urls.json")
  );
  const { batchId, jobs: allJobs } = loadExport(urlsFile);
  let jobs = allJobs;
  if (args.offset) jobs = jobs.slice(args.offset);
  if (args.limit) jobs = jobs.slice(0, args.limit);

  const outPath = path.resolve(
    args.out ||
      path.join(__dirname, "../../data/cache/accessibility", `lighthouse-${batchId}.ndjson`)
  );
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const metaCopy = path.join(path.dirname(outPath), "urls.meta.json");
  if (!fs.existsSync(metaCopy)) fs.copyFileSync(urlsFile, metaCopy);

  const restartEvery = Math.max(
    0,
    parseInt(process.env.LIGHTHOUSE_CHROME_RESTART_EVERY || "0", 10) || 0
  );

  const chromeFlags = chromeFlagsResolved();

  /** Avoid chrome-launcher WSL bug: makeTmpDir() can yield a Windows TEMP path that is not absolute on Linux, so profiles appear as literal dirs under cwd (e.g. `C:\\Users\\...\\lighthouse.*`). */
  const chromeUserDataDir =
    process.env.LIGHTHOUSE_CHROME_USER_DATA_DIR?.trim() ||
    fs.mkdtempSync(path.join(os.tmpdir(), "open-nav-lighthouse-"));

  let chrome;
  async function launchChrome() {
    chrome = await chromeLauncher.launch({
      chromePath:
        process.env.LIGHTHOUSE_CHROME_PATH?.trim() || puppeteerExecutablePath(),
      chromeFlags,
      userDataDir: chromeUserDataDir,
    });
  }

  await launchChrome();
  const out = fs.createWriteStream(outPath, { flags: "w" });

  console.log(
    `lighthouse: ${jobs.length} URL(s), categories=${parseCategories().join(",")}, batch=${batchId}`
  );
  let done = 0;
  try {
    for (let i = 0; i < jobs.length; i++) {
      const job = jobs[i];
      const url = typeof job === "string" ? job : job.url;
      if (!url) continue;

      if (restartEvery > 0 && i > 0 && i % restartEvery === 0) {
        try {
          chrome.kill();
        } catch {
          /* noop */
        }
        await launchChrome();
      }

      const port = chrome.port;
      const rec = await lighthouseOne(url, job, port);
      rec.batch_id = batchId;
      out.write(JSON.stringify(rec) + "\n");

      done += 1;
      if (done % 10 === 0) console.log(`  scanned ${done}/${jobs.length}`);
    }
  } finally {
    try {
      chrome?.kill?.();
    } catch {
      /* noop */
    }
    out.end();
    if (!process.env.LIGHTHOUSE_CHROME_USER_DATA_DIR?.trim()) {
      try {
        fs.rmSync(chromeUserDataDir, { recursive: true, force: true });
      } catch {
        /* noop */
      }
    }
  }

  console.log(`Wrote NDJSON to ${outPath}`);
  console.log(
    `Persist: python -m scripts.accessibility.persist_lighthouse_results --ensure-ddl --input ${outPath}`
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
