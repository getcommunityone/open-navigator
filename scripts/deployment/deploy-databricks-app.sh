#!/usr/bin/env bash
#
# DEPRECATED SHIM. The old version built a non-existent `frontend/` dir and
# deployed the dead "oral-health-policy-pulse" app with hardcoded port 8000 and
# OpenAI/model-serving cruft. That whole approach is gone.
#
# The ready-to-deploy Databricks Apps config now lives in a self-contained app
# directory and is driven by its own build script:
#
#     apps/open-navigator-web/build.sh
#
# This shim just forwards there so existing references keep working. New work
# should call apps/open-navigator-web/build.sh directly.
#
# Usage (forwarded verbatim):
#   scripts/deployment/deploy-databricks-app.sh              # build + validate only
#   scripts/deployment/deploy-databricks-app.sh --deploy     # build + validate + deploy

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_BUILD="$REPO/apps/open-navigator-web/build.sh"

if [[ ! -x "$APP_BUILD" ]]; then
  echo "ERROR: $APP_BUILD not found or not executable." >&2
  echo "       The Databricks Apps config moved to apps/open-navigator-web/." >&2
  exit 1
fi

echo "==> Forwarding to apps/open-navigator-web/build.sh $*"
exec "$APP_BUILD" "$@"
