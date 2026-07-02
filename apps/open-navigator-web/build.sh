#!/usr/bin/env bash
#
# Build + stage the Open Navigator web app for Databricks Apps, then validate the
# bundle. Does NOT deploy unless --deploy is passed (deploy needs explicit user
# consent). Mirrors the HuggingFace Dockerfile's build, adapted to a SINGLE
# process with no nginx (FastAPI serves the SPA + docs directly).
#
# Usage:
#   ./build.sh                 # build frontend+docs, stage source, validate
#   ./build.sh --skip-build    # re-stage + validate without rebuilding npm
#   ./build.sh --deploy        # build + stage + validate + deploy (CONSENT REQUIRED)
#
# Prereqs: node/npm, python, databricks CLI (profile opennav-prod authed).

set -euo pipefail

PROFILE="opennav-prod"
TARGET="dev"
APP_NAME="open-navigator"
MAX_BYTES=10485760            # 10 MB per-file Databricks Apps limit

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # apps/open-navigator-web
REPO="$(cd "$HERE/../.." && pwd)"                       # repo root

DO_BUILD=1
DO_DEPLOY=0
for arg in "$@"; do
  case "$arg" in
    --skip-build) DO_BUILD=0 ;;
    --deploy)     DO_DEPLOY=1 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

# --------------------------------------------------------------------------
# 1. Build the docs (Docusaurus) and frontend (Vite) from the repo source.
#    Vite outDir is ../api/static (see web_app/vite.config.ts), so the SPA lands
#    in api/static. Docusaurus is built with base /docs/ and copied to
#    api/static/docs so FastAPI serves it at /docs/.
# --------------------------------------------------------------------------
if [[ "$DO_BUILD" == "1" ]]; then
  log "Building Docusaurus docs (base=/docs/)"
  pushd "$REPO/web_docs" >/dev/null
  npm ci --prefer-offline --no-audit || npm install --no-audit
  DOCUSAURUS_BASE_URL=/docs/ npm run build
  popd >/dev/null

  log "Building React frontend (Vite -> api/static)"
  pushd "$REPO/web_app" >/dev/null
  npm ci --prefer-offline --no-audit || npm install --no-audit
  VITE_API_URL=/api npm run build
  popd >/dev/null

  log "Placing built docs under api/static/docs"
  rm -rf "$REPO/api/static/docs"
  mkdir -p "$REPO/api/static/docs"
  cp -r "$REPO/web_docs/build/." "$REPO/api/static/docs/"
else
  log "Skipping npm build (--skip-build)"
fi

# --------------------------------------------------------------------------
# 2. Stage the repo source into the app dir (self-contained bundle source root).
#    Preserve the SAME relative layout the code expects (api/, packages/,
#    scripts/, web_app/public/) so main.py's Path(...).parent logic is unchanged.
#    node_modules / .git / caches are excluded; >10 MB files are stripped after.
# --------------------------------------------------------------------------
log "Staging source trees into $HERE"
RSYNC_EXCL=(--exclude '__pycache__' --exclude '*.pyc' --exclude '.git')

stage() {  # stage <relpath>
  local rel="$1"
  rm -rf "${HERE:?}/$rel"
  mkdir -p "$HERE/$(dirname "$rel")"
  rsync -a "${RSYNC_EXCL[@]}" "$REPO/$rel/" "$HERE/$rel/"
}

stage api
stage packages
stage scripts

# web_app/public is needed for the /static and /data mounts (census map JSONs,
# logos, pdfs). It is partly git-ignored (the /data marts), so copy from the live
# working tree. node_modules/src/etc are NOT copied — only public.
log "Staging web_app/public (static assets + /data marts)"
rm -rf "$HERE/web_app/public"
mkdir -p "$HERE/web_app/public"
rsync -a "${RSYNC_EXCL[@]}" "$REPO/web_app/public/" "$HERE/web_app/public/"

# --------------------------------------------------------------------------
# 3. Strip files over the 10 MB per-file limit (e.g. web_app/public/wikicommons/
#    GA_latest.jpg ~36 MB). Same policy the HF deploy uses. These are decorative
#    state photos; their absence degrades gracefully (broken <img>), it does not
#    break the app.
# --------------------------------------------------------------------------
log "Stripping files larger than 10 MB (Databricks Apps per-file limit)"
BIG=$(find "$HERE/api" "$HERE/packages" "$HERE/scripts" "$HERE/web_app" \
        -type f -size +"$MAX_BYTES"c 2>/dev/null || true)
if [[ -n "$BIG" ]]; then
  while IFS= read -r f; do
    printf '   removing %s (%s)\n' "${f#"$HERE"/}" "$(du -h "$f" | cut -f1)"
    rm -f "$f"
  done <<< "$BIG"
else
  echo "   none found"
fi

# Sanity: the SPA build must be present after staging.
if [[ ! -f "$HERE/api/static/index.html" ]]; then
  echo "ERROR: api/static/index.html missing after staging — did the Vite build run?" >&2
  echo "       Re-run without --skip-build." >&2
  exit 1
fi

# --------------------------------------------------------------------------
# 4. Validate the bundle. (databricks apps validate is Node-project oriented;
#    for this Python app we validate the DAB instead.)
# --------------------------------------------------------------------------
log "Validating bundle (target=$TARGET, profile=$PROFILE)"
databricks bundle validate -t "$TARGET" --profile "$PROFILE"

if [[ "$DO_DEPLOY" != "1" ]]; then
  cat <<EOF

✅ Build + stage + validate complete. NOT deployed.

To deploy when ready (requires consent + MANAGE on the 'open-navigator' secret scope):
   cd $HERE
   databricks bundle deploy -t $TARGET --profile $PROFILE
   databricks bundle run $APP_NAME -t $TARGET --profile $PROFILE
EOF
  exit 0
fi

# --------------------------------------------------------------------------
# 5. Deploy (only with --deploy).
# --------------------------------------------------------------------------
log "Deploying bundle (target=$TARGET, profile=$PROFILE)"
databricks bundle deploy -t "$TARGET" --profile "$PROFILE"
log "Starting app: $APP_NAME"
databricks bundle run "$APP_NAME" -t "$TARGET" --profile "$PROFILE"
log "Done. Check status: databricks apps get $APP_NAME --profile $PROFILE -o json"
