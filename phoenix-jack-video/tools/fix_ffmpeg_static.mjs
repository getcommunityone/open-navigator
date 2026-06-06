// The bundled `ffmpeg-ffprobe-static` binaries are unreliable in some
// environments (e.g. WSL2: ffmpeg lands non-executable/corrupt and ffprobe
// fails to extract). When that happens, the canvas-commons ffmpeg exporter —
// which hardcodes this package's binary paths — can't spawn ffmpeg, frames pile
// up in memory, and the dev server OOMs mid-render ("Failed to fetch").
//
// This script repoints the package's `ffmpeg`/`ffprobe` paths at the working
// system binaries when the bundled ones are missing or not executable. Wired as
// a postinstall hook so it survives `npm install` / `npm ci`. No-op when the
// bundled binaries already work.
import {accessSync, constants, existsSync, lstatSync, readFileSync, renameSync, symlinkSync, writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);

function systemPath(bin) {
  try {
    return execFileSync('which', [bin]).toString().trim() || null;
  } catch {
    return null;
  }
}

function usable(p) {
  try {
    accessSync(p, constants.X_OK);
    execFileSync(p, ['-version'], {stdio: 'ignore'});
    return true;
  } catch {
    return false;
  }
}

let staticPaths;
try {
  staticPaths = require('ffmpeg-ffprobe-static');
} catch {
  console.log('[fix-ffmpeg-static] ffmpeg-ffprobe-static not installed; skipping.');
  process.exit(0);
}

for (const [name, bundled] of [
  ['ffmpeg', staticPaths.ffmpegPath],
  ['ffprobe', staticPaths.ffprobePath],
]) {
  if (usable(bundled)) {
    console.log(`[fix-ffmpeg-static] bundled ${name} works; leaving as-is.`);
    continue;
  }
  const sys = systemPath(name);
  if (!sys) {
    console.warn(`[fix-ffmpeg-static] bundled ${name} broken and no system ${name} found on PATH.`);
    continue;
  }
  if (existsSync(bundled) && !lstatSync(bundled).isSymbolicLink()) {
    renameSync(bundled, `${bundled}.broken.bak`);
  } else if (existsSync(bundled)) {
    // stale symlink — remove before recreating
    renameSync(bundled, `${bundled}.broken.bak`);
  }
  symlinkSync(sys, bundled);
  console.log(`[fix-ffmpeg-static] linked ${name} -> ${sys}`);
}

// --- Patch 2: x264 preset --------------------------------------------------
// The exporter encodes with x264's default ("medium") preset, which only
// manages ~0.3x realtime at 1080x1920. The renderer produces frames much
// faster than that, so the server's in-memory frame queue grows unbounded and
// the dev server OOMs mid-render ("Failed to fetch"). `-preset ultrafast`
// pushes encoding past realtime so the queue drains and memory stays bounded.
try {
  // The package's `exports` map blocks require.resolve of internal files, so
  // search standard node_modules locations for the server bundle instead.
  const here = path.dirname(fileURLToPath(import.meta.url));
  const rel = path.join('node_modules', '@canvas-commons', 'ffmpeg', 'lib', 'server', 'index.js');
  const serverFile = [
    path.join(here, '..', rel), // project-local node_modules
    path.join(process.cwd(), rel), // cwd node_modules
  ].map((p) => path.resolve(p)).find((p) => existsSync(p));
  if (!serverFile) throw new Error('@canvas-commons/ffmpeg server bundle not found');
  const src = readFileSync(serverFile, 'utf8');
  const marker = '"-pix_fmt yuv420p", `-t ${settings.duration / settings.fps}`';
  const patched = '"-pix_fmt yuv420p", "-preset ultrafast", "-threads 0", `-t ${settings.duration / settings.fps}`';
  if (src.includes(patched)) {
    console.log('[fix-ffmpeg-static] x264 preset patch already applied.');
  } else if (src.includes(marker)) {
    writeFileSync(serverFile, src.replace(marker, patched));
    console.log('[fix-ffmpeg-static] applied -preset ultrafast to exporter output options.');
  } else {
    console.warn('[fix-ffmpeg-static] could not find output-options marker to patch (plugin version changed?).');
  }
} catch (e) {
  console.warn(`[fix-ffmpeg-static] preset patch skipped: ${e.message}`);
}
