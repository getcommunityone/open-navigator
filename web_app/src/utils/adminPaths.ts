/** Admin area base path (operational tools behind the logged-in profile menu). */
export const ADMIN_BASE = '/admin'

/** Lighthouse data-quality scores from bronze (paired with accessibility batches). */
export const ADMIN_LIGHTHOUSE_REPORT = '/admin/lighthouse-report'

/** YouTube caption / policy pipeline batch job progress (live from API). */
export const ADMIN_BATCH_JOBS = '/admin/batch-jobs'

/**
 * Databricks (external) — the production Azure Databricks workspace
 * (`dbw-opennav-prod-eastus-001`) and the deployed Databricks App. These open
 * in a new tab and are surfaced only behind the admin-gated profile menu.
 */
export const DATABRICKS_WORKSPACE_URL = 'https://adb-7405608833986267.7.azuredatabricks.net'

/**
 * Deployed Databricks App URL (the running app itself, not the workspace manage
 * page): `https://<app-name>-<workspace-id>.<region>.azure.databricksapps.com/`.
 */
export const DATABRICKS_APP_URL = 'https://rag-chat-app-7405608833986267.7.azure.databricksapps.com/'
