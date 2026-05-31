# Council Data Project (CDP) ingestion

Lands meeting events from [Council Data Project](https://councildataproject.org/)
instances into `bronze.bronze_events_cdp`.

CDP runs per-jurisdiction deployments that index, archive, and transcribe
city/county council meetings. This pipeline does **not** use the `cdp-data`
PyPI package, which pins an old pandas and shells out to `pip install` at
runtime.

## ⚠️ Status: upstream is sunset — loader is structural-only

The DB target (`bronze.bronze_events_cdp`) and the pipeline plumbing
(validate → batch → upsert) are verified working. **Fetching is not, and cannot
be** against the current CDP infrastructure:

- The GraphQL endpoints in `events.py` are inherited from the legacy
  `scripts/datasources/cdp/` loader and never worked —
  `councildataproject.org` is a static GitHub Pages site (GET → 404, POST → 405),
  not a GraphQL gateway.
- CDP's real data lived in per-instance Google **Firestore** databases. As of
  **2026-05-30** those projects are deactivated: anonymous, ADC-authenticated,
  and REST (`firestore.googleapis.com`) reads all return `403 CONSUMER_INVALID`
  on the *owning* project — verified across `cdp-seattle-21723dcf`,
  `cdp-seattle-staging-dbengvtn`, and `cdp-denver-962aefef`. Firestore always
  bills the API call to the project that owns the database, so no external
  credential/quota project can read a deactivated CDP project. The static sites
  still load, but there is no live data behind them.

In short, CDP appears sunset and its data is not retrievable by anyone through
these backends. The table + pipeline stay as ready scaffolding in case CDP
revives or a replacement source appears; `fetch_instance()` would need rewiring
to whatever that new source is.

## Run

```bash
# One instance
python -m ingestion.cdp.events --instance seattle

# Limit events per instance (testing)
python -m ingestion.cdp.events --instance seattle --limit 50

# All instances, full reload
python -m ingestion.cdp.events --instance all --truncate

# Replay strictly from cache (offline) / force a re-fetch
python -m ingestion.cdp.events --instance portland --no-fetch
python -m ingestion.cdp.events --instance denver --refresh
```

The table is created idempotently on first run (matching migration
`086_create_bronze_events_cdp.sql`). Raw GraphQL responses are cached under
`data/cache/cdp/{instance}.json`; re-runs hit the cache unless `--refresh`.

Database target is resolved by `core_lib.db` from
`NEON_DATABASE_URL_DEV` / `NEON_DATABASE_URL` / `DATABASE_URL`.

## Available instances

| Instance | City/County | State |
|----------|-------------|-------|
| `seattle` | Seattle | WA |
| `portland` | Portland | OR |
| `boston` | Boston | MA |
| `denver` | Denver | CO |
| `king-county` | King County | WA |
| `alameda` | Alameda County | CA |
| `oakland` | Oakland | CA |
| `charlotte` | Charlotte | NC |
| `san-jose` | San José | CA |

## Field mapping (CDP → bronze)

| CDP GraphQL field | `bronze_events_cdp` column |
|-------------------|----------------------------|
| `eventDatetime` | `event_datetime` (+ derived `event_date`, `event_time`) |
| `body.name` | `body_name` |
| `body.description` | `body_description` |
| `agendaUri` | `agenda_url` |
| `minutesUri` | `minutes_url` |
| `id` | `external_source_id` |
| `sessions[0].videoUri` | `video_url` |
| `sessions[0].sessionContentHash` | `session_content_hash` |

`source` is always `cdp`; `datasource_id` carries the instance slug. The table
is a CDP-compatible superset shared with YouTube/LocalView events — YouTube-only
columns (`channel_id`, `view_count`, …) stay NULL for CDP rows.

## Downstream

```bash
./scripts/dbt.sh run --select stg_bronze_events_cdp event
```

`bronze_events_cdp → stg_bronze_events_cdp → event` (marts).

## Resources

- CDP site: https://councildataproject.org/
- CDP backend models: https://councildataproject.org/cdp-backend/database_models.html
