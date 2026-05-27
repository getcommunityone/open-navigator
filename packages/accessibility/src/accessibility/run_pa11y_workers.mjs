#!/usr/bin/env node
/**
 * Chunked Pa11y-CI runner with a worker pool (parallel child processes).
 *
 * Usage:
 *   node run_pa11y_workers.mjs --urls ../../data/cache/accessibility/urls.json
 *   PA11YCI_CONCURRENCY=8 WORKER_POOL_SIZE=4 node run_pa11y_workers.mjs --urls ...
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const out = { urls: "", out: "", workers: 0, chunk: 0 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--urls" && argv[i + 1]) out.urls = argv[++i];
    else if (a === "--out" && argv[i + 1]) out.out = argv[++i];
    else if (a === "--workers" && argv[i + 1]) out.workers = parseInt(argv[++i], 10);
    else if (a === "--chunk-size" && argv[i + 1]) out.chunk = parseInt(argv[++i], 10);
  }
  return out;
}

function loadExport(filePath) {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  const batchId = raw.batch_id || `pa11y-${Date.now()}`;
  const jobs = Array.isArray(raw.urls) ? raw.urls : raw;
  return { batchId, jobs };
}

function chunkArray(arr, size) {
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

/**
 * Pa11y-CI --json emits { total, passes, errors, results: { "<url>": Issue[] | [Error-ish] } }.
 * persist_results expects a list of { url, issues, error?, isError? } when scanner=pa11y.
 */
function flattenPa11yCiReport(part) {
  if (Array.isArray(part)) return part;
  if (!part || typeof part !== "object") return [];
  const results = part.results;
  const map =
    typeof results === "object" && results !== null ? results : part;
  if (typeof map !== "object" || map === null) return [];

  const out = [];
  for (const pageUrl of Object.keys(map)) {
    const raw = map[pageUrl];
    const url = String(pageUrl || "").trim();
    if (!url || !Array.isArray(raw)) continue;

    const issues = [];
    let errMsg = null;
    let isError = false;
    for (const item of raw) {
      if (
        item &&
        typeof item === "object" &&
        ("type" in item ||
          "code" in item ||
          "runner" in item ||
          "typeCode" in item ||
          ("message" in item && "elements" in item))
      ) {
        issues.push(item);
      } else if (
        item &&
        typeof item === "object" &&
        "message" in item &&
        raw.length === 1
      ) {
        // Pa11y-CI catches navigation failures as { message } (serialized Error).
        isError = true;
        errMsg = String(item.message ?? item);
      } else if (typeof item === "string") {
        isError = true;
        errMsg = item;
      }
    }

    const row = { url, issues };
    if (isError && errMsg != null && errMsg !== "") {
      row.error = errMsg;
      row.isError = true;
    }
    out.push(row);
  }
  return out;
}

function runPa11yChunk({ chunkIndex, urls, outDir, batchId }) {
  return new Promise((resolve, reject) => {
    // pa11y-ci strips only .js/.json extensions before load; .cjs is parsed as JSON and fails.
    const cfgPath = path.join(outDir, `pa11yci-chunk-${chunkIndex}.js`);
    const outPath = path.join(outDir, `pa11y-results-chunk-${chunkIndex}.json`);
    const baseCfg = path.join(__dirname, "pa11yci.config.cjs");
    const cfgBody = `const base = require(${JSON.stringify(baseCfg)});\nmodule.exports = {\n  ...base,\n  urls: ${JSON.stringify(urls)},\n};\n`;
    fs.writeFileSync(cfgPath, cfgBody);

    // pa11y-ci exits 2 when issue count >= threshold (default 0) — useless for bulk warehouse loads.
    // Override with PA11YCI_THRESHOLD=0 if you want process failure when any threshold is exceeded.
    const threshold = (process.env.PA11YCI_THRESHOLD ?? `${Number.MAX_SAFE_INTEGER}`).trim();
    const child = spawn(
      process.platform === "win32" ? "npx.cmd" : "npx",
      ["pa11y-ci", "--config", cfgPath, "--json", "--threshold", threshold],
      { cwd: __dirname, stdio: ["ignore", "pipe", "pipe"], env: process.env }
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("close", (code) => {
      if (code !== 0) {
        fs.writeFileSync(outPath + ".err.txt", stderr || stdout);
        reject(new Error(`pa11y-ci chunk ${chunkIndex} exited ${code}`));
        return;
      }
      fs.writeFileSync(outPath, stdout);
      resolve({ chunkIndex, outPath, batchId });
    });
  });
}

async function poolRun(tasks, poolSize) {
  const results = [];
  let idx = 0;
  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      results[i] = await tasks[i]();
    }
  }
  await Promise.all(Array.from({ length: poolSize }, () => worker()));
  return results;
}

async function main() {
  const args = parseArgs(process.argv);
  const urlsFile = path.resolve(args.urls || path.join(__dirname, "../../data/cache/accessibility/urls.json"));
  const { batchId, jobs } = loadExport(urlsFile);
  const pa11yUrls = jobs.map((j) => (typeof j === "string" ? j : j.url)).filter(Boolean);
  if (!pa11yUrls.length) {
    console.error("No URLs in export:", urlsFile);
    process.exit(1);
  }

  const outDir = path.resolve(
    args.out || path.join(__dirname, "../../data/cache/accessibility", `pa11y-${batchId}`)
  );
  fs.mkdirSync(outDir, { recursive: true });

  const chunkSize =
    args.chunk ||
    parseInt(process.env.WORKER_CHUNK_SIZE || "25", 10) ||
    25;
  const poolSize =
    args.workers ||
    parseInt(process.env.WORKER_POOL_SIZE || String(Math.min(4, os.cpus().length)), 10) ||
    4;

  const chunks = chunkArray(pa11yUrls, chunkSize);
  console.log(
    `Pa11y-CI: ${pa11yUrls.length} URL(s), ${chunks.length} chunk(s), pool=${poolSize}, chunk=${chunkSize}`
  );

  const metaPath = path.join(outDir, "urls.meta.json");
  fs.copyFileSync(urlsFile, metaPath);

  const tasks = chunks.map((urls, chunkIndex) => () =>
    runPa11yChunk({ chunkIndex, urls, outDir, batchId })
  );
  await poolRun(tasks, poolSize);

  const merged = [];
  for (let i = 0; i < chunks.length; i++) {
    const p = path.join(outDir, `pa11y-results-chunk-${i}.json`);
    if (!fs.existsSync(p)) continue;
    const part = JSON.parse(fs.readFileSync(p, "utf8"));
    merged.push(...flattenPa11yCiReport(part));
  }

  const mergedPath = path.join(outDir, "pa11y-results-merged.json");
  fs.writeFileSync(
    mergedPath,
    JSON.stringify({ batch_id: batchId, results: merged }, null, 2)
  );
  console.log(`Wrote ${merged.length} result(s) to ${mergedPath}`);
  console.log(`Persist: python -m scripts.accessibility.persist_results --scanner pa11y --input ${mergedPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
