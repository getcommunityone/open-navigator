#!/usr/bin/env node
/**
 * axe-core + Puppeteer batch scanner for jurisdiction homepages.
 * Writes NDJSON for accessibility.persist_results.
 *
 * Usage:
 *   node run_axe_scan.mjs --urls ../../data/cache/accessibility/urls.json
 *   AXE_CONCURRENCY=10 node run_axe_scan.mjs --urls ... --limit 100
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer";
import { AxePuppeteer } from "@axe-core/puppeteer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const UA =
  process.env.ACCESSIBILITY_USER_AGENT ||
  "OpenNavigator-AccessibilityBot/1.0 (+https://www.communityone.com)";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseArgs(argv) {
  const out = { urls: "", out: "", limit: 0, offset: 0, concurrency: 0 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--urls" && argv[i + 1]) out.urls = argv[++i];
    else if (a === "--out" && argv[i + 1]) out.out = argv[++i];
    else if (a === "--limit" && argv[i + 1]) out.limit = parseInt(argv[++i], 10);
    else if (a === "--offset" && argv[i + 1]) out.offset = parseInt(argv[++i], 10);
    else if (a === "--concurrency" && argv[i + 1])
      out.concurrency = parseInt(argv[++i], 10);
  }
  return out;
}

function loadExport(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const batchId = raw.batch_id || `axe-${Date.now()}`;
  let jobs = Array.isArray(raw.urls) ? raw.urls : raw;
  return { batchId, jobs };
}

async function scanOne(browser, job) {
  const url = typeof job === "string" ? job : job.url;
  const meta = typeof job === "object" && job !== null ? job : { url };
  const maxAttempts = Math.max(
    1,
    parseInt(process.env.AXE_NAV_RETRIES || "3", 10) || 3
  );
  const backoffMs = parseInt(process.env.AXE_RETRY_BACKOFF_MS || "2500", 10) || 2500;
  const navTimeout = parseInt(process.env.AXE_NAV_TIMEOUT_MS || "45000", 10) || 45000;

  let lastErr;
  const startedOuter = Date.now();
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const page = await browser.newPage();
    try {
      await page.setUserAgent(UA);
      await page.setViewport({ width: 1280, height: 720 });
      await page.setDefaultNavigationTimeout(navTimeout);

      const response = await page.goto(url, {
        waitUntil: "domcontentloaded",
        timeout: navTimeout,
      });
      const httpStatus = response ? response.status() : null;
      const finalUrl = page.url();
      const pageTitle = await page.title();
      const axeResults = await new AxePuppeteer(page).analyze();
      await page.close().catch(() => {});
      return {
        status: "ok",
        meta,
        url,
        final_url: finalUrl,
        http_status: httpStatus,
        page_title: pageTitle,
        scanned_at: new Date().toISOString(),
        scan_duration_ms: Date.now() - startedOuter,
        axe: axeResults,
        nav_attempts: attempt,
      };
    } catch (err) {
      lastErr = err;
      await page.close().catch(() => {});
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
    nav_attempts: maxAttempts,
  };
}

async function poolMap(items, concurrency, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i], i);
    }
  }
  await Promise.all(
    Array.from({ length: Math.min(concurrency, items.length) }, () => worker())
  );
  return results;
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

  const concurrency =
    args.concurrency ||
    parseInt(process.env.AXE_CONCURRENCY || "5", 10) ||
    5;

  const outPath = path.resolve(
    args.out ||
      path.join(__dirname, "../../data/cache/accessibility", `axe-${batchId}.ndjson`)
  );
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const metaCopy = path.join(path.dirname(outPath), "urls.meta.json");
  if (!fs.existsSync(metaCopy)) fs.copyFileSync(urlsFile, metaCopy);

  const out = fs.createWriteStream(outPath, { flags: "w" });
  const browser = await puppeteer.launch({
    headless: process.env.AXE_HEADLESS !== "false",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  console.log(`axe: ${jobs.length} URL(s), concurrency=${concurrency}, batch=${batchId}`);
  let done = 0;
  await poolMap(
    jobs,
    concurrency,
    async (job) => {
      const rec = await scanOne(browser, job);
      rec.batch_id = batchId;
      out.write(JSON.stringify(rec) + "\n");
      done += 1;
      if (done % 50 === 0) console.log(`  scanned ${done}/${jobs.length}`);
      return rec;
    }
  );

  await browser.close();
  out.end();
  console.log(`Wrote NDJSON to ${outPath}`);
  console.log(
    `Persist: python -m accessibility.persist_results --scanner axe --input ${outPath} --ensure-ddl`
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
