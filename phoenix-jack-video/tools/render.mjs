#!/usr/bin/env node
/**
 * Headless render automation for this canvas-commons project.
 *
 * canvas-commons has no headless CLI renderer — the render runs in the browser
 * (the @canvas-commons/ffmpeg vite plugin muxes the streamed frames into an MP4
 * under ./output). This script drives that flow with Playwright: it opens the
 * editor, switches to Video Settings, clicks RENDER, and waits for the MP4.
 *
 * Prereqs (already true in this repo):
 *   - the editor dev server is running on :9000  (`npm start`)
 *   - ffmpeg available; exporter is @canvas-commons/ffmpeg (set in project.meta)
 *   - Playwright + a Chromium are installed (we resolve Playwright from web_app)
 *
 * Run:
 *   # from phoenix-jack-video/, with Playwright on NODE_PATH:
 *   NODE_PATH=../web_app/node_modules node tools/render.mjs
 *   # options: EDITOR_URL (default http://localhost:9000), RENDER_TIMEOUT_MS
 */
import { createRequire } from 'node:module';
import { existsSync, readdirSync, statSync, mkdirSync, symlinkSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright'); // resolved via NODE_PATH=../web_app/node_modules

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'output');
const EDITOR_URL = process.env.EDITOR_URL || 'http://localhost:9000/';
const RENDER_TIMEOUT_MS = Number(process.env.RENDER_TIMEOUT_MS || 20 * 60 * 1000);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mp4s = () =>
  (existsSync(OUT) ? readdirSync(OUT) : [])
    .filter((f) => f.endsWith('.mp4'))
    .map((f) => ({ f, ...statSync(join(OUT, f)) }));

(async () => {
  if (!existsSync(OUT)) mkdirSync(OUT, { recursive: true });

  // The ffmpeg exporter feeds sound paths to ffmpeg as "audio/<f>.wav" (it
  // strips the leading "/" of the served URL), resolved relative to the project
  // CWD — but the WAVs live in public/audio. Without ./audio, ffmpeg exits 254
  // ("No such file or directory") and the render aborts. Make ./audio resolve.
  const audioLink = join(ROOT, 'audio');
  if (!existsSync(audioLink)) {
    try { symlinkSync('public/audio', audioLink); console.log('[render] linked ./audio -> public/audio'); }
    catch (e) { console.log('[render] WARN could not create ./audio symlink:', e.message); }
  }

  const before = new Set(mp4s().map((m) => m.f));

  console.log('[render] launching headless chromium');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
           '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
           // CRITICAL for headless render: Chrome throttles/pauses the rAF render
           // loop when the page is considered hidden/backgrounded, so canvas-commons
           // captures 0 frames and ffmpeg writes an empty MP4. Keep it running.
           '--disable-background-timer-throttling',
           '--disable-backgrounding-occluded-windows',
           '--disable-renderer-backgrounding',
           '--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage();
  await page.bringToFront().catch(() => {});
  page.on('pageerror', (e) => console.log('[page-error]', e.message.slice(0, 160)));
  page.on('console', (m) => {
    const t = m.text();
    if (/render|export|ffmpeg|error|finish|%/i.test(t)) console.log('[page]', t.slice(0, 160));
  });

  console.log('[render] opening editor', EDITOR_URL);
  await page.goto(EDITOR_URL, { waitUntil: 'commit', timeout: 30000 }).catch((e) => console.log('[goto]', e.message));

  // Wait for the editor UI to mount.
  let ready = false;
  for (let i = 0; i < 30; i++) {
    await sleep(2000);
    const n = await page.evaluate(() => document.querySelectorAll('button').length).catch(() => 0);
    if (n > 5) { ready = true; break; }
  }
  if (!ready) throw new Error('editor UI never mounted (is :9000 running?)');
  console.log('[render] editor ready');

  // Buttons may be icon-only (label lives in title/aria-label) or text ("RENDER").
  const click = async (label) => {
    const sel = `button:has-text("${label}"), button[aria-label="${label}"], button[title="${label}"]`;
    const btn = page.locator(sel).first();
    await btn.waitFor({ state: 'visible', timeout: 15000 });
    await btn.click();
  };

  // Video Settings is the default-open tab, so RENDER is usually already visible.
  // Only open the panel if it isn't (clicking the tab toggles it).
  const renderBtn = page.locator('button:has-text("RENDER")').first();
  if (!(await renderBtn.isVisible().catch(() => false))) {
    await click('Video Settings');
    await sleep(800);
  }
  console.log('[render] clicking RENDER (exporter=@canvas-commons/ffmpeg per project.meta)');
  await renderBtn.waitFor({ state: 'visible', timeout: 15000 });
  await renderBtn.click();

  // Wait for a new MP4 to appear and stop growing.
  const start = Date.now();
  let last = null, stableSince = null, target = null;
  while (Date.now() - start < RENDER_TIMEOUT_MS) {
    await sleep(3000);
    const fresh = mp4s().filter((m) => !before.has(m.f) || (target && m.f === target));
    if (fresh.length) {
      const newest = fresh.sort((a, b) => b.mtimeMs - a.mtimeMs)[0];
      target = newest.f;
      // Require a non-trivial size: a 0-frame render writes a ~48-byte empty
      // container, which must NOT count as success.
      if (last !== null && newest.size === last && newest.size > 100_000) {
        if (!stableSince) stableSince = Date.now();
        if (Date.now() - stableSince > 6000) {
          console.log(`[render] DONE -> output/${newest.f} (${(newest.size / 1e6).toFixed(1)} MB)`);
          await browser.close();
          process.exit(0);
        }
      } else {
        stableSince = null;
        console.log(`[render] writing output/${newest.f} ... ${(newest.size / 1e6).toFixed(1)} MB`);
      }
      last = newest.size;
    } else {
      const s = Math.round((Date.now() - start) / 1000);
      if (s % 15 === 0) console.log(`[render] rendering frames... ${s}s elapsed`);
    }
  }
  await browser.close();
  throw new Error('render timed out before producing an MP4');
})().catch((e) => { console.error('[render] FAILED:', e.message); process.exit(1); });
