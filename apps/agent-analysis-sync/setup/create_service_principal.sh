#!/usr/bin/env bash
# One-time setup of a Databricks Free Edition workspace for the `free` bundle target (#294), copied from the
# Health Transformation Lab's databricks/setup/create_service_principal.sh.
#
# Creates the identity CI deploys and runs as: service principal open_navigator_<target>_sp and admin group
# open_navigator_<target>_admin (you and the principal), assigned to this workspace. Free Edition has no account
# console, so it goes through the workspace's account SCIM proxy. It creates the catalog once with SQL (a Free
# Edition workspace with Default Storage can't create a catalog through the bundle's API) and gives the group ALL
# PRIVILEGES on it; the bundle deploy then creates the schemas and the crawl volume.
#
# The OAuth secret is not made here: the script prints the command, and the secret goes straight into GitHub
# (gh secret set), never into a file or chat. Run once, logged in as a workspace admin:
#   databricks auth login --host https://<workspace>
#   apps/agent-analysis-sync/setup/create_service_principal.sh free
#   apps/agent-analysis-sync/setup/create_service_principal.sh free --print-config   # names only, no calls
# Guide: web_docs/docs/deployment/databricks-free-edition.md
set -euo pipefail
target="${1:?target: free}"
shift
print_only=""
while [ $# -gt 0 ]; do
  case "$1" in
    --print-config) print_only=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
root="$(cd "$(dirname "$0")/.." && pwd)"
# catalog and warehouse name as the bundle resolves them for the target (default, then target override)
read -r catalog warehouse < <(python3 - "$root/databricks.yml" "$target" <<'EOF'
import sys, yaml
b = yaml.safe_load(open(sys.argv[1]))
if sys.argv[2] not in b["targets"]:
    sys.exit(f"no target {sys.argv[2]!r} in databricks.yml")
v = {k: x.get("default") for k, x in b["variables"].items()}
v.update(b["targets"][sys.argv[2]].get("variables", {}))
wh = v["warehouse_id"]
name = wh["lookup"]["warehouse"] if isinstance(wh, dict) else ""
print(v["catalog"], name.replace(" ", "_"))
EOF
)
warehouse="${warehouse//_/ }"
sp="open_navigator_${target}_sp"
group="open_navigator_${target}_admin"
if [ -n "$print_only" ]; then echo "$sp $group $catalog $warehouse"; exit 0; fi
json_field() { python3 -c "import json,sys; print(json.load(sys.stdin)['$1'])"; }

me=$(databricks current-user me -o json | json_field id)
sp_json=$(databricks api post /api/2.0/account/scim/v2/ServicePrincipals --json "{\"displayName\": \"$sp\", \"active\": true}")
sp_id=$(echo "$sp_json" | json_field id)
sp_app=$(echo "$sp_json" | json_field applicationId)
group_id=$(databricks api post /api/2.0/account/scim/v2/Groups \
             --json "{\"displayName\": \"$group\", \"members\": [{\"value\": \"$me\"}, {\"value\": \"$sp_id\"}]}" | json_field id)
for id in "$group_id" "$sp_id"; do
  databricks api put "/api/2.0/preview/permissionassignments/principals/$id" --json '{"permissions": ["USER"]}' > /dev/null
done
echo "created $sp (id $sp_id, application id $sp_app) and $group with you and the principal"
# without workspace-access every API call fails; without databricks-sql-access validate can't look up the warehouse
databricks service-principals patch "$sp_id" --json '{"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
  "Operations": [{"op": "add", "path": "entitlements", "value": [{"value": "workspace-access"}, {"value": "databricks-sql-access"}]}]}' > /dev/null

# the catalog, once, with SQL on the starter warehouse; then the group gets ALL PRIVILEGES on it
wh_id=$(databricks warehouses list -o json | python3 -c "import json,sys; n=sys.argv[1]; print(next(w['id'] for w in json.load(sys.stdin) if w['name']==n))" "$warehouse")
databricks api post /api/2.0/sql/statements --json \
  "{\"warehouse_id\": \"$wh_id\", \"statement\": \"CREATE CATALOG IF NOT EXISTS $catalog\", \"wait_timeout\": \"30s\"}" > /dev/null
databricks grants update catalog "$catalog" --json "{\"changes\": [{\"principal\": \"$group\", \"add\": [\"ALL_PRIVILEGES\"]}]}" > /dev/null
# the job runs as the principal and its SQL runs on the starter warehouse
databricks permissions update warehouses "$wh_id" \
  --json "{\"access_control_list\": [{\"service_principal_name\": \"$sp_app\", \"permission_level\": \"CAN_USE\"}]}" > /dev/null

repo="getcommunityone/open-navigator"
cat <<EOF
done: catalog $catalog (group $group has ALL PRIVILEGES), warehouse "$warehouse" usable by $sp.
next (web_docs/docs/deployment/databricks-free-edition.md):
  1. OAuth secret, 90 days; shown once, put it straight into GitHub:
       databricks service-principal-secrets-proxy create $sp_id --lifetime 7776000s
  2. GitHub environment $target:
       gh api -X PUT repos/$repo/environments/$target
       gh variable set DATABRICKS_HOST      -R $repo -e $target -b <workspace url>
       gh variable set DATABRICKS_CLIENT_ID -R $repo -e $target -b $sp_app
       gh secret set   DATABRICKS_CLIENT_SECRET -R $repo -e $target
  3. Actions > Deploy to Databricks Free Edition > Run workflow: it validates and deploys the free target.
EOF
